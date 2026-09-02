# events/views.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import EventForm, EventRegistrationForm
from .models import Event, EventRegistration


# =========================================================
# PERMISSION HELPERS
# =========================================================


def is_admin(user):
    """
    Return True when the authenticated user is a KUCSA
    administrator or Django superuser/staff user.
    """

    if not user or not user.is_authenticated:
        return False

    return (
        user.is_superuser
        or user.is_staff
        or getattr(user, "role", None) == "ADMIN"
    )


def is_executive(user):
    """
    Return True when the authenticated user is a KUCSA
    executive or administrator.
    """

    if not user or not user.is_authenticated:
        return False

    if is_admin(user):
        return True

    return bool(
        getattr(user, "is_executive", False)
    )


def can_manage_events(user):
    """
    Return True when the authenticated user can manage
    KUCSA events and event registrations.
    """

    return is_executive(user)


# =========================================================
# EVENT VISIBILITY HELPERS
# =========================================================


def public_event_statuses():
    """
    Event statuses that ordinary authenticated members
    are allowed to see.

    Draft events remain private because they may still be
    under preparation by executives/admins.

    Cancelled and completed events remain visible so members
    can still see the event history and cancellation status.
    """

    return (
        Event.Status.PUBLISHED,
        Event.Status.ONGOING,
        Event.Status.COMPLETED,
        Event.Status.CANCELLED,
    )


def can_view_event(user, event):
    """
    Determine whether a user can view a particular event.

    Executives/admins:
        - Can view every event, including drafts.

    Members:
        - Can view every non-draft event.
    """

    if can_manage_events(user):
        return True

    return event.status in public_event_statuses()


# =========================================================
# EVENT LIST
# =========================================================


@login_required
def event_list(request):
    """
    Display KUCSA events.

    Students/members:
        - See all public events.
        - Draft events remain hidden.

    Executives/admins:
        - See all events, including drafts.
        - Can filter by status.

    Supported filters:
        - Search
        - Event type
        - Status
        - Registration status
        - Featured
        - Upcoming
        - Online
    """

    can_manage = can_manage_events(request.user)

    now = timezone.now()

    # -----------------------------------------------------
    # BASE QUERYSET
    # -----------------------------------------------------

    events = (
        Event.objects
        .select_related("organizer")
        .annotate(
            total_registrations=Count(
                "registrations",
                filter=Q(
                    registrations__status__in=[
                        EventRegistration.RegistrationStatus.REGISTERED,
                        EventRegistration.RegistrationStatus.ATTENDED,
                    ]
                ),
                distinct=True,
            ),
            total_attendees=Count(
                "registrations",
                filter=Q(
                    registrations__status=(
                        EventRegistration
                        .RegistrationStatus
                        .ATTENDED
                    )
                ),
                distinct=True,
            ),
        )
    )

    # -----------------------------------------------------
    # FILTER VALUES
    # -----------------------------------------------------

    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    event_type = request.GET.get(
        "event_type",
        "",
    ).strip()

    status = request.GET.get(
        "status",
        "",
    ).strip()

    registration_status = request.GET.get(
        "registration_status",
        "",
    ).strip()

    featured = request.GET.get(
        "featured",
        "",
    ).strip()

    upcoming = request.GET.get(
        "upcoming",
        "",
    ).strip()

    online = request.GET.get(
        "online",
        "",
    ).strip()

    # =====================================================
    # MEMBER VISIBILITY
    # =====================================================

    if not can_manage:
        events = events.filter(
            status__in=public_event_statuses()
        )

    # =====================================================
    # SEARCH
    # =====================================================

    if search_query:
        events = events.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(venue__icontains=search_query)
            | Q(location_details__icontains=search_query)
            | Q(target_audience__icontains=search_query)
            | Q(requirements__icontains=search_query)
            | Q(event_type__icontains=search_query)
        )

    # =====================================================
    # EVENT TYPE
    # =====================================================

    if event_type:
        valid_event_types = {
            value
            for value, _label in Event.EventType.choices
        }

        if event_type in valid_event_types:
            events = events.filter(
                event_type=event_type
            )

    # =====================================================
    # EVENT STATUS
    # =====================================================

    if status:
        valid_statuses = {
            value
            for value, _label in Event.Status.choices
        }

        if status in valid_statuses:

            # Members must never be able to expose drafts
            # through a URL query parameter.
            if can_manage:
                events = events.filter(
                    status=status
                )
            elif status in public_event_statuses():
                events = events.filter(
                    status=status
                )

    # =====================================================
    # REGISTRATION STATUS
    # =====================================================

    if registration_status:

        valid_registration_statuses = {
            value
            for value, _label
            in Event.RegistrationStatus.choices
        }

        if registration_status in valid_registration_statuses:
            events = events.filter(
                registration_status=registration_status
            )

    # =====================================================
    # FEATURED
    # =====================================================

    if featured == "1":
        events = events.filter(
            is_featured=True
        )

    # =====================================================
    # UPCOMING
    # =====================================================

    if upcoming == "1":
        events = events.filter(
            start_datetime__gt=now
        )

    # =====================================================
    # ONLINE
    # =====================================================

    if online == "1":
        events = events.filter(
            is_online=True
        )

    # =====================================================
    # ORDERING
    # =====================================================

    events = events.order_by(
        "start_datetime",
        "title",
    )

    # =====================================================
    # CONTEXT
    # =====================================================

    context = {
        "events": events,

        "can_manage_events": can_manage,

        "is_executive": is_executive(request.user),

        "is_admin": is_admin(request.user),

        "search_query": search_query,

        "selected_event_type": event_type,

        "selected_status": status,

        "selected_registration_status": registration_status,

        "featured": featured,

        "upcoming": upcoming,

        "online": online,

        "event_types": Event.EventType.choices,

        "event_statuses": Event.Status.choices,

        "registration_statuses": (
            Event.RegistrationStatus.choices
        ),

        "public_event_statuses": public_event_statuses(),
    }

    return render(
        request,
        "event_list.html",
        context,
    )


