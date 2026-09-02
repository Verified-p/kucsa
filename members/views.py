# members/views.py

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    MemberForm,
    MemberProfileForm,
    MemberUserForm,
)
from .models import Member
from .services import MemberService


User = get_user_model()


# =========================================================
# ACCESS CONTROL HELPERS
# =========================================================


def is_admin(user):
    """
    Determine whether the authenticated user has
    administrator privileges.

    An administrator is identified by any of:

        - User role = ADMIN
        - is_staff = True
        - is_superuser = True
    """

    if not user or not user.is_authenticated:
        return False

    return (
        getattr(user, "role", None) == User.Role.ADMIN
        or user.is_staff
        or user.is_superuser
    )


def is_executive(user):
    """
    Determine whether the authenticated user is a
    KUCSA executive.
    """

    if not user or not user.is_authenticated:
        return False

    return bool(
        getattr(user, "is_executive", False)
    )


def can_manage_members(user):
    """
    Determine whether a user may manage member profiles.

    Administrators and KUCSA executives may manage
    member profile information.

    This permission does NOT grant authority to activate,
    reject, suspend, or otherwise control membership status.
    """

    return (
        is_admin(user)
        or is_executive(user)
    )


def can_manage_membership(user):
    """
    Determine whether a user may perform membership
    administration.

    Only administrators are allowed to perform these
    operations.
    """

    return is_admin(user)


def require_member_management(request):
    """
    Require administrator or executive privileges.
    """

    if not can_manage_members(request.user):

        messages.error(
            request,
            "You do not have permission to manage members.",
        )

        return False

    return True


def require_membership_management(request):
    """
    Require administrator privileges for membership
    administration.
    """

    if not can_manage_membership(request.user):

        messages.error(
            request,
            "Only administrators can manage membership status.",
        )

        return False

    return True


# =========================================================
# MEMBER PROFILE HELPER
# =========================================================


def get_or_create_member_profile(user):
    """
    Retrieve the Member profile belonging to a user.

    If the profile does not exist, create it through
    MemberService.

    Normal members remain PENDING until the required
    membership payment has been successfully processed
    and verified.

    Administrators are handled separately and may have
    automatically activated membership.
    """

    member = MemberService.get_member(user)

    if member is None:
        member = MemberService.create_member(user)

    # -----------------------------------------------------
    # ADMINISTRATOR MEMBERSHIP
    # -----------------------------------------------------

    if is_admin(user):

        needs_activation = (
            member.membership_status
            != Member.MembershipStatus.ACTIVE
            or not member.membership_number
            or not member.expiry_date
        )

        if needs_activation:

            member = (
                MemberService
                ._activate_administrator_membership(
                    member
                )
            )

        if not user.is_verified:

            user.is_verified = True

            user.save(
                update_fields=[
                    "is_verified",
                ]
            )

    return member


# =========================================================
# MEMBER LIST
# =========================================================


@login_required
def member_list(request):
    """
    Display KUCSA members.

    Supports:

        - Name search
        - Username search
        - Registration number search
        - Email search
        - Membership number search
        - Course search
        - Membership status filtering
        - Technical level filtering
    """

    members = (
        Member.objects
        .select_related("user")
        .all()
        .order_by(
            "user__first_name",
            "user__last_name",
        )
    )

    search_query = (
        request.GET.get("q", "")
        .strip()
    )

    status = (
        request.GET.get("status", "")
        .strip()
    )

    technical_level = (
        request.GET.get("technical_level", "")
        .strip()
    )

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    if search_query:

        members = members.filter(
            Q(
                user__first_name__icontains=search_query
            )
            | Q(
                user__last_name__icontains=search_query
            )
            | Q(
                user__username__icontains=search_query
            )
            | Q(
                user__registration_number__icontains=search_query
            )
            | Q(
                user__email__icontains=search_query
            )
            | Q(
                membership_number__icontains=search_query
            )
            | Q(
                course__icontains=search_query
            )
        ).distinct()

    # -----------------------------------------------------
    # MEMBERSHIP STATUS
    # -----------------------------------------------------

    valid_statuses = {
        value
        for value, label
        in Member.MembershipStatus.choices
    }

    if status and status in valid_statuses:

        members = members.filter(
            membership_status=status
        )

    # -----------------------------------------------------
    # TECHNICAL LEVEL
    # -----------------------------------------------------

    valid_levels = {
        value
        for value, label
        in Member.TechnicalLevel.choices
    }

    if (
        technical_level
        and technical_level in valid_levels
    ):

        members = members.filter(
            technical_level=technical_level
        )

    context = {
        "members": members,
        "search_query": search_query,
        "selected_status": status,
        "selected_technical_level": technical_level,

        "membership_statuses": (
            Member.MembershipStatus.choices
        ),

        "technical_levels": (
            Member.TechnicalLevel.choices
        ),

        "can_manage_members": (
            can_manage_members(request.user)
        ),

        "can_manage_membership": (
            can_manage_membership(request.user)
        ),

        "is_admin": (
            is_admin(request.user)
        ),
    }

    return render(
        request,
        "member_list.html",
        context,
    )


