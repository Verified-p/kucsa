# payments/views.py

"""
KUCSA Payment Views
===================

HTTP views for KUCSA payment processing.

SUPPORTED PAYMENT TYPES
------------------------
1. Membership
2. KUCSA Support

PAYMENT LIFECYCLE
-----------------

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
      Validate
          ↓
      COMPLETED
          ↓
    ┌───────────────┐
    │               │
MEMBERSHIP       SUPPORT
    │               │
    ↓               ↓
Activate       Record payment
membership     only


IMPORTANT
---------

The browser NEVER completes a payment.

The browser may only READ the current payment status.

Only the Safaricom Daraja callback can complete
or fail the payment.

Membership activation is performed only after:

    1. Callback identifies the payment.
    2. ResultCode == 0.
    3. Amount matches expected amount.
    4. Receipt exists.
    5. Payment is locked.
    6. Payment is completed.

Support payments NEVER activate membership.
"""

import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from members.models import Member

from .models import (
    Payment,
    PaymentMethod,
    PaymentStatus,
    PaymentType,
)
from .services import (
    format_phone_number,
    get_membership_fee,
    initiate_stk_push,
    validate_support_amount,
)


logger = logging.getLogger(__name__)


# =========================================================
# USER / ACCOUNT HELPERS
# =========================================================


def is_system_admin(user):
    """
    Return True when the authenticated user is a KUCSA
    system administrator.

    Administrators:

        - do not require a Member profile
        - do not pay membership fees
        - do not use member payment workflows
        - access the system directly
    """

    if not user or not user.is_authenticated:
        return False

    return (
        getattr(user, "is_superuser", False)
        or getattr(user, "role", None)
        == getattr(
            getattr(user, "Role", None),
            "ADMIN",
            "ADMIN",
        )
    )


def get_user_member(user):
    """
    Safely return the Member associated with a User.

    Returns:
        Member instance or None.
    """

    if not user or not user.is_authenticated:
        return None

    if is_system_admin(user):
        return None

    return (
        Member.objects
        .filter(user=user)
        .select_related("user")
        .first()
    )


def require_member(request):
    """
    Return the authenticated user's Member profile.

    Administrators are intentionally excluded.
    """

    if is_system_admin(request.user):
        return None

    return get_user_member(request.user)


def redirect_non_member(request):
    """
    Handle an authenticated user who does not have
    a Member profile.

    The user is already authenticated, so there is
    no reason to redirect them to login.
    """

    messages.error(
        request,
        (
            "Your KUCSA member profile could not be found. "
            "Please contact the system administrator."
        ),
    )

    return redirect("dashboard:dashboard")


# =========================================================
# PAYMENT AMOUNTS
# =========================================================


def get_payment_amount():
    """
    Return the configured KUCSA membership fee.
    """

    return get_membership_fee()


def get_support_payment_amount(raw_amount):
    """
    Validate and normalize a support contribution amount.
    """

    return validate_support_amount(raw_amount)


# =========================================================
# MEMBERSHIP PAYMENT PAGE
# =========================================================


@login_required
@require_GET
def payment_create_view(request):
    """
    Display the KUCSA membership payment page.

    Administrators cannot access this workflow.
    """

    # -----------------------------------------------------
    # ADMINISTRATOR
    # -----------------------------------------------------

    if is_system_admin(request.user):

        messages.info(
            request,
            (
                "System administrators do not require "
                "membership payment."
            ),
        )

        return redirect(
            "dashboard:dashboard"
        )

    # -----------------------------------------------------
    # MEMBER
    # -----------------------------------------------------

    member = get_user_member(
        request.user
    )

    if member is None:

        logger.warning(
            "User %s attempted to access membership "
            "payment page without a Member profile.",
            request.user.pk,
        )

        return redirect_non_member(
            request
        )

    # -----------------------------------------------------
    # ACTIVE MEMBERSHIP
    # -----------------------------------------------------

    if member.can_access_platform:

        messages.info(
            request,
            "Your KUCSA membership is already active.",
        )

        return redirect(
            "dashboard:dashboard"
        )

    # -----------------------------------------------------
    # COMPLETED MEMBERSHIP PAYMENT
    # -----------------------------------------------------

    completed_payment = (
        Payment.objects
        .filter(
            member=member,
            payment_type=PaymentType.MEMBERSHIP,
            status=PaymentStatus.COMPLETED,
        )
        .order_by(
            "-completed_at",
            "-created_at",
        )
        .first()
    )

    if completed_payment:

        return render(
            request,
            "payment_create.html",
            {
                "membership_fee": get_payment_amount(),
                "already_paid": True,
                "payment": completed_payment,
                "member": member,
            },
        )

    # -----------------------------------------------------
    # PENDING MEMBERSHIP PAYMENT
    # -----------------------------------------------------

    pending_payment = (
        Payment.objects
        .filter(
            member=member,
            payment_type=PaymentType.MEMBERSHIP,
            status=PaymentStatus.PENDING,
        )
        .order_by("-created_at")
        .first()
    )

    if pending_payment:

        return redirect(
            "payments:payment_pending",
            payment_id=pending_payment.id,
        )

    # -----------------------------------------------------
    # PAYMENT REQUIRED
    # -----------------------------------------------------

    return render(
        request,
        "payment_create.html",
        {
            "membership_fee": get_payment_amount(),
            "already_paid": False,
            "payment": None,
            "member": member,
        },
    )


