"""
KUCSA Attendance Services
=========================

Business logic for the KUCSA attendance application.

Architecture
------------

AttendanceSession
        |
        └── AttendanceRecord
                |
                └── User


The attendance application is intentionally independent of:

    - Events
    - EventRegistration
    - Event attendance
    - Event eligibility

Responsibilities
----------------

This service layer is responsible for:

    - creating attendance sessions
    - opening sessions
    - closing sessions
    - expiring sessions
    - finalizing expired attendance
    - creating attendance records
    - marking members present
    - marking members absent
    - marking members excused
    - resetting attendance
    - self-attendance
    - bulk attendance updates
    - retrieving attendance
    - attendance statistics
    - attendance validation
    - attendance time handling
    - attendance notes

Important attendance rule
-------------------------

For an expired attendance session:

    PRESENT
        -> remains PRESENT

    ABSENT
        -> remains ABSENT

    EXCUSED
        -> remains EXCUSED

    PENDING
        -> automatically becomes ABSENT

This ensures that an expired session always has a
complete attendance report.

The service layer does NOT handle:

    - HTTP requests
    - forms
    - templates
    - redirects
    - messages
    - authentication decorators
    - URL routing

Views should call these services rather than manipulating
attendance records directly.
"""


from __future__ import annotations


from datetime import timedelta
from typing import Iterable

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone


from .models import (
    AttendanceRecord,
    AttendanceSession,
)


User = get_user_model()


# =========================================================
# CONSTANTS
# =========================================================

DEFAULT_SESSION_DURATION = timedelta(hours=1)

MIN_SESSION_DURATION = timedelta(minutes=1)

MAX_SESSION_DURATION = timedelta(days=7)


# =========================================================
# SYSTEM NOTES
# =========================================================

AUTO_ABSENT_NOTE = (
    "Automatically marked absent because the attendance "
    "window expired without the member marking attendance."
)

AUTO_EXPIRED_NOTE = (
    "Automatically finalized as absent when the "
    "attendance session expired."
)


# =========================================================
# EXCEPTIONS
# =========================================================


class AttendanceServiceError(Exception):
    """
    Base exception for attendance service errors.
    """

    pass


class AttendancePermissionError(
    AttendanceServiceError
):
    """
    Raised when an attendance operation is not permitted.
    """

    pass


class AttendanceSessionError(
    AttendanceServiceError
):
    """
    Raised when a session operation is invalid.
    """

    pass


class AttendanceRecordError(
    AttendanceServiceError
):
    """
    Raised when an attendance record operation is invalid.
    """

    pass


# =========================================================
# MODEL ENUM HELPERS
# =========================================================


def _session_status():
    """
    Return the AttendanceSession status enum.
    """

    return AttendanceSession.SessionStatus


def _attendance_status():
    """
    Return the AttendanceRecord status enum.
    """

    return AttendanceRecord.AttendanceStatus


# =========================================================
# USER VALIDATION
# =========================================================


def _validate_user(user):
    """
    Validate that a user object exists and is authenticated.
    """

    if user is None:
        raise AttendanceRecordError(
            "A valid member is required."
        )

    if not getattr(
        user,
        "is_authenticated",
        False,
    ):
        raise AttendanceRecordError(
            "The member must be authenticated."
        )

    return user


# =========================================================
# MANAGEMENT PERMISSIONS
# =========================================================


def can_manage_attendance(user) -> bool:
    """
    Determine whether a user can manage attendance.

    Management access:

        - superusers
        - staff users
        - authenticated users with an Executive record
    """

    if not user:
        return False

    if not getattr(
        user,
        "is_authenticated",
        False,
    ):
        return False

    if getattr(
        user,
        "is_superuser",
        False,
    ):
        return True

    if getattr(
        user,
        "is_staff",
        False,
    ):
        return True

    try:

        from executives.models import Executive

        return Executive.objects.filter(
            user=user
        ).exists()

    except Exception:
        return False