# =========================================================
# MEMBER DETAIL
# =========================================================


@login_required
def member_detail(request, pk):
    """
    Display a complete KUCSA member profile.
    """

    member = get_object_or_404(
        Member.objects.select_related("user"),
        pk=pk,
    )

    membership_information = (
        MemberService.get_membership_information(
            member
        )
    )

    context = {
        "member": member,

        "membership_information": (
            membership_information
        ),

        "can_manage_members": (
            can_manage_members(request.user)
        ),

        "can_manage_membership": (
            can_manage_membership(request.user)
        ),

        "is_admin": (
            is_admin(request.user)
        ),
    }

    return render(
        request,
        "member_detail.html",
        context,
    )


# =========================================================
# MY MEMBER PROFILE
# =========================================================


@login_required
def member_profile(request):
    """
    Display the currently authenticated user's
    KUCSA membership profile.
    """

    member = get_or_create_member_profile(
        request.user
    )

    membership_information = (
        MemberService.get_membership_information(
            member
        )
    )

    profile_complete = (
        MemberService.check_profile_completeness(
            member
        )
    )

    context = {
        "member": member,

        "membership_information": (
            membership_information
        ),

        "profile_complete": profile_complete,

        "is_admin": (
            is_admin(request.user)
        ),

        "is_executive": (
            is_executive(request.user)
        ),
    }

    return render(
        request,
        "member_profile.html",
        context,
    )


# =========================================================
# EDIT MY PROFILE
# =========================================================


@login_required
@transaction.atomic
def edit_member_profile(request):
    """
    Allow an authenticated member to update their personal
    and technical profile.

    TWO FORMS ARE USED:

        MemberUserForm
            Handles User information.

        MemberProfileForm
            Handles Member profile information.

    MEMBERSHIP-CONTROLLED INFORMATION IS NOT EXPOSED:

        - membership number
        - membership status
        - joined date
        - expiry date

    Membership activation and payment information remain
    controlled by the membership/payment workflow.
    """

    member = get_or_create_member_profile(
        request.user
    )

    if request.method == "POST":

        user_form = MemberUserForm(
            request.POST,
            request.FILES,
            instance=request.user,
        )

        profile_form = MemberProfileForm(
            request.POST,
            instance=member,
        )

        user_valid = user_form.is_valid()
        profile_valid = profile_form.is_valid()

        if user_valid and profile_valid:

            # -------------------------------------------------
            # Save User information
            # -------------------------------------------------

            user_form.save()

            # -------------------------------------------------
            # Save Member profile information
            # -------------------------------------------------

            profile_form.save()

            # -------------------------------------------------
            # Recalculate profile completeness
            # -------------------------------------------------

            profile_complete = (
                MemberService.check_profile_completeness(
                    member
                )
            )

            messages.success(
                request,
                (
                    "Your KUCSA profile has been "
                    "updated successfully."
                ),
            )

            return redirect(
                "members:profile"
            )

    else:

        user_form = MemberUserForm(
            instance=request.user,
        )

        profile_form = MemberProfileForm(
            instance=member,
        )

    # -----------------------------------------------------
    # IMPORTANT
    # -----------------------------------------------------
    #
    # The template must render BOTH forms:
    #
    #     user_form
    #     profile_form
    #
    # instead of looping over a non-existent "form".
    # -----------------------------------------------------

    context = {
        "member": member,

        "user_form": user_form,

        "profile_form": profile_form,

        "profile_complete": (
            MemberService.check_profile_completeness(
                member
            )
        ),

        "page_title": "Edit My Profile",

        "is_admin": (
            is_admin(request.user)
        ),

        "is_executive": (
            is_executive(request.user)
        ),
    }

    return render(
        request,
        "member_form.html",
        context,
    )


