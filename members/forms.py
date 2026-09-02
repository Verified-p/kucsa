# members/forms.py

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Member


User = get_user_model()


# =========================================================
# COMMON JSON LIST FIELD HELPER
# =========================================================

class JSONListFieldMixin:
    """
    Helper for Member JSON list fields.

    Database format:

        ["Python", "Django", "Cybersecurity"]

    Form format:

        Python, Django, Cybersecurity

    The form converts the comma-separated text into a
    clean Python list before saving.
    """

    JSON_LIST_FIELDS = (
        "technical_domains",
        "skills",
        "interests",
    )

    def _prepare_json_list_initial_values(self):
        """
        Convert stored JSON lists into comma-separated text
        when displaying an existing member in the form.
        """

        for field_name in self.JSON_LIST_FIELDS:

            if field_name not in self.fields:
                continue

            value = self.initial.get(field_name)

            if isinstance(value, list):
                self.initial[field_name] = ", ".join(
                    str(item).strip()
                    for item in value
                    if str(item).strip()
                )

    def _clean_json_list_field(self, field_name):
        """
        Convert comma-separated input into a clean list.

        Example:

            Python, Django, Python, Git

        becomes:

            ["Python", "Django", "Git"]
        """

        value = self.cleaned_data.get(field_name)

        if not value:
            return []

        if isinstance(value, list):
            values = value
        else:
            values = str(value).split(",")

        cleaned = []
        seen = set()

        for item in values:

            item = str(item).strip()

            if not item:
                continue

            normalized = item.casefold()

            if normalized in seen:
                continue

            seen.add(normalized)
            cleaned.append(item)

        return cleaned


# =========================================================
# MEMBER PROFILE FORM
# =========================================================

class MemberProfileForm(
    JSONListFieldMixin,
    forms.ModelForm,
):
    """
    Form used by a normal KUCSA member to update their
    personal and technical membership profile.

    Payment-controlled membership information is deliberately
    excluded.

    Members CANNOT change:

        - Membership number
        - Membership status
        - Joined date
        - Expiry date

    Those values are controlled by the membership/payment
    workflow.
    """

    class Meta:
        model = Member

        fields = [
            "bio",
            "course",
            "year_of_study",
            "technical_level",
            "technical_domains",
            "skills",
            "interests",
            "github_url",
            "linkedin_url",
            "portfolio_url",
        ]

        widgets = {

            "bio": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": (
                        "Tell the KUCSA community about yourself..."
                    ),
                }
            ),

            "course": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "e.g. Bachelor of Science in "
                        "Computer Science"
                    ),
                }
            ),

            "year_of_study": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "max": 8,
                    "placeholder": "e.g. 3",
                }
            ),

            "technical_level": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "technical_domains": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Web Development, Cybersecurity, "
                        "Artificial Intelligence, Data Science"
                    ),
                }
            ),

            "skills": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Python, Django, JavaScript, Git"
                    ),
                }
            ),

            "interests": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Artificial Intelligence, Cloud Computing, "
                        "Networking"
                    ),
                }
            ),

            "github_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://github.com/username",
                }
            ),

            "linkedin_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://linkedin.com/in/username",
                }
            ),

            "portfolio_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://example.com",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._prepare_json_list_initial_values()

    # =====================================================
    # YEAR OF STUDY
    # =====================================================

    def clean_year_of_study(self):
        year = self.cleaned_data.get("year_of_study")

        if year is None:
            return None

        if year < 1:
            raise forms.ValidationError(
                "Year of study must be at least 1."
            )

        if year > 8:
            raise forms.ValidationError(
                "Please enter a valid year of study."
            )

        return year

    # =====================================================
    # BIO
    # =====================================================

    def clean_bio(self):
        return self.cleaned_data.get("bio", "").strip()

    # =====================================================
    # COURSE
    # =====================================================

    def clean_course(self):
        return self.cleaned_data.get("course", "").strip()

    # =====================================================
    # JSON LIST FIELDS
    # =====================================================

    def clean_technical_domains(self):
        return self._clean_json_list_field(
            "technical_domains"
        )

    def clean_skills(self):
        return self._clean_json_list_field(
            "skills"
        )

    def clean_interests(self):
        return self._clean_json_list_field(
            "interests"
        )


