# executives/forms.py

from django import forms
from django.contrib.auth import get_user_model

from .models import Executive


User = get_user_model()


# =========================================================
# EXECUTIVE ROLE CONSTANTS
# =========================================================

EXECUTIVE_ROLES = (
    User.Role.CHAIRPERSON,
    User.Role.VICE_CHAIRPERSON,
    User.Role.SECRETARY,
    User.Role.SECRETARY_GENERAL,
    User.Role.TREASURER,
    User.Role.ORGANIZING_SECRETARY,
    User.Role.PUBLICITY_SECRETARY,
)


# =========================================================
# EXECUTIVE ROLE CHOICES
# =========================================================

def get_executive_role_choices(include_empty=False):
    """
    Return the official KUCSA executive role choices.

    The User model remains the source of truth for roles.
    """

    choices = [
        choice
        for choice in User.Role.choices
        if choice[0] in EXECUTIVE_ROLES
    ]

    if include_empty:
        return [
            ("", "Select Executive Role"),
            *choices,
        ]

    return choices


# =========================================================
# EXECUTIVE PROFILE FORM
# =========================================================

class ExecutiveProfileForm(forms.ModelForm):
    """
    Form used to create or update an Executive profile.

    This form manages only executive-specific information.

    User account information such as:
        - name
        - email
        - phone
        - profile picture
        - role

    remains on the User model and is handled separately.
    """

    class Meta:
        model = Executive

        fields = [
            "committee",
            "office_location",
            "responsibilities",
            "vision",
            "biography",
            "term_start",
            "term_end",
        ]

        widgets = {
            "committee": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "office_location": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "e.g. Computing Laboratory, Block A"
                    ),
                    "maxlength": 150,
                }
            ),
            "responsibilities": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": (
                        "Describe your main responsibilities "
                        "as a KUCSA executive..."
                    ),
                }
            ),
            "vision": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": (
                        "Describe your vision for KUCSA..."
                    ),
                }
            ),
            "biography": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": (
                        "Write a short biography about yourself..."
                    ),
                }
            ),
            "term_start": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "term_end": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
        }

        labels = {
            "committee": "Committee",
            "office_location": "Office Location",
            "responsibilities": "Responsibilities",
            "vision": "Vision",
            "biography": "Biography",
            "term_start": "Term Start",
            "term_end": "Term End",
        }

        help_texts = {
            "committee": (
                "Select the committee to which this executive "
                "is assigned."
            ),
            "term_start": (
                "Leave blank if the beginning of the term "
                "has not been specified."
            ),
            "term_end": (
                "Leave blank if the executive term has no "
                "specified end date."
            ),
        }

    def clean(self):
        """
        Validate the executive profile as a whole.
        """

        cleaned_data = super().clean()

        term_start = cleaned_data.get("term_start")
        term_end = cleaned_data.get("term_end")

        if (
            term_start
            and term_end
            and term_end < term_start
        ):
            self.add_error(
                "term_end",
                (
                    "The term end date cannot be earlier "
                    "than the term start date."
                ),
            )

        return cleaned_data


# =========================================================
# EXECUTIVE USER INFORMATION FORM
# =========================================================

