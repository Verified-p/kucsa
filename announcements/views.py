
# announcements/views.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    AnnouncementFilterForm,
    AnnouncementStatusForm,
    CreateAnnouncementForm,
    EditAnnouncementForm,
    PublishAnnouncementForm,
)
from .models import Announcement
from .services import (
    archive_announcement,
    can_manage_announcements,
    create_announcement,
    delete_announcement,
    expire_announcements,
    feature_announcement,
    get_announcement_statistics,
    get_announcements_for_user,
    get_featured_announcements,
    increment_view_count,
    publish_announcement,
    restore_announcement,
    unfeature_announcement,
    unpublish_announcement,
    update_announcement,
)


# =========================================================
# HELPER FUNCTIONS
# =========================================================


def _can_manage(user):
    """
    Centralized announcement-management permission check.
    """

    return can_manage_announcements(user)


def _member_queryset(user):
    """
    Return announcements visible to the logged-in member.

    Visibility and audience rules are handled by the service
    layer so that the same logic is reused throughout the app.
    """

    return get_announcements_for_user(user)


def _management_queryset():
    """
    Return the complete announcement queryset for
    administrators and executives.
    """

    return (
        Announcement.objects
        .select_related(
            "created_by",
            "updated_by",
        )
        .order_by(
            "-is_featured",
            "-published_at",
            "-created_at",
        )
    )


# =========================================================
# ANNOUNCEMENT LIST
# =========================================================


@login_required
def announcement_list(request):
    """
    Display announcements available to the current user.

    Members:
        - See only published announcements.
        - See only announcements targeted to them.
        - Cannot see drafts or archived announcements.

    Administrators/executives:
        - Can see all announcements.
        - Can filter by status.
        - Can manage announcements.
    """

    # -----------------------------------------------------
    # Expire old announcements first
    # -----------------------------------------------------

    expire_announcements()

    can_manage = _can_manage(request.user)

    # -----------------------------------------------------
    # Base queryset
    # -----------------------------------------------------

    if can_manage:
        queryset = _management_queryset()
    else:
        queryset = _member_queryset(request.user)

    # -----------------------------------------------------
    # Filter form
    # -----------------------------------------------------

    form = AnnouncementFilterForm(
        request.GET or None
    )

    if form.is_valid():

        search = form.cleaned_data.get("search")
        announcement_type = form.cleaned_data.get(
            "announcement_type"
        )
        priority = form.cleaned_data.get("priority")
        target_audience = form.cleaned_data.get(
            "target_audience"
        )
        status = form.cleaned_data.get("status")
        featured = form.cleaned_data.get("featured")

        # -------------------------------------------------
        # Search
        # -------------------------------------------------

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(summary__icontains=search)
                | Q(content__icontains=search)
            )

        # -------------------------------------------------
        # Announcement type
        # -------------------------------------------------

        if announcement_type:
            queryset = queryset.filter(
                announcement_type=announcement_type
            )

        # -------------------------------------------------
        # Priority
        # -------------------------------------------------

        if priority:
            queryset = queryset.filter(
                priority=priority
            )

        # -------------------------------------------------
        # Target audience
        # -------------------------------------------------

        if target_audience and can_manage:
            queryset = queryset.filter(
                target_audience=target_audience
            )

        # -------------------------------------------------
        # Status
        # -------------------------------------------------

        if status and can_manage:
            queryset = queryset.filter(
                status=status
            )

        # -------------------------------------------------
        # Featured
        # -------------------------------------------------

        if featured == "yes":
            queryset = queryset.filter(
                is_featured=True
            )

        elif featured == "no":
            queryset = queryset.filter(
                is_featured=False
            )

    # -----------------------------------------------------
    # Featured announcements
    # -----------------------------------------------------

    if can_manage:
        featured_queryset = get_featured_announcements(
            limit=5
        )
    else:
        featured_queryset = get_featured_announcements(
            limit=5,
            user=request.user,
        )

    # -----------------------------------------------------
    # Context
    # -----------------------------------------------------

    context = {
        "announcements": queryset,
        "form": form,
        "featured_announcements": featured_queryset,
        "can_manage": can_manage,
        "page_title": "Announcements",
    }

    # -----------------------------------------------------
    # Management statistics
    # -----------------------------------------------------

    if can_manage:
        context["statistics"] = (
            get_announcement_statistics()
        )

    return render(
        request,
        "announcement_list.html",
        context,
    )


# =========================================================
# ANNOUNCEMENT DETAIL
# =========================================================