def require_attendance_manager(user):
    """
    Require the user to have attendance management access.
    """

    if not can_manage_attendance(user):

        raise AttendancePermissionError(
            "You do not have permission to manage attendance."
        )

    return user


# =========================================================
# QUERYSETS
# =========================================================


def attendance_session_queryset() -> QuerySet:
    """
    Return the optimized attendance session queryset.
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


def attendance_record_queryset() -> QuerySet:
    """
    Return the optimized attendance record queryset.
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


def session_records(
    session: AttendanceSession,
) -> QuerySet:
    """
    Return all attendance records for one session.
    """

    return (
        attendance_record_queryset()
        .filter(
            session=session
        )
    )


def user_attendance(
    user,
) -> QuerySet:
    """
    Return all attendance records belonging to one user.
    """

    _validate_user(user)

    return (
        attendance_record_queryset()
        .filter(
            user=user
        )
    )


# =========================================================
# SESSION VALIDATION
# =========================================================


def _validate_session(session):
    """
    Validate an attendance session instance.
    """

    if session is None:
        raise AttendanceSessionError(
            "Attendance session is required."
        )

    if not isinstance(
        session,
        AttendanceSession,
    ):
        raise AttendanceSessionError(
            "Invalid attendance session."
        )

    return session


def _session_is_open(session) -> bool:
    return (
        session.status
        == _session_status().OPEN
    )


def _session_is_draft(session) -> bool:
    return (
        session.status
        == _session_status().DRAFT
    )


def _session_is_closed(session) -> bool:
    return (
        session.status
        == _session_status().CLOSED
    )


def _session_is_expired(session) -> bool:
    return (
        session.status
        == _session_status().EXPIRED
    )


# =========================================================
# SESSION TIME HELPERS
# =========================================================


def _normalize_session_times(
    opens_at=None,
    closes_at=None,
):
    """
    Normalize session opening and closing times.
    """

    now = timezone.now()

    if opens_at is None:
        opens_at = now

    if closes_at is None:
        closes_at = (
            opens_at
            + DEFAULT_SESSION_DURATION
        )

    if closes_at <= opens_at:

        raise AttendanceSessionError(
            "Closing time must be after opening time."
        )

    duration = closes_at - opens_at

    if duration < MIN_SESSION_DURATION:

        raise AttendanceSessionError(
            "Attendance session must last at least one minute."
        )

    if duration > MAX_SESSION_DURATION:

        raise AttendanceSessionError(
            "Attendance session cannot be longer than seven days."
        )

    return opens_at, closes_at


def attendance_seconds_remaining(
    session: AttendanceSession,
) -> int:
    """
    Return the number of seconds remaining.
    """

    _validate_session(session)

    if not session.closes_at:
        return 0

    if not _session_is_open(session):
        return 0

    remaining = (
        session.closes_at
        - timezone.now()
    ).total_seconds()

    return max(
        0,
        int(remaining),
    )


# =========================================================
# FINALIZE PENDING RECORDS
# =========================================================


def _finalize_pending_attendance_records(
    *,
    session: AttendanceSession,
) -> int:
    """
    Finalize all remaining PENDING attendance records
    when a session expires.

    Attendance rule:

        PRESENT -> untouched
        ABSENT  -> untouched
        EXCUSED -> untouched
        PENDING -> ABSENT

    This guarantees that an expired attendance session
    contains a complete and reportable attendance result.

    Returns:
        Number of records automatically marked ABSENT.
    """

    _validate_session(session)

    status = _attendance_status()

    pending_records = (
        AttendanceRecord.objects
        .select_for_update()
        .filter(
            session=session,
            status=status.PENDING,
        )
    )

    now = timezone.now()

    count = pending_records.update(
        status=status.ABSENT,
        attendance_time=None,
        marked_by=None,
        notes=AUTO_ABSENT_NOTE,
        **(
            {"marked_at": now}
            if hasattr(
                AttendanceRecord,
                "marked_at",
            )
            else {}
        ),
    )

    return count