# =========================================================
# CREATE MEMBERSHIP PAYMENT
# =========================================================


@login_required
@require_POST
def payment_create_submit_view(request):
    """
    Create a membership payment and initiate an STK Push.

    IMPORTANT:

    This view creates the payment and sends the STK Push.

    It NEVER completes the payment.

    Completion occurs only through the Safaricom callback.
    """

    # -----------------------------------------------------
    # ADMINISTRATOR
    # -----------------------------------------------------

    if is_system_admin(request.user):

        messages.info(
            request,
            (
                "System administrators do not require "
                "membership payment."
            ),
        )

        return redirect(
            "dashboard:dashboard"
        )

    # -----------------------------------------------------
    # MEMBER
    # -----------------------------------------------------

    member = get_user_member(
        request.user
    )

    if member is None:

        logger.warning(
            "User %s attempted to create membership "
            "payment without a Member profile.",
            request.user.pk,
        )

        return redirect_non_member(
            request
        )

    # =====================================================
    # DATABASE TRANSACTION
    # =====================================================

    with transaction.atomic():

        member = (
            Member.objects
            .select_for_update()
            .get(
                pk=member.pk
            )
        )

        # -------------------------------------------------
        # ACTIVE MEMBERSHIP
        # -------------------------------------------------

        if member.can_access_platform:

            messages.info(
                request,
                "Your KUCSA membership is already active.",
            )

            return redirect(
                "dashboard:dashboard"
            )

        # -------------------------------------------------
        # EXISTING PENDING PAYMENT
        # -------------------------------------------------

        existing_payment = (
            Payment.objects
            .filter(
                member=member,
                payment_type=PaymentType.MEMBERSHIP,
                status=PaymentStatus.PENDING,
            )
            .order_by("-created_at")
            .first()
        )

        if existing_payment:

            messages.info(
                request,
                (
                    "You already have a pending "
                    "M-Pesa membership payment."
                ),
            )

            return redirect(
                "payments:payment_pending",
                payment_id=existing_payment.id,
            )

        # -------------------------------------------------
        # PHONE NUMBER
        # -------------------------------------------------

        phone_number = (
            request.POST.get(
                "phone_number",
                "",
            )
            .strip()
        )

        if not phone_number:

            messages.error(
                request,
                "Please enter your M-Pesa phone number.",
            )

            return redirect(
                "payments:payment_create"
            )

        # -------------------------------------------------
        # NORMALIZE PHONE
        # -------------------------------------------------

        try:

            normalized_phone = (
                format_phone_number(
                    phone_number
                )
            )

        except ValueError as exc:

            messages.error(
                request,
                str(exc),
            )

            return redirect(
                "payments:payment_create"
            )

        # -------------------------------------------------
        # MEMBERSHIP FEE
        # -------------------------------------------------

        try:

            amount = get_payment_amount()

        except (
            ValueError,
            TypeError,
            InvalidOperation,
        ):

            logger.exception(
                "Invalid KUCSA membership fee configuration."
            )

            messages.error(
                request,
                (
                    "The membership fee is not configured "
                    "correctly."
                ),
            )

            return redirect(
                "payments:payment_create"
            )

        # -------------------------------------------------
        # CREATE PAYMENT
        # -------------------------------------------------

        payment = Payment.objects.create(
            member=member,
            payment_type=PaymentType.MEMBERSHIP,
            amount=amount,
            method=PaymentMethod.MPESA,
            phone_number=normalized_phone,
            status=PaymentStatus.PENDING,
        )

    # =====================================================
    # INITIATE STK PUSH
    #
    # This intentionally happens OUTSIDE the database
    # transaction because Safaricom is an external service.
    # =====================================================

    try:

        stk_response = initiate_stk_push(
            payment=payment,
            phone_number=normalized_phone,
            amount=amount,
            purpose=PaymentType.MEMBERSHIP,
        )

    except Exception:

        logger.exception(
            "Unexpected error initiating membership "
            "STK Push for payment %s.",
            payment.id,
        )

        payment.mark_failed()

        messages.error(
            request,
            (
                "We could not initiate the M-Pesa payment. "
                "Please try again."
            ),
        )

        return redirect(
            "payments:payment_create"
        )

    # =====================================================
    # STK FAILURE
    # =====================================================

    if not stk_response.get("success"):

        payment.mark_failed()

        logger.error(
            "Membership STK Push failed for payment %s: %s",
            payment.id,
            stk_response.get("message"),
        )

        messages.error(
            request,
            stk_response.get(
                "message",
                "Unable to initiate M-Pesa payment.",
            ),
        )

        return redirect(
            "payments:payment_create"
        )

    # =====================================================
    # SAVE DARAJA IDS
    # =====================================================

    merchant_request_id = (
        stk_response.get(
            "merchant_request_id"
        )
    )

    checkout_request_id = (
        stk_response.get(
            "checkout_request_id"
        )
    )

    if not checkout_request_id:

        logger.error(
            "STK Push succeeded without CheckoutRequestID "
            "for payment %s.",
            payment.id,
        )

        payment.mark_failed()

        messages.error(
            request,
            (
                "M-Pesa did not return a valid payment "
                "request ID. Please try again."
            ),
        )

        return redirect(
            "payments:payment_create"
        )

    # -----------------------------------------------------
    # SAVE IDENTIFIERS
    # -----------------------------------------------------

    payment.merchant_request_id = (
        merchant_request_id
    )

    payment.checkout_request_id = (
        checkout_request_id
    )

    payment.save(
        update_fields=[
            "merchant_request_id",
            "checkout_request_id",
            "updated_at",
        ]
    )

    # =====================================================
    # REDIRECT TO PENDING
    # =====================================================

    messages.success(
        request,
        "M-Pesa payment request sent to your phone.",
    )

    return redirect(
        "payments:payment_pending",
        payment_id=payment.id,
    )