# =========================================================
# EVENT DETAIL
# =========================================================


@login_required
def event_detail(request, pk):
    """
    Display complete information about an event.

    Students:
        - Can view public events.
        - Can see their own registration.
        - Can register where permitted.

    Executives/admins:
        - Can view all events.
        - Can see registrations.
        - Can manage attendance.
        - Can manage event status.
    """

    can_manage = can_manage_events(
        request.user
    )

    event = get_object_or_404(
        Event.objects
        .select_related("organizer")
        .prefetch_related(
            Prefetch(
                "registrations",
                queryset=(
                    EventRegistration.objects
                    .select_related("user")
                    .order_by(
                        "status",
                        "registered_at",
                    )
                ),
            )
        ),
        pk=pk,
    )

    # =====================================================
    # VISIBILITY
    # =====================================================

    if not can_view_event(
        request.user,
        event,
    ):
        messages.error(
            request,
            "This event is not currently available.",
        )

        return redirect(
            "events:list"
        )

    # =====================================================
    # CURRENT USER REGISTRATION
    # =====================================================

    registration = (
        EventRegistration.objects
        .filter(
            event=event,
            user=request.user,
        )
        .first()
    )

    # =====================================================
    # REGISTRATION FORM
    # =====================================================

    registration_form = EventRegistrationForm(
        event=event,
        user=request.user,
    )

    # =====================================================
    # MANAGEMENT DATA
    # =====================================================

    if can_manage:

        registrations = (
            EventRegistration.objects
            .select_related(
                "user",
                "event",
            )
            .filter(
                event=event
            )
            .order_by(
                "status",
                "registered_at",
            )
        )

        registered_count = registrations.filter(
            status=(
                EventRegistration
                .RegistrationStatus
                .REGISTERED
            )
        ).count()

        attended_count = registrations.filter(
            status=(
                EventRegistration
                .RegistrationStatus
                .ATTENDED
            )
        ).count()

        absent_count = registrations.filter(
            status=(
                EventRegistration
                .RegistrationStatus
                .ABSENT
            )
        ).count()

        cancelled_count = registrations.filter(
            status=(
                EventRegistration
                .RegistrationStatus
                .CANCELLED
            )
        ).count()

    else:

        registrations = EventRegistration.objects.none()

        registered_count = event.registration_count

        attended_count = 0

        absent_count = 0

        cancelled_count = 0

    # =====================================================
    # CONTEXT
    # =====================================================

    context = {
        "event": event,

        "registration": registration,

        "registration_form": registration_form,

        "can_manage_events": can_manage,

        "is_executive": is_executive(request.user),

        "is_admin": is_admin(request.user),

        "registrations": registrations,

        "registered_count": registered_count,

        "attended_count": attended_count,

        "absent_count": absent_count,

        "cancelled_count": cancelled_count,

        "registration_is_open": (
            event.registration_is_open
        ),

        "available_slots": event.available_slots,

        "is_full": event.is_full,

        "attendance_rate": event.attendance_rate,
    }

    return render(
        request,
        "event_detail.html",
        context,
    )


