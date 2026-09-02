"""
KUCSA Attendance Forms
======================

Forms for the KUCSA general attendance management system.

Architecture
------------

AttendanceSession
        |
        └── AttendanceRecord
                |
                └── User

The attendance system is intentionally independent of
events and event registrations.

An attendance session represents a general KUCSA
attendance exercise, for example:

    - General meeting
    - Weekly meeting
    - Training session
    - Workshop
    - Club activity
    - Executive meeting
    - Special gathering
    - Any other KUCSA activity

Members/students can mark themselves present when a
session is active.

Management users can manage attendance records after
the session has been opened or closed.

Forms are responsible for:

    - collecting input
    - validating input
    - cleaning text
    - validating dates and times
    - validating attendance status
    - validating report/filter parameters
    - validating selected attendance IDs

Forms are NOT responsible for:

    - authentication
    - authorization
    - determining whether a user is a KUCSA member
    - opening sessions
    - closing sessions
    - expiring sessions
    - marking attendance
    - creating attendance records
    - database transactions
    - business rules

Those responsibilities belong to:

    attendance.models
    attendance.services
    attendance.views
"""


from django import forms

from .models import (
    AttendanceRecord,
    AttendanceSession,
)


# =========================================================
# CONSTANTS
# =========================================================

MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_NOTES_LENGTH = 1000
MAX_SEARCH_LENGTH = 200

DEFAULT_TEXTAREA_ROWS = 4


# =========================================================
# COMMON HELPERS
# =========================================================


def _clean_text(value, default=""):
    """
    Safely normalize text.

    Converts None to the supplied default and removes
    unnecessary leading/trailing whitespace.
    """

    if value is None:
        return default

    return str(value).strip()


def _validate_date_range(
    cleaned_data,
    start_field="start_date",
    end_field="end_date",
    message="End date cannot be earlier than start date.",
):
    """
    Validate a date range.
    """

    start_date = cleaned_data.get(start_field)
    end_date = cleaned_data.get(end_field)

    if (
        start_date
        and end_date
        and end_date < start_date
    ):
        raise forms.ValidationError(message)

    return cleaned_data


def _validate_datetime_range(
    cleaned_data,
    start_field="opens_at",
    end_field="closes_at",
    message="Closing time must be after opening time.",
):
    """
    Validate an attendance session datetime range.
    """

    opens_at = cleaned_data.get(start_field)
    closes_at = cleaned_data.get(end_field)

    if (
        opens_at
        and closes_at
        and closes_at <= opens_at
    ):
        raise forms.ValidationError(message)

    return cleaned_data


def _attendance_status_choices(include_all=False):
    """
    Return attendance status choices directly from the
    AttendanceRecord model.

    This prevents status values from being duplicated
    inside the forms module.
    """

    choices = list(
        AttendanceRecord.AttendanceStatus.choices
    )

    if include_all:
        return [
            ("", "All Statuses"),
            *choices,
        ]

    return choices


def _session_status_choices(include_all=False):
    """
    Return attendance session status choices directly
    from AttendanceSession.
    """

    choices = list(
        AttendanceSession.SessionStatus.choices
    )

    if include_all:
        return [
            ("", "All Session Statuses"),
            *choices,
        ]

    return choices


# =========================================================
# STATUS MIXINS
# =========================================================


class AttendanceStatusMixin:
    """
    Shared validation for attendance record statuses.
    """

    VALID_STATUSES = frozenset(
        value
        for value, _label
        in AttendanceRecord.AttendanceStatus.choices
    )

    def validate_attendance_status(
        self,
        status,
        allow_empty=False,
    ):
        """
        Validate an attendance status.
        """

        status = _clean_text(status)

        if allow_empty and not status:
            return ""

        if status not in self.VALID_STATUSES:
            raise forms.ValidationError(
                "Invalid attendance status."
            )

        return status


class AttendanceSessionStatusMixin:
    """
    Shared validation for attendance session statuses.
    """

    VALID_SESSION_STATUSES = frozenset(
        value
        for value, _label
        in AttendanceSession.SessionStatus.choices
    )

    def validate_session_status(
        self,
        status,
        allow_empty=False,
    ):
        """
        Validate an attendance session status.
        """

        status = _clean_text(status)

        if allow_empty and not status:
            return ""

        if status not in self.VALID_SESSION_STATUSES:
            raise forms.ValidationError(
                "Invalid attendance session status."
            )

        return status


