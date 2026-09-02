
# accounts/services.py

from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from members.models import Member


User = get_user_model()


class UserService:
    """
    Handles all user-related business logic for the
    KUCSA Digital Computing Community Platform.

    Registration and membership follow this flow:

        Account Created
              ↓
        Member Profile Created
              ↓
        Membership Status = PENDING
              ↓
        User Logs In
              ↓
        Membership Payment Required
              ↓
        M-Pesa STK Push
              ↓
        Payment COMPLETED
              ↓
        Membership ACTIVE
              ↓
        Platform Access Granted

    IMPORTANT:

    Creating a user does NOT activate membership.

    A Member profile is created immediately with PENDING status
    so that the payment system has a valid member to associate
    the payment with.

    Membership activation happens only after successful
    M-Pesa payment confirmation.
    """

    # =========================================================
    # CREATE USER
    # =========================================================

    @staticmethod
    @transaction.atomic
    def create_user(form):
        """
        Create a new KUCSA user account and its Member profile.

        Registration creates TWO related records:

            1. User
            2. Member

        The Member starts with:

            membership_status = PENDING

        The member is NOT activated at registration.

        This is important because the user must first pay the
        KUCSA membership fee before accessing the platform.

        Returns:
            User instance.
        """

        if not form.is_valid():
            raise ValidationError(form.errors)

        # -----------------------------------------------------
        # CREATE USER
        # -----------------------------------------------------

        user = form.save(commit=False)

        # New users must be able to log in so they can
        # complete the membership payment process.
        user.is_active = True

        # Verification is completed as part of the successful
        # membership/payment workflow.
        user.is_verified = False

        # New registrations are students by default.
        if not user.role:
            user.role = User.Role.STUDENT

        user.save()

        # -----------------------------------------------------
        # CREATE MEMBER PROFILE
        # -----------------------------------------------------

        # A Member profile MUST exist immediately after
        # registration.
        #
        # This prevents:
        #
        #     User exists
        #          ↓
        #     Member missing
        #          ↓
        #     Payment page cannot find member
        #          ↓
        #     Redirect to profile
        #          ↓
        #     Redirect back to payment
        #
        # The OneToOne relationship guarantees that one
        # membership profile belongs to one user.

        Member.objects.get_or_create(
            user=user,
            defaults={
                "membership_status": (
                    Member.MembershipStatus.PENDING
                ),
            },
        )

        return user

    # =========================================================
    # AUTHENTICATE USER
    # =========================================================

    @staticmethod
    def authenticate_user(username, password):
        """
        Authenticate a user using username and password.

        Returns:
            User instance if authentication succeeds.
            None if authentication fails.
        """

        return authenticate(
            username=username,
            password=password,
        )

    # =========================================================
    # UPDATE PROFILE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def update_profile(user, form):
        """
        Update an existing user's account/profile information.

        The form must already be associated with the user
        instance.
        """

        if not form.is_valid():
            raise ValidationError(form.errors)

        updated_user = form.save()

        return updated_user

    # =========================================================
    # CHANGE PASSWORD
    # =========================================================

    @staticmethod
    @transaction.atomic
    def change_password(user, form):
        """
        Change the user's password using a validated
        password-change form.
        """

        if not form.is_valid():
            raise ValidationError(form.errors)

        updated_user = form.save()

        return updated_user

    # =========================================================
    # GET USER BY ID
    # =========================================================

    @staticmethod
    def get_user_by_id(user_id):
        """
        Return a user by primary key.

        Returns:
            User instance or None.
        """

        return User.objects.filter(
            pk=user_id
        ).first()

    # =========================================================
    # GET USER BY REGISTRATION NUMBER
    # =========================================================

    @staticmethod
    def get_user_by_registration_number(
        registration_number,
    ):
        """
        Return a user using the KUCSA registration number.

        Returns:
            User instance or None.
        """

        return User.objects.filter(
            registration_number=registration_number
        ).first()

    # =========================================================
    # GET USER BY EMAIL
    # =========================================================

    @staticmethod
    def get_user_by_email(email):
        """
        Return a user using their email address.

        Returns:
            User instance or None.
        """

        return User.objects.filter(
            email__iexact=email
        ).first()

    # =========================================================
    # GET USER BY USERNAME
    # =========================================================

    @staticmethod
    def get_user_by_username(username):
        """
        Return a user using their username.

        Returns:
            User instance or None.
        """

        return User.objects.filter(
            username=username
        ).first()

    # =========================================================
    # GET OR CREATE MEMBER PROFILE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def get_or_create_member(user):
        """
        Return the Member profile belonging to a user.

        If the user does not yet have a Member profile, one is
        created with PENDING membership status.

        This method is intentionally safe to use for older
        accounts that may have been created before the Member
        profile was automatically created during registration.

        Returns:
            Member instance.
        """

        member, created = Member.objects.get_or_create(
            user=user,
            defaults={
                "membership_status": (
                    Member.MembershipStatus.PENDING
                ),
            },
        )

        # -----------------------------------------------------
        # SAFETY NORMALIZATION
        # -----------------------------------------------------

        # If an old Member record exists without a valid
        # membership status, keep it in the payment-required
        # state rather than accidentally granting access.
        if not member.membership_status:
            member.membership_status = (
                Member.MembershipStatus.PENDING
            )

            member.save(
                update_fields=[
                    "membership_status",
                    "updated_at",
                ]
            )

        return member

    # =========================================================
    # ACTIVATE USER
    # =========================================================

    @staticmethod
    @transaction.atomic
    def activate_user(user):
        """
        Activate a user account.

        Account activation is separate from membership activation.

        A user must be active in order to log in and complete
        the membership payment process.
        """

        if not user.is_active:
            user.is_active = True

            user.save(
                update_fields=[
                    "is_active",
                    "updated_at",
                ]
            )

        return user

    # =========================================================
    # DEACTIVATE USER
    # =========================================================

    @staticmethod
    @transaction.atomic
    def deactivate_user(user):
        """
        Deactivate a user account.

        This does not delete the user's membership record.
        """

        if user.is_active:
            user.is_active = False

            user.save(
                update_fields=[
                    "is_active",
                    "updated_at",
                ]
            )

        return user

    # =========================================================
    # VERIFY USER
    # =========================================================

    @staticmethod
    @transaction.atomic
    def verify_user(user):
        """
        Mark a user's account as verified.

        This can be used for account/email verification.

        Successful membership payment also verifies the user
        through Member.activate_membership().
        """

        if not user.is_verified:

            user.is_verified = True

            user.save(
                update_fields=[
                    "is_verified",
                    "updated_at",
                ]
            )

        return user

    # =========================================================
    # UNVERIFY USER
    # =========================================================

    @staticmethod
    @transaction.atomic
    def unverify_user(user):
        """
        Mark a user's account as unverified.
        """

        if user.is_verified:

            user.is_verified = False

            user.save(
                update_fields=[
                    "is_verified",
                    "updated_at",
                ]
            )

        return user

    # =========================================================
    # CHANGE USER ROLE
    # =========================================================

    @staticmethod
    @transaction.atomic
    def change_user_role(user, role):
        """
        Assign a new KUCSA role to a user.

        Valid roles are taken directly from User.Role.
        """

        valid_roles = {
            choice[0]
            for choice in User.Role.choices
        }

        if role not in valid_roles:
            raise ValidationError(
                {
                    "role": (
                        "Invalid KUCSA user role."
                    )
                }
            )

        user.role = role

        user.save(
            update_fields=[
                "role",
                "updated_at",
            ]
        )

        return user

    # =========================================================
    # DELETE USER
    # =========================================================

    @staticmethod
    @transaction.atomic
    def delete_user(user):
        """
        Permanently delete a user account.

        Related objects using CASCADE will be removed according
        to the model relationships.
        """

        user.delete()

    # =========================================================
    # CHECK ACCOUNT ACCESS
    # =========================================================

    @staticmethod
    def can_login(user):
        """
        Determine whether a user account is allowed to log in.

        IMPORTANT:

        A user does NOT need an active membership to log in.

        They must be able to log in first so they can reach
        the membership payment page.

        Membership access is controlled separately by the
        Member.can_access_platform property.
        """

        if user is None:
            return False

        if not user.is_active:
            return False

        return True

    # =========================================================
    # GET EXECUTIVES
    # =========================================================

    @staticmethod
    def get_executives():
        """
        Return all KUCSA executive users.
        """

        executive_roles = [
            User.Role.CHAIRPERSON,
            User.Role.VICE_CHAIRPERSON,
            User.Role.SECRETARY,
            User.Role.SECRETARY_GENERAL,
            User.Role.TREASURER,
            User.Role.ORGANIZING_SECRETARY,
            User.Role.PUBLICITY_SECRETARY,
        ]

        return (
            User.objects
            .filter(role__in=executive_roles)
            .order_by(
                "first_name",
                "last_name",
            )
        )

    # =========================================================
    # GET ADMINISTRATORS
    # =========================================================

    @staticmethod
    def get_administrators():
        """
        Return all KUCSA administrator users.
        """

        return (
            User.objects
            .filter(role=User.Role.ADMIN)
            .order_by(
                "first_name",
                "last_name",
            )
        )
