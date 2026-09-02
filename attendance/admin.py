# attendance/admin.py

"""
KUCSA Attendance Admin
======================

Django administration configuration for the KUCSA
general attendance-session system.

ARCHITECTURE
------------

AttendanceSession
        |
        └── AttendanceRecord
                |
                └── User


IMPORTANT
---------

This attendance application is intentionally independent
of the Events application.

There is NO dependency on:

    - Event
    - EventRegistration
    - Event attendance
    - Event registration status

Attendance is recorded directly against authenticated
members/students through general attendance sessions.

The admin interface is intended for:

    - administrators
    - authorized KUCSA management

Business rules remain in:

    attendance.services
    attendance.models

The admin is responsible primarily for:

    - displaying data
    - searching
    - filtering
    - organizing records
    - providing safe administrative editing
"""


from django.contrib import admin
from django.db.models import Count, Q
from django.utils import timezone

from .models import (
    AttendanceRecord,
    AttendanceSession,
)


# =========================================================
# ADMIN SITE CONFIGURATION
# =========================================================


admin.site.site_header = "KUCSA Attendance Administration"
admin.site.site_title = "KUCSA Attendance Admin"
admin.site.index_title = "Attendance Management"


# =========================================================
# ATTENDANCE RECORD INLINE
# =========================================================


class AttendanceRecordInline(admin.TabularInline):
    """
    Display attendance records directly inside an
    AttendanceSession administration page.

    This allows management to inspect the members/students
    attached to a session without leaving the session page.
    """

    model = AttendanceRecord

    extra = 0

    show_change_link = True

    ordering = (
        "user__first_name",
        "user__last_name",
        "user__username",
    )

    fields = (
        "user",
        "status",
        "source",
        "attendance_time",
        "marked_by",
        "marked_at",
        "notes",
    )

    readonly_fields = (
        "attendance_time",
        "marked_by",
        "marked_at",
    )

    autocomplete_fields = (
        "user",
    )

    classes = (
        "collapse",
    )

    verbose_name = "Attendance Record"
    verbose_name_plural = "Attendance Records"


