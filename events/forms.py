# events/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Event, EventRegistration


# =========================================================
# EVENT CREATION / UPDATE FORM
# =========================================================


class EventForm(forms.ModelForm):
    """
    Form used by authorized KUCSA executives and
    administrators to create and update events.

    The organizer is intentionally excluded from the form.
    It is assigned by the view.
    """

    class Meta:
        model = Event

        fields = [
            "title",
            "description",
            "event_type",
            "start_datetime",
            "end_datetime",
            "venue",
            "location_details",
            "is_online",
            "online_link",
            "image",
            "capacity",
            "registration_status",
            "registration_deadline",
            "requires_registration",
            "status",
            "requirements",
            "target_audience",
            "certificate_available",
            "is_featured",
        ]

        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter event title",
                    "maxlength": 200,
                    "autocomplete": "off",
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": (
                        "Describe the event, what attendees "
                        "will learn, and what to expect..."
                    ),
                }
            ),

            "event_type": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "start_datetime": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                },
            ),

            "end_datetime": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                },
            ),

            "venue": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "e.g. Kisii University Main Hall"
                    ),
                    "maxlength": 255,
                }
            ),

            "location_details": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "Room, building, hall, or additional "
                        "location details"
                    ),
                    "maxlength": 255,
                }
            ),

            "is_online": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),

            "online_link": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://meet.google.com/...",
                }
            ),

            "image": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/*",
                }
            ),

            "capacity": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "placeholder": (
                        "Leave blank for unlimited capacity"
                    ),
                }
            ),

            "registration_status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "registration_deadline": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                },
            ),

            "requires_registration": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),

            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "requirements": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": (
                        "Requirements, materials, software, "
                        "or preparation attendees need..."
                    ),
                }
            ),

            "target_audience": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "e.g. All KUCSA Members, "
                        "First Year Students, CS Students"
                    ),
                    "maxlength": 255,
                }
            ),

            "certificate_available": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),

            "is_featured": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

        labels = {
            "title": "Event Title",
            "description": "Event Description",
            "event_type": "Event Type",
            "start_datetime": "Start Date & Time",
            "end_datetime": "End Date & Time",
            "venue": "Venue",
            "location_details": "Location Details",
            "is_online": "Online Event",
            "online_link": "Online Meeting Link",
            "image": "Event Image",
            "capacity": "Maximum Capacity",
            "registration_status": "Registration Status",
            "registration_deadline": "Registration Deadline",
            "requires_registration": "Require Registration",
            "status": "Event Status",
            "requirements": "Requirements",
            "target_audience": "Target Audience",
            "certificate_available": "Certificate Available",
            "is_featured": "Featured Event",
        }

        help_texts = {
            "capacity": (
                "Leave blank if the event has unlimited capacity."
            ),
            "registration_deadline": (
                "Must be before the event start time."
            ),
            "online_link": (
                "Required when the event is online."
            ),
            "is_featured": (
                "Featured events receive additional visibility "
                "on the platform."
            ),
        }

    # =====================================================
    # INITIALIZATION
    # =====================================================

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        datetime_fields = (
            "start_datetime",
            "end_datetime",
            "registration_deadline",
        )

        for field_name in datetime_fields:
            field = self.fields.get(field_name)

            if not field:
                continue

            field.input_formats = [
                "%Y-%m-%dT%H:%M",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d %H:%M:%S",
            ]

            # Make sure an existing value is displayed correctly
            # inside a datetime-local input.
            if self.instance and self.instance.pk:
                value = getattr(
                    self.instance,
                    field_name,
                    None,
                )

                if value:
                    field.initial = timezone.localtime(
                        value
                    ).strftime(
                        "%Y-%m-%dT%H:%M"
                    )

    # =====================================================
    # START DATE/TIME
    # =====================================================

    def clean_start_datetime(self):
        """
        Validate the event start time.

        New events must start in the future.

        Existing events:
            - cannot be moved from the future into the past;
            - can retain an already-past start time when editing
              historical records.
        """

        start_datetime = self.cleaned_data.get(
            "start_datetime"
        )

        if not start_datetime:
            return start_datetime

        now = timezone.now()

        # -------------------------------------------------
        # NEW EVENT
        # -------------------------------------------------

        if not self.instance.pk:

            if start_datetime <= now:
                raise ValidationError(
                    "A new event must have a future start "
                    "date and time."
                )

            return start_datetime

        # -------------------------------------------------
        # EXISTING EVENT
        # -------------------------------------------------

        original_start = self.instance.start_datetime

        if (
            original_start
            and original_start > now
            and start_datetime <= now
        ):
            raise ValidationError(
                "The event start time cannot be moved "
                "into the past."
            )

        return start_datetime

    # =====================================================
    # END DATE/TIME
    # =====================================================

    def clean_end_datetime(self):
        """
        Ensure the event ends after it starts.
        """

        end_datetime = self.cleaned_data.get(
            "end_datetime"
        )

        start_datetime = self.cleaned_data.get(
            "start_datetime"
        )

        if not end_datetime:
            return end_datetime

        if (
            start_datetime
            and end_datetime <= start_datetime
        ):
            raise ValidationError(
                "The event end time must be after "
                "the start time."
            )

        return end_datetime

    # =====================================================
    # CAPACITY
    # =====================================================

    def clean_capacity(self):
        """
        Validate event capacity.

        Existing active registrations must always fit
        within the new capacity.
        """

        capacity = self.cleaned_data.get(
            "capacity"
        )

        if capacity is not None and capacity <= 0:
            raise ValidationError(
                "Event capacity must be greater than zero."
            )

        if (
            self.instance.pk
            and capacity is not None
        ):
            active_registrations = (
                self.instance.registration_count
            )

            if capacity < active_registrations:
                raise ValidationError(
                    "Capacity cannot be lower than the "
                    f"current number of active registrations "
                    f"({active_registrations})."
                )

        return capacity

    # =====================================================
    # REGISTRATION DEADLINE
    # =====================================================

    def clean_registration_deadline(self):
        """
        Ensure registration deadline occurs before
        the event starts.
        """

        deadline = self.cleaned_data.get(
            "registration_deadline"
        )

        start_datetime = self.cleaned_data.get(
            "start_datetime"
        )

        if not deadline:
            return deadline

        if (
            start_datetime
            and deadline >= start_datetime
        ):
            raise ValidationError(
                "Registration deadline must be before "
                "the event starts."
            )

        return deadline

    # =====================================================
    # FORM-WIDE VALIDATION
    # =====================================================

    def clean(self):
        cleaned_data = super().clean()

        is_online = cleaned_data.get(
            "is_online"
        )

        online_link = cleaned_data.get(
            "online_link"
        )

        venue = (
            cleaned_data.get("venue")
            or ""
        ).strip()

        location_details = (
            cleaned_data.get("location_details")
            or ""
        ).strip()

        requires_registration = cleaned_data.get(
            "requires_registration"
        )

        registration_status = cleaned_data.get(
            "registration_status"
        )

        registration_deadline = cleaned_data.get(
            "registration_deadline"
        )

        status = cleaned_data.get(
            "status"
        )

        start_datetime = cleaned_data.get(
            "start_datetime"
        )

        end_datetime = cleaned_data.get(
            "end_datetime"
        )

        # =================================================
        # LOCATION VALIDATION
        # =================================================

        if is_online:

            # Online events require a meeting link.
            if not online_link:
                self.add_error(
                    "online_link",
                    (
                        "An online meeting link is required "
                        "for online events."
                    ),
                )

            # Venue is not required for online events.
            cleaned_data["venue"] = venue

        else:

            # Physical events require a venue.
            if not venue:
                self.add_error(
                    "venue",
                    (
                        "A venue is required for "
                        "physical events."
                    ),
                )

            cleaned_data["online_link"] = (
                online_link
            )

        cleaned_data["venue"] = venue
        cleaned_data["location_details"] = (
            location_details
        )

        # =================================================
        # DATE/TIME VALIDATION
        # =================================================

        if (
            start_datetime
            and end_datetime
            and end_datetime <= start_datetime
        ):
            self.add_error(
                "end_datetime",
                (
                    "The event end time must be after "
                    "the start time."
                ),
            )

        # =================================================
        # REGISTRATION SETTINGS
        # =================================================

        if not requires_registration:

            cleaned_data["registration_status"] = (
                Event.RegistrationStatus.CLOSED
            )

            cleaned_data["registration_deadline"] = (
                None
            )

        else:

            if not registration_status:
                cleaned_data["registration_status"] = (
                    Event.RegistrationStatus.CLOSED
                )

            # Registration deadline is only meaningful
            # when registration is enabled.
            if (
                registration_deadline
                and start_datetime
                and registration_deadline >= start_datetime
            ):
                self.add_error(
                    "registration_deadline",
                    (
                        "Registration deadline must be "
                        "before the event starts."
                    ),
                )

        # =================================================
        # CANCELLED EVENTS
        # =================================================

        if status == Event.Status.CANCELLED:

            cleaned_data["registration_status"] = (
                Event.RegistrationStatus.CLOSED
            )

            cleaned_data["registration_deadline"] = (
                None
            )

        # =================================================
        # COMPLETED EVENTS
        # =================================================

        if status == Event.Status.COMPLETED:

            cleaned_data["registration_status"] = (
                Event.RegistrationStatus.CLOSED
            )

        # =================================================
        # PUBLISHED EVENTS
        # =================================================

        if status == Event.Status.PUBLISHED:

            if (
                start_datetime
                and start_datetime <= timezone.now()
            ):
                self.add_error(
                    "start_datetime",
                    (
                        "A published event must have a "
                        "future start date and time."
                    ),
                )

            if requires_registration:

                cleaned_data["registration_status"] = (
                    Event.RegistrationStatus.OPEN
                )

            else:

                cleaned_data["registration_status"] = (
                    Event.RegistrationStatus.CLOSED
                )

        # =================================================
        # ONGOING EVENTS
        # =================================================

        if status == Event.Status.ONGOING:

            if (
                start_datetime
                and end_datetime
                and not (
                    start_datetime
                    <= timezone.now()
                    <= end_datetime
                )
            ):
                self.add_error(
                    "status",
                    (
                        "An event can only be marked as "
                        "ongoing while it is taking place."
                    ),
                )

            cleaned_data["registration_status"] = (
                Event.RegistrationStatus.CLOSED
            )

        return cleaned_data


# =========================================================
# EVENT REGISTRATION FORM
# =========================================================


class EventRegistrationForm(forms.ModelForm):
    """
    Form used by authenticated KUCSA members/students
    to register for an event.

    The event and user are supplied by the view.

    They are intentionally NOT selectable through the form.
    """

    class Meta:
        model = EventRegistration

        fields = [
            "notes",
        ]

        widgets = {
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "maxlength": 5000,
                    "placeholder": (
                        "Optional notes or information "
                        "you would like the organizers "
                        "to know..."
                    ),
                }
            ),
        }

        labels = {
            "notes": "Additional Notes",
        }

    def __init__(
        self,
        *args,
        event=None,
        user=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.event = event
        self.user = user

    # =====================================================
    # VALIDATION
    # =====================================================

    def clean(self):
        cleaned_data = super().clean()

        # =================================================
        # EVENT
        # =================================================

        if not self.event:
            raise ValidationError(
                "An event is required for registration."
            )

        # =================================================
        # USER
        # =================================================

        if (
            not self.user
            or not self.user.is_authenticated
        ):
            raise ValidationError(
                "You must be logged in to register "
                "for an event."
            )

        # =================================================
        # MEMBERSHIP
        # =================================================

        member = getattr(
            self.user,
            "member_profile",
            None,
        )

        if not member:
            raise ValidationError(
                "You must have a KUCSA membership profile "
                "before registering for an event."
            )

        if not getattr(
            member,
            "can_access_platform",
            False,
        ):
            raise ValidationError(
                "Only active KUCSA members can register "
                "for events."
            )

        # =================================================
        # EVENT VISIBILITY
        # =================================================

        if self.event.status != Event.Status.PUBLISHED:
            raise ValidationError(
                "Registration is only available for "
                "published events."
            )

        # =================================================
        # REGISTRATION AVAILABILITY
        # =================================================

        if not self.event.registration_is_open:
            raise ValidationError(
                "Registration for this event is "
                "currently closed."
            )

        # =================================================
        # DUPLICATE REGISTRATION
        # =================================================

        existing_registration = (
            EventRegistration.objects
            .filter(
                event=self.event,
                user=self.user,
            )
            .first()
        )

        if existing_registration:

            status = existing_registration.status

            if (
                status
                == EventRegistration
                .RegistrationStatus
                .CANCELLED
            ):
                # The view handles re-registration.
                return cleaned_data

            if (
                status
                == EventRegistration
                .RegistrationStatus
                .ATTENDED
            ):
                raise ValidationError(
                    "You have already attended this event."
                )

            if (
                status
                == EventRegistration
                .RegistrationStatus
                .ABSENT
            ):
                raise ValidationError(
                    "You already have an attendance record "
                    "for this event."
                )

            raise ValidationError(
                "You are already registered for this event."
            )

        return cleaned_data


# =========================================================
# EVENT REGISTRATION MANAGEMENT FORM
# =========================================================


class EventRegistrationAdminForm(forms.ModelForm):
    """
    Form used by authorized executives and administrators
    to manage event registrations.

    This is intended for management interfaces, not the
    normal student registration flow.
    """

    class Meta:
        model = EventRegistration

        fields = [
            "event",
            "user",
            "status",
            "notes",
        ]

        widgets = {
            "event": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "user": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "maxlength": 5000,
                    "placeholder": (
                        "Optional administrative notes..."
                    ),
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        event = cleaned_data.get("event")
        user = cleaned_data.get("user")
        status = cleaned_data.get("status")

        if not event or not user:
            return cleaned_data

        # -------------------------------------------------
        # CANCELLED EVENT
        # -------------------------------------------------

        if (
            event.status
            == Event.Status.CANCELLED
            and status
            in (
                EventRegistration
                .RegistrationStatus
                .REGISTERED,
                EventRegistration
                .RegistrationStatus
                .ATTENDED,
            )
        ):
            raise ValidationError(
                "A registration cannot be active for "
                "a cancelled event."
            )

        # -------------------------------------------------
        # CAPACITY
        # -------------------------------------------------

        if (
            status
            in (
                EventRegistration
                .RegistrationStatus
                .REGISTERED,
                EventRegistration
                .RegistrationStatus
                .ATTENDED,
            )
        ):

            existing_active = (
                EventRegistration.objects
                .filter(
                    event=event,
                    status__in=[
                        EventRegistration
                        .RegistrationStatus
                        .REGISTERED,
                        EventRegistration
                        .RegistrationStatus
                        .ATTENDED,
                    ],
                )
                .exclude(
                    pk=self.instance.pk
                )
                .count()
            )

            if (
                event.capacity is not None
                and existing_active >= event.capacity
            ):
                raise ValidationError(
                    "This event has reached its "
                    "registration capacity."
                )

        return cleaned_data


# =========================================================
# EVENT STATUS FORM
# =========================================================


class EventStatusForm(forms.ModelForm):
    """
    Form used by authorized executives and administrators
    to change an event status.
    """

    class Meta:
        model = Event

        fields = [
            "status",
        ]

        widgets = {
            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
        }

        labels = {
            "status": "Event Status",
        }


# =========================================================
# REGISTRATION STATUS FORM
# =========================================================


class RegistrationStatusForm(forms.ModelForm):
    """
    Form used by authorized executives and administrators
    to update an event registration status.
    """

    class Meta:
        model = EventRegistration

        fields = [
            "status",
        ]

        widgets = {
            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
        }

        labels = {
            "status": "Registration Status",
        }


# =========================================================
# EVENT FILTER FORM
# =========================================================


class EventFilterForm(forms.Form):
    """
    Search and filtering form for the KUCSA event list.

    GET parameter names intentionally match those consumed
    by events.views.event_list.
    """

    q = forms.CharField(
        required=False,
        label="Search Events",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Search by title, description, "
                    "venue..."
                ),
                "autocomplete": "off",
            }
        ),
    )

    event_type = forms.ChoiceField(
        required=False,
        label="Event Type",
        choices=[
            ("", "All Event Types"),
            *Event.EventType.choices,
        ],
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    status = forms.ChoiceField(
        required=False,
        label="Status",
        choices=[
            ("", "All Statuses"),
            *Event.Status.choices,
        ],
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    featured = forms.BooleanField(
        required=False,
        label="Featured Events Only",
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
    )

    upcoming = forms.BooleanField(
        required=False,
        label="Upcoming Events Only",
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
    )

    def clean_q(self):
        """
        Normalize the search query.
        """

        return (
            self.cleaned_data
            .get("q", "")
            .strip()
        )