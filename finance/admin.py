
# finance/admin.py

"""
KUCSA Finance Admin
===================

Django admin configuration for the KUCSA Finance application.

The admin interface provides controlled access to:

    - Financial Categories
    - Financial Transactions
    - Expenses
    - Financial Reconciliations
    - Financial Audit Logs

Financial audit logs are intentionally read-only.
"""

from django.contrib import admin

from .models import (
    FinancialCategory,
    FinancialTransaction,
    Expense,
    FinancialReconciliation,
    FinancialAuditLog,
)


# =========================================================
# FINANCIAL CATEGORY
# =========================================================

@admin.register(FinancialCategory)
class FinancialCategoryAdmin(admin.ModelAdmin):
    """
    Admin configuration for financial categories.
    """

    list_display = (
        "name",
        "category_type",
        "is_active",
        "is_system",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "category_type",
        "is_active",
        "is_system",
    )

    search_fields = (
        "name",
        "description",
    )

    ordering = (
        "category_type",
        "name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    list_editable = (
        "is_active",
    )


# =========================================================
# FINANCIAL TRANSACTION
# =========================================================

@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    """
    Admin configuration for financial transactions.

    Posted and voided transactions should normally be
    controlled through the application rather than casually
    edited through Django admin.
    """

    list_display = (
        "transaction_number",
        "transaction_type",
        "amount",
        "category",
        "status",
        "payment_source",
        "member",
        "transaction_date",
        "posted_at",
    )

    list_filter = (
        "transaction_type",
        "status",
        "payment_source",
        "category",
        "transaction_date",
    )

    search_fields = (
        "transaction_number",
        "reference",
        "description",
        "notes",
        "member__user__username",
        "member__user__first_name",
        "member__user__last_name",
        "payment__mpesa_receipt_number",
    )

    ordering = (
        "-transaction_date",
        "-created_at",
    )

    readonly_fields = (
        "transaction_number",
        "posted_at",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "category",
        "payment",
        "member",
        "recorded_by",
    )

    date_hierarchy = "transaction_date"

    fieldsets = (
        (
            "Transaction",
            {
                "fields": (
                    "transaction_number",
                    "transaction_type",
                    "status",
                    "category",
                    "amount",
                )
            },
        ),
        (
            "Description",
            {
                "fields": (
                    "description",
                    "reference",
                    "notes",
                )
            },
        ),
        (
            "Payment",
            {
                "fields": (
                    "payment_source",
                    "payment",
                )
            },
        ),
        (
            "Member",
            {
                "fields": (
                    "member",
                )
            },
        ),
        (
            "Accounting",
            {
                "fields": (
                    "recorded_by",
                    "transaction_date",
                    "posted_at",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )


# =========================================================
# EXPENSE
# =========================================================

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    """
    Admin configuration for expenses.

    Expense workflow:

        DRAFT
        SUBMITTED
        APPROVED
        PAID

    Alternative states:

        REJECTED
        VOIDED
    """

    list_display = (
        "expense_number",
        "title",
        "amount",
        "category",
        "status",
        "payment_source",
        "payee",
        "expense_date",
        "recorded_by",
    )

    list_filter = (
        "status",
        "payment_source",
        "category",
        "expense_date",
    )

    search_fields = (
        "expense_number",
        "title",
        "description",
        "payee",
        "payment_reference",
        "notes",
    )

    ordering = (
        "-expense_date",
        "-created_at",
    )

    readonly_fields = (
        "expense_number",
        "submitted_at",
        "approved_at",
        "rejected_at",
        "paid_at",
        "voided_at",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "transaction",
        "category",
        "recorded_by",
        "submitted_by",
        "approved_by",
        "rejected_by",
        "paid_by",
        "voided_by",
    )

    date_hierarchy = "expense_date"

    fieldsets = (
        (
            "Expense",
            {
                "fields": (
                    "expense_number",
                    "title",
                    "description",
                    "category",
                    "amount",
                )
            },
        ),
        (
            "Payee",
            {
                "fields": (
                    "payee",
                    "payment_source",
                    "payment_reference",
                    "receipt",
                )
            },
        ),
        (
            "Workflow",
            {
                "fields": (
                    "status",
                    "transaction",
                )
            },
        ),
        (
            "Workflow Users",
            {
                "fields": (
                    "recorded_by",
                    "submitted_by",
                    "approved_by",
                    "rejected_by",
                    "paid_by",
                    "voided_by",
                )
            },
        ),
        (
            "Workflow Dates",
            {
                "fields": (
                    "expense_date",
                    "submitted_at",
                    "approved_at",
                    "rejected_at",
                    "paid_at",
                    "voided_at",
                )
            },
        ),
        (
            "Reasons",
            {
                "fields": (
                    "rejection_reason",
                    "void_reason",
                )
            },
        ),
        (
            "Notes",
            {
                "fields": (
                    "notes",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )


# =========================================================
# FINANCIAL RECONCILIATION
# =========================================================

@admin.register(FinancialReconciliation)
class FinancialReconciliationAdmin(admin.ModelAdmin):
    """
    Admin configuration for financial reconciliation.

    The model uses `source` to identify the external
    statement source:

        MPESA
        BANK
        CASH
        OTHER
    """

    list_display = (
        "reconciliation_number",
        "source",
        "statement_reference",
        "period_start",
        "period_end",
        "system_income",
        "external_income",
        "system_expenses",
        "external_expenses",
        "status",
        "reconciled_by",
        "reconciled_at",
    )

    list_filter = (
        "source",
        "status",
        "period_end",
    )

    search_fields = (
        "reconciliation_number",
        "statement_reference",
        "notes",
    )

    ordering = (
        "-period_end",
        "-created_at",
    )

    readonly_fields = (
        "reconciliation_number",
        "reconciled_at",
        "created_at",
        "updated_at",
        "income_difference",
        "expense_difference",
        "net_difference",
        "is_balanced",
    )

    autocomplete_fields = (
        "prepared_by",
        "reconciled_by",
    )

    date_hierarchy = "period_end"

    fieldsets = (
        (
            "Reconciliation",
            {
                "fields": (
                    "reconciliation_number",
                    "source",
                    "statement_reference",
                    "status",
                )
            },
        ),
        (
            "Period",
            {
                "fields": (
                    "period_start",
                    "period_end",
                )
            },
        ),
        (
            "System Records",
            {
                "fields": (
                    "system_income",
                    "system_expenses",
                )
            },
        ),
        (
            "External Statement",
            {
                "fields": (
                    "external_income",
                    "external_expenses",
                    "statement_file",
                )
            },
        ),
        (
            "Differences",
            {
                "fields": (
                    "income_difference",
                    "expense_difference",
                    "net_difference",
                    "is_balanced",
                )
            },
        ),
        (
            "Users",
            {
                "fields": (
                    "prepared_by",
                    "reconciled_by",
                )
            },
        ),
        (
            "Completion",
            {
                "fields": (
                    "reconciled_at",
                    "notes",
                )
            },
        ),
        (
            "System Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )


# =========================================================
# FINANCIAL AUDIT LOG
# =========================================================

@admin.register(FinancialAuditLog)
class FinancialAuditLogAdmin(admin.ModelAdmin):
    """
    Admin configuration for financial audit logs.

    Audit logs are intentionally read-only.
    """

    list_display = (
        "created_at",
        "user",
        "action",
        "transaction",
        "expense",
        "reconciliation",
        "category",
    )

    list_filter = (
        "action",
        "created_at",
    )

    search_fields = (
        "description",
        "user__username",
        "user__first_name",
        "user__last_name",
        "transaction__transaction_number",
        "expense__expense_number",
        "reconciliation__reconciliation_number",
        "category__name",
    )

    ordering = (
        "-created_at",
    )

    readonly_fields = (
        "user",
        "action",
        "transaction",
        "expense",
        "reconciliation",
        "category",
        "description",
        "old_values",
        "new_values",
        "created_at",
    )

    autocomplete_fields = (
        "user",
        "transaction",
        "expense",
        "reconciliation",
        "category",
    )

    def has_add_permission(self, request):
        """
        Audit logs should be created by the finance
        application, not manually from Django admin.
        """

        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        """
        Audit logs cannot be edited.
        """

        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        """
        Audit logs cannot be deleted.
        """

        return False
