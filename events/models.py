# events/models.py

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


# =========================================================
# EVENT
# =========================================================


class Event(models.Model):
    """
    KUCSA Event.

    Represents an official KUCSA event such as:

        - Career talks
        - Hackathons
        - Bootcamps
        - Workshops
        - Networking sessions
        - Competitions
        - Project showcases
        - General meetings
        - Seminars
        - Trainings
        - Other KUCSA activities

    Visibility
    ----------
    Students/members can see:
        - Published events
        - Ongoing events

    Executives/administrators can see:
        - Draft events
        - Published events
        - Ongoing events
        - Completed events
        - Cancelled events
    """

    # =========================================================
    # CHOICES
    # =========================================================

    class EventType(models.TextChoices):
        WORKSHOP = "WORKSHOP", "Workshop"
        BOOTCAMP = "BOOTCAMP", "Bootcamp"
        CAREER_TALK = "CAREER_TALK", "Career Talk"
        HACKATHON = "HACKATHON", "Hackathon"
        COMPETITION = "COMPETITION", "Competition"
        NETWORKING = "NETWORKING", "Networking"
        PROJECT_SHOWCASE = (
            "PROJECT_SHOWCASE",
            "Project Showcase",
        )
        GENERAL_MEETING = (
            "GENERAL_MEETING",
            "General Meeting",
        )
        SEMINAR = "SEMINAR", "Seminar"
        TRAINING = "TRAINING", "Training"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        ONGOING = "ONGOING", "Ongoing"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class RegistrationStatus(models.TextChoices):
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"

    # =========================================================
    # BASIC EVENT INFORMATION
    # =========================================================

    title = models.CharField(
        max_length=200,
        verbose_name="Event Title",
    )

    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
    )

    description = models.TextField(
        verbose_name="Event Description",
    )

    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
        default=EventType.OTHER,
    )

    # =========================================================
    # EVENT DATE & TIME
    # =========================================================

    start_datetime = models.DateTimeField(
        verbose_name="Start Date & Time",
    )

    end_datetime = models.DateTimeField(
        verbose_name="End Date & Time",
    )

    # =========================================================
    # LOCATION
    # =========================================================

    venue = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Venue",
    )

    location_details = models.CharField(
        max_length=255,
        blank=True,
        help_text=(
            "Room, building, hall, or additional "
            "location details."
        ),
    )

    is_online = models.BooleanField(
        default=False,
    )

    online_link = models.URLField(
        blank=True,
        help_text=(
            "Meeting link for online events."
        ),
    )

    # =========================================================
    # EVENT IMAGE
    # =========================================================

    image = models.ImageField(
        upload_to="events/",
        blank=True,
        null=True,
    )

    # =========================================================
    # ORGANIZATION
    # =========================================================

    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organized_events",
    )

    # =========================================================
    # CAPACITY & REGISTRATION
    # =========================================================

    capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Maximum number of attendees. "
            "Leave blank for unlimited capacity."
        ),
    )

    registration_status = models.CharField(
        max_length=20,
        choices=RegistrationStatus.choices,
        default=RegistrationStatus.CLOSED,
    )

    registration_deadline = models.DateTimeField(
        null=True,
        blank=True,
    )

    requires_registration = models.BooleanField(
        default=True,
    )

    # =========================================================
    # EVENT STATUS
    # =========================================================

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    # =========================================================
    # ADDITIONAL INFORMATION
    # =========================================================

    requirements = models.TextField(
        blank=True,
        help_text=(
            "Requirements, materials, or things "
            "attendees should bring."
        ),
    )

    target_audience = models.CharField(
        max_length=255,
        blank=True,
        help_text=(
            "Example: All KUCSA members, "
            "First Years, CS students."
        ),
    )

    certificate_available = models.BooleanField(
        default=False,
    )

    is_featured = models.BooleanField(
        default=False,
    )

    # =========================================================
    # TIMESTAMPS
    # =========================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # =========================================================
    # META
    # =========================================================

    class Meta:
        ordering = [
            "start_datetime",
        ]

        verbose_name = "Event"
        verbose_name_plural = "Events"

        indexes = [
            models.Index(
                fields=[
                    "status",
                    "start_datetime",
                ],
            ),
            models.Index(
                fields=[
                    "event_type",
                    "status",
                ],
            ),
            models.Index(
                fields=[
                    "registration_status",
                    "start_datetime",
                ],
            ),
            models.Index(
                fields=[
                    "is_featured",
                    "start_datetime",
                ],
            ),
            models.Index(
                fields=[
                    "organizer",
                    "start_datetime",
                ],
            ),
        ]

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        return self.title

    # =========================================================
    # SAVE
    # =========================================================

    def save(self, *args, **kwargs):
        """
        Generate a unique slug when one does not already exist.

        Existing slugs are preserved when an event is edited.
        """

        if not self.slug:
            base_slug = slugify(self.title)

            if not base_slug:
                base_slug = "event"

            slug = base_slug
            counter = 2

            while (
                Event.objects
                .filter(slug=slug)
                .exclude(pk=self.pk)
                .exists()
            ):
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        # -----------------------------------------------------
        # REGISTRATION CONSISTENCY
        # -----------------------------------------------------

        if not self.requires_registration:
            self.registration_status = (
                self.RegistrationStatus.CLOSED
            )

        # Registration cannot remain open for states where
        # registration no longer makes sense.
        if self.status in (
            self.Status.DRAFT,
            self.Status.ONGOING,
            self.Status.COMPLETED,
            self.Status.CANCELLED,
        ):
            self.registration_status = (
                self.RegistrationStatus.CLOSED
            )

        super().save(*args, **kwargs)

    # =========================================================
    # VALIDATION
    # =========================================================

    def clean(self):
        """
        Validate event information before saving.
        """

        errors = {}

        # =====================================================
        # REQUIRED DATE/TIME
        # =====================================================

        if not self.start_datetime:
            errors["start_datetime"] = (
                "Event start date and time are required."
            )

        if not self.end_datetime:
            errors["end_datetime"] = (
                "Event end date and time are required."
            )

        # =====================================================
        # DATE VALIDATION
        # =====================================================

        if (
            self.start_datetime
            and self.end_datetime
            and self.end_datetime <= self.start_datetime
        ):
            errors["end_datetime"] = (
                "The event end time must be after "
                "the start time."
            )

        # =====================================================
        # REGISTRATION DEADLINE
        # =====================================================

        if (
            self.registration_deadline
            and self.start_datetime
            and self.registration_deadline >= self.start_datetime
        ):
            errors["registration_deadline"] = (
                "Registration deadline must be before "
                "the event starts."
            )

        # =====================================================
        # CAPACITY
        # =====================================================

        if (
            self.capacity is not None
            and self.capacity <= 0
        ):
            errors["capacity"] = (
                "Event capacity must be greater than zero."
            )

        # =====================================================
        # ONLINE EVENT
        # =====================================================

        if self.is_online:

            if not self.online_link:
                errors["online_link"] = (
                    "An online meeting link is required "
                    "for online events."
                )

        # =====================================================
        # PHYSICAL EVENT
        # =====================================================

        else:

            if not self.venue:
                errors["venue"] = (
                    "A venue is required for physical events."
                )

        # =====================================================
        # REGISTRATION SETTINGS
        # =====================================================

        if not self.requires_registration:

            if (
                self.registration_status
                == self.RegistrationStatus.OPEN
            ):
                errors["registration_status"] = (
                    "Registration cannot be open when "
                    "registration is disabled."
                )

            if self.registration_deadline:
                errors["registration_deadline"] = (
                    "A registration deadline is not required "
                    "when registration is disabled."
                )

        # =====================================================
        # REGISTRATION DEADLINE MUST NOT BE IN THE PAST
        # FOR A NEW/ACTIVE EVENT
        # =====================================================

        if (
            self.registration_deadline
            and self.status
            in (
                self.Status.PUBLISHED,
                self.Status.ONGOING,
            )
            and self.registration_deadline < timezone.now()
        ):
            # This is intentionally not treated as a hard
            # validation failure for ongoing events because
            # historical data may legitimately contain a
            # deadline that has already passed.
            pass

        # =====================================================
        # PUBLISHED EVENT VALIDATION
        # =====================================================

        if (
            self.status == self.Status.PUBLISHED
            and self.start_datetime
            and self.start_datetime <= timezone.now()
        ):
            errors["status"] = (
                "An event that has already started cannot "
                "remain in Published status. Mark it as "
                "Ongoing or Completed instead."
            )

        # =====================================================
        # ONGOING EVENT VALIDATION
        # =====================================================

        if (
            self.status == self.Status.ONGOING
            and self.start_datetime
            and self.end_datetime
        ):

            now = timezone.now()

            if now < self.start_datetime:
                errors["status"] = (
                    "An event cannot be marked as ongoing "
                    "before its start time."
                )

            if now >= self.end_datetime:
                errors["status"] = (
                    "An event whose end time has passed "
                    "cannot be marked as ongoing."
                )

        # =====================================================
        # COMPLETED EVENT VALIDATION
        # =====================================================

        if (
            self.status == self.Status.COMPLETED
            and self.end_datetime
            and self.end_datetime > timezone.now()
        ):
            errors["status"] = (
                "An event cannot be marked as completed "
                "before its end time."
            )

        if errors:
            raise ValidationError(errors)

    # =========================================================
    # DISPLAY HELPERS
    # =========================================================

    @property
    def event_type_display(self):
        return self.get_event_type_display()

    @property
    def status_display(self):
        return self.get_status_display()

    @property
    def registration_status_display(self):
        return self.get_registration_status_display()

    # =========================================================
    # STATUS HELPERS
    # =========================================================

    @property
    def is_upcoming(self):
        """
        True when the event is scheduled for the future.
        """

        now = timezone.now()

        return (
            self.start_datetime > now
            and self.status
            not in (
                self.Status.CANCELLED,
                self.Status.COMPLETED,
            )
        )

    @property
    def is_ongoing(self):
        """
        True when the event is currently taking place.
        """

        now = timezone.now()

        return (
            self.start_datetime <= now <= self.end_datetime
            and self.status != self.Status.CANCELLED
            and self.status != self.Status.COMPLETED
        )

    @property
    def is_completed(self):
        """
        True when the event has explicitly been completed
        or its end time has passed.
        """

        now = timezone.now()

        return (
            self.status == self.Status.COMPLETED
            or (
                self.end_datetime
                and self.end_datetime <= now
            )
        )

    @property
    def is_cancelled(self):
        """
        True when the event has been cancelled.
        """

        return self.status == self.Status.CANCELLED

    @property
    def is_published(self):
        """
        True when the event is in Published status.
        """

        return self.status == self.Status.PUBLISHED

    @property
    def is_public(self):
        """
        True when students/members are allowed to see
        this event.

        Draft, completed and cancelled events are not part
        of the normal student event listing.

        Ongoing events remain visible because members may
        need to access event information or an online link.
        """

        return self.status in (
            self.Status.PUBLISHED,
            self.Status.ONGOING,
        )

    # =========================================================
    # REGISTRATION HELPERS
    # =========================================================

    @property
    def registration_count(self):
        """
        Number of active registrations occupying capacity.

        REGISTERED and ATTENDED registrations occupy a slot.

        CANCELLED and ABSENT registrations do not occupy
        capacity.
        """

        return self.registrations.filter(
            status__in=[
                EventRegistration
                .RegistrationStatus
                .REGISTERED,

                EventRegistration
                .RegistrationStatus
                .ATTENDED,
            ],
        ).count()

    @property
    def attendee_count(self):
        """
        Number of users who actually attended.
        """

        return self.registrations.filter(
            status=(
                EventRegistration
                .RegistrationStatus
                .ATTENDED
            ),
        ).count()

    @property
    def cancelled_count(self):
        """
        Number of cancelled registrations.
        """

        return self.registrations.filter(
            status=(
                EventRegistration
                .RegistrationStatus
                .CANCELLED
            ),
        ).count()

    @property
    def absent_count(self):
        """
        Number of registered users marked absent.
        """

        return self.registrations.filter(
            status=(
                EventRegistration
                .RegistrationStatus
                .ABSENT
            ),
        ).count()

    @property
    def total_registration_records(self):
        """
        Total number of registration records, regardless
        of status.
        """

        return self.registrations.count()

    @property
    def available_slots(self):
        """
        Number of remaining active registration slots.

        Returns None when capacity is unlimited.
        """

        if self.capacity is None:
            return None

        return max(
            self.capacity - self.registration_count,
            0,
        )

    @property
    def is_full(self):
        """
        True when the event has reached its capacity.
        """

        if self.capacity is None:
            return False

        return self.registration_count >= self.capacity

    @property
    def registration_is_open(self):
        """
        Determine whether a student/member can currently
        register for this event.
        """

        if not self.requires_registration:
            return False

        if self.status != self.Status.PUBLISHED:
            return False

        if (
            self.registration_status
            != self.RegistrationStatus.OPEN
        ):
            return False

        if self.is_full:
            return False

        now = timezone.now()

        if self.start_datetime <= now:
            return False

        if (
            self.registration_deadline
            and now >= self.registration_deadline
        ):
            return False

        return True

    @property
    def registration_closed_reason(self):
        """
        Human-readable explanation of why registration
        cannot currently be made.

        Useful for templates.
        """

        if not self.requires_registration:
            return "Registration is not required."

        if self.status == self.Status.DRAFT:
            return "Registration is not available for draft events."

        if self.status == self.Status.CANCELLED:
            return "This event has been cancelled."

        if self.status == self.Status.COMPLETED:
            return "This event has already been completed."

        if self.status == self.Status.ONGOING:
            return "Registration is closed because the event is ongoing."

        if self.registration_status != self.RegistrationStatus.OPEN:
            return "Registration is currently closed."

        if self.is_full:
            return "This event is full."

        now = timezone.now()

        if self.start_datetime <= now:
            return "Registration has closed because the event has started."

        if (
            self.registration_deadline
            and now >= self.registration_deadline
        ):
            return "The registration deadline has passed."

        return "Registration is currently unavailable."

    # =========================================================
    # EVENT STATISTICS
    # =========================================================

    @property
    def attendance_rate(self):
        """
        Return attendance percentage among active registrations.

        Returns 0 when there are no active registrations.
        """

        registered_count = self.registration_count

        if registered_count == 0:
            return 0

        return round(
            (
                self.attendee_count
                / registered_count
            )
            * 100
        )

    # =========================================================
    # ORGANIZER HELPERS
    # =========================================================

    @property
    def organizer_name(self):
        """
        Return a readable organizer name.
        """

        if not self.organizer:
            return "KUCSA"

        return (
            self.organizer.get_full_name()
            or self.organizer.username
        )