# =========================================================
# SUPPORT PAYMENT PAGE
# =========================================================


@login_required
@require_GET
def support_payment_view(request):
    """
    Display the KUCSA support contribution page.

    Support payments are optional.

    They NEVER affect membership status.
    """

    if is_system_admin(request.user):

        messages.info(
            request,
            (
                "System administrators do not use "
                "the member support payment workflow."
            ),
        )

        return redirect(
            "dashboard:dashboard"
        )

    member = get_user_member(
        request.user
    )

    if member is None:

        return redirect_non_member(
            request
        )

    return render(
        request,
        "support_payment.html",
        {
            "member": member,
        },
    )


# =========================================================
# CREATE SUPPORT PAYMENT
# =========================================================


@login_required
@require_POST
def support_payment_submit_view(request):
    """
    Create a KUCSA support contribution and initiate
    an M-Pesa STK Push.

    Support payments NEVER activate membership.
    """

    if is_system_admin(request.user):

        messages.info(
            request,
            (
                "System administrators do not use "
                "the member support payment workflow."
            ),
        )

        return redirect(
            "dashboard:dashboard"
        )

    member = get_user_member(
        request.user
    )

    if member is None:

        return redirect_non_member(
            request
        )

    # -----------------------------------------------------
    # AMOUNT
    # -----------------------------------------------------

    raw_amount = (
        request.POST.get(
            "amount",
            "",
        )
        .strip()
    )

    try:

        amount = get_support_payment_amount(
            raw_amount
        )

    except ValueError as exc:

        messages.error(
            request,
            str(exc),
        )

        return redirect(
            "payments:support"
        )

    # -----------------------------------------------------
    # PHONE
    # -----------------------------------------------------

    phone_number = (
        request.POST.get(
            "phone_number",
            "",
        )
        .strip()
    )

    if not phone_number:

        messages.error(
            request,
            "Please enter your M-Pesa phone number.",
        )

        return redirect(
            "payments:support"
        )

    try:

        normalized_phone = (
            format_phone_number(
                phone_number
            )
        )

    except ValueError as exc:

        messages.error(
            request,
            str(exc),
        )

        return redirect(
            "payments:support"
        )

    # -----------------------------------------------------
    # CREATE PAYMENT
    # -----------------------------------------------------

    payment = Payment.objects.create(
        member=member,
        payment_type=PaymentType.SUPPORT,
        amount=amount,
        method=PaymentMethod.MPESA,
        phone_number=normalized_phone,
        status=PaymentStatus.PENDING,
    )

    # -----------------------------------------------------
    # INITIATE STK PUSH
    # -----------------------------------------------------

    try:

        stk_response = initiate_stk_push(
            payment=payment,
            phone_number=normalized_phone,
            amount=amount,
            purpose=PaymentType.SUPPORT,
        )

    except Exception:

        logger.exception(
            "Unexpected error initiating support "
            "STK Push for payment %s.",
            payment.id,
        )

        payment.mark_failed()

        messages.error(
            request,
            (
                "We could not initiate the support payment. "
                "Please try again."
            ),
        )

        return redirect(
            "payments:support"
        )

    # -----------------------------------------------------
    # FAILURE
    # -----------------------------------------------------

    if not stk_response.get("success"):

        payment.mark_failed()

        logger.error(
            "Support STK Push failed for payment %s: %s",
            payment.id,
            stk_response.get("message"),
        )

        messages.error(
            request,
            stk_response.get(
                "message",
                "Unable to initiate support payment.",
            ),
        )

        return redirect(
            "payments:support"
        )

    # -----------------------------------------------------
    # SAVE REQUEST IDS
    # -----------------------------------------------------

    checkout_request_id = (
        stk_response.get(
            "checkout_request_id"
        )
    )

    merchant_request_id = (
        stk_response.get(
            "merchant_request_id"
        )
    )

    if not checkout_request_id:

        payment.mark_failed()

        logger.error(
            "Support STK Push succeeded without "
            "CheckoutRequestID. Payment=%s",
            payment.id,
        )

        messages.error(
            request,
            (
                "M-Pesa did not return a valid payment "
                "request ID."
            ),
        )

        return redirect(
            "payments:support"
        )

    payment.merchant_request_id = (
        merchant_request_id
    )

    payment.checkout_request_id = (
        checkout_request_id
    )

    payment.save(
        update_fields=[
            "merchant_request_id",
            "checkout_request_id",
            "updated_at",
        ]
    )

    messages.success(
        request,
        "Support payment request sent to your phone.",
    )

    return redirect(
        "payments:payment_pending",
        payment_id=payment.id,
    )


