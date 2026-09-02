# executives/models.py

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Executive(models.Model):
    """
    KUCSA Executive Profile.

    The accounts.User model remains the source of truth for:

        - Authentication
        - Account status
        - User role
        - Staff/admin permissions
        - Personal account information

    This model stores information specific to an executive:

        - Committee assignment
        - Office location
        - Responsibilities
        - Vision
        - Biography
        - Leadership term
        - Executive profile activation status

    Executive position/role is intentionally NOT duplicated here.
    The official role is read from User.role.
    """

    # =========================================================
    # COMMITTEES
    # =========================================================

    class Committee(models.TextChoices):
        EXECUTIVE = (
            "EXECUTIVE",
            "Executive Committee",
        )

        TECHNICAL = (
            "TECHNICAL",
            "Technical Committee",
        )

        EVENTS = (
            "EVENTS",
            "Events Committee",
        )

        FINANCE = (
            "FINANCE",
            "Finance Committee",
        )

        COMMUNICATIONS = (
            "COMMUNICATIONS",
            "Communications Committee",
        )

    # =========================================================
    # USER RELATIONSHIP
    # =========================================================

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="executive_profile",
        db_index=True,
        help_text=(
            "User account associated with this executive profile."
        ),
    )

    # =========================================================
    # EXECUTIVE INFORMATION
    # =========================================================

    committee = models.CharField(
        max_length=30,
        choices=Committee.choices,
        default=Committee.EXECUTIVE,
        db_index=True,
        help_text="Committee assigned to the executive.",
    )

    office_location = models.CharField(
        max_length=150,
        blank=True,
        help_text="Office or physical location of the executive.",
    )

    responsibilities = models.TextField(
        blank=True,
        help_text="Main responsibilities of the executive.",
    )

    vision = models.TextField(
        blank=True,
        help_text="Executive's vision for KUCSA.",
    )

    biography = models.TextField(
        blank=True,
        help_text="Short executive biography.",
    )

    # =========================================================
    # TERM INFORMATION
    # =========================================================

    term_start = models.DateField(
        blank=True,
        null=True,
        db_index=True,
        help_text="Date the executive term begins.",
    )

    term_end = models.DateField(
        blank=True,
        null=True,
        db_index=True,
        help_text="Date the executive term ends.",
    )

    # =========================================================
    # EXECUTIVE PROFILE STATUS
    # =========================================================

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=(
            "Whether this executive profile is "
            "administratively active."
        ),
    )

    # =========================================================
    # PLATFORM INFORMATION
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

        verbose_name = "Executive"
        verbose_name_plural = "Executives"

        indexes = [
            models.Index(
                fields=[
                    "committee",
                    "is_active",
                ],
                name="exec_committee_active_idx",
            ),
            models.Index(
                fields=[
                    "term_start",
                    "term_end",
                ],
                name="exec_term_dates_idx",
            ),
            models.Index(
                fields=[
                    "is_active",
                    "created_at",
                ],
                name="exec_active_created_idx",
            ),
        ]

    # =========================================================
    # VALIDATION
    # =========================================================

    def clean(self):
        """
        Validate executive profile data.

        Rules:

            - A User account is required.
            - Term end cannot precede term start.
            - Historical/ended terms are allowed.
            - Future terms are allowed.
            - Inactive executive profiles are allowed.
        """

        errors = {}

        # -----------------------------------------------------
        # USER
        # -----------------------------------------------------

        if not self.user_id:
            errors["user"] = (
                "A user account is required for an "
                "executive profile."
            )

        # -----------------------------------------------------
        # COMMITTEE
        # -----------------------------------------------------

        if self.committee not in {
            choice[0]
            for choice in self.Committee.choices
        }:
            errors["committee"] = (
                "Please select a valid KUCSA committee."
            )

        # -----------------------------------------------------
        # TERM DATES
        # -----------------------------------------------------

        if (
            self.term_start
            and self.term_end
            and self.term_end < self.term_start
        ):
            errors["term_end"] = (
                "Executive term end date cannot be "
                "earlier than the term start date."
            )

        if errors:
            raise ValidationError(errors)

    # =========================================================
    # SAVE
    # =========================================================

    def save(self, *args, **kwargs):
        """
        Normalize executive profile text before saving.

        Database structure and business meaning are preserved.
        """

        if self.office_location:
            self.office_location = (
                self.office_location.strip()
            )

        if self.responsibilities:
            self.responsibilities = (
                self.responsibilities.strip()
            )

        if self.vision:
            self.vision = self.vision.strip()

        if self.biography:
            self.biography = self.biography.strip()

        super().save(*args, **kwargs)

    # =========================================================
    # STRING REPRESENTATION
    # =========================================================

    def __str__(self):
        return f"{self.full_name} - {self.role}"

    # =========================================================
    # USER INFORMATION
    # =========================================================

    @property
    def full_name(self):
        """
        Return the executive's display name.
        """

        if not self.user_id:
            return "Unknown Executive"

        name = self.user.get_full_name()

        if name:
            return name

        username = getattr(
            self.user,
            "username",
            None,
        )

        if username:
            return username

        email = getattr(
            self.user,
            "email",
            None,
        )

        if email:
            return email

        return "Unnamed Executive"

    @property
    def role(self):
        """
        Return the human-readable User role.
        """

        if not self.user_id:
            return "Executive"

        return self.user.get_role_display()

    @property
    def role_code(self):
        """
        Return the underlying User role code.
        """

        if not self.user_id:
            return None

        return getattr(
            self.user,
            "role",
            None,
        )

    @property
    def registration_number(self):
        """
        Return the university registration number
        stored on User.
        """

        if not self.user_id:
            return ""

        return getattr(
            self.user,
            "registration_number",
            "",
        ) or ""

    @property
    def email(self):
        """
        Return the executive email address.
        """

        if not self.user_id:
            return ""

        return getattr(
            self.user,
            "email",
            "",
        ) or ""

    @property
    def phone_number(self):
        """
        Return the executive phone number.
        """

        if not self.user_id:
            return ""

        return getattr(
            self.user,
            "phone_number",
            "",
        ) or ""

    @property
    def profile_picture(self):
        """
        Return the profile picture stored on User.
        """

        if not self.user_id:
            return None

        return getattr(
            self.user,
            "profile_picture",
            None,
        )

    # =========================================================
    # VERIFICATION INFORMATION
    # =========================================================

    @property
    def is_verified(self):
        """
        Return the User account verification status.
        """

        if not self.user_id:
            return False

        return bool(
            getattr(
                self.user,
                "is_verified",
                False,
            )
        )

    @property
    def verification_display(self):
        """
        Return a human-readable verification status.
        """

        return (
            "Verified"
            if self.is_verified
            else "Not Verified"
        )

    # =========================================================
    # TERM STATUS
    # =========================================================

    @property
    def has_started(self):
        """
        Return True when the executive term has started.

        If no start date is specified, the term is considered
        to have no future start restriction.
        """

        if not self.term_start:
            return True

        return self.term_start <= timezone.localdate()

    @property
    def has_ended(self):
        """
        Return True when the executive term has ended.

        If no end date is specified, the term has not ended.
        """

        if not self.term_end:
            return False

        return self.term_end < timezone.localdate()

    @property
    def is_current(self):
        """
        Return True only when the executive is currently serving.

        Requirements:

            1. Executive profile is administratively active.
            2. Executive term has started, if specified.
            3. Executive term has not ended, if specified.
        """

        if not self.is_active:
            return False

        if not self.has_started:
            return False

        if self.has_ended:
            return False

        return True

    @property
    def term_status(self):
        """
        Return the current leadership-term status.

        Possible values:

            - Inactive
            - Upcoming
            - Ended
            - Current
        """

        if not self.is_active:
            return "Inactive"

        if not self.has_started:
            return "Upcoming"

        if self.has_ended:
            return "Ended"

        return "Current"

    # =========================================================
    # EXECUTIVE STATUS
    # =========================================================

    @property
    def status_display(self):
        """
        Return the administrative executive-profile status.
        """

        return (
            "Active"
            if self.is_active
            else "Inactive"
        )

    @property
    def current_status_display(self):
        """
        Return the actual current-serving status.

        This is different from status_display.

        Example:

            is_active=True
            term_start=future date

        results in:

            status_display = "Active"
            current_status_display = "Upcoming"
        """

        return self.term_status

    # =========================================================
    # COMMITTEE HELPERS
    # =========================================================

    @property
    def committee_display(self):
        """
        Return the human-readable committee name.
        """

        return self.get_committee_display()

    # =========================================================
    # TERM DISPLAY
    # =========================================================

    @property
    def term_display(self):
        """
        Return a readable executive term.

        Examples:

            Not specified - Present
            01 Aug 2026 - Present
            01 Aug 2026 - 31 Jul 2027
        """

        start = (
            self.term_start.strftime("%d %b %Y")
            if self.term_start
            else "Not specified"
        )

        end = (
            self.term_end.strftime("%d %b %Y")
            if self.term_end
            else "Present"
        )

        return f"{start} - {end}"

    # =========================================================
    # PROFILE COMPLETENESS
    # =========================================================

    @property
    def profile_completion(self):
        """
        Return a simple profile-completion percentage.

        This is intended for the executive profile/dashboard
        templates and does not create any database field.
        """

        fields = [
            self.office_location,
            self.responsibilities,
            self.vision,
            self.biography,
            self.term_start,
            self.term_end,
        ]

        completed = sum(
            1
            for value in fields
            if value
        )

        return round(
            (completed / len(fields)) * 100
        )

    @property
    def has_complete_profile(self):
        """
        Return True when all executive profile fields are
        populated.
        """

        return self.profile_completion == 100