def _finalize_closed_session_records(
    *,
    session: AttendanceSession,
) -> int:
    """
    Finalize pending records when management explicitly
    closes an attendance session.

    This is intentionally the same attendance rule used
    for expiration.

    Anyone who did not mark PRESENT before the session
    was finalized is considered ABSENT unless already
    EXCUSED or otherwise finalized.
    """

    return _finalize_pending_attendance_records(
        session=session
    )


# =========================================================
# SESSION EXPIRY
# =========================================================


@transaction.atomic
def expire_attendance_session_if_needed(
    session: AttendanceSession,
) -> AttendanceSession:
    """
    Automatically expire an open attendance session when
    its closing time has passed.

    IMPORTANT:

    Expiration also finalizes every remaining PENDING
    attendance record as ABSENT.

    This makes the attendance report complete immediately
    after the session expires.
    """

    _validate_session(session)

    if not _session_is_open(session):
        return session

    if not session.closes_at:
        return session

    now = timezone.now()

    if now < session.closes_at:
        return session

    # -----------------------------------------------------
    # Lock the session before changing it.
    # -----------------------------------------------------

    session = (
        AttendanceSession.objects
        .select_for_update()
        .get(pk=session.pk)
    )

    # Another request may already have expired it.
    if not _session_is_open(session):
        return session

    # -----------------------------------------------------
    # IMPORTANT:
    #
    # Finalize pending records BEFORE changing the session
    # status so the complete operation happens atomically.
    # -----------------------------------------------------

    _finalize_pending_attendance_records(
        session=session
    )

    session.status = _session_status().EXPIRED

    update_fields = ["status"]

    if hasattr(
        AttendanceSession,
        "updated_at",
    ):
        update_fields.append(
            "updated_at"
        )

    session.save(
        update_fields=update_fields
    )

    return session


def expire_due_sessions():
    """
    Expire all attendance sessions whose closing time
    has passed.

    Every expired session is also finalized:

        PENDING -> ABSENT

    Returns:
        Number of sessions expired.
    """

    now = timezone.now()

    session_ids = list(
        AttendanceSession.objects.filter(
            status=_session_status().OPEN,
            closes_at__isnull=False,
            closes_at__lte=now,
        ).values_list(
            "pk",
            flat=True,
        )
    )

    count = 0

    for session_id in session_ids:

        try:

            session = (
                AttendanceSession.objects
                .get(pk=session_id)
            )

            previous_status = session.status

            expire_attendance_session_if_needed(
                session
            )

            if (
                previous_status
                == _session_status().OPEN
            ):
                count += 1

        except AttendanceSession.DoesNotExist:
            continue

    return count


# =========================================================
# CREATE SESSION
# =========================================================


@transaction.atomic
def create_attendance_session(
    *,
    user,
    title: str,
    description: str = "",
    opens_at=None,
    closes_at=None,
) -> AttendanceSession:

    require_attendance_manager(user)

    title = (
        str(title or "")
        .strip()
    )

    description = (
        str(description or "")
        .strip()
    )

    if not title:
        raise AttendanceSessionError(
            "Attendance session title is required."
        )

    opens_at, closes_at = (
        _normalize_session_times(
            opens_at,
            closes_at,
        )
    )

    session = AttendanceSession.objects.create(
        title=title,
        description=description,
        status=_session_status().DRAFT,
        opens_at=opens_at,
        closes_at=closes_at,
        created_by=user,
    )

    return session


# =========================================================
# UPDATE SESSION
# =========================================================