# =========================================================
# PAYMENT PENDING
# =========================================================


@login_required
@require_GET
def payment_pending_view(request, payment_id):
    """
    Display the payment waiting page.

    The page is used for:

        - Membership payments
        - Support payments

    The browser can poll the status endpoint, but it
    cannot modify the payment.
    """

    # -----------------------------------------------------
    # ADMINISTRATOR
    # -----------------------------------------------------

    if is_system_admin(request.user):

        return redirect(
            "dashboard:dashboard"
        )

    # -----------------------------------------------------
    # GET PAYMENT
    # -----------------------------------------------------

    payment = get_object_or_404(
        Payment.objects.select_related(
            "member",
            "member__user",
        ),
        id=payment_id,
        member__user=request.user,
    )

    # -----------------------------------------------------
    # COMPLETED
    # -----------------------------------------------------

    if payment.status == PaymentStatus.COMPLETED:

        return redirect(
            "payments:payment_success",
            payment_id=payment.id,
        )

    # -----------------------------------------------------
    # FAILED / CANCELLED
    # -----------------------------------------------------

    if payment.status in (
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED,
    ):

        return redirect(
            "payments:payment_failed",
            payment_id=payment.id,
        )

    # -----------------------------------------------------
    # PENDING
    # -----------------------------------------------------

    return render(
        request,
        "payment_pending.html",
        {
            "payment": payment,
            "member": payment.member,
            "is_membership_payment": (
                payment.is_membership_payment
            ),
            "is_support_payment": (
                payment.is_support_payment
            ),
        },
    )


# =========================================================
# PAYMENT STATUS
# =========================================================


