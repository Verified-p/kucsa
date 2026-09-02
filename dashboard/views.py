# dashboard/views.py

"""
KUCSA Dashboard Views
=====================

HTTP views responsible for routing authenticated users
to the appropriate KUCSA dashboard.

Architecture
------------

    URL
      │
      ▼
    VIEW
      │
      ├── Access Control
      │
      ▼
    DashboardService
      │
      ├── Membership
      ├── Events
      ├── Attendance
      ├── Announcements
      └── Analytics
      │
      ▼
    TEMPLATE

IMPORTANT
---------

Dashboard views are intentionally kept thin.

Business calculations remain inside DashboardService.

Finance access
--------------

Finance management is a dedicated organizational privilege.

    ADMIN
       │
       └──► Finance Management

    TREASURER
       │
       └──► Finance Management

Other executives do NOT automatically receive Finance
Management access merely because they are executives.

A Treasurer must first be assigned the TREASURER role
through the authorized role-assignment process.

Therefore:

    Student
       │
       ▼
    Admin assigns TREASURER role
       │
       ▼
    User.role == TREASURER
       │
       ▼
    Finance Management Access

The dashboard does not assign roles. It only checks
the already-assigned organizational role.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone

from events.models import Event

from .services import DashboardService


# =========================================================
# ACCESS CONTROL HELPERS
# =========================================================


def is_authenticated(user):
    """
    Return True when the supplied user is authenticated.
    """

    return bool(
        user
        and user.is_authenticated
    )


def is_admin(user):
    """
    Return True when the user is a KUCSA administrator,
    Django staff member, or superuser.

    This preserves the existing administrative access
    behavior used throughout the dashboard.
    """

    if not is_authenticated(user):
        return False

    user_role = getattr(
        user,
        "role",
        None,
    )

    role_class = getattr(
        user,
        "Role",
        None,
    )

    admin_role = getattr(
        role_class,
        "ADMIN",
        "ADMIN",
    )

    return (
        user.is_superuser
        or user.is_staff
        or user_role == admin_role
        or user_role == "ADMIN"
    )


def is_executive(user):
    """
    Return True when the user is an executive
    or administrator.
    """

    if not is_authenticated(user):
        return False

    if is_admin(user):
        return True

    return bool(
        getattr(
            user,
            "is_executive",
            False,
        )
    )


def is_student(user):
    """
    Return True when the user has the STUDENT role.
    """

    if not is_authenticated(user):
        return False

    user_role = getattr(
        user,
        "role",
        None,
    )

    role_class = getattr(
        user,
        "Role",
        None,
    )

    student_role = getattr(
        role_class,
        "STUDENT",
        "STUDENT",
    )

    return (
        user_role == student_role
        or user_role == "STUDENT"
    )


# =========================================================
# FINANCE ACCESS
# =========================================================


def is_treasurer(user):
    """
    Return True when the user has the official
    KUCSA TREASURER role.

    Finance management is intentionally tied to the
    organizational role assigned to the user.

    A user does NOT become a Treasurer simply because
    they are:

        - a student
        - an ordinary executive
        - Django staff

    The user must explicitly have:

        role = TREASURER

    This role is assigned through the existing authorized
    role-assignment process.
    """

    if not is_authenticated(user):
        return False

    user_role = getattr(
        user,
        "role",
        None,
    )

    role_class = getattr(
        user,
        "Role",
        None,
    )

    treasurer_role = getattr(
        role_class,
        "TREASURER",
        "TREASURER",
    )

    return (
        user_role == treasurer_role
        or user_role == "TREASURER"
    )


def can_manage_finance(user):
    """
    Return True when the user is authorized to manage
    KUCSA financial records.

    Finance managers are:

        1. KUCSA administrators
        2. The officially assigned Treasurer

    Other executive positions do not automatically receive
    Finance Management access.
    """

    if not is_authenticated(user):
        return False

    return (
        is_admin(user)
        or is_treasurer(user)
    )


def require_finance_manager(user):
    """
    Require Finance Management privileges.

    Access is granted only to:

        - Administrators
        - Users assigned the TREASURER role
    """

    if not can_manage_finance(user):
        raise PermissionDenied(
            "Treasurer or administrator privileges "
            "are required to access Finance Management."
        )


# =========================================================
# GENERAL ACCESS REQUIREMENTS
# =========================================================


def require_admin(user):
    """
    Require administrator privileges.
    """

    if not is_admin(user):
        raise PermissionDenied(
            "Administrator privileges are required "
            "to access this page."
        )


def require_executive_or_admin(user):
    """
    Require executive or administrator privileges.
    """

    if not is_executive(user):
        raise PermissionDenied(
            "Executive or administrator privileges "
            "are required to access this page."
        )


# =========================================================
# MAIN DASHBOARD ROUTER
# =========================================================


@login_required
def dashboard_view(request):
    """
    Route the authenticated user to the correct
    KUCSA dashboard according to their role.
    """

    user = request.user

    # -----------------------------------------------------
    # ADMINISTRATORS
    # -----------------------------------------------------

    if is_admin(user):
        return redirect(
            "dashboard:executive_dashboard"
        )

    # -----------------------------------------------------
    # EXECUTIVES
    # -----------------------------------------------------

    if is_executive(user):
        return redirect(
            "dashboard:executive_dashboard"
        )

    # -----------------------------------------------------
    # STUDENTS / MEMBERS
    # -----------------------------------------------------

    if is_student(user):
        return redirect(
            "dashboard:student_dashboard"
        )

    # -----------------------------------------------------
    # INVALID ROLE
    # -----------------------------------------------------

    raise PermissionDenied(
        "Your account does not have a valid KUCSA role."
    )


# =========================================================
# STUDENT DASHBOARD
# =========================================================


@login_required
def student_dashboard_view(request):
    """
    Display the KUCSA student/member dashboard.

    Business calculations are handled by DashboardService.
    This view only adds querysets required specifically
    by the dashboard interface.
    """

    user = request.user

    # =====================================================
    # ACCESS CONTROL
    # =====================================================

    if is_admin(user) or is_executive(user):
        return redirect(
            "dashboard:executive_dashboard"
        )

    if not is_student(user):
        raise PermissionDenied(
            "You do not have permission to access "
            "the student dashboard."
        )

    # =====================================================
    # CENTRAL DASHBOARD DATA
    # =====================================================

    context = (
        DashboardService
        .get_student_dashboard(user)
    )

    # =====================================================
    # CURRENT TIME
    # =====================================================

    now = timezone.now()

    # =====================================================
    # UPCOMING EVENTS
    # =====================================================

    upcoming_events = (
        Event.objects
        .select_related(
            "organizer",
        )
        .filter(
            status=Event.Status.PUBLISHED,
            start_datetime__gt=now,
        )
        .order_by(
            "start_datetime",
        )[:6]
    )

    # =====================================================
    # FEATURED EVENTS
    # =====================================================

    featured_events = (
        Event.objects
        .select_related(
            "organizer",
        )
        .filter(
            status=Event.Status.PUBLISHED,
            is_featured=True,
            start_datetime__gt=now,
        )
        .order_by(
            "start_datetime",
        )[:3]
    )

    # =====================================================
    # MY UPCOMING EVENTS
    # =====================================================

    my_upcoming_events = (
        context[
            "upcoming_event_registrations"
        ][:5]
    )

    # =====================================================
    # RECENT REGISTRATIONS
    # =====================================================

    recent_event_registrations = (
        context[
            "my_registrations"
        ]
        .order_by(
            "-registered_at",
        )[:5]
    )

    # =====================================================
    # UI-SPECIFIC CONTEXT
    # =====================================================

    context.update(
        {
            "user": user,

            "upcoming_events": (
                upcoming_events
            ),

            "featured_events": (
                featured_events
            ),

            "my_upcoming_events": (
                my_upcoming_events
            ),

            "recent_event_registrations": (
                recent_event_registrations
            ),

            "event_registrations": (
                context["my_registrations"]
            ),

            # -------------------------------------------------
            # FINANCE ACCESS
            # -------------------------------------------------
            #
            # Students normally receive False.
            #
            # This is included for consistency and allows
            # templates/navigation to safely determine whether
            # Finance Management should be displayed.
            #

            "can_manage_finance": (
                can_manage_finance(user)
            ),
        }
    )

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "student_dashboard.html",
        context,
    )


# =========================================================
# EXECUTIVE DASHBOARD
# =========================================================


@login_required
def executive_dashboard_view(request):
    """
    Display the KUCSA executive/administrator dashboard.

    Administrators are intentionally allowed to access
    the executive dashboard because it contains the
    organization-wide management statistics.

    Treasurer access
    ----------------

    A Treasurer is an executive whose role has specifically
    been assigned as:

        TREASURER

    Being an executive alone does not grant Finance
    Management access.

    Finance access is exposed to the dashboard through:

        can_manage_finance

    The actual Finance views must independently enforce
    the same authorization rule.
    """

    user = request.user

    # =====================================================
    # ACCESS CONTROL
    # =====================================================

    require_executive_or_admin(user)

    # =====================================================
    # CENTRAL DASHBOARD DATA
    # =====================================================

    context = (
        DashboardService
        .get_executive_dashboard(request.user)
    )

    # =====================================================
    # CURRENT TIME
    # =====================================================

    now = timezone.now()

    # =====================================================
    # UPCOMING EVENTS
    # =====================================================

    upcoming_event_list = (
        Event.objects
        .select_related(
            "organizer",
        )
        .filter(
            status=Event.Status.PUBLISHED,
            start_datetime__gt=now,
        )
        .order_by(
            "start_datetime",
        )[:8]
    )

    # =====================================================
    # RECENT EVENTS
    # =====================================================

    recent_events = (
        Event.objects
        .select_related(
            "organizer",
        )
        .order_by(
            "-created_at",
        )[:8]
    )

    # =====================================================
    # EXECUTIVE PROFILE
    # =====================================================

    current_executive = getattr(
        user,
        "executive_profile",
        None,
    )

    # =====================================================
    # UI CONTEXT
    # =====================================================

    context.update(
        {
            "user": user,

            "upcoming_event_list": (
                upcoming_event_list
            ),

            "recent_events": (
                recent_events
            ),

            "current_executive": (
                current_executive
            ),

            # =================================================
            # FINANCE MANAGEMENT ACCESS
            # =================================================
            #
            # Only:
            #
            #     ADMIN
            #     TREASURER
            #
            # receive True.
            #
            # Chairperson, Secretary, Organizing Secretary,
            # Publicity Secretary, etc. receive False unless
            # they are separately assigned the Treasurer role.
            #

            "is_treasurer": (
                is_treasurer(user)
            ),

            "can_manage_finance": (
                can_manage_finance(user)
            ),
        }
    )

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "executive_dashboard.html",
        context,
    )


# =========================================================
# ANALYTICS
# =========================================================


@login_required
def analytics_view(request):
    """
    Display KUCSA organizational analytics.

    Analytics calculations are handled by DashboardService.
    """

    user = request.user

    # =====================================================
    # ACCESS CONTROL
    # =====================================================

    require_executive_or_admin(user)

    # =====================================================
    # ANALYTICS DATA
    # =====================================================

    context = (
        DashboardService
        .get_analytics()
    )

    context["user"] = user

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "analytics.html",
        context,
    )


# =========================================================
# DASHBOARD WIDGETS
# =========================================================


@login_required
def widgets_view(request):
    """
    Display reusable KUCSA dashboard widgets.

    This page is restricted to executives and
    administrators.
    """

    user = request.user

    # =====================================================
    # ACCESS CONTROL
    # =====================================================

    require_executive_or_admin(user)

    # =====================================================
    # WIDGET DATA
    # =====================================================

    context = (
        DashboardService
        .get_dashboard_widgets()
    )

    context.update(
        {
            "user": user,

            # Finance permission is exposed to the widget
            # interface without changing existing widget
            # calculations.

            "is_treasurer": (
                is_treasurer(user)
            ),

            "can_manage_finance": (
                can_manage_finance(user)
            ),
        }
    )

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "widgets.html",
        context,
    )



@login_required
def admin_dashboard_view(request):
    """
    Display the KUCSA Admin Control Center.

    Only authorized KUCSA administrators may access this page.
    """

    require_admin(request.user)

    context = DashboardService.get_admin_dashboard()

    context.update({
        "full_name": (
            request.user.get_full_name()
            or request.user.username
        ),
        "role": getattr(
            request.user,
            "role",
            None,
        ),
    })

    return render(
        request,
        "admin_dashboard.html",
        context,
    )