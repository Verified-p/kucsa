
# executives/admin.py

from django.contrib import admin
from django.contrib import messages

from .models import Executive


@admin.register(Executive)
class ExecutiveAdmin(admin.ModelAdmin):
    """
    Admin configuration for KUCSA executives.
    """

    # =========================================================
    # LIST DISPLAY
    # =========================================================

    list_display = (
        "full_name",
        "registration_number",
        "role",
        "committee",
        "email",
        "phone_number",
        "term_start",
        "term_end",
        "is_active",
    )

    # =========================================================
    # LIST FILTERS
    # =========================================================

    list_filter = (
        "committee",
        "is_active",
        "term_start",
        "term_end",
        "user__role",
        "user__is_verified",
    )

    # =========================================================
    # SEARCH
    # =========================================================

    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__username",
        "user__registration_number",
        "user__email",
        "user__phone_number",
        "committee",
        "office_location",
        "responsibilities",
    )

    # =========================================================
    # ORDERING
    # =========================================================

    ordering = (
        "user__first_name",
        "user__last_name",
    )

    # =========================================================
    # READ-ONLY FIELDS
    # =========================================================

    readonly_fields = (
        "created_at",
        "updated_at",
        "full_name",
        "role",
        "registration_number",
        "email",
        "phone_number",
    )

    # =========================================================
    # FIELD GROUPS
    # =========================================================

    fieldsets = (
        (
            "User Account",
            {
                "fields": (
                    "user",
                )
            },
        ),

        (
            "Executive Information",
            {
                "fields": (
                    "committee",
                    "office_location",
                    "responsibilities",
                    "vision",
                    "biography",
                )
            },
        ),

        (
            "Term Information",
            {
                "fields": (
                    "term_start",
                    "term_end",
                    "is_active",
                )
            },
        ),

        (
            "Profile Information",
            {
                "fields": (
                    "full_name",
                    "role",
                    "registration_number",
                    "email",
                    "phone_number",
                )
            },
        ),

        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    # =========================================================
    # AUTOCOMPLETE USER
    # =========================================================

    autocomplete_fields = (
        "user",
    )

    # =========================================================
    # DATE HIERARCHY
    # =========================================================

    date_hierarchy = "term_start"

    # =========================================================
    # ADMIN ACTIONS
    # =========================================================

    actions = (
        "activate_executives",
        "deactivate_executives",
    )

    # =========================================================
    # ACTIVATE EXECUTIVES
    # =========================================================

    @admin.action(description="Activate selected executives")
    def activate_executives(self, request, queryset):
        """
        Activate selected executive profiles.
        """

        updated = queryset.update(
            is_active=True
        )

        self.message_user(
            request,
            f"{updated} executive(s) activated successfully.",
            messages.SUCCESS,
        )

    # =========================================================
    # DEACTIVATE EXECUTIVES
    # =========================================================

    @admin.action(
        description="Deactivate selected executives"
    )
    def deactivate_executives(self, request, queryset):
        """
        Deactivate selected executive profiles.
        """

        updated = queryset.update(
            is_active=False
        )

        self.message_user(
            request,
            f"{updated} executive(s) deactivated successfully.",
            messages.WARNING,
        )

    # =========================================================
    # CUSTOM ADMIN DISPLAY METHODS
    # =========================================================

    @admin.display(
        description="Name",
        ordering="user__first_name",
    )
    def full_name(self, obj):
        """
        Display the executive's full name.
        """

        return obj.user.get_full_name() or obj.user.username

    @admin.display(
        description="Role",
        ordering="user__role",
    )
    def role(self, obj):
        """
        Display the executive's KUCSA role.
        """

        return obj.user.get_role_display()

    @admin.display(
        description="Registration Number",
        ordering="user__registration_number",
    )
    def registration_number(self, obj):
        """
        Display the university registration number.
        """

        return obj.user.registration_number

    @admin.display(
        description="Email",
        ordering="user__email",
    )
    def email(self, obj):
        """
        Display the executive's email address.
        """

        return obj.user.email

    @admin.display(
        description="Phone",
    )
    def phone_number(self, obj):
        """
        Display the executive's phone number.
        """

        return obj.user.phone_number