# =========================================================
# ATTENDANCE SESSION CREATE / EDIT FORM
# =========================================================


class AttendanceSessionForm(forms.ModelForm):
    """
    Main form for creating and editing an attendance session.

    An attendance session is completely independent of
    events and event registrations.

    Example sessions:

        KUCSA Weekly Meeting
        First Semester General Meeting
        Python Training Attendance
        Computing Students Workshop

    The service layer determines the initial status and
    controls whether the session can actually be opened.
    """

    class Meta:
        model = AttendanceSession

        fields = (
            "title",
            "description",
            "opens_at",
            "closes_at",
        )

        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "Example: KUCSA General Meeting"
                    ),
                    "autocomplete": "off",
                    "maxlength": MAX_TITLE_LENGTH,
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": DEFAULT_TEXTAREA_ROWS,
                    "maxlength": MAX_DESCRIPTION_LENGTH,
                    "placeholder": (
                        "Enter optional information "
                        "about this attendance session..."
                    ),
                }
            ),
            "opens_at": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                }
            ),
            "closes_at": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                }
            ),
        }

        labels = {
            "title": "Attendance Session Title",
            "description": "Description",
            "opens_at": "Opening Time",
            "closes_at": "Closing Time",
        }

        help_texts = {
            "title": (
                "Enter a clear name for this attendance session."
            ),
            "description": (
                "Optional information or instructions "
                "for members."
            ),
            "opens_at": (
                "When members should be allowed to "
                "mark attendance."
            ),
            "closes_at": (
                "When members should no longer be "
                "allowed to mark attendance."
            ),
        }

    def clean_title(self):
        title = _clean_text(
            self.cleaned_data.get("title")
        )

        if not title:
            raise forms.ValidationError(
                "Attendance session title cannot be empty."
            )

        if len(title) > MAX_TITLE_LENGTH:
            raise forms.ValidationError(
                (
                    "Attendance session title cannot exceed "
                    f"{MAX_TITLE_LENGTH} characters."
                )
            )

        return title

    def clean_description(self):
        description = _clean_text(
            self.cleaned_data.get("description")
        )

        if len(description) > MAX_DESCRIPTION_LENGTH:
            raise forms.ValidationError(
                (
                    "Description cannot exceed "
                    f"{MAX_DESCRIPTION_LENGTH} characters."
                )
            )

        return description

    def clean(self):
        cleaned_data = super().clean()

        _validate_datetime_range(
            cleaned_data,
            message=(
                "Closing time must be after opening time."
            ),
        )

        return cleaned_data


# =========================================================
# CREATE SESSION FORM ALIAS
# =========================================================


class AttendanceSessionCreateForm(
    AttendanceSessionForm
):
    """
    Explicit create-session form.

    Kept separate so views can clearly communicate whether
    a form is being used for creation or general editing.
    """

    pass


# =========================================================
# SESSION TITLE FORM
# =========================================================


class AttendanceSessionTitleForm(forms.Form):
    """
    Form for changing only an attendance session title.
    """

    title = forms.CharField(
        required=True,
        max_length=MAX_TITLE_LENGTH,
        strip=True,
        label="Attendance Session Title",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Enter attendance session title..."
                ),
                "autocomplete": "off",
                "maxlength": MAX_TITLE_LENGTH,
            }
        ),
    )

    def clean_title(self):
        title = _clean_text(
            self.cleaned_data.get("title")
        )

        if not title:
            raise forms.ValidationError(
                "Attendance session title cannot be empty."
            )

        return title


# =========================================================
# SESSION DESCRIPTION FORM
# =========================================================


class AttendanceSessionDescriptionForm(
    forms.Form
):
    """
    Form for changing only the attendance session
    description.
    """

    description = forms.CharField(
        required=False,
        max_length=MAX_DESCRIPTION_LENGTH,
        label="Attendance Description",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": DEFAULT_TEXTAREA_ROWS,
                "maxlength": MAX_DESCRIPTION_LENGTH,
                "placeholder": (
                    "Optional information or instructions "
                    "for members..."
                ),
            }
        ),
    )

    def clean_description(self):
        return _clean_text(
            self.cleaned_data.get("description")
        )


# =========================================================
# SESSION TIMING FORM
# =========================================================


