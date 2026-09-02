
# finance/signals.py

"""
KUCSA Finance Signals
=====================

Automatic integration between the Payments application
and the Finance application.

RESPONSIBILITY
--------------

This module handles one automatic accounting event:

    Payment
       │
       │ COMPLETED
       ▼
    Finance
       │
       ▼
    FinancialTransaction
       │
       ▼
      POSTED

Only successfully completed payments are recorded as
financial income.

IMPORTANT
---------

These signals do NOT:

    - verify M-Pesa payments
    - communicate with Safaricom
    - process M-Pesa callbacks
    - activate membership
    - create expense transactions
    - replace finance services

The Payments application remains responsible for
payment processing.

The Finance service layer remains responsible for
financial business workflows.

This signal only creates the accounting record after
a Payment has already become COMPLETED.
"""

import logging
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from payments.models import Payment, PaymentStatus

from .models import (
    FinancialAuditLog,
    FinancialCategory,
    FinancialTransaction,
)


logger = logging.getLogger(__name__)


# =========================================================
# CONSTANTS
# =========================================================

MEMBERSHIP_INCOME_CATEGORY = "Membership Income"
SUPPORT_INCOME_CATEGORY = "Club Support"


# =========================================================
# HELPERS
# =========================================================

def _get_income_category(payment):
    """
    Return the appropriate active income category.

    Membership payments use:

        Membership Income

    Support payments use:

        Club Support

    The categories are created automatically when they do
    not already exist.

    This prevents the Finance income workflow from failing
    simply because an administrator has not manually created
    the default income categories.
    """

    if payment.is_membership_payment:
        category_name = MEMBERSHIP_INCOME_CATEGORY
        description = (
            "Income received from KUCSA membership "
            "payments."
        )

    else:
        category_name = SUPPORT_INCOME_CATEGORY
        description = (
            "Voluntary financial contributions made "
            "to support KUCSA activities."
        )

    category, created = (
        FinancialCategory.objects.get_or_create(
            name=category_name,
            defaults={
                "category_type": (
                    FinancialCategory.CategoryType.INCOME
                ),
                "description": description,
                "is_active": True,
                "is_system": True,
            },
        )
    )

    # -----------------------------------------------------
    # SAFETY CHECK
    # -----------------------------------------------------

    if (
        category.category_type
        != FinancialCategory.CategoryType.INCOME
    ):
        raise ValueError(
            f"Financial category '{category.name}' "
            "is not an income category."
        )

    if not category.is_active:
        raise ValueError(
            f"Financial category '{category.name}' "
            "is inactive."
        )

    if created:
        logger.info(
            "Created Finance income category '%s'.",
            category.name,
        )

    return category


def _get_recording_user(payment):
    """
    Determine which user should be recorded as the
    Finance transaction owner.

    Payment belongs to a Member, and the Member normally
    belongs to a User.

    We intentionally resolve the user dynamically so this
    works with the existing KUCSA Member relationship
    without adding a user field to Payment.
    """

    member = payment.member

    user = getattr(
        member,
        "user",
        None,
    )

    if user is None:
        raise ValueError(
            "The payment member does not have an associated "
            "user. Finance cannot determine recorded_by."
        )

    return user


def _build_transaction_description(payment):
    """
    Build a clear human-readable Finance description.
    """

    if payment.is_membership_payment:
        return (
            "KUCSA membership payment received "
            f"from {payment.member_name}."
        )

    return (
        "KUCSA club support contribution received "
        f"from {payment.member_name}."
    )


def _get_transaction_date(payment):
    """
    Use the Safaricom transaction date when available.

    Fallback order:

        1. Safaricom transaction_date
        2. Payment completed_at
        3. Current time
    """

    return (
        payment.transaction_date
        or payment.completed_at
        or timezone.now()
    )


# =========================================================
# PAYMENT → FINANCE
# =========================================================

