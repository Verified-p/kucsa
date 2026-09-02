
# announcements/services.py

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from .models import Announcement


# =========================================================
# PERMISSION HELPERS
# =========================================================


def is_admin(user):
    """
    Return True when the authenticated user is a system administrator.
    """

    return bool(
        user
        and user.is_authenticated
        and (
            getattr(user, "is_superuser", False)
            or getattr(user, "role", None) == "ADMIN"
        )
    )


def is_executive(user):
    """
    Return True when the user is a KUCSA executive.
    """

    return bool(
        user
        and user.is_authenticated
        and getattr(user, "is_executive", False)
    )


def can_manage_announcements(user):
    """
    Return True when the user can create or manage announcements.
    """

    return is_admin(user) or is_executive(user)


def require_management_permission(user):
    """
    Ensure that the user has announcement-management permission.
    """

    if not can_manage_announcements(user):
        raise PermissionDenied(
            "You do not have permission to manage announcements."
        )


# =========================================================
# ANNOUNCEMENT CREATION
# =========================================================


@transaction.atomic
def create_announcement(
    *,
    user,
    title,
    content,
    announcement_type=Announcement.AnnouncementType.GENERAL,
    priority=Announcement.Priority.NORMAL,
    target_audience=Announcement.TargetAudience.ALL,
    summary="",
    status=Announcement.Status.DRAFT,
    published_at=None,
    expires_at=None,
    image=None,
    attachment=None,
    is_featured=False,
    allow_comments=False,
):
    """
    Create a new KUCSA announcement.
    """

    require_management_permission(user)

    now = timezone.now()

    if status == Announcement.Status.PUBLISHED:
        if not published_at:
            published_at = now

    if status != Announcement.Status.PUBLISHED:
        is_featured = False

    announcement = Announcement(
        title=title,
        summary=summary,
        content=content,
        announcement_type=announcement_type,
        priority=priority,
        target_audience=target_audience,
        status=status,
        published_at=published_at,
        expires_at=expires_at,
        image=image,
        attachment=attachment,
        is_featured=is_featured,
        allow_comments=allow_comments,
        created_by=user,
        updated_by=user,
    )

    announcement.full_clean()
    announcement.save()

    return announcement


# =========================================================
# ANNOUNCEMENT UPDATE
# =========================================================


@transaction.atomic
def update_announcement(
    *,
    announcement,
    user,
    **changes,
):
    """
    Update an existing announcement.

    System-managed fields cannot be changed through this service.
    """

    require_management_permission(user)

    if not announcement:
        raise ValidationError(
            "Announcement does not exist."
        )

    protected_fields = {
        "id",
        "pk",
        "created_by",
        "created_at",
        "updated_at",
        "view_count",
        "slug",
    }

    for field, value in changes.items():

        if field in protected_fields:
            continue

        if hasattr(announcement, field):
            setattr(
                announcement,
                field,
                value,
            )

    if announcement.status == Announcement.Status.PUBLISHED:

        if not announcement.published_at:
            announcement.published_at = timezone.now()

    if announcement.status != Announcement.Status.PUBLISHED:
        announcement.is_featured = False

    announcement.updated_by = user

    announcement.full_clean()
    announcement.save()

    return announcement


# =========================================================
# PUBLISH ANNOUNCEMENT
# =========================================================


@transaction.atomic
def publish_announcement(
    *,
    announcement,
    user,
):
    """
    Publish an announcement.
    """

    require_management_permission(user)

    if not announcement:
        raise ValidationError(
            "Announcement does not exist."
        )

    now = timezone.now()

    if announcement.status == Announcement.Status.PUBLISHED:

        if not announcement.published_at:
            announcement.published_at = now
            announcement.updated_by = user

            announcement.full_clean()

            announcement.save(
                update_fields=[
                    "published_at",
                    "updated_by",
                    "updated_at",
                ]
            )

        return announcement

    if not announcement.published_at:
        announcement.published_at = now

    announcement.status = Announcement.Status.PUBLISHED
    announcement.updated_by = user

    announcement.full_clean()

    announcement.save(
        update_fields=[
            "status",
            "published_at",
            "updated_by",
            "updated_at",
        ]
    )

    return announcement