class AttendanceSessionTimingForm(forms.ModelForm):
    """
    Form for setting or editing attendance session timing.

    This form validates only the supplied dates/times.

    It does not determine whether the current user is
    allowed to modify the session.

    Authorization and session-state rules belong to
    attendance.services.
    """

    class Meta:
        model = AttendanceSession

        fields = (
            "opens_at",
            "closes_at",
        )

        widgets = {
            "opens_at": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                }
            ),
            "closes_at": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                }
            ),
        }

        labels = {
            "opens_at": "Opening Time",
            "closes_at": "Closing Time",
        }

        help_texts = {
            "opens_at": (
                "When members should be allowed to "
                "mark attendance."
            ),
            "closes_at": (
                "When attendance should stop accepting "
                "member submissions."
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        _validate_datetime_range(
            cleaned_data,
            message=(
                "Closing time must be after opening time."
            ),
        )

        return cleaned_data


# =========================================================
# SELF ATTENDANCE FORM
# =========================================================


class SelfAttendanceForm(forms.Form):
    """
    Member self-attendance confirmation form.

    A successful submission tells the service layer:

        The authenticated member confirms that they
        are present.

    The service layer is responsible for:

        - checking authentication
        - checking membership eligibility
        - checking session status
        - checking attendance window
        - preventing duplicate attendance
        - creating/updating the attendance record
    """

    confirmation = forms.BooleanField(
        required=True,
        label=(
            "I confirm that I am present and want to "
            "mark my attendance."
        ),
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
        error_messages={
            "required": (
                "You must confirm your attendance "
                "before submitting."
            ),
        },
    )


# =========================================================
# ACTIVE ATTENDANCE FORM
# =========================================================


class ActiveAttendanceForm(
    SelfAttendanceForm
):
    """
    Form used by the active attendance page.

    It intentionally contains only confirmation.
    """

    pass


# =========================================================
# MANAGEMENT ATTENDANCE FORM
# =========================================================


class AttendanceForm(
    AttendanceStatusMixin,
    forms.ModelForm,
):
    """
    Management form for updating one attendance record.

    The form deliberately does NOT expose:

        user
        session
        marked_by
        source
        attendance_time
        marked_at

    Those values are controlled by the service layer.

    This prevents a management form from accidentally
    becoming responsible for attendance business logic.
    """

    class Meta:
        model = AttendanceRecord

        fields = (
            "status",
            "notes",
        )

        widgets = {
            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "maxlength": MAX_NOTES_LENGTH,
                    "placeholder": (
                        "Optional attendance notes..."
                    ),
                }
            ),
        }

        labels = {
            "status": "Attendance Status",
            "notes": "Attendance Notes",
        }

        help_texts = {
            "status": (
                "Select the appropriate attendance "
                "status for this member."
            ),
            "notes": (
                "Optional notes explaining the "
                "attendance status."
            ),
        }

    def clean_status(self):
        return self.validate_attendance_status(
            self.cleaned_data.get("status")
        )

    def clean_notes(self):
        notes = _clean_text(
            self.cleaned_data.get("notes")
        )

        if len(notes) > MAX_NOTES_LENGTH:
            raise forms.ValidationError(
                (
                    "Notes cannot exceed "
                    f"{MAX_NOTES_LENGTH} characters."
                )
            )

        return notes


# =========================================================
# SINGLE ATTENDANCE ACTION FORM
# =========================================================


class AttendanceRecordActionForm(
    AttendanceStatusMixin,
    forms.Form,
):
    """
    Form for changing one attendance record.

    The service layer determines whether the requested
    operation is permitted.
    """

    status = forms.ChoiceField(
        required=True,
        choices=_attendance_status_choices(),
        label="Attendance Status",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    notes = forms.CharField(
        required=False,
        max_length=MAX_NOTES_LENGTH,
        label="Notes",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 2,
                "maxlength": MAX_NOTES_LENGTH,
                "placeholder": (
                    "Optional attendance notes..."
                ),
            }
        ),
    )

    def clean_status(self):
        return self.validate_attendance_status(
            self.cleaned_data.get("status")
        )

    def clean_notes(self):
        return _clean_text(
            self.cleaned_data.get("notes")
        )


# =========================================================
# BULK ATTENDANCE FORM
# =========================================================


