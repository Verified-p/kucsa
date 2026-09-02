# attendance/models.py

"""
KUCSA Attendance Models
=======================

Standalone attendance management system for KUCSA.

ARCHITECTURE
------------

    User
      |
      └── AttendanceRecord
                |
                └── AttendanceSession


IMPORTANT
---------

This application is intentionally independent of the
Events application.

There is NO relationship with:

    - Event
    - EventRegistration
    - event attendance
    - event participation

Attendance sessions are general sessions used to record
whether KUCSA members/students attended a particular
attendance session.


ATTENDANCE FLOW
---------------

1. Management creates an attendance session.

2. The session starts as DRAFT.

3. Management opens the session.

4. Members can mark themselves PRESENT while the
   attendance session is OPEN.

5. Management can manually manage attendance records.

6. The session can be manually CLOSED.

7. A session can become EXPIRED after its closing time.

8. Attendance records remain available for reporting
   after a session is closed or expired.


IMPORTANT DESIGN RULE
---------------------

Business logic belongs in:

    attendance.services

The models are responsible for:

    - database structure
    - validation
    - simple read-only properties
    - relationships
    - status/source helpers

The models do NOT:

    - open sessions
    - close sessions
    - expire sessions
    - mark attendance
    - create attendance records automatically
    - calculate report annotations


IMPORTANT
---------

Do NOT create model properties with names commonly used
for Django queryset annotations, such as:

    present_count
    absent_count
    excused_count
    pending_count
    total_records

Attendance statistics are handled by the service layer.

This prevents errors such as:

    AttributeError:
    property 'present_count' of 'AttendanceSession'
    object has no setter
"""


from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# =========================================================
# ATTENDANCE SESSION
# =========================================================


class AttendanceSession(models.Model):
    """
    Represents one standalone attendance session.

    A session does not belong to an event.

    Examples:

        KUCSA General Meeting
        Weekly Monday Attendance
        Semester Opening Attendance
    """

    # =====================================================
    # SESSION STATUS
    # =====================================================

    class SessionStatus(models.TextChoices):
        """
        Lifecycle states of an attendance session.
        """

        DRAFT = "DRAFT", "Draft"

        OPEN = "OPEN", "Open"

        CLOSED = "CLOSED", "Closed"

        EXPIRED = "EXPIRED", "Expired"

    # =====================================================
    # BASIC INFORMATION
    # =====================================================

    title = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Name of the attendance session.",
    )

    description = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Optional description or instructions "
            "for members."
        ),
    )

    # =====================================================
    # SESSION STATUS
    # =====================================================

    status = models.CharField(
        max_length=20,
        choices=SessionStatus.choices,
        default=SessionStatus.DRAFT,
        db_index=True,
        help_text=(
            "Current lifecycle status of the "
            "attendance session."
        ),
    )

    # =====================================================
    # ATTENDANCE WINDOW
    # =====================================================

    opens_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Date and time when members can start "
            "marking attendance."
        ),
    )

    closes_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Date and time when the attendance "
            "window closes."
        ),
    )

    # =====================================================
    # AUDIT INFORMATION
    # =====================================================

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_attendance_sessions",
        help_text=(
            "User who created the attendance session."
        ),
    )

    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_attendance_sessions",
        help_text=(
            "User who opened/published the attendance "
            "session."
        ),
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Date and time when the attendance session "
            "was opened."
        ),
    )

    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_attendance_sessions",
        help_text=(
            "User who manually closed the attendance "
            "session."
        ),
    )

    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Date and time when the attendance session "
            "was manually closed."
        ),
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # =====================================================
    # META
    # =====================================================

    class Meta:
        ordering = (
            "-created_at",
            "-pk",
        )

        indexes = [
            models.Index(
                fields=[
                    "status",
                    "opens_at",
                ],
                name="att_sess_status_open",
            ),
            models.Index(
                fields=[
                    "status",
                    "closes_at",
                ],
                name="att_sess_status_close",
            ),
            models.Index(
                fields=[
                    "-created_at",
                ],
                name="att_sess_created",
            ),
        ]

        verbose_name = "Attendance Session"
        verbose_name_plural = "Attendance Sessions"

    # =====================================================
    # STRING REPRESENTATION
    # =====================================================

    def __str__(self):
        return self.title

    # =====================================================
    # VALIDATION
    # =====================================================

    def clean(self):
        """
        Validate attendance session data.

        Business operations such as opening, closing and
        automatic expiry remain in attendance.services.
        """

        super().clean()

        if self.title:
            self.title = self.title.strip()

        if self.description:
            self.description = self.description.strip()

        if (
            self.opens_at
            and self.closes_at
            and self.closes_at <= self.opens_at
        ):
            raise ValidationError(
                {
                    "closes_at": (
                        "Closing time must be after "
                        "opening time."
                    )
                }
            )

    # =====================================================
    # SESSION PROPERTIES
    # =====================================================

    @property
    def is_draft(self):
        """
        Return True when the session is still a draft.
        """

        return (
            self.status
            == self.SessionStatus.DRAFT
        )

    @property
    def is_open(self):
        """
        Return True when the session status is OPEN.
        """

        return (
            self.status
            == self.SessionStatus.OPEN
        )

    @property
    def is_closed(self):
        """
        Return True when the session was manually closed.
        """

        return (
            self.status
            == self.SessionStatus.CLOSED
        )

    @property
    def is_expired(self):
        """
        Return True when the session is expired.

        This property does NOT modify the database.

        Automatic expiration belongs to attendance.services.
        """

        if self.status == self.SessionStatus.EXPIRED:
            return True

        if not self.closes_at:
            return False

        return (
            self.status == self.SessionStatus.OPEN
            and timezone.now() >= self.closes_at
        )

    @property
    def attendance_is_open(self):
        """
        Determine whether members should currently be able
        to mark attendance.

        The service layer remains responsible for enforcing
        attendance permissions and state changes.
        """

        if self.status != self.SessionStatus.OPEN:
            return False

        now = timezone.now()

        if self.opens_at and now < self.opens_at:
            return False

        if self.closes_at and now >= self.closes_at:
            return False

        return True

    @property
    def seconds_remaining(self):
        """
        Return the number of seconds remaining in the
        attendance window.

        Returns:

            0
                when the session is not open or has expired.

            positive integer
                when attendance is currently available.

            None
                when no closing time has been configured.
        """

        if self.status != self.SessionStatus.OPEN:
            return 0

        if not self.closes_at:
            return None

        remaining = (
            self.closes_at - timezone.now()
        ).total_seconds()

        return max(
            0,
            int(remaining),
        )


