
# announcements/admin.py

from django.contrib import admin
from django.utils.html import format_html

from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    """
    Django Admin configuration for KUCSA announcements.
    """

    # =====================================================
    # LIST DISPLAY
    # =====================================================

    list_display = (
        "title",
        "announcement_type",
        "priority",
        "status",
        "created_by",
        "target_audience",
        "is_featured",
        "published_at",
        "expires_at",
        "view_count",
    )

    # =====================================================
    # FILTERS
    # =====================================================

    list_filter = (
        "announcement_type",
        "priority",
        "status",
        "target_audience",
        "is_featured",
        "allow_comments",
        "published_at",
        "created_at",
    )

    # =====================================================
    # SEARCH
    # =====================================================

    search_fields = (
        "title",
        "summary",
        "content",
        "created_by__username",
        "created_by__first_name",
        "created_by__last_name",
        "created_by__email",
    )

    # =====================================================
    # PREPOPULATE SLUG
    # =====================================================

    prepopulated_fields = {
        "slug": ("title",),
    }

    # =====================================================
    # DATE HIERARCHY
    # =====================================================

    date_hierarchy = "created_at"

    # =====================================================
    # ORDERING
    # =====================================================

    ordering = (
        "-is_featured",
        "-published_at",
        "-created_at",
    )

    # =====================================================
    # ITEMS PER PAGE
    # =====================================================

    list_per_page = 25

    # =====================================================
    # READ-ONLY FIELDS
    # =====================================================

    readonly_fields = (
        "view_count",
        "created_at",
        "updated_at",
        "published_at",
        "announcement_status",
        "author_information",
    )

    # =====================================================
    # FIELD GROUPS
    # =====================================================

    fieldsets = (

        # -------------------------------------------------
        # BASIC INFORMATION
        # -------------------------------------------------

        (
            "Announcement Information",
            {
                "fields": (
                    "title",
                    "slug",
                    "summary",
                    "content",
                ),
            },
        ),

        # -------------------------------------------------
        # CLASSIFICATION
        # -------------------------------------------------

        (
            "Classification",
            {
                "fields": (
                    "announcement_type",
                    "priority",
                    "status",
                    "target_audience",
                ),
            },
        ),

        # -------------------------------------------------
        # AUTHORSHIP
        # -------------------------------------------------

        (
            "Authorship",
            {
                "fields": (
                    "created_by",
                    "updated_by",
                    "author_information",
                ),
            },
        ),

        # -------------------------------------------------
        # MEDIA
        # -------------------------------------------------

        (
            "Media & Attachments",
            {
                "fields": (
                    "image",
                    "attachment",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),

        # -------------------------------------------------
        # PUBLICATION
        # -------------------------------------------------

        (
            "Publication",
            {
                "fields": (
                    "published_at",
                    "expires_at",
                ),
            },
        ),

        # -------------------------------------------------
        # DISPLAY OPTIONS
        # -------------------------------------------------

        (
            "Display Options",
            {
                "fields": (
                    "is_featured",
                    "allow_comments",
                ),
            },
        ),

        # -------------------------------------------------
        # STATISTICS
        # -------------------------------------------------

        (
            "Statistics",
            {
                "fields": (
                    "view_count",
                    "announcement_status",
                ),
            },
        ),

        # -------------------------------------------------
        # SYSTEM INFORMATION
        # -------------------------------------------------

        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    # =====================================================
    # CUSTOM ADMIN DISPLAY
    # =====================================================

    @admin.display(
        description="Current Status",
        ordering="status",
    )
    def announcement_status(self, obj):
        """
        Display the current announcement status
        with a visual indicator.
        """

        if obj.status == Announcement.Status.PUBLISHED:

            if obj.is_expired:
                return format_html(
                    '<span style="color:#dc3545; font-weight:600;">'
                    '● Expired'
                    '</span>'
                )

            return format_html(
                '<span style="color:#198754; font-weight:600;">'
                '● Published'
                '</span>'
            )

        if obj.status == Announcement.Status.DRAFT:

            return format_html(
                '<span style="color:#6c757d; font-weight:600;">'
                '● Draft'
                '</span>'
            )

        if obj.status == Announcement.Status.ARCHIVED:

            return format_html(
                '<span style="color:#6f42c1; font-weight:600;">'
                '● Archived'
                '</span>'
            )

        return obj.get_status_display()

    # =====================================================
    # AUTHOR INFORMATION
    # =====================================================

    @admin.display(
        description="Author",
    )
    def author_information(self, obj):
        """
        Display author information inside the admin form.
        """

        if not obj.created_by:
            return "KUCSA Administration"

        name = (
            obj.created_by.get_full_name()
            or obj.created_by.username
        )

        email = getattr(
            obj.created_by,
            "email",
            "",
        )

        if email:
            return f"{name} ({email})"

        return name

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
        Automatically record the user who created
        or updated the announcement.
        """

        if not change and not obj.created_by:
            obj.created_by = request.user

        if change:
            obj.updated_by = request.user

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    # =====================================================
    # SAVE RELATED MODEL
    # =====================================================

    def save_formset(
        self,
        request,
        form,
        formset,
        change,
    ):
        """
        Keep compatibility with future inline formsets.
        """

        instances = formset.save(
            commit=False,
        )

        for instance in instances:
            if hasattr(instance, "created_by"):
                if not instance.created_by:
                    instance.created_by = request.user

            if hasattr(instance, "updated_by"):
                instance.updated_by = request.user

            instance.save()

        formset.save_m2m()