@transaction.atomic
def update_attendance_session(
    *,
    session: AttendanceSession,
    user,
    title=None,
    description=None,
    opens_at=None,
    closes_at=None,
) -> AttendanceSession:

    require_attendance_manager(user)

    session = _validate_session(session)

    session = (
        AttendanceSession.objects
        .select_for_update()
        .get(pk=session.pk)
    )

    if not _session_is_draft(session):

        raise AttendanceSessionError(
            "Only draft attendance sessions can be edited."
        )

    if title is not None:

        title = str(title).strip()

        if not title:
            raise AttendanceSessionError(
                "Attendance session title is required."
            )

        session.title = title

    if description is not None:

        session.description = (
            str(description).strip()
        )

    if (
        opens_at is not None
        or closes_at is not None
    ):

        new_opens_at = (
            opens_at
            if opens_at is not None
            else session.opens_at
        )

        new_closes_at = (
            closes_at
            if closes_at is not None
            else session.closes_at
        )

        (
            new_opens_at,
            new_closes_at,
        ) = _normalize_session_times(
            new_opens_at,
            new_closes_at,
        )

        session.opens_at = new_opens_at
        session.closes_at = new_closes_at

    session.save()

    return session


# =========================================================
# OPEN SESSION
# =========================================================


@transaction.atomic
def open_attendance_session(
    *,
    session: AttendanceSession,
    user,
) -> AttendanceSession:

    require_attendance_manager(user)

    session = _validate_session(session)

    session = (
        AttendanceSession.objects
        .select_for_update()
        .get(pk=session.pk)
    )

    if not _session_is_draft(session):

        raise AttendanceSessionError(
            "Only draft attendance sessions can be opened."
        )

    now = timezone.now()

    if not session.opens_at:
        session.opens_at = now

    if not session.closes_at:

        session.closes_at = (
            session.opens_at
            + DEFAULT_SESSION_DURATION
        )

    if session.closes_at <= session.opens_at:

        raise AttendanceSessionError(
            "Closing time must be after opening time."
        )

    if session.closes_at <= now:

        raise AttendanceSessionError(
            "This attendance session has already expired. "
            "Set a future closing time before opening it."
        )

    session.status = _session_status().OPEN
    session.published_by = user

    session.save()

    _create_missing_attendance_records(
        session=session
    )

    return session


# =========================================================
# CLOSE SESSION
# =========================================================


@transaction.atomic
def close_attendance_session(
    *,
    session: AttendanceSession,
    user,
) -> AttendanceSession:

    require_attendance_manager(user)

    session = _validate_session(session)

    session = (
        AttendanceSession.objects
        .select_for_update()
        .get(pk=session.pk)
    )

    if _session_is_closed(session):

        raise AttendanceSessionError(
            "Attendance session is already closed."
        )

    if _session_is_expired(session):

        raise AttendanceSessionError(
            "An expired attendance session cannot be closed."
        )

    if _session_is_draft(session):

        raise AttendanceSessionError(
            "A draft attendance session cannot be closed."
        )

    # -----------------------------------------------------
    # FINALIZE PENDING MEMBERS WHEN SESSION IS CLOSED.
    # -----------------------------------------------------

    _finalize_closed_session_records(
        session=session
    )

    session.status = _session_status().CLOSED
    session.closed_by = user

    session.save()

    return session


# =========================================================
# RECORD CREATION
# =========================================================


def _create_missing_attendance_records(
    *,
    session: AttendanceSession,
):
    """
    Create missing PENDING attendance records for all
    active users.
    """

    _validate_session(session)

    users = User.objects.filter(
        is_active=True
    ).only("pk")

    existing_user_ids = set(
        AttendanceRecord.objects.filter(
            session=session
        ).values_list(
            "user_id",
            flat=True,
        )
    )

    new_records = []

    for user in users:

        if user.pk in existing_user_ids:
            continue

        new_records.append(
            AttendanceRecord(
                session=session,
                user=user,
                status=_attendance_status().PENDING,
            )
        )

    if new_records:

        AttendanceRecord.objects.bulk_create(
            new_records,
            ignore_conflicts=True,
        )

    return new_records


@transaction.atomic
def ensure_attendance_record(
    *,
    session: AttendanceSession,
    user,
) -> AttendanceRecord:

    _validate_session(session)
    _validate_user(user)

    record, created = (
        AttendanceRecord.objects.get_or_create(
            session=session,
            user=user,
            defaults={
                "status": _attendance_status().PENDING,
            },
        )
    )

    return record


