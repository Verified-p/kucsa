
# finance/urls.py

from django.urls import path

from . import views


app_name = "finance"


urlpatterns = [

    # =====================================================
    # FINANCE DASHBOARD
    # =====================================================

    path(
        "",
        views.dashboard,
        name="dashboard",
    ),

    # =====================================================
    # TRANSACTIONS
    # =====================================================

    path(
        "transactions/",
        views.transactions,
        name="transactions",
    ),

    path(
        "transactions/<int:pk>/",
        views.transaction_detail,
        name="transaction_detail",
    ),

    # =====================================================
    # INCOME
    # =====================================================

    path(
        "income/",
        views.income,
        name="income",
    ),

    # =====================================================
    # EXPENSES
    # =====================================================

    path(
        "expenses/",
        views.expenses,
        name="expenses",
    ),

    path(
        "expenses/create/",
        views.expense_create,
        name="expense_create",
    ),

    path(
        "expenses/<int:pk>/",
        views.expense_detail,
        name="expense_detail",
    ),

    path(
        "expenses/<int:pk>/submit/",
        views.expense_submit,
        name="expense_submit",
    ),

    path(
        "expenses/<int:pk>/approve/",
        views.expense_approve,
        name="expense_approve",
    ),

    path(
        "expenses/<int:pk>/reject/",
        views.expense_reject,
        name="expense_reject",
    ),

    path(
        "expenses/<int:pk>/pay/",
        views.expense_pay,
        name="expense_pay",
    ),

    path(
        "expenses/<int:pk>/void/",
        views.expense_void,
        name="expense_void",
    ),

    # =====================================================
    # CATEGORIES
    # =====================================================

    path(
        "categories/",
        views.category_list,
        name="categories",
    ),

    path(
        "categories/create/",
        views.category_create,
        name="category_create",
    ),

    path(
        "categories/<int:pk>/edit/",
        views.category_update,
        name="category_edit",
    ),

    path(
        "categories/<int:pk>/toggle/",
        views.category_toggle,
        name="category_toggle",
    ),

    # =====================================================
    # RECONCILIATION
    # =====================================================

    path(
        "reconciliation/",
        views.reconciliation,
        name="reconciliation",
    ),

    path(
        "reconciliation/<int:pk>/",
        views.reconciliation_detail,
        name="reconciliation_detail",
    ),

    # =====================================================
    # AUDIT LOGS
    # =====================================================

    path(
        "audit-logs/",
        views.audit_logs,
        name="audit_logs",
    ),
]
