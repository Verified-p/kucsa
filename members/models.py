
# members/models.py

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Member(models.Model):
    """
    KUCSA membership profile.

    Membership lifecycle:

        Account Created
              ↓
        Member Profile Created
              ↓
        Membership Payment Required
              ↓
        M-Pesa Payment
              ↓
        Payment Confirmed
              ↓
        Membership Activated
              ↓
        Platform Access Granted

    Payment processing belongs to the payments application.

    This model is responsible for:
        - Membership information
        - Academic/profile information
        - Technical skills and interests
        - Membership status
        - Membership activation
        - Membership expiry
        - Membership suspension
        - Platform access determination
        - Profile completion
    """

    # =========================================================
    # MEMBERSHIP STATUS
    # =========================================================

    class MembershipStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"
        EXPIRED = "EXPIRED", "Expired"

    # =========================================================
    # TECHNICAL LEVEL
    # =========================================================

    class TechnicalLevel(models.TextChoices):
        BEGINNER = "BEGINNER", "Beginner"
        INTERMEDIATE = "INTERMEDIATE", "Intermediate"
        ADVANCED = "ADVANCED", "Advanced"
        EXPERT = "EXPERT", "Expert"

    # =========================================================
    # USER RELATIONSHIP
    # =========================================================

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="member_profile",
        db_index=True,
        help_text="User account associated with this KUCSA membership.",
    )

    # =========================================================
    # MEMBERSHIP INFORMATION
    # =========================================================

    membership_number = models.CharField(
        max_length=30,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Membership Number",
        help_text="Unique KUCSA membership number.",
    )

    membership_status = models.CharField(
        max_length=20,
        choices=MembershipStatus.choices,
        default=MembershipStatus.PENDING,
        db_index=True,
        help_text="Current KUCSA membership status.",
    )

    joined_date = models.DateField(
        blank=True,
        null=True,
        db_index=True,
        help_text="Date the member officially joined KUCSA.",
    )

    expiry_date = models.DateField(
        blank=True,
        null=True,
        db_index=True,
        help_text="Date the current KUCSA membership expires.",
    )

    # =========================================================
    # ACADEMIC INFORMATION
    # =========================================================

    course = models.CharField(
        max_length=150,
        blank=True,
        help_text="Academic course or programme.",
    )

    year_of_study = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        help_text="Current year of study.",
    )

    # =========================================================
    # PROFILE INFORMATION
    # =========================================================

    bio = models.TextField(
        blank=True,
        help_text="Short description about the member.",
    )

    # =========================================================
    # TECHNICAL INFORMATION
    # =========================================================

    technical_level = models.CharField(
        max_length=20,
        choices=TechnicalLevel.choices,
        default=TechnicalLevel.BEGINNER,
        db_index=True,
        help_text="Current technical skill level.",
    )

    technical_domains = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Technical domains such as Web Development, "
            "Cybersecurity, AI, Networking, Data Science, "
            "Cloud Computing, UI/UX, Mobile Development, etc."
        ),
    )

    skills = models.JSONField(
        default=list,
        blank=True,
        help_text="List of technical and professional skills.",
    )

    interests = models.JSONField(
        default=list,
        blank=True,
        help_text="List of member interests.",
    )

    # =========================================================
    # PROFESSIONAL LINKS
    # =========================================================

    github_url = models.URLField(
        blank=True,
        help_text="Member's GitHub profile.",
    )

    linkedin_url = models.URLField(
        blank=True,
        help_text="Member's LinkedIn profile.",
    )

    portfolio_url = models.URLField(
        blank=True,
        help_text="Member's portfolio website.",
    )

    # =========================================================
    # PROFILE COMPLETION
    # =========================================================

    is_profile_complete = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether the member has completed their KUCSA profile.",
    )

    # =========================================================
    # TIMESTAMPS
    # =========================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # =========================================================
    # META
    # =========================================================

    class Meta:
        ordering = [
            "user__first_name",
            "user__last_name",
        ]

        verbose_name = "Member"
        verbose_name_plural = "Members"

        indexes = [
            models.Index(
                fields=[
                    "membership_status",
                    "expiry_date",
                ],
                name="member_status_expiry_idx",
            ),
            models.Index(
                fields=[
                    "membership_status",
                    "created_at",
                ],
                name="member_status_created_idx",
            ),
            models.Index(
                fields=[
                    "technical_level",
                ],
                name="member_technical_level_idx",
            ),
            models.Index(
                fields=[
                    "course",
                ],
                name="member_course_idx",
            ),
        ]

    # =========================================================
    # VALIDATION
    # =========================================================

    def clean(self):
        errors = {}

        if not self.user_id:
            errors["user"] = (
                "A user account is required for a KUCSA member."
            )

        # -----------------------------------------------------
        # YEAR OF STUDY
        # -----------------------------------------------------

        if self.year_of_study is not None:
            if self.year_of_study < 1:
                errors["year_of_study"] = (
                    "Year of study must be at least 1."
                )

            elif self.year_of_study > 8:
                errors["year_of_study"] = (
                    "Please enter a valid year of study."
                )

        today = timezone.localdate()

        # -----------------------------------------------------
        # JOINED DATE
        # -----------------------------------------------------

        if self.joined_date and self.joined_date > today:
            errors["joined_date"] = (
                "Joined date cannot be in the future."
            )

        # -----------------------------------------------------
        # EXPIRY DATE
        # -----------------------------------------------------

        if self.expiry_date and self.joined_date:
            if self.expiry_date < self.joined_date:
                errors["expiry_date"] = (
                    "Membership expiry date cannot be earlier "
                    "than the joined date."
                )

        # -----------------------------------------------------
        # ACTIVE MEMBERSHIP
        # -----------------------------------------------------

        if self.membership_status == self.MembershipStatus.ACTIVE:

            if not self.membership_number:
                errors["membership_number"] = (
                    "An active member must have a membership number."
                )

            if not self.joined_date:
                errors["joined_date"] = (
                    "An active member must have a joined date."
                )

            if not self.expiry_date:
                errors["expiry_date"] = (
                    "An active member must have an expiry date."
                )

        # -----------------------------------------------------
        # EXPIRED MEMBERSHIP
        # -----------------------------------------------------

        elif self.membership_status == self.MembershipStatus.EXPIRED:

            if not self.membership_number:
                errors["membership_number"] = (
                    "An expired member must have a membership number."
                )

            if not self.expiry_date:
                errors["expiry_date"] = (
                    "An expired member must have an expiry date."
                )

        # -----------------------------------------------------
        # SUSPENDED MEMBERSHIP
        # -----------------------------------------------------

        elif self.membership_status == self.MembershipStatus.SUSPENDED:

            if not self.membership_number:
                errors["membership_number"] = (
                    "A suspended member must have a membership number."
                )

        # -----------------------------------------------------
        # PENDING MEMBERSHIP
        # -----------------------------------------------------

        elif self.membership_status == self.MembershipStatus.PENDING:

            if self.membership_number:
                errors["membership_number"] = (
                    "A pending member cannot have a membership number."
                )

        # -----------------------------------------------------
        # JSON LIST FIELDS
        # -----------------------------------------------------

        for field_name in (
            "technical_domains",
            "skills",
            "interests",
        ):
            value = getattr(self, field_name, None)

            if value is not None and not isinstance(value, list):
                errors[field_name] = (
                    f"{field_name.replace('_', ' ').capitalize()} "
                    "must be stored as a list."
                )

        if errors:
            raise ValidationError(errors)

    # =========================================================
    # SAVE
    # =========================================================

    def save(self, *args, **kwargs):
        """
        Normalize member data before saving.

        Membership activation is deliberately NOT performed here.

        Activation must happen explicitly after successful
        payment verification.
        """

        if self.membership_number:
            self.membership_number = (
                self.membership_number.strip().upper()
            )

        if self.bio:
            self.bio = self.bio.strip()

        if self.course:
            self.course = self.course.strip()

        if self.github_url:
            self.github_url = self.github_url.strip()

        if self.linkedin_url:
            self.linkedin_url = self.linkedin_url.strip()

        if self.portfolio_url:
            self.portfolio_url = self.portfolio_url.strip()

        for field_name in (
            "technical_domains",
            "skills",
            "interests",
        ):
            if getattr(self, field_name, None) is None:
                setattr(self, field_name, [])

        super().save(*args, **kwargs)

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        member_name = (
            self.user.get_full_name()
            if self.user_id
            else "Unknown Member"
        )

        return (
            f"{self.membership_number or 'No Membership Number'} - "
            f"{member_name}"
        )

    # =========================================================
    # ACCOUNT PROPERTIES
    # =========================================================

    @property
    def full_name(self):
        if not self.user_id:
            return "Unknown Member"

        return (
            self.user.get_full_name()
            or self.user.username
            or self.user.email
            or "Unnamed Member"
        )

    @property
    def email(self):
        return self.user.email if self.user_id else ""

    @property
    def registration_number(self):
        if not self.user_id:
            return ""

        return getattr(
            self.user,
            "registration_number",
            "",
        )

    @property
    def display_registration_number(self):
        return self.registration_number

    # =========================================================
    # MEMBERSHIP STATUS PROPERTIES
    # =========================================================

    @property
    def is_active(self):
        return (
            self.membership_status
            == self.MembershipStatus.ACTIVE
        )

    @property
    def is_pending(self):
        return (
            self.membership_status
            == self.MembershipStatus.PENDING
        )

    @property
    def is_suspended(self):
        return (
            self.membership_status
            == self.MembershipStatus.SUSPENDED
        )

    @property
    def is_expired(self):
        return (
            self.membership_status
            == self.MembershipStatus.EXPIRED
        )

    # =========================================================
    # MEMBERSHIP EXPIRY
    # =========================================================

    @property
    def has_expiry_date(self):
        return self.expiry_date is not None

    @property
    def is_membership_expired(self):
        if not self.expiry_date:
            return False

        return self.expiry_date < timezone.localdate()

    @property
    def days_until_expiry(self):
        if not self.expiry_date:
            return None

        return (
            self.expiry_date
            - timezone.localdate()
        ).days

    # =========================================================
    # PLATFORM ACCESS
    # =========================================================

    @property
    def can_access_platform(self):
        """
        A member can access the platform only when:

            1. Membership status is ACTIVE.
            2. An expiry date exists.
            3. Membership has not expired.
        """

        if self.membership_status != self.MembershipStatus.ACTIVE:
            return False

        if not self.expiry_date:
            return False

        return self.expiry_date >= timezone.localdate()

    @property
    def payment_required(self):
        return not self.can_access_platform

    # =========================================================
    # PAYMENT STATE HELPERS
    # =========================================================

    @property
    def has_pending_payment(self):
        if not self.pk:
            return False

        return self.payments.filter(
            status="PENDING"
        ).exists()

    @property
    def has_completed_payment(self):
        if not self.pk:
            return False

        return self.payments.filter(
            status="COMPLETED"
        ).exists()

    @property
    def latest_payment(self):
        if not self.pk:
            return None

        return (
            self.payments
            .order_by("-created_at")
            .first()
        )

    # =========================================================
    # MEMBERSHIP ACTIVATION
    # =========================================================

    def activate_membership(
        self,
        membership_duration_days=None,
    ):
        """
        Activate membership after successful payment verification.

        This method does not process M-Pesa transactions.

        The payment service/callback must first confirm that
        the payment was successfully completed.

        Activation performs:

            - Membership number generation
            - Joined date assignment
            - Expiry date calculation
            - Membership status activation
            - User verification
        """

        if not self.user_id:
            raise ValidationError(
                "Cannot activate a membership without a user account."
            )

        today = timezone.localdate()

        # -----------------------------------------------------
        # ALREADY ACTIVE
        # -----------------------------------------------------

        if (
            self.membership_status
            == self.MembershipStatus.ACTIVE
            and self.expiry_date
            and self.expiry_date >= today
        ):
            user = self.user

            if hasattr(user, "is_verified") and not user.is_verified:
                user.is_verified = True
                user.save(update_fields=["is_verified"])

            return self

        # -----------------------------------------------------
        # MEMBERSHIP NUMBER
        # -----------------------------------------------------

        if not self.membership_number:

            registration_number = getattr(
                self.user,
                "registration_number",
                None,
            )

            if registration_number:
                self.membership_number = (
                    f"KUCSA-"
                    f"{str(registration_number).strip().upper()}"
                )
            else:
                self.membership_number = (
                    f"KUCSA-{self.user.pk}"
                )

        # -----------------------------------------------------
        # JOINED DATE
        # -----------------------------------------------------

        if not self.joined_date:
            self.joined_date = today

        # -----------------------------------------------------
        # MEMBERSHIP DURATION
        # -----------------------------------------------------

        if membership_duration_days is None:
            membership_duration_days = getattr(
                settings,
                "KUCSA_MEMBERSHIP_DURATION_DAYS",
                365,
            )

        try:
            membership_duration_days = int(
                membership_duration_days
            )
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "Membership duration must be a valid number."
            ) from exc

        if membership_duration_days <= 0:
            raise ValidationError(
                "Membership duration must be greater than zero."
            )

        # -----------------------------------------------------
        # EXPIRY DATE
        # -----------------------------------------------------

        self.expiry_date = (
            today
            + timedelta(
                days=membership_duration_days
            )
        )

        # -----------------------------------------------------
        # ACTIVATE
        # -----------------------------------------------------

        self.membership_status = (
            self.MembershipStatus.ACTIVE
        )

        self.save(
            update_fields=[
                "membership_number",
                "membership_status",
                "joined_date",
                "expiry_date",
                "updated_at",
            ]
        )

        # -----------------------------------------------------
        # VERIFY USER
        # -----------------------------------------------------

        user = self.user

        if hasattr(user, "is_verified") and not user.is_verified:
            user.is_verified = True
            user.save(update_fields=["is_verified"])

        return self

    # =========================================================
    # EXPIRE MEMBERSHIP
    # =========================================================

    def expire_membership(self):
        """
        Expire membership and remove account verification.
        """

        self.membership_status = (
            self.MembershipStatus.EXPIRED
        )

        self.save(
            update_fields=[
                "membership_status",
                "updated_at",
            ]
        )

        user = self.user

        if hasattr(user, "is_verified") and user.is_verified:
            user.is_verified = False
            user.save(update_fields=["is_verified"])

        return self

    # =========================================================
    # SUSPEND MEMBERSHIP
    # =========================================================

    def suspend_membership(self):
        """
        Suspend membership and remove account verification.
        """

        self.membership_status = (
            self.MembershipStatus.SUSPENDED
        )

        self.save(
            update_fields=[
                "membership_status",
                "updated_at",
            ]
        )

        user = self.user

        if hasattr(user, "is_verified") and user.is_verified:
            user.is_verified = False
            user.save(update_fields=["is_verified"])

        return self

    # =========================================================
    # PROFILE COMPLETION
    # =========================================================

    @property
    def profile_completion_status(self):
        return (
            "Complete"
            if self.is_profile_complete
            else "Incomplete"
        )

    def calculate_profile_completion(self):
        """
        Determine whether the important profile information
        has been supplied.
        """

        required_fields = (
            self.course,
            self.year_of_study,
            self.bio,
            self.technical_level,
            self.technical_domains,
            self.skills,
        )

        return all(bool(value) for value in required_fields)

    def update_profile_completion(self, save=True):
        """
        Recalculate and update profile completion status.
        """

        self.is_profile_complete = (
            self.calculate_profile_completion()
        )

        if save:
            self.save(
                update_fields=[
                    "is_profile_complete",
                    "updated_at",
                ]
            )

        return self.is_profile_complete

    # =========================================================
    # DISPLAY HELPERS
    # =========================================================

    @property
    def membership_status_display(self):
        return self.get_membership_status_display()

    @property
    def technical_level_display(self):
        return self.get_technical_level_display()
