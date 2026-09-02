
# finance/services.py

"""
KUCSA Finance Services
======================

Centralized business logic for the KUCSA Finance application.

Architecture
------------

    URL
      ↓
    VIEW
      ↓
    PERMISSION
      ↓
    SERVICE
      ↓
    MODEL

Finance is responsible for:

- Financial categories
- Financial transactions
- Income
- Expenses
- Expense approval workflow
- Payment → Finance integration
- Reconciliation
- Financial balance
- Financial audit logging

IMPORTANT
---------

The Payments application remains responsible for:

- M-Pesa STK Push
- Safaricom authentication
- M-Pesa callbacks
- Payment verification
- Payment status
- M-Pesa receipt information

Finance DOES NOT verify M-Pesa payments.

Finance only records a payment as income after the
Payments application has already marked it COMPLETED.
"""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    Expense,
    FinancialAuditLog,
    FinancialCategory,
    FinancialReconciliation,
    FinancialTransaction,
)

from .permissions import (
    can_manage_categories,
    can_manage_expenses,
    can_manage_income,
    can_manage_reconciliation,
    can_manage_transactions,
    can_view_audit_logs,
    require_permission,
)


# =============================================================================
# CONSTANTS
# =============================================================================

ZERO = Decimal("0.00")
MONEY_PRECISION = Decimal("0.01")
COMPLETED_PAYMENT_VALUE = "COMPLETED"


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _enum_value(value):
    """
    Return the underlying value of a Django TextChoices member.

    This allows the service to safely compare:

        PaymentStatus.COMPLETED

    with:

        "COMPLETED"
    """

    return getattr(value, "value", value)


def _get_choice_constant(owner, *names):
    """
    Safely retrieve the first available constant from a class.

    This is useful for compatibility with slightly different
    enum naming conventions across the project.
    """

    if owner is None:
        return None

    for name in names:
        value = getattr(owner, name, None)

        if value is not None:
            return value

    return None


def _is_completed_payment(payment):
    """
    Return True only when the Payments application has marked
    the payment as COMPLETED.

    The current Payments model uses:

        PaymentStatus.COMPLETED

    as a top-level TextChoices enum.

    We intentionally do not require Finance to import the
    Payments enum directly. This keeps the Finance service
    loosely coupled to the Payments implementation.
    """

    if payment is None:
        return False

    status = getattr(payment, "status", None)

    if status is None:
        return False

    # Current project representation.
    if _enum_value(status) == COMPLETED_PAYMENT_VALUE:
        return True

    # Compatibility with a nested Status enum, should another
    # payment implementation use one.
    status_class = getattr(
        payment.__class__,
        "Status",
        None,
    )

    completed = _get_choice_constant(
        status_class,
        "COMPLETED",
    )

    if completed is not None:
        return _enum_value(status) == _enum_value(completed)

    # Compatibility with Payment.PaymentStatus.
    payment_status_class = getattr(
        payment.__class__,
        "PaymentStatus",
        None,
    )

    completed = _get_choice_constant(
        payment_status_class,
        "COMPLETED",
    )

    if completed is not None:
        return _enum_value(status) == _enum_value(completed)

    return False


def _get_payment_finance_transaction(payment):
    """
    Find the Finance transaction belonging to a Payment.

    We query FinancialTransaction directly rather than relying on
    a reverse relation such as:

        payment.finance_transaction

    because the current Payments model intentionally does not
    define a Finance reverse relation.

    The Finance transaction owns the relationship.
    """

    if payment is None:
        return None

    return (
        FinancialTransaction.objects
        .filter(payment=payment)
        .order_by("pk")
        .first()
    )


def _audit(
    *,
    user,
    action,
    description,
    transaction=None,
    expense=None,
    reconciliation=None,
    category=None,
    old_values=None,
    new_values=None,
):
    """
    Create a centralized financial audit log.
    """

    if user is None:
        raise ValidationError(
            "A user is required for financial audit logging."
        )

    return FinancialAuditLog.objects.create(
        user=user,
        action=action,
        description=description,
        transaction=transaction,
        expense=expense,
        reconciliation=reconciliation,
        category=category,
        old_values=old_values or {},
        new_values=new_values or {},
    )


def _ensure_positive_amount(amount, *, field_name="amount"):
    """
    Validate and normalize a monetary amount.

    Returns:
        Decimal rounded to two decimal places.
    """

    if amount is None:
        raise ValidationError(
            f"{field_name.capitalize()} is required."
        )

    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(
            f"Invalid {field_name}."
        ) from exc

    if amount <= ZERO:
        raise ValidationError(
            f"{field_name.capitalize()} must be greater than zero."
        )

    return amount.quantize(MONEY_PRECISION)


def _ensure_non_negative_amount(
    amount,
    *,
    field_name,
):
    """
    Validate an amount that may be zero but cannot be negative.
    """

    if amount in (None, ""):
        amount = ZERO

    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(
            f"Invalid {field_name} amount."
        ) from exc

    if amount < ZERO:
        raise ValidationError(
            f"{field_name.capitalize()} cannot be negative."
        )

    return amount.quantize(MONEY_PRECISION)


def _validate_financial_category(
    *,
    category,
    expected_type,
):
    """
    Validate that a category:

    - exists
    - is active
    - belongs to the expected category type
    """

    if category is None:
        raise ValidationError(
            "A financial category is required."
        )

    if not getattr(category, "is_active", False):
        raise ValidationError(
            "The selected financial category is inactive."
        )

    if category.category_type != expected_type:

        if expected_type == (
            FinancialCategory.CategoryType.INCOME
        ):
            raise ValidationError(
                "The selected category must be an income category."
            )

        raise ValidationError(
            "The selected category must be an expense category."
        )

    return category