# =========================================================
# MEMBER USER FORM
# =========================================================

class MemberUserForm(forms.ModelForm):
    """
    Form for updating personal information stored on the
    main User model.

    This form does NOT modify:

        - username
        - registration number
        - role
        - verification status
        - account status
        - membership/payment information
    """

    class Meta:
        model = User

        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "profile_picture",
        ]

        widgets = {

            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "First Name",
                }
            ),

            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Last Name",
                }
            ),

            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Email Address",
                }
            ),

            "phone_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Phone Number",
                }
            ),

            "profile_picture": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/*",
                }
            ),
        }

    # =====================================================
    # NAME VALIDATION
    # =====================================================

    def clean_first_name(self):
        value = self.cleaned_data.get(
            "first_name",
            "",
        ).strip()

        if not value:
            raise forms.ValidationError(
                "First name is required."
            )

        return value

    def clean_last_name(self):
        value = self.cleaned_data.get(
            "last_name",
            "",
        ).strip()

        if not value:
            raise forms.ValidationError(
                "Last name is required."
            )

        return value

    # =====================================================
    # EMAIL VALIDATION
    # =====================================================

    def clean_email(self):
        email = (
            self.cleaned_data.get(
                "email",
                "",
            )
            .strip()
            .lower()
        )

        if not email:
            raise forms.ValidationError(
                "Email address is required."
            )

        queryset = User.objects.filter(
            email__iexact=email
        )

        if self.instance and self.instance.pk:
            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():
            raise forms.ValidationError(
                "This email address is already in use."
            )

        return email

    # =====================================================
    # PHONE
    # =====================================================

    def clean_phone_number(self):
        return (
            self.cleaned_data.get(
                "phone_number",
                "",
            )
            .strip()
        )


# =========================================================
# COMPLETE MEMBER MANAGEMENT FORM
# =========================================================

class MemberForm(
    JSONListFieldMixin,
    forms.ModelForm,
):
    """
    Complete KUCSA member-management form.

    Intended for:

        - Administrators
        - Authorized KUCSA executives
        - Member management

    This form manages both:

        1. User information
        2. Member information

    It does NOT process payments.

    Payment verification, membership activation, renewal,
    rejection and suspension should be performed through
    the payment/membership service layer.
    """

    # =====================================================
    # USER INFORMATION
    # =====================================================

    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "First Name",
            }
        ),
    )

    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Last Name",
            }
        ),
    )

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Email Address",
            }
        ),
    )

    phone_number = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Phone Number",
            }
        ),
    )

    # =====================================================
    # META
    # =====================================================

    class Meta:
        model = Member

        fields = [
            "membership_number",
            "membership_status",
            "joined_date",
            "expiry_date",
            "bio",
            "course",
            "year_of_study",
            "technical_level",
            "technical_domains",
            "skills",
            "interests",
            "github_url",
            "linkedin_url",
            "portfolio_url",
        ]

        widgets = {

            "membership_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. KUCSA-00001",
                }
            ),

            "membership_status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "joined_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "expiry_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "bio": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": (
                        "Short description about the member..."
                    ),
                }
            ),

            "course": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "e.g. Bachelor of Science in "
                        "Computer Science"
                    ),
                }
            ),

            "year_of_study": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "max": 8,
                }
            ),

            "technical_level": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "technical_domains": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Web Development, Cybersecurity, AI..."
                    ),
                }
            ),

            "skills": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Python, Django, JavaScript..."
                    ),
                }
            ),

            "interests": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "AI, Cloud Computing, Networking..."
                    ),
                }
            ),

            "github_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://github.com/username",
                }
            ),

            "linkedin_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://linkedin.com/in/username",
                }
            ),

            "portfolio_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://example.com",
                }
            ),
        }

    # =====================================================
    # INITIALIZATION
    # =====================================================

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if (
            self.instance
            and self.instance.pk
            and self.instance.user_id
        ):
            user = self.instance.user

            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name
            self.fields["email"].initial = user.email
            self.fields["phone_number"].initial = (
                user.phone_number
            )

        self._prepare_json_list_initial_values()

    # =====================================================
    # MEMBERSHIP NUMBER
    # =====================================================

    def clean_membership_number(self):
        membership_number = (
            self.cleaned_data.get(
                "membership_number"
            )
            or ""
        ).strip().upper()

        if not membership_number:
            return ""

        queryset = Member.objects.filter(
            membership_number__iexact=membership_number
        )

        if self.instance and self.instance.pk:
            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():
            raise forms.ValidationError(
                "This KUCSA membership number is already "
                "assigned to another member."
            )

        return membership_number

    # =====================================================
    # YEAR OF STUDY
    # =====================================================

    def clean_year_of_study(self):
        year = self.cleaned_data.get("year_of_study")

        if year is None:
            return None

        if year < 1:
            raise forms.ValidationError(
                "Year of study must be at least 1."
            )

        if year > 8:
            raise forms.ValidationError(
                "Please enter a valid year of study."
            )

        return year

    # =====================================================
    # DATES
    # =====================================================

    def clean(self):
        cleaned_data = super().clean()

        joined_date = cleaned_data.get("joined_date")
        expiry_date = cleaned_data.get("expiry_date")
        status = cleaned_data.get("membership_status")

        if (
            joined_date
            and expiry_date
            and expiry_date <= joined_date
        ):
            self.add_error(
                "expiry_date",
                "Expiry date must be after the joined date.",
            )

        if (
            status == Member.MembershipStatus.ACTIVE
            and not joined_date
        ):
            self.add_error(
                "joined_date",
                "An active member must have a joined date.",
            )

        if (
            status == Member.MembershipStatus.ACTIVE
            and not cleaned_data.get("membership_number")
        ):
            self.add_error(
                "membership_number",
                "An active member must have a membership number.",
            )

        if (
            status == Member.MembershipStatus.EXPIRED
            and not expiry_date
        ):
            self.add_error(
                "expiry_date",
                "An expired member must have an expiry date.",
            )

        return cleaned_data

    # =====================================================
    # USER INFORMATION
    # =====================================================

    def clean_first_name(self):
        value = self.cleaned_data.get(
            "first_name",
            "",
        ).strip()

        if not value:
            raise forms.ValidationError(
                "First name is required."
            )

        return value

    def clean_last_name(self):
        value = self.cleaned_data.get(
            "last_name",
            "",
        ).strip()

        if not value:
            raise forms.ValidationError(
                "Last name is required."
            )

        return value

    def clean_email(self):
        email = (
            self.cleaned_data.get(
                "email",
                "",
            )
            .strip()
            .lower()
        )

        if not email:
            raise forms.ValidationError(
                "Email address is required."
            )

        queryset = User.objects.filter(
            email__iexact=email
        )

        if (
            self.instance
            and self.instance.pk
            and self.instance.user_id
        ):
            queryset = queryset.exclude(
                pk=self.instance.user_id
            )

        if queryset.exists():
            raise forms.ValidationError(
                "This email address is already in use."
            )

        return email

    def clean_phone_number(self):
        return (
            self.cleaned_data.get(
                "phone_number",
                "",
            )
            .strip()
        )

    # =====================================================
    # JSON LIST FIELDS
    # =====================================================

    def clean_technical_domains(self):
        return self._clean_json_list_field(
            "technical_domains"
        )

    def clean_skills(self):
        return self._clean_json_list_field(
            "skills"
        )

    def clean_interests(self):
        return self._clean_json_list_field(
            "interests"
        )

    # =====================================================
    # SAVE
    # =====================================================

    @transaction.atomic
    def save(self, commit=True):
        """
        Save Member and User information atomically.

        If either operation fails, the transaction is rolled
        back.

        Payment processing is deliberately NOT performed here.
        """

        member = super().save(commit=False)

        if not member.user_id:
            raise ValidationError(
                "A member must be associated with a user."
            )

        user = member.user

        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.phone_number = self.cleaned_data["phone_number"]

        if commit:
            user.save()
            member.save()
            self.save_m2m()

        return member