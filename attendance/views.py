"""
KUCSA Attendance Views
======================

HTTP views for the KUCSA general attendance system.

The attendance application is completely independent of
events and event registrations.

Architecture
------------

AttendanceSession
        |
        └── AttendanceRecord
                |
                └── User


Responsibilities
----------------

Views are responsible for:

    - authentication
    - authorization checks
    - form handling
    - request processing
    - calling attendance services
    - rendering
    - redirects
    - user messages

Business logic belongs to:

    attendance.services
"""

import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    AttendanceForm,
    AttendanceReportForm,
    AttendanceSessionControlForm,
    AttendanceSessionCreateForm,
    AttendanceSessionFilterForm,
    AttendanceSessionReportForm,
    AttendanceSessionTimingForm,
    BulkAttendanceForm,
    CloseAttendanceSessionForm,
    MyAttendanceFilterForm,
    SelfAttendanceForm,
)

from .models import (
    AttendanceRecord,
    AttendanceSession,
)

from .services import (
    AttendanceServiceError,
    attendance_seconds_remaining,
    calculate_attendance_statistics,
    can_manage_attendance,
    close_attendance_session,
    create_attendance_session,
    expire_attendance_session_if_needed,
    get_member_attendance,
    get_member_attendance_statistics,
    get_session_statistics,
    mark_absent,
    mark_bulk_attendance,
    mark_excused,
    mark_present,
    mark_self_attendance,
    open_attendance_session,
    reset_attendance as service_reset_attendance,
)


# =========================================================
# INTERNAL HELPERS
# =========================================================


def _user_display_name(user):
    """
    Return a safe human-readable display name.
    """

    if not user:
        return "Member"

    return (
        user.get_full_name()
        or getattr(user, "username", None)
        or "Member"
    )


def _can_manage(request):
    """
    Determine whether the authenticated user can manage
    attendance.

    Permission logic remains in the service layer.
    """

    return can_manage_attendance(request.user)


def _redirect_my_attendance():
    """
    Redirect to the current user's attendance history.
    """

    return redirect("attendance:my_attendance")


def _redirect_attendance_list():
    """
    Redirect to the attendance session list.
    """

    return redirect("attendance:list")


def _redirect_session_detail(session):
    """
    Redirect to a specific attendance session.
    """

    return redirect(
        "attendance:detail",
        session_id=session.pk,
    )


def _redirect_active_attendance():
    """
    Redirect to the active attendance page.
    """

    return redirect("attendance:active")


# =========================================================
# QUERYSETS
# =========================================================


def _session_queryset():
    """
    Base queryset for attendance sessions.
    """

    return (
        AttendanceSession.objects
        .select_related(
            "created_by",
            "published_by",
            "closed_by",
        )
        .order_by(
            "-created_at",
            "-opens_at",
            "-pk",
        )
    )


def _attendance_queryset():
    """
    Base queryset for attendance records.
    """

    return (
        AttendanceRecord.objects
        .select_related(
            "session",
            "user",
            "marked_by",
        )
        .order_by(
            "-session__opens_at",
            "user__last_name",
            "user__first_name",
            "user__username",
            "pk",
        )
    )


def _session_records_queryset(session):
    """
    Return attendance records belonging to one session.
    """

    return (
        AttendanceRecord.objects
        .select_related(
            "session",
            "user",
            "marked_by",
        )
        .filter(
            session=session,
        )
        .order_by(
            "user__first_name",
            "user__last_name",
            "user__username",
            "pk",
        )
    )


# =========================================================
# LEGACY / LOCAL STATISTICS HELPER
# =========================================================


def _calculate_statistics(queryset):
    """
    Calculate attendance statistics from a queryset.

    This helper is retained for backwards compatibility with
    existing views/templates.

    The attendance service layer remains the preferred source
    of statistics for reports.

    Pending records are excluded from the finalized
    attendance percentage.

    Present, absent and excused are finalized records.
    """

    status = AttendanceRecord.AttendanceStatus

    total = queryset.count()

    present = queryset.filter(
        status=status.PRESENT
    ).count()

    absent = queryset.filter(
        status=status.ABSENT
    ).count()

    excused = queryset.filter(
        status=status.EXCUSED
    ).count()

    pending = queryset.filter(
        status=status.PENDING
    ).count()

    finalized = (
        present
        + absent
        + excused
    )

    attendance_percentage = (
        round(
            (present / finalized) * 100,
            2,
        )
        if finalized
        else 0
    )

    return {
        "total": total,
        "total_records": total,

        "present": present,
        "attended": present,

        "absent": absent,

        "excused": excused,

        "pending": pending,

        "finalized": finalized,

        "attendance_percentage": attendance_percentage,

        "records": total,
        "rate": attendance_percentage,
    }


# =========================================================
# EXPIRED SESSION FINALIZATION
# =========================================================