class ExecutiveUserForm(forms.ModelForm):
    """
    Form for updating personal information stored on
    the accounts.User model.

    Executive role information is deliberately excluded.
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
                    "autocomplete": "given-name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Last Name",
                    "autocomplete": "family-name",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Email Address",
                    "autocomplete": "email",
                }
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Phone Number",
                    "autocomplete": "tel",
                }
            ),
            "profile_picture": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": "image/*",
                }
            ),
        }

        labels = {
            "first_name": "First Name",
            "last_name": "Last Name",
            "email": "Email Address",
            "phone_number": "Phone Number",
            "profile_picture": "Profile Picture",
        }


# =========================================================
# ASSIGN EXECUTIVE ROLE FORM
# =========================================================

class AssignExecutiveRoleForm(forms.Form):
    """
    Form used by an administrator to assign an official
    KUCSA executive role to an existing user.

    The selected role is stored on User.

    The ExecutiveService is responsible for performing
    the actual assignment and creating the Executive
    profile where necessary.
    """

    user = forms.ModelChoiceField(
        queryset=User.objects.none(),
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
        label="Select User",
        empty_label="Select a user",
        required=True,
    )

    role = forms.ChoiceField(
        choices=[],
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
        label="Executive Role",
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # -----------------------------------------------------
        # USERS ELIGIBLE FOR EXECUTIVE ASSIGNMENT
        # -----------------------------------------------------

        self.fields["user"].queryset = (
            User.objects
            .filter(
                is_active=True,
            )
            .exclude(
                role__in=EXECUTIVE_ROLES,
            )
            .order_by(
                "first_name",
                "last_name",
                "username",
            )
        )

        # -----------------------------------------------------
        # EXECUTIVE ROLES
        # -----------------------------------------------------

        self.fields["role"].choices = (
            get_executive_role_choices(
                include_empty=True
            )
        )

    def clean(self):
        """
        Prevent invalid or duplicate executive assignments.
        """

        cleaned_data = super().clean()

        user = cleaned_data.get("user")
        role = cleaned_data.get("role")

        if role and role not in EXECUTIVE_ROLES:
            self.add_error(
                "role",
                "Please select a valid KUCSA executive role.",
            )

        if user:
            if not user.is_active:
                self.add_error(
                    "user",
                    "Only active users can be assigned an "
                    "executive role.",
                )

            if user.role in EXECUTIVE_ROLES:
                self.add_error(
                    "user",
                    (
                        "This user already holds a KUCSA "
                        "executive role."
                    ),
                )

        return cleaned_data


# =========================================================
# EXECUTIVE ASSIGNMENT MODEL FORM
# =========================================================

class ExecutiveAssignmentForm(forms.ModelForm):
    """
    Model form for assigning an official KUCSA executive
    role directly to an existing User instance.

    This form is intended for administrative management
    of an existing executive.
    """

    class Meta:
        model = User

        fields = [
            "role",
        ]

        widgets = {
            "role": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
        }

        labels = {
            "role": "Executive Role",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["role"].choices = (
            get_executive_role_choices()
        )

    def clean_role(self):
        """
        Ensure only official KUCSA executive roles
        can be assigned.
        """

        role = self.cleaned_data.get("role")

        if role not in EXECUTIVE_ROLES:
            raise forms.ValidationError(
                "Please select a valid KUCSA executive role."
            )

        return role


# =========================================================
# EXECUTIVE MANAGEMENT FORM
# =========================================================

class ExecutiveManagementForm(forms.ModelForm):
    """
    Form used by administrators to manage an executive
    User account.

    This includes:
        - Personal information
        - Contact information
        - Executive role
        - Verification status

    Account authentication credentials are deliberately
    not managed here.
    """

    class Meta:
        model = User

        fields = [
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "role",
            "is_verified",
        ]

        widgets = {
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "First Name",
                    "autocomplete": "given-name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Last Name",
                    "autocomplete": "family-name",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Email Address",
                    "autocomplete": "email",
                }
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Phone Number",
                    "autocomplete": "tel",
                }
            ),
            "role": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "is_verified": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

        labels = {
            "first_name": "First Name",
            "last_name": "Last Name",
            "email": "Email Address",
            "phone_number": "Phone Number",
            "role": "Executive Role",
            "is_verified": "Verified Account",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["role"].choices = (
            get_executive_role_choices()
        )

    def clean_role(self):
        """
        Ensure that the selected role is an official
        KUCSA executive role.
        """

        role = self.cleaned_data.get("role")

        if role not in EXECUTIVE_ROLES:
            raise forms.ValidationError(
                "Please select a valid KUCSA executive role."
            )

        return role


# =========================================================
# EXECUTIVE SEARCH FORM
# =========================================================

class ExecutiveSearchForm(forms.Form):
    """
    Form used to search and filter KUCSA executives.

    Supported filters:

        - Name
        - Username
        - Registration number
        - Email
        - Role
        - Committee
        - Active status
        - Verification status
    """

    query = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Search by name, registration number, "
                    "username or email..."
                ),
                "autocomplete": "off",
            }
        ),
    )

    role = forms.ChoiceField(
        required=False,
        choices=[],
        label="Role",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    committee = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All Committees"),
            *Executive.Committee.choices,
        ],
        label="Committee",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    is_active = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All Statuses"),
            ("true", "Active"),
            ("false", "Inactive"),
        ],
        label="Status",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    is_verified = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All Verification Statuses"),
            ("true", "Verified"),
            ("false", "Not Verified"),
        ],
        label="Verification",
        widget=forms.Select(
            attrs={
                "class": "form-select",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["role"].choices = [
            ("", "All Executive Roles"),
            *get_executive_role_choices(),
        ]

    def clean_is_active(self):
        """
        Convert the HTML string value into a Python boolean.

        Empty value remains None so the service can interpret
        it as 'do not filter'.
        """

        value = self.cleaned_data.get("is_active")

        if value == "":
            return None

        return value == "true"

    def clean_is_verified(self):
        """
        Convert the HTML string value into a Python boolean.

        Empty value remains None.
        """

        value = self.cleaned_data.get("is_verified")

        if value == "":
            return None

        return value == "true"


# =========================================================
# EXECUTIVE STATUS FORM
# =========================================================

class ExecutiveStatusForm(forms.ModelForm):
    """
    Form used to activate or deactivate an executive profile.

    Administrative activation/deactivation should normally
    be performed through the corresponding service methods.
    """

    class Meta:
        model = Executive

        fields = [
            "is_active",
        ]

        widgets = {
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

        labels = {
            "is_active": "Executive Active",
        }


# =========================================================
# EXECUTIVE TERM FORM
# =========================================================

class ExecutiveTermForm(forms.ModelForm):
    """
    Form used to manage an executive's leadership term.
    """

    class Meta:
        model = Executive

        fields = [
            "term_start",
            "term_end",
        ]

        widgets = {
            "term_start": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "term_end": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
        }

        labels = {
            "term_start": "Term Start",
            "term_end": "Term End",
        }

    def clean(self):
        """
        Validate executive term dates.
        """

        cleaned_data = super().clean()

        term_start = cleaned_data.get("term_start")
        term_end = cleaned_data.get("term_end")

        if (
            term_start
            and term_end
            and term_end < term_start
        ):
            self.add_error(
                "term_end",
                (
                    "The term end date cannot be earlier "
                    "than the term start date."
                ),
            )

        return cleaned_data