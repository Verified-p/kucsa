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

IMPORTANT
---------

The User model does not contain a single:

    Role.EXECUTIVE

choice.

Instead, KUCSA executive positions are defined individually:

    CHAIRPERSON
    VICE_CHAIRPERSON
    SECRETARY
    SECRETARY_GENERAL
    TREASURER
    ORGANIZING_SECRETARY
    PUBLICITY_SECRETARY

The User model exposes these through:

    User.EXECUTIVE_ROLES

Therefore, this permission module must use
User.EXECUTIVE_ROLES when determining whether
a user is an executive.

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

IMPORTANT FINANCE RULE
----------------------

Viewing financial records is different from managing financial
records.

Therefore:

    ADMIN
        Full access.

    TREASURER
        Full access.

    EXECUTIVE
        Read-only access.

    MEMBER / STUDENT
        No finance access.
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
        and getattr(
            user,
            "is_authenticated",
            False,
        )
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
            can_view_income
            can_view_audit_logs

    Returns
    -------
    True
        When permission is granted.

    Raises
    ------
    PermissionDenied
        When permission is not granted.
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


def _has_executive_role(user):
    """
    Check whether the user holds any KUCSA executive role.

    The User model defines executive roles centrally through:

        User.EXECUTIVE_ROLES

    This avoids assuming that there is a single
    User.Role.EXECUTIVE choice.
    """

    if not is_authenticated(user):
        return False

    role = _get_role(user)

    executive_roles = getattr(
        user.__class__,
        "EXECUTIVE_ROLES",
        frozenset(),
    )

    return role in executive_roles


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

    IMPORTANT
    ---------

    Treasurer is an explicit KUCSA organizational role.

    Being an executive does not automatically make a user
    a Treasurer.
    """

    return _has_role(
        user,
        "TREASURER",
    )


def is_executive(user):
    """
    Check whether the user holds any KUCSA executive role.

    Executive roles are defined centrally by the User model
    through User.EXECUTIVE_ROLES.

    Current executive roles include:

        CHAIRPERSON
        VICE_CHAIRPERSON
        SECRETARY
        SECRETARY_GENERAL
        TREASURER
        ORGANIZING_SECRETARY
        PUBLICITY_SECRETARY

    IMPORTANT
    ---------

    There is intentionally no requirement for:

        User.Role.EXECUTIVE

    because the User model defines executive positions
    individually.
    """

    return _has_executive_role(user)


# =============================================================================
# FINANCE MANAGEMENT
# =============================================================================

def can_manage_finance(user):
    """
    Full finance management access.

    Allowed:

        ADMIN
        TREASURER

    This permission MUST NOT be used for simple
    read-only finance pages.

    Executive positions such as:

        CHAIRPERSON
        VICE_CHAIRPERSON
        SECRETARY
        SECRETARY_GENERAL
        ORGANIZING_SECRETARY
        PUBLICITY_SECRETARY

    do not receive finance management access merely
    because they are executives.
    """

    return (
        is_admin(user)
        or is_treasurer(user)
    )


# =============================================================================
# GENERAL FINANCE VIEW ACCESS
# =============================================================================

def can_view_finance(user):
    """
    General finance read access.

    Allowed:

        ADMIN
        TREASURER
        EXECUTIVE

    This is the basic read-only finance permission.

    Executives may view financial records but may not
    perform finance management actions.
    """

    return (
        is_admin(user)
        or is_treasurer(user)
        or is_executive(user)
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

    return can_view_finance(user)


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

    return can_view_finance(user)


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

def can_view_income(user):
    """
    View income records.

    Allowed:

        ADMIN
        TREASURER
        EXECUTIVE

    EXECUTIVE users have read-only access.

    They cannot create, edit, post, void, or otherwise
    manage income.
    """

    return can_view_finance(user)


def can_manage_income(user):
    """
    Create, edit, post, update, or otherwise manage
    financial income.

    Allowed:

        ADMIN
        TREASURER

    EXECUTIVE users are intentionally excluded because
    their finance access is read-only.
    """

    return can_manage_finance(user)


def can_create_income_from_payment(
    user,
    payment=None,
):
    """
    Determine whether a user can create income
    from a completed payment.

    Only ADMIN and TREASURER may perform this action.

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

    Only ADMIN and TREASURER may submit expenses
    under the current finance authorization model.
    """

    return can_manage_expenses(user)


def can_approve_expense(user):
    """
    Approve an expense.

    Allowed:

        ADMIN
        TREASURER
    """

    return can_manage_expenses(user)


def can_reject_expense(user):
    """
    Reject an expense.

    Allowed:

        ADMIN
        TREASURER
    """

    return can_manage_expenses(user)


def can_pay_expense(user):
    """
    Pay an approved expense.

    Allowed:

        ADMIN
        TREASURER
    """

    return can_manage_expenses(user)


def can_void_expense(user):
    """
    Void an expense.

    Allowed:

        ADMIN
        TREASURER
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

    return can_view_finance(user)


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

    return can_view_finance(user)


# =============================================================================
# FINANCIAL REPORTS
# =============================================================================

def can_view_financial_reports(user):
    """
    View detailed financial reports.

    Restricted to:

        ADMIN
        TREASURER

    Executives do not receive access to detailed
    financial reports under this permission model.
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

    Therefore physical deletion is never permitted.
    """

    return False