def _validate_transaction_type(transaction_type):
    """
    Validate a financial transaction type.
    """

    valid_types = dict(
        FinancialTransaction.TransactionType.choices
    )

    if transaction_type not in valid_types:
        raise ValidationError(
            "Invalid financial transaction type."
        )


def _validate_transaction_status(status):
    """
    Validate a financial transaction status.
    """

    valid_statuses = dict(
        FinancialTransaction.Status.choices
    )

    if status not in valid_statuses:
        raise ValidationError(
            "Invalid financial transaction status."
        )


def _validate_expense_status(expense, expected_status):
    """
    Validate that an expense is currently in the expected state.
    """

    if expense.status != expected_status:
        raise ValidationError(
            (
                f"Expense {expense.expense_number} must be "
                f"in {expected_status} status."
            )
        )


# =============================================================================
# CATEGORY SERVICES
# =============================================================================

@transaction.atomic
def create_category(
    *,
    user,
    name,
    category_type,
    description="",
    is_active=True,
    is_system=False,
):
    """
    Create a financial category.
    """

    require_permission(
        user,
        can_manage_categories,
    )

    name = (name or "").strip()

    if not name:
        raise ValidationError(
            "Category name is required."
        )

    valid_types = dict(
        FinancialCategory.CategoryType.choices
    )

    if category_type not in valid_types:
        raise ValidationError(
            "Invalid financial category type."
        )

    category = FinancialCategory(
        name=name,
        category_type=category_type,
        description=description or "",
        is_active=bool(is_active),
        is_system=bool(is_system),
    )

    category.full_clean()
    category.save()

    _audit(
        user=user,
        action=FinancialAuditLog.Action.CREATED,
        category=category,
        description=(
            f"Financial category '{category.name}' "
            f"was created."
        ),
        new_values={
            "name": category.name,
            "category_type": category.category_type,
            "description": category.description,
            "is_active": category.is_active,
            "is_system": category.is_system,
        },
    )

    return category


@transaction.atomic
def update_category(
    *,
    user,
    category,
    name=None,
    description=None,
    is_active=None,
):
    """
    Update a financial category.

    System categories cannot be modified.
    """

    require_permission(
        user,
        can_manage_categories,
    )

    if category is None:
        raise ValidationError(
            "A financial category is required."
        )

    if category.is_system:
        raise ValidationError(
            "System categories cannot be modified."
        )

    old_values = {
        "name": category.name,
        "description": category.description,
        "is_active": category.is_active,
    }

    if name is not None:

        name = name.strip()

        if not name:
            raise ValidationError(
                "Category name cannot be empty."
            )

        category.name = name

    if description is not None:
        category.description = description

    if is_active is not None:
        category.is_active = bool(is_active)

    category.full_clean()
    category.save()

    _audit(
        user=user,
        action=FinancialAuditLog.Action.UPDATED,
        category=category,
        description=(
            f"Financial category '{category.name}' "
            f"was updated."
        ),
        old_values=old_values,
        new_values={
            "name": category.name,
            "description": category.description,
            "is_active": category.is_active,
        },
    )

    return category


@transaction.atomic
def deactivate_category(
    *,
    user,
    category,
):
    """
    Deactivate a financial category.

    Existing transactions remain preserved.
    """

    require_permission(
        user,
        can_manage_categories,
    )

    if category is None:
        raise ValidationError(
            "A financial category is required."
        )

    if category.is_system:
        raise ValidationError(
            "System categories cannot be deactivated."
        )

    if not category.is_active:
        return category

    old_values = {
        "is_active": category.is_active,
    }

    category.is_active = False

    category.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.UPDATED,
        category=category,
        description=(
            f"Financial category '{category.name}' "
            f"was deactivated."
        ),
        old_values=old_values,
        new_values={
            "is_active": False,
        },
    )

    return category


@transaction.atomic
def activate_category(
    *,
    user,
    category,
):
    """
    Activate an inactive financial category.
    """

    require_permission(
        user,
        can_manage_categories,
    )

    if category is None:
        raise ValidationError(
            "A financial category is required."
        )

    if category.is_active:
        return category

    old_values = {
        "is_active": category.is_active,
    }

    category.is_active = True

    category.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.UPDATED,
        category=category,
        description=(
            f"Financial category '{category.name}' "
            f"was activated."
        ),
        old_values=old_values,
        new_values={
            "is_active": True,
        },
    )

    return category


@transaction.atomic
def toggle_category(
    *,
    user,
    category,
):
    """
    Toggle a financial category between active and inactive.

    System categories cannot be deactivated.
    """

    require_permission(
        user,
        can_manage_categories,
    )

    if category is None:
        raise ValidationError(
            "A financial category is required."
        )

    if category.is_system and category.is_active:
        raise ValidationError(
            "System categories cannot be deactivated."
        )

    old_status = category.is_active

    category.is_active = not category.is_active

    category.save(
        update_fields=[
            "is_active",
            "updated_at",
        ]
    )

    action_description = (
        "activated"
        if category.is_active
        else "deactivated"
    )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.UPDATED,
        category=category,
        description=(
            f"Financial category '{category.name}' "
            f"was {action_description}."
        ),
        old_values={
            "is_active": old_status,
        },
        new_values={
            "is_active": category.is_active,
        },
    )

    return category