# =========================================================
# CREATE EVENT
# =========================================================


@login_required
@transaction.atomic
def create_event(request):
    """
    Create a new KUCSA event.

    Only executives and administrators can create events.
    """

    if not can_manage_events(request.user):

        messages.error(
            request,
            "You do not have permission to create events.",
        )

        return redirect(
            "events:list"
        )

    if request.method == "POST":

        form = EventForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():

            event = form.save(
                commit=False
            )

            event.organizer = request.user

            event.save()

            messages.success(
                request,
                f'"{event.title}" was created successfully.',
            )

            return redirect(
                "events:detail",
                pk=event.pk,
            )

    else:

        form = EventForm()

    context = {
        "form": form,
        "page_title": "Create Event",
        "can_manage_events": True,
    }

    return render(
        request,
        "create_event.html",
        context,
    )


# =========================================================
# UPDATE EVENT
# =========================================================


@login_required
@transaction.atomic
def update_event(request, pk):
    """
    Update an existing KUCSA event.

    Only executives and administrators can edit events.
    """

    if not can_manage_events(request.user):

        messages.error(
            request,
            "You do not have permission to edit events.",
        )

        return redirect(
            "events:list"
        )

    event = get_object_or_404(
        Event,
        pk=pk,
    )

    if request.method == "POST":

        form = EventForm(
            request.POST,
            request.FILES,
            instance=event,
        )

        if form.is_valid():

            updated_event = form.save(
                commit=False
            )

            # Preserve organizer unless it was explicitly
            # removed and the current user is creating the
            # organizer relationship.
            if not updated_event.organizer_id:
                updated_event.organizer = (
                    event.organizer
                    or request.user
                )

            updated_event.save()

            messages.success(
                request,
                (
                    f'"{updated_event.title}" '
                    "was updated successfully."
                ),
            )

            return redirect(
                "events:detail",
                pk=updated_event.pk,
            )

    else:

        form = EventForm(
            instance=event,
        )

    context = {
        "form": form,

        "event": event,

        "page_title": "Update Event",

        "can_manage_events": True,
    }

    return render(
        request,
        "update_event.html",
        context,
    )


# =========================================================
# REGISTER FOR EVENT
# =========================================================


