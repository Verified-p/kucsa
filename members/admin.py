# members/admin.py

from django.contrib import admin, messages
from django.db import transaction

from .models import Member
from .services import MemberService


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    """
    Django Admin configuration for KUCSA members.

    The admin interface provides:
        - Member management
        - Membership status management
        - Profile management
        - Membership activation
        - Membership suspension
        - Membership rejection
        - Profile completeness management

    Important:
        Membership business logic is delegated to MemberService
        instead of directly modifying membership fields.
    """

    # =========================================================
    # LIST DISPLAY
    # =========================================================

    list_display = (
        "membership_number",
        "member_name",
        "registration_number",
        "course",
        "year_of_study",
        "technical_level",
        "membership_status",
        "verification_status",
        "joined_date",
        "expiry_date",
        "is_profile_complete",
    )

    # =========================================================
    # LIST FILTERS
    # =========================================================

    list_filter = (
        "membership_status",
        "technical_level",
        "is_profile_complete",
        "joined_date",
        "expiry_date",
        "user__is_verified",
        "user__role",
    )

    # =========================================================
    # SEARCH
    # =========================================================

    search_fields = (
        "membership_number",
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "user__registration_number",
        "course",
    )

    # =========================================================
    # ORDERING
    # =========================================================

    ordering = (
        "user__first_name",
        "user__last_name",
    )

    # =========================================================
    # READ ONLY FIELDS
    # =========================================================

    readonly_fields = (
        "created_at",
        "updated_at",
        "member_name",
        "registration_number",
        "verification_status",
    )

    # =========================================================
    # FIELDSETS
    # =========================================================

    fieldsets = (
        (
            "User Account",
            {
                "fields": (
                    "user",
                    "member_name",
                    "registration_number",
                    "verification_status",
                )
            },
        ),

        (
            "Membership Information",
            {
                "fields": (
                    "membership_number",
                    "membership_status",
                    "joined_date",
                    "expiry_date",
                )
            },
        ),

        (
            "Personal & Academic Information",
            {
                "fields": (
                    "bio",
                    "course",
                    "year_of_study",
                )
            },
        ),

        (
            "Technical Profile",
            {
                "fields": (
                    "technical_level",
                    "technical_domains",
                    "skills",
                    "interests",
                )
            },
        ),

        (
            "Professional Links",
            {
                "fields": (
                    "github_url",
                    "linkedin_url",
                    "portfolio_url",
                )
            },
        ),

        (
            "Profile Status",
            {
                "fields": (
                    "is_profile_complete",
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
    # DATE HIERARCHY
    # =========================================================

    date_hierarchy = "joined_date"

    # =========================================================
    # USER AUTOCOMPLETE
    # =========================================================

    autocomplete_fields = (
        "user",
    )

    # =========================================================
    # PERFORMANCE
    # =========================================================

    list_select_related = (
        "user",
    )

    # =========================================================
    # ADMIN ACTIONS
    # =========================================================

    actions = (
        "activate_members",
        "suspend_members",
        "reject_members",
        "expire_members",
        "mark_profiles_complete",
        "mark_profiles_incomplete",
    )

    # =========================================================
    # CUSTOM DISPLAY METHODS
    # =========================================================

    @admin.display(
        description="Full Name",
        ordering="user__first_name",
    )
    def member_name(self, obj):
        """
        Display the member's full name from User.
        """

        if not obj or not obj.user:
            return "-"

        return (
            obj.user.get_full_name()
            or obj.user.username
        )

    @admin.display(
        description="Registration Number",
        ordering="user__registration_number",
    )
    def registration_number(self, obj):
        """
        Display the university registration number
        from the related User account.
        """

        if not obj or not obj.user:
            return "-"

        return obj.user.registration_number

    @admin.display(
        description="Verified",
        boolean=True,
        ordering="user__is_verified",
    )
    def verification_status(self, obj):
        """
        Display the User verification status.
        """

        if not obj or not obj.user:
            return False

        return obj.user.is_verified

    # =========================================================
    # ACTIVATE MEMBERS
    # =========================================================

    @admin.action(
        description="Activate selected members"
    )
    @transaction.atomic
    def activate_members(self, request, queryset):
        """
        Activate selected members using MemberService.

        This ensures that activation also:
            - Generates a membership number
            - Sets membership status to ACTIVE
            - Sets joined date
            - Sets expiry date
            - Verifies the user account
        """

        activated = 0
        skipped = 0

        for member in queryset.select_related("user"):

            # Administrators are already handled automatically.
            # Do not cause unnecessary changes.
            if MemberService.is_administrator(
                member.user
            ):
                skipped += 1
                continue

            try:
                MemberService.activate_member(
                    member
                )

                member.user.is_verified = True
                member.user.save(
                    update_fields=[
                        "is_verified",
                        "updated_at",
                    ]
                )

                activated += 1

            except Exception as exc:
                self.message_user(
                    request,
                    (
                        f"Could not activate "
                        f"{member}: {exc}"
                    ),
                    level=messages.ERROR,
                )

        if activated:
            self.message_user(
                request,
                (
                    f"{activated} member(s) "
                    "activated successfully."
                ),
                level=messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                (
                    f"{skipped} administrator "
                    "membership(s) were skipped because "
                    "administrators are automatically active."
                ),
                level=messages.WARNING,
            )

    # =========================================================
    # SUSPEND MEMBERS
    # =========================================================

    @admin.action(
        description="Suspend selected members"
    )
    @transaction.atomic
    def suspend_members(self, request, queryset):
        """
        Suspend selected members.

        Administrators cannot be suspended.
        """

        suspended = 0
        skipped = 0

        for member in queryset.select_related("user"):

            if MemberService.is_administrator(
                member.user
            ):
                skipped += 1
                continue

            try:
                MemberService.suspend_member(
                    member
                )

                member.user.is_verified = False
                member.user.save(
                    update_fields=[
                        "is_verified",
                        "updated_at",
                    ]
                )

                suspended += 1

            except Exception as exc:
                self.message_user(
                    request,
                    (
                        f"Could not suspend "
                        f"{member}: {exc}"
                    ),
                    level=messages.ERROR,
                )

        if suspended:
            self.message_user(
                request,
                (
                    f"{suspended} member(s) "
                    "suspended successfully."
                ),
                level=messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                (
                    f"{skipped} administrator "
                    "membership(s) were skipped."
                ),
                level=messages.WARNING,
            )

    # =========================================================
    # REJECT MEMBERS
    # =========================================================

    @admin.action(
        description="Reject selected members"
    )
    @transaction.atomic
    def reject_members(self, request, queryset):
        """
        Reject selected memberships.

        Administrators cannot be rejected.
        """

        rejected = 0
        skipped = 0

        for member in queryset.select_related("user"):

            if MemberService.is_administrator(
                member.user
            ):
                skipped += 1
                continue

            try:
                MemberService.reject_member(
                    member
                )

                member.user.is_verified = False
                member.user.save(
                    update_fields=[
                        "is_verified",
                        "updated_at",
                    ]
                )

                rejected += 1

            except Exception as exc:
                self.message_user(
                    request,
                    (
                        f"Could not reject "
                        f"{member}: {exc}"
                    ),
                    level=messages.ERROR,
                )

        if rejected:
            self.message_user(
                request,
                (
                    f"{rejected} member(s) "
                    "rejected successfully."
                ),
                level=messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                (
                    f"{skipped} administrator "
                    "membership(s) were skipped."
                ),
                level=messages.WARNING,
            )

    # =========================================================
    # EXPIRE MEMBERS
    # =========================================================

    @admin.action(
        description="Mark selected memberships as expired"
    )
    @transaction.atomic
    def expire_members(self, request, queryset):
        """
        Mark selected memberships as expired.

        User verification is also removed.
        Administrators cannot be expired.
        """

        expired = 0
        skipped = 0

        for member in queryset.select_related("user"):

            if MemberService.is_administrator(
                member.user
            ):
                skipped += 1
                continue

            member.membership_status = (
                Member.MembershipStatus.EXPIRED
            )

            member.save(
                update_fields=[
                    "membership_status",
                    "updated_at",
                ]
            )

            member.user.is_verified = False

            member.user.save(
                update_fields=[
                    "is_verified",
                    "updated_at",
                ]
            )

            expired += 1

        if expired:
            self.message_user(
                request,
                (
                    f"{expired} membership(s) "
                    "marked as expired."
                ),
                level=messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                (
                    f"{skipped} administrator "
                    "membership(s) were skipped."
                ),
                level=messages.WARNING,
            )

    # =========================================================
    # MARK PROFILES COMPLETE
    # =========================================================

    @admin.action(
        description="Mark profiles as complete"
    )
    def mark_profiles_complete(
        self,
        request,
        queryset,
    ):
        """
        Mark selected member profiles as complete.
        """

        updated = queryset.update(
            is_profile_complete=True
        )

        self.message_user(
            request,
            (
                f"{updated} member profile(s) "
                "marked as complete."
            ),
            level=messages.SUCCESS,
        )

    # =========================================================
    # MARK PROFILES INCOMPLETE
    # =========================================================

    @admin.action(
        description="Mark profiles as incomplete"
    )
    def mark_profiles_incomplete(
        self,
        request,
        queryset,
    ):
        """
        Mark selected member profiles as incomplete.
        """

        updated = queryset.update(
            is_profile_complete=False
        )

        self.message_user(
            request,
            (
                f"{updated} member profile(s) "
                "marked as incomplete."
            ),
            level=messages.SUCCESS,
        )

    # =========================================================
    # SAVE MODEL
    # =========================================================

    @transaction.atomic
    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        """
        Save a Member through the admin interface.

        Administrators are automatically activated.
        """

        super().save_model(
            request,
            obj,
            form,
            change,
        )

        # -----------------------------------------------------
        # Automatically activate administrator membership
        # -----------------------------------------------------

        if obj.user and MemberService.is_administrator(
            obj.user
        ):
            MemberService._activate_administrator_membership(
                obj
            )