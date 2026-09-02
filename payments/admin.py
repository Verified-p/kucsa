# payments/admin.py

from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):

    # =========================================================
    # LIST DISPLAY
    # =========================================================

    list_display = (
        "id",
        "member",
        "amount",
        "phone_number",
        "method",
        "status",
        "mpesa_receipt_number",
        "created_at",
        "completed_at",
    )

    # =========================================================
    # FILTERS
    # =========================================================

    list_filter = (
        "status",
        "method",
        "created_at",
        "completed_at",
    )

    # =========================================================
    # SEARCH
    # =========================================================

    search_fields = (
        "member__user__username",
        "member__user__first_name",
        "member__user__last_name",
        "phone_number",
        "mpesa_receipt_number",
        "checkout_request_id",
        "merchant_request_id",
    )

    # =========================================================
    # READ-ONLY FIELDS
    # =========================================================

    readonly_fields = (
        "created_at",
        "updated_at",
        "completed_at",
        "merchant_request_id",
        "checkout_request_id",
        "mpesa_receipt_number",
        "transaction_date",
    )

    # =========================================================
    # DEFAULT ORDERING
    # =========================================================

    ordering = (
        "-created_at",
    )

    # =========================================================
    # ITEMS PER PAGE
    # =========================================================

    list_per_page = 25

    # =========================================================
    # DATE HIERARCHY
    # =========================================================

    date_hierarchy = "created_at"

    # =========================================================
    # FIELD GROUPING
    # =========================================================

    fieldsets = (
        (
            "Payment Information",
            {
                "fields": (
                    "member",
                    "amount",
                    "method",
                    "status",
                )
            },
        ),

        (
            "M-Pesa Information",
            {
                "fields": (
                    "phone_number",
                    "merchant_request_id",
                    "checkout_request_id",
                    "mpesa_receipt_number",
                    "transaction_date",
                )
            },
        ),

        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "completed_at",
                )
            },
        ),
    )