@login_required
@transaction.atomic
def event_registration(request, pk):
    """
    Register the authenticated user for an event.

    Handles:
        - Registration availability
        - Capacity
        - Duplicate registration
        - Re-registration after cancellation
        - Registration notes
    """

    if request.method != "POST":

        return redirect(
            "events:detail",
            pk=pk,
        )

    # =====================================================
    # LOCK EVENT
    # =====================================================

    event = get_object_or_404(
        Event.objects.select_for_update(),
        pk=pk,
    )

    # =====================================================
    # REGISTRATION AVAILABILITY
    # =====================================================

    if not event.registration_is_open:

        messages.error(
            request,
            "Registration for this event is currently closed.",
        )

        return redirect(
            "events:detail",
            pk=event.pk,
        )

    # =====================================================
    # EXISTING REGISTRATION
    # =====================================================

    existing = (
        EventRegistration.objects
        .select_for_update()
        .filter(
            event=event,
            user=request.user,
        )
        .first()
    )

    if existing:

        # -------------------------------------------------
        # CANCELLED → REGISTER AGAIN
        # -------------------------------------------------

        if (
            existing.status
            == EventRegistration
            .RegistrationStatus
            .CANCELLED
        ):

            if event.is_full:

                messages.error(
                    request,
                    "This event is now full.",
                )

                return redirect(
                    "events:detail",
                    pk=event.pk,
                )

            form = EventRegistrationForm(
                request.POST,
                instance=existing,
                event=event,
                user=request.user,
            )

            if not form.is_valid():

                return render(
                    request,
                    "event_registration.html",
                    {
                        "event": event,
                        "form": form,
                    },
                )

            registration = form.save(
                commit=False
            )

            registration.event = event

            registration.user = request.user

            registration.status = (
                EventRegistration
                .RegistrationStatus
                .REGISTERED
            )

            registration.cancelled_at = None
            registration.attended_at = None

            registration.save()

            messages.success(
                request,
                "You have successfully registered again.",
            )

            return redirect(
                "events:my_events"
            )

        # -------------------------------------------------
        # ALREADY REGISTERED / ATTENDED / ABSENT
        # -------------------------------------------------

        messages.info(
            request,
            "You already have a registration for this event.",
        )

        return redirect(
            "events:detail",
            pk=event.pk,
        )

    # =====================================================
    # REGISTRATION FORM
    # =====================================================

    form = EventRegistrationForm(
        request.POST,
        event=event,
        user=request.user,
    )

    if not form.is_valid():

        return render(
            request,
            "event_registration.html",
            {
                "event": event,
                "form": form,
            },
        )

    # =====================================================
    # CREATE REGISTRATION
    # =====================================================

    registration = form.save(
        commit=False
    )

    registration.event = event

    registration.user = request.user

    registration.status = (
        EventRegistration
        .RegistrationStatus
        .REGISTERED
    )

    try:

        registration.save()

    except IntegrityError:

        messages.error(
            request,
            "You are already registered for this event.",
        )

        return redirect(
            "events:detail",
            pk=event.pk,
        )

    messages.success(
        request,
        (
            f'You have successfully registered for '
            f'"{event.title}".'
        ),
    )

    return redirect(
        "events:my_events"
    )


# =========================================================
# CANCEL EVENT REGISTRATION
# =========================================================


@login_required
@transaction.atomic
def cancel_registration(request, pk):
    """
    Cancel the authenticated user's event registration.

    Only active registrations can be cancelled.
    """

    if request.method != "POST":

        return redirect(
            "events:detail",
            pk=pk,
        )

    event = get_object_or_404(
        Event,
        pk=pk,
    )

    registration = get_object_or_404(
        EventRegistration,
        event=event,
        user=request.user,
    )

    # =====================================================
    # ALREADY CANCELLED
    # =====================================================

    if (
        registration.status
        == EventRegistration
        .RegistrationStatus
        .CANCELLED
    ):

        messages.info(
            request,
            "Your registration is already cancelled.",
        )

        return redirect(
            "events:my_events"
        )

    # =====================================================
    # ATTENDED
    # =====================================================

    if (
        registration.status
        == EventRegistration
        .RegistrationStatus
        .ATTENDED
    ):

        messages.error(
            request,
            "An attendance record cannot be cancelled.",
        )

        return redirect(
            "events:detail",
            pk=event.pk,
        )

    # =====================================================
    # CANCEL REGISTRATION
    # =====================================================

    registration.status = (
        EventRegistration
        .RegistrationStatus
        .CANCELLED
    )

    registration.cancelled_at = timezone.now()

    registration.attended_at = None

    registration.save(
        update_fields=[
            "status",
            "cancelled_at",
            "attended_at",
        ]
    )

    messages.success(
        request,
        "Your event registration has been cancelled.",
    )

    return redirect(
        "events:my_events"
    )