def _finalize_expired_session(session):
    """
    Finalize an attendance session when its attendance window
    has expired.

    PENDING records are converted to ABSENT once the session
    can no longer accept member self-attendance.

    Existing PRESENT, ABSENT and EXCUSED records are never
    intentionally overwritten.
    """

    if not session:
        return session

    try:
        session = expire_attendance_session_if_needed(
            session
        )
    except AttendanceServiceError:
        return session
    except Exception:
        return session

    # If attendance is still open, pending records must remain
    # pending because members can still mark themselves.
    if _session_attendance_is_open(session):
        return session

    status = AttendanceRecord.AttendanceStatus

    pending_records = (
        AttendanceRecord.objects
        .select_related(
            "session",
            "user",
            "marked_by",
        )
        .filter(
            session=session,
            status=status.PENDING,
        )
    )

    for record in pending_records:
        try:
            mark_absent(
                session=session,
                user=record.user,
                marked_by=(
                    getattr(session, "closed_by", None)
                    or getattr(session, "created_by", None)
                ),
                notes=(
                    "Automatically marked absent because "
                    "the attendance session expired before "
                    "the member marked attendance."
                ),
            )

        except AttendanceServiceError:
            continue

        except Exception:
            continue

    return session


# =========================================================
# SESSION STATE HELPERS
# =========================================================


def _session_seconds_remaining(session):
    """
    Safely calculate remaining attendance time.
    """

    try:
        return attendance_seconds_remaining(session)

    except AttendanceServiceError:
        return 0

    except Exception:
        return 0


def _session_attendance_is_open(session):
    """
    Determine whether attendance is currently available.

    This helper does not modify AttendanceSession.
    """

    if not session:
        return False

    if (
        session.status
        != AttendanceSession.SessionStatus.OPEN
    ):
        return False

    seconds_remaining = _session_seconds_remaining(
        session
    )

    if seconds_remaining is None:
        return True

    return seconds_remaining > 0


# =========================================================
# SESSION PREPARATION
# =========================================================


def _prepare_session(session):
    """
    Prepare one attendance session for rendering.

    Expired sessions are transitioned through the service
    layer and remaining pending records are finalized.
    """

    if not session:
        return session

    try:
        session = expire_attendance_session_if_needed(
            session
        )
    except AttendanceServiceError:
        pass
    except Exception:
        pass

    session = _finalize_expired_session(
        session
    )

    return session


def _prepare_sessions(sessions):
    """
    Prepare multiple attendance sessions.
    """

    return [
        _prepare_session(session)
        for session in sessions
    ]


# =========================================================
# SESSION REPORT STATISTICS
# =========================================================


def _attach_session_statistics(session):
    """
    Attach service-generated statistics to a session for
    template use.

    IMPORTANT
    ---------

    AttendanceSession already exposes read-only calculated
    properties such as:

        total_records
        present_count
        absent_count
        excused_count
        pending_count

    Therefore this function MUST NOT do:

        session.present_count = ...
        session.absent_count = ...
        session.pending_count = ...

    Those assignments cause:

        AttributeError:
        property 'present_count' of 'AttendanceSession'
        object has no setter

    Instead, statistics are attached under the separate
    `statistics` attribute.

    The model's read-only properties remain untouched.
    """

    try:
        statistics = get_session_statistics(
            session
        )
    except AttendanceServiceError:
        statistics = _calculate_statistics(
            _session_records_queryset(session)
        )
    except Exception:
        statistics = _calculate_statistics(
            _session_records_queryset(session)
        )

    # This is NOT a model property such as present_count.
    # It is simply an additional attribute used by templates.
    session.statistics = statistics

    return session


def _prepare_report_sessions(sessions):
    """
    Prepare sessions and attach service-generated statistics.

    No read-only AttendanceSession property is overwritten.
    """

    prepared = []

    for session in sessions:

        session = _prepare_session(
            session
        )

        session = _attach_session_statistics(
            session
        )

        prepared.append(
            session
        )

    return prepared


# =========================================================
# ACTIVE SESSIONS
# =========================================================

def _get_active_sessions_for_user(user):
    """
    Return currently active attendance sessions for a user.

    AttendanceRecord existence does NOT mean that the member
    has marked attendance.

        PENDING  -> not yet marked
        PRESENT  -> successfully marked
        ABSENT   -> management marked absent
        EXCUSED  -> management marked excused

    Responsibilities:
        - Return only OPEN attendance sessions.
        - Respect the session's actual attendance window.
        - Retrieve the current user's attendance record.
        - Determine whether the user has marked attendance.
        - Determine whether the user can mark attendance.
        - Attach user-specific attendance information to the session.

    Important:
        `seconds_remaining` and `attendance_is_open` are model
        properties. They are calculated dynamically and must NOT
        be assigned to from the view.
    """

    if not user or not user.is_authenticated:
        return []

    sessions = (
        _session_queryset()
        .filter(
            status=AttendanceSession.SessionStatus.OPEN
        )
    )

    active_sessions = []

    attendance_status = AttendanceRecord.AttendanceStatus

    for session in sessions:

        # Prepare the session using the existing helper.
        session = _prepare_session(session)

        # The model property determines whether the attendance
        # window is currently open.
        if not session.attendance_is_open:
            continue

        attendance = (
            AttendanceRecord.objects
            .select_related(
                "session",
                "user",
                "marked_by",
            )
            .filter(
                session=session,
                user=user,
            )
            .first()
        )

        # Only PRESENT means the member has successfully
        # marked their attendance.
        attendance_marked = (
            attendance is not None
            and attendance.status
            == attendance_status.PRESENT
        )

        # A member can self-mark when there is no record
        # or the existing record is still PENDING.
        #
        # PRESENT, ABSENT and EXCUSED records cannot be
        # overwritten through self-attendance.
        can_mark_attendance = (
            not attendance_marked
            and (
                attendance is None
                or attendance.status
                == attendance_status.PENDING
            )
        )

        # ---------------------------------------------------------
        # Attach user-specific, view-only attributes.
        # ---------------------------------------------------------
        #
        # These are NOT model properties, so assigning them here
        # is safe.
        #

        session.attendance_record = attendance

        session.attendance_marked = attendance_marked

        session.can_mark_attendance = (
            can_mark_attendance
        )

        # Only expose a PRESENT record as actual user attendance.
        session.user_attendance = (
            attendance
            if attendance_marked
            else None
        )

        # ---------------------------------------------------------
        # DO NOT assign:
        #
        #     session.seconds_remaining = ...
        #     session.attendance_is_open = ...
        #
        # Both are read-only properties on AttendanceSession.
        # Access them directly whenever required:
        #
        #     session.seconds_remaining
        #     session.attendance_is_open
        # ---------------------------------------------------------

        active_sessions.append(session)

    return active_sessions