# =========================================================
# UNPUBLISH ANNOUNCEMENT
# =========================================================


@transaction.atomic
def unpublish_announcement(
    *,
    announcement,
    user,
):
    """
    Return an announcement to draft status.
    """

    require_management_permission(user)

    if not announcement:
        raise ValidationError(
            "Announcement does not exist."
        )

    announcement.status = Announcement.Status.DRAFT
    announcement.is_featured = False
    announcement.updated_by = user

    announcement.full_clean()

    announcement.save(
        update_fields=[
            "status",
            "is_featured",
            "updated_by",
            "updated_at",
        ]
    )

    return announcement


# =========================================================
# ARCHIVE ANNOUNCEMENT
# =========================================================


@transaction.atomic
def archive_announcement(
    *,
    announcement,
    user,
):
    """
    Archive an announcement.
    """

    require_management_permission(user)

    if not announcement:
        raise ValidationError(
            "Announcement does not exist."
        )

    announcement.status = Announcement.Status.ARCHIVED
    announcement.is_featured = False
    announcement.updated_by = user

    announcement.full_clean()

    announcement.save(
        update_fields=[
            "status",
            "is_featured",
            "updated_by",
            "updated_at",
        ]
    )

    return announcement


# =========================================================
# RESTORE ANNOUNCEMENT
# =========================================================


@transaction.atomic
def restore_announcement(
    *,
    announcement,
    user,
):
    """
    Restore an archived announcement as a draft.
    """

    require_management_permission(user)

    if not announcement:
        raise ValidationError(
            "Announcement does not exist."
        )

    if announcement.status != Announcement.Status.ARCHIVED:
        raise ValidationError(
            "Only archived announcements can be restored."
        )

    announcement.status = Announcement.Status.DRAFT
    announcement.is_featured = False
    announcement.updated_by = user

    announcement.full_clean()

    announcement.save(
        update_fields=[
            "status",
            "is_featured",
            "updated_by",
            "updated_at",
        ]
    )

    return announcement


# =========================================================
# DELETE ANNOUNCEMENT
# =========================================================


@transaction.atomic
def delete_announcement(
    *,
    announcement,
    user,
):
    """
    Permanently delete an announcement.

    Only administrators can permanently delete announcements.
    """

    if not is_admin(user):
        raise PermissionDenied(
            "Only administrators can permanently delete announcements."
        )

    if not announcement:
        raise ValidationError(
            "Announcement does not exist."
        )

    announcement.delete()

    return True


# =========================================================
# FEATURE ANNOUNCEMENT
# =========================================================


@transaction.atomic
def feature_announcement(
    *,
    announcement,
    user,
):
    """
    Mark a published announcement as featured.
    """

    require_management_permission(user)

    if not announcement:
        raise ValidationError(
            "Announcement does not exist."
        )

    if announcement.status != Announcement.Status.PUBLISHED:
        raise ValidationError(
            "Only published announcements can be featured."
        )

    if (
        announcement.expires_at
        and announcement.expires_at <= timezone.now()
    ):
        raise ValidationError(
            "Expired announcements cannot be featured."
        )

    announcement.is_featured = True
    announcement.updated_by = user

    announcement.full_clean()

    announcement.save(
        update_fields=[
            "is_featured",
            "updated_by",
            "updated_at",
        ]
    )

    return announcement


# =========================================================
# UNFEATURE ANNOUNCEMENT
# =========================================================


@transaction.atomic
def unfeature_announcement(
    *,
    announcement,
    user,
):
    """
    Remove featured status from an announcement.
    """

    require_management_permission(user)

    if not announcement:
        raise ValidationError(
            "Announcement does not exist."
        )

    announcement.is_featured = False
    announcement.updated_by = user

    announcement.full_clean()

    announcement.save(
        update_fields=[
            "is_featured",
            "updated_by",
            "updated_at",
        ]
    )

    return announcement


# =========================================================
# VIEW COUNT
# =========================================================


def increment_view_count(announcement):
    """
    Safely increment the announcement view counter.
    """

    if not announcement:
        return

    Announcement.objects.filter(
        pk=announcement.pk,
    ).update(
        view_count=F("view_count") + 1,
    )