@login_required
def announcement_detail(request, pk):
    """
    Display a single announcement.

    Members can only open announcements that are currently
    visible to them.

    Administrators/executives can also open drafts and
    archived announcements.
    """

    announcement = get_object_or_404(
        Announcement.objects.select_related(
            "created_by",
            "updated_by",
        ),
        pk=pk,
    )

    can_manage = _can_manage(request.user)

    # -----------------------------------------------------
    # Management users
    # -----------------------------------------------------

    if can_manage:
        increment_view_count(announcement)

    # -----------------------------------------------------
    # Normal members
    # -----------------------------------------------------

    else:

        if not announcement.is_active:
            raise Http404(
                "Announcement not found."
            )

        visible_queryset = _member_queryset(
            request.user
        )

        if not visible_queryset.filter(
            pk=announcement.pk
        ).exists():
            raise Http404(
                "Announcement not found."
            )

        increment_view_count(announcement)

    context = {
        "announcement": announcement,
        "can_manage": can_manage,
        "page_title": announcement.title,
    }

    return render(
        request,
        "announcement_detail.html",
        context,
    )


# =========================================================
# CREATE ANNOUNCEMENT
# =========================================================


@login_required
def create_announcement_view(request):
    """
    Create a new announcement.

    Only administrators and authorized executives
    can create announcements.
    """

    if not _can_manage(request.user):
        raise PermissionDenied(
            "You do not have permission to create announcements."
        )

    if request.method == "POST":

        form = CreateAnnouncementForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():

            try:
                announcement = create_announcement(
                    user=request.user,
                    **form.cleaned_data,
                )

                messages.success(
                    request,
                    (
                        f'Announcement "{announcement.title}" '
                        "was created successfully."
                    ),
                )

                return redirect(
                    "announcements:detail",
                    pk=announcement.pk,
                )

            except PermissionDenied:
                raise

            except ValidationError as exc:
                form.add_error(
                    None,
                    exc.message
                    if hasattr(exc, "message")
                    else str(exc),
                )

    else:
        form = CreateAnnouncementForm()

    context = {
        "form": form,
        "page_title": "Create Announcement",
        "page_heading": "Create Announcement",
    }

    return render(
        request,
        "create_announcement.html",
        context,
    )


# =========================================================
# EDIT ANNOUNCEMENT
# =========================================================


@login_required
def edit_announcement(request, pk):
    """
    Edit an existing announcement.

    Only administrators and authorized executives
    can edit announcements.
    """

    if not _can_manage(request.user):
        raise PermissionDenied(
            "You do not have permission to edit announcements."
        )

    announcement = get_object_or_404(
        Announcement,
        pk=pk,
    )

    if request.method == "POST":

        form = EditAnnouncementForm(
            request.POST,
            request.FILES,
            instance=announcement,
        )

        if form.is_valid():

            try:
                updated = update_announcement(
                    announcement=announcement,
                    user=request.user,
                    **form.cleaned_data,
                )

                messages.success(
                    request,
                    (
                        f'Announcement "{updated.title}" '
                        "was updated successfully."
                    ),
                )

                return redirect(
                    "announcements:detail",
                    pk=updated.pk,
                )

            except PermissionDenied:
                raise

            except ValidationError as exc:
                form.add_error(
                    None,
                    exc.message
                    if hasattr(exc, "message")
                    else str(exc),
                )

    else:

        form = EditAnnouncementForm(
            instance=announcement
        )

    context = {
        "form": form,
        "announcement": announcement,
        "page_title": "Edit Announcement",
        "page_heading": "Edit Announcement",
    }

    return render(
        request,
        "edit_announcement.html",
        context,
    )


# =========================================================
# PUBLISH ANNOUNCEMENT
# =========================================================