# =========================================================
# ATTENDANCE STATUS PROCESSING
# =========================================================


def _process_attendance_status(
    *,
    session,
    user,
    status,
    marked_by,
    notes="",
):
    """
    Delegate attendance status changes to the service layer.
    """

    attendance_status = (
        AttendanceRecord.AttendanceStatus
    )

    if status == attendance_status.PRESENT:

        return mark_present(
            session=session,
            user=user,
            marked_by=marked_by,
        )

    if status == attendance_status.ABSENT:

        return mark_absent(
            session=session,
            user=user,
            marked_by=marked_by,
            notes=notes,
        )

    if status == attendance_status.EXCUSED:

        return mark_excused(
            session=session,
            user=user,
            marked_by=marked_by,
            notes=notes,
        )

    if status == attendance_status.PENDING:

        return service_reset_attendance(
            session=session,
            user=user,
            marked_by=marked_by,
        )

    raise AttendanceServiceError(
        "Invalid attendance status."
    )


# =========================================================
# ATTENDANCE FILTERING
# =========================================================


def _apply_attendance_filters(
    queryset,
    cleaned_data,
):
    """
    Apply management filters to attendance records.
    """

    status = cleaned_data.get(
        "status"
    )

    search = (
        cleaned_data.get(
            "search"
        )
        or ""
    ).strip()

    start_date = cleaned_data.get(
        "start_date"
    )

    end_date = cleaned_data.get(
        "end_date"
    )

    if status:
        queryset = queryset.filter(
            status=status
        )

    if start_date:
        queryset = queryset.filter(
            session__opens_at__date__gte=start_date
        )

    if end_date:
        queryset = queryset.filter(
            session__opens_at__date__lte=end_date
        )

    if search:
        queryset = queryset.filter(
            Q(
                user__username__icontains=search
            )
            | Q(
                user__first_name__icontains=search
            )
            | Q(
                user__last_name__icontains=search
            )
            | Q(
                user__email__icontains=search
            )
            | Q(
                user__registration_number__icontains=search
            )
        )

    return queryset


def _apply_session_filters(
    queryset,
    cleaned_data,
):
    """
    Apply filters to attendance sessions.
    """

    status = cleaned_data.get(
        "status"
    )

    search = (
        cleaned_data.get(
            "search"
        )
        or ""
    ).strip()

    start_date = cleaned_data.get(
        "start_date"
    )

    end_date = cleaned_data.get(
        "end_date"
    )

    if status:
        queryset = queryset.filter(
            status=status
        )

    if search:
        queryset = queryset.filter(
            Q(
                title__icontains=search
            )
            | Q(
                description__icontains=search
            )
        )

    if start_date:
        queryset = queryset.filter(
            opens_at__date__gte=start_date
        )

    if end_date:
        queryset = queryset.filter(
            opens_at__date__lte=end_date
        )

    return queryset


# =========================================================
# ATTENDANCE SESSION LIST
# =========================================================


@login_required
def attendance_list(request):
    """
    Display all attendance sessions.
    """

    if not _can_manage(request):

        messages.info(
            request,
            (
                "You can only view your own "
                "attendance history."
            ),
        )

        return _redirect_my_attendance()

    sessions = _session_queryset()

    form = AttendanceSessionFilterForm(
        request.GET or None
    )

    if form.is_valid():

        sessions = _apply_session_filters(
            sessions,
            form.cleaned_data,
        )

    sessions = _prepare_sessions(
        sessions
    )

    context = {
        "sessions": sessions,
        "attendance_sessions": sessions,

        "form": form,

        "can_manage": True,

        "session_count": len(sessions),
        "total_sessions": len(sessions),
    }

    return render(
        request,
        "attendance_list.html",
        context,
    )


# =========================================================
# CREATE ATTENDANCE SESSION
# =========================================================


@login_required
def create_attendance(request):
    """
    Create a new attendance session.
    """

    if not _can_manage(request):

        messages.error(
            request,
            (
                "You do not have permission "
                "to create attendance sessions."
            ),
        )

        return _redirect_my_attendance()

    if request.method == "POST":

        form = AttendanceSessionCreateForm(
            request.POST
        )

        if form.is_valid():

            try:

                session = create_attendance_session(
                    user=request.user,
                    title=form.cleaned_data[
                        "title"
                    ],
                    description=(
                        form.cleaned_data.get(
                            "description",
                            "",
                        )
                    ),
                    opens_at=(
                        form.cleaned_data.get(
                            "opens_at"
                        )
                    ),
                    closes_at=(
                        form.cleaned_data.get(
                            "closes_at"
                        )
                    ),
                )

                try:

                    session = open_attendance_session(
                        session=session,
                        user=request.user,
                    )

                    messages.success(
                        request,
                        (
                            f'Attendance session '
                            f'"{session.title}" '
                            "was created and opened successfully."
                        ),
                    )

                except AttendanceServiceError as exc:

                    messages.warning(
                        request,
                        (
                            f'Attendance session '
                            f'"{session.title}" was created, '
                            f'but could not be opened automatically: '
                            f'{exc}'
                        ),
                    )

                return _redirect_session_detail(
                    session
                )

            except AttendanceServiceError as exc:

                messages.error(
                    request,
                    str(exc),
                )

    else:

        form = AttendanceSessionCreateForm()

    context = {
        "form": form,

        "session": None,
        "attendance_session": None,

        "page_title": (
            "Create Attendance Session"
        ),

        "can_manage": True,
    }

    return render(
        request,
        "session_form.html",
        context,
    )


