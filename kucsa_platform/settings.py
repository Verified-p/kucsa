
"""
Django settings for kucsa_platform project.

KUCSA Digital Computing Community Platform

Development configuration.
For production, move sensitive values such as SECRET_KEY,
database credentials, and M-Pesa credentials to environment
variables.
"""

from dotenv import load_dotenv
import os

load_dotenv()

import dj_database_url

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# =========================================================
# BASE DIRECTORY
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

import os
from dotenv import load_dotenv

load_dotenv()
# ================================
# SECURITY
# ================================
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-dev-key"
)

# False on Vercel / production
DEBUG = os.getenv("VERCEL") is None

ALLOWED_HOSTS = [
    ".vercel.app",
    "localhost",
    "127.0.0.1",
    "freddy-porkiest-rumblingly.ngrok-free.dev", 
    ".ngrok-free.dev",
]


# =========================================================
# APPLICATION DEFINITION
# =========================================================

INSTALLED_APPS = [
    # -----------------------------------------------------
    # Django
    # -----------------------------------------------------

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # -----------------------------------------------------
    # KUCSA Applications
    # -----------------------------------------------------

    "accounts",
    "members",
    "payments",
    "events",
    "attendance",
    "announcements",
    "executives",
    "dashboard",
    "reports",
    "core",
    'finance',
]


# =========================================================
# MIDDLEWARE
# =========================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =========================================================
# URL CONFIGURATION
# =========================================================

ROOT_URLCONF = "kucsa_platform.urls"


# =========================================================
# TEMPLATES
# =========================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        # Global templates directory
        "DIRS": [
            BASE_DIR / "templates",
        ],

        # App templates:
        # payments/templates/payments/...
        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",

                "django.template.context_processors.request",

                "django.contrib.auth.context_processors.auth",

                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# =========================================================
# WSGI
# =========================================================

WSGI_APPLICATION = "kucsa_platform.wsgi.application"


# =========================================================
# DATABASE
# =========================================================

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv("DATABASE_URL"),
        conn_max_age=600
    )
}


# =========================================================
# CUSTOM USER MODEL
# =========================================================

AUTH_USER_MODEL = "accounts.User"


# =========================================================
# AUTHENTICATION REDIRECTS
# =========================================================

LOGIN_URL = "accounts:login"

LOGIN_REDIRECT_URL = "dashboard:dashboard"

LOGOUT_REDIRECT_URL = "accounts:login"


# =========================================================
# PASSWORD VALIDATION
# =========================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =========================================================
# INTERNATIONALIZATION
# =========================================================

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Nairobi'   # ✅ FIXED (important for real system)

USE_I18N = True
USE_TZ = True


# =========================================================
# STATIC FILES
# =========================================================

# ================================
# STATIC FILES
# ================================
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = (
    'whitenoise.storage.CompressedManifestStaticFilesStorage'
)
# =========================================================
# MEDIA FILES
# =========================================================

# Payment proof uploads are stored here.
#
# Example:
# media/
# └── payments/
#     └── proofs/
#         └── 2026/
#             └── 08/
#                 └── receipt.pdf

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# =========================================================
# FILE UPLOAD SETTINGS
# =========================================================

# Maximum request body size.
# Adjust depending on the type of payment proofs allowed.

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024


# =========================================================
# DEFAULT PRIMARY KEY
# =========================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =========================================================
# MESSAGES
# =========================================================

from django.contrib.messages import constants as message_constants

MESSAGE_TAGS = {
    message_constants.DEBUG: "debug",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "error",
}


# =========================================================
# EMAIL
# =========================================================

# Development configuration.
#
# Emails will be printed in the terminal instead of
# actually being sent.

EMAIL_BACKEND = (
    "django.core.mail.backends.console.EmailBackend"
)

DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    "KUCSA <noreply@kucsa.local>",
)


# =========================================================
# M-PESA / SAFARICOM DARAJA
# =========================================================

# These values MUST be provided through environment variables
# in production.



# =========================================================
# SECURITY SETTINGS
# =========================================================

# Development defaults.
#
# These should be enabled/strengthened in production.

SECURE_BROWSER_XSS_FILTER = True

SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = "DENY"

# ================================
# SECURITY HEADERS (PRODUCTION)
# ================================
if not DEBUG:

    SECURE_BROWSER_XSS_FILTER = True

    SECURE_CONTENT_TYPE_NOSNIFF = True

    X_FRAME_OPTIONS = 'DENY'

    SECURE_PROXY_SSL_HEADER = (
        'HTTP_X_FORWARDED_PROTO',
        'https'
    )

    SESSION_COOKIE_SECURE = True

    CSRF_COOKIE_SECURE = True


# =========================================================
# SESSION SETTINGS
# =========================================================

SESSION_COOKIE_HTTPONLY = True

SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SAMESITE = "Lax"


# =========================================================
# CSRF
# =========================================================

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "",
    ).split(",")
    if origin.strip()
]


# =========================================================
# LOGGING
# =========================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "verbose": {
            "format": (
                "{levelname} {asctime} "
                "{module} {process:d} {thread:d} "
                "{message}"
            ),
            "style": "{",
        },

        "simple": {
            "format": (
                "{levelname} {message}"
            ),
            "style": "{",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },

    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },

        "payments": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

KUCSA_MEMBERSHIP_FEE = 1

# =========================================================
# M-PESA DARAJA CONFIGURATION
# =========================================================

MPESA_CONSUMER_KEY = os.getenv(
    "MPESA_CONSUMER_KEY"
)

MPESA_CONSUMER_SECRET = os.getenv(
    "MPESA_CONSUMER_SECRET"
)

MPESA_SHORTCODE = os.getenv(
    "MPESA_SHORTCODE",
    "174379"
)

MPESA_PASSKEY = os.getenv(
    "MPESA_PASSKEY"
)

MPESA_CALLBACK_URL = os.getenv(
    "MPESA_CALLBACK_URL"
)

MPESA_ENVIRONMENT = os.getenv(
    "MPESA_ENVIRONMENT",
    "sandbox"
)


# =========================================================
# M-PESA API URLS
# =========================================================

if MPESA_ENVIRONMENT == "production":

    MPESA_BASE_URL = (
        "https://api.safaricom.co.ke"
    )

else:

    MPESA_BASE_URL = (
        "https://sandbox.safaricom.co.ke"
    )


MPESA_AUTH_URL = (
    f"{MPESA_BASE_URL}/oauth/v1/generate"
)

MPESA_STK_PUSH_URL = (
    f"{MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest"
)


CSRF_TRUSTED_ORIGINS = [
    "https://kucsa.vercel.app",
]

# ── Auto logout after 5 minutes of inactivity ──
SESSION_COOKIE_AGE = 300              # 5 minutes in seconds
SESSION_SAVE_EVERY_REQUEST = True     # reset timer on every request
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # also logout when browser closes