# =============================================================================
# TRANSACTION SERVICES
# =============================================================================

@transaction.atomic
def create_transaction(
    *,
    user,
    transaction_type,
    category,
    amount,
    description,
    payment_source,
    member=None,
    reference="",
    payment=None,
    transaction_date=None,
    notes="",
    status=FinancialTransaction.Status.DRAFT,
):
    """
    Create a financial transaction.

    Supported transaction types:

        INCOME
        EXPENSE

    Payment-originated income is accepted only when the
    Payments application has already marked the payment
    COMPLETED.
    """

    require_permission(
        user,
        can_manage_transactions,
    )

    _validate_transaction_type(transaction_type)

    _validate_transaction_status(status)

    amount = _ensure_positive_amount(amount)

    if transaction_type == (
        FinancialTransaction.TransactionType.INCOME
    ):

        _validate_financial_category(
            category=category,
            expected_type=(
                FinancialCategory.CategoryType.INCOME
            ),
        )

    else:

        _validate_financial_category(
            category=category,
            expected_type=(
                FinancialCategory.CategoryType.EXPENSE
            ),
        )

    # -----------------------------------------------------------------
    # PAYMENT VALIDATION
    # -----------------------------------------------------------------

    if payment is not None:

        if transaction_type != (
            FinancialTransaction.TransactionType.INCOME
        ):
            raise ValidationError(
                "A Payment can only create an income transaction."
            )

        if not _is_completed_payment(payment):
            raise ValidationError(
                "Only COMPLETED payments can become "
                "financial income."
            )

        existing_transaction = (
            _get_payment_finance_transaction(payment)
        )

        if existing_transaction is not None:
            raise ValidationError(
                "This payment already has a financial transaction."
            )

    # -----------------------------------------------------------------
    # CREATE TRANSACTION
    # -----------------------------------------------------------------

    financial_transaction = FinancialTransaction(
        transaction_type=transaction_type,
        status=status,
        category=category,
        amount=amount,
        description=(description or "").strip(),
        reference=(reference or "").strip(),
        payment_source=payment_source,
        payment=payment,
        member=member,
        recorded_by=user,
        transaction_date=(
            transaction_date
            or timezone.now()
        ),
        notes=notes or "",
    )

    financial_transaction.full_clean()
    financial_transaction.save()

    _audit(
        user=user,
        action=FinancialAuditLog.Action.CREATED,
        transaction=financial_transaction,
        description=(
            f"Financial transaction "
            f"{financial_transaction.transaction_number} "
            f"was created."
        ),
        new_values={
            "transaction_type": (
                financial_transaction.transaction_type
            ),
            "amount": str(
                financial_transaction.amount
            ),
            "status": (
                financial_transaction.status
            ),
            "category": category.name,
            "payment_source": (
                financial_transaction.payment_source
            ),
            "reference": (
                financial_transaction.reference
            ),
            "payment_id": (
                payment.pk
                if payment is not None
                else None
            ),
            "member_id": (
                member.pk
                if member is not None
                else None
            ),
        },
    )

    return financial_transaction


@transaction.atomic
def create_income(
    *,
    user,
    category,
    amount,
    description,
    payment_source=FinancialTransaction.PaymentSource.MPESA,
    member=None,
    reference="",
    payment=None,
    transaction_date=None,
    notes="",
    post=False,
):
    """
    Create an income transaction.

    When payment is supplied, it must already be COMPLETED.

    Finance never verifies the payment itself.
    """

    require_permission(
        user,
        can_manage_income,
    )

    _validate_financial_category(
        category=category,
        expected_type=(
            FinancialCategory.CategoryType.INCOME
        ),
    )

    status = (
        FinancialTransaction.Status.POSTED
        if post
        else FinancialTransaction.Status.DRAFT
    )

    return create_transaction(
        user=user,
        transaction_type=(
            FinancialTransaction.TransactionType.INCOME
        ),
        category=category,
        amount=amount,
        description=description,
        payment_source=payment_source,
        member=member,
        reference=reference,
        payment=payment,
        transaction_date=transaction_date,
        notes=notes,
        status=status,
    )


@transaction.atomic
def create_expense_transaction(
    *,
    user,
    category,
    amount,
    description,
    payment_source=FinancialTransaction.PaymentSource.MPESA,
    member=None,
    reference="",
    transaction_date=None,
    notes="",
    post=False,
):
    """
    Create an expense ledger transaction.

    Normally called internally when an approved expense
    is actually paid.
    """

    require_permission(
        user,
        can_manage_transactions,
    )

    _validate_financial_category(
        category=category,
        expected_type=(
            FinancialCategory.CategoryType.EXPENSE
        ),
    )

    status = (
        FinancialTransaction.Status.POSTED
        if post
        else FinancialTransaction.Status.DRAFT
    )

    return create_transaction(
        user=user,
        transaction_type=(
            FinancialTransaction.TransactionType.EXPENSE
        ),
        category=category,
        amount=amount,
        description=description,
        payment_source=payment_source,
        member=member,
        reference=reference,
        transaction_date=transaction_date,
        notes=notes,
        status=status,
    )


