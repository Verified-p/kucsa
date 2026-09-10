
from django.shortcuts import redirect, render
from django.http import FileResponse
from django.conf import settings
from pathlib import Path

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


def landing_page_view(request):
    """
    Display the public KUCSA landing page.

    This page is accessible to both authenticated
    and unauthenticated users.
    """

    return render(
        request,
        "landing.html"
    )






def service_worker(request):
    """
    Serve the KUCSA PWA service worker from the website root.

    The actual service-worker.js file remains inside:
        static/service-worker.js

    But browsers receive it from:
        /service-worker.js

    This allows the service worker to control the entire
    KUCSA website rather than only /static/.
    """

    service_worker_path = (
        Path(settings.BASE_DIR)
        / "static"
        / "service-worker.js"
    )

    return FileResponse(
        open(service_worker_path, "rb"),
        content_type="application/javascript",
    )