@login_required
@require_POST
def publish_announcement_view(request, pk):
    """
    Publish an announcement.

    Publishing makes the announcement visible to the
    appropriate members according to its target audience.
    """

    if not _can_manage(request.user):
        raise PermissionDenied(
            "You do not have permission to publish announcements."
        )

    announcement = get_object_or_404(
        Announcement,
        pk=pk,
    )

    form = PublishAnnouncementForm(
        request.POST
    )

    if not form.is_valid():

        messages.error(
            request,
            (
                "Unable to publish the announcement. "
                "Please correct the provided information."
            ),
        )

        return redirect(
            "announcements:detail",
            pk=pk,
        )

    try:

        # -------------------------------------------------
        # Publication information
        # -------------------------------------------------

        published_at = form.cleaned_data.get(
            "published_at"
        )

        expires_at = form.cleaned_data.get(
            "expires_at"
        )

        is_featured = form.cleaned_data.get(
            "is_featured",
            False,
        )

        announcement.published_at = published_at
        announcement.expires_at = expires_at
        announcement.is_featured = is_featured

        announcement.full_clean(
            exclude=["slug"]
        )

        announcement.save(
            update_fields=[
                "published_at",
                "expires_at",
                "is_featured",
                "updated_at",
            ]
        )

        # -------------------------------------------------
        # Publish through service layer
        # -------------------------------------------------

        publish_announcement(
            announcement=announcement,
            user=request.user,
        )

        messages.success(
            request,
            (
                f'Announcement "{announcement.title}" '
                "has been published successfully."
            ),
        )

    except PermissionDenied:
        raise

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "announcements:detail",
        pk=pk,
    )


# =========================================================
# UNPUBLISH ANNOUNCEMENT
# =========================================================


@login_required
@require_POST
def unpublish_announcement_view(request, pk):
    """
    Return a published announcement to draft status.
    """

    if not _can_manage(request.user):
        raise PermissionDenied(
            "You do not have permission to unpublish announcements."
        )

    announcement = get_object_or_404(
        Announcement,
        pk=pk,
    )

    try:

        unpublish_announcement(
            announcement=announcement,
            user=request.user,
        )

        messages.success(
            request,
            (
                f'Announcement "{announcement.title}" '
                "has been returned to draft."
            ),
        )

    except PermissionDenied:
        raise

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "announcements:detail",
        pk=pk,
    )


# =========================================================
# ARCHIVE ANNOUNCEMENT
# =========================================================


@login_required
@require_POST
def archive_announcement_view(request, pk):
    """
    Archive an announcement.
    """

    if not _can_manage(request.user):
        raise PermissionDenied(
            "You do not have permission to archive announcements."
        )

    announcement = get_object_or_404(
        Announcement,
        pk=pk,
    )

    try:

        archive_announcement(
            announcement=announcement,
            user=request.user,
        )

        messages.success(
            request,
            (
                f'Announcement "{announcement.title}" '
                "has been archived."
            ),
        )

    except PermissionDenied:
        raise

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "announcements:detail",
        pk=pk,
    )


# =========================================================
# RESTORE ANNOUNCEMENT
# =========================================================


@login_required
@require_POST
def restore_announcement_view(request, pk):
    """
    Restore an archived announcement to draft status.
    """

    if not _can_manage(request.user):
        raise PermissionDenied(
            "You do not have permission to restore announcements."
        )

    announcement = get_object_or_404(
        Announcement,
        pk=pk,
    )

    try:

        restore_announcement(
            announcement=announcement,
            user=request.user,
        )

        messages.success(
            request,
            (
                f'Announcement "{announcement.title}" '
                "has been restored as a draft."
            ),
        )

    except PermissionDenied:
        raise

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "announcements:detail",
        pk=pk,
    )


# =========================================================
# FEATURE ANNOUNCEMENT
# =========================================================


@login_required
@require_POST
def feature_announcement_view(request, pk):
    """
    Feature an announcement.

    Only published announcements should be featured.
    """

    if not _can_manage(request.user):
        raise PermissionDenied(
            "You do not have permission to feature announcements."
        )

    announcement = get_object_or_404(
        Announcement,
        pk=pk,
    )

    try:

        feature_announcement(
            announcement=announcement,
            user=request.user,
        )

        messages.success(
            request,
            (
                f'Announcement "{announcement.title}" '
                "is now featured."
            ),
        )

    except PermissionDenied:
        raise

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "announcements:detail",
        pk=pk,
    )


# =========================================================
# UNFEATURE ANNOUNCEMENT
# =========================================================


@login_required
@require_POST
def unfeature_announcement_view(request, pk):
    """
    Remove the featured status from an announcement.
    """

    if not _can_manage(request.user):
        raise PermissionDenied(
            "You do not have permission to manage featured announcements."
        )

    announcement = get_object_or_404(
        Announcement,
        pk=pk,
    )

    try:

        unfeature_announcement(
            announcement=announcement,
            user=request.user,
        )

        messages.success(
            request,
            (
                f'Announcement "{announcement.title}" '
                "is no longer featured."
            ),
        )

    except PermissionDenied:
        raise

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "announcements:detail",
        pk=pk,
    )


