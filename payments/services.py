# payments/services.py

"""
KUCSA Payment Services
======================

Centralized payment-processing services for the KUCSA platform.

Supported payment types
-----------------------

1. MEMBERSHIP
   Payment for KUCSA membership.

2. SUPPORT
   Voluntary financial support/contribution toward KUCSA.

M-Pesa flow
-----------

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
    Purpose-specific action

Membership:
    Payment completed
        ↓
    Activate / renew membership

Support:
    Payment completed
        ↓
    Record contribution
        ↓
    NO membership activation

IMPORTANT
---------

This service is responsible for:

    - Safaricom authentication
    - STK password generation
    - Kenyan phone normalization
    - STK Push initiation
    - Payment-type validation
    - Payment-purpose configuration

This service does NOT:

    - activate membership directly
    - record membership activation directly
    - render templates
    - redirect users
    - decide permissions
    - manually mark payments completed

Payment completion must come from the Safaricom callback.
"""

import base64
import logging
from decimal import Decimal, InvalidOperation

import requests

from django.conf import settings
from django.utils import timezone


logger = logging.getLogger(__name__)


# =========================================================
# DARAJA BASE URLS
# =========================================================

DARAJA_SANDBOX_BASE_URL = (
    "https://sandbox.safaricom.co.ke"
)

DARAJA_PRODUCTION_BASE_URL = (
    "https://api.safaricom.co.ke"
)


# =========================================================
# PAYMENT TYPES
# =========================================================

PAYMENT_PURPOSE_MEMBERSHIP = "MEMBERSHIP"
PAYMENT_PURPOSE_SUPPORT = "SUPPORT"


# =========================================================
# DARAJA CONFIGURATION
# =========================================================

def get_daraja_base_url():
    """
    Return the correct Safaricom Daraja base URL.

    Supported environments:

        sandbox
        production
    """

    environment = str(
        getattr(
            settings,
            "MPESA_ENVIRONMENT",
            "sandbox",
        )
    ).strip().lower()

    if environment == "production":
        return DARAJA_PRODUCTION_BASE_URL

    return DARAJA_SANDBOX_BASE_URL


# =========================================================
# MEMBERSHIP FEE
# =========================================================

def get_membership_fee():
    """
    Return the configured KUCSA membership fee.

    Django settings:

        KUCSA_MEMBERSHIP_FEE = 500

    Returns:
        Decimal
    """

    fee = getattr(
        settings,
        "KUCSA_MEMBERSHIP_FEE",
        500,
    )

    try:
        fee = Decimal(str(fee))

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as exc:

        logger.exception(
            "Invalid KUCSA_MEMBERSHIP_FEE setting."
        )

        raise ValueError(
            "KUCSA membership fee is not configured correctly."
        ) from exc

    if fee <= Decimal("0.00"):

        raise ValueError(
            "KUCSA membership fee must be greater than zero."
        )

    return fee.quantize(
        Decimal("0.01")
    )


# =========================================================
# SUPPORT AMOUNT
# =========================================================