# =========================================================
# CREATE MEMBER
# =========================================================


@login_required
@transaction.atomic
def create_member(request):
    """
    Create a new KUCSA member account.

    Only administrators and executives may perform this
    operation.

    Creating a member does NOT activate membership.

    Newly created normal members remain PENDING until the
    membership payment has been successfully processed
    and verified.
    """

    if not require_member_management(request):

        return redirect(
            "members:list"
        )

    if request.method == "POST":

        form = MemberForm(
            request.POST
        )

        if form.is_valid():

            email = (
                form.cleaned_data["email"]
                .strip()
                .lower()
            )

            # -------------------------------------------------
            # EMAIL DUPLICATE CHECK
            # -------------------------------------------------

            if User.objects.filter(
                email__iexact=email
            ).exists():

                form.add_error(
                    "email",
                    "A user with this email address already exists.",
                )

            else:

                # -------------------------------------------------
                # GENERATE UNIQUE USERNAME
                # -------------------------------------------------

                username_base = (
                    email.split("@")[0]
                    .strip()
                    .lower()
                )

                if not username_base:

                    username_base = "kucsa_member"

                username = username_base
                counter = 1

                while User.objects.filter(
                    username=username
                ).exists():

                    username = (
                        f"{username_base}{counter}"
                    )

                    counter += 1

                # -------------------------------------------------
                # CREATE USER
                # -------------------------------------------------

                user = User.objects.create_user(
                    username=username,

                    email=email,

                    first_name=(
                        form.cleaned_data["first_name"]
                    ),

                    last_name=(
                        form.cleaned_data["last_name"]
                    ),

                    phone_number=(
                        form.cleaned_data["phone_number"]
                    ),

                    role=User.Role.STUDENT,
                )

                # -------------------------------------------------
                # REGISTRATION NUMBER
                # -------------------------------------------------
                #
                # This is NOT the KUCSA membership number.
                #
                # It is only a temporary platform identifier
                # when an actual university registration number
                # has not been supplied.
                # -------------------------------------------------

                generated_registration_number = (
                    f"KUCSA-REG-{user.pk:06d}"
                )

                user.registration_number = (
                    generated_registration_number
                )

                user.save(
                    update_fields=[
                        "registration_number",
                    ]
                )

                # -------------------------------------------------
                # CREATE MEMBER
                # -------------------------------------------------

                member = form.save(
                    commit=False
                )

                member.user = user

                # -------------------------------------------------
                # PAYMENT-FIRST MEMBERSHIP
                # -------------------------------------------------

                member.membership_status = (
                    Member.MembershipStatus.PENDING
                )

                member.membership_number = None
                member.joined_date = None
                member.expiry_date = None

                member.save()

                messages.success(
                    request,
                    (
                        "Member account created successfully. "
                        "The membership is pending payment."
                    ),
                )

                return redirect(
                    "members:detail",
                    pk=member.pk,
                )

    else:

        form = MemberForm()

    context = {
        "form": form,

        "page_title": "Create Member",

        "is_admin": (
            is_admin(request.user)
        ),

        "is_executive": (
            is_executive(request.user)
        ),
    }

    return render(
        request,
        "member_form.html",
        context,
    )


# =========================================================
# EDIT MEMBER
# =========================================================


