from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Django Admin configuration for the KUCSA custom User model.

    User.role represents the KUCSA organizational position.
    Django system permissions are controlled independently by
    is_staff, is_superuser, groups and user_permissions.
    """

    list_display = (
        "username",
        "full_name_display",
        "registration_number",
        "email",
        "role",
        "membership_display",
        "is_verified",
        "is_staff",
        "is_superuser",
        "is_active",
        "date_joined",
    )

    list_filter = (
        "role",
        "is_verified",
        "is_active",
        "is_staff",
        "is_superuser",
    )

    search_fields = (
        "username",
        "registration_number",
        "first_name",
        "last_name",
        "email",
        "phone_number",
    )

    ordering = (
        "first_name",
        "last_name",
        "username",
    )

    readonly_fields = (
        "last_login",
        "date_joined",
        "created_at",
        "updated_at",
        "membership_summary",
    )

    fieldsets = (
        (
            "Account Information",
            {
                "fields": (
                    "username",
                    "password",
                )
            },
        ),
        (
            "Personal Information",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "registration_number",
                    "email",
                    "phone_number",
                    "profile_picture",
                )
            },
        ),
        (
            "KUCSA Role & Membership",
            {
                "fields": (
                    "role",
                    "is_verified",
                    "membership_summary",
                ),
                "description": (
                    "Executive positions should only be assigned "
                    "to members whose KUCSA membership is active."
                ),
            },
        ),
        (
            "Django Administration Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
                "description": (
                    "These permissions control Django system "
                    "administration and are separate from the "
                    "user's KUCSA organizational role."
                ),
            },
        ),
        (
            "Important Dates",
            {
                "fields": (
                    "last_login",
                    "date_joined",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            "Create User Account",
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "email",
                    "first_name",
                    "last_name",
                    "registration_number",
                    "phone_number",
                    "role",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )

    @admin.display(description="Name", ordering="first_name")
    def full_name_display(self, obj):
        return obj.full_name

    @admin.display(description="Membership")
    def membership_display(self, obj):
        if obj.is_kucsa_admin:
            return format_html(
                "<strong>{}</strong>",
                "Administrator",
            )

        member = obj.member

        if member is None:
            return format_html(
                '<span style="color: {};">{}</span>',
                "#dc3545",
                "No Member Profile",
            )

        if member.can_access_platform:
            return format_html(
                '<strong style="color: {};">{}</strong>',
                "#198754",
                "ACTIVE",
            )

        if member.has_pending_payment:
            return format_html(
                '<strong style="color: {};">{}</strong>',
                "#fd7e14",
                "PAYMENT PENDING",
            )

        if member.is_suspended:
            return format_html(
                '<strong style="color: {};">{}</strong>',
                "#dc3545",
                "SUSPENDED",
            )

        if member.is_expired:
            return format_html(
                '<strong style="color: {};">{}</strong>',
                "#dc3545",
                "EXPIRED",
            )

        return format_html(
            '<span style="color: {};">{}</span>',
            "#6c757d",
            "PAYMENT REQUIRED",
        )

    @admin.display(description="Membership Information")
    def membership_summary(self, obj):
        if obj.is_kucsa_admin:
            return "Administrator — membership payment is not required."

        member = obj.member

        if member is None:
            return "No KUCSA Member profile is associated with this account."

        status = getattr(member, "membership_status", "Unknown")
        membership_number = getattr(member, "membership_number", None)

        if membership_number:
            return (
                f"Status: {status} | "
                f"Membership Number: {membership_number}"
            )

        return f"Status: {status}"

    def save_model(self, request, obj, form, change):
        """
        Only allow executive roles for members with active membership.
        """
        executive_roles = User.EXECUTIVE_ROLES

        if obj.role in executive_roles:
            member = obj.member

            if member is None:
                raise ValidationError(
                    "This user cannot be assigned an executive role "
                    "because they do not have a KUCSA Member profile."
                )

            if not member.can_access_platform:
                raise ValidationError(
                    "This user cannot be assigned an executive role "
                    "because their KUCSA membership is not active."
                )

        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)