# =========================================================
# ATTENDANCE RECORD
# =========================================================


class AttendanceRecord(models.Model):
    """
    Represents one user's attendance in one session.

    One user can have only one attendance record for a
    particular attendance session.
    """

    # =====================================================
    # ATTENDANCE STATUS
    # =====================================================

    class AttendanceStatus(models.TextChoices):
        """
        Possible states of an attendance record.
        """

        PENDING = "PENDING", "Pending"

        PRESENT = "PRESENT", "Present"

        ABSENT = "ABSENT", "Absent"

        EXCUSED = "EXCUSED", "Excused"

    # =====================================================
    # ATTENDANCE SOURCE
    # =====================================================

    class AttendanceSource(models.TextChoices):
        """
        Identifies how the attendance record was created
        or last recorded.

        SELF:
            Member marked themselves.

        MANUAL:
            Authorized management marked the member.

        SYSTEM:
            System-level process created/updated it.
        """

        SELF = "SELF", "Self Marked"

        MANUAL = "MANUAL", "Manually Marked"

        SYSTEM = "SYSTEM", "System"

    # =====================================================
    # SESSION
    # =====================================================

    session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name="attendance_records",
        db_index=True,
        help_text=(
            "Attendance session to which this record "
            "belongs."
        ),
    )

    # =====================================================
    # USER
    # =====================================================

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
        db_index=True,
        help_text=(
            "Member/student whose attendance is being "
            "recorded."
        ),
    )

    # =====================================================
    # STATUS
    # =====================================================

    status = models.CharField(
        max_length=20,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PENDING,
        db_index=True,
        help_text="Current attendance status.",
    )

    # =====================================================
    # SOURCE
    # =====================================================

    source = models.CharField(
        max_length=20,
        choices=AttendanceSource.choices,
        default=AttendanceSource.SYSTEM,
        db_index=True,
        help_text=(
            "How this attendance record was recorded."
        ),
    )

    # =====================================================
    # ATTENDANCE TIMING
    # =====================================================

    attendance_time = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Date and time when the member was recorded "
            "as present."
        ),
    )

    # =====================================================
    # MANAGEMENT AUDIT
    # =====================================================

    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records_marked",
        help_text=(
            "User who performed the attendance action."
        ),
    )

    marked_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Date and time when the current attendance "
            "status was recorded."
        ),
    )

    # =====================================================
    # NOTES
    # =====================================================

    notes = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Optional notes about this attendance record."
        ),
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # =====================================================
    # META
    # =====================================================

    class Meta:
        ordering = (
            "user__first_name",
            "user__last_name",
            "user__username",
            "pk",
        )

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "session",
                    "user",
                ],
                name="unique_attendance_session_user",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "session",
                    "status",
                ],
                name="att_rec_sess_stat",
            ),
            models.Index(
                fields=[
                    "user",
                    "status",
                ],
                name="att_rec_user_stat",
            ),
            models.Index(
                fields=[
                    "user",
                    "attendance_time",
                ],
                name="att_rec_user_time",
            ),
            models.Index(
                fields=[
                    "source",
                    "status",
                ],
                name="att_rec_src_stat",
            ),
            models.Index(
                fields=[
                    "-marked_at",
                ],
                name="att_rec_marked",
            ),
        ]

        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"

    # =====================================================
    # STRING REPRESENTATION
    # =====================================================

    def __str__(self):
        user_name = (
            self.user.get_full_name()
            if self.user
            else "Unknown Member"
        )

        session_title = (
            self.session.title
            if self.session
            else "Unknown Session"
        )

        return (
            f"{user_name} - "
            f"{session_title} - "
            f"{self.get_status_display()}"
        )

    # =====================================================
    # VALIDATION
    # =====================================================

    def clean(self):
        """
        Validate attendance record data.

        Business operations such as marking present,
        marking absent and resetting attendance remain
        in attendance.services.
        """

        super().clean()

        if self.notes:
            self.notes = self.notes.strip()

        if not self.user:
            raise ValidationError(
                {
                    "user": (
                        "An attendance record must "
                        "belong to a user."
                    )
                }
            )

        if not self.session:
            raise ValidationError(
                {
                    "session": (
                        "An attendance record must "
                        "belong to an attendance session."
                    )
                }
            )

    # =====================================================
    # STATUS PROPERTIES
    # =====================================================

    @property
    def is_pending(self):
        """Return True when attendance is pending."""

        return (
            self.status
            == self.AttendanceStatus.PENDING
        )

    @property
    def is_present(self):
        """Return True when the member is present."""

        return (
            self.status
            == self.AttendanceStatus.PRESENT
        )

    @property
    def is_absent(self):
        """Return True when the member is absent."""

        return (
            self.status
            == self.AttendanceStatus.ABSENT
        )

    @property
    def is_excused(self):
        """Return True when the member is excused."""

        return (
            self.status
            == self.AttendanceStatus.EXCUSED
        )

    # =====================================================
    # SOURCE PROPERTIES
    # =====================================================

    @property
    def is_self_marked(self):
        """
        Return True when the member marked themselves.
        """

        return (
            self.source
            == self.AttendanceSource.SELF
        )

    @property
    def is_manually_marked(self):
        """
        Return True when management manually marked
        attendance.
        """

        return (
            self.source
            == self.AttendanceSource.MANUAL
        )

    @property
    def is_system_recorded(self):
        """
        Return True when the system created or updated
        the record.
        """

        return (
            self.source
            == self.AttendanceSource.SYSTEM
        )

    # =====================================================
    # USER DISPLAY
    # =====================================================

    @property
    def member_name(self):
        """
        Return a safe display name for the member.
        """

        if not self.user:
            return "Unknown Member"

        return (
            self.user.get_full_name()
            or getattr(
                self.user,
                "username",
                None,
            )
            or "Member"
        )

    # =====================================================
    # STATUS LABEL
    # =====================================================

    @property
    def status_label(self):
        """
        Return the human-readable attendance status.
        """

        return self.get_status_display()

    # =====================================================
    # SOURCE LABEL
    # =====================================================

    @property
    def source_label(self):
        """
        Return the human-readable attendance source.
        """

        return self.get_source_display()