# =========================================================
# RECORD VALIDATION
# =========================================================


def _get_locked_record(
    *,
    session,
    user,
):

    try:

        return (
            AttendanceRecord.objects
            .select_for_update()
            .get(
                session=session,
                user=user,
            )
        )

    except AttendanceRecord.DoesNotExist:

        return ensure_attendance_record(
            session=session,
            user=user,
        )


def _validate_manual_attendance_session(
    session,
):

    session = expire_attendance_session_if_needed(
        session
    )

    if _session_is_draft(session):

        raise AttendanceSessionError(
            "Attendance cannot be managed before the "
            "session is opened."
        )

    return session


# =========================================================
# PRESENT
# =========================================================


@transaction.atomic
def mark_present(
    *,
    session: AttendanceSession,
    user,
    marked_by=None,
    notes: str = "",
) -> AttendanceRecord:
    """
    Mark a member as PRESENT.

    Notes are preserved when supplied by management.
    """

    _validate_user(user)

    session = _validate_manual_attendance_session(
        session
    )

    if marked_by is not None:
        _validate_user(marked_by)

    record = _get_locked_record(
        session=session,
        user=user,
    )

    record.status = _attendance_status().PRESENT
    record.attendance_time = timezone.now()
    record.marked_by = marked_by

    cleaned_notes = str(
        notes or ""
    ).strip()

    if cleaned_notes:
        record.notes = cleaned_notes
    elif not record.notes:
        record.notes = ""

    record.save()

    return record


# =========================================================
# ABSENT
# =========================================================


@transaction.atomic
def mark_absent(
    *,
    session: AttendanceSession,
    user,
    marked_by,
    notes: str = "",
) -> AttendanceRecord:

    require_attendance_manager(marked_by)

    _validate_user(user)

    session = _validate_manual_attendance_session(
        session
    )

    record = _get_locked_record(
        session=session,
        user=user,
    )

    record.status = _attendance_status().ABSENT
    record.attendance_time = None
    record.marked_by = marked_by
    record.notes = str(
        notes or ""
    ).strip()

    record.save()

    return record


# =========================================================
# EXCUSED
# =========================================================


@transaction.atomic
def mark_excused(
    *,
    session: AttendanceSession,
    user,
    marked_by,
    notes: str = "",
) -> AttendanceRecord:

    require_attendance_manager(marked_by)

    _validate_user(user)

    session = _validate_manual_attendance_session(
        session
    )

    record = _get_locked_record(
        session=session,
        user=user,
    )

    record.status = _attendance_status().EXCUSED
    record.attendance_time = None
    record.marked_by = marked_by
    record.notes = str(
        notes or ""
    ).strip()

    record.save()

    return record


# =========================================================
# RESET ATTENDANCE
# =========================================================


@transaction.atomic
def reset_attendance(
    *,
    session: AttendanceSession,
    user,
    marked_by,
) -> AttendanceRecord:

    require_attendance_manager(marked_by)

    _validate_user(user)

    session = _validate_manual_attendance_session(
        session
    )

    record = _get_locked_record(
        session=session,
        user=user,
    )

    record.status = _attendance_status().PENDING
    record.attendance_time = None
    record.marked_by = marked_by
    record.notes = ""

    record.save()

    return record


# =========================================================
# SELF ATTENDANCE
# =========================================================


@transaction.atomic
def mark_self_attendance(
    *,
    session: AttendanceSession,
    user,
) -> AttendanceRecord:
    """
    Mark the authenticated user as PRESENT.

    Self-attendance is allowed only while the session
    is OPEN.

    The system records:

        status          = PRESENT
        attendance_time = current time
        marked_by        = the member themselves

    Notes remain empty for normal self-attendance because
    the member has simply confirmed physical presence.
    """

    _validate_user(user)

    session = _validate_session(session)

    session = expire_attendance_session_if_needed(
        session
    )

    if not _session_is_open(session):

        raise AttendanceSessionError(
            "Self-attendance is only available while "
            "the attendance session is open."
        )

    if attendance_seconds_remaining(session) <= 0:

        raise AttendanceSessionError(
            "The attendance window has ended."
        )

    record = _get_locked_record(
        session=session,
        user=user,
    )

    record.status = _attendance_status().PRESENT
    record.attendance_time = timezone.now()
    record.marked_by = user

    # Do not destroy an existing explanatory note.
    if not record.notes:
        record.notes = ""

    record.save()

    return record


