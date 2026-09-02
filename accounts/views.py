# accounts/views.py

import logging

from django.contrib import messages
from django.contrib.auth import (
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import (
    UserLoginForm,
    UserPasswordChangeForm,
    UserRegistrationForm,
    UserUpdateForm,
)
from .services import UserService


logger = logging.getLogger(__name__)


# =========================================================
# USER / MEMBER HELPERS
# =========================================================


def get_user_member(user):
    """
    Return the KUCSA Member profile associated with a user.

    The Member model defines the relationship using:

        related_name="member_profile"

    Returns:
        Member instance or None.
    """

    if not user or not user.is_authenticated:
        return None

    try:
        return user.member_profile
    except AttributeError:
        return None


def get_pending_payment(member):
    """
    Return the latest pending payment for a member.

    Returns:
        Payment instance or None.
    """

    if member is None or not member.pk:
        return None

    try:
        from payments.models import Payment

        return (
            Payment.objects
            .filter(
                member=member,
                status="PENDING",
            )
            .order_by("-created_at")
            .first()
        )

    except (ImportError, AttributeError):
        logger.exception(
            "Unable to retrieve pending payment."
        )
        return None


def get_user_payment_state(user):
    """
    Return the latest membership payment status.

    Possible values depend on the Payment model, for example:

        COMPLETED
        PENDING
        FAILED
        CANCELLED
        NONE
    """

    member = get_user_member(user)

    if member is None:
        return "NONE"

    try:
        payment = (
            member.payments
            .order_by("-created_at")
            .first()
        )

    except AttributeError:
        logger.exception(
            "Unable to retrieve payment state for user %s.",
            user.pk,
        )
        return "NONE"

    if payment is None:
        return "NONE"

    return payment.status


# =========================================================
# MEMBERSHIP ACCESS
# =========================================================


def user_has_paid_membership(user):
    """
    Return True only when the user's membership currently
    grants valid KUCSA platform access.

    The Member model is the source of truth for membership
    access through:

        member.can_access_platform
    """

    member = get_user_member(user)

    if member is None:
        return False

    try:
        return bool(member.can_access_platform)

    except AttributeError:
        logger.exception(
            "Unable to determine membership access "
            "for user %s.",
            user.pk,
        )
        return False


# =========================================================
# PAYMENT REDIRECTION
# =========================================================


def redirect_student_to_payment(request, member):
    """
    Route a student who does not currently have active
    membership access through the payment workflow.

    Flow:

        Pending payment
            ↓
        Payment Pending

        No pending payment
            ↓
        Create Payment
    """

    if member is None:
        messages.error(
            request,
            (
                "Your KUCSA membership profile could not be "
                "found. Please contact the administrator."
            ),
        )

        return redirect("core:home")

    pending_payment = get_pending_payment(member)

    if pending_payment:

        messages.info(
            request,
            (
                "Your M-Pesa membership payment is awaiting "
                "confirmation."
            ),
        )

        return redirect(
            "payments:payment_pending",
            payment_id=pending_payment.pk,
        )

    messages.info(
        request,
        (
            "Please complete your KUCSA membership payment "
            "to access the platform."
        ),
    )

    return redirect(
        "payments:payment_create"
    )


# =========================================================
# AUTHENTICATED USER DESTINATION
# =========================================================


def redirect_authenticated_user(request):
    """
    Determine the correct KUCSA platform destination for an
    authenticated user.

    IMPORTANT
    ---------

    Django administration access and KUCSA platform access
    are two separate concerns.

    Therefore:

        - is_staff does NOT determine the post-login page.
        - is_superuser does NOT determine the post-login page.
        - role determines the user's KUCSA organizational role.
        - membership determines platform access for students
          and executives.

    Normal login flow:

        ADMIN / SUPERUSER
            ↓
        KUCSA Dashboard

        EXECUTIVE + ACTIVE MEMBERSHIP
            ↓
        Executive Dashboard

        STUDENT + ACTIVE MEMBERSHIP
            ↓
        Student Dashboard

        STUDENT + NO ACTIVE MEMBERSHIP
            ↓
        Membership Payment

        UNKNOWN / INVALID STATE
            ↓
        KUCSA Home

    Django Admin remains available separately at /admin/.
    """

    user = request.user

    # =========================================================
    # AUTHENTICATION CHECK
    # =========================================================

    if not user.is_authenticated:
        return redirect("accounts:login")

    # =========================================================
    # ADMINISTRATOR / SUPERUSER
    # =========================================================
    #
    # IMPORTANT:
    #
    # Do NOT redirect administrators to:
    #
    #     admin:index
    #
    # Django Admin is a separate administration interface.
    # The normal application login should take the administrator
    # into the KUCSA platform.
    #
    # user.is_kucsa_admin returns True when:
    #
    #     role == ADMIN
    #
    # OR
    #
    #     is_superuser == True
    # =========================================================

    if user.is_kucsa_admin:

        return redirect(
            "dashboard:dashboard"
        )

    # =========================================================
    # EXECUTIVE
    # =========================================================
    #
    # Executives are still KUCSA members.
    #
    # Therefore an executive must have valid active membership
    # before accessing the executive dashboard.
    # =========================================================

    if user.is_executive:

        # -----------------------------------------------------
        # ACTIVE MEMBERSHIP
        # -----------------------------------------------------

        if user.has_active_membership:

            return redirect(
                "dashboard:executive_dashboard"
            )

        # -----------------------------------------------------
        # EXECUTIVE WITHOUT ACTIVE MEMBERSHIP
        # -----------------------------------------------------

        messages.warning(
            request,
            (
                "Your executive account does not currently "
                "have active KUCSA membership. Please complete "
                "your membership payment to access the "
                "executive dashboard."
            ),
        )

        return redirect(
            "dashboard:dashboard"
        )

    # =========================================================
    # STUDENT / GENERAL MEMBER
    # =========================================================

    if user.role == user.Role.STUDENT:

        member = get_user_member(user)

        # -----------------------------------------------------
        # MEMBER PROFILE REQUIRED
        # -----------------------------------------------------

        if member is None:

            messages.warning(
                request,
                (
                    "Your KUCSA membership profile could not "
                    "be found. Please contact the administrator."
                ),
            )

            return redirect(
                "core:home"
            )

        # -----------------------------------------------------
        # ACTIVE MEMBERSHIP
        # -----------------------------------------------------

        if user.has_active_membership:

            return redirect(
                "dashboard:student_dashboard"
            )

        # -----------------------------------------------------
        # PAYMENT REQUIRED
        # -----------------------------------------------------

        return redirect_student_to_payment(
            request,
            member,
        )

    # =========================================================
    # FALLBACK
    # =========================================================
    #
    # This protects the application from unexpected or
    # unsupported account states.
    # =========================================================

    messages.info(
        request,
        (
            "Your account has been authenticated, but "
            "your KUCSA account role has not been configured."
        ),
    )

    return redirect(
        "core:home"
    )



# =========================================================
# REGISTER
# =========================================================


def register_view(request):
    """
    Register a new KUCSA platform user.

    Registration creates the account and, through
    UserService.create_user(), creates the associated
    pending Member profile.

    Registration does NOT activate membership.

    Flow:

        Register
            ↓
        User account
            ↓
        Pending Member profile
            ↓
        Login
            ↓
        Membership payment
    """

    if request.user.is_authenticated:

        return redirect_authenticated_user(request)

    if request.method == "POST":

        form = UserRegistrationForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():

            try:

                UserService.create_user(form)

            except Exception as exc:

                logger.exception(
                    "KUCSA user registration failed."
                )

                messages.error(
                    request,
                    (
                        "We could not create your account. "
                        "Please check your information "
                        "and try again."
                    ),
                )

                form.add_error(
                    None,
                    str(exc),
                )

            else:

                messages.success(
                    request,
                    (
                        "Your account has been created "
                        "successfully. Please log in to "
                        "complete your KUCSA membership payment."
                    ),
                )

                return redirect(
                    "accounts:login"
                )

    else:

        form = UserRegistrationForm()

    return render(
        request,
        "register.html",
        {
            "form": form,
        },
    )


# =========================================================
# LOGIN
# =========================================================

def login_view(request):
    """
    Authenticate a KUCSA platform user.

    Authentication and Django administration privileges are
    separate from KUCSA platform navigation.

    After successful authentication, users are always routed
    into the KUCSA platform rather than Django Admin.

    Routing:

        Administrator / Superuser
            ↓
        KUCSA Dashboard

        Executive
            ↓
        Executive Dashboard

        Student with active membership
            ↓
        Student Dashboard

        Student without active membership
            ↓
        Membership / Payment flow
    """

    # =========================================================
    # ALREADY AUTHENTICATED
    # =========================================================

    if request.user.is_authenticated:
        return redirect_authenticated_user(request)

    # =========================================================
    # LOGIN
    # =========================================================

    if request.method == "POST":

        form = UserLoginForm(
            request,
            data=request.POST,
        )

        if form.is_valid():

            username = form.cleaned_data.get(
                "username"
            )

            password = form.cleaned_data.get(
                "password"
            )

            user = UserService.authenticate_user(
                username=username,
                password=password,
            )

            if user is not None:

                # -------------------------------------------------
                # CREATE LOGIN SESSION
                # -------------------------------------------------

                login(
                    request,
                    user,
                )

                # -------------------------------------------------
                # SUCCESS MESSAGE
                # -------------------------------------------------

                messages.success(
                    request,
                    (
                        f"Welcome back, "
                        f"{user.first_name or user.username}."
                    ),
                )

                # -------------------------------------------------
                # KUCSA PLATFORM REDIRECT
                # -------------------------------------------------

                return redirect_authenticated_user(
                    request
                )

            messages.error(
                request,
                "Invalid username or password.",
            )

    # =========================================================
    # GET REQUEST
    # =========================================================

    else:

        form = UserLoginForm()

    return render(
        request,
        "login.html",
        {
            "form": form,
        },
    )


# =========================================================
# LOGOUT
# =========================================================


@login_required
def logout_view(request):
    """
    Log out the authenticated user.
    """

    logout(request)

    messages.success(
        request,
        "You have logged out successfully.",
    )

    return redirect(
        "accounts:login"
    )


# =========================================================
# PROFILE
# =========================================================


@login_required
def profile_view(request):
    """
    Display the authenticated user's profile.

    Students must have valid active membership access
    before accessing their profile.

    Administrators and executives are not subject to the
    student payment gate.
    """

    user = request.user

    # =====================================================
    # STUDENT MEMBERSHIP GATE
    # =====================================================

    if user.role == user.Role.STUDENT:

        member = get_user_member(user)

        # -------------------------------------------------
        # MEMBER PROFILE REQUIRED
        # -------------------------------------------------

        if member is None:

            messages.warning(
                request,
                (
                    "Your KUCSA membership profile could not "
                    "be found. Please contact the administrator."
                ),
            )

            return redirect(
                "core:home"
            )

        # -------------------------------------------------
        # ACTIVE MEMBERSHIP REQUIRED
        # -------------------------------------------------

        if not user_has_paid_membership(user):

            return redirect_student_to_payment(
                request,
                member,
            )

    else:

        member = get_user_member(user)

    # =====================================================
    # PROFILE
    # =====================================================

    return render(
        request,
        "profile.html",
        {
            "user": user,
            "member": member,
        },
    )


# =========================================================
# PROFILE UPDATE
# =========================================================


@login_required
def profile_update_view(request):
    """
    Update the authenticated user's account information.

    Students must have active membership access before
    modifying their profile.

    Administrators and executives can update their account
    information without passing through the student payment
    gate.
    """

    user = request.user

    # =====================================================
    # STUDENT MEMBERSHIP GATE
    # =====================================================

    if user.role == user.Role.STUDENT:

        member = get_user_member(user)

        if member is None:

            messages.warning(
                request,
                (
                    "Your KUCSA membership profile could not "
                    "be found. Please contact the administrator."
                ),
            )

            return redirect(
                "core:home"
            )

        if not user_has_paid_membership(user):

            return redirect_student_to_payment(
                request,
                member,
            )

    # =====================================================
    # FORM
    # =====================================================

    if request.method == "POST":

        form = UserUpdateForm(
            request.POST,
            request.FILES,
            instance=user,
        )

        if form.is_valid():

            UserService.update_profile(
                user,
                form,
            )

            messages.success(
                request,
                "Your profile has been updated successfully.",
            )

            return redirect(
                "accounts:profile"
            )

    else:

        form = UserUpdateForm(
            instance=user,
        )

    return render(
        request,
        "profile_update.html",
        {
            "form": form,
            "user": user,
        },
    )


# =========================================================
# CHANGE PASSWORD
# =========================================================


@login_required
def change_password_view(request):
    """
    Allow an authenticated user to change their password.

    Password management is an account-security function and
    therefore does not depend on membership payment status.
    """

    if request.method == "POST":

        form = UserPasswordChangeForm(
            request.user,
            request.POST,
        )

        if form.is_valid():

            user = UserService.change_password(
                request.user,
                form,
            )

            update_session_auth_hash(
                request,
                user,
            )

            messages.success(
                request,
                "Your password has been changed successfully.",
            )

            return redirect_authenticated_user(
                request
            )

    else:

        form = UserPasswordChangeForm(
            request.user,
        )

    return render(
        request,
        "change_password.html",
        {
            "form": form,
        },
    )


# =========================================================
# FORGOT PASSWORD
# =========================================================


def forgot_password_view(request):
    """
    Display the password recovery page.

    The actual password-reset workflow can be handled by
    the dedicated password-reset service/forms.
    """

    if request.user.is_authenticated:

        return redirect_authenticated_user(
            request
        )

    return render(
        request,
        "forgot_password.html",
    )


# =========================================================
# RESET PASSWORD
# =========================================================


def reset_password_view(request):
    """
    Display the password reset page.

    The actual password-reset workflow can be handled by
    the dedicated password-reset service/forms.
    """

    if request.user.is_authenticated:

        return redirect_authenticated_user(
            request
        )

    return render(
        request,
        "reset_password.html",
    )


# =========================================================
# EMAIL VERIFICATION
# =========================================================


@login_required
def verify_email_view(request):
    """
    Display the email verification page.

    Email verification is intentionally separate from:

        - M-Pesa payment verification
        - KUCSA membership activation
        - platform access
    """

    return render(
        request,
        "verify_email.html",
        {
            "user": request.user,
        },
    )