@login_required
@transaction.atomic
def edit_member(request, pk):
    """
    Edit an existing KUCSA member.

    Administrators and executives may edit member
    profile information.

    IMPORTANT:

    Membership activation/payment workflow is separate.

    This view therefore preserves the existing membership
    status, membership number, joined date and expiry date
    rather than allowing ordinary profile editing to alter
    them accidentally.
    """

    if not require_member_management(request):

        return redirect(
            "members:detail",
            pk=pk,
        )

    member = get_object_or_404(
        Member.objects.select_related("user"),
        pk=pk,
    )

    # -----------------------------------------------------
    # Preserve membership-controlled fields
    # -----------------------------------------------------

    original_membership_status = (
        member.membership_status
    )

    original_membership_number = (
        member.membership_number
    )

    original_joined_date = (
        member.joined_date
    )

    original_expiry_date = (
        member.expiry_date
    )

    if request.method == "POST":

        form = MemberForm(
            request.POST,
            instance=member,
        )

        if form.is_valid():

            # -------------------------------------------------
            # Update User
            # -------------------------------------------------

            user = member.user

            user.first_name = (
                form.cleaned_data["first_name"]
            )

            user.last_name = (
                form.cleaned_data["last_name"]
            )

            user.email = (
                form.cleaned_data["email"]
            )

            user.phone_number = (
                form.cleaned_data["phone_number"]
            )

            user.save()

            # -------------------------------------------------
            # Update Member
            #
            # Only profile fields are updated here.
            # -------------------------------------------------

            member.bio = form.cleaned_data.get(
                "bio",
                member.bio,
            )

            member.course = form.cleaned_data.get(
                "course",
                member.course,
            )

            member.year_of_study = form.cleaned_data.get(
                "year_of_study",
                member.year_of_study,
            )

            member.technical_level = (
                form.cleaned_data.get(
                    "technical_level",
                    member.technical_level,
                )
            )

            member.technical_domains = (
                form.cleaned_data.get(
                    "technical_domains",
                    member.technical_domains,
                )
            )

            member.skills = (
                form.cleaned_data.get(
                    "skills",
                    member.skills,
                )
            )

            member.interests = (
                form.cleaned_data.get(
                    "interests",
                    member.interests,
                )
            )

            member.github_url = (
                form.cleaned_data.get(
                    "github_url",
                    member.github_url,
                )
            )

            member.linkedin_url = (
                form.cleaned_data.get(
                    "linkedin_url",
                    member.linkedin_url,
                )
            )

            member.portfolio_url = (
                form.cleaned_data.get(
                    "portfolio_url",
                    member.portfolio_url,
                )
            )

            # -------------------------------------------------
            # Restore membership-controlled information
            # -------------------------------------------------

            member.membership_status = (
                original_membership_status
            )

            member.membership_number = (
                original_membership_number
            )

            member.joined_date = (
                original_joined_date
            )

            member.expiry_date = (
                original_expiry_date
            )

            member.save()

            # -------------------------------------------------
            # Recalculate profile completeness
            # -------------------------------------------------

            MemberService.check_profile_completeness(
                member
            )

            messages.success(
                request,
                "Member profile updated successfully.",
            )

            return redirect(
                "members:detail",
                pk=member.pk,
            )

    else:

        form = MemberForm(
            instance=member,
        )

    context = {
        "form": form,

        "member": member,

        "page_title": "Edit Member",

        "is_admin": (
            is_admin(request.user)
        ),

        "is_executive": (
            is_executive(request.user)
        ),
    }

    return render(
        request,
        "member_form.html",
        context,
    )


# =========================================================
# TECHNICAL DOMAINS
# =========================================================


@login_required
def technical_domains(request):
    """
    Display KUCSA members according to their technical
    domains.
    """

    domain = (
        request.GET.get("domain", "")
        .strip()
    )

    members = list(
        Member.objects
        .select_related("user")
        .all()
    )

    if domain:

        members = [
            member
            for member in members
            if any(
                domain.casefold()
                == str(item).strip().casefold()
                for item in (
                    member.technical_domains
                    or []
                )
            )
        ]

    # -----------------------------------------------------
    # AVAILABLE DOMAINS
    # -----------------------------------------------------

    domains = set()

    all_members = (
        Member.objects
        .only("technical_domains")
    )

    for member in all_members:

        for item in (
            member.technical_domains
            or []
        ):

            item = str(item).strip()

            if item:
                domains.add(item)

    context = {
        "members": members,

        "domains": sorted(
            domains,
            key=str.casefold,
        ),

        "selected_domain": domain,
    }

    return render(
        request,
        "technical_domains.html",
        context,
    )


# =========================================================
# MEMBERSHIP STATUS
# =========================================================


@login_required
def membership_status(request):
    """
    Display the authenticated user's current membership
    status.

    This view does not activate or modify membership.
    """

    member = get_or_create_member_profile(
        request.user
    )

    membership_information = (
        MemberService.get_membership_information(
            member
        )
    )

    context = {
        "member": member,

        "membership_information": (
            membership_information
        ),

        "membership_statuses": (
            Member.MembershipStatus.choices
        ),

        "is_admin": (
            is_admin(request.user)
        ),
    }

    return render(
        request,
        "membership_status.html",
        context,
    )


# =========================================================
# UPDATE MEMBERSHIP STATUS
# =========================================================