@login_required
@require_GET
def payment_status_view(request, payment_id):
    """
    Return the current payment status.

    IMPORTANT:

    This endpoint is READ-ONLY.

    It does NOT:

        - contact Safaricom
        - complete payments
        - fail payments
        - activate membership
        - modify database records

    The pending page can safely poll this endpoint.
    """

    # -----------------------------------------------------
    # ADMINISTRATOR
    # -----------------------------------------------------

    if is_system_admin(request.user):

        return JsonResponse(
            {
                "success": False,
                "message": (
                    "Administrators do not use "
                    "membership payments."
                ),
            },
            status=403,
        )

    # -----------------------------------------------------
    # GET PAYMENT
    # -----------------------------------------------------

    payment = get_object_or_404(
        Payment.objects.select_related(
            "member",
            "member__user",
        ),
        id=payment_id,
        member__user=request.user,
    )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return JsonResponse(
        {
            "success": True,

            "payment_id": payment.id,

            "payment_type": payment.payment_type,

            "payment_type_display": (
                payment.get_payment_type_display()
            ),

            "status": payment.status,

            "status_display": (
                payment.get_status_display()
            ),

            "completed": payment.is_completed,

            "failed": (
                payment.is_failed
                or payment.is_cancelled
            ),

            "cancelled": payment.is_cancelled,

            "pending": payment.is_pending,

            "finalized": payment.is_finalized,

            "receipt": payment.mpesa_receipt_number,

            "has_receipt": payment.has_receipt,

            "membership_payment": (
                payment.is_membership_payment
            ),

            "support_payment": (
                payment.is_support_payment
            ),

            "membership_active": (
                payment.member.can_access_platform
            ),

            "completed_at": (
                payment.completed_at.isoformat()
                if payment.completed_at
                else None
            ),

            "transaction_date": (
                payment.transaction_date.isoformat()
                if payment.transaction_date
                else None
            ),
        }
    )


# =========================================================
# PAYMENT SUCCESS
# =========================================================


@login_required
@require_GET
def payment_success_view(request, payment_id):
    """
    Display a successfully completed payment.

    This page is informational only.

    Payment completion must already have been performed
    by the Safaricom callback.
    """

    # -----------------------------------------------------
    # ADMINISTRATOR
    # -----------------------------------------------------

    if is_system_admin(request.user):

        return redirect(
            "dashboard:dashboard"
        )

    # -----------------------------------------------------
    # GET PAYMENT
    # -----------------------------------------------------

    payment = get_object_or_404(
        Payment.objects.select_related(
            "member",
            "member__user",
        ),
        id=payment_id,
        member__user=request.user,
    )

    # -----------------------------------------------------
    # NOT COMPLETED
    # -----------------------------------------------------

    if payment.status != PaymentStatus.COMPLETED:

        if payment.status in (
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
        ):

            return redirect(
                "payments:payment_failed",
                payment_id=payment.id,
            )

        return redirect(
            "payments:payment_pending",
            payment_id=payment.id,
        )

    # -----------------------------------------------------
    # SUCCESS PAGE
    # -----------------------------------------------------

    return render(
        request,
        "payment_success.html",
        {
            "payment": payment,
            "member": payment.member,
        },
    )


# =========================================================
# PAYMENT FAILED
# =========================================================


@login_required
@require_GET
def payment_failed_view(request, payment_id):
    """
    Display a failed or cancelled payment.
    """

    # -----------------------------------------------------
    # ADMINISTRATOR
    # -----------------------------------------------------

    if is_system_admin(request.user):

        return redirect(
            "dashboard:dashboard"
        )

    # -----------------------------------------------------
    # GET PAYMENT
    # -----------------------------------------------------

    payment = get_object_or_404(
        Payment.objects.select_related(
            "member",
            "member__user",
        ),
        id=payment_id,
        member__user=request.user,
    )

    # -----------------------------------------------------
    # SAFETY REDIRECT
    # -----------------------------------------------------

    if payment.status == PaymentStatus.COMPLETED:

        return redirect(
            "payments:payment_success",
            payment_id=payment.id,
        )

    # -----------------------------------------------------
    # FAILED PAGE
    # -----------------------------------------------------

    return render(
        request,
        "payment_failed.html",
        {
            "payment": payment,
            "member": payment.member,
        },
    )


# =========================================================
# PAYMENT HISTORY
# =========================================================

# =========================================================
# PAYMENT HISTORY
# =========================================================


