
# announcements/models.py

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Announcement(models.Model):
    """
    KUCSA Announcement.

    Announcements act as the communication/notification layer
    of the KUCSA platform.

    Authorized KUCSA administrators and executives can create
    and publish announcements.

    Members/students can see announcements according to their
    target audience, publication status and expiry date.
    """

    # =========================================================
    # ANNOUNCEMENT TYPE
    # =========================================================

    class AnnouncementType(models.TextChoices):
        GENERAL = "GENERAL", "General"
        EVENT = "EVENT", "Event"
        MEETING = "MEETING", "Meeting"
        ACADEMIC = "ACADEMIC", "Academic"
        CAREER = "CAREER", "Career Opportunity"
        TRAINING = "TRAINING", "Training"
        COMPETITION = "COMPETITION", "Competition"
        OPPORTUNITY = "OPPORTUNITY", "Opportunity"
        REMINDER = "REMINDER", "Reminder"
        EMERGENCY = "EMERGENCY", "Emergency"
        OTHER = "OTHER", "Other"

    # =========================================================
    # PRIORITY
    # =========================================================

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        NORMAL = "NORMAL", "Normal"
        IMPORTANT = "IMPORTANT", "Important"
        URGENT = "URGENT", "Urgent"

    # =========================================================
    # STATUS
    # =========================================================

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        ARCHIVED = "ARCHIVED", "Archived"

    # =========================================================
    # TARGET AUDIENCE
    # =========================================================

    class TargetAudience(models.TextChoices):
        ALL = "ALL", "All Members"
        STUDENTS = "STUDENTS", "Students"
        EXECUTIVES = "EXECUTIVES", "Executives"
        FIRST_YEARS = "FIRST_YEARS", "First Year Students"
        SECOND_YEARS = "SECOND_YEARS", "Second Year Students"
        THIRD_YEARS = "THIRD_YEARS", "Third Year Students"
        FOURTH_YEARS = "FOURTH_YEARS", "Fourth Year Students"
        ALUMNI = "ALUMNI", "Alumni"

    # =========================================================
    # BASIC INFORMATION
    # =========================================================

    title = models.CharField(
        max_length=255,
        verbose_name="Announcement Title",
    )

    slug = models.SlugField(
        max_length=280,
        unique=True,
        blank=True,
        help_text="Automatically generated from the announcement title.",
    )

    summary = models.CharField(
        max_length=500,
        blank=True,
        help_text=(
            "Short summary displayed on announcement lists, "
            "dashboard widgets and notification-style previews."
        ),
    )

    content = models.TextField(
        verbose_name="Announcement Content",
    )

    # =========================================================
    # CLASSIFICATION
    # =========================================================

    announcement_type = models.CharField(
        max_length=30,
        choices=AnnouncementType.choices,
        default=AnnouncementType.GENERAL,
        db_index=True,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    target_audience = models.CharField(
        max_length=30,
        choices=TargetAudience.choices,
        default=TargetAudience.ALL,
        db_index=True,
    )

    # =========================================================
    # AUTHORSHIP
    # =========================================================

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_announcements",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_announcements",
    )

    # =========================================================
    # OPTIONAL MEDIA
    # =========================================================

    image = models.ImageField(
        upload_to="announcements/images/",
        blank=True,
        null=True,
    )

    attachment = models.FileField(
        upload_to="announcements/attachments/",
        blank=True,
        null=True,
    )

    # =========================================================
    # PUBLICATION
    # =========================================================

    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Date and time when the announcement became visible "
            "to its target audience."
        ),
    )

    # =========================================================
    # EXPIRATION
    # =========================================================

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Optional date and time after which the announcement "
            "will no longer appear to members."
        ),
    )

    # =========================================================
    # DISPLAY OPTIONS
    # =========================================================

    is_featured = models.BooleanField(
        default=False,
        help_text=(
            "Display this announcement prominently on the "
            "announcement page and dashboard."
        ),
    )

    allow_comments = models.BooleanField(
        default=False,
        help_text="Allow members to comment on this announcement.",
    )

    # =========================================================
    # VIEW TRACKING
    # =========================================================

    view_count = models.PositiveIntegerField(
        default=0,
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
            "-is_featured",
            "-published_at",
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=["status", "published_at"],
            ),
            models.Index(
                fields=["status", "expires_at"],
            ),
            models.Index(
                fields=["announcement_type", "status"],
            ),
            models.Index(
                fields=["priority", "status"],
            ),
            models.Index(
                fields=["target_audience", "status"],
            ),
            models.Index(
                fields=["is_featured", "status"],
            ),
        ]

        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"

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
        Automatically generate a unique slug.

        Also automatically sets published_at when an announcement
        is published for the first time.
        """

        if not self.slug:
            base_slug = slugify(self.title) or "announcement"
            slug = base_slug
            counter = 2

            while type(self).objects.filter(
                slug=slug
            ).exclude(
                pk=self.pk
            ).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        if (
            self.status == self.Status.PUBLISHED
            and not self.published_at
        ):
            self.published_at = timezone.now()

        super().save(*args, **kwargs)

    # =========================================================
    # VALIDATION
    # =========================================================

    def clean(self):
        """
        Validate announcement information.
        """

        # -----------------------------------------------------
        # EXPIRATION
        # -----------------------------------------------------

        if (
            self.expires_at
            and self.published_at
            and self.expires_at <= self.published_at
        ):
            raise ValidationError(
                {
                    "expires_at": (
                        "The expiration date must be after "
                        "the publication date."
                    )
                }
            )

        # -----------------------------------------------------
        # EMERGENCY PRIORITY
        # -----------------------------------------------------

        if (
            self.announcement_type
            == self.AnnouncementType.EMERGENCY
            and self.priority == self.Priority.LOW
        ):
            raise ValidationError(
                {
                    "priority": (
                        "Emergency announcements cannot "
                        "have low priority."
                    )
                }
            )

        # -----------------------------------------------------
        # PUBLISHED ANNOUNCEMENT
        # -----------------------------------------------------

        if (
            self.status == self.Status.PUBLISHED
            and self.expires_at
            and self.published_at
            and self.expires_at <= self.published_at
        ):
            raise ValidationError(
                {
                    "expires_at": (
                        "A published announcement cannot "
                        "expire before its publication time."
                    )
                }
            )

    # =========================================================
    # PUBLICATION HELPERS
    # =========================================================

    @property
    def is_published(self):
        """
        Return True when the announcement has published status.
        """

        return self.status == self.Status.PUBLISHED

    @property
    def is_expired(self):
        """
        Return True when the announcement has passed its
        expiration date.
        """

        if not self.expires_at:
            return False

        return timezone.now() >= self.expires_at

    @property
    def is_active(self):
        """
        Return True when the announcement is currently visible
        to its target audience.
        """

        return (
            self.status == self.Status.PUBLISHED
            and not self.is_expired
        )

    # =========================================================
    # PRIORITY HELPERS
    # =========================================================

    @property
    def is_urgent(self):
        return self.priority == self.Priority.URGENT

    @property
    def is_important(self):
        return self.priority == self.Priority.IMPORTANT

    # =========================================================
    # DISPLAY HELPERS
    # =========================================================

    @property
    def type_label(self):
        return self.get_announcement_type_display()

    @property
    def priority_label(self):
        return self.get_priority_display()

    @property
    def audience_label(self):
        return self.get_target_audience_display()

    # =========================================================
    # AUTHOR HELPERS
    # =========================================================

    @property
    def author_name(self):
        """
        Return the author's full name where available.
        """

        if not self.created_by:
            return "KUCSA Administration"

        return (
            self.created_by.get_full_name()
            or self.created_by.username
        )

    # =========================================================
    # URL HELPER
    # =========================================================

    def get_absolute_url(self):
        """
        Return the announcement detail URL.

        announcements/urls.py should define:

            path(
                "<slug:slug>/",
                ...,
                name="detail",
            )
        """

        return reverse(
            "announcements:detail",
            kwargs={"slug": self.slug},
        )

    # =========================================================
    # VIEW COUNTER
    # =========================================================

    def increment_view_count(self):
        """
        Safely increment the announcement view counter.
        """

        type(self).objects.filter(
            pk=self.pk,
        ).update(
            view_count=F("view_count") + 1,
        )

        self.refresh_from_db(
            fields=["view_count"],
        )


# =============================================================
# ANNOUNCEMENT READ TRACKING
# =============================================================


class AnnouncementRead(models.Model):
    """
    Tracks whether a user has read an announcement.

    This allows the announcement system to behave similarly
    to a notification system without requiring a separate
    notifications application.

    Example:

        New announcement:
            is_read = False

        Member opens announcement:
            is_read = True

    This also allows the dashboard/sidebar to display:

        "3 New Announcements"

    and notification-style unread indicators.
    """

    announcement = models.ForeignKey(
        Announcement,
        on_delete=models.CASCADE,
        related_name="read_records",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="announcement_reads",
    )

    read_at = models.DateTimeField(
        default=timezone.now,
    )

    class Meta:
        ordering = ["-read_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["announcement", "user"],
                name="unique_announcement_read_per_user",
            ),
        ]

        indexes = [
            models.Index(
                fields=["user", "read_at"],
            ),
            models.Index(
                fields=["user", "announcement"],
            ),
        ]

        verbose_name = "Announcement Read Record"
        verbose_name_plural = "Announcement Read Records"

    def __str__(self):
        return (
            f"{self.user} read "
            f'"{self.announcement.title}"'
        )

    @property
    def is_read(self):
        return True

