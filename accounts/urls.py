
# accounts/urls.py

from django.urls import path

from . import views
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

app_name = "accounts"


urlpatterns = [

    # =========================================================
    # AUTHENTICATION
    # =========================================================

    path(
        "register/",
        views.register_view,
        name="register",
    ),

    path(
        "login/",
        views.login_view,
        name="login",
    ),

    path(
        "logout/",
        views.logout_view,
        name="logout",
    ),

    # =========================================================
    # USER PROFILE
    # =========================================================

    path(
        "profile/",
        views.profile_view,
        name="profile",
    ),

    path(
        "profile/update/",
        views.profile_update_view,
        name="profile_update",
    ),

   # =========================================================
    # PASSWORD MANAGEMENT
    # =========================================================

    # ---------------------------------------------------------
    # CHANGE PASSWORD
    # ---------------------------------------------------------
    #
    # For authenticated users who know their current password.
    #

    path(
        "change-password/",
        views.change_password_view,
        name="change_password",
    ),

    # ---------------------------------------------------------
    # FORGOT PASSWORD
    # ---------------------------------------------------------
    #
    # User enters their registered email address here.
    #
    # The view:
    #
    #     views.forgot_password_view
    #
    # processes the request and sends the secure reset email.
    #

    path(
        "forgot-password/",
        views.forgot_password_view,
        name="forgot_password",
    ),

    # ---------------------------------------------------------
    # PASSWORD RESET EMAIL SENT
    # ---------------------------------------------------------
    #
    # Django displays this page after the reset request has
    # been processed.
    #
    # IMPORTANT:
    #
    # This page intentionally does not reveal whether the
    # submitted email belongs to a KUCSA account.
    #

    path(
        "forgot-password/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name=(
                "password_reset_done.html"
            ),
        ),
        name="password_reset_done",
    ),

    # ---------------------------------------------------------
    # PASSWORD RESET CONFIRMATION
    # ---------------------------------------------------------
    #
    # This is the secure URL contained inside the email:
    #
    #     /reset-password/<uidb64>/<token>/
    #
    # Django validates:
    #
    #     - uidb64
    #     - password-reset token
    #     - token expiration
    #     - token validity
    #
    # The user then enters the new password.
    #

    path(
        "reset-password/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name=(
                "password_reset_confirm.html"
            ),
            success_url=reverse_lazy(
                "accounts:password_reset_complete"
            ),
        ),
        name="password_reset_confirm",
    ),

    # ---------------------------------------------------------
    # PASSWORD RESET COMPLETE
    # ---------------------------------------------------------
    #
    # Django redirects here after the new password has been
    # successfully saved.
    #

    path(
        "reset-password/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name=(
                "password_reset_complete.html"
            ),
        ),
        name="password_reset_complete",
    ),

    # ---------------------------------------------------------
    # LEGACY / GENERIC RESET PASSWORD URL
    # ---------------------------------------------------------
    #
    # Kept for backward compatibility.
    #
    # The actual secure reset URL contains:
    #
    #     <uidb64>/<token>
    #
    # This view redirects the generic URL to the forgot-password
    # page rather than attempting to reset a password without a
    # valid token.
    #

    path(
        "reset-password/",
        views.reset_password_view,
        name="reset_password",
    ),

    # =========================================================
    # EMAIL VERIFICATION
    # =========================================================

    path(
        "verify-email/",
        views.verify_email_view,
        name="verify_email",
    ),
]