# =========================================================
# BULK ATTENDANCE
# =========================================================


@transaction.atomic
def mark_bulk_attendance(
    *,
    attendance_ids: Iterable[int],
    status: str,
    marked_by,
    notes: str = "",
):

    require_attendance_manager(marked_by)

    if not attendance_ids:

        raise AttendanceRecordError(
            "No attendance records were selected."
        )

    valid_statuses = {
        value
        for value, _label
        in _attendance_status().choices
    }

    if status not in valid_statuses:

        raise AttendanceRecordError(
            "Invalid attendance status."
        )

    attendance_ids = list(
        dict.fromkeys(
            int(record_id)
            for record_id in attendance_ids
        )
    )

    records = list(
        AttendanceRecord.objects
        .select_for_update()
        .select_related(
            "session",
            "user",
        )
        .filter(
            pk__in=attendance_ids
        )
    )

    if not records:

        raise AttendanceRecordError(
            "No valid attendance records were found."
        )

    now = timezone.now()

    updated_records = []

    for record in records:

        session = (
            expire_attendance_session_if_needed(
                record.session
            )
        )

        if _session_is_draft(session):

            raise AttendanceSessionError(
                (
                    f'Attendance session '
                    f'"{session.title}" has not been opened.'
                )
            )

        record.status = status
        record.marked_by = marked_by

        if status == _attendance_status().PRESENT:

            record.attendance_time = now

            cleaned_notes = str(
                notes or ""
            ).strip()

            if cleaned_notes:
                record.notes = cleaned_notes

        elif status in (
            _attendance_status().ABSENT,
            _attendance_status().EXCUSED,
        ):

            record.attendance_time = None

            record.notes = str(
                notes or ""
            ).strip()

        elif status == _attendance_status().PENDING:

            record.attendance_time = None
            record.notes = ""

        record.save()

        updated_records.append(record)

    return updated_records


# =========================================================
# MEMBER ATTENDANCE
# =========================================================


def get_member_attendance(
    user,
) -> QuerySet:

    _validate_user(user)

    return (
        attendance_record_queryset()
        .filter(
            user=user
        )
    )


def get_member_attendance_statistics(
    user,
) -> dict:

    records = get_member_attendance(user)

    return calculate_attendance_statistics(
        records
    )


# =========================================================
# STATISTICS
# =========================================================


