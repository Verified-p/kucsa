"""
KUCSA Attendance URLs
=====================

URL configuration for the KUCSA general attendance application.

The attendance system is completely independent of events and
event registrations.

An AttendanceSession represents a general KUCSA attendance
opportunity such as:

    - General meetings
    - Weekly meetings
    - Trainings
    - Workshops
    - Seminars
    - Student gatherings
    - Executive meetings
    - Other KUCSA activities

URL responsibilities
--------------------

This module is responsible only for:

    - URL routing
    - URL naming
    - connecting URLs to views

Business logic belongs in:

    attendance.services

Views are responsible for:

    - authentication
    - authorization
    - form handling
    - request processing
    - calling services
    - rendering templates
    - redirects
    - messages

Application structure
---------------------

    attendance/
        admin.py
        models.py
        services.py
        forms.py
        views.py
        urls.py

        templates/
            attendance/
                attendance_list.html
                attendance_sheet.html
                active_attendance.html
                my_attendance.html
                attendance_report.html
                session_form.html
"""


from django.urls import path

from . import views


# =========================================================
# APPLICATION NAMESPACE
# =========================================================

app_name = "attendance"


# =========================================================
# URL PATTERNS
# =========================================================

urlpatterns = [

    # =====================================================
    # ATTENDANCE SESSION LIST
    # =====================================================
    #
    # Main attendance management page.
    #
    # URL:
    #
    #     /attendance/
    #
    # Name:
    #
    #     attendance:list
    #
    path(
        "",
        views.attendance_list,
        name="list",
    ),

    # Backwards-compatible descriptive alias.
    #
    #     attendance:attendance_list
    #
    path(
        "list/",
        views.attendance_list,
        name="attendance_list",
    ),


    # =====================================================
    # CREATE ATTENDANCE SESSION
    # =====================================================
    #
    # Creates a general KUCSA attendance session.
    #
    # Newly created sessions are handled by the view/service
    # flow and can be opened immediately.
    #
    # URL:
    #
    #     /attendance/create/
    #
    # Name:
    #
    #     attendance:create
    #
    path(
        "create/",
        views.create_attendance,
        name="create",
    ),


    # =====================================================
    # SESSION DETAIL / ATTENDANCE SHEET
    # =====================================================
    #
    # Displays one attendance session and its records.
    #
    # URL:
    #
    #     /attendance/session/<session_id>/
    #
    # Name:
    #
    #     attendance:detail
    #
    path(
        "session/<int:session_id>/",
        views.attendance_detail,
        name="detail",
    ),


    # =====================================================
    # ATTENDANCE SHEET ALIAS
    # =====================================================
    #
    # Backwards-compatible explicit attendance sheet route.
    #
    # URL:
    #
    #     /attendance/session/<session_id>/sheet/
    #
    # Name:
    #
    #     attendance:sheet
    #
    path(
        "session/<int:session_id>/sheet/",
        views.attendance_sheet,
        name="sheet",
    ),


    # =====================================================
    # UPDATE SESSION TIMING
    # =====================================================
    #
    # Allows authorized attendance managers to update:
    #
    #     - opening time
    #     - closing time
    #
    # URL:
    #
    #     /attendance/session/<session_id>/timing/
    #
    # Name:
    #
    #     attendance:update_timing
    #
    path(
        "session/<int:session_id>/timing/",
        views.update_session_timing,
        name="update_timing",
    ),


    # =====================================================
    # OPEN ATTENDANCE
    # =====================================================
    #
    # Opens a Draft attendance session.
    #
    # The request must be POST.
    #
    # URL:
    #
    #     /attendance/session/<session_id>/open/
    #
    # Name:
    #
    #     attendance:open
    #
    path(
        "session/<int:session_id>/open/",
        views.open_attendance,
        name="open",
    ),


    # =====================================================
    # CLOSE ATTENDANCE
    # =====================================================
    #
    # Manually closes an attendance session.
    #
    # URL:
    #
    #     /attendance/session/<session_id>/close/
    #
    # Name:
    #
    #     attendance:close
    #
    path(
        "session/<int:session_id>/close/",
        views.close_attendance,
        name="close",
    ),


    # =====================================================
    # ACTIVE ATTENDANCE
    # =====================================================
    #
    # Displays all currently open attendance sessions.
    #
    # URL:
    #
    #     /attendance/active/
    #
    # Name:
    #
    #     attendance:active
    #
    path(
        "active/",
        views.active_attendance,
        name="active",
    ),


    # Descriptive alias.
    #
    # URL:
    #
    #     /attendance/active-attendance/
    #
    # Name:
    #
    #     attendance:active_attendance
    #
    path(
        "active-attendance/",
        views.active_attendance,
        name="active_attendance",
    ),


    # =====================================================
    # MEMBER SELF ATTENDANCE
    # =====================================================
    #
    # Allows the logged-in member to mark themselves
    # present.
    #
    # The member is always request.user.
    #
    # URL:
    #
    #     /attendance/session/<session_id>/mark-self/
    #
    # Name:
    #
    #     attendance:mark_self
    #
    path(
        "session/<int:session_id>/mark-self/",
        views.mark_my_attendance,
        name="mark_self",
    ),


    # =====================================================
    # EXECUTIVE / ADMIN SELF ATTENDANCE
    # =====================================================
    #
    # Allows an authorized attendance manager to mark
    # themselves present.
    #
    # URL:
    #
    #     /attendance/session/<session_id>/mark-executive-self/
    #
    # Name:
    #
    #     attendance:mark_executive_self
    #
    path(
        "session/<int:session_id>/mark-executive-self/",
        views.mark_executive_self_attendance,
        name="mark_executive_self",
    ),


    # =====================================================
    # EXECUTIVE ATTENDANCE COMPATIBILITY ALIAS
    # =====================================================
    #
    # Existing templates or older code may use this name.
    #
    # URL:
    #
    #     /attendance/session/<session_id>/executive-mark/
    #
    # Name:
    #
    #     attendance:mark_executive
    #
    path(
        "session/<int:session_id>/executive-mark/",
        views.mark_executive_attendance,
        name="mark_executive",
    ),


    # =====================================================
    # MANUAL ATTENDANCE UPDATE
    # =====================================================
    #
    # Allows authorized attendance managers to update one
    # attendance record.
    #
    # URL:
    #
    #     /attendance/record/<attendance_id>/mark/
    #
    # Name:
    #
    #     attendance:mark
    #
    path(
        "record/<int:attendance_id>/mark/",
        views.mark_attendance,
        name="mark",
    ),


    # =====================================================
    # RESET ATTENDANCE
    # =====================================================
    #
    # Resets one attendance record to PENDING.
    #
    # URL:
    #
    #     /attendance/record/<attendance_id>/reset/
    #
    # Name:
    #
    #     attendance:reset
    #
    path(
        "record/<int:attendance_id>/reset/",
        views.reset_attendance,
        name="reset",
    ),


    # =====================================================
    # ATTENDANCE REPORT
    # =====================================================
    #
    # General attendance report.
    #
    # Supports:
    #
    #     - status filtering
    #     - date filtering
    #     - member searching
    #     - HTML reports
    #     - CSV export
    #
    # URL:
    #
    #     /attendance/reports/
    #
    # Name:
    #
    #     attendance:report
    #
    path(
        "reports/",
        views.attendance_report,
        name="report",
    ),


    # Descriptive alias.
    #
    # URL:
    #
    #     /attendance/reports/attendance/
    #
    # Name:
    #
    #     attendance:attendance_report
    #
    path(
        "reports/attendance/",
        views.attendance_report,
        name="attendance_report",
    ),


    # =====================================================
    # SESSION REPORT
    # =====================================================
    #
    # Session-oriented attendance report.
    #
    # URL:
    #
    #     /attendance/reports/sessions/
    #
    # Name:
    #
    #     attendance:session_report
    #
    path(
        "reports/sessions/",
        views.attendance_session_report,
        name="session_report",
    ),


    # =====================================================
    # MY ATTENDANCE
    # =====================================================
    #
    # Shows the authenticated user's own attendance history.
    #
    # URL:
    #
    #     /attendance/my-attendance/
    #
    # Name:
    #
    #     attendance:my_attendance
    #
    path(
        "my-attendance/",
        views.my_attendance,
        name="my_attendance",
    ),


    # =====================================================
    # ACTIVE SESSION STATUS
    # =====================================================
    #
    # Displays the current status of one active attendance
    # session.
    #
    # URL:
    #
    #     /attendance/session/<session_id>/status/
    #
    # Primary name:
    #
    #     attendance:session_status
    #
    path(
        "session/<int:session_id>/status/",
        views.active_session_status,
        name="session_status",
    ),


    # =====================================================
    # ACTIVE STATUS COMPATIBILITY ALIAS
    # =====================================================
    #
    # IMPORTANT:
    #
    # Your attendance_sheet.html currently contains:
    #
    #     {% url 'attendance:active_status' session.pk %}
    #
    # The previous urls.py did NOT define that URL name,
    # which caused:
    #
    #     NoReverseMatch
    #
    # This alias points to the SAME view and SAME URL.
    #
    # Therefore both of these are now valid:
    #
    #     attendance:session_status
    #     attendance:active_status
    #
    path(
        "session/<int:session_id>/status/",
        views.active_session_status,
        name="active_status",
    ),
]

