
# finance/permissions.py

"""
KUCSA Finance Permissions
=========================

Centralized permission system for the KUCSA Finance application.

Finance authority is based primarily on:

    User.role

Main finance roles:

    ADMIN
    TREASURER
    EXECUTIVE

Role access:

    ADMIN
        Full finance access.

    TREASURER
        Full finance management access.

    EXECUTIVE
        Read-only finance access.

    MEMBER / STUDENT
        No finance access.

Architecture:

    VIEW
      ↓
    PERMISSION
      ↓
    SERVICE
      ↓
    MODEL

IMPORTANT
---------

Permission functions return True/False.

The service layer can use:

    require_permission(user, permission_function)

which raises PermissionDenied when access is not allowed.
"""


from django.core.exceptions import PermissionDenied


# =============================================================================
# BASIC AUTHENTICATION
# =============================================================================

def is_authenticated(user):
    """
    Return True if the supplied user is authenticated.
    """

    return bool(
        user
        and getattr(user, "is_authenticated", False)
    )


# =============================================================================
# GENERIC PERMISSION ENFORCEMENT
# =============================================================================

def require_permission(user, permission):
    """
    Enforce a permission function.

    Parameters
    ----------
    user:
        The current authenticated user.

    permission:
        A permission function such as:

            can_manage_finance
            can_manage_expenses
            can_view_audit_logs

    Returns
    -------
    True
        When permission is granted.

    Raises
    ------
    PermissionDenied
        When permission is not granted.

    Example
    -------

        require_permission(
            user,
            can_manage_expenses,
        )
    """

    if not callable(permission):
        raise ValueError(
            "The supplied permission must be callable."
        )

    if not permission(user):
        raise PermissionDenied(
            "You do not have permission to perform "
            "this finance action."
        )

    return True


# =============================================================================
# ROLE HELPERS
# =============================================================================

def _get_role(user):
    """
    Safely return the user's role.
    """

    if not is_authenticated(user):
        return None

    return getattr(
        user,
        "role",
        None,
    )


def _has_role(user, role_name):
    """
    Check whether the user's role matches a role defined
    in User.Role.

    This is intentionally implemented without directly
    importing the User model, preventing unnecessary
    circular dependencies.
    """

    if not is_authenticated(user):
        return False

    role = _get_role(user)

    role_class = getattr(
        user.__class__,
        "Role",
        None,
    )

    if role_class is None:
        return False

    role_value = getattr(
        role_class,
        role_name,
        None,
    )

    return (
        role_value is not None
        and role == role_value
    )


# =============================================================================
# MAIN ROLES
# =============================================================================

def is_admin(user):
    """
    Check whether the user is an administrator.

    Superusers are automatically treated as administrators.
    """

    if not is_authenticated(user):
        return False

    if getattr(
        user,
        "is_superuser",
        False,
    ):
        return True

    return _has_role(
        user,
        "ADMIN",
    )


def is_treasurer(user):
    """
    Check whether the user is the Treasurer.
    """

    return _has_role(
        user,
        "TREASURER",
    )


def is_executive(user):
    """
    Check whether the user is an Executive.
    """

    return _has_role(
        user,
        "EXECUTIVE",
    )


# =============================================================================
# FINANCE MANAGEMENT
# =============================================================================

def can_manage_finance(user):
    """
    Full finance management access.

    Allowed:

        ADMIN
        TREASURER
    """

    return (
        is_admin(user)
        or is_treasurer(user)
    )


# =============================================================================
# FINANCE DASHBOARD
# =============================================================================

def can_access_finance_dashboard(user):
    """
    Determine whether a user can access the finance dashboard.

    Allowed:

        ADMIN
        TREASURER
        EXECUTIVE

    Executives receive read-only access.
    """

    return (
        is_admin(user)
        or is_treasurer(user)
        or is_executive(user)
    )


# =============================================================================
# FINANCIAL TRANSACTIONS
# =============================================================================

def can_manage_transactions(user):
    """
    Create, edit, post, void, or otherwise manage
    financial transactions.

    Allowed:

        ADMIN
        TREASURER
    """

    return can_manage_finance(user)


def can_view_financial_transactions(user):
    """
    View financial transactions.

    Allowed:

        ADMIN
        TREASURER
        EXECUTIVE
    """

    return (
        is_admin(user)
        or is_treasurer(user)
        or is_executive(user)
    )


def can_edit_transaction(
    user,
    transaction=None,
):
    """
    Determine whether a transaction can be edited.

    Only finance managers may edit transactions.

    If a transaction is supplied, it must be in DRAFT status.
    """

    if not can_manage_transactions(user):
        return False

    if transaction is None:
        return True

    return (
        transaction.status
        == transaction.Status.DRAFT
    )


# =============================================================================
# INCOME
# =============================================================================