@transaction.atomic
def post_transaction(
    *,
    user,
    financial_transaction,
):
    """
    Post a draft financial transaction.

    Only POSTED transactions affect the balance.
    """

    require_permission(
        user,
        can_manage_transactions,
    )

    if financial_transaction is None:
        raise ValidationError(
            "A financial transaction is required."
        )

    if financial_transaction.status != (
        FinancialTransaction.Status.DRAFT
    ):
        raise ValidationError(
            "Only draft transactions can be posted."
        )

    old_status = financial_transaction.status

    financial_transaction.status = (
        FinancialTransaction.Status.POSTED
    )

    financial_transaction.posted_at = timezone.now()

    financial_transaction.full_clean()

    financial_transaction.save(
        update_fields=[
            "status",
            "posted_at",
            "updated_at",
        ]
    )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.POSTED,
        transaction=financial_transaction,
        description=(
            f"Financial transaction "
            f"{financial_transaction.transaction_number} "
            f"was posted."
        ),
        old_values={
            "status": old_status,
        },
        new_values={
            "status": financial_transaction.status,
            "posted_at": (
                financial_transaction.posted_at.isoformat()
            ),
        },
    )

    return financial_transaction


@transaction.atomic
def void_transaction(
    *,
    user,
    financial_transaction,
):
    """
    Void a financial transaction.

    Transactions are never physically deleted.
    Financial history is preserved.
    """

    require_permission(
        user,
        can_manage_transactions,
    )

    if financial_transaction is None:
        raise ValidationError(
            "A financial transaction is required."
        )

    if financial_transaction.status == (
        FinancialTransaction.Status.VOIDED
    ):
        raise ValidationError(
            "Transaction is already voided."
        )

    old_status = financial_transaction.status

    financial_transaction.status = (
        FinancialTransaction.Status.VOIDED
    )

    financial_transaction.full_clean()

    financial_transaction.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.VOIDED,
        transaction=financial_transaction,
        description=(
            f"Financial transaction "
            f"{financial_transaction.transaction_number} "
            f"was voided."
        ),
        old_values={
            "status": old_status,
        },
        new_values={
            "status": financial_transaction.status,
        },
    )

    return financial_transaction


# =============================================================================
# EXPENSE SERVICES
# =============================================================================

@transaction.atomic
def create_expense(
    *,
    user,
    category,
    amount,
    title,
    description,
    payee="",
    payment_source=FinancialTransaction.PaymentSource.MPESA,
    expense_date=None,
    receipt=None,
    notes="",
):
    """
    Create an expense in DRAFT status.

    Draft expenses do not affect the financial balance.
    """

    require_permission(
        user,
        can_manage_expenses,
    )

    amount = _ensure_positive_amount(
        amount,
        field_name="expense amount",
    )

    _validate_financial_category(
        category=category,
        expected_type=(
            FinancialCategory.CategoryType.EXPENSE
        ),
    )

    title = (title or "").strip()

    if not title:
        raise ValidationError(
            "Expense title is required."
        )

    expense = Expense(
        category=category,
        amount=amount,
        title=title,
        description=(description or "").strip(),
        payee=(payee or "").strip(),
        payment_source=payment_source,
        status=Expense.Status.DRAFT,
        expense_date=(
            expense_date
            or timezone.now()
        ),
        recorded_by=user,
        receipt=receipt,
        notes=notes or "",
    )

    expense.full_clean()
    expense.save()

    _audit(
        user=user,
        action=FinancialAuditLog.Action.CREATED,
        expense=expense,
        description=(
            f"Expense {expense.expense_number} "
            f"was created."
        ),
        new_values={
            "title": expense.title,
            "amount": str(expense.amount),
            "category": category.name,
            "status": expense.status,
        },
    )

    return expense


@transaction.atomic
def update_expense(
    *,
    user,
    expense,
    category=None,
    amount=None,
    title=None,
    description=None,
    payee=None,
    payment_source=None,
    expense_date=None,
    receipt=None,
    notes=None,
):
    """
    Update an expense only while it is DRAFT.
    """

    require_permission(
        user,
        can_manage_expenses,
    )

    if expense is None:
        raise ValidationError(
            "An expense is required."
        )

    if expense.status != Expense.Status.DRAFT:
        raise ValidationError(
            "Only draft expenses can be edited."
        )

    old_values = {
        "category": (
            expense.category.name
            if expense.category
            else None
        ),
        "amount": str(expense.amount),
        "title": expense.title,
        "description": expense.description,
        "payee": expense.payee,
        "payment_source": expense.payment_source,
        "expense_date": (
            expense.expense_date.isoformat()
            if expense.expense_date
            else None
        ),
    }

    if category is not None:

        _validate_financial_category(
            category=category,
            expected_type=(
                FinancialCategory.CategoryType.EXPENSE
            ),
        )

        expense.category = category

    if amount is not None:
        expense.amount = _ensure_positive_amount(
            amount,
            field_name="expense amount",
        )

    if title is not None:

        title = title.strip()

        if not title:
            raise ValidationError(
                "Expense title cannot be empty."
            )

        expense.title = title

    if description is not None:
        expense.description = description

    if payee is not None:
        expense.payee = payee.strip()

    if payment_source is not None:
        expense.payment_source = payment_source

    if expense_date is not None:
        expense.expense_date = expense_date

    if receipt is not None:
        expense.receipt = receipt

    if notes is not None:
        expense.notes = notes

    expense.full_clean()
    expense.save()

    _audit(
        user=user,
        action=FinancialAuditLog.Action.UPDATED,
        expense=expense,
        description=(
            f"Expense {expense.expense_number} "
            f"was updated."
        ),
        old_values=old_values,
        new_values={
            "category": (
                expense.category.name
                if expense.category
                else None
            ),
            "amount": str(expense.amount),
            "title": expense.title,
            "description": expense.description,
            "payee": expense.payee,
            "payment_source": expense.payment_source,
            "expense_date": (
                expense.expense_date.isoformat()
                if expense.expense_date
                else None
            ),
        },
    )

    return expense


