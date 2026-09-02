# executives/views.py

"""
KUCSA Executive Views
=====================

HTTP views for the KUCSA executive management module.

Available templates:
    - executive_dashboard.html
    - executive_list.html
    - executive_profile.html
    - assign_roles.html

Business logic belongs in:
    - executives.services.ExecutiveService
    - executives.models.Executive

The User model remains the source of truth for:
    - Authentication
    - User roles
    - Verification
    - Account status

The Executive model remains responsible for:
    - Executive profile information
    - Committee
    - Responsibilities
    - Vision
    - Biography
    - Term information
    - Executive activation status
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from accounts.models import User

from .forms import (
    AssignExecutiveRoleForm,
    ExecutiveProfileForm,
    ExecutiveSearchForm,
)
from .models import Executive
from .services import ExecutiveService


# =========================================================
# ACCESS CONTROL HELPERS
# =========================================================


def is_admin(user):
    """
    Return True when the authenticated user is an administrator.
    """

    return bool(
        user
        and user.is_authenticated
        and getattr(user, "role", None)
        == User.Role.ADMIN
    )


def is_executive_or_admin(user):
    """
    Return True when the authenticated user is either:

        - A KUCSA executive
        - An administrator
    """

    if not user or not user.is_authenticated:
        return False

    return bool(
        getattr(user, "is_executive", False)
        or is_admin(user)
    )


def require_executive_or_admin(user):
    """
    Require executive or administrator privileges.
    """

    if not is_executive_or_admin(user):
        raise PermissionDenied(
            "You do not have permission to access "
            "the executive section."
        )


def require_admin(user):
    """
    Require administrator privileges.
    """

    if not is_admin(user):
        raise PermissionDenied(
            "Administrator privileges are required."
        )


# =========================================================
# EXECUTIVE DASHBOARD
# =========================================================


@login_required
def executive_dashboard(request):
    """
    Display the KUCSA executive management dashboard.

    Accessible to:
        - Executives
        - Administrators

    Provides:
        - Executive statistics
        - Current executive board
        - Current logged-in executive
        - Chairperson
        - Vice Chairperson
    """

    require_executive_or_admin(request.user)

    statistics = (
        ExecutiveService.get_executive_statistics()
    )

    executive_board = (
        ExecutiveService.get_executive_board()
    )

    current_executive = (
        ExecutiveService.get_executive(
            request.user
        )
    )

    chairperson = (
        ExecutiveService.get_chairperson()
    )

    vice_chairperson = (
        ExecutiveService.get_vice_chairperson()
    )

    context = {
        "statistics": statistics,
        "executive_board": executive_board,
        "current_executive": current_executive,
        "chairperson": chairperson,
        "vice_chairperson": vice_chairperson,
        "is_admin": is_admin(request.user),
    }

    return render(
        request,
        "executive_dashboard.html",
        context,
    )


# =========================================================
# EXECUTIVE LIST
# =========================================================


@login_required
def executive_list(request):
    """
    Display KUCSA executives.

    Accessible to:
        - Executives
        - Administrators

    Supports:
        - Search
        - Role filtering
        - Committee filtering
        - Active/inactive filtering
        - Verification filtering

    All filtering is delegated to ExecutiveService.
    """

    require_executive_or_admin(request.user)

    form = ExecutiveSearchForm(
        request.GET or None
    )

    executives = ExecutiveService.get_all_executives()

    if form.is_valid():

        query = form.cleaned_data.get(
            "query"
        )

        role = form.cleaned_data.get(
            "role"
        )

        committee = form.cleaned_data.get(
            "committee"
        )

        is_active = form.cleaned_data.get(
            "is_active"
        )

        is_verified = form.cleaned_data.get(
            "is_verified"
        )

        # -------------------------------------------------
        # CONVERT FORM VALUES
        # -------------------------------------------------

        if is_active == "true":
            is_active = True

        elif is_active == "false":
            is_active = False

        else:
            is_active = None

        if is_verified == "true":
            is_verified = True

        elif is_verified == "false":
            is_verified = False

        else:
            is_verified = None

        executives = (
            ExecutiveService.filter_executives(
                query=query,
                role=role,
                committee=committee,
                is_active=is_active,
                is_verified=is_verified,
            )
        )

    context = {
        "executives": executives,
        "form": form,
        "is_admin": is_admin(request.user),
        "current_executive": (
            ExecutiveService.get_executive(
                request.user
            )
        ),
    }

    return render(
        request,
        "executive_list.html",
        context,
    )


# =========================================================
# EXECUTIVE PROFILE
# =========================================================


@login_required
def executive_profile(request, pk=None):
    """
    Display an executive profile.

    When pk is omitted:
        Display the authenticated user's executive profile.

    When pk is supplied:
        Display the selected executive profile.

    The same template also supports:
        - Profile display
        - Profile editing
        - Activation confirmation
        - Deactivation confirmation
        - Role removal confirmation
    """

    require_executive_or_admin(request.user)

    # -----------------------------------------------------
    # CURRENT USER PROFILE
    # -----------------------------------------------------

    if pk is None:

        executive = (
            ExecutiveService.get_executive(
                request.user
            )
        )

        if executive is None:

            # An administrator may not necessarily have
            # an Executive profile.
            if is_admin(request.user):
                messages.info(
                    request,
                    (
                        "You are viewing the executive "
                        "section as an administrator. "
                        "You do not have an executive "
                        "profile."
                    ),
                )

                return redirect(
                    "executives:list"
                )

            messages.warning(
                request,
                (
                    "Your executive profile has not "
                    "been created yet."
                ),
            )

            return redirect(
                "executives:dashboard"
            )

    # -----------------------------------------------------
    # SELECTED EXECUTIVE PROFILE
    # -----------------------------------------------------

    else:

        executive = get_object_or_404(
            Executive.objects.select_related(
                "user"
            ),
            pk=pk,
        )

    # -----------------------------------------------------
    # PROFILE FORM
    # -----------------------------------------------------

    form = ExecutiveProfileForm(
        instance=executive
    )

    context = {
        "executive": executive,
        "form": form,
        "is_admin": is_admin(request.user),
        "is_owner": (
            executive.user_id
            == request.user.id
        ),
        "can_edit": (
            is_admin(request.user)
            or executive.user_id
            == request.user.id
        ),
    }

    return render(
        request,
        "executive_profile.html",
        context,
    )


# =========================================================
# EDIT EXECUTIVE PROFILE
# =========================================================


@login_required
def edit_executive_profile(request):
    """
    Update the authenticated executive's profile.

    Uses executive_profile.html for the form.

    No separate edit template is required.

    Administrators can also update their own executive
    profile if they have one.
    """

    require_executive_or_admin(request.user)

    executive = (
        ExecutiveService.get_executive(
            request.user
        )
    )

    # -----------------------------------------------------
    # ENSURE PROFILE EXISTS
    # -----------------------------------------------------

    if executive is None:

        if not ExecutiveService.is_executive(
            request.user
        ):
            messages.error(
                request,
                (
                    "You do not currently hold an "
                    "official KUCSA executive role."
                ),
            )

            return redirect(
                "executives:dashboard"
            )

        executive = (
            ExecutiveService.ensure_executive_profile(
                request.user
            )
        )

    # -----------------------------------------------------
    # POST
    # -----------------------------------------------------

    if request.method == "POST":

        form = ExecutiveProfileForm(
            request.POST,
            instance=executive,
        )

        if form.is_valid():

            ExecutiveService.update_executive(
                executive,
                **form.cleaned_data,
            )

            messages.success(
                request,
                (
                    "Your executive profile has been "
                    "updated successfully."
                ),
            )

            return redirect(
                "executives:profile"
            )

    # -----------------------------------------------------
    # GET
    # -----------------------------------------------------

    else:

        form = ExecutiveProfileForm(
            instance=executive
        )

    # -----------------------------------------------------
    # SAME PROFILE TEMPLATE
    # -----------------------------------------------------

    return render(
        request,
        "executive_profile.html",
        {
            "executive": executive,
            "form": form,
            "editing": True,
            "is_admin": is_admin(request.user),
            "is_owner": True,
            "can_edit": True,
        },
    )


# =========================================================
# ASSIGN EXECUTIVE ROLE
# =========================================================


@login_required
def assign_role(request):
    """
    Assign an official KUCSA executive role to an
    existing user.

    Only administrators can assign executive roles.

    Uses:
        assign_roles.html
    """

    require_admin(request.user)

    if request.method == "POST":

        form = AssignExecutiveRoleForm(
            request.POST
        )

        if form.is_valid():

            user = form.cleaned_data["user"]
            role = form.cleaned_data["role"]

            try:

                executive = (
                    ExecutiveService.assign_role(
                        user=user,
                        role=role,
                    )
                )

            except ValueError as error:

                messages.error(
                    request,
                    str(error),
                )

            else:

                full_name = (
                    user.get_full_name()
                    or user.username
                )

                messages.success(
                    request,
                    (
                        f"{full_name} has been assigned "
                        f"the role of "
                        f"{user.get_role_display()}."
                    ),
                )

                return redirect(
                    "executives:profile_detail",
                    pk=executive.pk,
                )

    else:

        form = AssignExecutiveRoleForm()

    context = {
        "form": form,
        "executive_roles": (
            ExecutiveService.EXECUTIVE_ROLES
        ),
    }

    return render(
        request,
        "assign_roles.html",
        context,
    )


# =========================================================
# REMOVE EXECUTIVE ROLE
# =========================================================


@login_required
def remove_role(request, pk):
    """
    Remove an executive role from a user.

    Only administrators can perform this action.

    The action itself is POST-only.

    GET requests use executive_profile.html as the
    confirmation interface.
    """

    require_admin(request.user)

    executive = get_object_or_404(
        Executive.objects.select_related(
            "user"
        ),
        pk=pk,
    )

    user = executive.user

    # -----------------------------------------------------
    # CONFIRMATION PAGE
    # -----------------------------------------------------

    if request.method != "POST":

        return render(
            request,
            "executive_profile.html",
            {
                "executive": executive,
                "confirm_remove_role": True,
                "is_admin": True,
                "is_owner": (
                    executive.user_id
                    == request.user.id
                ),
                "can_edit": True,
            },
        )

    # -----------------------------------------------------
    # REMOVE ROLE
    # -----------------------------------------------------

    ExecutiveService.remove_executive_role(
        user
    )

    full_name = (
        user.get_full_name()
        or user.username
    )

    messages.success(
        request,
        (
            f"{full_name} is no longer a "
            "KUCSA executive."
        ),
    )

    return redirect(
        "executives:list"
    )


# =========================================================
# ACTIVATE EXECUTIVE
# =========================================================


@login_required
def activate_executive(request, pk):
    """
    Activate an executive profile.

    Only administrators can perform this action.

    GET:
        Display confirmation using executive_profile.html.

    POST:
        Activate the executive.
    """

    require_admin(request.user)

    executive = get_object_or_404(
        Executive.objects.select_related(
            "user"
        ),
        pk=pk,
    )

    # -----------------------------------------------------
    # CONFIRMATION PAGE
    # -----------------------------------------------------

    if request.method != "POST":

        return render(
            request,
            "executive_profile.html",
            {
                "executive": executive,
                "confirm_activate": True,
                "is_admin": True,
                "is_owner": (
                    executive.user_id
                    == request.user.id
                ),
                "can_edit": True,
            },
        )

    # -----------------------------------------------------
    # ACTIVATE
    # -----------------------------------------------------

    try:

        ExecutiveService.activate_executive(
            executive
        )

    except ValueError as error:

        messages.error(
            request,
            str(error),
        )

        return redirect(
            "executives:profile_detail",
            pk=executive.pk,
        )

    messages.success(
        request,
        (
            f"{executive.full_name} has been "
            "activated successfully."
        ),
    )

    return redirect(
        "executives:profile_detail",
        pk=executive.pk,
    )


# =========================================================
# DEACTIVATE EXECUTIVE
# =========================================================


@login_required
def deactivate_executive(request, pk):
    """
    Deactivate an executive profile.

    Only administrators can perform this action.

    GET:
        Display confirmation using executive_profile.html.

    POST:
        Deactivate the executive.
    """

    require_admin(request.user)

    executive = get_object_or_404(
        Executive.objects.select_related(
            "user"
        ),
        pk=pk,
    )

    # -----------------------------------------------------
    # CONFIRMATION PAGE
    # -----------------------------------------------------

    if request.method != "POST":

        return render(
            request,
            "executive_profile.html",
            {
                "executive": executive,
                "confirm_deactivate": True,
                "is_admin": True,
                "is_owner": (
                    executive.user_id
                    == request.user.id
                ),
                "can_edit": True,
            },
        )

    # -----------------------------------------------------
    # DEACTIVATE
    # -----------------------------------------------------

    try:

        ExecutiveService.deactivate_executive(
            executive
        )

    except ValueError as error:

        messages.error(
            request,
            str(error),
        )

        return redirect(
            "executives:profile_detail",
            pk=executive.pk,
        )

    messages.success(
        request,
        (
            f"{executive.full_name} has been "
            "deactivated successfully."
        ),
    )

    return redirect(
        "executives:profile_detail",
        pk=executive.pk,
    )


# =========================================================
# EXECUTIVE SEARCH
# =========================================================


@login_required
def executive_search(request):
    """
    Search and filter KUCSA executives.

    Uses executive_list.html for displaying results.

    This is intentionally kept as a separate endpoint so
    existing URLs can continue to work.
    """

    require_executive_or_admin(request.user)

    form = ExecutiveSearchForm(
        request.GET or None
    )

    executives = ExecutiveService.get_all_executives()

    if form.is_valid():

        query = form.cleaned_data.get(
            "query"
        )

        role = form.cleaned_data.get(
            "role"
        )

        committee = form.cleaned_data.get(
            "committee"
        )

        is_active = form.cleaned_data.get(
            "is_active"
        )

        is_verified = form.cleaned_data.get(
            "is_verified"
        )

        # -------------------------------------------------
        # CONVERT STATUS VALUES
        # -------------------------------------------------

        if is_active == "true":
            is_active = True

        elif is_active == "false":
            is_active = False

        else:
            is_active = None

        if is_verified == "true":
            is_verified = True

        elif is_verified == "false":
            is_verified = False

        else:
            is_verified = None

        executives = (
            ExecutiveService.filter_executives(
                query=query,
                role=role,
                committee=committee,
                is_active=is_active,
                is_verified=is_verified,
            )
        )

    return render(
        request,
        "executive_list.html",
        {
            "executives": executives,
            "form": form,
            "is_admin": is_admin(request.user),
            "current_executive": (
                ExecutiveService.get_executive(
                    request.user
                )
            ),
        },
    )


# =========================================================
# CURRENT EXECUTIVE BOARD
# =========================================================


@login_required
def executive_board(request):
    """
    Display the current active KUCSA executive board.

    Uses executive_list.html.

    Accessible to:
        - Executives
        - Administrators
    """

    require_executive_or_admin(request.user)

    executives = (
        ExecutiveService.get_executive_board()
    )

    chairperson = (
        ExecutiveService.get_chairperson()
    )

    vice_chairperson = (
        ExecutiveService.get_vice_chairperson()
    )

    return render(
        request,
        "executive_list.html",
        {
            "executives": executives,
            "chairperson": chairperson,
            "vice_chairperson": vice_chairperson,
            "is_admin": is_admin(request.user),
            "current_executive": (
                ExecutiveService.get_executive(
                    request.user
                )
            ),
        },
    )