# =========================================================
# ATTENDANCE SESSION DETAIL
# =========================================================


@login_required
def attendance_detail(
    request,
    session_id,
):
    """
    Display and manage one attendance session.
    """

    if not _can_manage(request):

        messages.error(
            request,
            (
                "You do not have permission "
                "to manage attendance."
            ),
        )

        return _redirect_my_attendance()

    session = get_object_or_404(
        _session_queryset(),
        pk=session_id,
    )

    session = _prepare_session(
        session
    )

    records = _session_records_queryset(
        session
    )

    attendance_form = AttendanceForm()

    bulk_form = BulkAttendanceForm()

    open_form = AttendanceSessionControlForm()

    close_form = CloseAttendanceSessionForm()

    if request.method == "POST":

        # -------------------------------------------------
        # OPEN ATTENDANCE
        # -------------------------------------------------

        if "open_attendance" in request.POST:

            try:

                open_attendance_session(
                    session=session,
                    user=request.user,
                )

                messages.success(
                    request,
                    (
                        "Attendance is now "
                        "open for members."
                    ),
                )

                return _redirect_session_detail(
                    session
                )

            except AttendanceServiceError as exc:

                messages.error(
                    request,
                    str(exc),
                )

        # -------------------------------------------------
        # CLOSE ATTENDANCE
        # -------------------------------------------------

        elif "close_attendance" in request.POST:

            close_form = CloseAttendanceSessionForm(
                request.POST
            )

            if close_form.is_valid():

                try:

                    close_attendance_session(
                        session=session,
                        user=request.user,
                    )

                    session = _prepare_session(
                        session
                    )

                    messages.success(
                        request,
                        (
                            "Attendance session "
                            "has been closed."
                        ),
                    )

                    return _redirect_session_detail(
                        session
                    )

                except AttendanceServiceError as exc:

                    messages.error(
                        request,
                        str(exc),
                    )

            else:

                messages.error(
                    request,
                    (
                        "Please confirm before "
                        "closing attendance."
                    ),
                )

        # -------------------------------------------------
        # BULK ATTENDANCE UPDATE
        # -------------------------------------------------

        elif "bulk_update" in request.POST:

            bulk_form = BulkAttendanceForm(
                request.POST
            )

            if bulk_form.is_valid():

                selected_ids = (
                    bulk_form.cleaned_data[
                        "selected_attendance"
                    ]
                )

                status = (
                    bulk_form.cleaned_data[
                        "attendance_status"
                    ]
                )

                notes = (
                    bulk_form.cleaned_data.get(
                        "notes"
                    )
                    or ""
                ).strip()

                valid_ids = set(
                    records.filter(
                        pk__in=selected_ids
                    ).values_list(
                        "pk",
                        flat=True,
                    )
                )

                selected_ids = [
                    record_id
                    for record_id in selected_ids
                    if record_id in valid_ids
                ]

                if not selected_ids:

                    messages.error(
                        request,
                        (
                            "No valid attendance "
                            "records were selected."
                        ),
                    )

                else:

                    try:

                        updated_records = (
                            mark_bulk_attendance(
                                attendance_ids=selected_ids,
                                status=status,
                                marked_by=request.user,
                                notes=notes,
                            )
                        )

                        messages.success(
                            request,
                            (
                                f"{len(updated_records)} "
                                "attendance record(s) "
                                "updated successfully."
                            ),
                        )

                        return _redirect_session_detail(
                            session
                        )

                    except AttendanceServiceError as exc:

                        messages.error(
                            request,
                            str(exc),
                        )

        # -------------------------------------------------
        # INDIVIDUAL ATTENDANCE UPDATE
        # -------------------------------------------------

        elif "attendance_id" in request.POST:

            attendance_id = request.POST.get(
                "attendance_id"
            )

            attendance = get_object_or_404(
                AttendanceRecord.objects.select_related(
                    "session",
                    "user",
                    "marked_by",
                ),
                pk=attendance_id,
                session=session,
            )

            attendance_form = AttendanceForm(
                request.POST,
                instance=attendance,
            )

            if attendance_form.is_valid():

                status = (
                    attendance_form.cleaned_data[
                        "status"
                    ]
                )

                notes = (
                    attendance_form.cleaned_data.get(
                        "notes"
                    )
                    or ""
                ).strip()

                try:

                    _process_attendance_status(
                        session=session,
                        user=attendance.user,
                        status=status,
                        marked_by=request.user,
                        notes=notes,
                    )

                    messages.success(
                        request,
                        (
                            "Attendance for "
                            f"{_user_display_name(attendance.user)} "
                            "has been updated successfully."
                        ),
                    )

                    return _redirect_session_detail(
                        session
                    )

                except AttendanceServiceError as exc:

                    messages.error(
                        request,
                        str(exc),
                    )

            else:

                messages.error(
                    request,
                    (
                        "Please correct the "
                        "attendance form errors."
                    ),
                )

    # -----------------------------------------------------
    # REFRESH DATA AFTER POST
    # -----------------------------------------------------

    session = get_object_or_404(
        _session_queryset(),
        pk=session_id,
    )

    session = _prepare_session(
        session
    )

    records = _session_records_queryset(
        session
    )

    # Use the service-layer statistics for the detail page.
    try:
        statistics = get_session_statistics(
            session
        )
    except AttendanceServiceError:
        statistics = _calculate_statistics(
            records
        )
    except Exception:
        statistics = _calculate_statistics(
            records
        )

    seconds_remaining = (
        _session_seconds_remaining(
            session
        )
    )

    attendance_is_open = (
        _session_attendance_is_open(
            session
        )
    )

    context = {
        "session": session,
        "attendance_session": session,

        "attendance_records": records,
        "records": records,

        "form": attendance_form,
        "attendance_form": attendance_form,

        "bulk_form": bulk_form,

        "open_form": open_form,
        "close_form": close_form,

        "active_session": (
            session
            if attendance_is_open
            else None
        ),

        "attendance_is_open": (
            attendance_is_open
        ),

        "seconds_remaining": (
            seconds_remaining
        ),

        # Report/detail statistics.
        **statistics,

        # Keep a namespaced version available to templates.
        "statistics": statistics,

        "can_manage": True,
    }

    return render(
        request,
        "attendance_sheet.html",
        context,
    )


