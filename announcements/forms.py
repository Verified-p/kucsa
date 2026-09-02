# announcements/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Announcement


# =========================================================
# COMMON FORM STYLING
# =========================================================


class AnnouncementFormMixin:
    """
    Common Bootstrap styling shared by announcement forms.
    """

    def apply_bootstrap_classes(self):
        for field in self.fields.values():

            widget = field.widget

            # -------------------------------------------------
            # Checkbox and file inputs
            # -------------------------------------------------

            if isinstance(
                widget,
                (
                    forms.CheckboxInput,
                    forms.ClearableFileInput,
                ),
            ):
                continue

            # -------------------------------------------------
            # Existing classes
            # -------------------------------------------------

            existing_class = widget.attrs.get(
                "class",
                "",
            ).strip()

            # -------------------------------------------------
            # Select fields
            # -------------------------------------------------

            if isinstance(widget, forms.Select):
                widget.attrs["class"] = (
                    f"{existing_class} form-select"
                ).strip()

            # -------------------------------------------------
            # All other fields
            # -------------------------------------------------

            else:
                widget.attrs["class"] = (
                    f"{existing_class} form-control"
                ).strip()


# =========================================================
# MAIN ANNOUNCEMENT FORM
# =========================================================


class AnnouncementForm(
    AnnouncementFormMixin,
    forms.ModelForm,
):
    """
    Main form used for creating and editing KUCSA
    announcements.

    Authorization is intentionally NOT handled here.

    The views are responsible for determining whether the
    authenticated user is:

        - KUCSA administrator
        - KUCSA executive
        - ordinary member/student
    """

    class Meta:
        model = Announcement

        fields = [
            "title",
            "summary",
            "content",
            "announcement_type",
            "priority",
            "target_audience",
            "status",
            "published_at",
            "expires_at",
            "image",
            "attachment",
            "is_featured",
            "allow_comments",
        ]

        widgets = {
            # -------------------------------------------------
            # TITLE
            # -------------------------------------------------

            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "Enter announcement title"
                    ),
                    "maxlength": 255,
                    "autocomplete": "off",
                }
            ),

            # -------------------------------------------------
            # SUMMARY
            # -------------------------------------------------

            "summary": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "Enter a short summary"
                    ),
                    "maxlength": 500,
                }
            ),

            # -------------------------------------------------
            # CONTENT
            # -------------------------------------------------

            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 10,
                    "placeholder": (
                        "Write the announcement content..."
                    ),
                }
            ),

            # -------------------------------------------------
            # TYPE
            # -------------------------------------------------

            "announcement_type": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            # -------------------------------------------------
            # PRIORITY
            # -------------------------------------------------

            "priority": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            # -------------------------------------------------
            # TARGET AUDIENCE
            # -------------------------------------------------

            "target_audience": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            # -------------------------------------------------
            # STATUS
            # -------------------------------------------------

            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            # -------------------------------------------------
            # PUBLICATION DATE
            # -------------------------------------------------

            "published_at": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                }
            ),

            # -------------------------------------------------
            # EXPIRATION DATE
            # -------------------------------------------------

            "expires_at": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                }
            ),

            # -------------------------------------------------
            # IMAGE
            # -------------------------------------------------

            "image": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": (
                        "image/jpeg,"
                        "image/png,"
                        "image/webp"
                    ),
                }
            ),

            # -------------------------------------------------
            # ATTACHMENT
            # -------------------------------------------------

            "attachment": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                }
            ),

            # -------------------------------------------------
            # FEATURED
            # -------------------------------------------------

            "is_featured": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),

            # -------------------------------------------------
            # COMMENTS
            # -------------------------------------------------

            "allow_comments": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

        labels = {
            "title": "Announcement Title",
            "summary": "Short Summary",
            "content": "Announcement Content",
            "announcement_type": "Announcement Type",
            "priority": "Priority",
            "target_audience": "Target Audience",
            "status": "Publication Status",
            "published_at": "Publication Date",
            "expires_at": "Expiration Date",
            "image": "Announcement Image",
            "attachment": "Attachment",
            "is_featured": "Featured Announcement",
            "allow_comments": "Allow Comments",
        }

        help_texts = {
            "summary": (
                "A short description displayed on announcement "
                "lists and notification-style previews."
            ),
            "published_at": (
                "Leave empty when saving as a draft. "
                "A publication time will be assigned automatically "
                "when the announcement is published."
            ),
            "expires_at": (
                "Optional. After this date and time, the "
                "announcement will no longer appear as active."
            ),
            "image": (
                "Optional JPEG, PNG, or WebP announcement image. "
                "Maximum size: 5 MB."
            ),
            "attachment": (
                "Optional supporting document or file. "
                "Maximum size: 10 MB."
            ),
            "is_featured": (
                "Featured announcements are displayed prominently "
                "on announcement and dashboard areas."
            ),
            "allow_comments": (
                "Allow members to comment on this announcement. "
                "Comment functionality must be implemented separately."
            ),
        }

    # =====================================================
    # INITIALIZATION
    # =====================================================

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()

        # -------------------------------------------------
        # Date/time input formats
        # -------------------------------------------------

        for field_name in (
            "published_at",
            "expires_at",
        ):
            field = self.fields.get(field_name)

            if field:
                field.input_formats = [
                    "%Y-%m-%dT%H:%M",
                    "%Y-%m-%d %H:%M",
                ]

        # -------------------------------------------------
        # Required fields
        # -------------------------------------------------

        self.fields["title"].required = True
        self.fields["content"].required = True

    # =====================================================
    # TITLE VALIDATION
    # =====================================================

    def clean_title(self):
        """
        Validate announcement title.
        """

        title = (
            self.cleaned_data
            .get("title", "")
            .strip()
        )

        if not title:
            raise ValidationError(
                "Announcement title is required."
            )

        if len(title) < 5:
            raise ValidationError(
                "The announcement title must contain "
                "at least 5 characters."
            )

        return title

    # =====================================================
    # SUMMARY VALIDATION
    # =====================================================

    def clean_summary(self):
        """
        Normalize the announcement summary.
        """

        summary = (
            self.cleaned_data
            .get("summary", "")
            .strip()
        )

        return summary

    # =====================================================
    # CONTENT VALIDATION
    # =====================================================

    def clean_content(self):
        """
        Validate announcement content.
        """

        content = (
            self.cleaned_data
            .get("content", "")
            .strip()
        )

        if not content:
            raise ValidationError(
                "Announcement content is required."
            )

        if len(content) < 10:
            raise ValidationError(
                "The announcement content must contain "
                "at least 10 characters."
            )

        return content

    # =====================================================
    # IMAGE VALIDATION
    # =====================================================

    def clean_image(self):
        """
        Validate announcement image.

        Maximum:
            5 MB

        Allowed:
            JPEG
            PNG
            WebP
        """

        image = self.cleaned_data.get("image")

        if not image:
            return image

        max_size = 5 * 1024 * 1024

        if image.size > max_size:
            raise ValidationError(
                "Announcement images must not exceed 5 MB."
            )

        allowed_types = {
            "image/jpeg",
            "image/png",
            "image/webp",
        }

        content_type = getattr(
            image,
            "content_type",
            None,
        )

        if (
            content_type
            and content_type not in allowed_types
        ):
            raise ValidationError(
                "Only JPEG, PNG, and WebP images are allowed."
            )

        return image

    # =====================================================
    # ATTACHMENT VALIDATION
    # =====================================================

    def clean_attachment(self):
        """
        Validate announcement attachment.

        Maximum:
            10 MB
        """

        attachment = self.cleaned_data.get(
            "attachment"
        )

        if not attachment:
            return attachment

        max_size = 10 * 1024 * 1024

        if attachment.size > max_size:
            raise ValidationError(
                "Announcement attachments must not exceed 10 MB."
            )

        return attachment

    # =====================================================
    # FORM-LEVEL VALIDATION
    # =====================================================

    def clean(self):
        """
        Perform cross-field announcement validation.
        """

        cleaned_data = super().clean()

        status = cleaned_data.get("status")
        published_at = cleaned_data.get(
            "published_at"
        )
        expires_at = cleaned_data.get(
            "expires_at"
        )
        priority = cleaned_data.get("priority")
        announcement_type = cleaned_data.get(
            "announcement_type"
        )
        is_featured = cleaned_data.get(
            "is_featured"
        )

        # -------------------------------------------------
        # PUBLISHED ANNOUNCEMENT
        # -------------------------------------------------

        if (
            status == Announcement.Status.PUBLISHED
            and not published_at
        ):
            published_at = timezone.now()

            cleaned_data["published_at"] = (
                published_at
            )

        # -------------------------------------------------
        # EXPIRATION
        # -------------------------------------------------

        if (
            expires_at
            and published_at
            and expires_at <= published_at
        ):
            self.add_error(
                "expires_at",
                (
                    "The expiration date must be after "
                    "the publication date."
                ),
            )

        # -------------------------------------------------
        # EMERGENCY PRIORITY
        # -------------------------------------------------

        if (
            announcement_type
            == Announcement.AnnouncementType.EMERGENCY
            and priority
            == Announcement.Priority.LOW
        ):
            self.add_error(
                "priority",
                (
                    "Emergency announcements cannot "
                    "have low priority."
                ),
            )

        # -------------------------------------------------
        # FEATURED ANNOUNCEMENTS
        # -------------------------------------------------

        if (
            is_featured
            and status != Announcement.Status.PUBLISHED
        ):
            self.add_error(
                "is_featured",
                (
                    "Only published announcements "
                    "can be featured."
                ),
            )

        return cleaned_data


