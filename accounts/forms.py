# accounts/forms.py

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
)


User = get_user_model()


# =========================================================
# COMMON FORM STYLING
# =========================================================


class BootstrapFormMixin:
    """
    Apply Bootstrap styling consistently to form fields.

    Normal fields:
        form-control

    Select fields:
        form-select

    Checkbox / radio fields:
        form-check-input
    """

    def apply_bootstrap_classes(self):
        for field in self.fields.values():

            widget = field.widget

            # -------------------------------------------------
            # CHECKBOXES
            # -------------------------------------------------

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"
                continue

            # -------------------------------------------------
            # RADIO BUTTONS
            # -------------------------------------------------

            if isinstance(widget, forms.RadioSelect):
                widget.attrs["class"] = "form-check-input"
                continue

            # -------------------------------------------------
            # SELECT FIELDS
            # -------------------------------------------------

            if isinstance(
                widget,
                (
                    forms.Select,
                    forms.SelectMultiple,
                ),
            ):
                existing_class = widget.attrs.get(
                    "class",
                    "",
                )

                if "form-select" not in existing_class:
                    widget.attrs["class"] = (
                        f"{existing_class} form-select"
                    ).strip()

                continue

            # -------------------------------------------------
            # NORMAL INPUTS
            # -------------------------------------------------

            existing_class = widget.attrs.get(
                "class",
                "",
            )

            if "form-control" not in existing_class:
                widget.attrs["class"] = (
                    f"{existing_class} form-control"
                ).strip()


# =========================================================
# USER REGISTRATION
# =========================================================


class UserRegistrationForm(
    BootstrapFormMixin,
    UserCreationForm,
):
    """
    Register a new KUCSA platform user.

    RESPONSIBILITY
    --------------

    This form creates and validates the User account only.

    It does NOT:

        - create a payment
        - process M-Pesa
        - verify payment
        - activate membership
        - grant platform access
        - create an executive profile

    Those responsibilities belong to the appropriate
    services and applications.

    Registration flow:

        Registration
             ↓
        User created
             ↓
        Member profile created by UserService
             ↓
        Login
             ↓
        Membership payment
             ↓
        Payment verification
             ↓
        Membership activation
             ↓
        Platform access
    """

    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Create a password",
                "autocomplete": "new-password",
            }
        ),
        help_text=(
            "Use a strong password that you do not use "
            "on other websites."
        ),
    )

    password2 = forms.CharField(
        label="Confirm Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm your password",
                "autocomplete": "new-password",
            }
        ),
    )

    class Meta:
        model = User

        fields = [
            "first_name",
            "last_name",
            "username",
            "registration_number",
            "email",
            "phone_number",
            "profile_picture",
            "password1",
            "password2",
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
            "username": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Choose a username",
                    "autocomplete": "username",
                }
            ),
            "registration_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "University Registration Number",
                    "autocomplete": "off",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "University Email Address",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()

    # -----------------------------------------------------
    # FIRST NAME
    # -----------------------------------------------------

    def clean_first_name(self):
        first_name = self.cleaned_data.get("first_name")

        if not first_name:
            return first_name

        return " ".join(
            first_name.strip().split()
        )

    # -----------------------------------------------------
    # LAST NAME
    # -----------------------------------------------------

    def clean_last_name(self):
        last_name = self.cleaned_data.get("last_name")

        if not last_name:
            return last_name

        return " ".join(
            last_name.strip().split()
        )

    # -----------------------------------------------------
    # USERNAME
    # -----------------------------------------------------

    def clean_username(self):
        username = self.cleaned_data.get("username")

        if not username:
            return username

        username = username.strip()

        if not username:
            raise forms.ValidationError(
                "Username cannot be empty."
            )

        queryset = User.objects.filter(
            username__iexact=username
        )

        if queryset.exists():
            raise forms.ValidationError(
                "This username is already taken."
            )

        return username

    # -----------------------------------------------------
    # EMAIL
    # -----------------------------------------------------

    def clean_email(self):
        email = self.cleaned_data.get("email")

        if not email:
            return email

        email = email.strip().lower()

        queryset = User.objects.filter(
            email__iexact=email
        )

        if queryset.exists():
            raise forms.ValidationError(
                "An account with this email already exists."
            )

        return email

    # -----------------------------------------------------
    # REGISTRATION NUMBER
    # -----------------------------------------------------

    def clean_registration_number(self):
        registration_number = self.cleaned_data.get(
            "registration_number"
        )

        if not registration_number:
            return registration_number

        registration_number = (
            registration_number.strip().upper()
        )

        if not registration_number:
            raise forms.ValidationError(
                "Registration number cannot be empty."
            )

        queryset = User.objects.filter(
            registration_number__iexact=registration_number
        )

        if queryset.exists():
            raise forms.ValidationError(
                "This registration number is already registered."
            )

        return registration_number

    # -----------------------------------------------------
    # PHONE NUMBER
    # -----------------------------------------------------

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get(
            "phone_number"
        )

        if not phone_number:
            return phone_number

        phone_number = " ".join(
            phone_number.strip().split()
        )

        return phone_number

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    def save(self, commit=True):
        """
        Create the User account securely.

        New registrations always start as:

            is_active = True
            is_verified = False
            role = STUDENT

        Membership activation is handled separately.
        """

        user = super().save(commit=False)

        user.is_active = True
        user.is_verified = False

        # -------------------------------------------------
        # FORCE NORMAL REGISTRATION TO STUDENT
        # -------------------------------------------------
        #
        # Do not trust a model default or submitted value
        # for the role during public registration.
        #

        user.role = User.Role.STUDENT

        if commit:
            user.save()

        return user