@transaction.atomic
def submit_expense(
    *,
    user,
    expense,
):
    """
    Submit a DRAFT expense for approval.
    """

    require_permission(
        user,
        can_manage_expenses,
    )

    if expense is None:
        raise ValidationError(
            "An expense is required."
        )

    _validate_expense_status(
        expense,
        Expense.Status.DRAFT,
    )

    expense.status = Expense.Status.SUBMITTED
    expense.submitted_by = user
    expense.submitted_at = timezone.now()

    expense.full_clean()

    expense.save(
        update_fields=[
            "status",
            "submitted_by",
            "submitted_at",
            "updated_at",
        ]
    )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.SUBMITTED,
        expense=expense,
        description=(
            f"Expense {expense.expense_number} "
            f"was submitted for approval."
        ),
        new_values={
            "status": expense.status,
            "submitted_by": user.pk,
            "submitted_at": (
                expense.submitted_at.isoformat()
            ),
        },
    )

    return expense


@transaction.atomic
def approve_expense(
    *,
    user,
    expense,
):
    """
    Approve a submitted expense.

    Approval does NOT affect the balance.

    Only payment of the expense creates the posted
    expense ledger transaction.
    """

    require_permission(
        user,
        can_manage_expenses,
    )

    if expense is None:
        raise ValidationError(
            "An expense is required."
        )

    _validate_expense_status(
        expense,
        Expense.Status.SUBMITTED,
    )

    expense.status = Expense.Status.APPROVED
    expense.approved_by = user
    expense.approved_at = timezone.now()

    expense.full_clean()

    expense.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_at",
            "updated_at",
        ]
    )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.APPROVED,
        expense=expense,
        description=(
            f"Expense {expense.expense_number} "
            f"was approved."
        ),
        new_values={
            "status": expense.status,
            "approved_by": user.pk,
            "approved_at": (
                expense.approved_at.isoformat()
            ),
        },
    )

    return expense


@transaction.atomic
def reject_expense(
    *,
    user,
    expense,
    reason,
):
    """
    Reject a submitted expense.

    A meaningful rejection reason is mandatory.
    """

    require_permission(
        user,
        can_manage_expenses,
    )

    if expense is None:
        raise ValidationError(
            "An expense is required."
        )

    _validate_expense_status(
        expense,
        Expense.Status.SUBMITTED,
    )

    reason = (reason or "").strip()

    if not reason:
        raise ValidationError(
            "A rejection reason is required."
        )

    expense.status = Expense.Status.REJECTED
    expense.rejected_by = user
    expense.rejected_at = timezone.now()
    expense.rejection_reason = reason

    expense.full_clean()

    expense.save(
        update_fields=[
            "status",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "updated_at",
        ]
    )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.REJECTED,
        expense=expense,
        description=(
            f"Expense {expense.expense_number} "
            f"was rejected."
        ),
        new_values={
            "status": expense.status,
            "rejected_by": user.pk,
            "rejected_at": (
                expense.rejected_at.isoformat()
            ),
            "rejection_reason": reason,
        },
    )

    return expense


@transaction.atomic
def pay_expense(
    *,
    user,
    expense,
    payment_reference=None,
):
    """
    Pay an APPROVED expense.

    Workflow:

        DRAFT
          ↓
        SUBMITTED
          ↓
        APPROVED
          ↓
        PAID
          ↓
        POSTED EXPENSE TRANSACTION

    Only the POSTED transaction affects the balance.
    """

    require_permission(
        user,
        can_manage_expenses,
    )

    if expense is None:
        raise ValidationError(
            "An expense is required."
        )

    _validate_expense_status(
        expense,
        Expense.Status.APPROVED,
    )

    # Prevent duplicate payment/ledger creation.
    if expense.transaction_id:
        raise ValidationError(
            "This expense already has a financial transaction."
        )

    if payment_reference is not None:

        payment_reference = (
            str(payment_reference).strip()
        )

        if payment_reference:
            expense.payment_reference = payment_reference

    current_reference = (
        getattr(
            expense,
            "payment_reference",
            "",
        )
        or ""
    ).strip()

    if not current_reference:
        raise ValidationError(
            "A payment reference is required for a paid expense."
        )

    # -----------------------------------------------------------------
    # Mark expense paid first inside the same atomic transaction.
    # If ledger creation fails, the expense update is rolled back.
    # -----------------------------------------------------------------

    expense.status = Expense.Status.PAID
    expense.paid_by = user
    expense.paid_at = timezone.now()

    expense.full_clean()

    expense.save(
        update_fields=[
            "status",
            "paid_by",
            "paid_at",
            "payment_reference",
            "updated_at",
        ]
    )

    # -----------------------------------------------------------------
    # CREATE POSTED EXPENSE TRANSACTION
    # -----------------------------------------------------------------

    ledger_transaction = create_expense_transaction(
        user=user,
        category=expense.category,
        amount=expense.amount,
        description=(
            f"Payment of expense "
            f"{expense.expense_number}: "
            f"{expense.title}"
        ),
        payment_source=expense.payment_source,
        reference=current_reference,
        transaction_date=expense.paid_at,
        notes=expense.notes,
        post=True,
    )

    expense.transaction = ledger_transaction

    expense.save(
        update_fields=[
            "transaction",
            "updated_at",
        ]
    )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.PAID,
        expense=expense,
        transaction=ledger_transaction,
        description=(
            f"Expense {expense.expense_number} "
            f"was paid and posted to the financial ledger."
        ),
        new_values={
            "status": expense.status,
            "paid_by": user.pk,
            "paid_at": expense.paid_at.isoformat(),
            "payment_reference": current_reference,
            "transaction": (
                ledger_transaction.transaction_number
            ),
        },
    )

    return expense