# =========================================================
# ATTENDANCE SHEET ALIAS
# =========================================================


@login_required
def attendance_sheet(
    request,
    session_id,
):
    """
    Backwards-compatible alias for the attendance detail page.
    """

    return attendance_detail(
        request=request,
        session_id=session_id,
    )


# =========================================================
# OPEN ATTENDANCE SESSION
# =========================================================


@login_required
def open_attendance(
    request,
    session_id,
):
    """
    Open an attendance session.
    """

    if not _can_manage(request):

        messages.error(
            request,
            (
                "You do not have permission "
                "to open attendance."
            ),
        )

        return _redirect_my_attendance()

    session = get_object_or_404(
        AttendanceSession,
        pk=session_id,
    )

    if request.method != "POST":

        messages.error(
            request,
            (
                "Attendance can only be opened "
                "using the Open Attendance button."
            ),
        )

        return _redirect_session_detail(
            session
        )

    try:

        session = open_attendance_session(
            session=session,
            user=request.user,
        )

        messages.success(
            request,
            (
                f'Attendance for "{session.title}" '
                "is now open for members."
            ),
        )

    except AttendanceServiceError as exc:

        messages.error(
            request,
            str(exc),
        )

    return _redirect_session_detail(
        session
    )


# =========================================================
# CLOSE ATTENDANCE SESSION
# =========================================================


@login_required
def close_attendance(
    request,
    session_id,
):
    """
    Close an attendance session.

    Remaining pending records are finalized as absent.
    """

    if not _can_manage(request):

        messages.error(
            request,
            (
                "You do not have permission "
                "to close attendance."
            ),
        )

        return _redirect_my_attendance()

    session = get_object_or_404(
        AttendanceSession,
        pk=session_id,
    )

    if request.method != "POST":

        return _redirect_session_detail(
            session
        )

    form = CloseAttendanceSessionForm(
        request.POST
    )

    if not form.is_valid():

        messages.error(
            request,
            (
                "Please confirm before "
                "closing attendance."
            ),
        )

        return _redirect_session_detail(
            session
        )

    try:

        close_attendance_session(
            session=session,
            user=request.user,
        )

        _prepare_session(
            session
        )

        messages.success(
            request,
            (
                "Attendance session "
                "has been closed successfully."
            ),
        )

    except AttendanceServiceError as exc:

        messages.error(
            request,
            str(exc),
        )

    return _redirect_session_detail(
        session
    )


# =========================================================
# MEMBER SELF ATTENDANCE
# =========================================================


@login_required
def mark_my_attendance(
    request,
    session_id,
):
    """
    Allow the authenticated member to mark themselves
    present.
    """

    if request.method != "POST":

        messages.error(
            request,
            (
                "Attendance can only be "
                "marked using the attendance form."
            ),
        )

        return _redirect_active_attendance()

    session = get_object_or_404(
        AttendanceSession,
        pk=session_id,
    )

    form = SelfAttendanceForm(
        request.POST
    )

    if not form.is_valid():

        messages.error(
            request,
            (
                "Please confirm your attendance "
                "before submitting."
            ),
        )

        return _redirect_active_attendance()

    try:

        mark_self_attendance(
            session=session,
            user=request.user,
        )

        messages.success(
            request,
            (
                f'Your attendance for '
                f'"{session.title}" '
                "has been recorded successfully."
            ),
        )

    except AttendanceServiceError as exc:

        messages.error(
            request,
            str(exc),
        )

    return _redirect_active_attendance()


# =========================================================
# EXECUTIVE / ADMIN SELF ATTENDANCE
# =========================================================


