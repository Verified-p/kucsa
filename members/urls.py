# members/urls.py

from django.urls import path

from . import views


app_name = "members"


urlpatterns = [

    # =====================================================
    # MEMBER LIST
    # =====================================================

    path(
        "",
        views.member_list,
        name="list",
    ),

    # =====================================================
    # MY PROFILE
    # =====================================================

    path(
        "profile/",
        views.member_profile,
        name="profile",
    ),

    path(
        "profile/edit/",
        views.edit_member_profile,
        name="edit_profile",
    ),

    # =====================================================
    # TECHNICAL DOMAINS
    # =====================================================

    path(
        "technical-domains/",
        views.technical_domains,
        name="technical_domains",
    ),

    # =====================================================
    # MEMBERSHIP STATUS
    # =====================================================

    path(
        "membership-status/",
        views.membership_status,
        name="membership_status",
    ),

    # =====================================================
    # CREATE MEMBER
    # =====================================================

    path(
        "create/",
        views.create_member,
        name="create",
    ),

    # =====================================================
    # MEMBER DETAIL
    # =====================================================

    path(
        "<int:pk>/",
        views.member_detail,
        name="detail",
    ),

    # =====================================================
    # EDIT MEMBER
    # =====================================================

    path(
        "<int:pk>/edit/",
        views.edit_member,
        name="edit",
    ),

    # =====================================================
    # MEMBERSHIP MANAGEMENT
    # =====================================================

    path(
        "<int:pk>/membership-status/update/",
        views.update_membership_status,
        name="update_membership_status",
    ),

    path(
        "<int:pk>/approve/",
        views.approve_member,
        name="approve",
    ),

    path(
        "<int:pk>/reject/",
        views.reject_member,
        name="reject",
    ),

    path(
        "<int:pk>/suspend/",
        views.suspend_member,
        name="suspend",
    ),

    # =====================================================
    # DELETE MEMBER
    # =====================================================

    path(
        "<int:pk>/delete/",
        views.delete_member,
        name="delete",
    ),
]