@transaction.atomic
def void_expense(
    *,
    user,
    expense,
    reason,
):
    """
    Void an expense.

    Financial history is preserved.

    If a financial transaction exists, it is also voided.
    """

    require_permission(
        user,
        can_manage_expenses,
    )

    if expense is None:
        raise ValidationError(
            "An expense is required."
        )

    reason = (reason or "").strip()

    if not reason:
        raise ValidationError(
            "A void reason is required."
        )

    if expense.status == Expense.Status.VOIDED:
        raise ValidationError(
            "This expense is already voided."
        )

    old_status = expense.status

    expense.status = Expense.Status.VOIDED
    expense.voided_by = user
    expense.voided_at = timezone.now()
    expense.void_reason = reason

    expense.full_clean()

    expense.save(
        update_fields=[
            "status",
            "voided_by",
            "voided_at",
            "void_reason",
            "updated_at",
        ]
    )

    linked_transaction = expense.transaction

    if linked_transaction is not None:

        void_transaction(
            user=user,
            financial_transaction=linked_transaction,
        )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.VOIDED,
        expense=expense,
        transaction=linked_transaction,
        description=(
            f"Expense {expense.expense_number} "
            f"was voided."
        ),
        old_values={
            "status": old_status,
        },
        new_values={
            "status": expense.status,
            "void_reason": reason,
            "transaction": (
                linked_transaction.transaction_number
                if linked_transaction
                else None
            ),
        },
    )

    return expense


# =============================================================================
# PAYMENT → FINANCE
# =============================================================================

@transaction.atomic
def record_completed_payment(
    *,
    user,
    payment,
    category,
    description=None,
    member=None,
    reference=None,
    notes="",
):
    """
    Record a COMPLETED payment as financial income.

    Finance does not verify M-Pesa.

    The Payments application must first mark the payment
    as COMPLETED.
    """

    require_permission(
        user,
        can_manage_income,
    )

    if payment is None:
        raise ValidationError(
            "A payment is required."
        )

    if not _is_completed_payment(payment):
        raise ValidationError(
            "Only COMPLETED payments can be recorded "
            "as financial income."
        )

    # -----------------------------------------------------------------
    # DUPLICATE PROTECTION
    # -----------------------------------------------------------------

    existing_transaction = (
        _get_payment_finance_transaction(payment)
    )

    if existing_transaction is not None:
        return existing_transaction

    # -----------------------------------------------------------------
    # PAYMENT AMOUNT
    # -----------------------------------------------------------------

    amount = getattr(
        payment,
        "amount",
        None,
    )

    if amount is None:
        raise ValidationError(
            "The payment does not contain an amount."
        )

    # -----------------------------------------------------------------
    # MEMBER
    # -----------------------------------------------------------------

    if member is None:
        member = getattr(
            payment,
            "member",
            None,
        )

    # -----------------------------------------------------------------
    # M-PESA RECEIPT
    # -----------------------------------------------------------------

    if reference is None:

        reference = getattr(
            payment,
            "mpesa_receipt_number",
            "",
        )

    if not reference:

        reference = getattr(
            payment,
            "reference",
            "",
        )

    if not reference:

        reference = getattr(
            payment,
            "checkout_request_id",
            "",
        )

    if not reference:

        reference = getattr(
            payment,
            "merchant_request_id",
            "",
        )

    # -----------------------------------------------------------------
    # DESCRIPTION
    # -----------------------------------------------------------------

    if not description:

        if member is not None:
            description = (
                f"Completed payment from {member}."
            )
        else:
            description = (
                "Income received from completed payment."
            )

    # -----------------------------------------------------------------
    # PAYMENT COMPLETION TIME
    # -----------------------------------------------------------------

    completed_at = getattr(
        payment,
        "completed_at",
        None,
    )

    transaction_date = (
        completed_at
        or getattr(
            payment,
            "transaction_date",
            None,
        )
        or timezone.now()
    )

    # -----------------------------------------------------------------
    # CREATE POSTED FINANCIAL INCOME
    # -----------------------------------------------------------------

    financial_transaction = create_income(
        user=user,
        category=category,
        amount=amount,
        description=description,
        payment_source=(
            FinancialTransaction.PaymentSource.MPESA
        ),
        member=member,
        reference=reference or "",
        payment=payment,
        transaction_date=transaction_date,
        notes=notes,
        post=True,
    )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.POSTED,
        transaction=financial_transaction,
        description=(
            f"Completed payment was recorded as "
            f"financial income under transaction "
            f"{financial_transaction.transaction_number}."
        ),
        new_values={
            "payment_id": payment.pk,
            "transaction": (
                financial_transaction.transaction_number
            ),
            "amount": str(
                financial_transaction.amount
            ),
            "reference": reference or "",
            "completed_at": (
                completed_at.isoformat()
                if completed_at
                else None
            ),
        },
    )

    return financial_transaction


