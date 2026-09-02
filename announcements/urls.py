
# announcements/urls.py

from django.urls import path

from . import views


app_name = "announcements"


urlpatterns = [
    # =========================================================
    # ANNOUNCEMENT LIST
    # =========================================================

    path(
        "",
        views.announcement_list,
        name="list",
    ),

    # =========================================================
    # ANNOUNCEMENT MANAGEMENT
    # =========================================================

    path(
        "management/",
        views.announcement_management,
        name="management",
    ),

    # =========================================================
    # RECENT ANNOUNCEMENTS
    # =========================================================

    path(
        "recent/",
        views.recent_announcements,
        name="recent",
    ),

    # =========================================================
    # FEATURED ANNOUNCEMENTS
    # =========================================================

    path(
        "featured/",
        views.featured_announcements,
        name="featured",
    ),

    # =========================================================
    # EXPIRE ANNOUNCEMENTS
    # =========================================================

    path(
        "expire/",
        views.expire_announcements_view,
        name="expire",
    ),

    # =========================================================
    # CREATE ANNOUNCEMENT
    # =========================================================

    path(
        "create/",
        views.create_announcement_view,
        name="create",
    ),

    # =========================================================
    # ANNOUNCEMENT DETAIL
    # =========================================================

    path(
        "<int:pk>/",
        views.announcement_detail,
        name="detail",
    ),

    # =========================================================
    # EDIT ANNOUNCEMENT
    # =========================================================

    path(
        "<int:pk>/edit/",
        views.edit_announcement,
        name="edit",
    ),

    # =========================================================
    # PUBLISH ANNOUNCEMENT
    # =========================================================

    path(
        "<int:pk>/publish/",
        views.publish_announcement_view,
        name="publish",
    ),

    # =========================================================
    # UNPUBLISH ANNOUNCEMENT
    # =========================================================

    path(
        "<int:pk>/unpublish/",
        views.unpublish_announcement_view,
        name="unpublish",
    ),

    # =========================================================
    # ARCHIVE ANNOUNCEMENT
    # =========================================================

    path(
        "<int:pk>/archive/",
        views.archive_announcement_view,
        name="archive",
    ),

    # =========================================================
    # RESTORE ANNOUNCEMENT
    # =========================================================

    path(
        "<int:pk>/restore/",
        views.restore_announcement_view,
        name="restore",
    ),

    # =========================================================
    # FEATURE ANNOUNCEMENT
    # =========================================================

    path(
        "<int:pk>/feature/",
        views.feature_announcement_view,
        name="feature",
    ),

    # =========================================================
    # UNFEATURE ANNOUNCEMENT
    # =========================================================

    path(
        "<int:pk>/unfeature/",
        views.unfeature_announcement_view,
        name="unfeature",
    ),

    # =========================================================
    # DELETE ANNOUNCEMENT
    # =========================================================

    path(
        "<int:pk>/delete/",
        views.delete_announcement_view,
        name="delete",
    ),

    # =========================================================
    # CHANGE ANNOUNCEMENT STATUS
    # =========================================================

    path(
        "<int:pk>/status/",
        views.change_announcement_status,
        name="change_status",
    ),
]