# =========================================================
# EVENT REGISTRATION
# =========================================================


class EventRegistration(models.Model):
    """
    Registration of a KUCSA member/user for an event.

    A user can have only one registration record per event.

    Registration lifecycle:

        REGISTERED
            ↓
        ATTENDED

        REGISTERED
            ↓
        ABSENT

        REGISTERED
            ↓
        CANCELLED
    """

    # =========================================================
    # CHOICES
    # =========================================================

    class RegistrationStatus(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        ATTENDED = "ATTENDED", "Attended"
        CANCELLED = "CANCELLED", "Cancelled"
        ABSENT = "ABSENT", "Absent"

    # =========================================================
    # RELATIONSHIPS
    # =========================================================

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="registrations",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_registrations",
    )

    # =========================================================
    # REGISTRATION INFORMATION
    # =========================================================

    status = models.CharField(
        max_length=20,
        choices=RegistrationStatus.choices,
        default=RegistrationStatus.REGISTERED,
    )

    registered_at = models.DateTimeField(
        auto_now_add=True,
    )

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    attended_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # =========================================================
    # OPTIONAL INFORMATION
    # =========================================================

    notes = models.TextField(
        blank=True,
        help_text=(
            "Optional notes from the attendee."
        ),
    )

    # =========================================================
    # META
    # =========================================================

    class Meta:
        ordering = [
            "-registered_at",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "event",
                    "user",
                ],
                name="unique_event_registration",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "event",
                    "status",
                ],
            ),
            models.Index(
                fields=[
                    "user",
                    "status",
                ],
            ),
            models.Index(
                fields=[
                    "event",
                    "registered_at",
                ],
            ),
            models.Index(
                fields=[
                    "user",
                    "registered_at",
                ],
            ),
        ]

        verbose_name = "Event Registration"
        verbose_name_plural = "Event Registrations"

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        full_name = (
            self.user.get_full_name()
            or self.user.username
        )

        return (
            f"{full_name} - {self.event.title}"
        )

    # =========================================================
    # VALIDATION
    # =========================================================

    def clean(self):
        """
        Validate an event registration.

        New registrations must satisfy the event's
        registration rules.

        Existing registrations may be managed by
        authorized users.
        """

        if not self.event_id or not self.user_id:
            return

        # =====================================================
        # NEW REGISTRATION
        # =====================================================

        if self._state.adding:

            if not self.event.registration_is_open:
                raise ValidationError(
                    "Registration for this event is "
                    "currently closed."
                )

            # -------------------------------------------------
            # CAPACITY CHECK
            # -------------------------------------------------

            if self.event.is_full:
                raise ValidationError(
                    "This event has reached its capacity."
                )

        # =====================================================
        # CANCELLED STATUS
        # =====================================================

        if (
            self.status
            == self.RegistrationStatus.CANCELLED
        ):
            if not self.cancelled_at:
                self.cancelled_at = timezone.now()

            self.attended_at = None

        # =====================================================
        # ATTENDED STATUS
        # =====================================================

        elif (
            self.status
            == self.RegistrationStatus.ATTENDED
        ):
            if not self.attended_at:
                self.attended_at = timezone.now()

            self.cancelled_at = None

        # =====================================================
        # REGISTERED STATUS
        # =====================================================

        elif (
            self.status
            == self.RegistrationStatus.REGISTERED
        ):
            self.cancelled_at = None
            self.attended_at = None

        # =====================================================
        # ABSENT STATUS
        # =====================================================

        elif (
            self.status
            == self.RegistrationStatus.ABSENT
        ):
            self.cancelled_at = None
            self.attended_at = None

    # =========================================================
    # SAVE
    # =========================================================

    def save(self, *args, **kwargs):
        """
        Maintain registration timestamps consistently.

        This method intentionally does not call full_clean().
        Validation is handled by Django forms/admin and the
        event-registration view.
        """

        now = timezone.now()

        # =====================================================
        # CANCELLED
        # =====================================================

        if (
            self.status
            == self.RegistrationStatus.CANCELLED
        ):
            if not self.cancelled_at:
                self.cancelled_at = now

            self.attended_at = None

        # =====================================================
        # ATTENDED
        # =====================================================

        elif (
            self.status
            == self.RegistrationStatus.ATTENDED
        ):
            if not self.attended_at:
                self.attended_at = now

            self.cancelled_at = None

        # =====================================================
        # REGISTERED / ABSENT
        # =====================================================

        else:
            self.cancelled_at = None
            self.attended_at = None

        super().save(*args, **kwargs)

    # =========================================================
    # STATUS HELPERS
    # =========================================================

    @property
    def is_registered(self):
        return (
            self.status
            == self.RegistrationStatus.REGISTERED
        )

    @property
    def has_attended(self):
        return (
            self.status
            == self.RegistrationStatus.ATTENDED
        )

    @property
    def is_cancelled(self):
        return (
            self.status
            == self.RegistrationStatus.CANCELLED
        )

    @property
    def is_absent(self):
        return (
            self.status
            == self.RegistrationStatus.ABSENT
        )

    # =========================================================
    # DISPLAY HELPERS
    # =========================================================

    @property
    def status_display(self):
        return self.get_status_display()

    @property
    def attendee_name(self):
        """
        Return a readable attendee name.
        """

        return (
            self.user.get_full_name()
            or self.user.username
        )

    @property
    def event_title(self):
        return self.event.title