@login_required
@transaction.atomic
def update_membership_status(request, pk):
    """
    Administrative membership-status management.

    NORMAL MEMBERS
    --------------

    ACTIVE status cannot be manually assigned.

    The intended workflow is:

        Payment
            ↓
        Payment verification
            ↓
        MemberService.activate_member()
            ↓
        ACTIVE membership

    ADMINISTRATORS
    --------------

    Administrator membership is handled separately and
    may be activated automatically.

    Administrators may otherwise manage:

        - PENDING
        - SUSPENDED
        - REJECTED
        - EXPIRED
    """

    if not require_membership_management(request):

        return redirect(
            "members:detail",
            pk=pk,
        )

    member = get_object_or_404(
        Member.objects.select_related("user"),
        pk=pk,
    )

    if request.method != "POST":

        messages.error(
            request,
            "Membership status can only be changed using a POST request.",
        )

        return redirect(
            "members:detail",
            pk=member.pk,
        )

    new_status = (
        request.POST.get(
            "membership_status",
            "",
        )
        .strip()
    )

    valid_statuses = {
        value
        for value, label
        in Member.MembershipStatus.choices
    }

    if new_status not in valid_statuses:

        messages.error(
            request,
            "Invalid membership status.",
        )

        return redirect(
            "members:detail",
            pk=member.pk,
        )

    # -----------------------------------------------------
    # ADMINISTRATOR PROTECTION
    # -----------------------------------------------------

    if (
        is_admin(member.user)
        and new_status
        != Member.MembershipStatus.ACTIVE
    ):

        messages.warning(
            request,
            (
                "Administrator membership cannot "
                "be set to an inactive status."
            ),
        )

        return redirect(
            "members:detail",
            pk=member.pk,
        )

    # -----------------------------------------------------
    # ACTIVE
    # -----------------------------------------------------

    if (
        new_status
        == Member.MembershipStatus.ACTIVE
    ):

        if is_admin(member.user):

            member = (
                MemberService
                ._activate_administrator_membership(
                    member
                )
            )

            member.user.is_verified = True

            member.user.save(
                update_fields=[
                    "is_verified",
                ]
            )

            messages.success(
                request,
                (
                    f"{member.full_name}'s administrator "
                    "membership is active."
                ),
            )

        else:

            messages.warning(
                request,
                (
                    "This member cannot be activated manually. "
                    "The required membership payment must be "
                    "successfully verified through the payment "
                    "workflow."
                ),
            )

        return redirect(
            "members:detail",
            pk=member.pk,
        )

    # -----------------------------------------------------
    # SUSPENDED
    # -----------------------------------------------------

    if (
        new_status
        == Member.MembershipStatus.SUSPENDED
    ):

        MemberService.suspend_member(
            member
        )

        member.user.is_verified = False

        member.user.save(
            update_fields=[
                "is_verified",
            ]
        )

        messages.success(
            request,
            (
                f"{member.full_name}'s membership "
                "has been suspended."
            ),
        )

    # -----------------------------------------------------
    # REJECTED
    # -----------------------------------------------------

    elif (
        new_status
        == Member.MembershipStatus.REJECTED
    ):

        MemberService.reject_member(
            member
        )

        member.user.is_verified = False

        member.user.save(
            update_fields=[
                "is_verified",
            ]
        )

        messages.success(
            request,
            (
                f"{member.full_name}'s membership "
                "has been rejected."
            ),
        )

    # -----------------------------------------------------
    # PENDING
    # -----------------------------------------------------

    elif (
        new_status
        == Member.MembershipStatus.PENDING
    ):

        member.membership_status = (
            Member.MembershipStatus.PENDING
        )

        member.save(
            update_fields=[
                "membership_status",
                "updated_at",
            ]
        )

        member.user.is_verified = False

        member.user.save(
            update_fields=[
                "is_verified",
            ]
        )

        messages.success(
            request,
            (
                f"{member.full_name}'s membership "
                "has been returned to pending."
            ),
        )

    # -----------------------------------------------------
    # EXPIRED
    # -----------------------------------------------------

    elif (
        new_status
        == Member.MembershipStatus.EXPIRED
    ):

        member.membership_status = (
            Member.MembershipStatus.EXPIRED
        )

        member.save(
            update_fields=[
                "membership_status",
                "updated_at",
            ]
        )

        member.user.is_verified = False

        member.user.save(
            update_fields=[
                "is_verified",
            ]
        )

        messages.success(
            request,
            (
                f"{member.full_name}'s membership "
                "has been marked as expired."
            ),
        )

    return redirect(
        "members:detail",
        pk=member.pk,
    )


# =========================================================
# APPROVE MEMBER
# =========================================================


