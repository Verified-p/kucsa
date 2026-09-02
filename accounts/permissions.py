
# accounts/permissions.py

"""
KUCSA Account Permissions
=========================

Centralized role-based access control for the KUCSA platform.

Architecture
------------

    User
      │
      ├── STUDENT
      │
      ├── EXECUTIVE ROLES
      │      ├── CHAIRPERSON
      │      ├── VICE CHAIRPERSON
      │      ├── SECRETARY
      │      ├── SECRETARY GENERAL
      │      ├── TREASURER
      │      ├── ORGANIZING SECRETARY
      │      └── PUBLICITY SECRETARY
      │
      └── ADMIN


Role-Based Access Control
-------------------------

KUCSA organizational roles are the source of truth for
feature authorization.

Finance access, for example, follows this flow:

    Student
       ↓
    Membership
       ↓
    Administrator assigns TREASURER role
       ↓
    Treasurer
       ↓
    Finance Management Access

Permissions are NOT inferred from:

- Membership status
- Payment status
- is_staff
- is_superuser
- is_verified
- Being an executive without the required role

The TREASURER role must be explicitly assigned.

Administrators receive protected administrative access
through the ADMIN organizational role.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import User


# =============================================================================
# ROLE GROUPS
# =============================================================================

EXECUTIVE_ROLES = (
    User.Role.CHAIRPERSON,
    User.Role.VICE_CHAIRPERSON,
    User.Role.SECRETARY,
    User.Role.SECRETARY_GENERAL,
    User.Role.TREASURER,
    User.Role.ORGANIZING_SECRETARY,
    User.Role.PUBLICITY_SECRETARY,
)

ADMIN_ROLES = (
    User.Role.ADMIN,
)

EXECUTIVE_AND_ADMIN_ROLES = (
    *EXECUTIVE_ROLES,
    *ADMIN_ROLES,
)

FINANCE_MANAGER_ROLES = (
    User.Role.TREASURER,
    User.Role.ADMIN,
)


# =============================================================================
# CORE ROLE DECORATOR
# =============================================================================

def role_required(allowed_roles):
    """
    Restrict access to users whose assigned KUCSA role
    matches one of the supplied roles.

    Parameters
    ----------
    allowed_roles:
        Iterable containing User.Role values.

    Behavior
    --------
    - Requires authentication.
    - Checks the user's explicit organizational role.
    - Allows access when the role matches.
    - Redirects unauthorized users to the dashboard.

    Notes
    -----
    This decorator does not infer authorization from:

    - is_staff
    - is_superuser
    - is_verified
    - membership status
    - payment status
    - executive status
    """

    allowed_roles = tuple(allowed_roles)

    def decorator(view_func):

        @login_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.role in allowed_roles:
                return view_func(
                    request,
                    *args,
                    **kwargs,
                )

            messages.error(
                request,
                "You do not have permission to access this page.",
            )

            return redirect("dashboard")

        return wrapper

    return decorator


# =============================================================================
# STUDENT
# =============================================================================

def student_required(view_func):
    """
    Allow access to ordinary KUCSA students only.

    Executives and administrators are not included.
    """
    return role_required(
        (
            User.Role.STUDENT,
        )
    )(view_func)


# =============================================================================
# EXECUTIVE
# =============================================================================

def executive_required(view_func):
    """
    Allow access to all officially assigned KUCSA
    executive roles and administrators.

    Includes the Treasurer because Treasurer is an
    official KUCSA executive position.

    IMPORTANT
    ---------
    Being an executive does not automatically grant
    Finance management access.

    Finance-specific functionality should use
    finance_manager_required().
    """
    return role_required(
        EXECUTIVE_AND_ADMIN_ROLES
    )(view_func)


# =============================================================================
# ADMIN
# =============================================================================

def admin_required(view_func):
    """
    Allow access to KUCSA administrators only.

    The ADMIN role must be explicitly assigned.
    """
    return role_required(
        ADMIN_ROLES
    )(view_func)


# =============================================================================
# CHAIRPERSON
# =============================================================================

def chairperson_required(view_func):
    """
    Allow access to the Chairperson only.
    """
    return role_required(
        (
            User.Role.CHAIRPERSON,
        )
    )(view_func)


# =============================================================================
# VICE CHAIRPERSON
# =============================================================================

def vice_chairperson_required(view_func):
    """
    Allow access to the Vice Chairperson only.
    """
    return role_required(
        (
            User.Role.VICE_CHAIRPERSON,
        )
    )(view_func)


# =============================================================================
# SECRETARY
# =============================================================================

def secretary_required(view_func):
    """
    Allow access to the Secretary only.
    """
    return role_required(
        (
            User.Role.SECRETARY,
        )
    )(view_func)


# =============================================================================
# SECRETARY GENERAL
# =============================================================================

def secretary_general_required(view_func):
    """
    Allow access to the Secretary General only.
    """
    return role_required(
        (
            User.Role.SECRETARY_GENERAL,
        )
    )(view_func)


# =============================================================================
# TREASURER
# =============================================================================

def treasurer_required(view_func):
    """
    Allow access to the officially assigned Treasurer only.

    Finance authority is based strictly on the explicit
    TREASURER organizational role.

    The following do NOT make a user a Treasurer:

    - Being a student
    - Being a paid member
    - Being another executive
    - Being staff
    - Being a superuser
    - Being verified

    The administrator must explicitly assign:

        User.Role.TREASURER
    """
    return role_required(
        (
            User.Role.TREASURER,
        )
    )(view_func)


# =============================================================================
# FINANCE MANAGER
# =============================================================================

def finance_manager_required(view_func):
    """
    Allow access to users authorized to manage KUCSA finances.

    Current Finance management roles:

    - TREASURER
    - ADMIN

    Treasurer
    ---------
    Must have the explicitly assigned TREASURER role.

    Admin
    -----
    Administrators retain Finance access for oversight,
    administration, and financial control.

    Typical Finance management areas include:

    - Financial dashboard
    - Income
    - Expenses
    - Transactions
    - Reconciliation
    - Financial reports
    - Financial audit records
    """
    return role_required(
        FINANCE_MANAGER_ROLES
    )(view_func)


# =============================================================================
# ORGANIZING SECRETARY
# =============================================================================

def organizing_secretary_required(view_func):
    """
    Allow access to the Organizing Secretary only.
    """
    return role_required(
        (
            User.Role.ORGANIZING_SECRETARY,
        )
    )(view_func)


# =============================================================================
# PUBLICITY SECRETARY
# =============================================================================

def publicity_secretary_required(view_func):
    """
    Allow access to the Publicity Secretary only.
    """
    return role_required(
        (
            User.Role.PUBLICITY_SECRETARY,
        )
    )(view_func)