# =========================================================
# ATTENDANCE SESSION ADMIN
# =========================================================


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    """
    Administration interface for attendance sessions.

    An attendance session represents one general KUCSA
    attendance opportunity.

    Examples:

        - KUCSA General Meeting
        - Computing Students Seminar
        - Weekly Members Meeting
        - Leadership Training
        - Career Talk
        - Special Student Session

    Sessions are independent of the Events application.
    """

    # -----------------------------------------------------
    # LIST DISPLAY
    # -----------------------------------------------------

    list_display = (
        "title",
        "status",
        "opens_at",
        "closes_at",
        "record_count",
        "present_count",
        "absent_count",
        "created_by",
        "created_at",
    )

    # -----------------------------------------------------
    # LIST FILTERS
    # -----------------------------------------------------

    list_filter = (
        "status",
        "opens_at",
        "closes_at",
        "created_at",
    )

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    search_fields = (
        "title",
        "description",
        "created_by__username",
        "created_by__first_name",
        "created_by__last_name",
        "created_by__email",
    )

    # -----------------------------------------------------
    # DATE HIERARCHY
    # -----------------------------------------------------

    date_hierarchy = "created_at"

    # -----------------------------------------------------
    # DEFAULT ORDERING
    # -----------------------------------------------------

    ordering = (
        "-created_at",
        "-opens_at",
        "-pk",
    )

    # -----------------------------------------------------
    # RELATED OBJECTS
    # -----------------------------------------------------

    autocomplete_fields = (
        "created_by",
        "published_by",
        "closed_by",
    )

    # -----------------------------------------------------
    # READ-ONLY FIELDS
    # -----------------------------------------------------

    readonly_fields = (
        "created_at",
        "updated_at",
        "published_at",
        "closed_at",
        "record_count",
        "present_count",
        "absent_count",
        "excused_count",
        "pending_count",
    )

    # -----------------------------------------------------
    # INLINE RECORDS
    # -----------------------------------------------------

    inlines = (
        AttendanceRecordInline,
    )

    # -----------------------------------------------------
    # FIELD ORGANIZATION
    # -----------------------------------------------------

    fieldsets = (
        (
            "Attendance Session",
            {
                "fields": (
                    "title",
                    "description",
                    "status",
                ),
            },
        ),

        (
            "Attendance Window",
            {
                "fields": (
                    "opens_at",
                    "closes_at",
                ),
                "description": (
                    "Define the period during which members "
                    "may mark their attendance."
                ),
            },
        ),

        (
            "Session Management",
            {
                "fields": (
                    "created_by",
                    "published_by",
                    "closed_by",
                ),
            },
        ),

        (
            "Session Statistics",
            {
                "fields": (
                    "record_count",
                    "present_count",
                    "absent_count",
                    "excused_count",
                    "pending_count",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),

        (
            "Audit Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "published_at",
                    "closed_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    # =====================================================
    # QUERYSET
    # =====================================================

    def get_queryset(self, request):
        """
        Optimize the AttendanceSession admin queryset.

        Related users are loaded with select_related(),
        while attendance statistics are calculated using
        database aggregation.
        """

        queryset = (
            super()
            .get_queryset(request)
            .select_related(
                "created_by",
                "published_by",
                "closed_by",
            )
            .annotate(
                _record_count=Count(
                    "attendance_records",
                    distinct=True,
                ),
                _present_count=Count(
                    "attendance_records",
                    filter=Q(
                        attendance_records__status=(
                            AttendanceRecord
                            .AttendanceStatus
                            .PRESENT
                        )
                    ),
                    distinct=True,
                ),
                _absent_count=Count(
                    "attendance_records",
                    filter=Q(
                        attendance_records__status=(
                            AttendanceRecord
                            .AttendanceStatus
                            .ABSENT
                        )
                    ),
                    distinct=True,
                ),
                _excused_count=Count(
                    "attendance_records",
                    filter=Q(
                        attendance_records__status=(
                            AttendanceRecord
                            .AttendanceStatus
                            .EXCUSED
                        )
                    ),
                    distinct=True,
                ),
                _pending_count=Count(
                    "attendance_records",
                    filter=Q(
                        attendance_records__status=(
                            AttendanceRecord
                            .AttendanceStatus
                            .PENDING
                        )
                    ),
                    distinct=True,
                ),
            )
        )

        return queryset

    # =====================================================
    # SESSION STATISTICS
    # =====================================================

    @admin.display(
        description="Records",
        ordering="_record_count",
    )
    def record_count(self, obj):
        """
        Number of attendance records belonging to the
        session.
        """

        return getattr(
            obj,
            "_record_count",
            0,
        )

    @admin.display(
        description="Present",
        ordering="_present_count",
    )
    def present_count(self, obj):
        """
        Number of members/students marked present.
        """

        return getattr(
            obj,
            "_present_count",
            0,
        )

    @admin.display(
        description="Absent",
        ordering="_absent_count",
    )
    def absent_count(self, obj):
        """
        Number of members/students marked absent.
        """

        return getattr(
            obj,
            "_absent_count",
            0,
        )

    @admin.display(
        description="Excused",
        ordering="_excused_count",
    )
    def excused_count(self, obj):
        """
        Number of members/students marked excused.
        """

        return getattr(
            obj,
            "_excused_count",
            0,
        )

    @admin.display(
        description="Pending",
        ordering="_pending_count",
    )
    def pending_count(self, obj):
        """
        Number of attendance records still pending.
        """

        return getattr(
            obj,
            "_pending_count",
            0,
        )

    # =====================================================
    # SESSION STATUS DISPLAY
    # =====================================================

    @admin.display(
        description="Status",
        ordering="status",
    )
    def status_display(self, obj):
        """
        Human-readable session status.

        Kept as a helper for templates/custom admin
        extensions if needed.
        """

        return obj.get_status_display()

    # =====================================================
    # ADMIN ACTIONS
    # =====================================================

    @admin.action(
        description="Close selected attendance sessions"
    )
    def close_sessions(
        self,
        request,
        queryset,
    ):
        """
        Administrative bulk action for closing sessions.

        This action deliberately does not implement the
        complete attendance business logic.

        It simply updates sessions that are currently open.

        Service-layer operations remain preferred for normal
        application workflows.
        """

        open_status = (
            AttendanceSession
            .SessionStatus
            .OPEN
        )

        now = timezone.now()

        updated = (
            queryset
            .filter(
                status=open_status,
            )
            .update(
                status=(
                    AttendanceSession
                    .SessionStatus
                    .CLOSED
                ),
                closed_at=now,
                closed_by=request.user,
            )
        )

        self.message_user(
            request,
            (
                f"{updated} attendance session(s) "
                "were closed."
            ),
        )

    actions = (
        "close_sessions",
    )


# =========================================================
# ATTENDANCE RECORD ADMIN
# =========================================================


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    """
    Administration interface for individual attendance
    records.

    Each record represents one member/student's attendance
    within one AttendanceSession.
    """

    # -----------------------------------------------------
    # LIST DISPLAY
    # -----------------------------------------------------

    list_display = (
        "member_name",
        "session",
        "status",
        "source",
        "attendance_time",
        "marked_by",
        "marked_at",
    )

    # -----------------------------------------------------
    # FILTERS
    # -----------------------------------------------------

    list_filter = (
        "status",
        "source",
        "session__status",
        "attendance_time",
        "marked_at",
    )

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "user__registration_number",
        "session__title",
        "notes",
    )

    # -----------------------------------------------------
    # DATE HIERARCHY
    # -----------------------------------------------------

    date_hierarchy = "marked_at"

    # -----------------------------------------------------
    # DEFAULT ORDERING
    # -----------------------------------------------------

    ordering = (
        "-marked_at",
        "-attendance_time",
        "user__last_name",
        "user__first_name",
        "pk",
    )

    # -----------------------------------------------------
    # RELATED OBJECTS
    # -----------------------------------------------------

    autocomplete_fields = (
        "user",
        "session",
        "marked_by",
    )

    # -----------------------------------------------------
    # READ-ONLY FIELDS
    # -----------------------------------------------------

    readonly_fields = (
        "attendance_time",
        "marked_at",
    )

    # -----------------------------------------------------
    # FIELDSETS
    # -----------------------------------------------------

    fieldsets = (
        (
            "Attendance",
            {
                "fields": (
                    "session",
                    "user",
                    "status",
                    "source",
                ),
            },
        ),

        (
            "Attendance Timing",
            {
                "fields": (
                    "attendance_time",
                    "marked_at",
                ),
            },
        ),

        (
            "Management",
            {
                "fields": (
                    "marked_by",
                    "notes",
                ),
            },
        ),
    )

    # =====================================================
    # QUERYSET
    # =====================================================

    def get_queryset(self, request):
        """
        Optimize attendance record administration.
        """

        return (
            super()
            .get_queryset(request)
            .select_related(
                "session",
                "user",
                "marked_by",
            )
        )

    # =====================================================
    # MEMBER DISPLAY
    # =====================================================

    @admin.display(
        description="Member / Student",
        ordering="user__last_name",
    )
    def member_name(self, obj):
        """
        Display a clean member/student name.
        """

        user = obj.user

        if not user:
            return "Unknown Member"

        full_name = user.get_full_name()

        if full_name:
            return full_name

        return (
            getattr(
                user,
                "username",
                None,
            )
            or "Unknown Member"
        )

    # =====================================================
    # SESSION DISPLAY
    # =====================================================

    @admin.display(
        description="Attendance Session",
        ordering="session__title",
    )
    def session_title(self, obj):
        """
        Return the session title.

        Useful for custom admin extensions.
        """

        return obj.session.title

    # =====================================================
    # ATTENDANCE STATUS
    # =====================================================

    @admin.display(
        description="Attendance Status",
        ordering="status",
    )
    def attendance_status(self, obj):
        """
        Human-readable attendance status.
        """

        return obj.get_status_display()


# =========================================================
# ADMIN CHECK NOTES
# =========================================================

"""
ADMIN DESIGN SUMMARY
====================

AttendanceSession admin provides:

    - session creation/editing
    - session status visibility
    - opening/closing time visibility
    - creator/publisher/closer information
    - attendance statistics
    - inline member attendance records
    - searching
    - filtering
    - date navigation


AttendanceRecord admin provides:

    - member/student identification
    - attendance session identification
    - status management
    - attendance source
    - attendance time
    - marked-by information
    - notes
    - searching
    - filtering


IMPORTANT ARCHITECTURAL RULE
----------------------------

This admin does NOT use:

    Event
    EventRegistration
    EventRegistrationInline

Attendance is completely independent.

The relationship is simply:

    User
      |
      └── AttendanceRecord
              |
              └── AttendanceSession


Application-level workflows should continue to use:

    attendance.services

rather than duplicating business logic inside admin.py.
"""