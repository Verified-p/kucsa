# payments/models.py

"""
KUCSA Payments Models
======================

Models responsible for recording payments made through the
KUCSA platform.

Supported payment purposes:

    - MEMBERSHIP
    - SUPPORT

Payment processing is intentionally separated from finance.

The payment application is responsible for:

    - Creating payment records
    - Tracking M-Pesa payment state
    - Storing Safaricom references
    - Recording successful/failed/cancelled payments

The finance application is responsible for:

    - Creating financial transactions
    - Categorising completed payments
    - Financial reporting
    - Income calculations
    - Reconciliation
    - Financial audit records

FINANCE INTEGRATION
-------------------

The relationship is intentionally one-directional:

    Payment
       │
       │ completed
       ↓
    Finance Service
       │
       ↓
    FinancialTransaction

A completed payment may therefore become a financial
transaction.

IMPORTANT
---------

Payment completion does NOT directly create a financial
transaction inside this model.

That operation belongs to the payment service/callback
layer so that payment processing and financial accounting
remain separate responsibilities.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


# =========================================================
# PAYMENT METHOD
# =========================================================


class PaymentMethod(models.TextChoices):
    """
    Supported payment methods.
    """

    MPESA = "MPESA", "M-Pesa"


# =========================================================
# PAYMENT TYPE
# =========================================================


class PaymentType(models.TextChoices):
    """
    Defines the purpose of a KUCSA payment.

    MEMBERSHIP
        Payment for KUCSA membership.

    SUPPORT
        Voluntary financial contribution toward KUCSA.

    IMPORTANT
    ---------
    SUPPORT payments must never activate or renew
    membership.
    """

    MEMBERSHIP = "MEMBERSHIP", "Membership"
    SUPPORT = "SUPPORT", "Club Support"


# =========================================================
# PAYMENT STATUS
# =========================================================


class PaymentStatus(models.TextChoices):
    """
    Payment lifecycle states.
    """

    PENDING = "PENDING", "Pending"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


# =========================================================
# PAYMENT
# =========================================================


class Payment(models.Model):
    """
    KUCSA Payment.

    Represents one payment initiated through the KUCSA
    platform.

    Supported payment types:

        MEMBERSHIP
        SUPPORT

    PAYMENT FLOW
    ------------

        Payment Created
              ↓
           PENDING
              ↓
         STK Push
              ↓
       Member enters PIN
              ↓
     Safaricom Callback
              ↓
          COMPLETED
              ↓
       Payment Service
              ↓
      Finance Transaction
              ↓
       Financial Reports


    RESPONSIBILITIES
    ----------------

    This model is responsible for representing payment
    state and payment information.

    It does NOT:

        - communicate with Safaricom
        - initiate STK Pushes
        - create financial transactions
        - activate membership directly
        - determine platform permissions

    Those responsibilities belong to the appropriate
    service, callback, finance, and permission layers.
    """

    # =====================================================
    # MEMBER
    # =====================================================

    member = models.ForeignKey(
        "members.Member",
        on_delete=models.CASCADE,
        related_name="payments",
        db_index=True,
        help_text=(
            "KUCSA member associated with this payment."
        ),
    )

    # =====================================================
    # PAYMENT TYPE
    # =====================================================

    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.MEMBERSHIP,
        db_index=True,
        help_text=(
            "Purpose of the payment: membership or "
            "club support."
        ),
    )

    # =====================================================
    # PAYMENT AMOUNT
    # =====================================================

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("1.00")
            ),
        ],
        help_text=(
            "Payment amount in Kenyan Shillings."
        ),
    )

    # =====================================================
    # PAYMENT METHOD
    # =====================================================

    method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.MPESA,
        db_index=True,
        help_text=(
            "Payment method used for this transaction."
        ),
    )

    # =====================================================
    # PAYMENT STATUS
    # =====================================================

    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
        help_text=(
            "Current lifecycle state of the payment."
        ),
    )

    # =====================================================
    # M-PESA PHONE NUMBER
    # =====================================================

    phone_number = models.CharField(
        max_length=20,
        help_text=(
            "Normalized Kenyan phone number used for "
            "the M-Pesa STK Push."
        ),
    )

    # =====================================================
    # SAFARICOM MERCHANT REQUEST ID
    # =====================================================

    merchant_request_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text=(
            "Safaricom MerchantRequestID returned when "
            "the STK Push is initiated."
        ),
    )

    # =====================================================
    # SAFARICOM CHECKOUT REQUEST ID
    # =====================================================

    checkout_request_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text=(
            "Safaricom CheckoutRequestID used to match "
            "the callback to this payment."
        ),
    )

    # =====================================================
    # M-PESA RECEIPT
    # =====================================================

    mpesa_receipt_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text=(
            "Official M-Pesa receipt number supplied "
            "by Safaricom after successful payment."
        ),
    )

    # =====================================================
    # SAFARICOM TRANSACTION DATE
    # =====================================================

    transaction_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text=(
            "Transaction date and time reported "
            "by Safaricom."
        ),
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        db_index=True,
        help_text=(
            "Date and time the payment was confirmed "
            "as completed."
        ),
    )

    # =====================================================
    # META
    # =====================================================

    class Meta:

        ordering = [
            "-created_at",
        ]

        verbose_name = "Payment"

        verbose_name_plural = "Payments"

        indexes = [

            # -------------------------------------------------
            # MEMBER + STATUS
            # -------------------------------------------------

            models.Index(
                fields=[
                    "member",
                    "status",
                ],
                name="pay_member_status_idx",
            ),

            # -------------------------------------------------
            # STATUS + CREATED
            # -------------------------------------------------

            models.Index(
                fields=[
                    "status",
                    "created_at",
                ],
                name="pay_status_created_idx",
            ),

            # -------------------------------------------------
            # MEMBER + CREATED
            # -------------------------------------------------

            models.Index(
                fields=[
                    "member",
                    "created_at",
                ],
                name="pay_member_created_idx",
            ),

            # -------------------------------------------------
            # PAYMENT TYPE + STATUS
            # -------------------------------------------------

            models.Index(
                fields=[
                    "payment_type",
                    "status",
                ],
                name="pay_type_status_idx",
            ),

            # -------------------------------------------------
            # MEMBER + PAYMENT TYPE + CREATED
            # -------------------------------------------------

            models.Index(
                fields=[
                    "member",
                    "payment_type",
                    "created_at",
                ],
                name="pay_mem_type_created",
            ),
        ]

    # =====================================================
    # STRING REPRESENTATION
    # =====================================================

    def __str__(self):

        return (
            f"{self.member} - "
            f"{self.get_payment_type_display()} - "
            f"KES {self.amount:,.2f} - "
            f"{self.get_status_display()}"
        )

    # =====================================================
    # PAYMENT TYPE PROPERTIES
    # =====================================================

    @property
    def is_membership_payment(self):
        """
        Return True when this payment is for membership.
        """

        return (
            self.payment_type
            == PaymentType.MEMBERSHIP
        )

    # -----------------------------------------------------

    @property
    def is_support_payment(self):
        """
        Return True when this payment is a voluntary
        KUCSA support contribution.
        """

        return (
            self.payment_type
            == PaymentType.SUPPORT
        )

    # -----------------------------------------------------

    @property
    def payment_type_display(self):
        """
        Return the human-readable payment type.
        """

        return self.get_payment_type_display()

    # =====================================================
    # FINANCE PROPERTIES
    # =====================================================

    @property
    def is_financially_eligible(self):
        """
        Return True when this payment is eligible to be
        recorded by the finance application.

        Only successfully completed payments should enter
        the financial transaction ledger.
        """

        return self.status == PaymentStatus.COMPLETED

    # -----------------------------------------------------

    @property
    def finance_reference(self):
        """
        Return the best available reference for finance.

        The official M-Pesa receipt is preferred because
        it is the strongest external payment reference.
        """

        return (
            self.mpesa_receipt_number
            or self.checkout_request_id
            or self.merchant_request_id
            or f"PAY-{self.pk}"
        )

    # =====================================================
    # STATUS PROPERTIES
    # =====================================================

    @property
    def is_pending(self):
        """
        Return True when the payment is awaiting
        Safaricom confirmation.
        """

        return (
            self.status
            == PaymentStatus.PENDING
        )

    # -----------------------------------------------------

    @property
    def is_completed(self):
        """
        Return True when Safaricom has confirmed
        successful payment.
        """

        return (
            self.status
            == PaymentStatus.COMPLETED
        )

    # -----------------------------------------------------

    @property
    def is_failed(self):
        """
        Return True when the payment failed.
        """

        return (
            self.status
            == PaymentStatus.FAILED
        )

    # -----------------------------------------------------

    @property
    def is_cancelled(self):
        """
        Return True when the payment was cancelled.
        """

        return (
            self.status
            == PaymentStatus.CANCELLED
        )

    # -----------------------------------------------------

    @property
    def is_finalized(self):
        """
        Return True when the payment has reached
        a terminal state.
        """

        return self.status in {
            PaymentStatus.COMPLETED,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
        }

    # =====================================================
    # PAYMENT LIFECYCLE
    # =====================================================

    def mark_completed(
        self,
        receipt_number=None,
        transaction_date=None,
    ):
        """
        Mark a pending payment as completed.

        This method changes only the payment.

        It does NOT create a financial transaction.

        Finance integration is handled by the payment
        service after successful completion.
        """

        # -------------------------------------------------
        # IDEMPOTENCY
        # -------------------------------------------------

        if self.status == PaymentStatus.COMPLETED:
            return self

        # -------------------------------------------------
        # ONLY PENDING PAYMENTS CAN BE COMPLETED
        # -------------------------------------------------

        if self.status != PaymentStatus.PENDING:
            return self

        # -------------------------------------------------
        # UPDATE STATUS
        # -------------------------------------------------

        self.status = PaymentStatus.COMPLETED

        # -------------------------------------------------
        # RECEIPT
        # -------------------------------------------------

        if receipt_number:

            self.mpesa_receipt_number = (
                str(receipt_number).strip()
            )

        # -------------------------------------------------
        # TRANSACTION DATE
        # -------------------------------------------------

        if transaction_date:

            self.transaction_date = transaction_date

        # -------------------------------------------------
        # COMPLETION TIME
        # -------------------------------------------------

        self.completed_at = timezone.now()

        # -------------------------------------------------
        # SAVE
        # -------------------------------------------------

        self.save(
            update_fields=[
                "status",
                "mpesa_receipt_number",
                "transaction_date",
                "completed_at",
                "updated_at",
            ]
        )

        return self

    # =====================================================
    # MARK FAILED
    # =====================================================

    def mark_failed(self):
        """
        Mark a pending payment as failed.

        Completed payments cannot be changed to failed.
        """

        if self.status != PaymentStatus.PENDING:
            return self

        self.status = PaymentStatus.FAILED

        self.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return self

    # =====================================================
    # MARK CANCELLED
    # =====================================================

    def mark_cancelled(self):
        """
        Mark a pending payment as cancelled.

        Completed payments cannot be cancelled.
        """

        if self.status != PaymentStatus.PENDING:
            return self

        self.status = PaymentStatus.CANCELLED

        self.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return self

    # =====================================================
    # PAYMENT OWNERSHIP
    # =====================================================

    @property
    def member_name(self):
        """
        Return the member's full name.
        """

        if not self.member_id:
            return "Unknown Member"

        return self.member.full_name

    # -----------------------------------------------------

    @property
    def membership_number(self):
        """
        Return the member's membership number.
        """

        if not self.member_id:
            return None

        return self.member.membership_number

    # =====================================================
    # PAYMENT DISPLAY
    # =====================================================

    @property
    def amount_display(self):
        """
        Return a human-readable payment amount.
        """

        return f"KES {self.amount:,.2f}"

    # -----------------------------------------------------

    @property
    def status_display(self):
        """
        Return the human-readable payment status.
        """

        return self.get_status_display()

    # -----------------------------------------------------

    @property
    def receipt_display(self):
        """
        Return the M-Pesa receipt number or fallback.
        """

        return (
            self.mpesa_receipt_number
            or "Not available"
        )

    # =====================================================
    # RECEIPT CHECK
    # =====================================================

    @property
    def has_receipt(self):
        """
        Return True when Safaricom supplied an
        M-Pesa receipt number.
        """

        return bool(
            self.mpesa_receipt_number
        )

    # =====================================================
    # PAYMENT AGE
    # =====================================================

    @property
    def age_in_seconds(self):
        """
        Return the number of seconds since
        the payment was created.

        Useful for pending-payment monitoring.
        """

        if not self.created_at:
            return 0

        return max(
            0,
            int(
                (
                    timezone.now()
                    - self.created_at
                ).total_seconds()
            ),
        )

    # =====================================================
    # PAYMENT AGE DISPLAY
    # =====================================================

    @property
    def age_display(self):
        """
        Return a simple human-readable payment age.
        """

        seconds = self.age_in_seconds

        if seconds < 60:
            return f"{seconds}s"

        minutes = seconds // 60

        if minutes < 60:
            return f"{minutes}m"

        hours = minutes // 60

        if hours < 24:
            return f"{hours}h"

        days = hours // 24

        return f"{days}d"