# =========================================================
# MY EVENTS
# =========================================================


@login_required
def my_events(request):
    """
    Display the authenticated user's event registrations.

    Sections:
        - Upcoming registrations
        - Past events
        - Cancelled registrations
    """

    registrations = (
        EventRegistration.objects
        .select_related(
            "event",
            "event__organizer",
        )
        .filter(
            user=request.user
        )
        .order_by(
            "-registered_at"
        )
    )

    now = timezone.now()

    # =====================================================
    # UPCOMING EVENTS
    # =====================================================

    upcoming_events = registrations.filter(
        event__start_datetime__gt=now,
        status=(
            EventRegistration
            .RegistrationStatus
            .REGISTERED
        ),
    )

    # =====================================================
    # PAST EVENTS
    # =====================================================

    past_events = (
        registrations
        .filter(
            event__end_datetime__lte=now,
        )
        .exclude(
            status=(
                EventRegistration
                .RegistrationStatus
                .CANCELLED
            )
        )
    )

    # =====================================================
    # CANCELLED EVENTS
    # =====================================================

    cancelled_events = registrations.filter(
        status=(
            EventRegistration
            .RegistrationStatus
            .CANCELLED
        )
    )

    # =====================================================
    # CONTEXT
    # =====================================================

    context = {
        "registrations": registrations,

        "upcoming_events": upcoming_events,

        "past_events": past_events,

        "cancelled_events": cancelled_events,

        "upcoming_count": upcoming_events.count(),

        "past_count": past_events.count(),

        "cancelled_count": cancelled_events.count(),
    }

    return render(
        request,
        "my_events.html",
        context,
    )


# =========================================================
# PUBLISH EVENT
# =========================================================


@login_required
@transaction.atomic
def publish_event(request, pk):
    """
    Publish a draft event.

    Publishing:
        - Makes the event visible to members.
        - Opens registration when required.
    """

    if not can_manage_events(request.user):

        messages.error(
            request,
            "You do not have permission to publish events.",
        )

        return redirect(
            "events:list"
        )

    if request.method != "POST":

        return redirect(
            "events:detail",
            pk=pk,
        )

    event = get_object_or_404(
        Event,
        pk=pk,
    )

    # =====================================================
    # VALIDATION
    # =====================================================

    if event.status == Event.Status.CANCELLED:

        messages.error(
            request,
            "A cancelled event cannot be published.",
        )

        return redirect(
            "events:detail",
            pk=event.pk,
        )

    if event.status == Event.Status.COMPLETED:

        messages.error(
            request,
            "A completed event cannot be published.",
        )

        return redirect(
            "events:detail",
            pk=event.pk,
        )

    if event.start_datetime <= timezone.now():

        messages.error(
            request,
            "An event cannot be published after its start time.",
        )

        return redirect(
            "events:detail",
            pk=event.pk,
        )

    # =====================================================
    # PUBLISH
    # =====================================================

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

    messages.success(
        request,
        f'"{event.title}" has been published.',
    )

    return redirect(
        "events:detail",
        pk=event.pk,
    )


# =========================================================
# CANCEL EVENT
# =========================================================


@login_required
@transaction.atomic
def cancel_event(request, pk):
    """
    Cancel a KUCSA event.

    Cancelling:
        - Changes event status to CANCELLED.
        - Closes registration.
    """

    if not can_manage_events(request.user):

        messages.error(
            request,
            "You do not have permission to cancel events.",
        )

        return redirect(
            "events:list"
        )

    if request.method != "POST":

        return redirect(
            "events:detail",
            pk=pk,
        )

    event = get_object_or_404(
        Event,
        pk=pk,
    )

    if event.status == Event.Status.COMPLETED:

        messages.error(
            request,
            "A completed event cannot be cancelled.",
        )

        return redirect(
            "events:detail",
            pk=event.pk,
        )

    if event.status == Event.Status.CANCELLED:

        messages.info(
            request,
            "This event is already cancelled.",
        )

        return redirect(
            "events:detail",
            pk=event.pk,
        )

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

    messages.success(
        request,
        f'"{event.title}" has been cancelled.',
    )

    return redirect(
        "events:detail",
        pk=event.pk,
    )