# =============================================================================
# PAYMENT → FINANCE AUTOMATIC SYNCHRONIZATION
# =============================================================================

@transaction.atomic
def sync_completed_payment_to_finance(
    *,
    payment,
    category,
    user=None,
    description=None,
    member=None,
    reference=None,
    notes="",
):
    """
    Synchronize a COMPLETED payment into Finance.

    Intended usage:

        Payments application
              ↓
        Payment becomes COMPLETED
              ↓
        Payment service/callback
              ↓
        sync_completed_payment_to_finance()
              ↓
        Finance income transaction
              ↓
        POSTED
              ↓
        Financial balance updated

    IMPORTANT
    ---------

    This function does NOT:

    - perform M-Pesa verification
    - call Safaricom
    - perform STK Push
    - modify Payment status
    - activate membership

    It only consumes an already-COMPLETED payment.

    Idempotency
    -----------

    If the payment already has a Finance transaction,
    that transaction is returned instead of creating a duplicate.
    """

    if payment is None:
        raise ValidationError(
            "A payment is required."
        )

    # -----------------------------------------------------------------
    # PAYMENT STATUS
    # -----------------------------------------------------------------

    if not _is_completed_payment(payment):
        raise ValidationError(
            "Only COMPLETED payments can be synchronized "
            "to Finance."
        )

    # -----------------------------------------------------------------
    # IDEMPOTENCY
    # -----------------------------------------------------------------

    existing_transaction = (
        _get_payment_finance_transaction(payment)
    )

    if existing_transaction is not None:
        return existing_transaction

    # -----------------------------------------------------------------
    # USER
    # -----------------------------------------------------------------

    if user is None:

        # A payment may have an explicitly recorded creator
        # depending on the current Payment implementation.
        user = getattr(
            payment,
            "recorded_by",
            None,
        )

    if user is None:

        user = getattr(
            payment,
            "created_by",
            None,
        )

    if user is None:

        # verified_by is supported only when the Payment model
        # actually provides it.
        user = getattr(
            payment,
            "verified_by",
            None,
        )

    if user is None:
        raise ValidationError(
            "A Finance user is required to synchronize "
            "the completed payment."
        )

    # -----------------------------------------------------------------
    # MEMBER
    # -----------------------------------------------------------------

    if member is None:
        member = getattr(
            payment,
            "member",
            None,
        )

    # -----------------------------------------------------------------
    # REFERENCE
    # -----------------------------------------------------------------

    if reference is None:

        reference = getattr(
            payment,
            "mpesa_receipt_number",
            "",
        )

    if not reference:

        reference = getattr(
            payment,
            "reference",
            "",
        )

    if not reference:

        reference = getattr(
            payment,
            "checkout_request_id",
            "",
        )

    if not reference:

        reference = getattr(
            payment,
            "merchant_request_id",
            "",
        )

    # -----------------------------------------------------------------
    # DESCRIPTION
    # -----------------------------------------------------------------

    if not description:

        if member is not None:
            description = (
                f"Completed payment from {member}."
            )
        else:
            description = (
                "Completed payment synchronized to Finance."
            )

    # -----------------------------------------------------------------
    # RECORD PAYMENT
    # -----------------------------------------------------------------

    return record_completed_payment(
        user=user,
        payment=payment,
        category=category,
        description=description,
        member=member,
        reference=reference,
        notes=notes,
    )


# =============================================================================
# RECONCILIATION SERVICES
# =============================================================================

@transaction.atomic
def create_reconciliation(
    *,
    user,
    source,
    period_start,
    period_end,
    statement_reference="",
    external_income=ZERO,
    external_expenses=ZERO,
    notes="",
    statement_file=None,
):
    """
    Create a financial reconciliation record.

    System totals are calculated exclusively from POSTED
    Finance transactions within the selected period.
    """

    require_permission(
        user,
        can_manage_reconciliation,
    )

    if period_start is None or period_end is None:
        raise ValidationError(
            "Both period start and period end are required."
        )

    if period_end < period_start:
        raise ValidationError(
            "Period end cannot be earlier than period start."
        )

    valid_sources = dict(
        FinancialReconciliation.Source.choices
    )

    if source not in valid_sources:
        raise ValidationError(
            "Invalid reconciliation source."
        )

    external_income = _ensure_non_negative_amount(
        external_income,
        field_name="external income",
    )

    external_expenses = _ensure_non_negative_amount(
        external_expenses,
        field_name="external expenses",
    )

    # -----------------------------------------------------------------
    # SYSTEM INCOME
    # -----------------------------------------------------------------

    system_income = (
        FinancialTransaction.objects
        .filter(
            transaction_type=(
                FinancialTransaction.TransactionType.INCOME
            ),
            status=(
                FinancialTransaction.Status.POSTED
            ),
            transaction_date__date__gte=period_start,
            transaction_date__date__lte=period_end,
        )
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or ZERO
    )

    # -----------------------------------------------------------------
    # SYSTEM EXPENSES
    # -----------------------------------------------------------------

    system_expenses = (
        FinancialTransaction.objects
        .filter(
            transaction_type=(
                FinancialTransaction.TransactionType.EXPENSE
            ),
            status=(
                FinancialTransaction.Status.POSTED
            ),
            transaction_date__date__gte=period_start,
            transaction_date__date__lte=period_end,
        )
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or ZERO
    )

    system_income = Decimal(
        str(system_income)
    ).quantize(MONEY_PRECISION)

    system_expenses = Decimal(
        str(system_expenses)
    ).quantize(MONEY_PRECISION)

    reconciliation = FinancialReconciliation(
        source=source,
        statement_reference=(
            statement_reference or ""
        ).strip(),
        period_start=period_start,
        period_end=period_end,
        system_income=system_income,
        system_expenses=system_expenses,
        external_income=external_income,
        external_expenses=external_expenses,
        status=(
            FinancialReconciliation.Status.DRAFT
        ),
        prepared_by=user,
        notes=notes or "",
        statement_file=statement_file,
    )

    reconciliation.full_clean()
    reconciliation.save()

    _audit(
        user=user,
        action=FinancialAuditLog.Action.CREATED,
        reconciliation=reconciliation,
        description=(
            f"Financial reconciliation "
            f"{reconciliation.reconciliation_number} "
            f"was created."
        ),
        new_values={
            "source": source,
            "statement_reference": (
                statement_reference or ""
            ),
            "period_start": str(period_start),
            "period_end": str(period_end),
            "system_income": str(system_income),
            "system_expenses": str(system_expenses),
            "external_income": str(external_income),
            "external_expenses": str(external_expenses),
        },
    )

    return reconciliation


