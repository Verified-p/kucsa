# events/admin.py

from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils import timezone

from .models import Event, EventRegistration


# =========================================================
# EVENT REGISTRATION INLINE
# =========================================================


class EventRegistrationInline(admin.TabularInline):
    """
    Display event registrations directly inside the
    Event administration page.
    """

    model = EventRegistration

    extra = 0

    fields = (
        "user",
        "status",
        "registered_at",
        "cancelled_at",
        "attended_at",
        "notes",
    )

    readonly_fields = (
        "registered_at",
        "cancelled_at",
        "attended_at",
    )

    autocomplete_fields = (
        "user",
    )

    show_change_link = True

    ordering = (
        "-registered_at",
    )


# =========================================================
# EVENT ADMIN
# =========================================================


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """
    KUCSA Event administration.

    Provides:

        - Event management
        - Registration management
        - Attendance overview
        - Event publishing
        - Event cancellation
        - Event completion
        - Capacity monitoring
        - Search and filtering
    """

    # =====================================================
    # LIST DISPLAY
    # =====================================================

    list_display = (
        "title",
        "event_type_display",
        "start_datetime",
        "location_display",
        "organizer_display",
        "status_display",
        "registration_status_display",
        "registration_count_display",
        "capacity_display",
        "is_featured",
    )

    # =====================================================
    # LIST FILTERS
    # =====================================================

    list_filter = (
        "status",
        "event_type",
        "registration_status",
        "requires_registration",
        "is_online",
        "certificate_available",
        "is_featured",
        "start_datetime",
    )

    # =====================================================
    # SEARCH
    # =====================================================

    search_fields = (
        "title",
        "description",
        "venue",
        "location_details",
        "target_audience",
        "requirements",
        "slug",
        "organizer__username",
        "organizer__first_name",
        "organizer__last_name",
        "organizer__email",
    )

    # =====================================================
    # DATE HIERARCHY
    # =====================================================

    date_hierarchy = "start_datetime"

    # =====================================================
    # DEFAULT ORDERING
    # =====================================================

    ordering = (
        "-start_datetime",
    )

    # =====================================================
    # PAGINATION
    # =====================================================

    list_per_page = 25

    # =====================================================
    # SLUG
    # =====================================================

    prepopulated_fields = {
        "slug": ("title",),
    }

    # =====================================================
    # AUTOCOMPLETE
    # =====================================================

    autocomplete_fields = (
        "organizer",
    )

    # =====================================================
    # INLINE REGISTRATIONS
    # =====================================================

    inlines = (
        EventRegistrationInline,
    )

    # =====================================================
    # ADMIN UI
    # =====================================================

    save_on_top = True
    save_as = True

    # =====================================================
    # FIELDSETS
    # =====================================================

    fieldsets = (
        (
            "Event Information",
            {
                "fields": (
                    "title",
                    "slug",
                    "description",
                    "event_type",
                    "image",
                ),
            },
        ),
        (
            "Date & Time",
            {
                "fields": (
                    "start_datetime",
                    "end_datetime",
                ),
            },
        ),
        (
            "Venue & Location",
            {
                "fields": (
                    "is_online",
                    "venue",
                    "location_details",
                    "online_link",
                ),
            },
        ),
        (
            "Organization",
            {
                "fields": (
                    "organizer",
                ),
            },
        ),
        (
            "Registration",
            {
                "fields": (
                    "requires_registration",
                    "registration_status",
                    "registration_deadline",
                    "capacity",
                ),
            },
        ),
        (
            "Event Status",
            {
                "fields": (
                    "status",
                    "is_featured",
                ),
            },
        ),
        (
            "Additional Information",
            {
                "fields": (
                    "requirements",
                    "target_audience",
                    "certificate_available",
                ),
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    # =====================================================
    # READONLY FIELDS
    # =====================================================

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    # =====================================================
    # DISPLAY HELPERS
    # =====================================================

    @admin.display(
        description="Type",
        ordering="event_type",
    )
    def event_type_display(self, obj):
        return obj.get_event_type_display()

    @admin.display(
        description="Location",
    )
    def location_display(self, obj):
        if obj.is_online:
            return "Online"

        return obj.venue or "Not specified"

    @admin.display(
        description="Organizer",
    )
    def organizer_display(self, obj):
        if not obj.organizer:
            return "—"

        return (
            obj.organizer.get_full_name()
            or obj.organizer.username
        )

    @admin.display(
        description="Status",
        ordering="status",
    )
    def status_display(self, obj):
        return obj.get_status_display()

    @admin.display(
        description="Registration",
        ordering="registration_status",
    )
    def registration_status_display(self, obj):
        if not obj.requires_registration:
            return "Not Required"

        return obj.get_registration_status_display()

    @admin.display(
        description="Registrations",
        ordering="active_registration_count",
    )
    def registration_count_display(self, obj):
        return obj.active_registration_count

    @admin.display(
        description="Capacity",
    )
    def capacity_display(self, obj):
        if obj.capacity is None:
            return "Unlimited"

        return (
            f"{obj.active_registration_count}/"
            f"{obj.capacity}"
        )

    # =====================================================
    # QUERYSET OPTIMIZATION
    # =====================================================

    def get_queryset(self, request):
        """
        Optimize event administration queries.

        Active registrations are:

            - REGISTERED
            - ATTENDED

        Cancelled and absent registrations do not occupy
        event capacity.
        """

        return (
            super()
            .get_queryset(request)
            .select_related("organizer")
            .annotate(
                active_registration_count=Count(
                    "registrations",
                    filter=Q(
                        registrations__status__in=[
                            EventRegistration
                            .RegistrationStatus
                            .REGISTERED,

                            EventRegistration
                            .RegistrationStatus
                            .ATTENDED,
                        ]
                    ),
                    distinct=True,
                )
            )
        )

    # =====================================================
    # SAVE MODEL
    # =====================================================

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        """
        Automatically assign the logged-in user as the
        organizer when creating an event without one.
        """

        if not change and not obj.organizer_id:
            obj.organizer = request.user

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    # =====================================================
    # ADMIN ACTIONS
    # =====================================================

    actions = (
        "publish_events",
        "cancel_events",
        "complete_events",
    )

    # =====================================================
    # PUBLISH EVENTS
    # =====================================================

    @admin.action(
        description="Publish selected events",
    )
    def publish_events(
        self,
        request,
        queryset,
    ):
        """
        Publish valid future events.

        Cancelled and completed events are excluded.
        """

        now = timezone.now()

        valid_events = (
            queryset
            .filter(
                start_datetime__gt=now,
            )
            .exclude(
                status__in=[
                    Event.Status.CANCELLED,
                    Event.Status.COMPLETED,
                ]
            )
        )

        published_count = 0

        for event in valid_events:

            event.status = Event.Status.PUBLISHED

            if event.requires_registration:
                event.registration_status = (
                    Event.RegistrationStatus.OPEN
                )
            else:
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

            published_count += 1

        skipped_count = (
            queryset.count()
            - published_count
        )

        if published_count:
            self.message_user(
                request,
                (
                    f"{published_count} event(s) "
                    "published successfully."
                ),
                level=messages.SUCCESS,
            )

        if skipped_count:
            self.message_user(
                request,
                (
                    f"{skipped_count} event(s) were skipped "
                    "because they were cancelled, completed, "
                    "already started, or otherwise invalid."
                ),
                level=messages.WARNING,
            )

    # =====================================================
    # CANCEL EVENTS
    # =====================================================

    @admin.action(
        description="Cancel selected events",
    )
    def cancel_events(
        self,
        request,
        queryset,
    ):
        """
        Cancel selected events.

        Completed events cannot be cancelled.
        Registration is closed automatically.
        """

        valid_events = (
            queryset
            .exclude(
                status=Event.Status.COMPLETED,
            )
            .exclude(
                status=Event.Status.CANCELLED,
            )
        )

        cancelled_count = 0

        for event in valid_events:

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

            cancelled_count += 1

        skipped_count = (
            queryset.count()
            - cancelled_count
        )

        if cancelled_count:
            self.message_user(
                request,
                (
                    f"{cancelled_count} event(s) "
                    "cancelled successfully."
                ),
                level=messages.SUCCESS,
            )

        if skipped_count:
            self.message_user(
                request,
                (
                    f"{skipped_count} event(s) were skipped "
                    "because they were already cancelled "
                    "or completed."
                ),
                level=messages.WARNING,
            )

    # =====================================================
    # COMPLETE EVENTS
    # =====================================================

    @admin.action(
        description="Mark selected events as completed",
    )
    def complete_events(
        self,
        request,
        queryset,
    ):
        """
        Mark events as completed only after their end time.
        """

        now = timezone.now()

        valid_events = (
            queryset
            .filter(
                end_datetime__lte=now,
            )
            .exclude(
                status__in=[
                    Event.Status.CANCELLED,
                    Event.Status.COMPLETED,
                ]
            )
        )

        completed_count = 0

        for event in valid_events:

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

            completed_count += 1

        skipped_count = (
            queryset.count()
            - completed_count
        )

        if completed_count:
            self.message_user(
                request,
                (
                    f"{completed_count} event(s) "
                    "marked as completed."
                ),
                level=messages.SUCCESS,
            )

        if skipped_count:
            self.message_user(
                request,
                (
                    f"{skipped_count} event(s) were skipped "
                    "because they have not ended, are "
                    "cancelled, or are already completed."
                ),
                level=messages.WARNING,
            )


# =========================================================
# EVENT REGISTRATION ADMIN
# =========================================================


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    """
    KUCSA event registration administration.

    Provides:

        - Registration management
        - Attendance management
        - Cancellation management
        - Event/member search
        - Registration filtering
    """

    # =====================================================
    # LIST DISPLAY
    # =====================================================

    list_display = (
        "event",
        "user_display",
        "status_display",
        "registered_at",
        "attended_at",
        "cancelled_at",
    )

    # =====================================================
    # LIST FILTERS
    # =====================================================

    list_filter = (
        "status",
        "event__event_type",
        "event__status",
        "event__is_online",
        "registered_at",
        "attended_at",
        "cancelled_at",
    )

    # =====================================================
    # SEARCH
    # =====================================================

    search_fields = (
        "event__title",
        "event__slug",
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "user__registration_number",
    )

    # =====================================================
    # DATE HIERARCHY
    # =====================================================

    date_hierarchy = "registered_at"

    # =====================================================
    # AUTOCOMPLETE
    # =====================================================

    autocomplete_fields = (
        "event",
        "user",
    )

    # =====================================================
    # ORDERING
    # =====================================================

    ordering = (
        "-registered_at",
    )

    # =====================================================
    # PAGINATION
    # =====================================================

    list_per_page = 50

    # =====================================================
    # FIELDSETS
    # =====================================================

    fieldsets = (
        (
            "Registration",
            {
                "fields": (
                    "event",
                    "user",
                    "status",
                ),
            },
        ),
        (
            "Attendance",
            {
                "fields": (
                    "attended_at",
                    "cancelled_at",
                ),
            },
        ),
        (
            "Additional Information",
            {
                "fields": (
                    "notes",
                ),
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "registered_at",
                ),
            },
        ),
    )

    # =====================================================
    # READONLY FIELDS
    # =====================================================

    readonly_fields = (
        "registered_at",
        "cancelled_at",
        "attended_at",
    )

    # =====================================================
    # DISPLAY HELPERS
    # =====================================================

    @admin.display(
        description="User",
    )
    def user_display(self, obj):
        return (
            obj.user.get_full_name()
            or obj.user.username
        )

    @admin.display(
        description="Status",
        ordering="status",
    )
    def status_display(self, obj):
        return obj.get_status_display()

    # =====================================================
    # QUERYSET OPTIMIZATION
    # =====================================================

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "event",
                "user",
            )
        )

    # =====================================================
    # SAVE MODEL
    # =====================================================

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        """
        Allow the EventRegistration model to maintain
        attendance and cancellation timestamps.
        """

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    # =====================================================
    # ADMIN ACTIONS
    # =====================================================

    actions = (
        "mark_attended",
        "mark_absent",
        "cancel_registrations",
        "restore_registrations",
    )

    # =====================================================
    # MARK ATTENDED
    # =====================================================

    @admin.action(
        description="Mark selected registrations as attended",
    )
    def mark_attended(
        self,
        request,
        queryset,
    ):
        """
        Mark valid registrations as attended.

        Cancelled registrations and registrations belonging
        to cancelled events are excluded.
        """

        valid_registrations = (
            queryset
            .exclude(
                status=(
                    EventRegistration
                    .RegistrationStatus
                    .CANCELLED
                )
            )
            .exclude(
                event__status=Event.Status.CANCELLED,
            )
        )

        now = timezone.now()
        attended_count = 0

        for registration in valid_registrations:

            registration.status = (
                EventRegistration
                .RegistrationStatus
                .ATTENDED
            )

            registration.attended_at = now
            registration.cancelled_at = None

            registration.save(
                update_fields=[
                    "status",
                    "attended_at",
                    "cancelled_at",
                ]
            )

            attended_count += 1

        skipped_count = (
            queryset.count()
            - attended_count
        )

        if attended_count:
            self.message_user(
                request,
                (
                    f"{attended_count} registration(s) "
                    "marked as attended."
                ),
                level=messages.SUCCESS,
            )

        if skipped_count:
            self.message_user(
                request,
                (
                    f"{skipped_count} registration(s) "
                    "were skipped because they were "
                    "cancelled or belong to a cancelled event."
                ),
                level=messages.WARNING,
            )

    # =====================================================
    # MARK ABSENT
    # =====================================================

    @admin.action(
        description="Mark selected registrations as absent",
    )
    def mark_absent(
        self,
        request,
        queryset,
    ):
        """
        Mark active registrations as absent.

        Cancelled registrations remain cancelled.
        """

        valid_registrations = queryset.exclude(
            status=(
                EventRegistration
                .RegistrationStatus
                .CANCELLED
            )
        )

        absent_count = 0

        for registration in valid_registrations:

            registration.status = (
                EventRegistration
                .RegistrationStatus
                .ABSENT
            )

            registration.attended_at = None
            registration.cancelled_at = None

            registration.save(
                update_fields=[
                    "status",
                    "attended_at",
                    "cancelled_at",
                ]
            )

            absent_count += 1

        skipped_count = (
            queryset.count()
            - absent_count
        )

        if absent_count:
            self.message_user(
                request,
                (
                    f"{absent_count} registration(s) "
                    "marked as absent."
                ),
                level=messages.SUCCESS,
            )

        if skipped_count:
            self.message_user(
                request,
                (
                    f"{skipped_count} registration(s) "
                    "were skipped because they were "
                    "already cancelled."
                ),
                level=messages.WARNING,
            )

    # =====================================================
    # CANCEL REGISTRATIONS
    # =====================================================

    @admin.action(
        description="Cancel selected registrations",
    )
    def cancel_registrations(
        self,
        request,
        queryset,
    ):
        """
        Cancel active registrations.

        Attended registrations cannot be cancelled.
        """

        valid_registrations = (
            queryset
            .exclude(
                status=(
                    EventRegistration
                    .RegistrationStatus
                    .ATTENDED
                )
            )
            .exclude(
                status=(
                    EventRegistration
                    .RegistrationStatus
                    .CANCELLED
                )
            )
        )

        now = timezone.now()
        cancelled_count = 0

        for registration in valid_registrations:

            registration.status = (
                EventRegistration
                .RegistrationStatus
                .CANCELLED
            )

            registration.cancelled_at = now
            registration.attended_at = None

            registration.save(
                update_fields=[
                    "status",
                    "cancelled_at",
                    "attended_at",
                ]
            )

            cancelled_count += 1

        skipped_count = (
            queryset.count()
            - cancelled_count
        )

        if cancelled_count:
            self.message_user(
                request,
                (
                    f"{cancelled_count} registration(s) "
                    "cancelled successfully."
                ),
                level=messages.SUCCESS,
            )

        if skipped_count:
            self.message_user(
                request,
                (
                    f"{skipped_count} registration(s) "
                    "were skipped because they were "
                    "already cancelled or attended."
                ),
                level=messages.WARNING,
            )

    # =====================================================
    # RESTORE REGISTRATIONS
    # =====================================================

    @admin.action(
        description="Restore selected cancelled registrations",
    )
    def restore_registrations(
        self,
        request,
        queryset,
    ):
        """
        Restore cancelled registrations to REGISTERED.

        A registration can only be restored when:

            - It is currently cancelled.
            - The event is still open for registration.
            - The event has available capacity.
        """

        restored_count = 0
        skipped_count = 0

        for registration in queryset:

            event = registration.event

            # -------------------------------------------------
            # MUST BE CANCELLED
            # -------------------------------------------------

            if (
                registration.status
                != EventRegistration
                .RegistrationStatus
                .CANCELLED
            ):
                skipped_count += 1
                continue

            # -------------------------------------------------
            # EVENT MUST ACCEPT REGISTRATIONS
            # -------------------------------------------------

            if not event.registration_is_open:
                skipped_count += 1
                continue

            # -------------------------------------------------
            # CHECK CAPACITY
            # -------------------------------------------------

            if (
                event.capacity is not None
                and event.active_registration_count
                >= event.capacity
            ):
                skipped_count += 1
                continue

            # -------------------------------------------------
            # RESTORE
            # -------------------------------------------------

            registration.status = (
                EventRegistration
                .RegistrationStatus
                .REGISTERED
            )

            registration.cancelled_at = None
            registration.attended_at = None

            registration.save(
                update_fields=[
                    "status",
                    "cancelled_at",
                    "attended_at",
                ]
            )

            restored_count += 1

        if restored_count:
            self.message_user(
                request,
                (
                    f"{restored_count} registration(s) "
                    "restored successfully."
                ),
                level=messages.SUCCESS,
            )

        if skipped_count:
            self.message_user(
                request,
                (
                    f"{skipped_count} registration(s) "
                    "could not be restored because "
                    "registration is closed, the event is "
                    "full, or the registration was not cancelled."
                ),
                level=messages.WARNING,
            )