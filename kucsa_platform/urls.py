# kucsa_platform/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    # =====================================================
    # ADMIN
    # =====================================================

    path(
        "admin/",
        admin.site.urls,
    ),

    # =====================================================
    # AUTHENTICATION
    # =====================================================

    path(
        "accounts/",
        include("accounts.urls"),
    ),

    # =====================================================
    # PUBLIC WEBSITE
    # =====================================================

    path(
        "",
        include("core.urls"),
    ),

    # =====================================================
    # DASHBOARD
    # =====================================================

    path(
        "dashboard/",
        include("dashboard.urls"),
    ),

    # =====================================================
    # MEMBERS
    # =====================================================

    path(
        "members/",
        include("members.urls"),
    ),

    # =====================================================
    # EXECUTIVES
    # =====================================================

    path(
        "executives/",
        include("executives.urls"),
    ),

    # =====================================================
    # EVENTS
    # =====================================================

    path(
        "events/",
        include("events.urls"),
    ),

    # =====================================================
    # ATTENDANCE
    # =====================================================

    path(
        "attendance/",
        include("attendance.urls"),
    ),

    # =====================================================
    # ANNOUNCEMENTS
    # =====================================================

    path(
        "announcements/",
        include("announcements.urls"),
    ),

    # =====================================================
    # PAYMENTS
    # =====================================================

    path(
        "payments/",
        include("payments.urls"),
    ),

    path(
        "finance/",
        include("finance.urls"),
        ),


    # =====================================================
    # REPORTS
    # =====================================================


]


# =========================================================
# MEDIA FILES - DEVELOPMENT ONLY
# =========================================================

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )