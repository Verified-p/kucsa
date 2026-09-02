# payments/urls.py

"""
KUCSA Payment URL Configuration
===============================

Payment lifecycle
-----------------

    Membership Payment
          │
          ▼
    /payments/create/
          │
          ▼
    /payments/create/submit/
          │
          ▼
    M-Pesa STK Push
          │
          ▼
    /payments/pending/<payment_id>/
          │
          ├──► /payments/<payment_id>/status/
          │
          ▼
    Safaricom Callback
          │
          ├──► COMPLETED
          │       │
          │       ▼
          │   /payments/<payment_id>/success/
          │
          └──► FAILED
                  │
                  ▼
              /payments/<payment_id>/failed/


IMPORTANT
---------

The browser NEVER completes a payment.

The browser only:

    1. Creates a payment.
    2. Displays the pending page.
    3. Polls the payment status endpoint.
    4. Redirects according to the database status.

Only the Safaricom callback is allowed to complete
the payment.
"""

from django.urls import path

from . import views


app_name = "payments"


urlpatterns = [

    # =========================================================
    # MEMBERSHIP PAYMENT
    # =========================================================

    # Display membership payment form.
    #
    # GET:
    #     /payments/create/
    #
    path(
        "create/",
        views.payment_create_view,
        name="payment_create",
    ),

    # Submit membership payment request.
    #
    # POST:
    #     /payments/create/submit/
    #
    # This creates a PENDING payment and initiates
    # the M-Pesa STK Push.
    #
    path(
        "create/submit/",
        views.payment_create_submit_view,
        name="payment_create_submit",
    ),

    # =========================================================
    # SUPPORT PAYMENT
    # =========================================================

    # Display optional KUCSA support contribution form.
    #
    # GET:
    #     /payments/support/
    #
    path(
        "support/",
        views.support_payment_view,
        name="support",
    ),

    # Submit KUCSA support contribution.
    #
    # POST:
    #     /payments/support/submit/
    #
    path(
        "support/submit/",
        views.support_payment_submit_view,
        name="support_submit",
    ),

    # =========================================================
    # PAYMENT PENDING
    # =========================================================

    # Display the payment waiting page.
    #
    # GET:
    #     /payments/pending/<payment_id>/
    #
    # The pending page polls the status endpoint.
    #
    path(
        "pending/<int:payment_id>/",
        views.payment_pending_view,
        name="payment_pending",
    ),

    # =========================================================
    # PAYMENT STATUS
    # =========================================================

    # AJAX / JavaScript endpoint used by the pending page.
    #
    # GET:
    #     /payments/<payment_id>/status/
    #
    # IMPORTANT:
    #     This endpoint ONLY reads the current database state.
    #
    path(
        "<int:payment_id>/status/",
        views.payment_status_view,
        name="payment_status",
    ),

    # =========================================================
    # PAYMENT SUCCESS
    # =========================================================

    # Display completed payment.
    #
    # GET:
    #     /payments/<payment_id>/success/
    #
    path(
        "<int:payment_id>/success/",
        views.payment_success_view,
        name="payment_success",
    ),

    # =========================================================
    # PAYMENT FAILED
    # =========================================================

    # Display failed/cancelled payment.
    #
    # GET:
    #     /payments/<payment_id>/failed/
    #
    path(
        "<int:payment_id>/failed/",
        views.payment_failed_view,
        name="payment_failed",
    ),

    # =========================================================
    # M-PESA DARAJA CALLBACK
    # =========================================================

    # Safaricom calls this endpoint after processing
    # the STK Push.
    #
    # POST:
    #     /payments/mpesa/callback/
    #
    # IMPORTANT:
    #
    # This endpoint:
    #
    #     - does NOT require login
    #     - is CSRF exempt
    #     - validates the Safaricom callback
    #     - finds the payment
    #     - verifies amount
    #     - verifies receipt
    #     - completes/fails the payment
    #     - activates membership for MEMBERSHIP payments
    #
    # The callback is the authoritative source for
    # payment completion.
    #
    path(
        "mpesa/callback/",
        views.mpesa_callback_view,
        name="mpesa_callback",
    ),

    # =========================================================
    # PAYMENT HISTORY
    # =========================================================

    # Display all payments belonging to the authenticated
    # member.
    #
    # GET:
    #     /payments/
    #
    path(
        "",
        views.payment_list_view,
        name="payment_list",
    ),

    # =========================================================
    # PAYMENT DETAIL
    # =========================================================

    # Display one payment belonging to the authenticated
    # member.
    #
    # GET:
    #     /payments/<payment_id>/
    #
    # This generic route MUST remain after the more specific
    # payment routes above.
    #
    path(
        "<int:payment_id>/",
        views.payment_detail_view,
        name="payment_detail",
    ),
]