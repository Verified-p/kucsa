"""
KUCSA FINANCE SERVICES
======================

Centralized business logic for the KUCSA Finance application.

ARCHITECTURE
------------

Payments
    └── Handles M-Pesa/STK/payment processing

Finance
    └── Handles accounting records and financial reporting

IMPORTANT ACCOUNTING RULES
--------------------------

1. Only COMPLETED payments are eligible for Finance.
2. One completed Payment creates one FinancialTransaction.
3. Only POSTED FinancialTransactions affect the accounting balance.
4. DRAFT and VOIDED transactions do not affect the accounting balance.
5. Expenses follow:

       DRAFT
          ↓
       SUBMITTED
          ↓
       APPROVED
          ↓
        PAID
          ↓
    POSTED EXPENSE TRANSACTION

6. Membership/support payments are both recorded as income.
7. Support payments never activate or renew membership.
8. Finance is the accounting source of truth.
9. Financial audit logs are immutable.
10. Business logic belongs in this service layer, not in views.
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


# =============================================================================
# CONSTANTS
# =============================================================================

ZERO = Decimal("0.00")
MONEY_PRECISION = Decimal("0.01")

COMPLETED_PAYMENT_VALUE = "COMPLETED"


# =============================================================================
# INTERNAL ENUM HELPERS
# =============================================================================

def _enum_value(value):
    """
    Return the underlying value of a Django TextChoices/enum value.

    Works with both enum members and ordinary strings.
    """

    return getattr(value, "value", value)


def _get_choice_constant(choice_class, name):
    """
    Safely retrieve a choice constant.
    """

    return getattr(choice_class, name, None)


def _is_completed_payment(payment):
    """
    Determine whether a Payment is completed.

    PaymentStatus is defined at module level in payments.models,
    therefore this helper intentionally checks the stored status
    value instead of depending on Payment.Status.
    """

    if payment is None:
        return False

    status = getattr(payment, "status", None)

    return _enum_value(status) == COMPLETED_PAYMENT_VALUE


def _get_payment_finance_transaction(payment):
    """
    Return the Finance transaction linked to a payment.

    Payment -> FinancialTransaction is OneToOne with:

        related_name="finance_transaction"
    """

    if payment is None:
        return None

    try:
        return payment.finance_transaction
    except FinancialTransaction.DoesNotExist:
        return None
    except AttributeError:
        return None


# =============================================================================
# GENERAL VALIDATION HELPERS
# =============================================================================

def _ensure_positive_amount(amount, field_name="amount"):
    """
    Ensure an amount is a valid positive monetary value.
    """

    try:
        value = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(
            {field_name: "Enter a valid monetary amount."}
        )

    if value <= ZERO:
        raise ValidationError(
            {field_name: "Amount must be greater than zero."}
        )

    return value.quantize(MONEY_PRECISION)


def _ensure_non_negative_amount(amount, field_name="amount"):
    """
    Ensure an amount is zero or greater.
    """

    try:
        value = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(
            {field_name: "Enter a valid monetary amount."}
        )

    if value < ZERO:
        raise ValidationError(
            {field_name: "Amount cannot be negative."}
        )

    return value.quantize(MONEY_PRECISION)


def _validate_financial_category(
    category,
    transaction_type=None,
):
    """
    Validate that a financial category exists, is active and,
    when transaction_type is supplied, belongs to the correct type.
    """

    if category is None:
        raise ValidationError(
            {"category": "A financial category is required."}
        )

    if not category.is_active:
        raise ValidationError(
            {
                "category": (
                    "The selected financial category is inactive."
                )
            }
        )

    if transaction_type is not None:
        expected_type = _enum_value(transaction_type)
        actual_type = _enum_value(category.category_type)

        if actual_type != expected_type:
            raise ValidationError(
                {
                    "category": (
                        "The selected category does not belong "
                        "to the selected transaction type."
                    )
                }
            )

    return category


def _validate_transaction_type(transaction_type):
    """
    Validate FinancialTransaction transaction type.
    """

    valid_values = {
        _enum_value(choice.value)
        for choice in FinancialTransaction.TransactionType
    }

    value = _enum_value(transaction_type)

    if value not in valid_values:
        raise ValidationError(
            {
                "transaction_type": (
                    "Invalid financial transaction type."
                )
            }
        )

    return value


def _validate_transaction_status(status):
    """
    Validate FinancialTransaction status.
    """

    valid_values = {
        _enum_value(choice.value)
        for choice in FinancialTransaction.Status
    }

    value = _enum_value(status)

    if value not in valid_values:
        raise ValidationError(
            {
                "status": (
                    "Invalid financial transaction status."
                )
            }
        )

    return value


def _validate_expense_status(status):
    """
    Validate Expense status.
    """

    valid_values = {
        _enum_value(choice.value)
        for choice in Expense.Status
    }

    value = _enum_value(status)

    if value not in valid_values:
        raise ValidationError(
            {
                "status": (
                    "Invalid expense status."
                )
            }
        )

    return value


# =============================================================================
# AUDIT LOGGING
# =============================================================================

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
    Create an immutable financial audit log.

    All Finance mutations should create audit records through
    this helper.
    """

    return FinancialAuditLog.objects.create(
        user=user,
        action=action,
        description=description,
        transaction=transaction,
        expense=expense,
        reconciliation=reconciliation,
        category=category,
        old_values=old_values,
        new_values=new_values,
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

    if not name or not name.strip():
        raise ValidationError(
            {"name": "Category name is required."}
        )

    name = name.strip()

    valid_types = {
        _enum_value(choice.value)
        for choice in FinancialCategory.CategoryType
    }

    category_type = _enum_value(category_type)

    if category_type not in valid_types:
        raise ValidationError(
            {
                "category_type": (
                    "Invalid financial category type."
                )
            }
        )

    if FinancialCategory.objects.filter(
        name__iexact=name,
        category_type=category_type,
    ).exists():
        raise ValidationError(
            {
                "name": (
                    "A category with this name already exists "
                    "for this category type."
                )
            }
        )

    category = FinancialCategory.objects.create(
        name=name,
        category_type=category_type,
        description=description or "",
        is_active=is_active,
        is_system=is_system,
    )

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

    Category type and system status are intentionally immutable
    through this service.
    """

    if category is None:
        raise ValidationError(
            "Financial category is required."
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
                {"name": "Category name is required."}
            )

        duplicate = (
            FinancialCategory.objects
            .filter(
                name__iexact=name,
                category_type=category.category_type,
            )
            .exclude(pk=category.pk)
            .exists()
        )

        if duplicate:
            raise ValidationError(
                {
                    "name": (
                        "A category with this name already "
                        "exists for this category type."
                    )
                }
            )

        category.name = name

    if description is not None:
        category.description = description

    if is_active is not None:
        if category.is_system and not is_active:
            raise ValidationError(
                "System financial categories cannot be deactivated."
            )

        category.is_active = is_active

    category.save()

    new_values = {
        "name": category.name,
        "description": category.description,
        "is_active": category.is_active,
    }

    _audit(
        user=user,
        action=FinancialAuditLog.Action.UPDATED,
        category=category,
        description=(
            f"Financial category '{category.name}' "
            f"was updated."
        ),
        old_values=old_values,
        new_values=new_values,
    )

    return category


@transaction.atomic
def deactivate_category(*, user, category):
    """
    Deactivate a financial category.
    """

    if category is None:
        raise ValidationError(
            "Financial category is required."
        )

    if category.is_system:
        raise ValidationError(
            "System financial categories cannot be deactivated."
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
def activate_category(*, user, category):
    """
    Activate a financial category.
    """

    if category is None:
        raise ValidationError(
            "Financial category is required."
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
def toggle_category(*, user, category):
    """
    Toggle a financial category's active state.
    """

    if category is None:
        raise ValidationError(
            "Financial category is required."
        )

    if category.is_system:
        raise ValidationError(
            "System financial categories cannot be toggled."
        )

    if category.is_active:
        return deactivate_category(
            user=user,
            category=category,
        )

    return activate_category(
        user=user,
        category=category,
    )


# =============================================================================
# FINANCIAL TRANSACTION SERVICES
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
    status=None,
    reference="",
    member=None,
    payment=None,
    transaction_date=None,
    notes="",
):
    """
    Create a FinancialTransaction.

    POSTED transactions affect accounting.

    DRAFT transactions do not.

    VOIDED transactions do not.
    """

    transaction_type = _validate_transaction_type(
        transaction_type
    )

    if status is None:
        status = FinancialTransaction.Status.DRAFT

    status = _validate_transaction_status(status)

    amount = _ensure_positive_amount(amount)

    category = _validate_financial_category(
        category,
        transaction_type,
    )

    # ---------------------------------------------------------
    # Payment validation
    # ---------------------------------------------------------

    if payment is not None:

        if transaction_type != (
            _enum_value(
                FinancialTransaction.TransactionType.INCOME
            )
        ):
            raise ValidationError(
                "Payments can only be linked to income transactions."
            )

        if not _is_completed_payment(payment):
            raise ValidationError(
                "Only completed payments can be recorded in Finance."
            )

        existing_transaction = (
            _get_payment_finance_transaction(payment)
        )

        if existing_transaction is not None:
            raise ValidationError(
                (
                    "This payment already has a Finance transaction: "
                    f"{existing_transaction.transaction_number}."
                )
            )

    # ---------------------------------------------------------
    # Posted transactions must have a valid posted state
    # ---------------------------------------------------------

    if status == FinancialTransaction.Status.POSTED:
        status = FinancialTransaction.Status.POSTED

    financial_transaction = FinancialTransaction.objects.create(
        transaction_type=transaction_type,
        category=category,
        amount=amount,
        description=description or "",
        payment_source=payment_source,
        status=status,
        reference=reference or "",
        member=member,
        payment=payment,
        transaction_date=transaction_date,
        notes=notes or "",
        recorded_by=user,
    )

    # ---------------------------------------------------------
    # Audit
    # ---------------------------------------------------------

    if (
        financial_transaction.status
        == FinancialTransaction.Status.POSTED
    ):
        audit_action = FinancialAuditLog.Action.POSTED

        audit_description = (
            f"Financial transaction "
            f"{financial_transaction.transaction_number} "
            f"was created and posted."
        )
    else:
        audit_action = FinancialAuditLog.Action.CREATED

        audit_description = (
            f"Financial transaction "
            f"{financial_transaction.transaction_number} "
            f"was created."
        )

    _audit(
        user=user,
        action=audit_action,
        transaction=financial_transaction,
        description=audit_description,
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
def update_transaction(
    *,
    user,
    financial_transaction,
    category=None,
    amount=None,
    description=None,
    payment_source=None,
    reference=None,
    transaction_date=None,
    notes=None,
):
    """
    Update a financial transaction.

    Posted and voided transactions cannot be edited through
    this service because doing so would compromise the audit trail.
    """

    if financial_transaction is None:
        raise ValidationError(
            "Financial transaction is required."
        )

    if financial_transaction.status in {
        FinancialTransaction.Status.POSTED,
        FinancialTransaction.Status.VOIDED,
    }:
        raise ValidationError(
            "Posted or voided transactions cannot be edited."
        )

    old_values = {
        "category": financial_transaction.category.name,
        "amount": str(financial_transaction.amount),
        "description": financial_transaction.description,
        "payment_source": financial_transaction.payment_source,
        "reference": financial_transaction.reference,
        "transaction_date": (
            str(financial_transaction.transaction_date)
            if financial_transaction.transaction_date
            else None
        ),
        "notes": financial_transaction.notes,
    }

    if category is not None:
        financial_transaction.category = (
            _validate_financial_category(
                category,
                financial_transaction.transaction_type,
            )
        )

    if amount is not None:
        financial_transaction.amount = (
            _ensure_positive_amount(amount)
        )

    if description is not None:
        financial_transaction.description = description

    if payment_source is not None:
        financial_transaction.payment_source = payment_source

    if reference is not None:
        financial_transaction.reference = reference

    if transaction_date is not None:
        financial_transaction.transaction_date = transaction_date

    if notes is not None:
        financial_transaction.notes = notes

    financial_transaction.save()

    new_values = {
        "category": financial_transaction.category.name,
        "amount": str(financial_transaction.amount),
        "description": financial_transaction.description,
        "payment_source": financial_transaction.payment_source,
        "reference": financial_transaction.reference,
        "transaction_date": (
            str(financial_transaction.transaction_date)
            if financial_transaction.transaction_date
            else None
        ),
        "notes": financial_transaction.notes,
    }

    _audit(
        user=user,
        action=FinancialAuditLog.Action.UPDATED,
        transaction=financial_transaction,
        description=(
            f"Financial transaction "
            f"{financial_transaction.transaction_number} "
            f"was updated."
        ),
        old_values=old_values,
        new_values=new_values,
    )

    return financial_transaction


@transaction.atomic
def create_income(
    *,
    user,
    category,
    amount,
    description,
    payment_source,
    member=None,
    reference="",
    payment=None,
    transaction_date=None,
    notes="",
    post=True,
):
    """
    Create an income transaction.
    """

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
        status=status,
        reference=reference,
        member=member,
        payment=payment,
        transaction_date=transaction_date,
        notes=notes,
    )


@transaction.atomic
def create_expense_transaction(
    *,
    user,
    category,
    amount,
    description,
    payment_source,
    reference="",
    member=None,
    transaction_date=None,
    notes="",
    post=False,
    expense=None,
):
    """
    Create an expense ledger transaction.

    Normally called only when an Expense becomes PAID.
    """

    status = (
        FinancialTransaction.Status.POSTED
        if post
        else FinancialTransaction.Status.DRAFT
    )

    financial_transaction = create_transaction(
        user=user,
        transaction_type=(
            FinancialTransaction.TransactionType.EXPENSE
        ),
        category=category,
        amount=amount,
        description=description,
        payment_source=payment_source,
        status=status,
        reference=reference,
        member=member,
        transaction_date=transaction_date,
        notes=notes,
    )

    if expense is not None:
        expense.transaction = financial_transaction
        expense.save(
            update_fields=[
                "transaction",
                "updated_at",
            ]
        )

    return financial_transaction


@transaction.atomic
def post_transaction(
    *,
    user,
    financial_transaction,
):
    """
    Post a draft financial transaction.
    """

    if financial_transaction is None:
        raise ValidationError(
            "Financial transaction is required."
        )

    if financial_transaction.status == (
        FinancialTransaction.Status.VOIDED
    ):
        raise ValidationError(
            "A voided transaction cannot be posted."
        )

    if financial_transaction.status == (
        FinancialTransaction.Status.POSTED
    ):
        return financial_transaction

    old_status = financial_transaction.status

    financial_transaction.status = (
        FinancialTransaction.Status.POSTED
    )

    financial_transaction.posted_at = timezone.now()

    financial_transaction.save()

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

    A posted transaction may be voided. Once voided it no longer
    affects the accounting balance.
    """

    if financial_transaction is None:
        raise ValidationError(
            "Financial transaction is required."
        )

    if financial_transaction.status == (
        FinancialTransaction.Status.VOIDED
    ):
        return financial_transaction

    old_status = financial_transaction.status

    financial_transaction.status = (
        FinancialTransaction.Status.VOIDED
    )

    financial_transaction.save()

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
    payee,
    payment_source,
    payment_reference="",
    expense_date=None,
    receipt=None,
    notes="",
):
    """
    Create a new expense in DRAFT status.

    IMPORTANT:

        Creating an expense does NOT affect the accounting balance.
    """

    amount = _ensure_positive_amount(amount)

    if not title or not title.strip():
        raise ValidationError(
            {"title": "Expense title is required."}
        )

    if not description or not description.strip():
        raise ValidationError(
            {"description": "Expense description is required."}
        )

    category = _validate_financial_category(
        category,
        FinancialCategory.CategoryType.EXPENSE,
    )

    expense = Expense.objects.create(
        category=category,
        amount=amount,
        title=title.strip(),
        description=description.strip(),
        payee=payee or "",
        payment_source=payment_source,
        payment_reference=payment_reference or "",
        expense_date=expense_date,
        receipt=receipt,
        notes=notes or "",
        status=Expense.Status.DRAFT,

        # IMPORTANT:
        # The Expense model uses recorded_by.
        recorded_by=user,
    )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.CREATED,
        expense=expense,
        description=(
            f"Expense {expense.expense_number} "
            f"was created."
        ),
        new_values={
            "amount": str(expense.amount),
            "title": expense.title,
            "category": category.name,
            "payee": expense.payee,
            "payment_source": expense.payment_source,
            "payment_reference": expense.payment_reference,
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
    payment_reference=None,
    expense_date=None,
    receipt=None,
    notes=None,
):
    """
    Update an expense.

    PAID and VOIDED expenses are immutable.
    """

    if expense is None:
        raise ValidationError(
            "Expense is required."
        )

    if expense.status in {
        Expense.Status.PAID,
        Expense.Status.VOIDED,
    }:
        raise ValidationError(
            "Paid or voided expenses cannot be edited."
        )

    old_values = {
        "category": expense.category.name,
        "amount": str(expense.amount),
        "title": expense.title,
        "description": expense.description,
        "payee": expense.payee,
        "payment_source": expense.payment_source,
        "payment_reference": expense.payment_reference,
        "expense_date": (
            str(expense.expense_date)
            if expense.expense_date
            else None
        ),
        "notes": expense.notes,
    }

    if category is not None:
        expense.category = _validate_financial_category(
            category,
            FinancialCategory.CategoryType.EXPENSE,
        )

    if amount is not None:
        expense.amount = _ensure_positive_amount(
            amount
        )

    if title is not None:
        if not title.strip():
            raise ValidationError(
                {"title": "Expense title is required."}
            )

        expense.title = title.strip()

    if description is not None:
        if not description.strip():
            raise ValidationError(
                {
                    "description": (
                        "Expense description is required."
                    )
                }
            )

        expense.description = description.strip()

    if payee is not None:
        expense.payee = payee

    if payment_source is not None:
        expense.payment_source = payment_source

    if payment_reference is not None:
        expense.payment_reference = payment_reference

    if expense_date is not None:
        expense.expense_date = expense_date

    if receipt is not None:
        expense.receipt = receipt

    if notes is not None:
        expense.notes = notes

    expense.save()

    new_values = {
        "category": expense.category.name,
        "amount": str(expense.amount),
        "title": expense.title,
        "description": expense.description,
        "payee": expense.payee,
        "payment_source": expense.payment_source,
        "payment_reference": expense.payment_reference,
        "expense_date": (
            str(expense.expense_date)
            if expense.expense_date
            else None
        ),
        "notes": expense.notes,
    }

    _audit(
        user=user,
        action=FinancialAuditLog.Action.UPDATED,
        expense=expense,
        description=(
            f"Expense {expense.expense_number} "
            f"was updated."
        ),
        old_values=old_values,
        new_values=new_values,
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

    if expense is None:
        raise ValidationError(
            "Expense is required."
        )

    if expense.status != Expense.Status.DRAFT:
        raise ValidationError(
            "Only draft expenses can be submitted."
        )

    old_status = expense.status

    expense.status = Expense.Status.SUBMITTED

    if hasattr(expense, "submitted_by_id"):
        expense.submitted_by = user

    if hasattr(expense, "submitted_at"):
        expense.submitted_at = timezone.now()

    expense.save()

    _audit(
        user=user,
        action=FinancialAuditLog.Action.SUBMITTED,
        expense=expense,
        description=(
            f"Expense {expense.expense_number} "
            f"was submitted for approval."
        ),
        old_values={
            "status": old_status,
        },
        new_values={
            "status": expense.status,
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

    Approval does not affect the accounting balance.
    """

    if expense is None:
        raise ValidationError(
            "Expense is required."
        )

    if expense.status != Expense.Status.SUBMITTED:
        raise ValidationError(
            "Only submitted expenses can be approved."
        )

    old_status = expense.status

    expense.status = Expense.Status.APPROVED

    if hasattr(expense, "approved_by_id"):
        expense.approved_by = user

    if hasattr(expense, "approved_at"):
        expense.approved_at = timezone.now()

    expense.save()

    _audit(
        user=user,
        action=FinancialAuditLog.Action.APPROVED,
        expense=expense,
        description=(
            f"Expense {expense.expense_number} "
            f"was approved."
        ),
        old_values={
            "status": old_status,
        },
        new_values={
            "status": expense.status,
        },
    )

    return expense


@transaction.atomic
def reject_expense(
    *,
    user,
    expense,
    reason="",
):
    """
    Reject a submitted or approved expense.
    """

    if expense is None:
        raise ValidationError(
            "Expense is required."
        )

    if expense.status not in {
        Expense.Status.SUBMITTED,
        Expense.Status.APPROVED,
    }:
        raise ValidationError(
            (
                "Only submitted or approved expenses "
                "can be rejected."
            )
        )

    if not reason or not reason.strip():
        raise ValidationError(
            {
                "reason": (
                    "A rejection reason is required."
                )
            }
        )

    old_status = expense.status

    expense.status = Expense.Status.REJECTED

    if hasattr(expense, "rejected_by_id"):
        expense.rejected_by = user

    if hasattr(expense, "rejected_at"):
        expense.rejected_at = timezone.now()

    if hasattr(expense, "rejection_reason"):
        expense.rejection_reason = reason.strip()

    expense.save()

    _audit(
        user=user,
        action=FinancialAuditLog.Action.REJECTED,
        expense=expense,
        description=(
            f"Expense {expense.expense_number} "
            f"was rejected."
        ),
        old_values={
            "status": old_status,
        },
        new_values={
            "status": expense.status,
            "reason": reason.strip(),
        },
    )

    return expense


@transaction.atomic
def pay_expense(
    *,
    user,
    expense,
):
    """
    Mark an APPROVED expense as PAID and create its
    corresponding POSTED expense transaction.

    This is the exact point at which the expense affects
    the accounting balance.
    """

    if expense is None:
        raise ValidationError(
            "Expense is required."
        )

    if expense.status != Expense.Status.APPROVED:
        raise ValidationError(
            "Only approved expenses can be paid."
        )

    if not expense.payment_reference:
        raise ValidationError(
            {
                "payment_reference": (
                    "Payment reference is required before "
                    "an expense can be paid."
                )
            }
        )

    if expense.transaction_id:
        raise ValidationError(
            "This expense already has a financial transaction."
        )

    old_status = expense.status

    expense.status = Expense.Status.PAID

    if hasattr(expense, "paid_by_id"):
        expense.paid_by = user

    if hasattr(expense, "paid_at"):
        expense.paid_at = timezone.now()

    expense.save()

    financial_transaction = create_expense_transaction(
        user=user,
        category=expense.category,
        amount=expense.amount,
        description=(
            f"Expense payment: {expense.title}"
        ),
        payment_source=expense.payment_source,
        reference=expense.payment_reference,
        transaction_date=expense.expense_date,
        notes=expense.notes,
        post=True,
        expense=expense,
    )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.PAID,
        expense=expense,
        transaction=financial_transaction,
        description=(
            f"Expense {expense.expense_number} "
            f"was paid and posted to Finance."
        ),
        old_values={
            "status": old_status,
        },
        new_values={
            "status": expense.status,
            "transaction": (
                financial_transaction.transaction_number
            ),
        },
    )

    return expense


@transaction.atomic
def void_expense(
    *,
    user,
    expense,
    reason="",
):
    """
    Void an expense.

    If the expense already has a financial transaction,
    the transaction is also voided.
    """

    if expense is None:
        raise ValidationError(
            "Expense is required."
        )

    if expense.status == Expense.Status.VOIDED:
        return expense

    if not reason or not reason.strip():
        raise ValidationError(
            {
                "reason": (
                    "A reason is required to void an expense."
                )
            }
        )

    old_status = expense.status

    expense.status = Expense.Status.VOIDED

    if hasattr(expense, "voided_by_id"):
        expense.voided_by = user

    if hasattr(expense, "voided_at"):
        expense.voided_at = timezone.now()

    if hasattr(expense, "void_reason"):
        expense.void_reason = reason.strip()

    expense.save()

    if expense.transaction_id:
        financial_transaction = expense.transaction

        if financial_transaction.status != (
            FinancialTransaction.Status.VOIDED
        ):
            void_transaction(
                user=user,
                financial_transaction=financial_transaction,
            )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.VOIDED,
        expense=expense,
        description=(
            f"Expense {expense.expense_number} "
            f"was voided."
        ),
        old_values={
            "status": old_status,
        },
        new_values={
            "status": expense.status,
            "reason": reason.strip(),
        },
    )

    return expense


# =============================================================================
# PAYMENT → FINANCE INTEGRATION
# =============================================================================

@transaction.atomic
def record_completed_payment(
    *,
    user,
    payment,
    category,
    description=None,
    transaction_date=None,
    notes="",
):
    """
    Record one COMPLETED Payment as one Finance income transaction.

    The operation is idempotent.

    If the payment already has a Finance transaction, the
    existing transaction is returned.
    """

    if payment is None:
        raise ValidationError(
            "Payment is required."
        )

    if not _is_completed_payment(payment):
        raise ValidationError(
            "Only completed payments can be recorded in Finance."
        )

    existing_transaction = (
        _get_payment_finance_transaction(payment)
    )

    if existing_transaction is not None:
        return existing_transaction

    category = _validate_financial_category(
        category,
        FinancialCategory.CategoryType.INCOME,
    )

    amount = _ensure_positive_amount(
        payment.amount
    )

    member = getattr(
        payment,
        "member",
        None,
    )

    reference = getattr(
        payment,
        "mpesa_receipt_number",
        "",
    )

    if not reference:
        reference = getattr(
            payment,
            "checkout_request_id",
            "",
        )

    if description is None:
        payment_type = getattr(
            payment,
            "payment_type",
            "",
        )

        description = (
            "Income received from "
            f"{_enum_value(payment_type) or 'payment'}."
        )

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

    return financial_transaction


@transaction.atomic
def sync_completed_payment_to_finance(
    *,
    user,
    payment,
    category,
    description=None,
    transaction_date=None,
    notes="",
):
    """
    Synchronize a completed payment into Finance.

    Safe to call repeatedly.
    """

    if payment is None:
        raise ValidationError(
            "Payment is required."
        )

    existing_transaction = (
        _get_payment_finance_transaction(payment)
    )

    if existing_transaction is not None:
        return existing_transaction

    return record_completed_payment(
        user=user,
        payment=payment,
        category=category,
        description=description,
        transaction_date=transaction_date,
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
    statement_reference,
    period_start,
    period_end,
    system_income=ZERO,
    system_expenses=ZERO,
    external_income=ZERO,
    external_expenses=ZERO,
    file=None,
    notes="",
):
    """
    Create a financial reconciliation record.
    """

    if period_start is None:
        raise ValidationError(
            {"period_start": "Start date is required."}
        )

    if period_end is None:
        raise ValidationError(
            {"period_end": "End date is required."}
        )

    if period_start > period_end:
        raise ValidationError(
            {
                "period_start": (
                    "Reconciliation start date cannot "
                    "be after end date."
                )
            }
        )

    system_income = _ensure_non_negative_amount(
        system_income,
        "system_income",
    )

    system_expenses = _ensure_non_negative_amount(
        system_expenses,
        "system_expenses",
    )

    external_income = _ensure_non_negative_amount(
        external_income,
        "external_income",
    )

    external_expenses = _ensure_non_negative_amount(
        external_expenses,
        "external_expenses",
    )

    reconciliation = FinancialReconciliation.objects.create(
        source=source,
        statement_reference=statement_reference or "",
        period_start=period_start,
        period_end=period_end,
        system_income=system_income,
        system_expenses=system_expenses,
        external_income=external_income,
        external_expenses=external_expenses,
        prepared_by=user,
        file=file,
        notes=notes or "",
        status=FinancialReconciliation.Status.DRAFT,
    )

    _audit(
        user=user,
        action=FinancialAuditLog.Action.CREATED,
        reconciliation=reconciliation,
        description=(
            f"Financial reconciliation "
            f"{reconciliation.pk} was created."
        ),
        new_values={
            "source": reconciliation.source,
            "statement_reference": (
                reconciliation.statement_reference
            ),
            "period_start": str(
                reconciliation.period_start
            ),
            "period_end": str(
                reconciliation.period_end
            ),
            "system_income": str(
                reconciliation.system_income
            ),
            "system_expenses": str(
                reconciliation.system_expenses
            ),
            "external_income": str(
                reconciliation.external_income
            ),
            "external_expenses": str(
                reconciliation.external_expenses
            ),
        },
    )

    return reconciliation


@transaction.atomic
def update_reconciliation(
    *,
    user,
    reconciliation,
    source=None,
    statement_reference=None,
    period_start=None,
    period_end=None,
    system_income=None,
    system_expenses=None,
    external_income=None,
    external_expenses=None,
    file=None,
    notes=None,
):
    """
    Update a draft or in-progress reconciliation.

    Completed/reconciled records should not be silently changed.
    """

    if reconciliation is None:
        raise ValidationError(
            "Reconciliation is required."
        )

    if reconciliation.status in {
        FinancialReconciliation.Status.RECONCILED,
    }:
        raise ValidationError(
            "A reconciled record cannot be edited."
        )

    old_values = {
        "source": reconciliation.source,
        "statement_reference": (
            reconciliation.statement_reference
        ),
        "period_start": str(
            reconciliation.period_start
        ),
        "period_end": str(
            reconciliation.period_end
        ),
        "system_income": str(
            reconciliation.system_income
        ),
        "system_expenses": str(
            reconciliation.system_expenses
        ),
        "external_income": str(
            reconciliation.external_income
        ),
        "external_expenses": str(
            reconciliation.external_expenses
        ),
        "notes": reconciliation.notes,
    }

    if source is not None:
        reconciliation.source = source

    if statement_reference is not None:
        reconciliation.statement_reference = (
            statement_reference
        )

    if period_start is not None:
        reconciliation.period_start = period_start

    if period_end is not None:
        reconciliation.period_end = period_end

    if (
        reconciliation.period_start
        and reconciliation.period_end
        and reconciliation.period_start
        > reconciliation.period_end
    ):
        raise ValidationError(
            {
                "period_start": (
                    "Reconciliation start date cannot "
                    "be after end date."
                )
            }
        )

    if system_income is not None:
        reconciliation.system_income = (
            _ensure_non_negative_amount(
                system_income,
                "system_income",
            )
        )

    if system_expenses is not None:
        reconciliation.system_expenses = (
            _ensure_non_negative_amount(
                system_expenses,
                "system_expenses",
            )
        )

    if external_income is not None:
        reconciliation.external_income = (
            _ensure_non_negative_amount(
                external_income,
                "external_income",
            )
        )

    if external_expenses is not None:
        reconciliation.external_expenses = (
            _ensure_non_negative_amount(
                external_expenses,
                "external_expenses",
            )
        )

    if file is not None:
        reconciliation.file = file

    if notes is not None:
        reconciliation.notes = notes

    reconciliation.save()

    new_values = {
        "source": reconciliation.source,
        "statement_reference": (
            reconciliation.statement_reference
        ),
        "period_start": str(
            reconciliation.period_start
        ),
        "period_end": str(
            reconciliation.period_end
        ),
        "system_income": str(
            reconciliation.system_income
        ),
        "system_expenses": str(
            reconciliation.system_expenses
        ),
        "external_income": str(
            reconciliation.external_income
        ),
        "external_expenses": str(
            reconciliation.external_expenses
        ),
        "notes": reconciliation.notes,
    }

    _audit(
        user=user,
        action=FinancialAuditLog.Action.UPDATED,
        reconciliation=reconciliation,
        description=(
            f"Financial reconciliation "
            f"{reconciliation.pk} was updated."
        ),
        old_values=old_values,
        new_values=new_values,
    )

    return reconciliation


@transaction.atomic
def reconcile_finance(
    *,
    user,
    reconciliation,
):
    """
    Process a reconciliation.

    Matching figures produce RECONCILED.

    Non-matching figures produce DISCREPANCY.
    """

    if reconciliation is None:
        raise ValidationError(
            "Reconciliation is required."
        )

    system_net = (
        reconciliation.system_income
        - reconciliation.system_expenses
    ).quantize(MONEY_PRECISION)

    external_net = (
        reconciliation.external_income
        - reconciliation.external_expenses
    ).quantize(MONEY_PRECISION)

    old_status = reconciliation.status

    if system_net == external_net:
        reconciliation.status = (
            FinancialReconciliation.Status.RECONCILED
        )
    else:
        reconciliation.status = (
            FinancialReconciliation.Status.DISCREPANCY
        )

    if hasattr(reconciliation, "reconciled_by_id"):
        reconciliation.reconciled_by = user

    if hasattr(reconciliation, "reconciled_at"):
        reconciliation.reconciled_at = timezone.now()

    reconciliation.save()

    _audit(
        user=user,
        action=FinancialAuditLog.Action.RECONCILED,
        reconciliation=reconciliation,
        description=(
            f"Financial reconciliation "
            f"{reconciliation.pk} was processed."
        ),
        old_values={
            "status": old_status,
            "system_net": str(system_net),
            "external_net": str(external_net),
        },
        new_values={
            "status": reconciliation.status,
            "system_net": str(system_net),
            "external_net": str(external_net),
        },
    )

    return reconciliation


# =============================================================================
# FINANCIAL REPORTING
# =============================================================================

def _money(value):
    """
    Normalize a database aggregate value to Decimal(0.00).
    """

    return Decimal(
        str(value or ZERO)
    ).quantize(MONEY_PRECISION)


def get_financial_totals():
    """
    Return authoritative accounting totals.

    ONLY POSTED transactions affect accounting.

        Posted Income
            -
        Posted Expenses
            =
        Available Balance
    """

    posted_transactions = (
        FinancialTransaction.objects
        .filter(
            status=FinancialTransaction.Status.POSTED,
        )
        .values("transaction_type")
        .annotate(
            total=Sum("amount")
        )
    )

    income = ZERO
    expenses = ZERO

    for row in posted_transactions:
        amount = _money(row["total"])

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

    return {
        "income": income,
        "expenses": expenses,
        "balance": (
            income - expenses
        ).quantize(MONEY_PRECISION),
    }


def get_financial_balance():
    """
    Return current available Finance balance.
    """

    return get_financial_totals()["balance"]


def get_income_totals():
    """
    Return income statistics.

    total_income:
        All income transaction amounts.

    posted_income:
        Only posted income.

    income_records:
        Number of income transaction records.
    """

    queryset = FinancialTransaction.objects.filter(
        transaction_type=(
            FinancialTransaction.TransactionType.INCOME
        )
    )

    total_income = _money(
        queryset.aggregate(
            total=Sum("amount")
        ).get("total")
    )

    posted_income = _money(
        queryset.filter(
            status=FinancialTransaction.Status.POSTED
        )
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
    )

    return {
        "total_income": total_income,
        "posted_income": posted_income,
        "income_records": queryset.count(),
    }


def get_expense_totals():
    """
    Return expense workflow and accounting statistics.

    total_expenses:
        All non-voided expense requests.

    paid_expenses:
        PAID expense requests.

    posted_expenses:
        POSTED accounting ledger expenses.

    pending_expenses:
        DRAFT + SUBMITTED + APPROVED.

    rejected_expenses:
        REJECTED expense count.

    paid_count:
        Number of PAID expenses.
    """

    expense_queryset = Expense.objects.exclude(
        status=Expense.Status.VOIDED
    )

    total_expenses = _money(
        expense_queryset.aggregate(
            total=Sum("amount")
        ).get("total")
    )

    paid_expenses = _money(
        expense_queryset.filter(
            status=Expense.Status.PAID
        )
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
    )

    posted_expenses = _money(
        FinancialTransaction.objects.filter(
            transaction_type=(
                FinancialTransaction.TransactionType.EXPENSE
            ),
            status=FinancialTransaction.Status.POSTED,
        )
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
    )

    pending_expenses = expense_queryset.filter(
        status__in=[
            Expense.Status.DRAFT,
            Expense.Status.SUBMITTED,
            Expense.Status.APPROVED,
        ]
    ).count()

    rejected_expenses = expense_queryset.filter(
        status=Expense.Status.REJECTED
    ).count()

    paid_count = expense_queryset.filter(
        status=Expense.Status.PAID
    ).count()

    return {
        "total_expenses": total_expenses,
        "paid_expenses": paid_expenses,
        "posted_expenses": posted_expenses,
        "pending_expenses": pending_expenses,
        "rejected_expenses": rejected_expenses,
        "paid_count": paid_count,
    }


def get_category_totals():
    """
    Return authoritative category statistics.
    """

    queryset = FinancialCategory.objects.all()

    return {
        "total_categories": queryset.count(),

        "income_categories": queryset.filter(
            category_type=(
                FinancialCategory.CategoryType.INCOME
            )
        ).count(),

        "expense_categories": queryset.filter(
            category_type=(
                FinancialCategory.CategoryType.EXPENSE
            )
        ).count(),

        "active_categories": queryset.filter(
            is_active=True
        ).count(),

        "inactive_categories": queryset.filter(
            is_active=False
        ).count(),
    }


def get_audit_log_totals():
    """
    Return financial audit-log statistics.
    """

    queryset = FinancialAuditLog.objects.all()

    workflow_actions = [
        FinancialAuditLog.Action.SUBMITTED,
        FinancialAuditLog.Action.APPROVED,
        FinancialAuditLog.Action.REJECTED,
        FinancialAuditLog.Action.PAID,
        FinancialAuditLog.Action.POSTED,
        FinancialAuditLog.Action.VOIDED,
        FinancialAuditLog.Action.RECONCILED,
    ]

    return {
        "total_logs": queryset.count(),

        "created_logs": queryset.filter(
            action=FinancialAuditLog.Action.CREATED
        ).count(),

        "updated_logs": queryset.filter(
            action=FinancialAuditLog.Action.UPDATED
        ).count(),

        "workflow_actions": queryset.filter(
            action__in=workflow_actions
        ).count(),
    }


def get_finance_dashboard_stats():
    """
    Return all authoritative statistics required by the
    Finance dashboard.

    This is the primary service consumed by the dashboard view.
    """

    financial_totals = get_financial_totals()
    income_totals = get_income_totals()
    expense_totals = get_expense_totals()
    category_totals = get_category_totals()

    return {
        # ---------------------------------------------------------
        # ACCOUNTING
        # ---------------------------------------------------------

        "available_balance": financial_totals["balance"],

        "posted_income": financial_totals["income"],

        "posted_expenses": financial_totals["expenses"],

        # ---------------------------------------------------------
        # INCOME
        # ---------------------------------------------------------

        "total_income": income_totals["total_income"],

        "income_records": income_totals["income_records"],

        # ---------------------------------------------------------
        # EXPENSE WORKFLOW
        # ---------------------------------------------------------

        "total_expenses": expense_totals["total_expenses"],

        "paid_expenses": expense_totals["paid_expenses"],

        "pending_expenses": expense_totals["pending_expenses"],

        "rejected_expenses": expense_totals["rejected_expenses"],

        "paid_count": expense_totals["paid_count"],

        # ---------------------------------------------------------
        # CATEGORIES
        # ---------------------------------------------------------

        "total_categories": (
            category_totals["total_categories"]
        ),

        "income_categories": (
            category_totals["income_categories"]
        ),

        "expense_categories": (
            category_totals["expense_categories"]
        ),

        "active_categories": (
            category_totals["active_categories"]
        ),

        "inactive_categories": (
            category_totals["inactive_categories"]
        ),
    }


# =============================================================================
# TRANSACTION REPORTING
# =============================================================================

def get_transaction_totals(queryset=None):
    """
    Calculate transaction totals for an optional queryset.

    If no queryset is supplied, all Finance transactions are used.

    This keeps transaction-page calculations out of views.
    """

    if queryset is None:
        queryset = FinancialTransaction.objects.all()

    income_queryset = queryset.filter(
        transaction_type=(
            FinancialTransaction.TransactionType.INCOME
        )
    )

    expense_queryset = queryset.filter(
        transaction_type=(
            FinancialTransaction.TransactionType.EXPENSE
        )
    )

    posted_queryset = queryset.filter(
        status=FinancialTransaction.Status.POSTED
    )

    posted_income = _money(
        posted_queryset.filter(
            transaction_type=(
                FinancialTransaction.TransactionType.INCOME
            )
        )
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
    )

    posted_expenses = _money(
        posted_queryset.filter(
            transaction_type=(
                FinancialTransaction.TransactionType.EXPENSE
            )
        )
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
    )

    return {
        "total_records": queryset.count(),

        "income_records": income_queryset.count(),

        "expense_records": expense_queryset.count(),

        "posted_records": posted_queryset.count(),

        "draft_records": queryset.filter(
            status=FinancialTransaction.Status.DRAFT
        ).count(),

        "voided_records": queryset.filter(
            status=FinancialTransaction.Status.VOIDED
        ).count(),

        "posted_income": posted_income,

        "posted_expenses": posted_expenses,

        "balance": (
            posted_income - posted_expenses
        ).quantize(MONEY_PRECISION),
    }


# =============================================================================
# AUDIT ACCESS
# =============================================================================

def get_audit_logs(
    *,
    transaction=None,
    expense=None,
    reconciliation=None,
    category=None,
    user=None,
    action=None,
):
    """
    Retrieve financial audit logs using optional filters.

    Read-only operation.
    """

    queryset = (
        FinancialAuditLog.objects
        .select_related(
            "user",
            "transaction",
            "expense",
            "reconciliation",
            "category",
        )
        .all()
    )

    if transaction is not None:
        queryset = queryset.filter(
            transaction=transaction
        )

    if expense is not None:
        queryset = queryset.filter(
            expense=expense
        )

    if reconciliation is not None:
        queryset = queryset.filter(
            reconciliation=reconciliation
        )

    if category is not None:
        queryset = queryset.filter(
            category=category
        )

    if user is not None:
        queryset = queryset.filter(
            user=user
        )

    if action is not None:
        queryset = queryset.filter(
            action=action
        )

    return queryset.order_by("-timestamp")