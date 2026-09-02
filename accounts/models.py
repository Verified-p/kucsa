
# accounts/models.py

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
    """
    Custom User model for the KUCSA Digital Computing
    Community Platform.

    =========================================================
    ACCOUNT ARCHITECTURE
    =========================================================

    Django administration permissions are separate from
    KUCSA organizational roles.

    Django permissions:

        is_staff
        is_superuser
        groups
        user_permissions

    KUCSA organizational roles:

        STUDENT
        CHAIRPERSON
        VICE_CHAIRPERSON
        SECRETARY
        SECRETARY_GENERAL
        TREASURER
        ORGANIZING_SECRETARY
        PUBLICITY_SECRETARY
        ADMIN

    IMPORTANT
    ---------

    A KUCSA executive is still a KUCSA member.

    Therefore:

        Executive
            ↓
        Active KUCSA membership
            ↓
        Successful membership payment
            ↓
        Administrator assigns executive role

    Only KUCSA administrators are exempt from membership
    payment requirements.

    Django superusers are treated as administrative accounts.

    FINANCE ACCESS
    --------------

    Finance management is restricted to:

        1. KUCSA ADMIN
        2. User explicitly assigned the TREASURER role

    Being an executive alone does NOT grant finance access.

    Therefore:

        STUDENT
            ↓
        Active Membership
            ↓
        Administrator assigns TREASURER role
            ↓
        TREASURER
            ↓
        Finance Management Access

    The TREASURER role must first be assigned through the
    existing authorized role-assignment process.
    """

    # =========================================================
    # USER ROLES
    # =========================================================

    class Role(models.TextChoices):

        STUDENT = (
            "STUDENT",
            "Student",
        )

        CHAIRPERSON = (
            "CHAIRPERSON",
            "Chairperson",
        )

        VICE_CHAIRPERSON = (
            "VICE_CHAIRPERSON",
            "Vice Chairperson",
        )

        SECRETARY = (
            "SECRETARY",
            "Secretary",
        )

        SECRETARY_GENERAL = (
            "SECRETARY_GENERAL",
            "Secretary General",
        )

        TREASURER = (
            "TREASURER",
            "Treasurer",
        )

        ORGANIZING_SECRETARY = (
            "ORGANIZING_SECRETARY",
            "Organizing Secretary",
        )

        PUBLICITY_SECRETARY = (
            "PUBLICITY_SECRETARY",
            "Publicity Secretary",
        )

        ADMIN = (
            "ADMIN",
            "Administrator",
        )

    # =========================================================
    # EXECUTIVE ROLES
    # =========================================================

    EXECUTIVE_ROLES = frozenset(
        {
            Role.CHAIRPERSON,
            Role.VICE_CHAIRPERSON,
            Role.SECRETARY,
            Role.SECRETARY_GENERAL,
            Role.TREASURER,
            Role.ORGANIZING_SECRETARY,
            Role.PUBLICITY_SECRETARY,
        }
    )

    # =========================================================
    # UNIVERSITY INFORMATION
    # =========================================================

    registration_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Registration Number",
        help_text=(
            "Official university registration number. "
            "Required for normal KUCSA student/member accounts "
            "but not required for administrative accounts."
        ),
    )

    # =========================================================
    # CONTACT INFORMATION
    # =========================================================

    email = models.EmailField(
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Email Address",
        help_text=(
            "Unique email address. Administrative accounts "
            "may exist without an email address."
        ),
    )

    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        verbose_name="Phone Number",
        help_text=(
            "Phone number used for KUCSA communication "
            "and M-Pesa payments."
        ),
    )

    # =========================================================
    # PROFILE
    # =========================================================

    profile_picture = models.ImageField(
        upload_to="profile_pictures/",
        blank=True,
        null=True,
        verbose_name="Profile Picture",
    )

    # =========================================================
    # KUCSA ROLE
    # =========================================================

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.STUDENT,
        db_index=True,
        verbose_name="KUCSA Role",
        help_text=(
            "Organizational role held by the user within KUCSA."
        ),
    )

    # =========================================================
    # ACCOUNT VERIFICATION
    # =========================================================

    is_verified = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Account Verified",
        help_text=(
            "Indicates whether the user's account has "
            "completed the required KUCSA verification process."
        ),
    )

    # =========================================================
    # TIMESTAMPS
    # =========================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At",
    )

    # =========================================================
    # AUTHENTICATION CONFIGURATION
    # =========================================================

    USERNAME_FIELD = "username"

    REQUIRED_FIELDS = []

    # =========================================================
    # META
    # =========================================================

    class Meta:
        ordering = [
            "first_name",
            "last_name",
        ]

        verbose_name = "User"
        verbose_name_plural = "Users"

        indexes = [
            models.Index(
                fields=["role"],
                name="user_role_idx",
            ),
            models.Index(
                fields=["is_verified"],
                name="user_verified_idx",
            ),
            models.Index(
                fields=["role", "is_verified"],
                name="user_role_verified_idx",
            ),
        ]

    # =========================================================
    # VALIDATION
    # =========================================================

    def clean(self):
        """
        Validate the KUCSA user configuration.

        Organizational role and Django administrative
        privileges are intentionally treated as separate
        concepts, but dangerous combinations are rejected.
        """

        super().clean()

        errors = {}

        # -----------------------------------------------------
        # REGISTRATION NUMBER
        # -----------------------------------------------------

        if self.registration_number:
            self.registration_number = (
                self.registration_number.strip().upper()
            )

        # -----------------------------------------------------
        # EMAIL
        # -----------------------------------------------------

        if self.email:
            self.email = self.email.strip().lower()

        # -----------------------------------------------------
        # PHONE NUMBER
        # -----------------------------------------------------

        if self.phone_number:
            self.phone_number = self.phone_number.strip()

        # -----------------------------------------------------
        # ROLE
        # -----------------------------------------------------

        valid_roles = {
            choice[0]
            for choice in self.Role.choices
        }

        if self.role not in valid_roles:
            errors["role"] = (
                f"Invalid KUCSA role: {self.role}"
            )

        # -----------------------------------------------------
        # EXECUTIVE ROLE
        # -----------------------------------------------------

        if self.role in self.EXECUTIVE_ROLES:

            if not self.pk:
                # Membership validation is completed by
                # assign_role() after the user exists.
                pass

        # -----------------------------------------------------
        # ADMIN ROLE
        # -----------------------------------------------------

        if self.role == self.Role.ADMIN:

            if not self.is_staff and not self.is_superuser:
                errors["role"] = (
                    "The ADMIN role requires Django "
                    "staff or superuser privileges."
                )

        if errors:
            raise ValidationError(errors)

    # =========================================================
    # SAVE
    # =========================================================

    def save(self, *args, **kwargs):
        """
        Normalize user data before saving.

        Empty unique values such as email and registration
        number are converted to NULL so that multiple
        administrative accounts can exist without those values.
        """

        # -----------------------------------------------------
        # NORMALIZE EMAIL
        # -----------------------------------------------------

        if self.email is not None:
            self.email = self.email.strip().lower()

            if not self.email:
                self.email = None

        # -----------------------------------------------------
        # NORMALIZE REGISTRATION NUMBER
        # -----------------------------------------------------

        if self.registration_number is not None:
            self.registration_number = (
                self.registration_number.strip().upper()
            )

            if not self.registration_number:
                self.registration_number = None

        # -----------------------------------------------------
        # NORMALIZE PHONE NUMBER
        # -----------------------------------------------------

        if self.phone_number is not None:
            self.phone_number = self.phone_number.strip()

            if not self.phone_number:
                self.phone_number = None

        # -----------------------------------------------------
        # ADMINISTRATIVE ACCOUNT
        # -----------------------------------------------------

        # Django superusers are always KUCSA administrators.
        #
        # This prevents an account such as:
        #
        #     role = STUDENT
        #     is_superuser = True
        #
        # from remaining in an inconsistent organizational state.

        if self.is_superuser:
            self.role = self.Role.ADMIN
            self.is_staff = True

        # -----------------------------------------------------
        # ADMIN ROLE
        # -----------------------------------------------------

        if self.role == self.Role.ADMIN:
            self.is_staff = True

        super().save(*args, **kwargs)

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        identity = (
            self.get_full_name()
            or self.username
            or self.email
            or "Unnamed User"
        )

        if self.registration_number:
            return (
                f"{self.registration_number} - "
                f"{identity}"
            )

        return identity

    # =========================================================
    # FULL NAME
    # =========================================================

    @property
    def full_name(self):
        """
        Return the user's full name.

        Falls back to username and then email.
        """

        return (
            self.get_full_name()
            or self.username
            or self.email
            or "Unnamed User"
        )

    # =========================================================
    # EXECUTIVE CHECK
    # =========================================================

    @property
    def is_executive(self):
        """
        Return True when the user holds a KUCSA
        executive position.

        Administrators are not considered executives simply
        because they have administrative privileges.
        """

        return self.role in self.EXECUTIVE_ROLES

    # =========================================================
    # TREASURER CHECK
    # =========================================================

    @property
    def is_treasurer(self):
        """
        Return True only when the user has explicitly been
        assigned the KUCSA TREASURER role.

        IMPORTANT
        ---------

        Being an executive does not make a user a treasurer.

        The user must first have:

            role = TREASURER

        through the authorized role-assignment process.
        """

        return self.role == self.Role.TREASURER

    # =========================================================
    # FINANCE MANAGEMENT ACCESS
    # =========================================================

    @property
    def can_manage_finance(self):
        """
        Return True when the user is authorized to manage
        KUCSA financial operations.

        Finance management is restricted to:

            1. KUCSA administrators
            2. The explicitly assigned Treasurer

        A Chairperson, Secretary, Secretary General, Vice
        Chairperson, Organizing Secretary, or Publicity
        Secretary does not automatically receive finance
        management access.

        The Treasurer must first be assigned the TREASURER
        organizational role by an authorized administrator.
        """

        return (
            self.is_kucsa_admin
            or self.is_treasurer
        )

    # =========================================================
    # STUDENT CHECK
    # =========================================================

    @property
    def is_student(self):
        """
        Return True when the user is an ordinary KUCSA student.
        """

        return self.role == self.Role.STUDENT

    # =========================================================
    # ADMIN CHECK
    # =========================================================

    @property
    def is_kucsa_admin(self):
        """
        Return True when the user is a KUCSA administrator.

        Django superusers are automatically considered
        administrators.
        """

        return (
            self.role == self.Role.ADMIN
            or self.is_superuser
            or (
                self.is_staff
                and self.role == self.Role.ADMIN
            )
        )

    # =========================================================
    # MANAGEMENT CHECK
    # =========================================================

    @property
    def is_management(self):
        """
        Return True when the user is either a KUCSA executive
        or administrator.
        """

        return (
            self.is_executive
            or self.is_kucsa_admin
        )

    # =========================================================
    # MEMBER PROFILE
    # =========================================================

    @property
    def member(self):
        """
        Return the associated KUCSA Member profile.

        Expected Member relationship:

            related_name="member_profile"
        """

        try:
            return self.member_profile

        except (
            AttributeError,
            self.__class__.member_profile.RelatedObjectDoesNotExist,
        ):
            return None

    # =========================================================
    # MEMBERSHIP CHECK
    # =========================================================

    @property
    def has_active_membership(self):
        """
        Return True when the user has valid active
        KUCSA membership.

        Administrators bypass the membership requirement.

        Executives do NOT bypass membership requirements.
        """

        if self.is_kucsa_admin:
            return True

        member = self.member

        if member is None:
            return False

        return member.can_access_platform

    # =========================================================
    # PLATFORM ACCESS
    # =========================================================

    @property
    def has_platform_access(self):
        """
        Determine whether the user can access protected
        KUCSA platform features.
        """

        if not self.is_active:
            return False

        return self.has_active_membership

    # =========================================================
    # PAYMENT REQUIRED
    # =========================================================

    @property
    def payment_required(self):
        """
        Return True when the user must complete membership
        payment before accessing protected platform features.
        """

        if self.is_kucsa_admin:
            return False

        return not self.has_platform_access

    # =========================================================
    # MEMBERSHIP STATUS
    # =========================================================

    @property
    def membership_status(self):
        """
        Return the current membership status.

        Returns None when no Member profile exists.
        """

        member = self.member

        if member is None:
            return None

        return member.membership_status

    # =========================================================
    # MEMBERSHIP NUMBER
    # =========================================================

    @property
    def membership_number(self):
        """
        Return the user's KUCSA membership number.
        """

        member = self.member

        if member is None:
            return None

        return member.membership_number

    # =========================================================
    # ACCOUNT STATUS
    # =========================================================

    @property
    def account_status(self):
        """
        Return the user's current account/membership state.
        """

        if not self.is_active:
            return "Account Disabled"

        if self.is_kucsa_admin:
            return "Administrator"

        member = self.member

        if member is None:
            return "Payment Required"

        if member.can_access_platform:
            return "Active Membership"

        if member.is_pending:

            if member.has_pending_payment:
                return "Payment Pending"

            return "Payment Required"

        if member.is_suspended:
            return "Membership Suspended"

        if member.is_expired:
            return "Membership Expired"

        return "Payment Required"

    # =========================================================
    # ACCOUNT PAYMENT STATE
    # =========================================================

    @property
    def payment_state(self):
        """
        Return a normalized membership/payment state.

        Possible values:

            REQUIRED
            PENDING
            ACTIVE
            SUSPENDED
            EXPIRED
        """

        if self.is_kucsa_admin:
            return "ACTIVE"

        member = self.member

        if member is None:
            return "REQUIRED"

        if member.can_access_platform:
            return "ACTIVE"

        if member.has_pending_payment:
            return "PENDING"

        if member.is_suspended:
            return "SUSPENDED"

        if member.is_expired:
            return "EXPIRED"

        return "REQUIRED"

    # =========================================================
    # VERIFICATION STATE
    # =========================================================

    @property
    def has_verified_access(self):
        """
        Backwards-compatible access property.

        Platform access is determined by valid membership,
        not merely by User.is_verified.
        """

        return self.has_platform_access

    # =========================================================
    # ROLE ASSIGNMENT
    # =========================================================

    def assign_role(self, role):
        """
        Assign a KUCSA organizational role.

        Rules:

        1. STUDENT can be assigned normally.
        2. Executive roles require active membership.
        3. TREASURER is treated as an executive role and
           therefore requires active KUCSA membership.
        4. ADMIN requires an authorized Django
           administrative account.

        IMPORTANT
        ---------

        The Treasurer does not receive finance access merely
        because they are a member or an executive.

        Finance access becomes available only after this method
        successfully assigns:

            role = TREASURER
        """

        valid_roles = {
            choice[0]
            for choice in self.Role.choices
        }

        if role not in valid_roles:
            raise ValidationError(
                f"Invalid KUCSA role: {role}"
            )

        # -----------------------------------------------------
        # ADMIN ROLE
        # -----------------------------------------------------

        if role == self.Role.ADMIN:

            if not (
                self.is_superuser
                or self.is_staff
            ):
                raise ValidationError(
                    "The ADMIN role can only be assigned "
                    "to an authorized Django administrator."
                )

        # -----------------------------------------------------
        # EXECUTIVE ROLE
        # -----------------------------------------------------

        elif role in self.EXECUTIVE_ROLES:

            member = self.member

            if member is None:
                raise ValidationError(
                    "An executive must have an existing "
                    "KUCSA Member profile."
                )

            if not member.can_access_platform:
                raise ValidationError(
                    "An executive role can only be assigned "
                    "to a member with active KUCSA membership."
                )

        # -----------------------------------------------------
        # STUDENT ROLE
        # -----------------------------------------------------

        elif role == self.Role.STUDENT:
            pass

        # -----------------------------------------------------
        # APPLY ROLE
        # -----------------------------------------------------

        self.role = role

        if role == self.Role.ADMIN:
            self.is_staff = True

        self.save(
            update_fields=[
                "role",
                "is_staff",
                "updated_at",
            ]
        )

        return self

    # =========================================================
    # ROLE LABEL
    # =========================================================

    @property
    def role_display(self):
        """
        Return the human-readable KUCSA role.
        """

        return self.get_role_display()