def can_manage_income(user):
    """
    Manage financial income.

    Allowed:

        ADMIN
        TREASURER
    """

    return can_manage_finance(user)


def can_create_income_from_payment(
    user,
    payment=None,
):
    """
    Determine whether a user can create income
    from a completed payment.

    The service layer additionally verifies that:

        payment.status == COMPLETED

    and that the payment has not already been linked
    to a financial transaction.
    """

    if not can_manage_income(user):
        return False

    if payment is None:
        return True

    payment_status_class = getattr(
        payment.__class__,
        "Status",
        None,
    )

    if payment_status_class is None:
        return False

    completed_status = getattr(
        payment_status_class,
        "COMPLETED",
        None,
    )

    if completed_status is None:
        return False

    return (
        payment.status
        == completed_status
    )


# =============================================================================
# EXPENSES
# =============================================================================

def can_manage_expenses(user):
    """
    Manage expenses.

    Allowed:

        ADMIN
        TREASURER
    """

    return can_manage_finance(user)


def can_submit_expense(user):
    """
    Submit an expense.
    """

    return can_manage_expenses(user)


def can_approve_expense(user):
    """
    Approve an expense.
    """

    return can_manage_expenses(user)


def can_reject_expense(user):
    """
    Reject an expense.
    """

    return can_manage_expenses(user)


def can_pay_expense(user):
    """
    Pay an approved expense.
    """

    return can_manage_expenses(user)


def can_void_expense(user):
    """
    Void an expense.
    """

    return can_manage_expenses(user)


def can_edit_expense(
    user,
    expense=None,
):
    """
    Determine whether an expense can be edited.

    Only DRAFT expenses may be edited.
    """

    if not can_manage_expenses(user):
        return False

    if expense is None:
        return True

    return (
        expense.status
        == expense.Status.DRAFT
    )


def can_view_expenses(user):
    """
    View expense records.

    Allowed:

        ADMIN
        TREASURER
        EXECUTIVE
    """

    return (
        is_admin(user)
        or is_treasurer(user)
        or is_executive(user)
    )


# =============================================================================
# FINANCIAL CATEGORIES
# =============================================================================

def can_manage_categories(user):
    """
    Create, update, activate, or deactivate
    financial categories.

    Allowed:

        ADMIN
        TREASURER
    """

    return can_manage_finance(user)


def can_delete_category(
    user,
    category=None,
):
    """
    Determine whether a category can be deleted.

    Only administrators may delete categories.

    A category cannot be deleted when:

        - It is a system category.
        - It is already used by transactions.
        - It is already used by expenses.

    In general, deactivation should be preferred
    over physical deletion.
    """

    if not is_admin(user):
        return False

    if category is None:
        return True

    if getattr(
        category,
        "is_system",
        False,
    ):
        return False

    if category.transactions.exists():
        return False

    if category.expenses.exists():
        return False

    return True


# =============================================================================
# RECONCILIATION
# =============================================================================

def can_manage_reconciliation(user):
    """
    Create and manage financial reconciliations.

    Allowed:

        ADMIN
        TREASURER
    """

    return can_manage_finance(user)


def can_reconcile_finance(user):
    """
    Complete a financial reconciliation.

    Allowed:

        ADMIN
        TREASURER
    """

    return can_manage_reconciliation(user)


def can_view_reconciliation(user):
    """
    View reconciliation records.

    Allowed:

        ADMIN
        TREASURER
        EXECUTIVE
    """

    return (
        is_admin(user)
        or is_treasurer(user)
        or is_executive(user)
    )


# =============================================================================
# FINANCIAL REPORTS
# =============================================================================

def can_view_financial_reports(user):
    """
    View detailed financial reports.

    Restricted to:

        ADMIN
        TREASURER
    """

    return can_manage_finance(user)


# =============================================================================
# AUDIT LOGS
# =============================================================================

def can_view_audit_logs(user):
    """
    View financial audit logs.

    Restricted to:

        ADMIN
        TREASURER
    """

    return can_manage_finance(user)


def can_manage_audit_logs(user):
    """
    Audit logs are intended to be immutable.

    Only administrators have management-level authority.

    In practice, audit log records should not be edited
    or deleted through normal application views.
    """

    return is_admin(user)


# =============================================================================
# FINANCIAL RECORD DELETION
# =============================================================================

def can_delete_financial_records(user):
    """
    Financial transactions should never be physically deleted.

    They should be voided instead so that financial history
    remains traceable.
    """

    return False


# =============================================================================
# OPTIONAL GENERAL FINANCE VIEW ACCESS
# =============================================================================

def can_view_finance(user):
    """
    General finance read access.

    Allowed:

        ADMIN
        TREASURER
        EXECUTIVE
    """

    return (
        is_admin(user)
        or is_treasurer(user)
        or is_executive(user)
    )
