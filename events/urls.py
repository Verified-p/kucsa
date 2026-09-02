# events/urls.py

from django.urls import path

from . import views


app_name = "events"


urlpatterns = [

    # =========================================================
    # EVENT DISCOVERY
    # =========================================================

    path(
        "",
        views.event_list,
        name="list",
    ),

    path(
        "my-events/",
        views.my_events,
        name="my_events",
    ),

    # =========================================================
    # EVENT CREATION
    # =========================================================

    path(
        "create/",
        views.create_event,
        name="create",
    ),

    # =========================================================
    # EVENT REGISTRATION
    # =========================================================

    path(
        "<int:pk>/register/",
        views.event_registration,
        name="register",
    ),

    path(
        "<int:pk>/cancel-registration/",
        views.cancel_registration,
        name="cancel_registration",
    ),

    # =========================================================
    # EVENT MANAGEMENT
    #
    # Executives/Admins only.
    # Permission checks are handled inside the views.
    # =========================================================

    path(
        "<int:pk>/edit/",
        views.update_event,
        name="update",
    ),

    path(
        "<int:pk>/publish/",
        views.publish_event,
        name="publish",
    ),

    path(
        "<int:pk>/cancel/",
        views.cancel_event,
        name="cancel",
    ),

    path(
        "<int:pk>/complete/",
        views.complete_event,
        name="complete",
    ),

    # =========================================================
    # ATTENDANCE MANAGEMENT
    #
    # Executives/Admins only.
    # =========================================================

    path(
        "registration/<int:registration_id>/attendance/",
        views.update_attendance,
        name="update_attendance",
    ),

    # =========================================================
    # EVENT DETAIL
    #
    # IMPORTANT:
    # Keep this route LAST because <int:pk>/ is generic.
    # =========================================================

    path(
        "<int:pk>/",
        views.event_detail,
        name="detail",
    ),
]