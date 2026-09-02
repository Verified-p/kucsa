
# accounts/urls.py

from django.urls import path

from . import views


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

    path(
        "change-password/",
        views.change_password_view,
        name="change_password",
    ),

    path(
        "forgot-password/",
        views.forgot_password_view,
        name="forgot_password",
    ),

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