@login_required
def mark_executive_self_attendance(
    request,
    session_id,
):
    """
    Allow an authorized management user to mark
    themselves present.
    """

    if request.method != "POST":

        messages.error(
            request,
            (
                "Attendance can only be "
                "marked using the attendance form."
            ),
        )

        return _redirect_active_attendance()

    if not _can_manage(request):

        messages.error(
            request,
            (
                "Only authorized attendance "
                "managers can use this action."
            ),
        )

        return _redirect_my_attendance()

    session = get_object_or_404(
        AttendanceSession,
        pk=session_id,
    )

    form = SelfAttendanceForm(
        request.POST
    )

    if not form.is_valid():

        messages.error(
            request,
            (
                "Please confirm your attendance "
                "before submitting."
            ),
        )

        return _redirect_active_attendance()

    try:

        mark_self_attendance(
            session=session,
            user=request.user,
        )

        messages.success(
            request,
            (
                f'Your attendance for '
                f'"{session.title}" '
                "has been recorded successfully."
            ),
        )

    except AttendanceServiceError as exc:

        messages.error(
            request,
            str(exc),
        )

    return _redirect_active_attendance()


# =========================================================
# EXECUTIVE ATTENDANCE COMPATIBILITY ALIAS
# =========================================================


@login_required
def mark_executive_attendance(
    request,
    session_id,
):
    """
    Compatibility wrapper for existing templates or URLs.
    """

    return mark_executive_self_attendance(
        request=request,
        session_id=session_id,
    )


# =========================================================
# ACTIVE ATTENDANCE
# =========================================================


@login_required
def active_attendance(request):
    """
    Display all currently active attendance sessions.
    """

    active_sessions = _get_active_sessions_for_user(
        request.user
    )

    can_manage = _can_manage(
        request
    )

    context = {
        "active_sessions": active_sessions,

        "active_count": len(
            active_sessions
        ),

        "active_attendance_count": len(
            active_sessions
        ),

        "can_manage": can_manage,
    }

    return render(
        request,
        "active_attendance.html",
        context,
    )


# =========================================================
# MY ATTENDANCE
# =========================================================


@login_required
def my_attendance(request):
    """
    Display the authenticated user's attendance history.
    """

    attendance_records = get_member_attendance(
        request.user
    )

    form = MyAttendanceFilterForm(
        request.GET or None
    )

    if form.is_valid():

        status = form.cleaned_data.get(
            "status"
        )

        start_date = form.cleaned_data.get(
            "start_date"
        )

        end_date = form.cleaned_data.get(
            "end_date"
        )

        if status:

            attendance_records = (
                attendance_records.filter(
                    status=status
                )
            )

        if start_date:

            attendance_records = (
                attendance_records.filter(
                    session__opens_at__date__gte=(
                        start_date
                    )
                )
            )

        if end_date:

            attendance_records = (
                attendance_records.filter(
                    session__opens_at__date__lte=(
                        end_date
                    )
                )
            )

    statistics = get_member_attendance_statistics(
        request.user
    )

    active_sessions = _get_active_sessions_for_user(
        request.user
    )

    context = {
        "attendance_records": attendance_records,

        "form": form,

        "total": statistics["total"],

        "total_records": statistics.get(
            "total_records",
            statistics["total"],
        ),

        "present": statistics["present"],

        "attended": statistics.get(
            "attended",
            statistics["present"],
        ),

        "absent": statistics["absent"],

        "excused": statistics["excused"],

        "pending": statistics["pending"],

        "finalized": statistics["finalized"],

        "attendance_percentage": (
            statistics["attendance_percentage"]
        ),

        "rate": statistics.get(
            "rate",
            statistics["attendance_percentage"],
        ),

        "active_sessions": active_sessions,

        "active_attendance_count": len(
            active_sessions
        ),

        "active_count": len(
            active_sessions
        ),

        "can_manage": _can_manage(
            request
        ),
    }

    return render(
        request,
        "my_attendance.html",
        context,
    )


# =========================================================
# MANUAL ATTENDANCE UPDATE
# =========================================================


@login_required
def mark_attendance(
    request,
    attendance_id,
):
    """
    Manually update one attendance record.

    Management only.
    """

    if not _can_manage(request):

        messages.error(
            request,
            (
                "You do not have permission "
                "to manage attendance."
            ),
        )

        return _redirect_my_attendance()

    if request.method != "POST":

        return _redirect_attendance_list()

    attendance = get_object_or_404(
        AttendanceRecord.objects.select_related(
            "session",
            "user",
            "marked_by",
        ),
        pk=attendance_id,
    )

    form = AttendanceForm(
        request.POST,
        instance=attendance,
    )

    if not form.is_valid():

        messages.error(
            request,
            (
                "Please correct the "
                "attendance form errors."
            ),
        )

        return _redirect_session_detail(
            attendance.session
        )

    status = form.cleaned_data[
        "status"
    ]

    notes = (
        form.cleaned_data.get(
            "notes"
        )
        or ""
    ).strip()

    try:

        _process_attendance_status(
            session=attendance.session,
            user=attendance.user,
            status=status,
            marked_by=request.user,
            notes=notes,
        )

        messages.success(
            request,
            (
                "Attendance for "
                f"{_user_display_name(attendance.user)} "
                "has been updated successfully."
            ),
        )

    except AttendanceServiceError as exc:

        messages.error(
            request,
            str(exc),
        )

    return _redirect_session_detail(
        attendance.session
    )


# =========================================================
# RESET ATTENDANCE
# =========================================================