def calculate_attendance_statistics(
    records: QuerySet,
) -> dict:
    """
    Calculate attendance statistics.

    Pending records are excluded from finalized
    attendance percentage.

    For expired sessions, pending records should already
    have been converted to ABSENT by the expiration
    service.
    """

    status = _attendance_status()

    total = records.count()

    present = records.filter(
        status=status.PRESENT
    ).count()

    absent = records.filter(
        status=status.ABSENT
    ).count()

    excused = records.filter(
        status=status.EXCUSED
    ).count()

    pending = records.filter(
        status=status.PENDING
    ).count()

    finalized = (
        present
        + absent
        + excused
    )

    percentage = (
        round(
            (
                present
                / finalized
            )
            * 100,
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

        "attendance_percentage": percentage,
    }


def get_session_statistics(
    session: AttendanceSession,
) -> dict:
    """
    Return complete statistics for one session.

    Before calculating statistics, an expired session is
    finalized so its pending records cannot remain pending.
    """

    _validate_session(session)

    session = expire_attendance_session_if_needed(
        session
    )

    records = session_records(
        session
    )

    return calculate_attendance_statistics(
        records
    )


# =========================================================
# SESSION ATTENDANCE
# =========================================================


def get_session_attendance(
    session: AttendanceSession,
) -> QuerySet:

    _validate_session(session)

    session = expire_attendance_session_if_needed(
        session
    )

    return session_records(
        session
    )


# =========================================================
# USER SESSION ATTENDANCE
# =========================================================


def get_user_session_attendance(
    *,
    user,
    session: AttendanceSession,
):

    _validate_user(user)
    _validate_session(session)

    return (
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


# =========================================================
# ACTIVE SESSIONS
# =========================================================


def get_active_sessions():
    """
    Return currently open attendance sessions.

    Expired sessions are finalized before being removed
    from the active result.
    """

    expire_due_sessions()

    now = timezone.now()

    return (
        attendance_session_queryset()
        .filter(
            status=_session_status().OPEN,
            opens_at__lte=now,
            closes_at__gt=now,
        )
        .order_by(
            "closes_at",
            "-opens_at",
        )
    )


def get_active_sessions_for_user(
    user,
):

    _validate_user(user)

    sessions = list(
        get_active_sessions()
    )

    if not sessions:
        return sessions

    records = {
        record.session_id: record
        for record in (
            AttendanceRecord.objects
            .select_related(
                "session",
                "user",
                "marked_by",
            )
            .filter(
                user=user,
                session_id__in=[
                    session.pk
                    for session in sessions
                ],
            )
        )
    }

    for session in sessions:

        record = records.get(
            session.pk
        )

        session.user_attendance = (
            record
            if (
                record
                and record.status
                == _attendance_status().PRESENT
            )
            else None
        )

        session.attendance_record = record

        session.attendance_marked = (
            record is not None
            and record.status
            == _attendance_status().PRESENT
        )

        session.can_mark_attendance = (
            not session.attendance_marked
            and (
                record is None
                or record.status
                == _attendance_status().PENDING
            )
        )

        session.seconds_remaining = (
            attendance_seconds_remaining(
                session
            )
        )

        session.attendance_is_open = (
            session.seconds_remaining > 0
        )

    return sessions


# =========================================================
# SESSION STATUS
# =========================================================


def get_session_status(
    session: AttendanceSession,
):

    session = (
        expire_attendance_session_if_needed(
            session
        )
    )

    return session.status


# =========================================================
# ATTENDANCE ELIGIBILITY
# =========================================================


def can_self_mark_attendance(
    *,
    user,
    session: AttendanceSession,
) -> bool:

    if not user:
        return False

    if not getattr(
        user,
        "is_authenticated",
        False,
    ):
        return False

    try:

        session = (
            expire_attendance_session_if_needed(
                session
            )
        )

        return (
            _session_is_open(session)
            and attendance_seconds_remaining(
                session
            ) > 0
        )

    except AttendanceServiceError:

        return False


# =========================================================
# ATTENDANCE STATUS LABEL
# =========================================================


def attendance_status_label(
    status: str,
) -> str:

    for value, label in (
        _attendance_status().choices
    ):

        if value == status:
            return label

    return str(status)


def session_status_label(
    status: str,
) -> str:

    for value, label in (
        _session_status().choices
    ):

        if value == status:
            return label

    return str(status)


# =========================================================
# DELETE SESSION
# =========================================================


@transaction.atomic
def delete_attendance_session(
    *,
    session: AttendanceSession,
    user,
):

    require_attendance_manager(user)

    session = _validate_session(session)

    if not _session_is_draft(session):

        raise AttendanceSessionError(
            "Only draft attendance sessions can be deleted."
        )

    session.delete()


# =========================================================
# BULK RECORD CREATION
# =========================================================


@transaction.atomic
def populate_session_attendance(
    *,
    session: AttendanceSession,
    user,
):

    require_attendance_manager(user)

    session = _validate_session(session)

    if _session_is_draft(session):

        raise AttendanceSessionError(
            "Open the attendance session before populating "
            "attendance records."
        )

    created = _create_missing_attendance_records(
        session=session
    )

    return len(created)