@login_required
@require_GET
def payment_list_view(request):
    """
    Display the authenticated member's payment history.

    Includes:

        - Membership payments
        - Support contributions

    Financial totals are calculated from COMPLETED
    payments only.

    Pending, failed, and cancelled payments are excluded
    from the received-money totals.
    """

    # -----------------------------------------------------
    # ADMINISTRATOR
    # -----------------------------------------------------

    if is_system_admin(request.user):

        messages.info(
            request,
            (
                "System administrators do not have "
                "member payment history."
            ),
        )

        return redirect(
            "dashboard:dashboard"
        )

    # -----------------------------------------------------
    # MEMBER
    # -----------------------------------------------------

    member = get_user_member(
        request.user
    )

    if member is None:

        return redirect_non_member(
            request
        )

    # -----------------------------------------------------
    # ALL PAYMENTS
    # -----------------------------------------------------

    payments = (
        Payment.objects
        .filter(
            member=member
        )
        .order_by(
            "-created_at"
        )
    )

    # -----------------------------------------------------
    # COMPLETED PAYMENTS
    # -----------------------------------------------------
    #
    # Only completed payments represent money actually
    # received by KUCSA.
    #

    completed_payments = payments.filter(
        status=PaymentStatus.COMPLETED
    )

    # -----------------------------------------------------
    # TOTAL RECEIVED
    # -----------------------------------------------------

    total_paid = (
        completed_payments.aggregate(
            total=Sum("amount")
        ).get("total")
        or Decimal("0.00")
    )

    # -----------------------------------------------------
    # MEMBERSHIP TOTAL
    # -----------------------------------------------------

    membership_total = (
        completed_payments
        .filter(
            payment_type=PaymentType.MEMBERSHIP
        )
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or Decimal("0.00")
    )

    # -----------------------------------------------------
    # SUPPORT TOTAL
    # -----------------------------------------------------

    support_total = (
        completed_payments
        .filter(
            payment_type=PaymentType.SUPPORT
        )
        .aggregate(
            total=Sum("amount")
        )
        .get("total")
        or Decimal("0.00")
    )

    # -----------------------------------------------------
    # PAYMENT COUNTS
    # -----------------------------------------------------

    completed_count = (
        completed_payments.count()
    )

    pending_count = (
        payments
        .filter(
            status=PaymentStatus.PENDING
        )
        .count()
    )

    failed_count = (
        payments
        .filter(
            status=PaymentStatus.FAILED
        )
        .count()
    )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return render(
        request,
        "payment_list.html",
        {
            "payments": payments,
            "member": member,

            # Financial totals
            "total_paid": total_paid,
            "membership_total": membership_total,
            "support_total": support_total,

            # Payment statistics
            "completed_count": completed_count,
            "pending_count": pending_count,
            "failed_count": failed_count,
        },
    )


# =========================================================
# PAYMENT DETAIL
# =========================================================


@login_required
@require_GET
def payment_detail_view(request, payment_id):
    """
    Display one payment belonging to the authenticated
    member.
    """

    # -----------------------------------------------------
    # ADMINISTRATOR
    # -----------------------------------------------------

    if is_system_admin(request.user):

        return redirect(
            "dashboard:dashboard"
        )

    # -----------------------------------------------------
    # GET PAYMENT
    # -----------------------------------------------------

    payment = get_object_or_404(
        Payment.objects.select_related(
            "member",
            "member__user",
        ),
        id=payment_id,
        member__user=request.user,
    )

    return render(
        request,
        "payment_detail.html",
        {
            "payment": payment,
            "member": payment.member,
        },
    )


# =========================================================
# M-PESA CALLBACK
# =========================================================