@transaction.atomic
def reconcile_finance(
    *,
    user,
    reconciliation,
):
    """
    Complete a financial reconciliation.

    A reconciliation becomes RECONCILED only when:

        system income == external income

    and:

        system expenses == external expenses
    """

    require_permission(
        user,
        can_manage_reconciliation,
    )

    if reconciliation is None:
        raise ValidationError(
            "A reconciliation is required."
        )

    if reconciliation.status == (
        FinancialReconciliation.Status.RECONCILED
    ):
        raise ValidationError(
            "This reconciliation is already completed."
        )

    if not reconciliation.is_balanced:

        reconciliation.status = (
            FinancialReconciliation.Status.DISCREPANCY
        )

        reconciliation.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        _audit(
            user=user,
            action=FinancialAuditLog.Action.UPDATED,
            reconciliation=reconciliation,
            description=(
                f"Financial reconciliation "
                f"{reconciliation.reconciliation_number} "
                f"has discrepancies."
            ),
            new_values={
                "status": reconciliation.status,
            },
        )

        raise ValidationError(
            "The reconciliation has discrepancies and "
            "cannot be marked as reconciled."
        )

    reconciliation.status = (
        FinancialReconciliation.Status.RECONCILED
    )

    reconciliation.reconciled_by = user
    reconciliation.reconciled_at = timezone.now()

    reconciliation.full_clean()

    reconciliation.save(
        update_fields=[
            "status",
            "reconciled_by",
            "reconciled_at",
            "updated_at",
        ]
    )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.RECONCILED,
        reconciliation=reconciliation,
        description=(
            f"Financial reconciliation "
            f"{reconciliation.reconciliation_number} "
            f"was completed."
        ),
        new_values={
            "status": reconciliation.status,
            "reconciled_by": user.pk,
            "reconciled_at": (
                reconciliation.reconciled_at.isoformat()
            ),
        },
    )

    return reconciliation


# =============================================================================
# FINANCIAL TOTALS
# =============================================================================

def get_financial_totals():
    """
    Return current Finance totals.

    Only POSTED transactions are included.

    Returns:

        {
            "income": Decimal,
            "expenses": Decimal,
            "balance": Decimal,
        }
    """

    totals = (
        FinancialTransaction.objects
        .filter(
            status=FinancialTransaction.Status.POSTED
        )
        .values(
            "transaction_type"
        )
        .annotate(
            total=Sum("amount")
        )
    )

    income = ZERO
    expenses = ZERO

    for row in totals:

        amount = (
            Decimal(str(row["total"] or ZERO))
            .quantize(MONEY_PRECISION)
        )

        if row["transaction_type"] == (
            FinancialTransaction.TransactionType.INCOME
        ):
            income += amount

        elif row["transaction_type"] == (
            FinancialTransaction.TransactionType.EXPENSE
        ):
            expenses += amount

    income = income.quantize(MONEY_PRECISION)
    expenses = expenses.quantize(MONEY_PRECISION)

    balance = (
        income - expenses
    ).quantize(MONEY_PRECISION)

    return {
        "income": income,
        "expenses": expenses,
        "balance": balance,
    }


def get_financial_balance():
    """
    Calculate the current financial balance.

        POSTED INCOME
              -
        POSTED EXPENSES
              =
        AVAILABLE BALANCE
    """

    return get_financial_totals()["balance"]


# =============================================================================
# AUDIT LOG ACCESS
# =============================================================================

def get_audit_logs(
    *,
    user,
    limit=None,
):
    """
    Return financial audit logs for authorized users.

    Audit logs are read-only.
    """

    require_permission(
        user,
        can_view_audit_logs,
    )

    queryset = (
        FinancialAuditLog.objects
        .select_related(
            "user",
            "transaction",
            "expense",
            "reconciliation",
            "category",
        )
        .order_by("-created_at")
    )

    if limit is not None:

        try:
            limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "Audit log limit must be a valid integer."
            ) from exc

        if limit <= 0:
            return queryset.none()

        queryset = queryset[:limit]

    return queryset