# =========================================================
# EXPIRATION
# =========================================================


@transaction.atomic
def expire_announcements():
    """
    Automatically archive published announcements whose
    expiration date has passed.
    """

    now = timezone.now()

    expired = Announcement.objects.filter(
        status=Announcement.Status.PUBLISHED,
        expires_at__isnull=False,
        expires_at__lte=now,
    )

    count = expired.update(
        status=Announcement.Status.ARCHIVED,
        is_featured=False,
        updated_at=now,
    )

    return count


# =========================================================
# ACTIVE ANNOUNCEMENTS
# =========================================================


def get_active_announcements():
    """
    Return currently active published announcements.

    An active announcement:

    - is published;
    - has reached its publication date;
    - has not expired.
    """

    now = timezone.now()

    return (
        Announcement.objects
        .filter(
            status=Announcement.Status.PUBLISHED,
        )
        .filter(
            Q(published_at__isnull=True)
            | Q(published_at__lte=now)
        )
        .filter(
            Q(expires_at__isnull=True)
            | Q(expires_at__gt=now)
        )
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
# USER AUDIENCE FILTER
# =========================================================


def _get_user_audience_filter(user):
    """
    Build the target-audience filter for a specific user.

    This helper is shared by:
        - get_announcements_for_user()
        - get_featured_announcements()
    """

    if not user or not user.is_authenticated:
        return Q(pk__in=[])

    role = getattr(
        user,
        "role",
        None,
    )

    year_of_study = getattr(
        user,
        "year_of_study",
        None,
    )

    normalized_year = str(
        year_of_study or ""
    ).strip().upper()

    # -----------------------------------------------------
    # Everyone
    # -----------------------------------------------------

    audience_filter = Q(
        target_audience=Announcement.TargetAudience.ALL
    )

    # -----------------------------------------------------
    # Students
    # -----------------------------------------------------

    if role == "STUDENT":

        audience_filter |= Q(
            target_audience=Announcement.TargetAudience.STUDENTS
        )

        first_year_values = {
            "1",
            "FIRST",
            "FIRST_YEAR",
            "YEAR_1",
        }

        second_year_values = {
            "2",
            "SECOND",
            "SECOND_YEAR",
            "YEAR_2",
        }

        third_year_values = {
            "3",
            "THIRD",
            "THIRD_YEAR",
            "YEAR_3",
        }

        fourth_year_values = {
            "4",
            "FOURTH",
            "FOURTH_YEAR",
            "YEAR_4",
        }

        if normalized_year in first_year_values:

            audience_filter |= Q(
                target_audience=Announcement.TargetAudience.FIRST_YEARS
            )

        elif normalized_year in second_year_values:

            audience_filter |= Q(
                target_audience=Announcement.TargetAudience.SECOND_YEARS
            )

        elif normalized_year in third_year_values:

            audience_filter |= Q(
                target_audience=Announcement.TargetAudience.THIRD_YEARS
            )

        elif normalized_year in fourth_year_values:

            audience_filter |= Q(
                target_audience=Announcement.TargetAudience.FOURTH_YEARS
            )

    # -----------------------------------------------------
    # Executives
    # -----------------------------------------------------

    if getattr(
        user,
        "is_executive",
        False,
    ):

        audience_filter |= Q(
            target_audience=Announcement.TargetAudience.EXECUTIVES
        )

    # -----------------------------------------------------
    # Alumni
    # -----------------------------------------------------

    if role == "ALUMNI":

        audience_filter |= Q(
            target_audience=Announcement.TargetAudience.ALUMNI
        )

    return audience_filter


# =========================================================
# FEATURED ANNOUNCEMENTS
# =========================================================


def get_featured_announcements(
    *,
    limit=5,
    user=None,
):
    """
    Return currently active featured announcements.

    When a user is supplied, only announcements intended for
    that user's target audience are returned.

    This allows views.py to safely call:

        get_featured_announcements(
            limit=5,
            user=request.user,
        )
    """

    queryset = (
        get_active_announcements()
        .filter(
            is_featured=True,
        )
    )

    # -----------------------------------------------------
    # Apply user audience when supplied
    # -----------------------------------------------------

    if user is not None:

        queryset = queryset.filter(
            _get_user_audience_filter(user)
        )

    # -----------------------------------------------------
    # Remove duplicate records
    # -----------------------------------------------------

    queryset = queryset.distinct()

    # -----------------------------------------------------
    # Apply limit
    # -----------------------------------------------------

    if limit is not None:
        return queryset[:limit]

    return queryset


# =========================================================
# ANNOUNCEMENTS FOR USER
# =========================================================


def get_announcements_for_user(user):
    """
    Return active announcements appropriate for the user.
    """

    if not user or not user.is_authenticated:
        return Announcement.objects.none()

    return (
        get_active_announcements()
        .filter(
            _get_user_audience_filter(user)
        )
        .distinct()
    )


# =========================================================
# SEARCH ANNOUNCEMENTS
# =========================================================


def search_announcements(
    *,
    query="",
    announcement_type=None,
    priority=None,
    target_audience=None,
    status=Announcement.Status.PUBLISHED,
):
    """
    Search and filter announcements.
    """

    if status == Announcement.Status.PUBLISHED:

        queryset = get_active_announcements()

    else:

        queryset = (
            Announcement.objects
            .filter(
                status=status,
            )
            .select_related(
                "created_by",
                "updated_by",
            )
        )

    # -----------------------------------------------------
    # Search
    # -----------------------------------------------------

    if query:

        query = query.strip()

        if query:

            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(summary__icontains=query)
                | Q(content__icontains=query)
            )

    # -----------------------------------------------------
    # Announcement type
    # -----------------------------------------------------

    if announcement_type:

        queryset = queryset.filter(
            announcement_type=announcement_type,
        )

    # -----------------------------------------------------
    # Priority
    # -----------------------------------------------------

    if priority:

        queryset = queryset.filter(
            priority=priority,
        )

    # -----------------------------------------------------
    # Target audience
    # -----------------------------------------------------

    if target_audience:

        queryset = queryset.filter(
            target_audience=target_audience,
        )

    return queryset.order_by(
        "-is_featured",
        "-published_at",
        "-created_at",
    )