@receiver(
    post_save,
    sender=Payment,
    dispatch_uid="finance_payment_completed",
)
def create_finance_transaction_for_completed_payment(
    sender,
    instance,
    created,
    **kwargs,
):
    """
    Create a Finance income transaction whenever a
    Payment is COMPLETED.

    The signal is intentionally idempotent.

    If a Finance transaction already exists for the
    payment, nothing new is created.
    """

    payment = instance

    # -----------------------------------------------------
    # ONLY COMPLETED PAYMENTS ENTER FINANCE
    # -----------------------------------------------------

    if payment.status != PaymentStatus.COMPLETED:
        return

    # -----------------------------------------------------
    # PAYMENT MUST HAVE A MEMBER
    # -----------------------------------------------------

    if not payment.member_id:
        logger.error(
            "Completed payment %s has no member. "
            "Finance transaction was not created.",
            payment.pk,
        )
        return

    # -----------------------------------------------------
    # IDEMPOTENCY
    #
    # Payment has a OneToOne relationship with the Finance
    # transaction, so one payment can only produce one
    # Finance transaction.
    # -----------------------------------------------------

    existing_transaction = (
        FinancialTransaction.objects
        .filter(payment_id=payment.pk)
        .first()
    )

    if existing_transaction:
        logger.info(
            "Finance transaction %s already exists for "
            "payment %s. Skipping duplicate creation.",
            existing_transaction.pk,
            payment.pk,
        )
        return

    # -----------------------------------------------------
    # CREATE FINANCE RECORD ATOMICALLY
    # -----------------------------------------------------

    try:
        with transaction.atomic():

            category = _get_income_category(
                payment
            )

            recorded_by = _get_recording_user(
                payment
            )

            financial_transaction = (
                FinancialTransaction.objects.create(
                    transaction_type=(
                        FinancialTransaction
                        .TransactionType
                        .INCOME
                    ),

                    status=(
                        FinancialTransaction
                        .Status
                        .POSTED
                    ),

                    category=category,

                    amount=(
                        Decimal(payment.amount)
                    ),

                    description=(
                        _build_transaction_description(
                            payment
                        )
                    ),

                    reference=(
                        payment.finance_reference
                    ),

                    payment_source=(
                        FinancialTransaction
                        .PaymentSource
                        .MPESA
                    ),

                    payment=payment,

                    member=payment.member,

                    recorded_by=recorded_by,

                    transaction_date=(
                        _get_transaction_date(
                            payment
                        )
                    ),

                    posted_at=(
                        payment.completed_at
                        or timezone.now()
                    ),

                    notes=(
                        "Automatically recorded from "
                        f"completed {payment.get_payment_type_display()} "
                        "payment."
                    ),
                )
            )

            # -------------------------------------------------
            # AUDIT TRAIL
            # -------------------------------------------------

            FinancialAuditLog.objects.create(
                user=recorded_by,

                action=(
                    FinancialAuditLog
                    .Action
                    .POSTED
                ),

                transaction=financial_transaction,

                description=(
                    "Finance income transaction automatically "
                    "created from completed payment "
                    f"{payment.pk}."
                ),

                old_values={},

                new_values={
                    "payment_id": payment.pk,
                    "transaction_id": (
                        financial_transaction.pk
                    ),
                    "transaction_number": (
                        financial_transaction
                        .transaction_number
                    ),
                    "payment_type": (
                        payment.payment_type
                    ),
                    "amount": str(
                        payment.amount
                    ),
                    "reference": (
                        payment.finance_reference
                    ),
                    "status": (
                        financial_transaction.status
                    ),
                },
            )

            logger.info(
                "Finance income transaction %s created "
                "for completed payment %s.",
                financial_transaction.transaction_number,
                payment.pk,
            )

    except IntegrityError:
        # -------------------------------------------------
        # RACE CONDITION PROTECTION
        #
        # If two processes attempt to create the Finance
        # transaction simultaneously, the OneToOne
        # constraint protects the ledger from duplicates.
        # -------------------------------------------------

        existing_transaction = (
            FinancialTransaction.objects
            .filter(payment_id=payment.pk)
            .first()
        )

        if existing_transaction:
            logger.warning(
                "Finance transaction already exists for "
                "payment %s after IntegrityError. "
                "Duplicate creation prevented.",
                payment.pk,
            )
            return

        logger.exception(
            "Unable to create Finance transaction for "
            "completed payment %s.",
            payment.pk,
        )

    except (ValueError, ValidationError) as error:
        logger.exception(
            "Finance integration failed for completed "
            "payment %s: %s",
            payment.pk,
            error,
        )