class BulkAttendanceForm(
    AttendanceStatusMixin,
    forms.Form,
):
    """
    Form for bulk attendance management.

    Example submitted value:

        selected_attendance = "12,15,18,20"

    Cleaned result:

        [12, 15, 18, 20]

    The form validates the submitted IDs only.

    The service layer remains responsible for:

        - authorization
        - verifying record ownership
        - verifying record existence
        - validating session state
        - performing updates
        - transactions
    """

    attendance_status = forms.ChoiceField(
        required=True,
        choices=_attendance_status_choices(),
        label="Attendance Status",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
        help_text=(
            "Apply this status to all selected "
            "attendance records."
        ),
    )

    notes = forms.CharField(
        required=False,
        max_length=MAX_NOTES_LENGTH,
        label="Attendance Notes",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "maxlength": MAX_NOTES_LENGTH,
                "placeholder": (
                    "Optional note to apply to "
                    "selected records..."
                ),
            }
        ),
    )

    selected_attendance = forms.CharField(
        required=True,
        label="Selected Attendance",
        widget=forms.HiddenInput(),
    )

    def clean_attendance_status(self):
        return self.validate_attendance_status(
            self.cleaned_data.get(
                "attendance_status"
            )
        )

    def clean_notes(self):
        return _clean_text(
            self.cleaned_data.get("notes")
        )

    def clean_selected_attendance(self):
        value = _clean_text(
            self.cleaned_data.get(
                "selected_attendance"
            )
        )

        if not value:
            raise forms.ValidationError(
                (
                    "Please select at least one "
                    "attendance record."
                )
            )

        raw_ids = value.split(",")

        attendance_ids = []

        for item in raw_ids:

            item = item.strip()

            if not item:
                continue

            try:
                attendance_id = int(item)

            except (TypeError, ValueError):
                raise forms.ValidationError(
                    "Invalid attendance record selection."
                )

            if attendance_id <= 0:
                raise forms.ValidationError(
                    (
                        "Attendance record IDs must be "
                        "positive integers."
                    )
                )

            attendance_ids.append(
                attendance_id
            )

        if not attendance_ids:
            raise forms.ValidationError(
                (
                    "Please select at least one "
                    "attendance record."
                )
            )

        # Remove duplicate IDs while preserving
        # the original selection order.
        return list(
            dict.fromkeys(attendance_ids)
        )


# =========================================================
# OPEN / PUBLISH SESSION FORM
# =========================================================


class AttendanceSessionControlForm(forms.Form):
    """
    Confirmation form for opening an attendance session.

    The form only captures the administrator's confirmation.

    The service layer determines:

        - whether the user has permission
        - whether the session can be opened
        - opening time
        - closing time
        - session status
        - attendance record preparation
    """

    confirmation = forms.BooleanField(
        required=True,
        label=(
            "I confirm that I want to open attendance "
            "for members."
        ),
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
        error_messages={
            "required": (
                "Please confirm before opening "
                "attendance."
            ),
        },
    )


class PublishAttendanceForm(
    AttendanceSessionControlForm
):
    """
    Explicit alias for publishing/opening attendance.
    """

    pass


# =========================================================
# CLOSE SESSION FORM
# =========================================================


class CloseAttendanceSessionForm(forms.Form):
    """
    Confirmation form for manually closing an
    attendance session.
    """

    confirmation = forms.BooleanField(
        required=True,
        label=(
            "I confirm that I want to close "
            "this attendance session."
        ),
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
        error_messages={
            "required": (
                "Please confirm before closing "
                "attendance."
            ),
        },
    )


# =========================================================
# ATTENDANCE FILTER FORM
# =========================================================