# =========================================================
# LOGIN
# =========================================================


class UserLoginForm(
    AuthenticationForm,
    BootstrapFormMixin,
):
    """
    KUCSA authentication form.

    Authentication and membership authorization are
    deliberately separate.

    After successful authentication:

        Active membership
            → Dashboard

        No active membership
            → Payment flow
    """

    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Username",
                "autocomplete": "username",
                "autofocus": True,
            }
        ),
    )

    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Password",
                "autocomplete": "current-password",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()


# =========================================================
# UPDATE USER PROFILE
# =========================================================


class UserUpdateForm(
    BootstrapFormMixin,
    forms.ModelForm,
):
    """
    Update the authenticated user's personal information.

    Security-sensitive fields are intentionally excluded:

        - role
        - is_staff
        - is_superuser
        - is_verified
        - is_active
        - registration_number

    These fields must only be managed through protected
    administrative workflows.
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()

    # -----------------------------------------------------
    # FIRST NAME
    # -----------------------------------------------------

    def clean_first_name(self):
        first_name = self.cleaned_data.get("first_name")

        if not first_name:
            return first_name

        return " ".join(
            first_name.strip().split()
        )

    # -----------------------------------------------------
    # LAST NAME
    # -----------------------------------------------------

    def clean_last_name(self):
        last_name = self.cleaned_data.get("last_name")

        if not last_name:
            return last_name

        return " ".join(
            last_name.strip().split()
        )

    # -----------------------------------------------------
    # EMAIL
    # -----------------------------------------------------

    def clean_email(self):
        email = self.cleaned_data.get("email")

        if not email:
            return email

        email = email.strip().lower()

        queryset = User.objects.filter(
            email__iexact=email
        )

        if self.instance and self.instance.pk:
            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():
            raise forms.ValidationError(
                "An account with this email already exists."
            )

        return email

    # -----------------------------------------------------
    # PHONE NUMBER
    # -----------------------------------------------------

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get(
            "phone_number"
        )

        if not phone_number:
            return phone_number

        return " ".join(
            phone_number.strip().split()
        )


# =========================================================
# PASSWORD CHANGE
# =========================================================


class UserPasswordChangeForm(
    PasswordChangeForm,
    BootstrapFormMixin,
):
    """
    Allow an authenticated user to securely change
    their password.

    Django's PasswordChangeForm handles:

        - current password verification
        - new password confirmation
        - password validation
        - password hashing
    """

    old_password = forms.CharField(
        label="Current Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Current Password",
                "autocomplete": "current-password",
            }
        ),
    )

    new_password1 = forms.CharField(
        label="New Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "New Password",
                "autocomplete": "new-password",
            }
        ),
        help_text=(
            "Your new password should be strong and "
            "different from your current password."
        ),
    )

    new_password2 = forms.CharField(
        label="Confirm New Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm New Password",
                "autocomplete": "new-password",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()


# =========================================================
# ADMIN / STAFF USER UPDATE
# =========================================================


class AdminUserUpdateForm(
    BootstrapFormMixin,
    forms.ModelForm,
):
    """
    Administrative user-management form.

    This form must ONLY be exposed through protected
    administrator views.

    Administrators can manage:

        - Personal information
        - Username
        - Registration number
        - Email
        - Phone number
        - Profile picture
        - Role
        - Account activation
        - Verification status
        - Staff status

    IMPORTANT:

    Membership activation is NOT controlled here.

    Membership activation must continue to happen through
    the verified payment/membership workflow.
    """

    class Meta:
        model = User

        fields = [
            "first_name",
            "last_name",
            "username",
            "registration_number",
            "email",
            "phone_number",
            "profile_picture",
            "role",
            "is_active",
            "is_verified",
            "is_staff",
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
            "username": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Username",
                }
            ),
            "registration_number": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Registration Number",
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
            "role": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
            "is_verified": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
            "is_staff": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()

        # Explicitly preserve Bootstrap checkbox styling.
        for field_name in (
            "is_active",
            "is_verified",
            "is_staff",
        ):
            if field_name in self.fields:
                self.fields[
                    field_name
                ].widget.attrs["class"] = (
                    "form-check-input"
                )

    # -----------------------------------------------------
    # FIRST NAME
    # -----------------------------------------------------

    def clean_first_name(self):
        first_name = self.cleaned_data.get("first_name")

        if not first_name:
            return first_name

        return " ".join(
            first_name.strip().split()
        )

    # -----------------------------------------------------
    # LAST NAME
    # -----------------------------------------------------

    def clean_last_name(self):
        last_name = self.cleaned_data.get("last_name")

        if not last_name:
            return last_name

        return " ".join(
            last_name.strip().split()
        )

    # -----------------------------------------------------
    # USERNAME
    # -----------------------------------------------------

    def clean_username(self):
        username = self.cleaned_data.get("username")

        if not username:
            return username

        username = username.strip()

        queryset = User.objects.filter(
            username__iexact=username
        )

        if self.instance and self.instance.pk:
            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():
            raise forms.ValidationError(
                "This username is already taken."
            )

        return username

    # -----------------------------------------------------
    # EMAIL
    # -----------------------------------------------------

    def clean_email(self):
        email = self.cleaned_data.get("email")

        if not email:
            return email

        email = email.strip().lower()

        queryset = User.objects.filter(
            email__iexact=email
        )

        if self.instance and self.instance.pk:
            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():
            raise forms.ValidationError(
                "An account with this email already exists."
            )

        return email

    # -----------------------------------------------------
    # REGISTRATION NUMBER
    # -----------------------------------------------------

    def clean_registration_number(self):
        registration_number = self.cleaned_data.get(
            "registration_number"
        )

        if not registration_number:
            return registration_number

        registration_number = (
            registration_number.strip().upper()
        )

        queryset = User.objects.filter(
            registration_number__iexact=registration_number
        )

        if self.instance and self.instance.pk:
            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():
            raise forms.ValidationError(
                "This registration number is already registered."
            )

        return registration_number

    # -----------------------------------------------------
    # PHONE NUMBER
    # -----------------------------------------------------

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get(
            "phone_number"
        )

        if not phone_number:
            return phone_number

        return " ".join(
            phone_number.strip().split()
        )