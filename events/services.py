# events/services.py

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Event, EventRegistration


class EventService:
    """
    Central business-logic service for KUCSA events.

    Responsibilities:
        - Event creation
        - Event updates
        - Event publishing
        - Event unpublishing
        - Event cancellation
        - Event completion
        - Automatic status synchronization
        - Event discovery and filtering
        - Event registration
        - Registration cancellation
        - Capacity management
        - Attendance management
        - Event statistics
        - Registration statistics
        - Upcoming-event reminders

    Views should ideally use this service for business operations
    rather than duplicating business rules inside views.
    """

    # =========================================================
    # EVENT CREATION
    # =========================================================

    @staticmethod
    @transaction.atomic
    def create_event(user, **data):
        """
        Create a new KUCSA event.

        The authenticated user becomes the event organizer.

        Raises:
            ValueError:
                If no valid user is supplied.

            ValidationError:
                If the event data is invalid.
        """

        if not user or not getattr(user, "is_authenticated", False):
            raise ValueError("A valid authenticated user is required.")

        event = Event(
            organizer=user,
            **data,
        )

        event.full_clean()
        event.save()

        return event

    # =========================================================
    # EVENT UPDATE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def update_event(event, **data):
        """
        Update an existing event.

        Protected fields:
            - id
            - created_at
            - updated_at
            - organizer

        The organizer is intentionally preserved.
        """

        if not event:
            raise ValueError("A valid event is required.")

        protected_fields = {
            "id",
            "pk",
            "created_at",
            "updated_at",
            "organizer",
        }

        valid_fields = {
            field.name
            for field in Event._meta.fields
        }

        for field_name, value in data.items():

            if field_name not in valid_fields:
                continue

            if field_name in protected_fields:
                continue

            setattr(
                event,
                field_name,
                value,
            )

        event.full_clean()
        event.save()

        return event

    # =========================================================
    # EVENT RETRIEVAL
    # =========================================================

    @staticmethod
    def get_event(event_id):
        """
        Retrieve an event by primary key.

        Returns:
            Event instance or None.
        """

        if not event_id:
            return None

        return (
            Event.objects
            .select_related("organizer")
            .filter(pk=event_id)
            .first()
        )

    # ---------------------------------------------------------

    @staticmethod
    def get_event_with_registrations(event_id):
        """
        Retrieve an event together with its registrations.
        """

        if not event_id:
            return None

        return (
            Event.objects
            .select_related("organizer")
            .prefetch_related(
                "registrations__user"
            )
            .filter(pk=event_id)
            .first()
        )

    # =========================================================
    # EVENT LISTS
    # =========================================================

    @staticmethod
    def get_all_events():
        """
        Return all KUCSA events.

        Intended mainly for administrators and executives.
        """

        return (
            Event.objects
            .select_related("organizer")
            .all()
            .order_by("start_datetime")
        )

    # ---------------------------------------------------------

    @staticmethod
    def get_published_events():
        """
        Return all published events.
        """

        return (
            Event.objects
            .select_related("organizer")
            .filter(
                status=Event.Status.PUBLISHED
            )
            .order_by("start_datetime")
        )

    # ---------------------------------------------------------

    @staticmethod
    def get_upcoming_events():
        """
        Return published events that have not started.
        """

        now = timezone.now()

        return (
            Event.objects
            .select_related("organizer")
            .filter(
                status=Event.Status.PUBLISHED,
                start_datetime__gt=now,
            )
            .order_by("start_datetime")
        )

    # ---------------------------------------------------------

    @staticmethod
    def get_ongoing_events():
        """
        Return currently ongoing published events.
        """

        now = timezone.now()

        return (
            Event.objects
            .select_related("organizer")
            .filter(
                status=Event.Status.ONGOING,
                start_datetime__lte=now,
                end_datetime__gte=now,
            )
            .order_by("start_datetime")
        )

    # ---------------------------------------------------------

    @staticmethod
    def get_past_events():
        """
        Return events whose end time has passed.

        Cancelled events are excluded because cancellation is a
        separate lifecycle state.
        """

        now = timezone.now()

        return (
            Event.objects
            .select_related("organizer")
            .filter(
                end_datetime__lt=now,
            )
            .exclude(
                status=Event.Status.CANCELLED
            )
            .order_by("-start_datetime")
        )

    # ---------------------------------------------------------

    @staticmethod
    def get_completed_events():
        """
        Return completed events.
        """

        return (
            Event.objects
            .select_related("organizer")
            .filter(
                status=Event.Status.COMPLETED
            )
            .order_by("-start_datetime")
        )

    # ---------------------------------------------------------

    @staticmethod
    def get_cancelled_events():
        """
        Return cancelled events.
        """

        return (
            Event.objects
            .select_related("organizer")
            .filter(
                status=Event.Status.CANCELLED
            )
            .order_by("-start_datetime")
        )

    # ---------------------------------------------------------

    @staticmethod
    def get_featured_events():
        """
        Return featured published upcoming events.
        """

        now = timezone.now()

        return (
            Event.objects
            .select_related("organizer")
            .filter(
                is_featured=True,
                status=Event.Status.PUBLISHED,
                start_datetime__gt=now,
            )
            .order_by("start_datetime")
        )

    # =========================================================
    # EVENT SEARCH
    # =========================================================

    @staticmethod
    def search_events(query=None):
        """
        Search events by:

            - title
            - description
            - venue
            - location details
            - target audience
            - event type
        """

        queryset = (
            Event.objects
            .select_related("organizer")
        )

        if not query:
            return queryset.order_by(
                "start_datetime"
            )

        query = query.strip()

        if not query:
            return queryset.order_by(
                "start_datetime"
            )

        return (
            queryset
            .filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(venue__icontains=query)
                | Q(location_details__icontains=query)
                | Q(target_audience__icontains=query)
                | Q(event_type__icontains=query)
            )
            .distinct()
            .order_by("start_datetime")
        )

    # =========================================================
    # EVENT FILTERING
    # =========================================================

    @staticmethod
    def filter_events(
        search=None,
        event_type=None,
        status=None,
        registration_status=None,
        featured=None,
        upcoming_only=False,
    ):
        """
        Filter events using optional criteria.

        This method is suitable for both executive and
        member-facing event discovery.
        """

        queryset = (
            Event.objects
            .select_related("organizer")
        )

        # -----------------------------------------------------
        # SEARCH
        # -----------------------------------------------------

        if search:
            search = search.strip()

            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search)
                    | Q(description__icontains=search)
                    | Q(venue__icontains=search)
                    | Q(location_details__icontains=search)
                    | Q(target_audience__icontains=search)
                    | Q(event_type__icontains=search)
                )

        # -----------------------------------------------------
        # EVENT TYPE
        # -----------------------------------------------------

        if event_type:
            queryset = queryset.filter(
                event_type=event_type
            )

        # -----------------------------------------------------
        # STATUS
        # -----------------------------------------------------

        if status:
            queryset = queryset.filter(
                status=status
            )

        # -----------------------------------------------------
        # REGISTRATION STATUS
        # -----------------------------------------------------

        if registration_status:
            queryset = queryset.filter(
                registration_status=registration_status
            )

        # -----------------------------------------------------
        # FEATURED
        # -----------------------------------------------------

        if featured is not None:
            queryset = queryset.filter(
                is_featured=featured
            )

        # -----------------------------------------------------
        # UPCOMING
        # -----------------------------------------------------

        if upcoming_only:
            queryset = queryset.filter(
                start_datetime__gt=timezone.now()
            )

        return (
            queryset
            .distinct()
            .order_by("start_datetime")
        )

    # =========================================================
    # EVENT PUBLISHING
    # =========================================================

    @staticmethod
    @transaction.atomic
    def publish_event(event):
        """
        Publish a draft event.

        Rules:
            - Event must exist.
            - Event cannot be cancelled.
            - Event must have a future start time.
            - Event must have a valid end time.
            - Registration opens only when registration is
              required.
        """

        if not event:
            raise ValueError(
                "A valid event is required."
            )

        now = timezone.now()

        if event.status == Event.Status.CANCELLED:
            raise ValueError(
                "A cancelled event cannot be published."
            )

        if not event.start_datetime:
            raise ValueError(
                "An event must have a start date and time."
            )

        if event.start_datetime <= now:
            raise ValueError(
                "A past event cannot be published."
            )

        if (
            event.end_datetime
            and event.end_datetime <= event.start_datetime
        ):
            raise ValueError(
                "The event end time must be after the start time."
            )

        event.status = Event.Status.PUBLISHED

        if event.requires_registration:
            event.registration_status = (
                Event.RegistrationStatus.OPEN
            )
        else:
            event.registration_status = (
                Event.RegistrationStatus.CLOSED
            )

        event.full_clean()

        event.save(
            update_fields=[
                "status",
                "registration_status",
                "updated_at",
            ]
        )

        return event

    # =========================================================
    # EVENT UNPUBLISH
    # =========================================================

    @staticmethod
    @transaction.atomic
    def unpublish_event(event):
        """
        Return a published event to draft status.

        Registration is closed while the event is a draft.
        """

        if not event:
            raise ValueError(
                "A valid event is required."
            )

        if event.status == Event.Status.CANCELLED:
            raise ValueError(
                "A cancelled event cannot be unpublished."
            )

        if event.status == Event.Status.COMPLETED:
            raise ValueError(
                "A completed event cannot be unpublished."
            )

        event.status = Event.Status.DRAFT

        event.registration_status = (
            Event.RegistrationStatus.CLOSED
        )

        event.save(
            update_fields=[
                "status",
                "registration_status",
                "updated_at",
            ]
        )

        return event

    # =========================================================
    # EVENT CANCELLATION
    # =========================================================

    @staticmethod
    @transaction.atomic
    def cancel_event(event):
        """
        Cancel an event.

        Registration history is preserved.

        Active registrations are changed to CANCELLED and their
        cancellation timestamp is recorded.
        """

        if not event:
            raise ValueError(
                "A valid event is required."
            )

        if event.status == Event.Status.COMPLETED:
            raise ValueError(
                "A completed event cannot be cancelled."
            )

        if event.status == Event.Status.CANCELLED:
            return event

        now = timezone.now()

        event.status = Event.Status.CANCELLED
        event.registration_status = (
            Event.RegistrationStatus.CLOSED
        )

        event.save(
            update_fields=[
                "status",
                "registration_status",
                "updated_at",
            ]
        )

        # -----------------------------------------------------
        # Cancel active registrations.
        #
        # ATTENDED records are preserved because attendance
        # history must never be destroyed.
        # -----------------------------------------------------

        EventRegistration.objects.filter(
            event=event,
            status=EventRegistration.RegistrationStatus.REGISTERED,
        ).update(
            status=EventRegistration.RegistrationStatus.CANCELLED,
            cancelled_at=now,
        )

        return event

    # =========================================================
    # EVENT COMPLETION
    # =========================================================

    @staticmethod
    @transaction.atomic
    def complete_event(event):
        """
        Mark an event as completed.

        Registration is automatically closed.

        Existing attendance records are preserved.
        """

        if not event:
            raise ValueError(
                "A valid event is required."
            )

        if event.status == Event.Status.CANCELLED:
            raise ValueError(
                "A cancelled event cannot be completed."
            )

        if event.status == Event.Status.COMPLETED:
            return event

        event.status = Event.Status.COMPLETED

        event.registration_status = (
            Event.RegistrationStatus.CLOSED
        )

        event.save(
            update_fields=[
                "status",
                "registration_status",
                "updated_at",
            ]
        )

        return event

    # =========================================================
    # EVENT STATUS SYNCHRONIZATION
    # =========================================================

    @staticmethod
    @transaction.atomic
    def update_event_statuses():
        """
        Synchronize event statuses with their scheduled times.

        Rules:

            PUBLISHED
                |
                | start time reached
                v
            ONGOING
                |
                | end time reached
                v
            COMPLETED

        Cancelled and draft events are never automatically
        changed.

        Returns:
            Dictionary containing counts of updated events.
        """

        now = timezone.now()

        # -----------------------------------------------------
        # PUBLISHED -> ONGOING
        # -----------------------------------------------------

        ongoing_count = (
            Event.objects
            .filter(
                status=Event.Status.PUBLISHED,
                start_datetime__lte=now,
                end_datetime__gt=now,
            )
            .update(
                status=Event.Status.ONGOING,
                updated_at=now,
            )
        )

        # -----------------------------------------------------
        # PUBLISHED -> COMPLETED
        #
        # Handles events whose complete lifecycle passed
        # before the status synchronization task ran.
        # -----------------------------------------------------

        completed_from_published = (
            Event.objects
            .filter(
                status=Event.Status.PUBLISHED,
                end_datetime__lte=now,
            )
            .update(
                status=Event.Status.COMPLETED,
                registration_status=(
                    Event.RegistrationStatus.CLOSED
                ),
                updated_at=now,
            )
        )

        # -----------------------------------------------------
        # ONGOING -> COMPLETED
        # -----------------------------------------------------

        completed_from_ongoing = (
            Event.objects
            .filter(
                status=Event.Status.ONGOING,
                end_datetime__lte=now,
            )
            .update(
                status=Event.Status.COMPLETED,
                registration_status=(
                    Event.RegistrationStatus.CLOSED
                ),
                updated_at=now,
            )
        )

        return {
            "ongoing": ongoing_count,
            "completed": (
                completed_from_published
                + completed_from_ongoing
            ),
        }

    # =========================================================
    # REGISTRATION COUNT
    # =========================================================

    @staticmethod
    def get_registration_count(event):
        """
        Return the number of registrations occupying a slot.

        REGISTERED and ATTENDED registrations count toward
        capacity.

        CANCELLED and ABSENT registrations do not occupy
        capacity.
        """

        if not event:
            return 0

        return (
            EventRegistration.objects
            .filter(
                event=event,
                status__in=[
                    EventRegistration.RegistrationStatus.REGISTERED,
                    EventRegistration.RegistrationStatus.ATTENDED,
                ],
            )
            .count()
        )

    # =========================================================
    # ATTENDEE COUNT
    # =========================================================

    @staticmethod
    def get_attendee_count(event):
        """
        Return the number of attendees.
        """

        if not event:
            return 0

        return (
            EventRegistration.objects
            .filter(
                event=event,
                status=(
                    EventRegistration
                    .RegistrationStatus.ATTENDED
                ),
            )
            .count()
        )

    # =========================================================
    # CANCELLED COUNT
    # =========================================================

    @staticmethod
    def get_cancelled_count(event):
        """
        Return the number of cancelled registrations.
        """

        if not event:
            return 0

        return (
            EventRegistration.objects
            .filter(
                event=event,
                status=(
                    EventRegistration
                    .RegistrationStatus.CANCELLED
                ),
            )
            .count()
        )

    # =========================================================
    # ABSENT COUNT
    # =========================================================

    @staticmethod
    def get_absent_count(event):
        """
        Return the number of registrations marked absent.
        """

        if not event:
            return 0

        return (
            EventRegistration.objects
            .filter(
                event=event,
                status=(
                    EventRegistration
                    .RegistrationStatus.ABSENT
                ),
            )
            .count()
        )

    # =========================================================
    # AVAILABLE SLOTS
    # =========================================================

    @staticmethod
    def get_available_slots(event):
        """
        Return remaining registration capacity.

        Returns:
            None for unlimited-capacity events.
        """

        if not event:
            return 0

        if event.capacity is None:
            return None

        registered = EventService.get_registration_count(
            event
        )

        return max(
            event.capacity - registered,
            0,
        )

    # =========================================================
    # EVENT FULL
    # =========================================================

    @staticmethod
    def is_event_full(event):
        """
        Determine whether an event has reached capacity.
        """

        if not event:
            return False

        if event.capacity is None:
            return False

        return (
            EventService.get_registration_count(event)
            >= event.capacity
        )

    # =========================================================
    # USER REGISTRATION
    # =========================================================

    @staticmethod
    @transaction.atomic
    def register_user(event, user, notes=""):
        """
        Register a user for an event.

        Handles:
            - Registration availability
            - Event publication
            - Registration deadline
            - Capacity
            - Duplicate registrations
            - Re-registration after cancellation

        The event is locked during the transaction to prevent
        race conditions when only one slot remains.
        """

        if not event:
            raise ValueError(
                "A valid event is required."
            )

        if not user or not getattr(
            user,
            "is_authenticated",
            False,
        ):
            raise ValueError(
                "A valid authenticated user is required."
            )

        # -----------------------------------------------------
        # Lock event for capacity-sensitive operation.
        # -----------------------------------------------------

        event = (
            Event.objects
            .select_for_update()
            .get(pk=event.pk)
        )

        # -----------------------------------------------------
        # Event status
        # -----------------------------------------------------

        if event.status != Event.Status.PUBLISHED:
            raise ValueError(
                "Only published events can accept registrations."
            )

        # -----------------------------------------------------
        # Registration enabled
        # -----------------------------------------------------

        if not event.requires_registration:
            raise ValueError(
                "Registration is not required for this event."
            )

        if (
            event.registration_status
            != Event.RegistrationStatus.OPEN
        ):
            raise ValueError(
                "Registration for this event is currently closed."
            )

        # -----------------------------------------------------
        # Event has not started
        # -----------------------------------------------------

        now = timezone.now()

        if event.start_datetime <= now:
            raise ValueError(
                "Registration is closed because the event has started."
            )

        # -----------------------------------------------------
        # Registration deadline
        # -----------------------------------------------------

        if (
            event.registration_deadline
            and now >= event.registration_deadline
        ):
            raise ValueError(
                "The registration deadline has passed."
            )

        # -----------------------------------------------------
        # Existing registration
        # -----------------------------------------------------

        existing = (
            EventRegistration.objects
            .select_for_update()
            .filter(
                event=event,
                user=user,
            )
            .first()
        )

        if existing:

            if (
                existing.status
                != EventRegistration.RegistrationStatus.CANCELLED
            ):
                raise ValueError(
                    "You are already registered for this event."
                )

        # -----------------------------------------------------
        # Capacity
        # -----------------------------------------------------

        if event.capacity is not None:

            active_count = (
                EventRegistration.objects
                .filter(
                    event=event,
                    status__in=[
                        EventRegistration
                        .RegistrationStatus.REGISTERED,
                        EventRegistration
                        .RegistrationStatus.ATTENDED,
                    ],
                )
                .count()
            )

            if active_count >= event.capacity:
                raise ValueError(
                    "This event has reached its maximum capacity."
                )

        # -----------------------------------------------------
        # Re-register cancelled registration
        # -----------------------------------------------------

        if existing:

            existing.status = (
                EventRegistration
                .RegistrationStatus.REGISTERED
            )

            existing.notes = notes
            existing.cancelled_at = None
            existing.attended_at = None

            existing.save(
                update_fields=[
                    "status",
                    "notes",
                    "cancelled_at",
                    "attended_at",
                ]
            )

            return existing

        # -----------------------------------------------------
        # Create registration
        # -----------------------------------------------------

        registration = EventRegistration.objects.create(
            event=event,
            user=user,
            status=(
                EventRegistration
                .RegistrationStatus.REGISTERED
            ),
            notes=notes,
        )

        return registration

    # =========================================================
    # GET USER REGISTRATION
    # =========================================================

    @staticmethod
    def get_user_registration(event, user):
        """
        Retrieve a user's registration for an event.

        Returns:
            EventRegistration or None.
        """

        if not event or not user:
            return None

        return (
            EventRegistration.objects
            .select_related("event", "user")
            .filter(
                event=event,
                user=user,
            )
            .first()
        )

    # =========================================================
    # CHECK REGISTRATION
    # =========================================================

    @staticmethod
    def is_user_registered(event, user):
        """
        Return True when a user currently occupies a registration
        slot for an event.

        REGISTERED and ATTENDED are considered active.
        """

        if not event or not user:
            return False

        return (
            EventRegistration.objects
            .filter(
                event=event,
                user=user,
                status__in=[
                    EventRegistration.RegistrationStatus.REGISTERED,
                    EventRegistration.RegistrationStatus.ATTENDED,
                ],
            )
            .exists()
        )

    # =========================================================
    # CANCEL REGISTRATION
    # =========================================================

    @staticmethod
    @transaction.atomic
    def cancel_registration(event, user):
        """
        Cancel a user's active registration.

        ATTENDED registrations cannot be cancelled because
        attendance history must remain intact.
        """

        if not event:
            raise ValueError(
                "A valid event is required."
            )

        if not user:
            raise ValueError(
                "A valid user is required."
            )

        registration = (
            EventRegistration.objects
            .select_for_update()
            .filter(
                event=event,
                user=user,
            )
            .first()
        )

        if not registration:
            raise ValueError(
                "You do not have a registration for this event."
            )

        if (
            registration.status
            == EventRegistration.RegistrationStatus.CANCELLED
        ):
            raise ValueError(
                "Your registration is already cancelled."
            )

        if (
            registration.status
            == EventRegistration.RegistrationStatus.ATTENDED
        ):
            raise ValueError(
                "An attendance record cannot be cancelled."
            )

        registration.status = (
            EventRegistration
            .RegistrationStatus.CANCELLED
        )

        registration.cancelled_at = timezone.now()

        registration.save(
            update_fields=[
                "status",
                "cancelled_at",
            ]
        )

        return registration

    # =========================================================
    # USER EVENTS
    # =========================================================

    @staticmethod
    def get_user_events(user):
        """
        Return all non-cancelled events registered by a user.
        """

        if not user:
            return Event.objects.none()

        return (
            Event.objects
            .select_related("organizer")
            .filter(
                registrations__user=user,
            )
            .exclude(
                registrations__status=(
                    EventRegistration
                    .RegistrationStatus.CANCELLED
                )
            )
            .distinct()
            .order_by("start_datetime")
        )

    # ---------------------------------------------------------

    @staticmethod
    def get_user_upcoming_events(user):
        """
        Return upcoming events for which the user has an active
        registration.
        """

        if not user:
            return Event.objects.none()

        return (
            Event.objects
            .select_related("organizer")
            .filter(
                registrations__user=user,
                registrations__status__in=[
                    EventRegistration
                    .RegistrationStatus.REGISTERED,
                    EventRegistration
                    .RegistrationStatus.ATTENDED,
                ],
                start_datetime__gt=timezone.now(),
            )
            .distinct()
            .order_by("start_datetime")
        )

    # ---------------------------------------------------------

    @staticmethod
    def get_user_past_events(user):
        """
        Return past events for which the user had a non-cancelled
        registration.
        """

        if not user:
            return Event.objects.none()

        return (
            Event.objects
            .select_related("organizer")
            .filter(
                registrations__user=user,
                start_datetime__lte=timezone.now(),
            )
            .exclude(
                registrations__status=(
                    EventRegistration
                    .RegistrationStatus.CANCELLED
                )
            )
            .distinct()
            .order_by("-start_datetime")
        )

    # ---------------------------------------------------------

    @staticmethod
    def get_user_attended_events(user):
        """
        Return events the user actually attended.
        """

        if not user:
            return Event.objects.none()

        return (
            Event.objects
            .select_related("organizer")
            .filter(
                registrations__user=user,
                registrations__status=(
                    EventRegistration
                    .RegistrationStatus.ATTENDED
                ),
            )
            .distinct()
            .order_by("-start_datetime")
        )

    # =========================================================
    # ATTENDANCE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def mark_attendance(registration, attended=True):
        """
        Mark a registration as attended or absent.

        Cancelled registrations cannot be marked as attended
        or absent.
        """

        if not registration:
            raise ValueError(
                "A valid registration is required."
            )

        registration = (
            EventRegistration.objects
            .select_for_update()
            .select_related("event", "user")
            .get(pk=registration.pk)
        )

        if (
            registration.status
            == EventRegistration.RegistrationStatus.CANCELLED
        ):
            raise ValueError(
                "A cancelled registration cannot receive attendance status."
            )

        if attended:

            registration.status = (
                EventRegistration
                .RegistrationStatus.ATTENDED
            )

            registration.attended_at = timezone.now()

            registration.save(
                update_fields=[
                    "status",
                    "attended_at",
                ]
            )

        else:

            registration.status = (
                EventRegistration
                .RegistrationStatus.ABSENT
            )

            registration.attended_at = None

            registration.save(
                update_fields=[
                    "status",
                    "attended_at",
                ]
            )

        return registration

    # =========================================================
    # BULK ATTENDANCE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def mark_event_attendance(
        event,
        attended_user_ids,
    ):
        """
        Mark multiple registered users as attended.

        attended_user_ids:
            Iterable containing user IDs.

        Returns:
            Number of registrations updated.
        """

        if not event:
            raise ValueError(
                "A valid event is required."
            )

        if attended_user_ids is None:
            attended_user_ids = []

        attended_user_ids = list(
            set(attended_user_ids)
        )

        if not attended_user_ids:
            return 0

        now = timezone.now()

        return (
            EventRegistration.objects
            .filter(
                event=event,
                user_id__in=attended_user_ids,
                status__in=[
                    EventRegistration
                    .RegistrationStatus.REGISTERED,
                    EventRegistration
                    .RegistrationStatus.ABSENT,
                ],
            )
            .update(
                status=(
                    EventRegistration
                    .RegistrationStatus.ATTENDED
                ),
                attended_at=now,
            )
        )

    # =========================================================
    # MARK EVENT ABSENTEES
    # =========================================================

    @staticmethod
    @transaction.atomic
    def mark_event_absentees(event):
        """
        Mark all remaining registered users as absent.

        Cancelled and already-attended registrations are not
        changed.

        Returns:
            Number of registrations marked absent.
        """

        if not event:
            raise ValueError(
                "A valid event is required."
            )

        return (
            EventRegistration.objects
            .filter(
                event=event,
                status=(
                    EventRegistration
                    .RegistrationStatus.REGISTERED
                ),
            )
            .update(
                status=(
                    EventRegistration
                    .RegistrationStatus.ABSENT
                ),
                attended_at=None,
            )
        )

    # =========================================================
    # EVENT REGISTRATIONS
    # =========================================================

    @staticmethod
    def get_event_registrations(event):
        """
        Return every registration for an event.

        Includes:
            - Registered
            - Attended
            - Absent
            - Cancelled
        """

        if not event:
            return EventRegistration.objects.none()

        return (
            EventRegistration.objects
            .filter(event=event)
            .select_related("user", "event")
            .order_by(
                "status",
                "registered_at",
            )
        )

    # ---------------------------------------------------------

    @staticmethod
    def get_active_registrations(event):
        """
        Return registrations currently occupying a slot.

        Includes:
            - Registered
            - Attended

        Excludes:
            - Cancelled
            - Absent
        """

        if not event:
            return EventRegistration.objects.none()

        return (
            EventRegistration.objects
            .filter(
                event=event,
                status__in=[
                    EventRegistration
                    .RegistrationStatus.REGISTERED,
                    EventRegistration
                    .RegistrationStatus.ATTENDED,
                ],
            )
            .select_related("user", "event")
            .order_by("registered_at")
        )

    # ---------------------------------------------------------

    @staticmethod
    def get_registered_users(event):
        """
        Return users currently registered for an event.
        """

        if not event:
            return EventRegistration.objects.none()

        return (
            EventRegistration.objects
            .filter(
                event=event,
                status=(
                    EventRegistration
                    .RegistrationStatus.REGISTERED
                ),
            )
            .select_related("user")
            .order_by("registered_at")
        )

    # =========================================================
    # EVENT STATISTICS
    # =========================================================

    @staticmethod
    def get_event_statistics(event):
        """
        Return comprehensive statistics for one event.
        """

        if not event:
            raise ValueError(
                "A valid event is required."
            )

        registrations = (
            EventRegistration.objects
            .filter(event=event)
        )

        total = registrations.count()

        registered = registrations.filter(
            status=(
                EventRegistration
                .RegistrationStatus.REGISTERED
            )
        ).count()

        attended = registrations.filter(
            status=(
                EventRegistration
                .RegistrationStatus.ATTENDED
            )
        ).count()

        absent = registrations.filter(
            status=(
                EventRegistration
                .RegistrationStatus.ABSENT
            )
        ).count()

        cancelled = registrations.filter(
            status=(
                EventRegistration
                .RegistrationStatus.CANCELLED
            )
        ).count()

        active_registrations = (
            registered + attended
        )

        capacity = event.capacity

        available_slots = None

        if capacity is not None:
            available_slots = max(
                capacity - active_registrations,
                0,
            )

        attendance_denominator = (
            attended + absent
        )

        attendance_rate = 0

        if attendance_denominator:
            attendance_rate = round(
                (
                    attended
                    / attendance_denominator
                )
                * 100,
                2,
            )

        return {
            "total": total,
            "registered": registered,
            "attended": attended,
            "absent": absent,
            "cancelled": cancelled,
            "active_registrations": active_registrations,
            "capacity": capacity,
            "available_slots": available_slots,
            "is_full": (
                capacity is not None
                and active_registrations >= capacity
            ),
            "attendance_rate": attendance_rate,
        }

    # =========================================================
    # GENERAL EVENT STATISTICS
    # =========================================================

    @staticmethod
    def get_event_counts():
        """
        Return overall KUCSA event statistics.
        """

        now = timezone.now()

        total = Event.objects.count()

        draft = Event.objects.filter(
            status=Event.Status.DRAFT
        ).count()

        published = Event.objects.filter(
            status=Event.Status.PUBLISHED
        ).count()

        ongoing = Event.objects.filter(
            status=Event.Status.ONGOING
        ).count()

        completed = Event.objects.filter(
            status=Event.Status.COMPLETED
        ).count()

        cancelled = Event.objects.filter(
            status=Event.Status.CANCELLED
        ).count()

        upcoming = Event.objects.filter(
            status=Event.Status.PUBLISHED,
            start_datetime__gt=now,
        ).count()

        total_registrations = (
            EventRegistration.objects
            .filter(
                status__in=[
                    EventRegistration
                    .RegistrationStatus.REGISTERED,
                    EventRegistration
                    .RegistrationStatus.ATTENDED,
                ]
            )
            .count()
        )

        total_attendees = (
            EventRegistration.objects
            .filter(
                status=(
                    EventRegistration
                    .RegistrationStatus.ATTENDED
                )
            )
            .count()
        )

        total_absent = (
            EventRegistration.objects
            .filter(
                status=(
                    EventRegistration
                    .RegistrationStatus.ABSENT
                )
            )
            .count()
        )

        total_cancelled_registrations = (
            EventRegistration.objects
            .filter(
                status=(
                    EventRegistration
                    .RegistrationStatus.CANCELLED
                )
            )
            .count()
        )

        return {
            "total": total,
            "draft": draft,
            "published": published,
            "ongoing": ongoing,
            "completed": completed,
            "cancelled": cancelled,
            "upcoming": upcoming,
            "total_registrations": total_registrations,
            "total_attendees": total_attendees,
            "total_absent": total_absent,
            "total_cancelled_registrations": (
                total_cancelled_registrations
            ),
        }

    # =========================================================
    # UPCOMING EVENT REMINDERS
    # =========================================================

    @staticmethod
    def get_events_starting_soon(hours=24):
        """
        Return published events starting within the specified
        number of hours.
        """

        if hours <= 0:
            raise ValueError(
                "Hours must be greater than zero."
            )

        now = timezone.now()

        limit = now + timedelta(
            hours=hours
        )

        return (
            Event.objects
            .select_related("organizer")
            .filter(
                status=Event.Status.PUBLISHED,
                start_datetime__gte=now,
                start_datetime__lte=limit,
            )
            .order_by("start_datetime")
        )

    # =========================================================
    # REGISTRATION REMINDER DATA
    # =========================================================

    @staticmethod
    def get_registration_reminder_data(event):
        """
        Return registration information useful for reminder
        systems and notifications.
        """

        if not event:
            raise ValueError(
                "A valid event is required."
            )

        registrations = (
            EventRegistration.objects
            .filter(
                event=event,
                status=(
                    EventRegistration
                    .RegistrationStatus.REGISTERED
                ),
            )
            .select_related("user")
            .order_by("registered_at")
        )

        return {
            "event": event,
            "registrations": registrations,
            "registration_count": registrations.count(),
            "available_slots": (
                EventService.get_available_slots(event)
            ),
        }