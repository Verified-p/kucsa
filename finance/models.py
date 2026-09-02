
# finance/models.py

"""
KUCSA Finance Models
====================

Core financial data models for the KUCSA Management System.

Architecture
------------

    Payments
        │
        │ COMPLETED payment
        ▼
    Finance
        │
        ▼
    FinancialTransaction
        │
        ├── Income
        └── Expense

Finance is responsible for:

    - Financial categories
    - Income
    - Expenses
    - Financial ledger
    - Reconciliation
    - Financial audit trail

The Payments application remains responsible for:

    - M-Pesa STK Push
    - Safaricom authentication
    - Safaricom callback
    - Payment verification
    - Payment status
    - M-Pesa receipt

IMPORTANT
---------

Finance never verifies M-Pesa payments.

Only a Payment whose status is COMPLETED may be
linked to a FinancialTransaction as income.

Financial balance is calculated from:

    POSTED INCOME - POSTED EXPENSES
"""


from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


# =========================================================
# CONSTANTS
# =========================================================

ZERO = Decimal("0.00")
MINIMUM_AMOUNT = Decimal("0.01")


# =========================================================
# FINANCIAL CATEGORY
# =========================================================

class FinancialCategory(models.Model):
    """
    Classifies financial transactions and expenses.
    """

    class CategoryType(models.TextChoices):
        INCOME = "INCOME", "Income"
        EXPENSE = "EXPENSE", "Expense"

    name = models.CharField(
        max_length=100,
        unique=True,
    )

    category_type = models.CharField(
        max_length=10,
        choices=CategoryType.choices,
    )

    description = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    is_system = models.BooleanField(
        default=False,
        help_text=(
            "System categories are protected from normal "
            "modification or deactivation."
        ),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "category_type",
            "name",
        ]

        indexes = [
            models.Index(
                fields=[
                    "category_type",
                    "is_active",
                ],
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()

        self.name = (self.name or "").strip()

        if not self.name:
            raise ValidationError({
                "name": "Category name cannot be empty.",
            })


# =========================================================
# FINANCIAL TRANSACTION
# =========================================================

class FinancialTransaction(models.Model):
    """
    Main KUCSA financial ledger.

    Transaction types:

        INCOME
        EXPENSE

    Transaction states:

        DRAFT
        POSTED
        VOIDED

    Only POSTED transactions affect the financial balance.
    """

    class TransactionType(models.TextChoices):
        INCOME = "INCOME", "Income"
        EXPENSE = "EXPENSE", "Expense"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        POSTED = "POSTED", "Posted"
        VOIDED = "VOIDED", "Voided"

    class PaymentSource(models.TextChoices):
        MPESA = "MPESA", "M-Pesa"
        CASH = "CASH", "Cash"
        BANK = "BANK", "Bank"
        OTHER = "OTHER", "Other"

    # -----------------------------------------------------
    # IDENTIFICATION
    # -----------------------------------------------------

    transaction_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        editable=False,
    )

    transaction_type = models.CharField(
        max_length=10,
        choices=TransactionType.choices,
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    # -----------------------------------------------------
    # CATEGORY
    # -----------------------------------------------------

    category = models.ForeignKey(
        FinancialCategory,
        on_delete=models.PROTECT,
        related_name="transactions",
    )

    # -----------------------------------------------------
    # MONEY
    # -----------------------------------------------------

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(MINIMUM_AMOUNT),
        ],
    )

    # -----------------------------------------------------
    # DESCRIPTION
    # -----------------------------------------------------

    description = models.CharField(
        max_length=255,
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
    )

    # -----------------------------------------------------
    # PAYMENT SOURCE
    # -----------------------------------------------------

    payment_source = models.CharField(
        max_length=10,
        choices=PaymentSource.choices,
        default=PaymentSource.MPESA,
    )

    # -----------------------------------------------------
    # ORIGINAL PAYMENT
    # -----------------------------------------------------

    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="finance_transaction",
        null=True,
        blank=True,
        help_text=(
            "Original completed payment when this "
            "transaction originated from Payments."
        ),
    )

    # -----------------------------------------------------
    # MEMBER
    # -----------------------------------------------------

    member = models.ForeignKey(
        "members.Member",
        on_delete=models.PROTECT,
        related_name="finance_transactions",
        null=True,
        blank=True,
    )

    # -----------------------------------------------------
    # USER
    # -----------------------------------------------------

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="finance_transactions_recorded",
    )

    # -----------------------------------------------------
    # DATES
    # -----------------------------------------------------

    transaction_date = models.DateTimeField(
        default=timezone.now,
    )

    posted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # -----------------------------------------------------
    # NOTES
    # -----------------------------------------------------

    notes = models.TextField(
        blank=True,
    )

    # -----------------------------------------------------
    # TIMESTAMPS
    # -----------------------------------------------------

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-transaction_date",
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "transaction_type",
                    "status",
                ],
            ),
            models.Index(
                fields=[
                    "transaction_date",
                ],
            ),
            models.Index(
                fields=[
                    "payment_source",
                ],
            ),
            models.Index(
                fields=[
                    "member",
                ],
            ),
            models.Index(
                fields=[
                    "category",
                    "transaction_date",
                ],
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="finance_transaction_amount_positive",
            ),
        ]

    def __str__(self):
        return (
            f"{self.transaction_number} - "
            f"{self.get_transaction_type_display()} - "
            f"KES {self.amount:,.2f}"
        )

    def clean(self):
        super().clean()

        errors = {}

        # -------------------------------------------------
        # AMOUNT
        # -------------------------------------------------

        if self.amount is not None and self.amount <= ZERO:
            errors["amount"] = (
                "Transaction amount must be greater than zero."
            )

        # -------------------------------------------------
        # CATEGORY
        #
        # IMPORTANT:
        # Use category_id instead of self.category.
        #
        # This prevents:
        #
        # RelatedObjectDoesNotExist:
        # FinancialTransaction has no category.
        # -------------------------------------------------

        if self.category_id:

            category = self.category

            if (
                self.transaction_type
                == self.TransactionType.INCOME
                and category.category_type
                != FinancialCategory.CategoryType.INCOME
            ):
                errors["category"] = (
                    "Income transactions must use "
                    "an income category."
                )

            elif (
                self.transaction_type
                == self.TransactionType.EXPENSE
                and category.category_type
                != FinancialCategory.CategoryType.EXPENSE
            ):
                errors["category"] = (
                    "Expense transactions must use "
                    "an expense category."
                )

        else:
            errors["category"] = (
                "A financial transaction must have a category."
            )

        # -------------------------------------------------
        # PAYMENT
        # -------------------------------------------------

        if self.payment_id:

            if (
                self.transaction_type
                != self.TransactionType.INCOME
            ):
                errors["payment"] = (
                    "A payment can only be linked "
                    "to an income transaction."
                )

            if (
                self.payment_source
                != self.PaymentSource.MPESA
            ):
                errors["payment_source"] = (
                    "A linked payment must use "
                    "M-Pesa as its payment source."
                )

            payment_status = getattr(
                self.payment,
                "status",
                None,
            )

            status_class = getattr(
                self.payment.__class__,
                "Status",
                None,
            )

            completed_status = (
                getattr(
                    status_class,
                    "COMPLETED",
                    None,
                )
                if status_class
                else None
            )

            if (
                completed_status is not None
                and payment_status != completed_status
            ):
                errors["payment"] = (
                    "Only completed payments can become "
                    "financial income."
                )

        # -------------------------------------------------
        # POSTING STATE
        # -------------------------------------------------

        if (
            self.status == self.Status.POSTED
            and self.posted_at is None
        ):
            errors["posted_at"] = (
                "A posted transaction must have "
                "a posting timestamp."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """
        Generate transaction number and maintain
        posting timestamp.

        Model validation is intentionally not forced here
        because some finance workflows construct related
        objects in stages.
        """

        if not self.transaction_number:
            date = timezone.now().strftime("%Y%m%d")
            code = uuid.uuid4().hex[:8].upper()

            self.transaction_number = (
                f"FIN-{date}-{code}"
            )

        if (
            self.status == self.Status.POSTED
            and self.posted_at is None
        ):
            self.posted_at = timezone.now()

        super().save(*args, **kwargs)

    # -----------------------------------------------------
    # PROPERTIES
    # -----------------------------------------------------

    @property
    def is_income(self):
        return (
            self.transaction_type
            == self.TransactionType.INCOME
        )

    @property
    def is_expense(self):
        return (
            self.transaction_type
            == self.TransactionType.EXPENSE
        )

    @property
    def is_draft(self):
        return self.status == self.Status.DRAFT

    @property
    def is_posted(self):
        return self.status == self.Status.POSTED

    @property
    def is_voided(self):
        return self.status == self.Status.VOIDED

    @property
    def affects_balance(self):
        return self.status == self.Status.POSTED

    @property
    def signed_amount(self):
        """
        Income  -> positive
        Expense -> negative
        Draft/voided -> zero
        """

        if not self.affects_balance:
            return ZERO

        if self.is_income:
            return self.amount

        if self.is_expense:
            return -self.amount

        return ZERO

    @property
    def amount_display(self):
        return f"KES {self.amount:,.2f}"


# =========================================================
# EXPENSE
# =========================================================

class Expense(models.Model):
    """
    Expense request and payment workflow.

    Normal workflow:

        DRAFT
          ↓
        SUBMITTED
          ↓
        APPROVED
          ↓
        PAID
          ↓
    FinancialTransaction

    Alternative terminal states:

        REJECTED
        VOIDED
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        PAID = "PAID", "Paid"
        VOIDED = "VOIDED", "Voided"

    # -----------------------------------------------------
    # IDENTIFICATION
    # -----------------------------------------------------

    expense_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        editable=False,
    )

    # -----------------------------------------------------
    # CATEGORY
    # -----------------------------------------------------

    category = models.ForeignKey(
        FinancialCategory,
        on_delete=models.PROTECT,
        related_name="expenses",
    )

    # -----------------------------------------------------
    # BASIC INFORMATION
    # -----------------------------------------------------

    title = models.CharField(
        max_length=200,
    )

    description = models.TextField(
        blank=True,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(MINIMUM_AMOUNT),
        ],
    )

    # -----------------------------------------------------
    # PAYEE
    # -----------------------------------------------------

    payee = models.CharField(
        max_length=200,
        blank=True,
    )

    # -----------------------------------------------------
    # PAYMENT
    # -----------------------------------------------------

    payment_source = models.CharField(
        max_length=10,
        choices=FinancialTransaction.PaymentSource.choices,
        default=FinancialTransaction.PaymentSource.MPESA,
    )

    payment_reference = models.CharField(
        max_length=100,
        blank=True,
    )

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    # -----------------------------------------------------
    # DATES
    # -----------------------------------------------------

    expense_date = models.DateTimeField(
        default=timezone.now,
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    voided_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # -----------------------------------------------------
    # USERS
    # -----------------------------------------------------

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expenses_recorded",
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expenses_submitted",
        null=True,
        blank=True,
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expenses_approved",
        null=True,
        blank=True,
    )

    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expenses_rejected",
        null=True,
        blank=True,
    )

    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expenses_paid",
        null=True,
        blank=True,
    )

    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="expenses_voided",
        null=True,
        blank=True,
    )

    # -----------------------------------------------------
    # REASONS
    # -----------------------------------------------------

    rejection_reason = models.TextField(
        blank=True,
    )

    void_reason = models.TextField(
        blank=True,
    )

    # -----------------------------------------------------
    # RECEIPT
    # -----------------------------------------------------

    receipt = models.FileField(
        upload_to="finance/receipts/%Y/%m/",
        null=True,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    # -----------------------------------------------------
    # LEDGER TRANSACTION
    # -----------------------------------------------------

    transaction = models.OneToOneField(
        FinancialTransaction,
        on_delete=models.PROTECT,
        related_name="expense_record",
        null=True,
        blank=True,
    )

    # -----------------------------------------------------
    # TIMESTAMPS
    # -----------------------------------------------------

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-expense_date",
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "status",
                    "expense_date",
                ],
            ),
            models.Index(
                fields=[
                    "category",
                    "expense_date",
                ],
            ),
            models.Index(
                fields=[
                    "payment_source",
                    "expense_date",
                ],
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="finance_expense_amount_positive",
            ),
        ]

    def __str__(self):
        return (
            f"{self.expense_number} - "
            f"{self.title} - "
            f"KES {self.amount:,.2f}"
        )

    def clean(self):
        super().clean()

        errors = {}

        # -------------------------------------------------
        # AMOUNT
        # -------------------------------------------------

        if self.amount is not None and self.amount <= ZERO:
            errors["amount"] = (
                "Expense amount must be greater than zero."
            )

        # -------------------------------------------------
        # CATEGORY
        #
        # IMPORTANT:
        # Check category_id before accessing self.category.
        # -------------------------------------------------

        if self.category_id:

            category = self.category

            if (
                category.category_type
                != FinancialCategory.CategoryType.EXPENSE
            ):
                errors["category"] = (
                    "An expense must use "
                    "an expense category."
                )

            if not category.is_active:
                errors["category"] = (
                    "The selected expense category "
                    "is inactive."
                )

        else:
            errors["category"] = (
                "An expense must have a category."
            )

        # -------------------------------------------------
        # STATUS WORKFLOW
        # -------------------------------------------------

        if self.status == self.Status.SUBMITTED:

            if not self.submitted_by_id:
                errors["submitted_by"] = (
                    "The user submitting the expense "
                    "is required."
                )

        # -------------------------------------------------

        if self.status == self.Status.APPROVED:

            if not self.submitted_by_id:
                errors["submitted_by"] = (
                    "An approved expense must have "
                    "a submitting user."
                )

            if not self.approved_by_id:
                errors["approved_by"] = (
                    "The user approving the expense "
                    "is required."
                )

        # -------------------------------------------------

        if self.status == self.Status.REJECTED:

            if not self.submitted_by_id:
                errors["submitted_by"] = (
                    "A rejected expense must have "
                    "a submitting user."
                )

            if not self.rejected_by_id:
                errors["rejected_by"] = (
                    "The user rejecting the expense "
                    "is required."
                )

            if not (self.rejection_reason or "").strip():
                errors["rejection_reason"] = (
                    "A rejection reason is required."
                )

        # -------------------------------------------------

        if self.status == self.Status.PAID:

            if not self.submitted_by_id:
                errors["submitted_by"] = (
                    "A paid expense must have "
                    "a submitting user."
                )

            if not self.approved_by_id:
                errors["approved_by"] = (
                    "A paid expense must have "
                    "an approving user."
                )

            if not self.paid_by_id:
                errors["paid_by"] = (
                    "The user who paid the expense "
                    "is required."
                )

            if not (self.payment_reference or "").strip():
                errors["payment_reference"] = (
                    "A payment reference is required "
                    "for a paid expense."
                )

            if not self.transaction_id:
                errors["transaction"] = (
                    "A paid expense must have "
                    "a financial ledger transaction."
                )

            else:
                transaction = self.transaction

                if (
                    transaction.transaction_type
                    != FinancialTransaction.TransactionType.EXPENSE
                ):
                    errors["transaction"] = (
                        "An expense must link to "
                        "an expense ledger transaction."
                    )

        # -------------------------------------------------

        if self.status == self.Status.VOIDED:

            if not self.voided_by_id:
                errors["voided_by"] = (
                    "The user who voided the expense "
                    "is required."
                )

            if not (self.void_reason or "").strip():
                errors["void_reason"] = (
                    "A void reason is required."
                )

        # -------------------------------------------------
        # TRANSACTION CONSISTENCY
        # -------------------------------------------------

        if self.transaction_id:

            transaction = self.transaction

            if (
                transaction.transaction_type
                != FinancialTransaction.TransactionType.EXPENSE
            ):
                errors["transaction"] = (
                    "An expense can only be linked "
                    "to an expense transaction."
                )

            if (
                self.category_id
                and self.category_id != transaction.category_id
            ):
                errors["transaction"] = (
                    "Expense category must match "
                    "the ledger transaction category."
                )

            if (
                self.amount is not None
                and self.amount != transaction.amount
            ):
                errors["transaction"] = (
                    "Expense amount must match "
                    "the ledger transaction amount."
                )

            if (
                transaction.payment_id is not None
            ):
                errors["transaction"] = (
                    "An expense transaction cannot "
                    "be linked to an incoming payment."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """
        Generate expense number and maintain
        workflow timestamps.

        Validation is performed by forms/services before
        persistence so multi-step workflows can construct
        objects safely.
        """

        if not self.expense_number:
            date = timezone.now().strftime("%Y%m%d")
            code = uuid.uuid4().hex[:8].upper()

            self.expense_number = (
                f"EXP-{date}-{code}"
            )

        now = timezone.now()

        if (
            self.status == self.Status.SUBMITTED
            and self.submitted_at is None
        ):
            self.submitted_at = now

        if (
            self.status == self.Status.APPROVED
            and self.approved_at is None
        ):
            self.approved_at = now

        if (
            self.status == self.Status.REJECTED
            and self.rejected_at is None
        ):
            self.rejected_at = now

        if (
            self.status == self.Status.PAID
            and self.paid_at is None
        ):
            self.paid_at = now

        if (
            self.status == self.Status.VOIDED
            and self.voided_at is None
        ):
            self.voided_at = now

        super().save(*args, **kwargs)

    # -----------------------------------------------------
    # PROPERTIES
    # -----------------------------------------------------

    @property
    def is_draft(self):
        return self.status == self.Status.DRAFT

    @property
    def is_submitted(self):
        return self.status == self.Status.SUBMITTED

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED

    @property
    def is_rejected(self):
        return self.status == self.Status.REJECTED

    @property
    def is_paid(self):
        return self.status == self.Status.PAID

    @property
    def is_voided(self):
        return self.status == self.Status.VOIDED

    @property
    def affects_balance(self):
        return (
            self.status == self.Status.PAID
            and self.transaction_id is not None
            and self.transaction.status
            == FinancialTransaction.Status.POSTED
        )

    @property
    def amount_display(self):
        return f"KES {self.amount:,.2f}"


# =========================================================
# FINANCIAL RECONCILIATION
# =========================================================

class FinancialReconciliation(models.Model):
    """
    Compares Finance ledger totals against an external
    financial statement.
    """

    class Source(models.TextChoices):
        MPESA = "MPESA", "M-Pesa"
        BANK = "BANK", "Bank"
        CASH = "CASH", "Cash Book"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        RECONCILED = "RECONCILED", "Reconciled"
        DISCREPANCY = "DISCREPANCY", "Discrepancy"

    reconciliation_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        editable=False,
    )

    source = models.CharField(
        max_length=10,
        choices=Source.choices,
    )

    statement_reference = models.CharField(
        max_length=100,
        blank=True,
    )

    period_start = models.DateField()

    period_end = models.DateField()

    system_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    system_expenses = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    external_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    external_expenses = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=ZERO,
        validators=[
            MinValueValidator(ZERO),
        ],
    )

    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reconciliations_prepared",
    )

    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reconciliations_completed",
        null=True,
        blank=True,
    )

    reconciled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    statement_file = models.FileField(
        upload_to="finance/statements/%Y/%m/",
        null=True,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-period_end",
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "source",
                    "period_end",
                ],
            ),
            models.Index(
                fields=[
                    "status",
                    "period_end",
                ],
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(
                    period_end__gte=F("period_start")
                ),
                name="finance_reconciliation_valid_period",
            ),
        ]

    def __str__(self):
        return (
            f"{self.reconciliation_number} - "
            f"{self.get_source_display()} - "
            f"{self.period_start} to {self.period_end}"
        )

    def clean(self):
        super().clean()

        errors = {}

        # -------------------------------------------------
        # PERIOD
        # -------------------------------------------------

        if (
            self.period_start is not None
            and self.period_end is not None
            and self.period_end < self.period_start
        ):
            errors["period_end"] = (
                "The end date cannot be before "
                "the start date."
            )

        # -------------------------------------------------
        # AMOUNTS
        # -------------------------------------------------

        monetary_fields = [
            "system_income",
            "system_expenses",
            "external_income",
            "external_expenses",
        ]

        for field_name in monetary_fields:

            value = getattr(
                self,
                field_name,
                ZERO,
            )

            if value is not None and value < ZERO:
                errors[field_name] = (
                    "This amount cannot be negative."
                )

        # -------------------------------------------------
        # RECONCILED STATE
        # -------------------------------------------------

        if self.status == self.Status.RECONCILED:

            if not self.reconciled_by_id:
                errors["reconciled_by"] = (
                    "A reconciled record must identify "
                    "the user who completed it."
                )

            if not self.is_balanced:
                errors["status"] = (
                    "A reconciliation with discrepancies "
                    "cannot be marked as reconciled."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):

        if not self.reconciliation_number:
            date = timezone.now().strftime("%Y%m%d")
            code = uuid.uuid4().hex[:8].upper()

            self.reconciliation_number = (
                f"REC-{date}-{code}"
            )

        if (
            self.status == self.Status.RECONCILED
            and self.reconciled_at is None
        ):
            self.reconciled_at = timezone.now()

        super().save(*args, **kwargs)

    # -----------------------------------------------------
    # DIFFERENCES
    # -----------------------------------------------------

    @property
    def income_difference(self):
        return (
            self.external_income
            - self.system_income
        ).quantize(Decimal("0.01"))

    @property
    def expense_difference(self):
        return (
            self.external_expenses
            - self.system_expenses
        ).quantize(Decimal("0.01"))

    @property
    def net_difference(self):
        return (
            self.income_difference
            - self.expense_difference
        ).quantize(Decimal("0.01"))

    @property
    def is_balanced(self):
        return (
            self.income_difference == ZERO
            and self.expense_difference == ZERO
        )


# =========================================================
# FINANCIAL AUDIT LOG
# =========================================================

class FinancialAuditLog(models.Model):
    """
    Immutable financial audit trail.
    """

    class Action(models.TextChoices):
        CREATED = "CREATED", "Created"
        UPDATED = "UPDATED", "Updated"
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        PAID = "PAID", "Paid"
        POSTED = "POSTED", "Posted"
        VOIDED = "VOIDED", "Voided"
        RECONCILED = "RECONCILED", "Reconciled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="finance_audit_logs",
    )

    action = models.CharField(
        max_length=15,
        choices=Action.choices,
    )

    transaction = models.ForeignKey(
        FinancialTransaction,
        on_delete=models.PROTECT,
        related_name="audit_logs",
        null=True,
        blank=True,
    )

    expense = models.ForeignKey(
        Expense,
        on_delete=models.PROTECT,
        related_name="audit_logs",
        null=True,
        blank=True,
    )

    reconciliation = models.ForeignKey(
        FinancialReconciliation,
        on_delete=models.PROTECT,
        related_name="audit_logs",
        null=True,
        blank=True,
    )

    category = models.ForeignKey(
        FinancialCategory,
        on_delete=models.PROTECT,
        related_name="audit_logs",
        null=True,
        blank=True,
    )

    description = models.TextField()

    old_values = models.JSONField(
        default=dict,
        blank=True,
    )

    new_values = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "user",
                    "created_at",
                ],
            ),
            models.Index(
                fields=[
                    "action",
                    "created_at",
                ],
            ),
        ]

    def __str__(self):
        return (
            f"{self.user} - "
            f"{self.get_action_display()} - "
            f"{self.created_at:%Y-%m-%d %H:%M}"
        )

    def delete(self, *args, **kwargs):
        """
        Financial audit logs cannot be deleted through
        normal application operations.
        """

        raise ValidationError(
            "Financial audit logs cannot be deleted."
        )