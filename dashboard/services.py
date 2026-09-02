
"""
KUCSA Dashboard Services
========================

Centralized service layer for preparing dashboard data.

Architecture
------------

    Dashboard View
          │
          ▼
    DashboardService
          │
          ├── Members
          ├── Executives
          ├── Events
          ├── Attendance
          ├── Announcements
          └── Payments


Responsibilities
----------------

DashboardService is responsible for:

- Collecting dashboard data.
- Calculating dashboard statistics.
- Preparing data for dashboard templates.
- Reading data from other applications.

DashboardService is NOT responsible for:

- Authorization.
- Payment processing.
- Payment verification.
- M-Pesa operations.
- Financial transaction creation.
- Membership activation.
- Creating attendance sessions.
- Opening attendance sessions.
- Closing attendance sessions.
- Marking attendance.
- Expiring attendance sessions.

Authorization
-------------

Authorization is handled by the appropriate permission layer.

Finance management access remains controlled by:

    finance/permissions.py

Current Finance management roles:

    - ADMIN
    - TREASURER

A user only receives Treasurer-level Finance access after
an administrator explicitly assigns:

    User.Role.TREASURER

Being:

    - verified
    - active
    - an executive
    - is_staff
    - is_superuser

does not automatically grant Treasurer-level Finance authority.

Payment Processing
------------------

Payment processing remains the responsibility of the
payments application.

This service only READS payment information for dashboard
statistics.

Attendance
----------

KUCSA attendance is a standalone system.

It is NOT connected to:

    - Event
    - EventRegistration
    - Event participation

Standalone attendance is calculated from:

    AttendanceSession
            │
            └── AttendanceRecord

Attendance records contain:

    - PENDING
    - PRESENT
    - ABSENT
    - EXCUSED

Attendance sources contain:

    - SELF
    - MANUAL
    - SYSTEM

The dashboard service only reads attendance information.

Attendance business operations remain in:

    attendance.services
"""


from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone

from announcements.services import (
    get_active_announcements,
    get_announcements_for_user,
)
from attendance.models import (
    AttendanceRecord,
    AttendanceSession,
)
from events.models import Event, EventRegistration
from executives.models import Executive
from members.models import Member
from payments.models import (
    Payment,
    PaymentStatus,
    PaymentType,
)


User = get_user_model()


