
# executives/urls.py

from django.urls import path

from . import views


app_name = "executives"


urlpatterns = [

    # =========================================================
    # EXECUTIVE DASHBOARD
    # =========================================================

    path(
        "",
        views.executive_dashboard,
        name="dashboard",
    ),

    path(
        "dashboard/",
        views.executive_dashboard,
        name="executive_dashboard",
    ),

    # =========================================================
    # EXECUTIVE BOARD
    # =========================================================

    path(
        "board/",
        views.executive_board,
        name="board",
    ),

    # =========================================================
    # EXECUTIVE LIST
    # =========================================================

    path(
        "list/",
        views.executive_list,
        name="list",
    ),

    # =========================================================
    # EXECUTIVE SEARCH
    # =========================================================

    path(
        "search/",
        views.executive_search,
        name="search",
    ),

    # =========================================================
    # CURRENT USER EXECUTIVE PROFILE
    # =========================================================

    path(
        "profile/",
        views.executive_profile,
        name="profile",
    ),

    # =========================================================
    # EDIT CURRENT EXECUTIVE PROFILE
    # =========================================================

    path(
        "profile/edit/",
        views.edit_executive_profile,
        name="edit_profile",
    ),

    # =========================================================
    # VIEW SPECIFIC EXECUTIVE PROFILE
    # =========================================================
    #
    # IMPORTANT:
    #
    # This route must exist because views such as
    # assign_role() redirect using:
    #
    #     executives:profile
    #     pk=executive.pk
    #
    # Example:
    #
    #     /executives/profile/1/
    #
    # =========================================================

    path(
        "profile/<int:pk>/",
        views.executive_profile,
        name="profile_detail",
    ),

    # =========================================================
    # ASSIGN EXECUTIVE ROLE
    # =========================================================

    path(
        "assign-role/",
        views.assign_role,
        name="assign_role",
    ),

    # =========================================================
    # REMOVE EXECUTIVE ROLE
    # =========================================================

    path(
        "<int:pk>/remove-role/",
        views.remove_role,
        name="remove_role",
    ),

    # =========================================================
    # ACTIVATE EXECUTIVE
    # =========================================================

    path(
        "<int:pk>/activate/",
        views.activate_executive,
        name="activate",
    ),

    # =========================================================
    # DEACTIVATE EXECUTIVE
    # =========================================================

    path(
        "<int:pk>/deactivate/",
        views.deactivate_executive,
        name="deactivate",
    ),

    # =========================================================
    # EXECUTIVE DETAIL
    # =========================================================
    #
    # Kept as a separate route for backwards compatibility.
    #
    # Example:
    #
    #     /executives/1/
    #
    # This uses the same executive_profile view but has
    # a different URL name from profile_detail.
    #
    # =========================================================

    path(
        "<int:pk>/",
        views.executive_profile,
        name="detail",
    ),
]