class AttendanceFilterForm(
    AttendanceStatusMixin,
    forms.Form,
):
    """
    Management filter for attendance records.

    Supports:

        - attendance status
        - member search
        - start date
        - end date

    No event or event-registration filtering exists because
    the new attendance system is completely independent
    of the events application.
    """

    status = forms.ChoiceField(
        required=False,
        choices=_attendance_status_choices(
            include_all=True
        ),
        label="Status",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    search = forms.CharField(
        required=False,
        max_length=MAX_SEARCH_LENGTH,
        strip=True,
        label="Search Member",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Search member, username, "
                    "email or registration number..."
                ),
                "autocomplete": "off",
            }
        ),
    )

    start_date = forms.DateField(
        required=False,
        label="Start Date",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    end_date = forms.DateField(
        required=False,
        label="End Date",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    def clean_status(self):
        return self.validate_attendance_status(
            self.cleaned_data.get("status"),
            allow_empty=True,
        )

    def clean_search(self):
        return _clean_text(
            self.cleaned_data.get("search")
        )

    def clean(self):
        cleaned_data = super().clean()

        return _validate_date_range(
            cleaned_data,
            message=(
                "End date cannot be earlier than "
                "start date."
            ),
        )


# =========================================================
# ATTENDANCE SESSION FILTER FORM
# =========================================================


class AttendanceSessionFilterForm(
    AttendanceSessionStatusMixin,
    forms.Form,
):
    """
    Filter form for attendance sessions.

    Supports:

        - session status
        - session title search
        - date range
    """

    status = forms.ChoiceField(
        required=False,
        choices=_session_status_choices(
            include_all=True
        ),
        label="Session Status",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    search = forms.CharField(
        required=False,
        max_length=MAX_SEARCH_LENGTH,
        strip=True,
        label="Search",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Search attendance sessions..."
                ),
                "autocomplete": "off",
            }
        ),
    )

    start_date = forms.DateField(
        required=False,
        label="Start Date",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    end_date = forms.DateField(
        required=False,
        label="End Date",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    def clean_status(self):
        return self.validate_session_status(
            self.cleaned_data.get("status"),
            allow_empty=True,
        )

    def clean_search(self):
        return _clean_text(
            self.cleaned_data.get("search")
        )

    def clean(self):
        cleaned_data = super().clean()

        return _validate_date_range(
            cleaned_data,
            message=(
                "End date cannot be earlier than "
                "start date."
            ),
        )


# =========================================================
# MY ATTENDANCE FILTER FORM
# =========================================================


class MyAttendanceFilterForm(
    AttendanceStatusMixin,
    forms.Form,
):
    """
    Member-facing attendance filter.

    The form NEVER accepts a user/member ID.

    The view always uses:

        request.user

    This prevents members from attempting to request
    another member's attendance history through the form.
    """

    status = forms.ChoiceField(
        required=False,
        choices=_attendance_status_choices(
            include_all=True
        ),
        label="Status",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    start_date = forms.DateField(
        required=False,
        label="From",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    end_date = forms.DateField(
        required=False,
        label="To",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    def clean_status(self):
        return self.validate_attendance_status(
            self.cleaned_data.get("status"),
            allow_empty=True,
        )

    def clean(self):
        cleaned_data = super().clean()

        return _validate_date_range(
            cleaned_data,
            message=(
                "The ending date cannot be earlier "
                "than the starting date."
            ),
        )


# =========================================================
# ATTENDANCE REPORT FORM
# =========================================================


class AttendanceReportForm(
    AttendanceStatusMixin,
    forms.Form,
):
    """
    Management attendance report form.

    Supports:

        - date range
        - attendance status
        - report format
    """

    REPORT_FORMATS = (
        ("html", "Web Report"),
        ("csv", "CSV"),
    )

    start_date = forms.DateField(
        required=False,
        label="Start Date",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    end_date = forms.DateField(
        required=False,
        label="End Date",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    status = forms.ChoiceField(
        required=False,
        choices=_attendance_status_choices(
            include_all=True
        ),
        label="Attendance Status",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    report_format = forms.ChoiceField(
        required=True,
        choices=REPORT_FORMATS,
        initial="html",
        label="Report Format",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    def clean_status(self):
        return self.validate_attendance_status(
            self.cleaned_data.get("status"),
            allow_empty=True,
        )

    def clean(self):
        cleaned_data = super().clean()

        return _validate_date_range(
            cleaned_data,
            message=(
                "End date cannot be earlier than "
                "start date."
            ),
        )


# =========================================================
# ATTENDANCE SESSION REPORT FORM
# =========================================================


class AttendanceSessionReportForm(
    AttendanceSessionStatusMixin,
    forms.Form,
):
    """
    Session-oriented attendance report form.

    Supports:

        - session status
        - start date
        - end date
    """

    status = forms.ChoiceField(
        required=False,
        choices=_session_status_choices(
            include_all=True
        ),
        label="Session Status",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    start_date = forms.DateField(
        required=False,
        label="From",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    end_date = forms.DateField(
        required=False,
        label="To",
        widget=forms.DateInput(
            attrs={
                "class": "form-control",
                "type": "date",
            }
        ),
    )

    def clean_status(self):
        return self.validate_session_status(
            self.cleaned_data.get("status"),
            allow_empty=True,
        )

    def clean(self):
        cleaned_data = super().clean()

        return _validate_date_range(
            cleaned_data,
            message=(
                "The ending date cannot be earlier "
                "than the starting date."
            ),
        )