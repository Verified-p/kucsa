
# dashboard/urls.py

from django.urls import path

from . import views


app_name = "dashboard"


urlpatterns = [

    # =========================================================
    # MAIN DASHBOARD
    # =========================================================

    path(
        "",
        views.dashboard_view,
        name="dashboard",
    ),

    # =========================================================
    # STUDENT DASHBOARD
    # =========================================================

    path(
        "student/",
        views.student_dashboard_view,
        name="student_dashboard",
    ),

    # =========================================================
    # EXECUTIVE DASHBOARD
    # =========================================================

    path(
        "executive/",
        views.executive_dashboard_view,
        name="executive_dashboard",
    ),

    # =========================================================
    # DASHBOARD ANALYTICS
    # =========================================================

    path(
        "analytics/",
        views.analytics_view,
        name="analytics",
    ),

    # =========================================================
    # DASHBOARD WIDGETS
    # =========================================================

    path(
        "widgets/",
        views.widgets_view,
        name="widgets",
    ),
]