# =========================================================
# CREATE ANNOUNCEMENT FORM
# =========================================================


class CreateAnnouncementForm(AnnouncementForm):
    """
    Form specifically used when creating a new
    announcement.

    New announcements default to:

        Status:
            Draft

        Priority:
            Normal

        Audience:
            All Members

        Type:
            General
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.is_bound:

            self.initial.setdefault(
                "status",
                Announcement.Status.DRAFT,
            )

            self.initial.setdefault(
                "priority",
                Announcement.Priority.NORMAL,
            )

            self.initial.setdefault(
                "target_audience",
                Announcement.TargetAudience.ALL,
            )

            self.initial.setdefault(
                "announcement_type",
                Announcement.AnnouncementType.GENERAL,
            )


# =========================================================
# EDIT ANNOUNCEMENT FORM
# =========================================================


class EditAnnouncementForm(AnnouncementForm):
    """
    Form used to edit an existing announcement.

    Existing announcement values are preserved automatically
    through the ModelForm instance.
    """

    pass


# =========================================================
# ANNOUNCEMENT FILTER FORM
# =========================================================


class AnnouncementFilterForm(
    AnnouncementFormMixin,
    forms.Form,
):
    """
    Filter form for the announcement list.

    The view decides which filter options are actually
    available to the authenticated user.

    Members normally see only active/published announcements.

    Executives and administrators may filter by status.
    """

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    search = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Search announcements..."
                ),
                "autocomplete": "off",
            }
        ),
    )

    # -----------------------------------------------------
    # ANNOUNCEMENT TYPE
    # -----------------------------------------------------

    announcement_type = forms.ChoiceField(
        required=False,
        label="Type",
        choices=[
            ("", "All Types"),
            *Announcement.AnnouncementType.choices,
        ],
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    # -----------------------------------------------------
    # PRIORITY
    # -----------------------------------------------------

    priority = forms.ChoiceField(
        required=False,
        label="Priority",
        choices=[
            ("", "All Priorities"),
            *Announcement.Priority.choices,
        ],
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    # -----------------------------------------------------
    # TARGET AUDIENCE
    # -----------------------------------------------------

    target_audience = forms.ChoiceField(
        required=False,
        label="Audience",
        choices=[
            ("", "All Audiences"),
            *Announcement.TargetAudience.choices,
        ],
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    status = forms.ChoiceField(
        required=False,
        label="Status",
        choices=[
            ("", "All Statuses"),
            *Announcement.Status.choices,
        ],
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    # -----------------------------------------------------
    # FEATURED
    # -----------------------------------------------------

    featured = forms.ChoiceField(
        required=False,
        label="Featured",
        choices=[
            ("", "All"),
            ("yes", "Featured"),
            ("no", "Not Featured"),
        ],
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    # =====================================================
    # INITIALIZATION
    # =====================================================

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()


# =========================================================
# ANNOUNCEMENT STATUS FORM
# =========================================================


class AnnouncementStatusForm(forms.Form):
    """
    Small form used by authorized users to change
    an announcement status.
    """

    status = forms.ChoiceField(
        label="Status",
        choices=Announcement.Status.choices,
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )


# =========================================================
# PUBLISH ANNOUNCEMENT FORM
# =========================================================


class PublishAnnouncementForm(forms.Form):
    """
    Form used when an authorized user publishes
    an announcement.

    Publication date:
        Optional.

    Expiration date:
        Optional.

    Featured:
        Optional.
    """

    # -----------------------------------------------------
    # PUBLICATION DATE
    # -----------------------------------------------------

    published_at = forms.DateTimeField(
        required=False,
        label="Publication Date",
        widget=forms.DateTimeInput(
            attrs={
                "class": "form-control",
                "type": "datetime-local",
            }
        ),
        input_formats=[
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M",
        ],
    )

    # -----------------------------------------------------
    # EXPIRATION DATE
    # -----------------------------------------------------

    expires_at = forms.DateTimeField(
        required=False,
        label="Expiration Date",
        widget=forms.DateTimeInput(
            attrs={
                "class": "form-control",
                "type": "datetime-local",
            }
        ),
        input_formats=[
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M",
        ],
    )

    # -----------------------------------------------------
    # FEATURED
    # -----------------------------------------------------

    is_featured = forms.BooleanField(
        required=False,
        label="Feature Announcement",
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
            }
        ),
    )

    # =====================================================
    # VALIDATION
    # =====================================================

    def clean(self):
        """
        Validate publication settings.
        """

        cleaned_data = super().clean()

        published_at = cleaned_data.get(
            "published_at"
        )

        expires_at = cleaned_data.get(
            "expires_at"
        )

        # -------------------------------------------------
        # Default publication time
        # -------------------------------------------------

        if not published_at:
            published_at = timezone.now()

            cleaned_data["published_at"] = (
                published_at
            )

        # -------------------------------------------------
        # Expiration validation
        # -------------------------------------------------

        if (
            expires_at
            and expires_at <= published_at
        ):
            self.add_error(
                "expires_at",
                (
                    "The expiration date must be after "
                    "the publication date."
                ),
            )

        return cleaned_data