# =========================================================
# DELETE ANNOUNCEMENT
# =========================================================


@login_required
@require_POST
def delete_announcement_view(request, pk):
    """
    Permanently delete an announcement.

    The service layer is responsible for enforcing the
    stricter administrator-only deletion rule.
    """

    announcement = get_object_or_404(
        Announcement,
        pk=pk,
    )

    title = announcement.title

    try:

        delete_announcement(
            announcement=announcement,
            user=request.user,
        )

        messages.success(
            request,
            (
                f'Announcement "{title}" '
                "was permanently deleted."
            ),
        )

    except PermissionDenied:
        raise

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

        return redirect(
            "announcements:detail",
            pk=pk,
        )

    return redirect(
        "announcements:list"
    )


# =========================================================
# CHANGE ANNOUNCEMENT STATUS
# =========================================================


@login_required
@require_POST
def change_announcement_status(request, pk):
    """
    Centralized announcement status transition endpoint.
    """

    if not _can_manage(request.user):
        raise PermissionDenied(
            "You do not have permission to change announcement status."
        )

    announcement = get_object_or_404(
        Announcement,
        pk=pk,
    )

    form = AnnouncementStatusForm(
        request.POST
    )

    if not form.is_valid():

        messages.error(
            request,
            "Invalid announcement status.",
        )

        return redirect(
            "announcements:detail",
            pk=pk,
        )

    status = form.cleaned_data["status"]

    try:

        if status == Announcement.Status.PUBLISHED:

            publish_announcement(
                announcement=announcement,
                user=request.user,
            )

        elif status == Announcement.Status.DRAFT:

            unpublish_announcement(
                announcement=announcement,
                user=request.user,
            )

        elif status == Announcement.Status.ARCHIVED:

            archive_announcement(
                announcement=announcement,
                user=request.user,
            )

        else:

            raise ValidationError(
                "Unsupported announcement status."
            )

        messages.success(
            request,
            "Announcement status updated successfully.",
        )

    except PermissionDenied:
        raise

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "announcements:detail",
        pk=pk,
    )


# =========================================================
# EXECUTIVE / ADMIN MANAGEMENT
# =========================================================


@login_required
def announcement_management(request):
    """
    Executive/admin announcement management dashboard.

    Shows all announcements regardless of publication status.
    """

    if not _can_manage(request.user):
        raise PermissionDenied(
            "You do not have permission to manage announcements."
        )

    expire_announcements()

    announcements = _management_queryset()

    context = {
        "announcements": announcements,
        "statistics": get_announcement_statistics(),
        "can_manage": True,
        "page_title": "Announcement Management",
    }

    return render(
        request,
        "announcement_list.html",
        context,
    )


# =========================================================
# RECENT ANNOUNCEMENTS
# =========================================================


@login_required
def recent_announcements(request):
    """
    Display the most recent announcements available to
    the current member.

    Useful for dashboard widgets and notification-style feeds.
    """

    expire_announcements()

    announcements = _member_queryset(
        request.user
    )[:10]

    context = {
        "announcements": announcements,
        "page_title": "Recent Announcements",
        "can_manage": _can_manage(request.user),
    }

    return render(
        request,
        "announcement_list.html",
        context,
    )


# =========================================================
# FEATURED ANNOUNCEMENTS
# =========================================================


@login_required
def featured_announcements(request):
    """
    Display featured announcements visible to the user.
    """

    expire_announcements()

    if _can_manage(request.user):

        announcements = get_featured_announcements(
            limit=None
        )

    else:

        announcements = get_featured_announcements(
            limit=None,
            user=request.user,
        )

    context = {
        "announcements": announcements,
        "page_title": "Featured Announcements",
        "can_manage": _can_manage(request.user),
    }

    return render(
        request,
        "announcement_list.html",
        context,
    )


# =========================================================
# EXPIRE ANNOUNCEMENTS
# =========================================================


@login_required
@require_POST
def expire_announcements_view(request):
    """
    Manually expire announcements.

    Intended for administrators and authorized executives.
    """

    if not _can_manage(request.user):
        raise PermissionDenied(
            "You do not have permission to expire announcements."
        )

    count = expire_announcements()

    if count:

        messages.success(
            request,
            (
                f"{count} announcement(s) "
                "were expired and archived."
            ),
        )

    else:

        messages.info(
            request,
            "There are no announcements that need to be expired.",
        )

    return redirect(
        "announcements:list"
    )