# =========================================================
# RECENT ANNOUNCEMENTS
# =========================================================


def get_recent_announcements(
    limit=5,
):
    """
    Return the most recently published active announcements.
    """

    queryset = get_active_announcements()

    if limit is not None:
        return queryset[:limit]

    return queryset


# =========================================================
# ANNOUNCEMENT STATISTICS
# =========================================================


def get_announcement_statistics():
    """
    Return announcement statistics for executive/admin dashboards.
    """

    now = timezone.now()

    statistics = Announcement.objects.aggregate(

        # -------------------------------------------------
        # Total
        # -------------------------------------------------

        total=Count("id"),

        # -------------------------------------------------
        # Drafts
        # -------------------------------------------------

        drafts=Count(
            "id",
            filter=Q(
                status=Announcement.Status.DRAFT,
            ),
        ),

        # -------------------------------------------------
        # Published
        # -------------------------------------------------

        published=Count(
            "id",
            filter=Q(
                status=Announcement.Status.PUBLISHED,
            ),
        ),

        # -------------------------------------------------
        # Archived
        # -------------------------------------------------

        archived=Count(
            "id",
            filter=Q(
                status=Announcement.Status.ARCHIVED,
            ),
        ),

        # -------------------------------------------------
        # Expired
        # -------------------------------------------------

        expired=Count(
            "id",
            filter=Q(
                status=Announcement.Status.PUBLISHED,
                expires_at__isnull=False,
                expires_at__lte=now,
            ),
        ),

        # -------------------------------------------------
        # Active featured
        # -------------------------------------------------

        featured=Count(
            "id",
            filter=(
                Q(
                    status=Announcement.Status.PUBLISHED,
                    is_featured=True,
                )
                & (
                    Q(published_at__isnull=True)
                    | Q(published_at__lte=now)
                )
                & (
                    Q(expires_at__isnull=True)
                    | Q(expires_at__gt=now)
                )
            ),
        ),

        # -------------------------------------------------
        # Total views
        # -------------------------------------------------

        total_views=Sum("view_count"),
    )

    statistics["total_views"] = (
        statistics["total_views"] or 0
    )

    return statistics