@login_required
@transaction.atomic
def approve_member(request, pk):
    """
    Administrative approval endpoint.

    Normal members cannot be activated manually.

    Their membership must pass through the payment
    verification workflow.

    Administrators are handled separately.
    """

    if not require_membership_management(request):

        return redirect(
            "members:detail",
            pk=pk,
        )

    member = get_object_or_404(
        Member.objects.select_related("user"),
        pk=pk,
    )

    if request.method != "POST":

        return redirect(
            "members:detail",
            pk=member.pk,
        )

    if is_admin(member.user):

        member = (
            MemberService
            ._activate_administrator_membership(
                member
            )
        )

        member.user.is_verified = True

        member.user.save(
            update_fields=[
                "is_verified",
            ]
        )

        messages.success(
            request,
            (
                f"{member.full_name}'s administrator "
                "membership has been activated."
            ),
        )

    else:

        messages.warning(
            request,
            (
                "Membership cannot be approved manually. "
                "The member must complete the required "
                "payment and the payment must be verified."
            ),
        )

    return redirect(
        "members:detail",
        pk=member.pk,
    )


# =========================================================
# REJECT MEMBER
# =========================================================


@login_required
@transaction.atomic
def reject_member(request, pk):
    """
    Reject a KUCSA membership application.

    Only administrators can reject memberships.
    """

    if not require_membership_management(request):

        return redirect(
            "members:detail",
            pk=pk,
        )

    member = get_object_or_404(
        Member.objects.select_related("user"),
        pk=pk,
    )

    if request.method != "POST":

        return redirect(
            "members:detail",
            pk=member.pk,
        )

    if is_admin(member.user):

        messages.warning(
            request,
            "Administrator membership cannot be rejected.",
        )

        return redirect(
            "members:detail",
            pk=member.pk,
        )

    MemberService.reject_member(
        member
    )

    member.user.is_verified = False

    member.user.save(
        update_fields=[
            "is_verified",
        ]
    )

    messages.success(
        request,
        (
            f"{member.full_name}'s membership "
            "has been rejected."
        ),
    )

    return redirect(
        "members:detail",
        pk=member.pk,
    )


# =========================================================
# SUSPEND MEMBER
# =========================================================


@login_required
@transaction.atomic
def suspend_member(request, pk):
    """
    Suspend an active KUCSA membership.

    Only administrators can suspend memberships.
    """

    if not require_membership_management(request):

        return redirect(
            "members:detail",
            pk=pk,
        )

    member = get_object_or_404(
        Member.objects.select_related("user"),
        pk=pk,
    )

    if request.method != "POST":

        return redirect(
            "members:detail",
            pk=member.pk,
        )

    if is_admin(member.user):

        messages.warning(
            request,
            "Administrator membership cannot be suspended.",
        )

        return redirect(
            "members:detail",
            pk=member.pk,
        )

    MemberService.suspend_member(
        member
    )

    member.user.is_verified = False

    member.user.save(
        update_fields=[
            "is_verified",
        ]
    )

    messages.success(
        request,
        (
            f"{member.full_name}'s membership "
            "has been suspended."
        ),
    )

    return redirect(
        "members:detail",
        pk=member.pk,
    )


# =========================================================
# DELETE MEMBER
# =========================================================


@login_required
@transaction.atomic
def delete_member(request, pk):
    """
    Delete a member and associated User account.

    Only administrators may perform this operation.

    Financial/payment records should be protected according
    to their ForeignKey on_delete configuration.
    """

    if not is_admin(request.user):

        messages.error(
            request,
            "Only administrators can delete members.",
        )

        return redirect(
            "members:detail",
            pk=pk,
        )

    member = get_object_or_404(
        Member.objects.select_related("user"),
        pk=pk,
    )

    # -----------------------------------------------------
    # PREVENT SELF-DELETION
    # -----------------------------------------------------

    if member.user == request.user:

        messages.error(
            request,
            "You cannot delete your own administrator account.",
        )

        return redirect(
            "members:detail",
            pk=member.pk,
        )

    # -----------------------------------------------------
    # DELETE
    # -----------------------------------------------------

    if request.method == "POST":

        user = member.user

        member.delete()

        user.delete()

        messages.success(
            request,
            "Member has been deleted successfully.",
        )

        return redirect(
            "members:list"
        )

    context = {
        "member": member,
        "delete_confirmation": True,
        "is_admin": True,
    }

    return render(
        request,
        "member_detail.html",
        context,
    )