@login_required
def reset_attendance(
    request,
    attendance_id,
):
    """
    Reset one attendance record to PENDING.

    Management only.
    """

    if not _can_manage(request):

        messages.error(
            request,
            (
                "You do not have permission "
                "to reset attendance."
            ),
        )

        return _redirect_my_attendance()

    if request.method != "POST":

        return _redirect_attendance_list()

    attendance = get_object_or_404(
        AttendanceRecord.objects.select_related(
            "session",
            "user",
        ),
        pk=attendance_id,
    )

    session = attendance.session

    try:

        service_reset_attendance(
            session=session,
            user=attendance.user,
            marked_by=request.user,
        )

        messages.success(
            request,
            (
                "Attendance for "
                f"{_user_display_name(attendance.user)} "
                "has been reset to pending."
            ),
        )

    except AttendanceServiceError as exc:

        messages.error(
            request,
            str(exc),
        )

    return _redirect_session_detail(
        session
    )


# =========================================================
# ATTENDANCE REPORT
# =========================================================


@login_required
def attendance_report(request):
    """
    Generate the complete attendance report.

    Supports:

        - HTML
        - CSV
        - status filtering
        - date filtering
        - member searching

    Session statistics are obtained from the attendance
    service layer.

    IMPORTANT:

    This view never assigns values to read-only
    AttendanceSession properties such as:

        present_count
        absent_count
        excused_count
        pending_count
        total_records
    """

    if not _can_manage(request):

        messages.error(
            request,
            (
                "You do not have permission "
                "to view attendance reports."
            ),
        )

        return _redirect_my_attendance()

    # -----------------------------------------------------
    # FORM / FILTERS
    # -----------------------------------------------------

    form = AttendanceReportForm(
        request.GET or None
    )

    report_format = "html"

    records = _attendance_queryset()

    if form.is_valid():

        cleaned_data = form.cleaned_data

        records = _apply_attendance_filters(
            records,
            cleaned_data,
        )

        report_format = (
            cleaned_data.get(
                "report_format"
            )
            or "html"
        )

    # -----------------------------------------------------
    # IDENTIFY SESSIONS IN THE REPORT
    # -----------------------------------------------------

    session_ids = (
        records
        .values_list(
            "session_id",
            flat=True,
        )
        .distinct()
    )

    sessions_queryset = (
        AttendanceSession.objects
        .select_related(
            "created_by",
            "published_by",
            "closed_by",
        )
        .filter(
            pk__in=session_ids,
        )
        .order_by(
            "-opens_at",
            "-created_at",
        )
    )

    # -----------------------------------------------------
    # PREPARE / FINALIZE SESSIONS
    # -----------------------------------------------------

    sessions = _prepare_report_sessions(
        sessions_queryset
    )

    # -----------------------------------------------------
    # REFRESH RECORDS AFTER FINALIZATION
    # -----------------------------------------------------

    records = _attendance_queryset()

    if form.is_valid():

        records = _apply_attendance_filters(
            records,
            form.cleaned_data,
        )

    # -----------------------------------------------------
    # CSV EXPORT
    # -----------------------------------------------------

    if (
        request.method == "GET"
        and request.GET
        and form.is_valid()
        and report_format == "csv"
    ):

        response = HttpResponse(
            content_type="text/csv"
        )

        response["Content-Disposition"] = (
            'attachment; '
            'filename="kucsa_attendance_report.csv"'
        )

        writer = csv.writer(
            response
        )

        writer.writerow(
            [
                "Attendance Session",
                "Session Status",
                "Opening Time",
                "Closing Time",
                "Member",
                "Registration Number",
                "Username",
                "Email",
                "Status",
                "Attendance Time",
                "Marked By",
                "Marked At",
                "Notes",
            ]
        )

        for record in records:

            session = record.session

            writer.writerow(
                [
                    session.title,
                    session.get_status_display(),

                    session.opens_at or "",

                    session.closes_at or "",

                    _user_display_name(
                        record.user
                    ),

                    getattr(
                        record.user,
                        "registration_number",
                        "",
                    ),

                    getattr(
                        record.user,
                        "username",
                        "",
                    ),

                    getattr(
                        record.user,
                        "email",
                        "",
                    ),

                    record.get_status_display(),

                    getattr(
                        record,
                        "attendance_time",
                        "",
                    ),

                    (
                        _user_display_name(
                            record.marked_by
                        )
                        if record.marked_by
                        else ""
                    ),

                    getattr(
                        record,
                        "marked_at",
                        "",
                    ),

                    getattr(
                        record,
                        "notes",
                        "",
                    ),
                ]
            )

        return response

    # -----------------------------------------------------
    # OVERALL REPORT STATISTICS
    # -----------------------------------------------------

    try:

        statistics = calculate_attendance_statistics(
            records
        )

    except AttendanceServiceError:

        statistics = _calculate_statistics(
            records
        )

    except Exception:

        statistics = _calculate_statistics(
            records
        )

    # -----------------------------------------------------
    # CONTEXT
    # -----------------------------------------------------

    context = {
        "attendance_records": records,
        "records": records,

        "sessions": sessions,
        "attendance_sessions": sessions,

        "form": form,

        **statistics,

        "statistics": statistics,

        "can_manage": True,
    }

    return render(
        request,
        "attendance_report.html",
        context,
    )


# =========================================================
# SESSION REPORT
# =========================================================