@csrf_exempt
@require_POST
def mpesa_callback_view(request):
    """
    Receive and process Safaricom Daraja STK Push callback.

    This endpoint is called by Safaricom.

    It does NOT require browser authentication.

    CALLBACK FLOW
    -------------

        Safaricom Callback
                ↓
        Parse JSON
                ↓
        Get CheckoutRequestID
                ↓
        Find Payment
                ↓
        Lock Payment
                ↓
        Check idempotency
                ↓
        ResultCode == 0?
             /        \
           YES        NO
            ↓          ↓
        Validate     Mark Failed
        amount
            ↓
        Validate
        receipt
            ↓
        Complete
        payment
            ↓
        MEMBERSHIP?
          /      \
        YES      NO
         ↓        ↓
    Activate    Nothing
    membership   else
         ↓
      ACKNOWLEDGE


    IMPORTANT
    ---------

    Membership activation occurs ONLY after successful
    payment verification.

    Support payments NEVER activate membership.
    """

    # =====================================================
    # PARSE JSON
    # =====================================================

    try:

        data = json.loads(
            request.body.decode("utf-8")
        )

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):

        logger.error(
            "Invalid M-Pesa callback received."
        )

        return JsonResponse(
            {
                "ResultCode": 1,
                "ResultDesc": "Invalid callback data",
            },
            status=400,
        )

    # =====================================================
    # CALLBACK STRUCTURE
    # =====================================================

    stk_callback = (
        data
        .get("Body", {})
        .get("stkCallback")
    )

    if not isinstance(
        stk_callback,
        dict,
    ):

        logger.error(
            "Invalid M-Pesa STK callback structure."
        )

        return JsonResponse(
            {
                "ResultCode": 1,
                "ResultDesc": (
                    "Invalid callback structure"
                ),
            },
            status=400,
        )

    # =====================================================
    # CALLBACK IDENTIFIERS
    # =====================================================

    checkout_request_id = (
        stk_callback.get(
            "CheckoutRequestID"
        )
    )

    merchant_request_id = (
        stk_callback.get(
            "MerchantRequestID"
        )
    )

    result_code = stk_callback.get(
        "ResultCode"
    )

    result_description = (
        stk_callback.get(
            "ResultDesc"
        )
        or ""
    )

    logger.info(
        "M-Pesa callback received. "
        "MerchantRequestID=%s "
        "CheckoutRequestID=%s "
        "ResultCode=%s "
        "ResultDesc=%s",
        merchant_request_id,
        checkout_request_id,
        result_code,
        result_description,
    )

    # =====================================================
    # CHECK CHECKOUT REQUEST ID
    # =====================================================

    if not checkout_request_id:

        logger.error(
            "M-Pesa callback missing CheckoutRequestID."
        )

        return JsonResponse(
            {
                "ResultCode": 1,
                "ResultDesc": (
                    "Missing CheckoutRequestID"
                ),
            },
            status=400,
        )

    # =====================================================
    # FIND PAYMENT
    # =====================================================

    try:

        payment = (
            Payment.objects
            .select_related(
                "member",
                "member__user",
            )
            .get(
                checkout_request_id=(
                    checkout_request_id
                )
            )
        )

    except Payment.DoesNotExist:

        logger.warning(
            "No payment found for "
            "CheckoutRequestID=%s",
            checkout_request_id,
        )

        # -------------------------------------------------
        # IMPORTANT
        # -------------------------------------------------
        #
        # Safaricom has already delivered a structurally
        # valid callback. We acknowledge it even if the
        # payment is unknown to avoid unnecessary retries.
        # -------------------------------------------------

        return JsonResponse(
            {
                "ResultCode": 0,
                "ResultDesc": "Accepted",
            }
        )

    # =====================================================
    # LOCK PAYMENT
    # =====================================================

    try:

        with transaction.atomic():

            payment = (
                Payment.objects
                .select_for_update()
                .select_related(
                    "member",
                    "member__user",
                )
                .get(
                    pk=payment.pk
                )
            )

            # =================================================
            # IDEMPOTENCY
            # =================================================

            if payment.status == PaymentStatus.COMPLETED:

                logger.info(
                    "Payment %s already completed. "
                    "Ignoring duplicate callback.",
                    payment.id,
                )

                return JsonResponse(
                    {
                        "ResultCode": 0,
                        "ResultDesc": "Accepted",
                    }
                )

            # =================================================
            # SUCCESSFUL PAYMENT
            # =================================================

            if str(result_code) == "0":

                callback_metadata = (
                    stk_callback.get(
                        "CallbackMetadata",
                        {},
                    )
                    or {}
                )

                items = (
                    callback_metadata.get(
                        "Item",
                        [],
                    )
                    or []
                )

                metadata = {}

                for item in items:

                    if not isinstance(
                        item,
                        dict,
                    ):
                        continue

                    name = item.get(
                        "Name"
                    )

                    if name:

                        metadata[name] = (
                            item.get("Value")
                        )

                # ---------------------------------------------
                # CALLBACK DATA
                # ---------------------------------------------

                receipt_number = (
                    metadata.get(
                        "MpesaReceiptNumber"
                    )
                )

                amount_paid = (
                    metadata.get(
                        "Amount"
                    )
                )

                transaction_date_raw = (
                    metadata.get(
                        "TransactionDate"
                    )
                )

                # =================================================
                # VALIDATE AMOUNT
                # =================================================

                if amount_paid is None:

                    logger.error(
                        "Successful callback missing "
                        "Amount for payment=%s.",
                        payment.id,
                    )

                    raise ValueError(
                        "Missing payment amount."
                    )

                try:

                    callback_amount = Decimal(
                        str(amount_paid)
                    )

                    expected_amount = Decimal(
                        str(payment.amount)
                    )

                except (
                    InvalidOperation,
                    TypeError,
                    ValueError,
                ) as exc:

                    logger.error(
                        "Invalid callback amount=%s "
                        "for payment=%s",
                        amount_paid,
                        payment.id,
                    )

                    raise ValueError(
                        "Invalid payment amount."
                    ) from exc

                # -------------------------------------------------
                # NORMALIZE TO TWO DECIMAL PLACES
                # -------------------------------------------------

                callback_amount = (
                    callback_amount.quantize(
                        Decimal("0.01")
                    )
                )

                expected_amount = (
                    expected_amount.quantize(
                        Decimal("0.01")
                    )
                )

                # -------------------------------------------------
                # COMPARE
                # -------------------------------------------------

                if callback_amount != expected_amount:

                    logger.error(
                        "Payment amount mismatch. "
                        "Payment=%s Expected=%s Received=%s",
                        payment.id,
                        expected_amount,
                        callback_amount,
                    )

                    raise ValueError(
                        "Payment amount mismatch."
                    )

                # =================================================
                # VALIDATE RECEIPT
                # =================================================

                if not receipt_number:

                    logger.error(
                        "Successful callback missing "
                        "M-Pesa receipt for payment=%s.",
                        payment.id,
                    )

                    raise ValueError(
                        "Missing M-Pesa receipt."
                    )

                receipt_number = str(
                    receipt_number
                ).strip()

                # =================================================
                # TRANSACTION DATE
                # =================================================

                transaction_date = None

                if transaction_date_raw:

                    try:

                        transaction_date = (
                            datetime.strptime(
                                str(
                                    transaction_date_raw
                                ),
                                "%Y%m%d%H%M%S",
                            )
                        )

                        if timezone.is_naive(
                            transaction_date
                        ):

                            transaction_date = (
                                timezone.make_aware(
                                    transaction_date
                                )
                            )

                    except (
                        ValueError,
                        TypeError,
                    ):

                        logger.warning(
                            "Unable to parse M-Pesa "
                            "TransactionDate=%s "
                            "for payment=%s",
                            transaction_date_raw,
                            payment.id,
                        )

                # =================================================
                # COMPLETE PAYMENT
                # =================================================

                payment.mark_completed(
                    receipt_number=receipt_number,
                    transaction_date=transaction_date,
                )

                # =================================================
                # PURPOSE-SPECIFIC ACTION
                # =================================================

                if payment.is_membership_payment:

                    # ---------------------------------------------
                    # MEMBERSHIP PAYMENT
                    # ---------------------------------------------

                    member = payment.member

                    if member is None:

                        logger.error(
                            "Membership payment %s has "
                            "no associated Member.",
                            payment.id,
                        )

                        raise ValueError(
                            "Payment has no associated Member."
                        )

                    # ---------------------------------------------
                    # ACTIVATE MEMBERSHIP
                    # ---------------------------------------------

                    member.activate_membership()

                    logger.info(
                        "Membership payment %s completed. "
                        "Receipt=%s. Member=%s activated.",
                        payment.id,
                        receipt_number,
                        member.id,
                    )

                elif payment.is_support_payment:

                    # ---------------------------------------------
                    # SUPPORT PAYMENT
                    # ---------------------------------------------

                    logger.info(
                        "KUCSA support payment %s completed. "
                        "Receipt=%s. Member=%s.",
                        payment.id,
                        receipt_number,
                        payment.member_id,
                    )

                    # IMPORTANT:
                    #
                    # Do NOT call:
                    #
                    #     member.activate_membership()
                    #
                    # Support payments have no membership
                    # side effects.

                else:

                    logger.error(
                        "Payment %s has unsupported "
                        "payment_type=%s.",
                        payment.id,
                        payment.payment_type,
                    )

                    raise ValueError(
                        "Unsupported payment type."
                    )

            # =====================================================
            # FAILED PAYMENT
            # =====================================================

            else:

                payment.mark_failed()

                logger.info(
                    "Payment %s marked FAILED. "
                    "ResultCode=%s ResultDesc=%s",
                    payment.id,
                    result_code,
                    result_description,
                )

    # =====================================================
    # VALIDATION ERROR
    # =====================================================

    except ValueError as exc:

        logger.error(
            "Payment validation failed for payment=%s: %s",
            payment.id,
            exc,
        )

        return JsonResponse(
            {
                "ResultCode": 1,
                "ResultDesc": str(exc),
            },
            status=400,
        )

    # =====================================================
    # UNEXPECTED ERROR
    # =====================================================

    except Exception:

        logger.exception(
            "Unexpected error processing M-Pesa callback "
            "for payment=%s CheckoutRequestID=%s",
            payment.id,
            checkout_request_id,
        )

        # Returning an error allows Safaricom to retry
        # the callback.

        return JsonResponse(
            {
                "ResultCode": 1,
                "ResultDesc": (
                    "Payment processing failed."
                ),
            },
            status=500,
        )

    # =====================================================
    # ACKNOWLEDGE SAFARICOM
    # =====================================================

    return JsonResponse(
        {
            "ResultCode": 0,
            "ResultDesc": "Accepted",
        }
    ) 