def validate_support_amount(amount):
    """
    Validate a KUCSA support contribution.

    Support does not have a fixed amount.

    Examples:

        KES 50
        KES 100
        KES 500
        KES 1,000
        KES 5,000

    Returns:
        Decimal
    """

    try:

        amount = Decimal(
            str(amount)
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as exc:

        raise ValueError(
            "Invalid support amount."
        ) from exc

    if amount < Decimal("1.00"):

        raise ValueError(
            "Support contribution must be at least KES 1."
        )

    return amount.quantize(
        Decimal("0.01")
    )


# =========================================================
# GENERIC PAYMENT AMOUNT VALIDATION
# =========================================================

def validate_payment_amount(amount):
    """
    Validate and normalize a payment amount.

    Returns:
        Decimal
    """

    try:

        amount = Decimal(
            str(amount)
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as exc:

        raise ValueError(
            "Invalid payment amount."
        ) from exc

    if amount <= Decimal("0.00"):

        raise ValueError(
            "Payment amount must be greater than zero."
        )

    return amount.quantize(
        Decimal("0.01")
    )


# =========================================================
# PHONE NUMBER
# =========================================================

def format_phone_number(phone_number):
    """
    Convert a Kenyan phone number into the format
    required by Safaricom Daraja.

    Examples:

        0712345678
            ↓
        254712345678

        0112345678
            ↓
        254112345678

        +254712345678
            ↓
        254712345678

        254712345678
            ↓
        254712345678
    """

    if phone_number is None:

        raise ValueError(
            "Phone number is required."
        )

    phone_number = str(
        phone_number
    ).strip()

    phone_number = (
        phone_number
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if phone_number.startswith("+254"):

        phone_number = phone_number[1:]

    elif phone_number.startswith("0"):

        phone_number = (
            "254"
            + phone_number[1:]
        )

    if not phone_number.startswith("254"):

        raise ValueError(
            "Invalid Kenyan phone number. "
            "Use a number such as 0712345678."
        )

    if len(phone_number) != 12:

        raise ValueError(
            "Invalid Kenyan phone number length."
        )

    if not phone_number[3:].isdigit():

        raise ValueError(
            "Invalid Kenyan phone number."
        )

    return phone_number


# =========================================================
# SAFE PHONE LOGGING
# =========================================================

def mask_phone_number(phone_number):
    """
    Mask a phone number before writing it to logs.

    Example:

        254712345678
            ↓
        2547******78
    """

    if not phone_number:
        return "unknown"

    phone_number = str(phone_number)

    if len(phone_number) <= 6:
        return "***"

    return (
        phone_number[:4]
        + "******"
        + phone_number[-2:]
    )


# =========================================================
# MPESA ACCESS TOKEN
# =========================================================

def get_mpesa_access_token():
    """
    Authenticate with Safaricom Daraja and return
    an OAuth access token.
    """

    consumer_key = str(
        getattr(
            settings,
            "MPESA_CONSUMER_KEY",
            "",
        )
    ).strip()

    consumer_secret = str(
        getattr(
            settings,
            "MPESA_CONSUMER_SECRET",
            "",
        )
    ).strip()

    if not consumer_key:

        raise ValueError(
            "MPESA_CONSUMER_KEY is not configured."
        )

    if not consumer_secret:

        raise ValueError(
            "MPESA_CONSUMER_SECRET is not configured."
        )

    credentials = (
        f"{consumer_key}:{consumer_secret}"
    )

    encoded_credentials = (
        base64.b64encode(
            credentials.encode("utf-8")
        )
        .decode("utf-8")
    )

    url = (
        f"{get_daraja_base_url()}"
        "/oauth/v1/generate"
        "?grant_type=client_credentials"
    )

    headers = {
        "Authorization": (
            f"Basic {encoded_credentials}"
        ),
        "Content-Type": "application/json",
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=30,
        )

    except requests.RequestException as exc:

        logger.exception(
            "Could not connect to the M-Pesa OAuth endpoint."
        )

        raise RuntimeError(
            "Unable to connect to M-Pesa."
        ) from exc

    if response.status_code != 200:

        logger.error(
            "M-Pesa OAuth failed. "
            "Status=%s Response=%s",
            response.status_code,
            response.text,
        )

        raise RuntimeError(
            "Unable to authenticate with M-Pesa."
        )

    try:

        data = response.json()

    except ValueError as exc:

        logger.error(
            "M-Pesa OAuth returned invalid JSON."
        )

        raise RuntimeError(
            "Invalid response received from M-Pesa."
        ) from exc

    access_token = data.get(
        "access_token"
    )

    if not access_token:

        logger.error(
            "M-Pesa OAuth response did not contain "
            "an access token."
        )

        raise RuntimeError(
            "M-Pesa access token was not returned."
        )

    return access_token


# =========================================================
# STK PASSWORD
# =========================================================

def generate_stk_password():
    """
    Generate the Base64 password required for
    Lipa na M-Pesa Online STK Push.

    Returns:

        (
            password,
            timestamp,
        )
    """

    shortcode = str(
        getattr(
            settings,
            "MPESA_SHORTCODE",
            "",
        )
    ).strip()

    passkey = str(
        getattr(
            settings,
            "MPESA_PASSKEY",
            "",
        )
    ).strip()

    if not shortcode:

        raise ValueError(
            "MPESA_SHORTCODE is not configured."
        )

    if not passkey:

        raise ValueError(
            "MPESA_PASSKEY is not configured."
        )

    timestamp = timezone.now().strftime(
        "%Y%m%d%H%M%S"
    )

    raw_password = (
        f"{shortcode}"
        f"{passkey}"
        f"{timestamp}"
    )

    password = (
        base64.b64encode(
            raw_password.encode("utf-8")
        )
        .decode("utf-8")
    )

    return password, timestamp


# =========================================================
# PAYMENT PURPOSE NORMALIZATION
# =========================================================

def normalize_payment_purpose(purpose):
    """
    Normalize a payment purpose.

    Supported:

        MEMBERSHIP
        SUPPORT

    Common aliases are also accepted.
    """

    if purpose is None:

        return PAYMENT_PURPOSE_MEMBERSHIP

    value = getattr(
        purpose,
        "value",
        purpose,
    )

    value = str(
        value
    ).strip().upper()

    value = value.replace("-", "_")

    if value in {
        "MEMBERSHIP",
        "MEMBERSHIP_PAYMENT",
        "MEMBERSHIP_FEE",
        "FEE",
    }:

        return PAYMENT_PURPOSE_MEMBERSHIP

    if value in {
        "SUPPORT",
        "DONATION",
        "DONATIONS",
        "CONTRIBUTION",
        "CONTRIBUTIONS",
        "CLUB_SUPPORT",
        "CLUB_SUPPORT_PAYMENT",
    }:

        return PAYMENT_PURPOSE_SUPPORT

    raise ValueError(
        "Unsupported payment purpose."
    )


# =========================================================
# PAYMENT PURPOSE FROM PAYMENT OBJECT
# =========================================================

def get_payment_purpose(payment):
    """
    Determine the payment purpose from the Payment object.

    IMPORTANT:

    The current Payment model uses:

        payment.payment_type

    Therefore payment_type is the primary source.

    Older names are supported only for backwards compatibility:

        payment.purpose
        payment.payment_purpose

    Existing payments without a recognized purpose are
    treated as MEMBERSHIP payments for backwards
    compatibility.
    """

    # -----------------------------------------------------
    # CURRENT MODEL FIELD
    # -----------------------------------------------------

    payment_type = getattr(
        payment,
        "payment_type",
        None,
    )

    if payment_type is not None:

        return normalize_payment_purpose(
            payment_type
        )

    # -----------------------------------------------------
    # BACKWARDS COMPATIBILITY
    # -----------------------------------------------------

    purpose = getattr(
        payment,
        "purpose",
        None,
    )

    if purpose is not None:

        return normalize_payment_purpose(
            purpose
        )

    payment_purpose = getattr(
        payment,
        "payment_purpose",
        None,
    )

    if payment_purpose is not None:

        return normalize_payment_purpose(
            payment_purpose
        )

    # -----------------------------------------------------
    # LEGACY RECORDS
    # -----------------------------------------------------

    return PAYMENT_PURPOSE_MEMBERSHIP


# =========================================================
# PAYMENT PURPOSE DETAILS
# =========================================================

def get_payment_purpose_details(
    purpose=PAYMENT_PURPOSE_MEMBERSHIP,
):
    """
    Return Safaricom transaction details according to
    payment purpose.

    MEMBERSHIP:

        AccountReference:
            KUCSA

        Description:
            KUCSA Membership Payment

    SUPPORT:

        AccountReference:
            KUCSASUPPORT

        Description:
            KUCSA Club Support
    """

    purpose = normalize_payment_purpose(
        purpose
    )

    if purpose == PAYMENT_PURPOSE_SUPPORT:

        account_reference = str(
            getattr(
                settings,
                "MPESA_SUPPORT_ACCOUNT_REFERENCE",
                "KUCSASUPPORT",
            )
        ).strip()

        transaction_description = str(
            getattr(
                settings,
                "MPESA_SUPPORT_TRANSACTION_DESCRIPTION",
                "KUCSA Club Support",
            )
        ).strip()

        return {
            "purpose": purpose,
            "account_reference": (
                account_reference
            ),
            "transaction_description": (
                transaction_description
            ),
        }

    account_reference = str(
        getattr(
            settings,
            "MPESA_ACCOUNT_REFERENCE",
            "KUCSA",
        )
    ).strip()

    transaction_description = str(
        getattr(
            settings,
            "MPESA_TRANSACTION_DESCRIPTION",
            "KUCSA Membership Payment",
        )
    ).strip()

    return {
        "purpose": purpose,
        "account_reference": (
            account_reference
        ),
        "transaction_description": (
            transaction_description
        ),
    }


# =========================================================
# STK PUSH CONFIGURATION
# =========================================================

def get_stk_push_configuration(
    purpose=PAYMENT_PURPOSE_MEMBERSHIP,
):
    """
    Return configuration required for an STK Push.
    """

    shortcode = str(
        getattr(
            settings,
            "MPESA_SHORTCODE",
            "",
        )
    ).strip()

    transaction_type = str(
        getattr(
            settings,
            "MPESA_TRANSACTION_TYPE",
            "CustomerPayBillOnline",
        )
    ).strip()

    callback_url = str(
        getattr(
            settings,
            "MPESA_CALLBACK_URL",
            "",
        )
    ).strip()

    if not shortcode:

        raise ValueError(
            "MPESA_SHORTCODE is not configured."
        )

    if not callback_url:

        raise ValueError(
            "MPESA_CALLBACK_URL is not configured."
        )

    purpose_details = (
        get_payment_purpose_details(
            purpose
        )
    )

    return {
        "shortcode": shortcode,
        "transaction_type": transaction_type,
        "callback_url": callback_url,
        "account_reference": (
            purpose_details[
                "account_reference"
            ]
        ),
        "transaction_description": (
            purpose_details[
                "transaction_description"
            ]
        ),
        "purpose": purpose_details[
            "purpose"
        ],
    }


# =========================================================
# STK PUSH
# =========================================================

def initiate_stk_push(
    payment,
    phone_number,
    amount,
    purpose=None,
):
    """
    Initiate an M-Pesa STK Push.

    Supports:

        - Membership payment
        - KUCSA support contribution

    If purpose is omitted, the Payment object's
    payment_type is used.

    This function ONLY communicates with Safaricom.

    It does NOT:

        - complete the Payment
        - activate membership
        - record support as completed
        - redirect the user

    Safaricom callback processing is responsible for
    final payment confirmation.
    """

    payment_id = getattr(
        payment,
        "id",
        "unknown",
    )

    # =====================================================
    # DETERMINE PAYMENT PURPOSE
    # =====================================================

    try:

        if purpose is None:

            purpose = get_payment_purpose(
                payment
            )

        else:

            purpose = normalize_payment_purpose(
                purpose
            )

    except ValueError as exc:

        logger.warning(
            "Invalid payment purpose for payment %s: %s",
            payment_id,
            exc,
        )

        return {
            "success": False,
            "message": str(exc),
        }

    # =====================================================
    # FORMAT PHONE NUMBER
    # =====================================================

    try:

        phone_number = format_phone_number(
            phone_number
        )

    except ValueError as exc:

        logger.warning(
            "Invalid phone number for payment %s: %s",
            payment_id,
            exc,
        )

        return {
            "success": False,
            "message": str(exc),
        }

    # =====================================================
    # VALIDATE AMOUNT
    # =====================================================

    try:

        amount = validate_payment_amount(
            amount
        )

    except ValueError as exc:

        return {
            "success": False,
            "message": str(exc),
        }

    # =====================================================
    # STK PUSH CONFIGURATION
    # =====================================================

    try:

        configuration = (
            get_stk_push_configuration(
                purpose
            )
        )

    except ValueError as exc:

        logger.error(
            "M-Pesa configuration error "
            "for payment %s: %s",
            payment_id,
            exc,
        )

        return {
            "success": False,
            "message": str(exc),
        }

    shortcode = configuration[
        "shortcode"
    ]

    transaction_type = configuration[
        "transaction_type"
    ]

    callback_url = configuration[
        "callback_url"
    ]

    account_reference = configuration[
        "account_reference"
    ]

    transaction_description = configuration[
        "transaction_description"
    ]

    # =====================================================
    # ACCESS TOKEN
    # =====================================================

    try:

        access_token = (
            get_mpesa_access_token()
        )

    except Exception as exc:

        logger.exception(
            "Could not obtain M-Pesa access token "
            "for payment %s.",
            payment_id,
        )

        return {
            "success": False,
            "message": (
                "Unable to connect to M-Pesa. "
                "Please try again."
            ),
        }

    # =====================================================
    # STK PASSWORD
    # =====================================================

    try:

        password, timestamp = (
            generate_stk_password()
        )

    except Exception as exc:

        logger.exception(
            "Could not generate STK password "
            "for payment %s.",
            payment_id,
        )

        return {
            "success": False,
            "message": (
                "Unable to prepare M-Pesa payment."
            ),
        }

    # =====================================================
    # STK PAYLOAD
    # =====================================================

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": transaction_type,
        "Amount": int(amount),
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": callback_url,
        "AccountReference": account_reference,
        "TransactionDesc": transaction_description,
    }

    # =====================================================
    # REQUEST URL
    # =====================================================

    url = (
        f"{get_daraja_base_url()}"
        "/mpesa/stkpush/v1/processrequest"
    )

    headers = {
        "Authorization": (
            f"Bearer {access_token}"
        ),
        "Content-Type": "application/json",
    }

    # =====================================================
    # SAFE LOGGING
    # =====================================================

    logger.info(
        "Initiating M-Pesa STK Push. "
        "Payment=%s Purpose=%s Amount=%s Phone=%s",
        payment_id,
        purpose,
        amount,
        mask_phone_number(phone_number),
    )

    # =====================================================
    # SEND STK PUSH
    # =====================================================

    try:

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30,
        )

    except requests.RequestException as exc:

        logger.exception(
            "STK Push request failed "
            "for payment %s.",
            payment_id,
        )

        return {
            "success": False,
            "message": (
                "Could not connect to M-Pesa. "
                "Please try again."
            ),
        }

    # =====================================================
    # PARSE RESPONSE
    # =====================================================

    try:

        data = response.json()

    except ValueError:

        logger.error(
            "Invalid STK Push response. "
            "Status=%s Response=%s",
            response.status_code,
            response.text,
        )

        return {
            "success": False,
            "message": (
                "Invalid response received "
                "from M-Pesa."
            ),
        }

    logger.info(
        "STK Push response for payment %s: "
        "HTTP=%s ResponseCode=%s",
        payment_id,
        response.status_code,
        data.get("ResponseCode"),
    )

    # =====================================================
    # SUCCESS
    # =====================================================

    if (
        response.status_code == 200
        and str(
            data.get("ResponseCode")
        ) == "0"
    ):

        merchant_request_id = data.get(
            "MerchantRequestID"
        )

        checkout_request_id = data.get(
            "CheckoutRequestID"
        )

        if not checkout_request_id:

            logger.error(
                "M-Pesa returned success but "
                "CheckoutRequestID was missing "
                "for payment %s.",
                payment_id,
            )

            return {
                "success": False,
                "message": (
                    "M-Pesa did not return a valid "
                    "payment request ID."
                ),
            }

        return {
            "success": True,
            "purpose": purpose,
            "merchant_request_id": (
                merchant_request_id
            ),
            "checkout_request_id": (
                checkout_request_id
            ),
            "customer_message": data.get(
                "CustomerMessage",
                (
                    "Please check your phone and "
                    "enter your M-Pesa PIN."
                ),
            ),
            "response_code": data.get(
                "ResponseCode"
            ),
            "response_description": data.get(
                "ResponseDescription"
            ),
        }

    # =====================================================
    # FAILURE
    # =====================================================

    error_message = (
        data.get("errorMessage")
        or data.get("ResponseDescription")
        or data.get("ResultDesc")
        or (
            "M-Pesa STK Push could not "
            "be initiated."
        )
    )

    logger.error(
        "STK Push failed for payment %s: %s",
        payment_id,
        error_message,
    )

    return {
        "success": False,
        "message": error_message,
        "response_code": data.get(
            "ResponseCode"
        ),
        "error_code": data.get(
            "errorCode"
        ),
    }


# =========================================================
# MEMBERSHIP PAYMENT CHECK
# =========================================================

def is_membership_payment(payment):
    """
    Return True when the payment is a membership payment.
    """

    try:

        return (
            get_payment_purpose(payment)
            == PAYMENT_PURPOSE_MEMBERSHIP
        )

    except ValueError:

        return False


# =========================================================
# SUPPORT PAYMENT CHECK
# =========================================================

def is_support_payment(payment):
    """
    Return True when the payment is a KUCSA support
    contribution.
    """

    try:

        return (
            get_payment_purpose(payment)
            == PAYMENT_PURPOSE_SUPPORT
        )

    except ValueError:

        return False


# =========================================================
# PAYMENT PURPOSE DISPLAY
# =========================================================

def get_payment_purpose_display(payment):
    """
    Return a human-readable payment purpose.

    Examples:

        Membership Payment
        KUCSA Support
    """

    purpose = get_payment_purpose(
        payment
    )

    if purpose == PAYMENT_PURPOSE_SUPPORT:

        return "KUCSA Support"

    return "Membership Payment"