@login_required
def attendance_session_report(request):
    """
    Generate a session-oriented attendance report.

    Each session receives statistics from the attendance
    service layer.

    Expired OPEN sessions are finalized before statistics
    are calculated.

    Read-only AttendanceSession properties are never assigned.
    """

    if not _can_manage(request):

        messages.error(
            request,
            (
                "You do not have permission "
                "to view attendance reports."
            ),
        )

        return _redirect_my_attendance()

    # -----------------------------------------------------
    # SESSION QUERYSET
    # -----------------------------------------------------

    sessions = _session_queryset()

    form = AttendanceSessionReportForm(
        request.GET or None
    )

    if form.is_valid():

        sessions = _apply_session_filters(
            sessions,
            form.cleaned_data,
        )

    # -----------------------------------------------------
    # PREPARE SESSIONS
    # -----------------------------------------------------

    sessions = _prepare_report_sessions(
        sessions
    )

    # -----------------------------------------------------
    # ENSURE SERVICE STATISTICS ARE AVAILABLE
    # -----------------------------------------------------

    for session in sessions:

        # Do NOT assign:
        #
        # session.present_count = ...
        # session.absent_count = ...
        #
        # These are read-only model properties.
        #
        # Instead, use a separate `statistics` attribute.

        session.statistics = (
            get_session_statistics(
                session
            )
        )

    # -----------------------------------------------------
    # OVERALL STATISTICS
    # -----------------------------------------------------

    session_ids = [
        session.pk
        for session in sessions
    ]

    if session_ids:

        records = (
            _attendance_queryset()
            .filter(
                session_id__in=session_ids
            )
        )

    else:

        records = (
            _attendance_queryset()
            .none()
        )

    try:

        statistics = calculate_attendance_statistics(
            records
        )

    except AttendanceServiceError:

        statistics = _calculate_statistics(
            records
        )

    except Exception:

        statistics = _calculate_statistics(
            records
        )

    # -----------------------------------------------------
    # CONTEXT
    # -----------------------------------------------------

    context = {
        "sessions": sessions,
        "attendance_sessions": sessions,

        "attendance_records": records,
        "records": records,

        "form": form,

        **statistics,

        "statistics": statistics,

        "can_manage": True,
    }

    return render(
        request,
        "attendance_report.html",
        context,
    )


# =========================================================
# UPDATE SESSION TIMING
# =========================================================


@login_required
def update_session_timing(
    request,
    session_id,
):
    """
    Update an attendance session's opening and closing
    times.

    Management only.
    """

    if not _can_manage(request):

        messages.error(
            request,
            (
                "You do not have permission "
                "to edit attendance sessions."
            ),
        )

        return _redirect_my_attendance()

    session = get_object_or_404(
        AttendanceSession,
        pk=session_id,
    )

    if request.method == "POST":

        form = AttendanceSessionTimingForm(
            request.POST,
            instance=session,
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                (
                    "Attendance session timing "
                    "has been updated."
                ),
            )

            return _redirect_session_detail(
                session
            )

    else:

        form = AttendanceSessionTimingForm(
            instance=session
        )

    context = {
        "form": form,

        "session": session,
        "attendance_session": session,

        "page_title": (
            "Update Attendance Session Timing"
        ),

        "can_manage": True,
    }

    return render(
        request,
        "session_form.html",
        context,
    )


# =========================================================
# ACTIVE SESSION STATUS
# =========================================================

@login_required
def active_session_status(
    request,
    session_id,
):
    """
    Display the current status of one attendance session.

    Only a PRESENT record is treated as attendance having
    been marked by the current user.

    `seconds_remaining` and `attendance_is_open` are read-only
    properties provided by AttendanceSession. They are accessed
    directly and are never assigned to by this view.
    """

    session = get_object_or_404(
        _session_queryset(),
        pk=session_id,
    )

    session = _prepare_session(
        session
    )

    active_sessions = []

    # `attendance_is_open` is a read-only property on the model.
    if session.attendance_is_open:

        attendance_status = (
            AttendanceRecord.AttendanceStatus
        )

        attendance = (
            AttendanceRecord.objects
            .select_related(
                "session",
                "user",
                "marked_by",
            )
            .filter(
                session=session,
                user=request.user,
            )
            .first()
        )

        # Only PRESENT means the user has successfully
        # marked their attendance.
        attendance_marked = (
            attendance is not None
            and attendance.status
            == attendance_status.PRESENT
        )

        # Attach user-specific information to the session.
        # These are dynamic view attributes, not model properties.
        session.attendance_record = (
            attendance
        )

        session.attendance_marked = (
            attendance_marked
        )

        session.can_mark_attendance = (
            not attendance_marked
            and (
                attendance is None
                or attendance.status
                == attendance_status.PENDING
            )
        )

        # Only expose PRESENT as actual user attendance.
        session.user_attendance = (
            attendance
            if attendance_marked
            else None
        )

        # DO NOT assign:
        #
        #     session.seconds_remaining = ...
        #
        # `seconds_remaining` is calculated dynamically by
        # AttendanceSession and can be accessed directly through:
        #
        #     session.seconds_remaining
        #
        # Likewise, `attendance_is_open` is already available as:
        #
        #     session.attendance_is_open

        active_sessions.append(
            session
        )

    context = {
        "active_sessions": active_sessions,

        "active_count": len(
            active_sessions
        ),

        "active_attendance_count": len(
            active_sessions
        ),

        "can_manage": _can_manage(
            request
        ),
    }

    return render(
        request,
        "active_attendance.html",
        context,
    )
