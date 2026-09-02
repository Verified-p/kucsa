# members/services.py

from calendar import monthrange
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import User

from .models import Member


class MemberService:
    """
    Central business-logic service for KUCSA membership.

    This service is responsible for:

        - Member creation and retrieval
        - Membership number generation
        - Membership activation
        - Membership renewal
        - Membership suspension
        - Membership rejection
        - Membership expiry
        - Membership status
        - Account verification synchronization
        - Profile completeness
        - Member searching
        - Membership statistics

    IMPORTANT
    =========

    Payment processing does NOT belong here.

    PaymentService is responsible for:

        1. Receiving payment
        2. Verifying payment
        3. Determining whether it is registration or renewal
        4. Calling the appropriate MemberService method

    Example:

        PaymentService
            |
            | verified registration payment
            v
        MemberService.activate_member()

    or:

        PaymentService
            |
            | verified renewal payment
            v
        MemberService.renew_membership()
    """

    # =========================================================
    # MEMBERSHIP CONFIGURATION
    # =========================================================

    MEMBERSHIP_DURATION_MONTHS = 4

    # Backwards compatibility for older code.
    DEFAULT_MEMBERSHIP_DURATION_DAYS = 120

    # KUCSA membership fees in Kenyan Shillings.
    REGISTRATION_FEE = 100
    RENEWAL_FEE = 50

    # =========================================================
    # EXECUTIVE ROLES
    # =========================================================

    EXECUTIVE_ROLES = [
        User.Role.CHAIRPERSON,
        User.Role.VICE_CHAIRPERSON,
        User.Role.SECRETARY,
        User.Role.SECRETARY_GENERAL,
        User.Role.TREASURER,
        User.Role.ORGANIZING_SECRETARY,
        User.Role.PUBLICITY_SECRETARY,
    ]

    # =========================================================
    # DATE UTILITIES
    # =========================================================

    @staticmethod
    def add_months(start_date, months):
        """
        Safely add calendar months to a date.

        Examples:

            2026-01-15 + 4 months
            -> 2026-05-15

            2026-01-31 + 1 month
            -> 2026-02-28

        This avoids invalid dates when the destination month
        has fewer days.
        """

        if not isinstance(start_date, date):
            raise ValueError(
                "A valid date is required."
            )

        if months < 0:
            raise ValueError(
                "Number of months cannot be negative."
            )

        month_index = (
            start_date.month - 1 + months
        )

        year = (
            start_date.year
            + month_index // 12
        )

        month = (
            month_index % 12
        ) + 1

        day = min(
            start_date.day,
            monthrange(year, month)[1],
        )

        return date(
            year,
            month,
            day,
        )

    @staticmethod
    def get_membership_expiry_date(
        start_date=None,
        duration_months=None,
    ):
        """
        Calculate membership expiry.

        Default duration:
            4 calendar months.
        """

        start_date = start_date or date.today()

        if duration_months is None:
            duration_months = (
                MemberService.MEMBERSHIP_DURATION_MONTHS
            )

        if duration_months <= 0:
            raise ValueError(
                "Membership duration must be greater than zero."
            )

        return MemberService.add_months(
            start_date,
            duration_months,
        )

    # =========================================================
    # FEES
    # =========================================================

    @staticmethod
    def get_registration_fee():
        """Return the new-member registration fee."""

        return MemberService.REGISTRATION_FEE

    @staticmethod
    def get_renewal_fee():
        """Return the existing-member renewal fee."""

        return MemberService.RENEWAL_FEE

    @staticmethod
    def get_membership_fee(member=None):
        """
        Determine the correct membership fee.

        No membership number:
            Registration fee

        Existing membership number:
            Renewal fee
        """

        if not member:
            return MemberService.REGISTRATION_FEE

        if MemberService.is_new_member(member):
            return MemberService.REGISTRATION_FEE

        return MemberService.RENEWAL_FEE

    @staticmethod
    def is_new_member(member):
        """
        Determine whether a member has never received
        a KUCSA membership number.
        """

        if not member:
            return True

        return not bool(
            member.membership_number
        )

    # =========================================================
    # USER / ADMINISTRATOR HELPERS
    # =========================================================

    @staticmethod
    def is_administrator(user):
        """
        Determine whether a user has administrator privileges.

        Administrator access is recognized through:

            - ADMIN role
            - Django staff
            - Django superuser
        """

        if not user:
            return False

        return bool(
            getattr(user, "role", None)
            == User.Role.ADMIN
            or getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
        )

    @staticmethod
    def is_executive(user):
        """
        Determine whether a user has a KUCSA executive role.
        """

        if not user:
            return False

        role = getattr(
            user,
            "role",
            None,
        )

        return role in MemberService.EXECUTIVE_ROLES

    @staticmethod
    @transaction.atomic
    def set_user_verified(user, verified):
        """
        Synchronize the Django user's verification state.

        Membership lifecycle methods use this method so that
        membership status and account verification do not drift
        apart.
        """

        if not user:
            return None

        verified = bool(verified)

        if user.is_verified != verified:

            user.is_verified = verified

            user.save(
                update_fields=[
                    "is_verified",
                ]
            )

        return user

    # =========================================================
    # MEMBERSHIP STATUS HELPERS
    # =========================================================

    @staticmethod
    def is_membership_active(member):
        """
        Determine whether a membership is genuinely active.

        A member is active only when:

            membership_status == ACTIVE

        and:

            expiry_date is today or in the future.
        """

        if not member:
            return False

        if (
            member.membership_status
            != Member.MembershipStatus.ACTIVE
        ):
            return False

        if not member.expiry_date:
            return False

        return member.expiry_date >= date.today()

    @staticmethod
    def is_membership_expired(member):
        """
        Determine whether a membership has passed its expiry date.
        """

        if not member:
            return False

        if not member.expiry_date:
            return False

        return member.expiry_date < date.today()

    @staticmethod
    def can_renew_membership(member):
        """
        Determine whether an existing member can renew.

        A membership number identifies an existing KUCSA member.
        """

        if not member:
            return False

        return bool(
            member.membership_number
        )

    # =========================================================
    # MEMBERSHIP NUMBER
    # =========================================================

    @staticmethod
    def generate_membership_number(member):
        """
        Generate a unique KUCSA membership number.

        Default format:

            KUCSA-00001

        Existing membership numbers are never replaced.
        """

        if not member:
            raise ValueError(
                "A valid member is required."
            )

        if member.membership_number:
            return member.membership_number

        if not member.pk:
            raise ValueError(
                "Member must be saved before generating "
                "a membership number."
            )

        base_number = (
            f"KUCSA-{member.pk:05d}"
        )

        membership_number = base_number
        counter = 1

        while Member.objects.filter(
            membership_number=membership_number
        ).exclude(
            pk=member.pk
        ).exists():

            membership_number = (
                f"{base_number}-{counter}"
            )

            counter += 1

        return membership_number

    # =========================================================
    # MEMBER CREATION
    # =========================================================

    @staticmethod
    @transaction.atomic
    def create_member(user, **data):
        """
        Create or retrieve a Member profile for a User.

        Normal members:

            PENDING
            ↓
            payment
            ↓
            payment verification
            ↓
            ACTIVE

        Administrators:

            automatically ACTIVE
            without payment.
        """

        if not user:
            raise ValueError(
                "A valid user is required."
            )

        member, created = Member.objects.get_or_create(
            user=user,
            defaults=data,
        )

        if not created and data:

            valid_fields = {
                field.name
                for field in Member._meta.fields
            }

            protected_fields = {
                "id",
                "user",
                "membership_number",
                "membership_status",
                "joined_date",
                "expiry_date",
                "created_at",
                "updated_at",
            }

            for field, value in data.items():

                if (
                    field in valid_fields
                    and field not in protected_fields
                ):

                    setattr(
                        member,
                        field,
                        value,
                    )

        # -----------------------------------------------------
        # ADMINISTRATOR
        # -----------------------------------------------------

        if MemberService.is_administrator(user):

            member = (
                MemberService
                ._activate_administrator_membership(
                    member
                )
            )

            MemberService.set_user_verified(
                user,
                True,
            )

            return member

        # -----------------------------------------------------
        # NORMAL MEMBER
        # -----------------------------------------------------

        if not member.membership_status:

            member.membership_status = (
                Member.MembershipStatus.PENDING
            )

        member.save()

        return member

    # =========================================================
    # ADMINISTRATOR MEMBERSHIP
    # =========================================================

    @staticmethod
    @transaction.atomic
    def _activate_administrator_membership(member):
        """
        Activate an administrator without payment.

        Administrators receive:

            - membership number
            - ACTIVE status
            - joined date
            - expiry date
            - verified account
        """

        if not member:
            raise ValueError(
                "A valid member is required."
            )

        today = date.today()

        if not member.membership_number:

            member.membership_number = (
                MemberService.generate_membership_number(
                    member
                )
            )

        member.membership_status = (
            Member.MembershipStatus.ACTIVE
        )

        if not member.joined_date:

            member.joined_date = today

        if (
            not member.expiry_date
            or member.expiry_date < today
        ):

            member.expiry_date = (
                MemberService.get_membership_expiry_date(
                    today
                )
            )

        member.save()

        MemberService.set_user_verified(
            member.user,
            True,
        )

        return member

    @staticmethod
    @transaction.atomic
    def activate_administrator_memberships():
        """
        Activate every administrator membership.

        Returns:
            Number of administrator memberships processed.
        """

        administrators = (
            Member.objects
            .select_related("user")
            .filter(
                Q(user__role=User.Role.ADMIN)
                | Q(user__is_staff=True)
                | Q(user__is_superuser=True)
            )
            .distinct()
        )

        activated_count = 0

        for member in administrators:

            MemberService._activate_administrator_membership(
                member
            )

            activated_count += 1

        return activated_count

    # =========================================================
    # MEMBER UPDATE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def update_member(member, **data):
        """
        Safely update profile information.

        Membership lifecycle fields cannot be modified through
        this method.
        """

        if not member:
            raise ValueError(
                "A valid member is required."
            )

        valid_fields = {
            field.name
            for field in Member._meta.fields
        }

        protected_fields = {
            "id",
            "user",
            "membership_number",
            "membership_status",
            "joined_date",
            "expiry_date",
            "created_at",
            "updated_at",
        }

        for field, value in data.items():

            if (
                field in valid_fields
                and field not in protected_fields
            ):

                setattr(
                    member,
                    field,
                    value,
                )

        member.save()

        return member

    # =========================================================
    # MEMBER RETRIEVAL
    # =========================================================

    @staticmethod
    def get_member(user):
        """Get a member profile by User."""

        if not user:
            return None

        try:

            return (
                Member.objects
                .select_related("user")
                .get(user=user)
            )

        except Member.DoesNotExist:

            return None

    @staticmethod
    def get_or_create_member(user):
        """
        Retrieve a member or create a basic profile.

        This is useful for authenticated users whose Member
        profile has not yet been created.
        """

        if not user:
            return None

        member = MemberService.get_member(user)

        if member:
            return member

        return MemberService.create_member(user)

    @staticmethod
    def get_member_by_id(member_id):
        """Get member by primary key."""

        if not member_id:
            return None

        try:

            return (
                Member.objects
                .select_related("user")
                .get(pk=member_id)
            )

        except Member.DoesNotExist:

            return None

    @staticmethod
    def get_member_by_registration_number(
        registration_number,
    ):
        """Get member using university registration number."""

        if not registration_number:
            return None

        registration_number = (
            str(registration_number).strip()
        )

        if not registration_number:
            return None

        try:

            return (
                Member.objects
                .select_related("user")
                .get(
                    user__registration_number=(
                        registration_number
                    )
                )
            )

        except Member.DoesNotExist:

            return None

    @staticmethod
    def get_member_by_membership_number(
        membership_number,
    ):
        """Get member using KUCSA membership number."""

        if not membership_number:
            return None

        membership_number = (
            str(membership_number)
            .strip()
            .upper()
        )

        if not membership_number:
            return None

        try:

            return (
                Member.objects
                .select_related("user")
                .get(
                    membership_number=membership_number
                )
            )

        except Member.DoesNotExist:

            return None

    # =========================================================
    # SEARCH
    # =========================================================

    @staticmethod
    def search_members(query):
        """
        Search members by:

            - first name
            - last name
            - username
            - registration number
            - membership number
            - email
            - course
        """

        queryset = (
            Member.objects
            .select_related("user")
        )

        if not query:
            return queryset

        query = str(query).strip()

        if not query:
            return queryset

        return queryset.filter(
            Q(
                user__first_name__icontains=query
            )
            | Q(
                user__last_name__icontains=query
            )
            | Q(
                user__username__icontains=query
            )
            | Q(
                user__registration_number__icontains=query
            )
            | Q(
                membership_number__icontains=query
            )
            | Q(
                user__email__icontains=query
            )
            | Q(
                course__icontains=query
            )
        ).distinct()

    # =========================================================
    # ACCOUNT VERIFICATION
    # =========================================================

    @staticmethod
    def get_verified_members():
        """
        Return members whose User account is verified.
        """

        return (
            Member.objects
            .select_related("user")
            .filter(
                user__is_verified=True
            )
        )

    @staticmethod
    def get_pending_members():
        """
        Return members whose User account is not verified.

        This is retained for backwards compatibility.

        For actual membership workflow, prefer:

            get_pending_memberships()
        """

        return (
            Member.objects
            .select_related("user")
            .filter(
                user__is_verified=False
            )
        )

    # =========================================================
    # ROLES
    # =========================================================

    @staticmethod
    def get_students():
        """Return student members."""

        return (
            Member.objects
            .select_related("user")
            .filter(
                user__role=User.Role.STUDENT
            )
        )

    @staticmethod
    def get_executives():
        """Return KUCSA executive members."""

        return (
            Member.objects
            .select_related("user")
            .filter(
                user__role__in=(
                    MemberService.EXECUTIVE_ROLES
                )
            )
        )

    @staticmethod
    def get_members_by_role(role):
        """Return members with a specific User role."""

        if not role:
            return Member.objects.none()

        return (
            Member.objects
            .select_related("user")
            .filter(
                user__role=role
            )
        )

    # =========================================================
    # MEMBERSHIP STATUS QUERIES
    # =========================================================

    @staticmethod
    def get_active_members():
        """
        Return genuinely active memberships.

        Expired ACTIVE records are not included.
        """

        today = date.today()

        return (
            Member.objects
            .select_related("user")
            .filter(
                membership_status=(
                    Member.MembershipStatus.ACTIVE
                ),
                expiry_date__gte=today,
            )
        )

    @staticmethod
    def get_pending_memberships():
        """
        Return normal members waiting for payment or
        payment verification.

        Administrators are excluded.
        """

        return (
            Member.objects
            .select_related("user")
            .filter(
                membership_status=(
                    Member.MembershipStatus.PENDING
                )
            )
            .exclude(
                Q(user__role=User.Role.ADMIN)
                | Q(user__is_staff=True)
                | Q(user__is_superuser=True)
            )
        )

    @staticmethod
    def get_suspended_members():
        """Return suspended members."""

        return (
            Member.objects
            .select_related("user")
            .filter(
                membership_status=(
                    Member.MembershipStatus.SUSPENDED
                )
            )
        )

    @staticmethod
    def get_expired_members():
        """
        Return memberships that are expired either because
        their status is EXPIRED or because their expiry date
        has passed.
        """

        today = date.today()

        return (
            Member.objects
            .select_related("user")
            .filter(
                Q(
                    membership_status=(
                        Member.MembershipStatus.EXPIRED
                    )
                )
                | Q(
                    expiry_date__lt=today
                )
            )
            .distinct()
        )

    @staticmethod
    def get_rejected_members():
        """Return rejected memberships."""

        return (
            Member.objects
            .select_related("user")
            .filter(
                membership_status=(
                    Member.MembershipStatus.REJECTED
                )
            )
        )

    # =========================================================
    # TECHNICAL DOMAINS
    # =========================================================

    @staticmethod
    def get_members_by_technical_domain(domain):
        """
        Return members associated with a technical domain.

        Assumes technical_domains is stored in a searchable
        Django field such as JSONField/TextField.
        """

        if not domain:
            return Member.objects.none()

        return (
            Member.objects
            .select_related("user")
            .filter(
                technical_domains__icontains=(
                    str(domain).strip()
                )
            )
        )

    @staticmethod
    def get_members_by_technical_level(level):
        """Return members at a specific technical level."""

        if not level:
            return Member.objects.none()

        return (
            Member.objects
            .select_related("user")
            .filter(
                technical_level=level
            )
        )

    # =========================================================
    # PROFILE COMPLETENESS
    # =========================================================

    @staticmethod
    def get_complete_profiles():
        """Return members with complete profiles."""

        return (
            Member.objects
            .select_related("user")
            .filter(
                is_profile_complete=True
            )
        )

    @staticmethod
    def get_incomplete_profiles():
        """Return members with incomplete profiles."""

        return (
            Member.objects
            .select_related("user")
            .filter(
                is_profile_complete=False
            )
        )

    @staticmethod
    @transaction.atomic
    def check_profile_completeness(member):
        """
        Calculate and save profile completeness.

        This does NOT affect membership activation.
        """

        if not member:
            return False

        user = member.user

        required_fields = [
            user.first_name,
            user.last_name,
            user.email,
            user.registration_number,
            member.course,
            member.year_of_study,
            member.bio,
            member.technical_level,
        ]

        complete = all(
            value not in [None, ""]
            for value in required_fields
        )

        member.is_profile_complete = complete

        member.save(
            update_fields=[
                "is_profile_complete",
                "updated_at",
            ]
        )

        return complete

    # =========================================================
    # MEMBERSHIP ACTIVATION
    # =========================================================

    @staticmethod
    @transaction.atomic
    def activate_member(
        member,
        membership_number=None,
        duration_months=None,
    ):
        """
        Activate a normal KUCSA member after successful
        payment verification.

        This method MUST be called only after PaymentService
        has verified a successful registration payment.

        Lifecycle:

            PENDING
                ↓
            payment verified
                ↓
            activate_member()
                ↓
            ACTIVE
                ↓
            membership number assigned
                ↓
            expiry date assigned
                ↓
            user verified
        """

        if not member:
            raise ValueError(
                "A valid member is required."
            )

        # Administrators should use the dedicated
        # administrator activation workflow.
        if MemberService.is_administrator(
            member.user
        ):

            return (
                MemberService
                ._activate_administrator_membership(
                    member
                )
            )

        if duration_months is None:
            duration_months = (
                MemberService.MEMBERSHIP_DURATION_MONTHS
            )

        if duration_months <= 0:
            raise ValueError(
                "Membership duration must be greater than zero."
            )

        # -----------------------------------------------------
        # MEMBERSHIP NUMBER
        # -----------------------------------------------------

        if member.membership_number:

            final_membership_number = (
                member.membership_number
            )

        elif membership_number:

            final_membership_number = (
                str(membership_number)
                .strip()
                .upper()
            )

            if not final_membership_number:

                final_membership_number = (
                    MemberService.generate_membership_number(
                        member
                    )
                )

        else:

            final_membership_number = (
                MemberService.generate_membership_number(
                    member
                )
            )

        # -----------------------------------------------------
        # DUPLICATE MEMBERSHIP NUMBER PROTECTION
        # -----------------------------------------------------

        if Member.objects.filter(
            membership_number=final_membership_number
        ).exclude(
            pk=member.pk
        ).exists():

            raise ValueError(
                "The membership number is already assigned "
                "to another member."
            )

        today = date.today()

        member.membership_number = (
            final_membership_number
        )

        member.membership_status = (
            Member.MembershipStatus.ACTIVE
        )

        if not member.joined_date:

            member.joined_date = today

        member.expiry_date = (
            MemberService.get_membership_expiry_date(
                today,
                duration_months,
            )
        )

        member.save()

        # -----------------------------------------------------
        # VERIFY ACCOUNT
        # -----------------------------------------------------

        MemberService.set_user_verified(
            member.user,
            True,
        )

        # Keep profile completeness independent from payment.
        MemberService.check_profile_completeness(
            member
        )

        return member

    # =========================================================
    # MEMBERSHIP SUSPENSION
    # =========================================================

    @staticmethod
    @transaction.atomic
    def suspend_member(member):
        """
        Suspend membership and disable account verification.
        """

        if not member:
            raise ValueError(
                "A valid member is required."
            )

        if MemberService.is_administrator(
            member.user
        ):

            raise ValueError(
                "Administrator membership cannot be suspended."
            )

        member.membership_status = (
            Member.MembershipStatus.SUSPENDED
        )

        member.save(
            update_fields=[
                "membership_status",
                "updated_at",
            ]
        )

        MemberService.set_user_verified(
            member.user,
            False,
        )

        return member

    # =========================================================
    # MEMBERSHIP REJECTION
    # =========================================================

    @staticmethod
    @transaction.atomic
    def reject_member(member):
        """
        Reject membership and disable account verification.
        """

        if not member:
            raise ValueError(
                "A valid member is required."
            )

        if MemberService.is_administrator(
            member.user
        ):

            raise ValueError(
                "Administrator membership cannot be rejected."
            )

        member.membership_status = (
            Member.MembershipStatus.REJECTED
        )

        member.save(
            update_fields=[
                "membership_status",
                "updated_at",
            ]
        )

        MemberService.set_user_verified(
            member.user,
            False,
        )

        return member

    # =========================================================
    # MEMBERSHIP EXPIRY
    # =========================================================

    @staticmethod
    @transaction.atomic
    def expire_memberships():
        """
        Automatically expire memberships whose expiry date
        has passed.

        Also marks the associated User as unverified.

        Returns:
            Number of memberships expired.
        """

        today = date.today()

        expired_members = list(
            Member.objects
            .select_related("user")
            .filter(
                membership_status=(
                    Member.MembershipStatus.ACTIVE
                ),
                expiry_date__lt=today,
            )
        )

        if not expired_members:
            return 0

        member_ids = [
            member.pk
            for member in expired_members
        ]

        updated_count = (
            Member.objects
            .filter(pk__in=member_ids)
            .update(
                membership_status=(
                    Member.MembershipStatus.EXPIRED
                ),
                updated_at=timezone.now(),
            )
        )

        # Keep account verification synchronized.
        user_ids = [
            member.user_id
            for member in expired_members
        ]

        User.objects.filter(
            pk__in=user_ids,
            is_verified=True,
        ).update(
            is_verified=False
        )

        return updated_count

    # =========================================================
    # MEMBERSHIP RENEWAL
    # =========================================================

    @staticmethod
    @transaction.atomic
    def renew_membership(
        member,
        duration_months=None,
    ):
        """
        Renew an existing KUCSA membership after successful
        renewal payment verification.

        Rules:

            Active membership:
                existing expiry date + duration

            Expired membership:
                today + duration

            Suspended membership:
                today + duration

            Rejected membership:
                should normally complete a new registration
                process unless business rules explicitly allow
                renewal.

        Membership number is always preserved.
        """

        if not member:
            raise ValueError(
                "A valid member is required."
            )

        if not member.membership_number:

            raise ValueError(
                "Only an existing KUCSA member can renew. "
                "A new member must complete registration."
            )

        if MemberService.is_administrator(
            member.user
        ):

            return (
                MemberService
                ._activate_administrator_membership(
                    member
                )
            )

        if duration_months is None:

            duration_months = (
                MemberService.MEMBERSHIP_DURATION_MONTHS
            )

        if duration_months <= 0:

            raise ValueError(
                "Membership duration must be greater than zero."
            )

        today = date.today()

        # -----------------------------------------------------
        # Determine renewal starting point
        # -----------------------------------------------------

        if (
            member.expiry_date
            and member.expiry_date >= today
        ):

            start_date = member.expiry_date

        else:

            start_date = today

        # -----------------------------------------------------
        # Activate membership
        # -----------------------------------------------------

        member.membership_status = (
            Member.MembershipStatus.ACTIVE
        )

        member.expiry_date = (
            MemberService.add_months(
                start_date,
                duration_months,
            )
        )

        if not member.joined_date:

            member.joined_date = today

        member.save()

        # -----------------------------------------------------
        # Reactivate verified account
        # -----------------------------------------------------

        MemberService.set_user_verified(
            member.user,
            True,
        )

        MemberService.check_profile_completeness(
            member
        )

        return member

    # =========================================================
    # MEMBERSHIP ACTION
    # =========================================================

    @staticmethod
    def get_membership_action(member):
        """
        Determine the next membership action.

        Possible results:

            REGISTER
            RENEW
            ACTIVE
            PENDING
            SUSPENDED
            REJECTED
        """

        if not member:
            return "REGISTER"

        # -----------------------------------------------------
        # ACTIVE
        # -----------------------------------------------------

        if (
            member.membership_status
            == Member.MembershipStatus.ACTIVE
        ):

            if MemberService.is_membership_expired(
                member
            ):

                return "RENEW"

            return "ACTIVE"

        # -----------------------------------------------------
        # PENDING
        # -----------------------------------------------------

        if (
            member.membership_status
            == Member.MembershipStatus.PENDING
        ):

            return "PENDING"

        # -----------------------------------------------------
        # SUSPENDED
        # -----------------------------------------------------

        if (
            member.membership_status
            == Member.MembershipStatus.SUSPENDED
        ):

            return "SUSPENDED"

        # -----------------------------------------------------
        # REJECTED
        # -----------------------------------------------------

        if (
            member.membership_status
            == Member.MembershipStatus.REJECTED
        ):

            return "REJECTED"

        # -----------------------------------------------------
        # EXPIRED
        # -----------------------------------------------------

        if (
            member.membership_status
            == Member.MembershipStatus.EXPIRED
        ):

            return "RENEW"

        # -----------------------------------------------------
        # EXISTING MEMBER
        # -----------------------------------------------------

        if member.membership_number:

            return "RENEW"

        return "REGISTER"

    # =========================================================
    # MEMBERSHIP INFORMATION
    # =========================================================

    @staticmethod
    def get_membership_information(member):
        """
        Return a normalized membership-information dictionary.

        Designed for:

            - dashboards
            - templates
            - payment pages
            - member profile pages
            - APIs
        """

        if not member:

            return {
                "exists": False,
                "action": "REGISTER",
                "membership_number": None,
                "status": (
                    Member.MembershipStatus.PENDING
                ),
                "joined_date": None,
                "expiry_date": None,
                "registration_fee": (
                    MemberService.REGISTRATION_FEE
                ),
                "renewal_fee": (
                    MemberService.RENEWAL_FEE
                ),
                "current_fee": (
                    MemberService.REGISTRATION_FEE
                ),
                "duration_months": (
                    MemberService.MEMBERSHIP_DURATION_MONTHS
                ),
                "is_active": False,
                "is_expired": False,
                "can_renew": False,
                "is_new_member": True,
            }

        action = (
            MemberService.get_membership_action(
                member
            )
        )

        if action == "REGISTER":

            current_fee = (
                MemberService.REGISTRATION_FEE
            )

        else:

            current_fee = (
                MemberService.RENEWAL_FEE
            )

        return {
            "exists": True,
            "action": action,
            "membership_number": (
                member.membership_number
            ),
            "status": (
                member.membership_status
            ),
            "joined_date": (
                member.joined_date
            ),
            "expiry_date": (
                member.expiry_date
            ),
            "registration_fee": (
                MemberService.REGISTRATION_FEE
            ),
            "renewal_fee": (
                MemberService.RENEWAL_FEE
            ),
            "current_fee": current_fee,
            "duration_months": (
                MemberService.MEMBERSHIP_DURATION_MONTHS
            ),
            "is_active": (
                MemberService.is_membership_active(
                    member
                )
            ),
            "is_expired": (
                MemberService.is_membership_expired(
                    member
                )
            ),
            "can_renew": (
                MemberService.can_renew_membership(
                    member
                )
            ),
            "is_new_member": (
                MemberService.is_new_member(
                    member
                )
            ),
        }

    # =========================================================
    # MEMBERSHIP STATISTICS
    # =========================================================

    @staticmethod
    def get_membership_statistics():
        """
        Return comprehensive KUCSA membership statistics.
        """

        total = Member.objects.count()

        active = (
            MemberService
            .get_active_members()
            .count()
        )

        pending = (
            MemberService
            .get_pending_memberships()
            .count()
        )

        suspended = (
            MemberService
            .get_suspended_members()
            .count()
        )

        expired = (
            MemberService
            .get_expired_members()
            .count()
        )

        rejected = (
            MemberService
            .get_rejected_members()
            .count()
        )

        verified = (
            Member.objects
            .filter(
                user__is_verified=True
            )
            .count()
        )

        unverified = (
            Member.objects
            .filter(
                user__is_verified=False
            )
            .count()
        )

        students = (
            Member.objects
            .filter(
                user__role=User.Role.STUDENT
            )
            .count()
        )

        executives = (
            MemberService
            .get_executives()
            .count()
        )

        administrators = (
            Member.objects
            .filter(
                Q(user__role=User.Role.ADMIN)
                | Q(user__is_staff=True)
                | Q(user__is_superuser=True)
            )
            .distinct()
            .count()
        )

        complete_profiles = (
            MemberService
            .get_complete_profiles()
            .count()
        )

        incomplete_profiles = (
            MemberService
            .get_incomplete_profiles()
            .count()
        )

        return {
            "total": total,
            "active": active,
            "pending": pending,
            "suspended": suspended,
            "expired": expired,
            "rejected": rejected,
            "verified": verified,
            "unverified": unverified,
            "students": students,
            "executives": executives,
            "administrators": administrators,
            "complete_profiles": complete_profiles,
            "incomplete_profiles": incomplete_profiles,
            "registration_fee": (
                MemberService.REGISTRATION_FEE
            ),
            "renewal_fee": (
                MemberService.RENEWAL_FEE
            ),
            "membership_duration_months": (
                MemberService.MEMBERSHIP_DURATION_MONTHS
            ),
        }

    # =========================================================
    # COUNTS
    # =========================================================

    @staticmethod
    def get_member_count():
        """Return total number of member profiles."""

        return Member.objects.count()

    @staticmethod
    def get_active_member_count():
        """Return genuinely active member count."""

        return (
            MemberService
            .get_active_members()
            .count()
        )

    # =========================================================
    # UPCOMING EXPIRIES
    # =========================================================

    @staticmethod
    def get_memberships_expiring_soon(days=30):
        """
        Return active memberships expiring within the
        specified number of days.
        """

        if days < 0:
            raise ValueError(
                "Number of days cannot be negative."
            )

        today = date.today()

        expiry_limit = (
            today
            + timedelta(days=days)
        )

        return (
            Member.objects
            .select_related("user")
            .filter(
                membership_status=(
                    Member.MembershipStatus.ACTIVE
                ),
                expiry_date__gte=today,
                expiry_date__lte=expiry_limit,
            )
            .order_by(
                "expiry_date"
            )
        )

    # =========================================================
    # MEMBERSHIP VALIDATION
    # =========================================================

    @staticmethod
    def validate_membership(member):
        """
        Perform a basic consistency check on a member.

        Returns a dictionary useful for administrative
        dashboards and debugging.
        """

        if not member:

            return {
                "valid": False,
                "errors": [
                    "Member does not exist."
                ],
            }

        errors = []

        # -----------------------------------------------------
        # ACTIVE MEMBERS
        # -----------------------------------------------------

        if (
            member.membership_status
            == Member.MembershipStatus.ACTIVE
        ):

            if not member.membership_number:

                errors.append(
                    "Active member has no membership number."
                )

            if not member.joined_date:

                errors.append(
                    "Active member has no joined date."
                )

            if not member.expiry_date:

                errors.append(
                    "Active member has no expiry date."
                )

            if (
                member.expiry_date
                and member.expiry_date < date.today()
            ):

                errors.append(
                    "Membership is marked ACTIVE but has expired."
                )

        # -----------------------------------------------------
        # NON-ACTIVE MEMBERS
        # -----------------------------------------------------

        if (
            member.membership_status
            != Member.MembershipStatus.ACTIVE
            and member.user.is_verified
            and not MemberService.is_administrator(
                member.user
            )
        ):

            errors.append(
                "Non-active member has a verified account."
            )

        return {
            "valid": not errors,
            "errors": errors,
        }

    # =========================================================
    # SYNCHRONIZE MEMBERSHIP STATES
    # =========================================================

    @staticmethod
    @transaction.atomic
    def synchronize_membership_states():
        """
        Synchronize membership records with account
        verification and expiry dates.

        This is useful for a scheduled task/management
        command.

        Operations:

            1. Expire overdue active memberships.
            2. Unverify expired users.
            3. Keep administrators active and verified.

        Returns a summary dictionary.
        """

        expired_count = (
            MemberService.expire_memberships()
        )

        administrator_count = (
            MemberService
            .activate_administrator_memberships()
        )

        return {
            "expired": expired_count,
            "administrators_synchronized": (
                administrator_count
            ),
        }