class DashboardService:
    """
    Central service for collecting and preparing KUCSA
    dashboard data.

    The service is the single source of truth for dashboard
    calculations.

    It does not perform authorization or mutate business data.
    """

    # =========================================================================
    # COMMON STATISTICS
    # =========================================================================

    @staticmethod
    def get_common_widgets():
        """
        Return statistics shared across dashboards.
        """

        return {
            "total_users": User.objects.count(),

            "verified_users": User.objects.filter(
                is_verified=True
            ).count(),

            "pending_users": User.objects.filter(
                is_verified=False
            ).count(),
        }

    # =========================================================================
    # ANNOUNCEMENTS
    # =========================================================================

    @staticmethod
    def get_announcement_statistics(user=None):
        """
        Return active announcements.

        If a user is supplied, announcements are filtered
        according to the announcement service's rules.

        If no user is supplied, all active announcements
        are returned.
        """

        if user is not None:
            announcements = get_announcements_for_user(user)
        else:
            announcements = get_active_announcements()

        announcements = announcements.order_by(
            "-created_at"
        )

        return {
            "announcements": announcements,
            "announcement_count": announcements.count(),
        }

    # =========================================================================
    # PAYMENT STATISTICS
    # =========================================================================

    @staticmethod
    def get_payment_statistics():
        """
        Return organization-wide payment statistics.

        This method is READ-ONLY.

        It does not:

        - verify payments
        - reject payments
        - modify payment status
        - activate memberships
        - initiate M-Pesa payments
        - create financial transactions

        Completed payments are treated as received income
        for dashboard reporting.

        Pending payments are reported separately and are
        excluded from received income.
        """

        pending_status = PaymentStatus.PENDING
        completed_status = PaymentStatus.COMPLETED
        failed_status = PaymentStatus.FAILED
        cancelled_status = PaymentStatus.CANCELLED

        # ---------------------------------------------------------------------
        # PAYMENT COUNTS
        # ---------------------------------------------------------------------

        total_payments = Payment.objects.count()

        pending_payments = Payment.objects.filter(
            status=pending_status
        ).count()

        completed_payments = Payment.objects.filter(
            status=completed_status
        ).count()

        failed_payments = Payment.objects.filter(
            status=failed_status
        ).count()

        cancelled_payments = Payment.objects.filter(
            status=cancelled_status
        ).count()

        # ---------------------------------------------------------------------
        # PAYMENT AMOUNTS
        # ---------------------------------------------------------------------

        completed_amount = (
            Payment.objects
            .filter(status=completed_status)
            .aggregate(total=Sum("amount"))
            .get("total")
            or Decimal("0.00")
        )

        pending_amount = (
            Payment.objects
            .filter(status=pending_status)
            .aggregate(total=Sum("amount"))
            .get("total")
            or Decimal("0.00")
        )

        # ---------------------------------------------------------------------
        # MEMBERSHIP PAYMENTS
        # ---------------------------------------------------------------------

        membership_payments = Payment.objects.filter(
            payment_type=PaymentType.MEMBERSHIP
        )

        membership_payment_count = (
            membership_payments.count()
        )

        membership_income = (
            membership_payments
            .filter(status=completed_status)
            .aggregate(total=Sum("amount"))
            .get("total")
            or Decimal("0.00")
        )

        # ---------------------------------------------------------------------
        # SUPPORT PAYMENTS
        # ---------------------------------------------------------------------

        support_payments = Payment.objects.filter(
            payment_type=PaymentType.SUPPORT
        )

        support_payment_count = (
            support_payments.count()
        )

        support_income = (
            support_payments
            .filter(status=completed_status)
            .aggregate(total=Sum("amount"))
            .get("total")
            or Decimal("0.00")
        )

        # ---------------------------------------------------------------------
        # TOTAL RECEIVED INCOME
        # ---------------------------------------------------------------------

        total_received_income = (
            membership_income
            + support_income
        )

        return {
            # Payment counts
            "total_payments": total_payments,
            "pending_payments": pending_payments,
            "completed_payments": completed_payments,
            "failed_payments": failed_payments,
            "cancelled_payments": cancelled_payments,

            # Payment amounts
            "completed_amount": completed_amount,
            "pending_amount": pending_amount,
            "total_received_income": total_received_income,

            # Membership payments
            "membership_payment_count": (
                membership_payment_count
            ),
            "membership_income": membership_income,

            # Support payments
            "support_payment_count": (
                support_payment_count
            ),
            "support_income": support_income,
        }

    # =========================================================================
    # STANDALONE ATTENDANCE STATISTICS
    # =========================================================================

    @staticmethod
    def get_attendance_statistics():
        """
        Return organization-wide standalone attendance statistics.

        Attendance is completely independent from events.

        Data source:

            AttendanceSession
                    │
                    └── AttendanceRecord

        This method is READ-ONLY.

        It does not:

        - create attendance sessions
        - open attendance sessions
        - close attendance sessions
        - mark attendance
        - expire attendance sessions
        - modify attendance records

        Session expiry and attendance state changes remain the
        responsibility of attendance.services.
        """

        session_status = AttendanceSession.SessionStatus
        attendance_status = (
            AttendanceRecord.AttendanceStatus
        )
        attendance_source = (
            AttendanceRecord.AttendanceSource
        )

        now = timezone.now()

        # ---------------------------------------------------------------------
        # SESSION COUNTS
        # ---------------------------------------------------------------------

        total_sessions = (
            AttendanceSession.objects.count()
        )

        draft_sessions = (
            AttendanceSession.objects.filter(
                status=session_status.DRAFT
            ).count()
        )

        open_sessions = (
            AttendanceSession.objects.filter(
                status=session_status.OPEN
            ).count()
        )

        closed_sessions = (
            AttendanceSession.objects.filter(
                status=session_status.CLOSED
            ).count()
        )

        expired_sessions = (
            AttendanceSession.objects.filter(
                status=session_status.EXPIRED
            ).count()
        )

        # ---------------------------------------------------------------------
        # ACTIVE ATTENDANCE SESSIONS
        # ---------------------------------------------------------------------

        active_sessions = (
            AttendanceSession.objects
            .filter(
                status=session_status.OPEN,
            )
            .filter(
                Q(opens_at__isnull=True)
                | Q(opens_at__lte=now)
            )
            .filter(
                Q(closes_at__isnull=True)
                | Q(closes_at__gt=now)
            )
        )

        active_session_count = (
            active_sessions.count()
        )

        # ---------------------------------------------------------------------
        # ATTENDANCE RECORD COUNTS
        # ---------------------------------------------------------------------

        total_records = (
            AttendanceRecord.objects.count()
        )

        pending_records = (
            AttendanceRecord.objects.filter(
                status=attendance_status.PENDING
            ).count()
        )

        present_records = (
            AttendanceRecord.objects.filter(
                status=attendance_status.PRESENT
            ).count()
        )

        absent_records = (
            AttendanceRecord.objects.filter(
                status=attendance_status.ABSENT
            ).count()
        )

        excused_records = (
            AttendanceRecord.objects.filter(
                status=attendance_status.EXCUSED
            ).count()
        )

        # ---------------------------------------------------------------------
        # ATTENDANCE SOURCES
        # ---------------------------------------------------------------------

        self_marked_records = (
            AttendanceRecord.objects.filter(
                source=attendance_source.SELF
            ).count()
        )

        manually_marked_records = (
            AttendanceRecord.objects.filter(
                source=attendance_source.MANUAL
            ).count()
        )

        system_recorded_records = (
            AttendanceRecord.objects.filter(
                source=attendance_source.SYSTEM
            ).count()
        )

        # ---------------------------------------------------------------------
        # ATTENDANCE RATE
        # ---------------------------------------------------------------------
        #
        # Pending records are excluded.
        #
        # Excused records are also excluded from the
        # present/absent attendance-rate denominator.
        #
        # Formula:
        #
        # PRESENT / (PRESENT + ABSENT) * 100
        # ---------------------------------------------------------------------

        finalized_records = (
            present_records
            + absent_records
        )

        if finalized_records:
            attendance_percentage = round(
                (
                    present_records
                    / finalized_records
                ) * 100,
                1,
            )
        else:
            attendance_percentage = 0

        # ---------------------------------------------------------------------
        # PRESENTATION ALIASES
        # ---------------------------------------------------------------------
        #
        # These aliases make the data easier to consume from
        # dashboard templates and preserve compatibility with
        # existing template variables.
        # ---------------------------------------------------------------------

        return {
            # Sessions
            "total_attendance_sessions": total_sessions,
            "attendance_sessions": total_sessions,
            "draft_attendance_sessions": draft_sessions,
            "open_attendance_sessions": open_sessions,
            "active_attendance_sessions": active_session_count,
            "closed_attendance_sessions": closed_sessions,
            "expired_attendance_sessions": expired_sessions,

            # Records
            "total_attendance_records": total_records,
            "attendance_records": total_records,
            "pending_attendance_records": pending_records,
            "present_attendance_records": present_records,
            "absent_attendance_records": absent_records,
            "excused_attendance_records": excused_records,

            # Simple aliases
            "pending_attendance": pending_records,
            "present_attendance": present_records,
            "absent_attendance": absent_records,
            "excused_attendance": excused_records,

            # Sources
            "self_marked_attendance": self_marked_records,
            "manual_attendance": manually_marked_records,
            "system_attendance": system_recorded_records,

            # Attendance percentage
            "attendance_percentage": (
                attendance_percentage
            ),

            "finalized_attendance_records": (
                finalized_records
            ),
        }

    # =========================================================================
    # RECENT / ACTIVE ATTENDANCE DATA
    # =========================================================================

    @staticmethod
    def get_attendance_dashboard_data():
        """
        Return attendance information specifically useful
        for the executive dashboard.

        This method only reads attendance data.
        """

        now = timezone.now()

        # ---------------------------------------------------------------------
        # ACTIVE SESSIONS
        # ---------------------------------------------------------------------

        active_sessions = (
            AttendanceSession.objects
            .filter(
                status=AttendanceSession.SessionStatus.OPEN,
            )
            .filter(
                Q(opens_at__isnull=True)
                | Q(opens_at__lte=now)
            )
            .filter(
                Q(closes_at__isnull=True)
                | Q(closes_at__gt=now)
            )
            .select_related(
                "created_by",
                "published_by",
            )
            .order_by(
                "closes_at",
                "-created_at",
            )[:5]
        )

        # ---------------------------------------------------------------------
        # RECENT SESSIONS
        # ---------------------------------------------------------------------

        recent_sessions = (
            AttendanceSession.objects
            .select_related(
                "created_by",
                "published_by",
            )
            .order_by(
                "-created_at",
            )[:8]
        )

        # ---------------------------------------------------------------------
        # RECENT ATTENDANCE RECORDS
        # ---------------------------------------------------------------------

        recent_records = (
            AttendanceRecord.objects
            .select_related(
                "user",
                "session",
                "marked_by",
            )
            .order_by(
                "-marked_at",
                "-created_at",
            )[:10]
        )

        return {
            "active_attendance_sessions": (
                active_sessions
            ),
            "recent_attendance_sessions": (
                recent_sessions
            ),
            "recent_attendance_records": (
                recent_records
            ),
        }

    # =========================================================================
    # EVENT STATISTICS
    # =========================================================================

    @staticmethod
    def get_event_statistics():
        """
        Return organization-wide event and registration
        statistics.

        IMPORTANT:

        Event attendance here refers specifically to
        EventRegistration status.

        It is NOT the standalone KUCSA Attendance system.

        Standalone attendance is handled separately by:

            get_attendance_statistics()
        """

        now = timezone.now()

        registration_status = (
            EventRegistration.RegistrationStatus
        )

        # ---------------------------------------------------------------------
        # EVENT COUNTS
        # ---------------------------------------------------------------------

        total_events = Event.objects.count()

        published_events = Event.objects.filter(
            status=Event.Status.PUBLISHED
        ).count()

        ongoing_events = Event.objects.filter(
            status=Event.Status.ONGOING
        ).count()

        completed_events = Event.objects.filter(
            status=Event.Status.COMPLETED
        ).count()

        cancelled_events = Event.objects.filter(
            status=Event.Status.CANCELLED
        ).count()

        draft_events = Event.objects.filter(
            status=Event.Status.DRAFT
        ).count()

        # ---------------------------------------------------------------------
        # UPCOMING EVENTS
        # ---------------------------------------------------------------------

        upcoming_events = Event.objects.filter(
            status=Event.Status.PUBLISHED,
            start_datetime__gt=now,
        )

        upcoming_event_count = (
            upcoming_events.count()
        )

        # ---------------------------------------------------------------------
        # REGISTRATION COUNTS
        # ---------------------------------------------------------------------

        total_registrations = (
            EventRegistration.objects.count()
        )

        registered_registrations = (
            EventRegistration.objects.filter(
                status=registration_status.REGISTERED
            ).count()
        )

        attended_registrations = (
            EventRegistration.objects.filter(
                status=registration_status.ATTENDED
            ).count()
        )

        absent_registrations = (
            EventRegistration.objects.filter(
                status=registration_status.ABSENT
            ).count()
        )

        cancelled_registrations = (
            EventRegistration.objects.filter(
                status=registration_status.CANCELLED
            ).count()
        )

        # ---------------------------------------------------------------------
        # EVENT ATTENDANCE
        # ---------------------------------------------------------------------

        attendance_records = (
            attended_registrations
            + absent_registrations
        )

        if attendance_records:
            attendance_percentage = round(
                (
                    attended_registrations
                    / attendance_records
                ) * 100,
                1,
            )
        else:
            attendance_percentage = 0

        return {
            # Events
            "total_events": total_events,
            "published_events": published_events,
            "ongoing_events": ongoing_events,
            "completed_events": completed_events,
            "cancelled_events": cancelled_events,
            "draft_events": draft_events,

            "upcoming_events": upcoming_events,
            "upcoming_event_count": upcoming_event_count,

            # Registrations
            "total_registrations": total_registrations,
            "registered_registrations": (
                registered_registrations
            ),

            # Backwards-compatible alias
            "active_registrations": (
                registered_registrations
            ),

            "attended_registrations": (
                attended_registrations
            ),

            "absent_registrations": (
                absent_registrations
            ),

            "cancelled_registrations": (
                cancelled_registrations
            ),

            # Event attendance
            "attendance_records": attendance_records,
            "attendance_percentage": (
                attendance_percentage
            ),
        }

    # =========================================================================
    # STUDENT EVENT DATA
    # =========================================================================

    @staticmethod
    def get_student_event_data(user):
        """
        Return event and event-registration information
        for a student.

        IMPORTANT:

        This method concerns event registrations only.

        Standalone KUCSA attendance is handled by the
        Attendance application.
        """

        now = timezone.now()

        registration_status = (
            EventRegistration.RegistrationStatus
        )

        # ---------------------------------------------------------------------
        # AVAILABLE EVENTS
        # ---------------------------------------------------------------------

        available_events = (
            Event.objects
            .select_related("organizer")
            .filter(
                status=Event.Status.PUBLISHED,
                start_datetime__gt=now,
            )
            .order_by(
                "start_datetime"
            )
        )

        # ---------------------------------------------------------------------
        # STUDENT REGISTRATIONS
        # ---------------------------------------------------------------------

        registrations = (
            EventRegistration.objects
            .select_related("event")
            .filter(user=user)
        )

        # ---------------------------------------------------------------------
        # UPCOMING REGISTERED EVENTS
        # ---------------------------------------------------------------------

        upcoming_registrations = (
            registrations
            .filter(
                status=registration_status.REGISTERED,
                event__status=Event.Status.PUBLISHED,
                event__start_datetime__gt=now,
            )
            .order_by(
                "event__start_datetime"
            )
        )

        # ---------------------------------------------------------------------
        # PAST REGISTERED EVENTS
        # ---------------------------------------------------------------------

        past_registrations = (
            registrations
            .filter(
                event__end_datetime__lt=now,
            )
            .exclude(
                status=registration_status.CANCELLED,
            )
            .order_by(
                "-event__start_datetime"
            )
        )

        # ---------------------------------------------------------------------
        # CANCELLED REGISTRATIONS
        # ---------------------------------------------------------------------

        cancelled_registrations = (
            registrations
            .filter(
                status=registration_status.CANCELLED,
            )
            .order_by(
                "-cancelled_at"
            )
        )

        # ---------------------------------------------------------------------
        # REGISTRATION COUNTS
        # ---------------------------------------------------------------------

        registered_count = (
            registrations
            .filter(
                status=registration_status.REGISTERED
            )
            .count()
        )

        attended_count = (
            registrations
            .filter(
                status=registration_status.ATTENDED
            )
            .count()
        )

        absent_count = (
            registrations
            .filter(
                status=registration_status.ABSENT
            )
            .count()
        )

        cancelled_count = (
            registrations
            .filter(
                status=registration_status.CANCELLED
            )
            .count()
        )

        # ---------------------------------------------------------------------
        # EVENT ATTENDANCE
        # ---------------------------------------------------------------------

        attendance_records = (
            attended_count
            + absent_count
        )

        if attendance_records:
            attendance_percentage = round(
                (
                    attended_count
                    / attendance_records
                ) * 100,
                1,
            )
        else:
            attendance_percentage = 0

        # ---------------------------------------------------------------------
        # COMPLETED EVENTS
        # ---------------------------------------------------------------------

        completed_count = (
            registrations
            .filter(
                event__end_datetime__lt=now,
            )
            .exclude(
                status=registration_status.CANCELLED,
            )
            .count()
        )

        return {
            # Querysets
            "available_events": available_events,
            "my_registrations": registrations,
            "upcoming_event_registrations": (
                upcoming_registrations
            ),
            "past_event_registrations": (
                past_registrations
            ),
            "cancelled_event_registrations": (
                cancelled_registrations
            ),

            # Counts
            "available_event_count": (
                available_events.count()
            ),
            "registered_event_count": registered_count,
            "attended_event_count": attended_count,
            "absent_event_count": absent_count,
            "cancelled_event_count": cancelled_count,
            "completed_event_count": completed_count,

            # Event attendance
            "attendance_records": attendance_records,
            "attendance_percentage": (
                attendance_percentage
            ),
        }

    # =========================================================================
    # STUDENT DASHBOARD
    # =========================================================================

    @staticmethod
    def get_student_dashboard(user):
        """
        Build the complete student dashboard context.
        """

        # ---------------------------------------------------------------------
        # MEMBER PROFILE
        # ---------------------------------------------------------------------

        member = getattr(
            user,
            "member_profile",
            None,
        )

        membership_status = None
        membership_status_display = "Pending"
        can_access_platform = False
        payment_required = True
        membership_number = None
        joined_date = None
        expiry_date = None
        profile_completion_status = "Incomplete"

        if member:
            membership_status = (
                member.membership_status
            )

            membership_status_display = (
                member.membership_status_display
            )

            can_access_platform = (
                member.can_access_platform
            )

            payment_required = (
                member.payment_required
            )

            membership_number = (
                member.membership_number
            )

            joined_date = member.joined_date
            expiry_date = member.expiry_date

            profile_completion_status = (
                member.profile_completion_status
            )

        # ---------------------------------------------------------------------
        # EVENT DATA
        # ---------------------------------------------------------------------

        event_data = (
            DashboardService.get_student_event_data(
                user
            )
        )

        # ---------------------------------------------------------------------
        # ANNOUNCEMENTS
        # ---------------------------------------------------------------------

        announcement_data = (
            DashboardService
            .get_announcement_statistics(
                user=user
            )
        )

        # ---------------------------------------------------------------------
        # COMMON DATA
        # ---------------------------------------------------------------------

        common_widgets = (
            DashboardService.get_common_widgets()
        )

        # ---------------------------------------------------------------------
        # DASHBOARD CONTEXT
        # ---------------------------------------------------------------------

        return {
            # User
            "user": user,

            "full_name": (
                user.get_full_name()
                or user.username
            ),

            "role": getattr(
                user,
                "role",
                None,
            ),

            "is_verified": getattr(
                user,
                "is_verified",
                False,
            ),

            # Membership
            "member": member,

            "membership_status": (
                membership_status
            ),

            "membership_status_display": (
                membership_status_display
            ),

            "membership_number": (
                membership_number
            ),

            "joined_date": joined_date,
            "expiry_date": expiry_date,

            "can_access_platform": (
                can_access_platform
            ),

            "payment_required": (
                payment_required
            ),

            "profile_completion_status": (
                profile_completion_status
            ),

            # Events
            "available_events": event_data[
                "available_events"
            ],

            "available_event_count": event_data[
                "available_event_count"
            ],

            "my_registrations": event_data[
                "my_registrations"
            ],

            "upcoming_event_registrations": (
                event_data[
                    "upcoming_event_registrations"
                ]
            ),

            "past_event_registrations": (
                event_data[
                    "past_event_registrations"
                ]
            ),

            "cancelled_event_registrations": (
                event_data[
                    "cancelled_event_registrations"
                ]
            ),

            # Event counts
            "registered_event_count": event_data[
                "registered_event_count"
            ],

            "attended_event_count": event_data[
                "attended_event_count"
            ],

            "absent_event_count": event_data[
                "absent_event_count"
            ],

            "cancelled_event_count": event_data[
                "cancelled_event_count"
            ],

            "completed_event_count": event_data[
                "completed_event_count"
            ],

            # Backwards-compatible event aliases
            "upcoming_event_count": event_data[
                "available_event_count"
            ],

            "attendance": event_data[
                "attended_event_count"
            ],

            "attendance_percentage": event_data[
                "attendance_percentage"
            ],

            "attendance_records": event_data[
                "attendance_records"
            ],

            "completed_events": event_data[
                "completed_event_count"
            ],

            # Announcements
            "announcements": announcement_data[
                "announcements"
            ],

            "announcement_count": (
                announcement_data[
                    "announcement_count"
                ]
            ),

            # Future modules
            "projects": 0,
            "certificates": 0,

            # Common widgets
            **common_widgets,
        }

    # =========================================================================
    # EXECUTIVE DASHBOARD
    # =========================================================================

    @staticmethod
    def get_executive_dashboard(user):
        """
        Build the complete executive dashboard context.

        Payment and financial information is READ-ONLY.

        Attendance information comes from the standalone
        Attendance application.

        Finance management authorization is handled outside
        this service by the Finance permission layer.
        """

        # ---------------------------------------------------------------------
        # MEMBERS
        # ---------------------------------------------------------------------

        membership_status = (
            Member.MembershipStatus
        )

        total_members = (
            Member.objects.count()
        )

        verified_members = (
            Member.objects.filter(
                membership_status=(
                    membership_status.ACTIVE
                )
            ).count()
        )

        pending_members = (
            Member.objects.filter(
                membership_status=(
                    membership_status.PENDING
                )
            ).count()
        )

        suspended_members = (
            Member.objects.filter(
                membership_status=(
                    membership_status.SUSPENDED
                )
            ).count()
        )

        expired_members = (
            Member.objects.filter(
                membership_status=(
                    membership_status.EXPIRED
                )
            ).count()
        )

        # ---------------------------------------------------------------------
        # EXECUTIVES
        # ---------------------------------------------------------------------

        active_executives = (
            Executive.objects.filter(
                is_active=True
            ).count()
        )

        inactive_executives = (
            Executive.objects.filter(
                is_active=False
            ).count()
        )

        # ---------------------------------------------------------------------
        # USERS
        # ---------------------------------------------------------------------

        total_users = (
            User.objects.count()
        )

        verified_users = (
            User.objects.filter(
                is_verified=True
            ).count()
        )

        pending_users = (
            User.objects.filter(
                is_verified=False
            ).count()
        )

        # ---------------------------------------------------------------------
        # EVENTS
        # ---------------------------------------------------------------------

        event_statistics = (
            DashboardService.get_event_statistics()
        )

        # ---------------------------------------------------------------------
        # STANDALONE ATTENDANCE
        # ---------------------------------------------------------------------

        attendance_statistics = (
            DashboardService
            .get_attendance_statistics()
        )

        attendance_dashboard_data = (
            DashboardService
            .get_attendance_dashboard_data()
        )

        # ---------------------------------------------------------------------
        # ANNOUNCEMENTS
        # ---------------------------------------------------------------------

        announcement_statistics = (
            DashboardService
            .get_announcement_statistics()
        )

        # ---------------------------------------------------------------------
        # PAYMENTS
        # ---------------------------------------------------------------------

        payment_statistics = (
            DashboardService
            .get_payment_statistics()
        )

        # ---------------------------------------------------------------------
        # RETURN DASHBOARD CONTEXT
        # ---------------------------------------------------------------------

        return {
            # =================================================================
            # MEMBERSHIP
            # =================================================================

            "total_members": total_members,

            "verified_members": (
                verified_members
            ),

            "pending_members": (
                pending_members
            ),

            "suspended_members": (
                suspended_members
            ),

            "expired_members": (
                expired_members
            ),

            # =================================================================
            # EXECUTIVES
            # =================================================================

            "executives": active_executives,

            "inactive_executives": (
                inactive_executives
            ),

            # =================================================================
            # USERS
            # =================================================================

            "total_users": total_users,

            "verified_users": (
                verified_users
            ),

            "pending_users": (
                pending_users
            ),

            # =================================================================
            # EVENTS
            # =================================================================

            "events": event_statistics[
                "total_events"
            ],

            "total_events": event_statistics[
                "total_events"
            ],

            "published_events": (
                event_statistics[
                    "published_events"
                ]
            ),

            "ongoing_events": (
                event_statistics[
                    "ongoing_events"
                ]
            ),

            "upcoming_events": (
                event_statistics[
                    "upcoming_event_count"
                ]
            ),

            "completed_events": (
                event_statistics[
                    "completed_events"
                ]
            ),

            "cancelled_events": (
                event_statistics[
                    "cancelled_events"
                ]
            ),

            "draft_events": (
                event_statistics[
                    "draft_events"
                ]
            ),

            # =================================================================
            # EVENT REGISTRATIONS
            # =================================================================

            "total_registrations": (
                event_statistics[
                    "total_registrations"
                ]
            ),

            "active_registrations": (
                event_statistics[
                    "active_registrations"
                ]
            ),

            "registered_registrations": (
                event_statistics[
                    "registered_registrations"
                ]
            ),

            # =================================================================
            # STANDALONE ATTENDANCE
            # =================================================================

            "attendance": (
                attendance_statistics[
                    "present_attendance_records"
                ]
            ),

            "attendance_records": (
                attendance_statistics[
                    "total_attendance_records"
                ]
            ),

            "total_attendance_records": (
                attendance_statistics[
                    "total_attendance_records"
                ]
            ),

            "pending_attendance_records": (
                attendance_statistics[
                    "pending_attendance_records"
                ]
            ),

            "present_attendance_records": (
                attendance_statistics[
                    "present_attendance_records"
                ]
            ),

            "absent_attendance_records": (
                attendance_statistics[
                    "absent_attendance_records"
                ]
            ),

            "excused_attendance_records": (
                attendance_statistics[
                    "excused_attendance_records"
                ]
            ),

            "attendance_percentage": (
                attendance_statistics[
                    "attendance_percentage"
                ]
            ),

            # Attendance sessions
            "attendance_sessions": (
                attendance_statistics[
                    "attendance_sessions"
                ]
            ),

            "total_attendance_sessions": (
                attendance_statistics[
                    "total_attendance_sessions"
                ]
            ),

            "draft_attendance_sessions": (
                attendance_statistics[
                    "draft_attendance_sessions"
                ]
            ),

            "open_attendance_sessions": (
                attendance_statistics[
                    "open_attendance_sessions"
                ]
            ),

            "active_attendance_sessions": (
                attendance_statistics[
                    "active_attendance_sessions"
                ]
            ),

            "closed_attendance_sessions": (
                attendance_statistics[
                    "closed_attendance_sessions"
                ]
            ),

            "expired_attendance_sessions": (
                attendance_statistics[
                    "expired_attendance_sessions"
                ]
            ),

            # Attendance sources
            "self_marked_attendance": (
                attendance_statistics[
                    "self_marked_attendance"
                ]
            ),

            "manual_attendance": (
                attendance_statistics[
                    "manual_attendance"
                ]
            ),

            "system_attendance": (
                attendance_statistics[
                    "system_attendance"
                ]
            ),

            # Attendance dashboard querysets
            "active_attendance_session_list": (
                attendance_dashboard_data[
                    "active_attendance_sessions"
                ]
            ),

            "recent_attendance_sessions": (
                attendance_dashboard_data[
                    "recent_attendance_sessions"
                ]
            ),

            "recent_attendance_records": (
                attendance_dashboard_data[
                    "recent_attendance_records"
                ]
            ),

            # =================================================================
            # EVENT ATTENDANCE — BACKWARDS COMPATIBILITY
            # =================================================================
            #
            # These keys refer specifically to event registrations.
            # They are preserved so existing event-related templates
            # do not break.
            # =================================================================

            "attended_registrations": (
                event_statistics[
                    "attended_registrations"
                ]
            ),

            "absent_registrations": (
                event_statistics[
                    "absent_registrations"
                ]
            ),

            "cancelled_registrations": (
                event_statistics[
                    "cancelled_registrations"
                ]
            ),

            "event_attendance_records": (
                event_statistics[
                    "attendance_records"
                ]
            ),

            "event_attendance_percentage": (
                event_statistics[
                    "attendance_percentage"
                ]
            ),

            # =================================================================
            # ANNOUNCEMENTS
            # =================================================================

            "announcements": (
                announcement_statistics[
                    "announcement_count"
                ]
            ),

            "announcement_count": (
                announcement_statistics[
                    "announcement_count"
                ]
            ),

            # =================================================================
            # PAYMENTS
            # =================================================================

            "payments": payment_statistics[
                "total_payments"
            ],

            "total_payments": payment_statistics[
                "total_payments"
            ],

            "pending_payments": payment_statistics[
                "pending_payments"
            ],

            "completed_payments": payment_statistics[
                "completed_payments"
            ],

            "failed_payments": payment_statistics[
                "failed_payments"
            ],

            "cancelled_payments": payment_statistics[
                "cancelled_payments"
            ],

            # =================================================================
            # FINANCIAL TOTALS
            # =================================================================

            "total_received_income": (
                payment_statistics[
                    "total_received_income"
                ]
            ),

            "completed_payment_amount": (
                payment_statistics[
                    "completed_amount"
                ]
            ),

            "pending_payment_amount": (
                payment_statistics[
                    "pending_amount"
                ]
            ),

            # =================================================================
            # MEMBERSHIP PAYMENTS
            # =================================================================

            "membership_payment_count": (
                payment_statistics[
                    "membership_payment_count"
                ]
            ),

            "membership_income": (
                payment_statistics[
                    "membership_income"
                ]
            ),

            # =================================================================
            # SUPPORT PAYMENTS
            # =================================================================

            "support_payment_count": (
                payment_statistics[
                    "support_payment_count"
                ]
            ),

            "support_income": (
                payment_statistics[
                    "support_income"
                ]
            ),
        }

    # =========================================================================
    # DASHBOARD WIDGETS
    # =========================================================================

    @staticmethod
    def get_dashboard_widgets():
        """
        Return reusable dashboard widget statistics.

        Attendance widgets use the standalone attendance
        application rather than EventRegistration.
        """

        common = (
            DashboardService.get_common_widgets()
        )

        events = (
            DashboardService.get_event_statistics()
        )

        attendance = (
            DashboardService.get_attendance_statistics()
        )

        announcements = (
            DashboardService
            .get_announcement_statistics()
        )

        payments = (
            DashboardService
            .get_payment_statistics()
        )

        return {
            # =================================================================
            # COMMON
            # =================================================================

            **common,

            # =================================================================
            # EVENTS
            # =================================================================

            "total_events": events[
                "total_events"
            ],

            "published_events": events[
                "published_events"
            ],

            "ongoing_events": events[
                "ongoing_events"
            ],

            "upcoming_events": events[
                "upcoming_event_count"
            ],

            "completed_events": events[
                "completed_events"
            ],

            "cancelled_events": events[
                "cancelled_events"
            ],

            # =================================================================
            # REGISTRATIONS
            # =================================================================

            "total_registrations": events[
                "total_registrations"
            ],

            "active_registrations": events[
                "active_registrations"
            ],

            "registered_registrations": events[
                "registered_registrations"
            ],

            # =================================================================
            # STANDALONE ATTENDANCE
            # =================================================================

            "attendance": attendance[
                "present_attendance_records"
            ],

            "attendance_records": attendance[
                "total_attendance_records"
            ],

            "total_attendance_records": attendance[
                "total_attendance_records"
            ],

            "pending_attendance_records": attendance[
                "pending_attendance_records"
            ],

            "present_attendance_records": attendance[
                "present_attendance_records"
            ],

            "absent_attendance_records": attendance[
                "absent_attendance_records"
            ],

            "excused_attendance_records": attendance[
                "excused_attendance_records"
            ],

            "attendance_sessions": attendance[
                "total_attendance_sessions"
            ],

            "active_attendance_sessions": attendance[
                "active_attendance_sessions"
            ],

            "open_attendance_sessions": attendance[
                "open_attendance_sessions"
            ],

            "expired_attendance_sessions": attendance[
                "expired_attendance_sessions"
            ],

            "attendance_percentage": attendance[
                "attendance_percentage"
            ],

            # =================================================================
            # ANNOUNCEMENTS
            # =================================================================

            "announcement_count": announcements[
                "announcement_count"
            ],

            # =================================================================
            # PAYMENTS
            # =================================================================

            "total_payments": payments[
                "total_payments"
            ],

            "pending_payments": payments[
                "pending_payments"
            ],

            "completed_payments": payments[
                "completed_payments"
            ],

            "total_received_income": payments[
                "total_received_income"
            ],

            "membership_income": payments[
                "membership_income"
            ],

            "support_income": payments[
                "support_income"
            ],
        }

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    @staticmethod
    def get_analytics():
        """
        Return organization-wide analytics.

        Includes:

        - Users
        - Membership
        - Events
        - Event registrations
        - Standalone attendance
        - Announcements
        - Payments

        Financial information is read-only.
        """

        # ---------------------------------------------------------------------
        # USERS
        # ---------------------------------------------------------------------

        student_count = User.objects.filter(
            role=User.Role.STUDENT
        ).count()

        executive_count = (
            Executive.objects.filter(
                is_active=True
            ).count()
        )

        # ---------------------------------------------------------------------
        # MEMBERSHIP
        # ---------------------------------------------------------------------

        membership_status = (
            Member.MembershipStatus
        )

        total_members = (
            Member.objects.count()
        )

        verified_count = (
            Member.objects.filter(
                membership_status=(
                    membership_status.ACTIVE
                )
            ).count()
        )

        unverified_count = (
            Member.objects.filter(
                membership_status=(
                    membership_status.PENDING
                )
            ).count()
        )

        suspended_count = (
            Member.objects.filter(
                membership_status=(
                    membership_status.SUSPENDED
                )
            ).count()
        )

        expired_count = (
            Member.objects.filter(
                membership_status=(
                    membership_status.EXPIRED
                )
            ).count()
        )

        # ---------------------------------------------------------------------
        # MEMBERSHIP PERCENTAGES
        # ---------------------------------------------------------------------

        if total_members:

            verified_percentage = round(
                verified_count
                / total_members
                * 100
            )

            unverified_percentage = round(
                unverified_count
                / total_members
                * 100
            )

            suspended_percentage = round(
                suspended_count
                / total_members
                * 100
            )

            expired_percentage = round(
                expired_count
                / total_members
                * 100
            )

        else:

            verified_percentage = 0
            unverified_percentage = 0
            suspended_percentage = 0
            expired_percentage = 0

        # ---------------------------------------------------------------------
        # EVENTS
        # ---------------------------------------------------------------------

        event_statistics = (
            DashboardService.get_event_statistics()
        )

        # ---------------------------------------------------------------------
        # ATTENDANCE
        # ---------------------------------------------------------------------

        attendance_statistics = (
            DashboardService
            .get_attendance_statistics()
        )

        # ---------------------------------------------------------------------
        # ANNOUNCEMENTS
        # ---------------------------------------------------------------------

        announcement_statistics = (
            DashboardService
            .get_announcement_statistics()
        )

        # ---------------------------------------------------------------------
        # PAYMENTS
        # ---------------------------------------------------------------------

        payment_statistics = (
            DashboardService
            .get_payment_statistics()
        )

        # ---------------------------------------------------------------------
        # ANALYTICS CONTEXT
        # ---------------------------------------------------------------------

        return {
            # =================================================================
            # USERS
            # =================================================================

            "student_count": student_count,
            "executive_count": executive_count,

            # =================================================================
            # MEMBERSHIP
            # =================================================================

            "total_members": total_members,

            "verified_count": verified_count,

            "unverified_count": unverified_count,

            "suspended_count": suspended_count,

            "expired_count": expired_count,

            # Membership percentages
            "verified_percentage": (
                verified_percentage
            ),

            "unverified_percentage": (
                unverified_percentage
            ),

            "suspended_percentage": (
                suspended_percentage
            ),

            "expired_percentage": (
                expired_percentage
            ),

            # =================================================================
            # EVENTS
            # =================================================================

            "event_count": event_statistics[
                "total_events"
            ],

            "published_event_count": (
                event_statistics[
                    "published_events"
                ]
            ),

            "upcoming_event_count": (
                event_statistics[
                    "upcoming_event_count"
                ]
            ),

            "completed_event_count": (
                event_statistics[
                    "completed_events"
                ]
            ),

            "cancelled_event_count": (
                event_statistics[
                    "cancelled_events"
                ]
            ),

            # =================================================================
            # EVENT REGISTRATIONS
            # =================================================================

            "registration_count": (
                event_statistics[
                    "total_registrations"
                ]
            ),

            "active_registration_count": (
                event_statistics[
                    "active_registrations"
                ]
            ),

            # =================================================================
            # STANDALONE ATTENDANCE
            # =================================================================

            "attendance_count": (
                attendance_statistics[
                    "present_attendance_records"
                ]
            ),

            "attendance_records": (
                attendance_statistics[
                    "total_attendance_records"
                ]
            ),

            "total_attendance_records": (
                attendance_statistics[
                    "total_attendance_records"
                ]
            ),

            "pending_attendance_count": (
                attendance_statistics[
                    "pending_attendance_records"
                ]
            ),

            "present_attendance_count": (
                attendance_statistics[
                    "present_attendance_records"
                ]
            ),

            "absent_attendance_count": (
                attendance_statistics[
                    "absent_attendance_records"
                ]
            ),

            "excused_attendance_count": (
                attendance_statistics[
                    "excused_attendance_records"
                ]
            ),

            "attendance_session_count": (
                attendance_statistics[
                    "total_attendance_sessions"
                ]
            ),

            "active_attendance_session_count": (
                attendance_statistics[
                    "active_attendance_sessions"
                ]
            ),

            "open_attendance_session_count": (
                attendance_statistics[
                    "open_attendance_sessions"
                ]
            ),

            "expired_attendance_session_count": (
                attendance_statistics[
                    "expired_attendance_sessions"
                ]
            ),

            "attendance_percentage": (
                attendance_statistics[
                    "attendance_percentage"
                ]
            ),

            # =================================================================
            # EVENT ATTENDANCE — BACKWARDS COMPATIBILITY
            # =================================================================

            "event_attendance_count": (
                event_statistics[
                    "attended_registrations"
                ]
            ),

            "event_attended_count": (
                event_statistics[
                    "attended_registrations"
                ]
            ),

            "event_absent_count": (
                event_statistics[
                    "absent_registrations"
                ]
            ),

            "cancelled_registration_count": (
                event_statistics[
                    "cancelled_registrations"
                ]
            ),

            "event_attendance_records": (
                event_statistics[
                    "attendance_records"
                ]
            ),

            "event_attendance_percentage": (
                event_statistics[
                    "attendance_percentage"
                ]
            ),

            # =================================================================
            # ANNOUNCEMENTS
            # =================================================================

            "announcement_count": (
                announcement_statistics[
                    "announcement_count"
                ]
            ),

            # =================================================================
            # PAYMENTS
            # =================================================================

            "payment_count": payment_statistics[
                "total_payments"
            ],

            "pending_payment_count": (
                payment_statistics[
                    "pending_payments"
                ]
            ),

            "completed_payment_count": (
                payment_statistics[
                    "completed_payments"
                ]
            ),

            "failed_payment_count": (
                payment_statistics[
                    "failed_payments"
                ]
            ),

            "cancelled_payment_count": (
                payment_statistics[
                    "cancelled_payments"
                ]
            ),

            # =================================================================
            # FINANCIAL ANALYTICS
            # =================================================================

            "total_received_income": (
                payment_statistics[
                    "total_received_income"
                ]
            ),

            "membership_income": (
                payment_statistics[
                    "membership_income"
                ]
            ),

            "support_income": (
                payment_statistics[
                    "support_income"
                ]
            ),

            "pending_payment_amount": (
                payment_statistics[
                    "pending_amount"
                ]
            ),

            # =================================================================
            # BACKWARDS-COMPATIBLE PAYMENT KEY
            # =================================================================

            "payments": payment_statistics[
                "total_payments"
            ],
        }
