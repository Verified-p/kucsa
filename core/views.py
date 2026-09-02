
from django.shortcuts import redirect, render


# =========================================================
# HOME / PLATFORM ENTRY
# =========================================================


def home_view(request):
    """
    Display the KUCSA platform entry point.

    Unauthenticated users are redirected to the login page.

    Authenticated users are redirected through the central
    KUCSA authentication routing logic, which determines
    whether they should go to:

        - Administrator dashboard
        - Executive dashboard
        - Student dashboard
        - Membership payment
        - Appropriate fallback destination
    """

    # =====================================================
    # AUTHENTICATION CHECK
    # =====================================================

    if not request.user.is_authenticated:

        return redirect(
            "accounts:login"
        )

    # =====================================================
    # AUTHENTICATED USER
    # =====================================================
    #
    # Use the existing centralized authentication routing
    # logic from the accounts application.
    # =====================================================

    from accounts.views import redirect_authenticated_user

    return redirect_authenticated_user(request)


# =========================================================
# ABOUT
# =========================================================


def about_view(request):
    """
    Display the public About page.
    """

    return render(
        request,
        "about.html",
    )


# =========================================================
# CONTACT
# =========================================================


def contact_view(request):
    """
    Display the public Contact page.
    """

    return render(
        request,
        "contact.html",
    )


# =========================================================
# FAQ
# =========================================================


def faq_view(request):
    """
    Display the public Frequently Asked Questions page.
    """

    return render(
        request,
        "faq.html",
    )


# =========================================================
# CUSTOM 404
# =========================================================


def error_404_view(request, exception):
    """
    Display the custom 404 error page.
    """

    return render(
        request,
        "error_404.html",
        status=404,
    )