# =========================================================
# COMPLETE EVENT
# =========================================================


@login_required
@transaction.atomic
def complete_event(request, pk):
    """
    Mark an event as completed.

    The event must have reached its end time.
    """

    if not can_manage_events(request.user):

        messages.error(
            request,
            "You do not have permission to complete events.",
        )

        return redirect(
            "events:list"
        )

    if request.method != "POST":

        return redirect(
            "events:detail",
            pk=pk,
        )

    event = get_object_or_404(
        Event,
        pk=pk,
    )

    # =====================================================
    # VALIDATION
    # =====================================================

    if event.status == Event.Status.CANCELLED:

        messages.error(
            request,
            "A cancelled event cannot be marked as completed.",
        )

        return redirect(
            "events:detail",
            pk=event.pk,
        )

    if event.status == Event.Status.COMPLETED:

        messages.info(
            request,
            "This event is already marked as completed.",
        )

        return redirect(
            "events:detail",
            pk=event.pk,
        )

    if event.end_datetime > timezone.now():

        messages.error(
            request,
            "An event can only be completed after its end time.",
        )

        return redirect(
            "events:detail",
            pk=event.pk,
        )

    # =====================================================
    # COMPLETE EVENT
    # =====================================================

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

    messages.success(
        request,
        f'"{event.title}" has been marked as completed.',
    )

    return redirect(
        "events:detail",
        pk=event.pk,
    )


# =========================================================
# MARK ATTENDANCE
# =========================================================


@login_required
@transaction.atomic
def update_attendance(request, registration_id):
    """
    Allow executives/admins to mark a registration as:

        - Attended
        - Absent

    Attendance cannot be recorded for cancelled
    registrations.
    """

    if not can_manage_events(request.user):

        messages.error(
            request,
            "You do not have permission to manage attendance.",
        )

        return redirect(
            "events:list"
        )

    if request.method != "POST":

        return redirect(
            "events:list"
        )

    registration = get_object_or_404(
        EventRegistration.objects.select_related(
            "event",
            "user",
        ),
        pk=registration_id,
    )

    attendance_status = request.POST.get(
        "attendance_status",
        "",
    ).strip()

    valid_statuses = {
        EventRegistration.RegistrationStatus.ATTENDED,
        EventRegistration.RegistrationStatus.ABSENT,
    }

    if attendance_status not in valid_statuses:

        messages.error(
            request,
            "Invalid attendance status.",
        )

        return redirect(
            "events:detail",
            pk=registration.event.pk,
        )

    # =====================================================
    # CANCELLED REGISTRATION
    # =====================================================

    if (
        registration.status
        == EventRegistration
        .RegistrationStatus
        .CANCELLED
    ):

        messages.error(
            request,
            "A cancelled registration cannot be marked for attendance.",
        )

        return redirect(
            "events:detail",
            pk=registration.event.pk,
        )

    # =====================================================
    # EVENT VALIDATION
    # =====================================================

    if registration.event.status == Event.Status.CANCELLED:

        messages.error(
            request,
            "Attendance cannot be recorded for a cancelled event.",
        )

        return redirect(
            "events:detail",
            pk=registration.event.pk,
        )

    # =====================================================
    # ATTENDED
    # =====================================================

    if (
        attendance_status
        == EventRegistration
        .RegistrationStatus
        .ATTENDED
    ):

        registration.status = (
            EventRegistration
            .RegistrationStatus
            .ATTENDED
        )

        registration.attended_at = timezone.now()

        registration.cancelled_at = None

        registration.save(
            update_fields=[
                "status",
                "attended_at",
                "cancelled_at",
            ]
        )

        messages.success(
            request,
            "Attendee marked as present.",
        )

    # =====================================================
    # ABSENT
    # =====================================================

    else:

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

        messages.success(
            request,
            "Attendee marked as absent.",
        )

    return redirect(
        "events:detail",
        pk=registration.event.pk,
    )