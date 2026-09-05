# finance/views.py

"""
KUCSA Finance Views
===================

Thin HTTP views for the KUCSA Finance application.

Architecture
------------

    URL
      ↓
    VIEW
      ↓
    PERMISSION
      ↓
    SERVICE
      ↓
    MODEL

The Finance application is responsible for:

    - Financial dashboard
    - Income
    - Expenses
    - Transactions
    - Categories
    - Reconciliation
    - Audit logs

IMPORTANT
---------

Views must remain thin.

Financial business logic belongs in:

    finance.services

Authorization belongs in:

    finance.permissions

The Payments application remains responsible for:

    - M-Pesa STK Push
    - Safaricom authentication
    - Callback processing
    - Payment verification
    - Payment status
    - M-Pesa receipt

Finance does not verify M-Pesa payments.

Only completed payments may become financial income.

Only POSTED financial transactions affect the
accounting balance.
"""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    ExpenseForm,
    ExpenseRejectionForm,
    ExpenseVoidForm,
    FinancialCategoryForm,
    FinancialReconciliationForm,
    FinancialTransactionForm,
    ReconciliationCompleteForm,
)

from .models import (
    Expense,
    FinancialAuditLog,
    FinancialCategory,
    FinancialReconciliation,
    FinancialTransaction,
)

from .permissions import (
    can_access_finance_dashboard,
    can_manage_categories,
    can_manage_expenses,
    can_manage_finance,
    can_view_audit_logs,
    can_view_expenses,
    can_view_financial_transactions,
    can_view_reconciliation,
)

from .services import (
    approve_expense,
    create_category,
    create_expense,
    create_reconciliation,
    create_transaction,
    deactivate_category,
    get_audit_logs,
    get_audit_log_totals,
    get_category_totals,
    get_expense_totals,
    get_finance_dashboard_stats,
    get_financial_totals,
    get_income_totals,
    post_transaction,
    reconcile_finance,
    reject_expense,
    submit_expense,
    update_category,
    update_expense,
    void_expense,
    void_transaction,
    pay_expense,
)


# =============================================================================
# CONSTANTS
# =============================================================================

ZERO = Decimal("0.00")


# =============================================================================
# HELPERS
# =============================================================================

def _require_permission(user, permission):
    """
    Raise HTTP 403 when the current user does not have
    the required Finance permission.
    """

    if not permission(user):
        raise PermissionDenied(
            "You do not have permission to access this finance area."
        )


def _redirect_to_expense_detail(expense):
    """
    Redirect to an expense detail page.
    """

    return redirect(
        "finance:expense_detail",
        pk=expense.pk,
    )


def _redirect_to_transaction_detail(financial_transaction):
    """
    Redirect to a transaction detail page.
    """

    return redirect(
        "finance:transaction_detail",
        pk=financial_transaction.pk,
    )


def _redirect_to_reconciliation_detail(reconciliation_record):
    """
    Redirect to a reconciliation detail page.
    """

    return redirect(
        "finance:reconciliation_detail",
        pk=reconciliation_record.pk,
    )


def _handle_validation_error(request, error):
    """
    Convert service/model ValidationError exceptions into
    readable Django messages.
    """

    if hasattr(error, "message_dict"):
        for field, errors in error.message_dict.items():
            for message in errors:
                messages.error(
                    request,
                    f"{field}: {message}",
                )
        return

    if hasattr(error, "messages"):
        for message in error.messages:
            messages.error(
                request,
                message,
            )
        return

    messages.error(
        request,
        str(error),
    )


def _get_selected_filter(request, name):
    """
    Return a cleaned GET filter value.

    Empty values are treated as None.
    """

    value = request.GET.get(
        name,
        "",
    ).strip()

    return value or None


# =============================================================================
# DASHBOARD
# =============================================================================

@login_required
def dashboard(request):
    """
    Display the main Finance dashboard.

    Accounting rule:

        POSTED income
            -
        POSTED expenses
            =
        Available balance

    Draft, submitted and approved expenses do not
    affect the available balance.
    """

    _require_permission(
        request.user,
        can_access_finance_dashboard,
    )

    # -------------------------------------------------------------------------
    # CENTRALIZED FINANCIAL STATISTICS
    # -------------------------------------------------------------------------

    dashboard_stats = get_finance_dashboard_stats()

    financial_totals = get_financial_totals()

    posted_income = financial_totals.get(
        "income",
        ZERO,
    )

    posted_expenses = financial_totals.get(
        "expenses",
        ZERO,
    )

    balance = financial_totals.get(
        "balance",
        posted_income - posted_expenses,
    )

    # -------------------------------------------------------------------------
    # TRANSACTION COUNTS
    # -------------------------------------------------------------------------

    transaction_queryset = FinancialTransaction.objects.all()

    posted_transaction_queryset = transaction_queryset.filter(
        status=FinancialTransaction.Status.POSTED,
    )

    posted_income_queryset = posted_transaction_queryset.filter(
        transaction_type=FinancialTransaction.TransactionType.INCOME,
    )

    posted_expense_queryset = posted_transaction_queryset.filter(
        transaction_type=FinancialTransaction.TransactionType.EXPENSE,
    )

    # -------------------------------------------------------------------------
    # EXPENSE COUNTS
    # -------------------------------------------------------------------------

    expense_queryset = Expense.objects.all()

    # -------------------------------------------------------------------------
    # CATEGORY STATISTICS
    # -------------------------------------------------------------------------

    category_stats = get_category_totals()

    # -------------------------------------------------------------------------
    # RECENT POSTED TRANSACTIONS
    # -------------------------------------------------------------------------

    recent_transactions = (
        FinancialTransaction.objects
        .filter(
            status=FinancialTransaction.Status.POSTED,
        )
        .select_related(
            "category",
            "member",
            "recorded_by",
            "payment",
        )
        .order_by(
            "-transaction_date",
            "-created_at",
        )[:10]
    )

    # -------------------------------------------------------------------------
    # RECENT EXPENSES
    # -------------------------------------------------------------------------

    recent_expenses = (
        Expense.objects
        .select_related(
            "category",
            "recorded_by",
            "submitted_by",
            "approved_by",
            "paid_by",
        )
        .order_by(
            "-expense_date",
            "-created_at",
        )[:10]
    )

    context = {
        # Accounting
        "available_balance": balance,
        "balance": balance,
        "posted_income": posted_income,
        "posted_expenses": posted_expenses,

        # Expense workflow
        "pending_expenses": dashboard_stats.get(
            "pending_expenses",
            0,
        ),
        "paid_expenses": dashboard_stats.get(
            "paid_expenses",
            0,
        ),
        "rejected_expenses": dashboard_stats.get(
            "rejected_expenses",
            0,
        ),

        # Transaction statistics
        "transaction_count": transaction_queryset.count(),
        "posted_transaction_count": (
            posted_transaction_queryset.count()
        ),
        "posted_income_count": (
            posted_income_queryset.count()
        ),
        "posted_expense_count": (
            posted_expense_queryset.count()
        ),

        # Expense records
        "expense_count": expense_queryset.count(),

        # Category statistics
        "category_count": category_stats.get(
            "total_categories",
            0,
        ),
        "active_category_count": category_stats.get(
            "active_categories",
            0,
        ),
        "income_category_count": category_stats.get(
            "income_categories",
            0,
        ),
        "expense_category_count": category_stats.get(
            "expense_categories",
            0,
        ),

        # Recent records
        "recent_transactions": recent_transactions,
        "recent_expenses": recent_expenses,
    }

    return render(
        request,
        "dashboard.html",
        context,
    )


# =============================================================================
# TRANSACTIONS
# =============================================================================

@login_required
def transactions(request):
    """
    Display financial transactions with optional filters.

    Filtered totals shown on this page describe the
    currently displayed transaction queryset.

    They do not replace the global accounting totals.
    """

    _require_permission(
        request.user,
        can_view_financial_transactions,
    )

    queryset = (
        FinancialTransaction.objects
        .select_related(
            "category",
            "member",
            "recorded_by",
            "payment",
        )
        .order_by(
            "-transaction_date",
            "-created_at",
        )
    )

    transaction_type = _get_selected_filter(
        request,
        "type",
    )

    status = _get_selected_filter(
        request,
        "status",
    )

    source = _get_selected_filter(
        request,
        "source",
    )

    if transaction_type:
        queryset = queryset.filter(
            transaction_type=transaction_type,
        )

    if status:
        queryset = queryset.filter(
            status=status,
        )

    if source:
        queryset = queryset.filter(
            payment_source=source,
        )

    # -------------------------------------------------------------------------
    # FILTERED STATISTICS
    # -------------------------------------------------------------------------

    from django.db.models import Sum

    posted_queryset = queryset.filter(
        status=FinancialTransaction.Status.POSTED,
    )

    income_queryset = queryset.filter(
        transaction_type=FinancialTransaction.TransactionType.INCOME,
    )

    expense_queryset = queryset.filter(
        transaction_type=FinancialTransaction.TransactionType.EXPENSE,
    )

    posted_income_queryset = income_queryset.filter(
        status=FinancialTransaction.Status.POSTED,
    )

    posted_expense_queryset = expense_queryset.filter(
        status=FinancialTransaction.Status.POSTED,
    )

    posted_income = (
        posted_income_queryset
        .aggregate(total=Sum("amount"))
        .get("total")
        or ZERO
    )

    posted_expenses = (
        posted_expense_queryset
        .aggregate(total=Sum("amount"))
        .get("total")
        or ZERO
    )

    context = {
        "transactions": queryset,

        "transaction_types": (
            FinancialTransaction.TransactionType.choices
        ),

        "transaction_statuses": (
            FinancialTransaction.Status.choices
        ),

        "payment_sources": (
            FinancialTransaction.PaymentSource.choices
        ),

        "selected_type": transaction_type,
        "selected_status": status,
        "selected_source": source,

        "transaction_count": queryset.count(),

        "posted_transaction_count": (
            posted_queryset.count()
        ),

        "income_count": income_queryset.count(),

        "expense_count": expense_queryset.count(),

        "posted_income": posted_income,

        "posted_expenses": posted_expenses,
    }

    return render(
        request,
        "transactions.html",
        context,
    )


# =============================================================================
# TRANSACTION DETAIL
# =============================================================================

@login_required
def transaction_detail(request, pk):
    """
    Display one financial transaction together with
    its audit history.
    """

    _require_permission(
        request.user,
        can_view_financial_transactions,
    )

    financial_transaction = get_object_or_404(
        FinancialTransaction.objects.select_related(
            "category",
            "member",
            "recorded_by",
            "payment",
        ),
        pk=pk,
    )

    audit_logs = (
        financial_transaction.audit_logs
        .select_related("user")
        .order_by("-created_at")
    )

    return render(
        request,
        "transaction_detail.html",
        {
            "transaction": financial_transaction,
            "audit_logs": audit_logs,
        },
    )


# =============================================================================
# TRANSACTION CREATE
# =============================================================================

@login_required
def transaction_create(request):
    """
    Create a financial transaction.

    Transactions are created as DRAFT.

    Posting is handled separately by the service layer.
    """

    _require_permission(
        request.user,
        can_manage_finance,
    )

    if request.method == "POST":
        form = FinancialTransactionForm(
            request.POST,
        )

        if form.is_valid():
            cleaned = form.cleaned_data

            try:
                financial_transaction = create_transaction(
                    user=request.user,
                    transaction_type=cleaned["transaction_type"],
                    category=cleaned["category"],
                    amount=cleaned["amount"],
                    description=cleaned.get(
                        "description",
                        "",
                    ),
                    reference=cleaned.get(
                        "reference",
                        "",
                    ),
                    payment_source=cleaned.get(
                        "payment_source",
                    ),
                    member=cleaned.get(
                        "member",
                    ),
                    transaction_date=cleaned.get(
                        "transaction_date",
                    ),
                    notes=cleaned.get(
                        "notes",
                        "",
                    ),
                )

                messages.success(
                    request,
                    "Financial transaction created successfully.",
                )

                return _redirect_to_transaction_detail(
                    financial_transaction,
                )

            except ValidationError as error:
                _handle_validation_error(
                    request,
                    error,
                )

    else:
        form = FinancialTransactionForm()

    return render(
        request,
        "transaction_form.html",
        {
            "form": form,
            "transaction": None,
            "page_title": "Create Financial Transaction",
        },
    )


# =============================================================================
# TRANSACTION POST
# =============================================================================

@login_required
def transaction_post(request, pk):
    """
    Post a draft financial transaction.
    """

    _require_permission(
        request.user,
        can_manage_finance,
    )

    if request.method != "POST":
        return redirect(
            "finance:transaction_detail",
            pk=pk,
        )

    financial_transaction = get_object_or_404(
        FinancialTransaction,
        pk=pk,
    )

    try:
        post_transaction(
            user=request.user,
            financial_transaction=financial_transaction,
        )

        messages.success(
            request,
            "Financial transaction posted successfully.",
        )

    except ValidationError as error:
        _handle_validation_error(
            request,
            error,
        )

    return _redirect_to_transaction_detail(
        financial_transaction,
    )


# =============================================================================
# TRANSACTION VOID
# =============================================================================

@login_required
def transaction_void(request, pk):
    """
    Void a financial transaction.

    Voiding preserves financial history.
    """

    _require_permission(
        request.user,
        can_manage_finance,
    )

    if request.method != "POST":
        return redirect(
            "finance:transaction_detail",
            pk=pk,
        )

    financial_transaction = get_object_or_404(
        FinancialTransaction,
        pk=pk,
    )

    try:
        void_transaction(
            user=request.user,
            financial_transaction=financial_transaction,
        )

        messages.success(
            request,
            "Financial transaction voided successfully.",
        )

    except ValidationError as error:
        _handle_validation_error(
            request,
            error,
        )

    return _redirect_to_transaction_detail(
        financial_transaction,
    )


# =============================================================================
# INCOME
# =============================================================================

@login_required
def income(request):
    """
    Display all Finance income transactions.

    Only POSTED income affects accounting.
    """

    _require_permission(
        request.user,
        can_view_financial_transactions,
    )

    income_transactions = (
        FinancialTransaction.objects
        .filter(
            transaction_type=FinancialTransaction.TransactionType.INCOME,
        )
        .select_related(
            "category",
            "member",
            "recorded_by",
            "payment",
        )
        .order_by(
            "-transaction_date",
            "-created_at",
        )
    )

    income_stats = get_income_totals()

    total_income = income_stats.get(
        "total_income",
        ZERO,
    )

    posted_income = income_stats.get(
        "posted_income",
        ZERO,
    )

    income_records = income_stats.get(
        "income_records",
        income_transactions.count(),
    )

    posted_income_transactions = income_transactions.filter(
        status=FinancialTransaction.Status.POSTED,
    )

    pending_income_count = (
        income_transactions
        .exclude(
            status=FinancialTransaction.Status.POSTED,
        )
        .count()
    )

    return render(
        request,
        "income.html",
        {
            "income_transactions": income_transactions,

            "total_income": total_income,

            "posted_income": posted_income,

            "income_records": income_records,

            "income_count": income_records,

            "posted_income_count": (
                posted_income_transactions.count()
            ),

            "pending_income_count": pending_income_count,
        },
    )


# =============================================================================
# EXPENSES
# =============================================================================

@login_required
def expenses(request):
    """
    Display expenses with optional filters.

    Accounting:

        PAID expense
            +
        POSTED expense transaction
            =
        expense affects balance
    """

    _require_permission(
        request.user,
        can_view_expenses,
    )

    queryset = (
        Expense.objects
        .select_related(
            "category",
            "transaction",
            "recorded_by",
            "submitted_by",
            "approved_by",
            "paid_by",
        )
        .order_by(
            "-expense_date",
            "-created_at",
        )
    )

    status = _get_selected_filter(
        request,
        "status",
    )

    category_id = _get_selected_filter(
        request,
        "category",
    )

    if status:
        queryset = queryset.filter(
            status=status,
        )

    if category_id:
        queryset = queryset.filter(
            category_id=category_id,
        )

    expense_stats = get_expense_totals()

    expense_categories = (
        FinancialCategory.objects
        .filter(
            category_type=FinancialCategory.CategoryType.EXPENSE,
            is_active=True,
        )
        .order_by("name")
    )

    return render(
        request,
        "expenses.html",
        {
            "expenses": queryset,

            "expense_statuses": Expense.Status.choices,

            "selected_status": status,

            "selected_category": category_id,

            "expense_categories": expense_categories,

            # Record counts
            "expense_count": Expense.objects.count(),

            "paid_expenses": expense_stats.get(
                "paid_count",
                0,
            ),

            "pending_expenses": expense_stats.get(
                "pending_expenses",
                0,
            ),

            "rejected_expenses": expense_stats.get(
                "rejected_expenses",
                0,
            ),

            # Amounts
            "total_expenses": expense_stats.get(
                "total_expenses",
                ZERO,
            ),

            "paid_expense_amount": expense_stats.get(
                "paid_expenses",
                ZERO,
            ),

            "posted_expenses": expense_stats.get(
                "posted_expenses",
                ZERO,
            ),

            # Compatibility
            "paid_expense_count": expense_stats.get(
                "paid_count",
                0,
            ),
        },
    )


# =============================================================================
# EXPENSE DETAIL
# =============================================================================

@login_required
def expense_detail(request, pk):
    """
    Display one expense and its complete audit history.
    """

    _require_permission(
        request.user,
        can_view_expenses,
    )

    expense = get_object_or_404(
        Expense.objects.select_related(
            "category",
            "transaction",
            "recorded_by",
            "submitted_by",
            "approved_by",
            "paid_by",
        ),
        pk=pk,
    )

    audit_logs = (
        expense.audit_logs
        .select_related("user")
        .order_by("-created_at")
    )

    return render(
        request,
        "expense_detail.html",
        {
            "expense": expense,
            "audit_logs": audit_logs,
        },
    )


# =============================================================================
# CREATE EXPENSE
# =============================================================================

@login_required
def expense_create(request):
    """
    Create a new expense in DRAFT status.
    """

    _require_permission(
        request.user,
        can_manage_expenses,
    )

    if request.method == "POST":
        form = ExpenseForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            cleaned = form.cleaned_data

            try:
                expense = create_expense(
                    user=request.user,

                    category=cleaned["category"],

                    amount=cleaned["amount"],

                    title=cleaned["title"],

                    description=cleaned["description"],

                    payee=cleaned.get(
                        "payee",
                        "",
                    ),

                    payment_source=cleaned.get(
                        "payment_source",
                    ),

                    payment_reference=cleaned.get(
                        "payment_reference",
                        "",
                    ),

                    expense_date=cleaned.get(
                        "expense_date",
                    ),

                    receipt=cleaned.get(
                        "receipt",
                    ),

                    notes=cleaned.get(
                        "notes",
                        "",
                    ),
                )

                messages.success(
                    request,
                    "Expense created successfully.",
                )

                return _redirect_to_expense_detail(
                    expense,
                )

            except ValidationError as error:
                _handle_validation_error(
                    request,
                    error,
                )

    else:
        form = ExpenseForm()

    return render(
        request,
        "expense_form.html",
        {
            "form": form,
            "expense": None,
            "page_title": "Create Expense",
        },
    )


# =============================================================================
# EDIT EXPENSE
# =============================================================================

@login_required
def expense_edit(request, pk):
    """
    Edit an expense while it remains in DRAFT status.
    """

    _require_permission(
        request.user,
        can_manage_expenses,
    )

    expense = get_object_or_404(
        Expense,
        pk=pk,
    )

    if expense.status != Expense.Status.DRAFT:
        messages.error(
            request,
            "Only draft expenses can be edited.",
        )

        return _redirect_to_expense_detail(
            expense,
        )

    if request.method == "POST":
        form = ExpenseForm(
            request.POST,
            request.FILES,
            instance=expense,
        )

        if form.is_valid():
            cleaned = form.cleaned_data

            try:
                expense = update_expense(
                    user=request.user,

                    expense=expense,

                    category=cleaned.get(
                        "category",
                    ),

                    amount=cleaned.get(
                        "amount",
                    ),

                    title=cleaned.get(
                        "title",
                    ),

                    description=cleaned.get(
                        "description",
                    ),

                    payee=cleaned.get(
                        "payee",
                    ),

                    payment_source=cleaned.get(
                        "payment_source",
                    ),

                    payment_reference=cleaned.get(
                        "payment_reference",
                    ),

                    expense_date=cleaned.get(
                        "expense_date",
                    ),

                    receipt=cleaned.get(
                        "receipt",
                    ),

                    notes=cleaned.get(
                        "notes",
                    ),
                )

                messages.success(
                    request,
                    "Expense updated successfully.",
                )

                return _redirect_to_expense_detail(
                    expense,
                )

            except ValidationError as error:
                _handle_validation_error(
                    request,
                    error,
                )

    else:
        form = ExpenseForm(
            instance=expense,
        )

    return render(
        request,
        "expense_form.html",
        {
            "form": form,
            "expense": expense,
            "page_title": "Edit Expense",
        },
    )


# =============================================================================
# SUBMIT EXPENSE
# =============================================================================

@login_required
def expense_submit(request, pk):
    """
    Submit a DRAFT expense for approval.
    """

    _require_permission(
        request.user,
        can_manage_expenses,
    )

    if request.method != "POST":
        return redirect(
            "finance:expense_detail",
            pk=pk,
        )

    expense = get_object_or_404(
        Expense,
        pk=pk,
    )

    try:
        submit_expense(
            user=request.user,
            expense=expense,
        )

        messages.success(
            request,
            "Expense submitted for approval.",
        )

    except ValidationError as error:
        _handle_validation_error(
            request,
            error,
        )

    return _redirect_to_expense_detail(
        expense,
    )


# =============================================================================
# APPROVE EXPENSE
# =============================================================================

@login_required
def expense_approve(request, pk):
    """
    Approve a submitted expense.
    """

    _require_permission(
        request.user,
        can_manage_finance,
    )

    if request.method != "POST":
        return redirect(
            "finance:expense_detail",
            pk=pk,
        )

    expense = get_object_or_404(
        Expense,
        pk=pk,
    )

    try:
        approve_expense(
            user=request.user,
            expense=expense,
        )

        messages.success(
            request,
            "Expense approved successfully.",
        )

    except ValidationError as error:
        _handle_validation_error(
            request,
            error,
        )

    return _redirect_to_expense_detail(
        expense,
    )


# =============================================================================
# REJECT EXPENSE
# =============================================================================

@login_required
def expense_reject(request, pk):
    """
    Reject a submitted expense.
    """

    _require_permission(
        request.user,
        can_manage_finance,
    )

    expense = get_object_or_404(
        Expense,
        pk=pk,
    )

    if expense.status != Expense.Status.SUBMITTED:
        messages.error(
            request,
            "Only submitted expenses can be rejected.",
        )

        return _redirect_to_expense_detail(
            expense,
        )

    if request.method == "POST":
        form = ExpenseRejectionForm(
            request.POST,
        )

        if form.is_valid():
            reason = form.cleaned_data[
                "rejection_reason"
            ]

            try:
                reject_expense(
                    user=request.user,
                    expense=expense,
                    reason=reason,
                )

                messages.warning(
                    request,
                    "Expense rejected successfully.",
                )

                return _redirect_to_expense_detail(
                    expense,
                )

            except ValidationError as error:
                _handle_validation_error(
                    request,
                    error,
                )

    else:
        form = ExpenseRejectionForm()

    return render(
        request,
        "expense_reject.html",
        {
            "form": form,
            "expense": expense,
            "page_title": "Reject Expense",
        },
    )


# =============================================================================
# PAY EXPENSE
# =============================================================================

@login_required
def expense_pay(request, pk):
    """
    Pay an approved expense.

    The service layer performs:

        1. Validation.
        2. Payment reference validation.
        3. PAID status transition.
        4. Expense ledger creation.
        5. Ledger POST.
        6. Expense/transaction linking.
        7. Audit logging.
    """

    _require_permission(
        request.user,
        can_manage_finance,
    )

    expense = get_object_or_404(
        Expense,
        pk=pk,
    )

    if expense.status != Expense.Status.APPROVED:
        messages.error(
            request,
            "Only approved expenses can be paid.",
        )

        return _redirect_to_expense_detail(
            expense,
        )

    if request.method != "POST":
        return redirect(
            "finance:expense_detail",
            pk=pk,
        )

    payment_reference = request.POST.get(
        "payment_reference",
        "",
    ).strip()

    if not payment_reference:
        messages.error(
            request,
            "A payment reference is required.",
        )

        return _redirect_to_expense_detail(
            expense,
        )

    expense.payment_reference = payment_reference

    try:
        expense = pay_expense(
            user=request.user,
            expense=expense,
        )

        messages.success(
            request,
            (
                "Expense paid and posted to the "
                "financial ledger successfully."
            ),
        )

    except ValidationError as error:
        _handle_validation_error(
            request,
            error,
        )

    return _redirect_to_expense_detail(
        expense,
    )


# =============================================================================
# VOID EXPENSE
# =============================================================================

@login_required
def expense_void(request, pk):
    """
    Void an expense.
    """

    _require_permission(
        request.user,
        can_manage_finance,
    )

    expense = get_object_or_404(
        Expense,
        pk=pk,
    )

    if request.method == "POST":
        form = ExpenseVoidForm(
            request.POST,
        )

        if form.is_valid():
            reason = form.cleaned_data[
                "void_reason"
            ]

            try:
                void_expense(
                    user=request.user,
                    expense=expense,
                    reason=reason,
                )

                messages.warning(
                    request,
                    "Expense voided successfully.",
                )

                return _redirect_to_expense_detail(
                    expense,
                )

            except ValidationError as error:
                _handle_validation_error(
                    request,
                    error,
                )

    else:
        form = ExpenseVoidForm()

    return render(
        request,
        "expense_void.html",
        {
            "form": form,
            "expense": expense,
            "page_title": "Void Expense",
        },
    )


# =============================================================================
# CATEGORIES
# =============================================================================

@login_required
def categories(request):
    """
    Display all financial categories and their statistics.
    """

    _require_permission(
        request.user,
        can_manage_categories,
    )

    category_queryset = (
        FinancialCategory.objects
        .order_by(
            "category_type",
            "name",
        )
    )

    category_stats = get_category_totals()

    return render(
        request,
        "categories.html",
        {
            "categories": category_queryset,

            "total_categories": category_stats.get(
                "total_categories",
                0,
            ),

            "income_categories": category_stats.get(
                "income_categories",
                0,
            ),

            "expense_categories": category_stats.get(
                "expense_categories",
                0,
            ),

            "active_categories": category_stats.get(
                "active_categories",
                0,
            ),

            "inactive_categories": category_stats.get(
                "inactive_categories",
                0,
            ),

            "system_categories": category_queryset.filter(
                is_system=True,
            ).count(),

            "custom_categories": category_queryset.filter(
                is_system=False,
            ).count(),
        },
    )


# =============================================================================
# CATEGORY LIST ALIAS
# =============================================================================

@login_required
def category_list(request):
    """
    Backwards-compatible alias for categories().
    """

    return categories(request)


# =============================================================================
# CREATE CATEGORY
# =============================================================================

@login_required
def category_create(request):
    """
    Create a financial category.
    """

    _require_permission(
        request.user,
        can_manage_categories,
    )

    if request.method == "POST":
        form = FinancialCategoryForm(
            request.POST,
        )

        if form.is_valid():
            cleaned = form.cleaned_data

            try:
                category = create_category(
                    user=request.user,

                    name=cleaned["name"],

                    category_type=cleaned["category_type"],

                    description=cleaned.get(
                        "description",
                        "",
                    ),

                    is_active=cleaned.get(
                        "is_active",
                        True,
                    ),
                )

                messages.success(
                    request,
                    (
                        f"Category '{category.name}' "
                        "created successfully."
                    ),
                )

                return redirect(
                    "finance:categories",
                )

            except ValidationError as error:
                _handle_validation_error(
                    request,
                    error,
                )

    else:
        form = FinancialCategoryForm()

    return render(
        request,
        "category_form.html",
        {
            "form": form,
            "title": "Create Financial Category",
        },
    )


# =============================================================================
# UPDATE CATEGORY
# =============================================================================

@login_required
def category_update(request, pk):
    """
    Update an existing financial category.
    """

    _require_permission(
        request.user,
        can_manage_categories,
    )

    category = get_object_or_404(
        FinancialCategory,
        pk=pk,
    )

    if request.method == "POST":
        form = FinancialCategoryForm(
            request.POST,
            instance=category,
        )

        if form.is_valid():
            cleaned = form.cleaned_data

            try:
                category = update_category(
                    user=request.user,

                    category=category,

                    name=cleaned.get(
                        "name",
                    ),

                    description=cleaned.get(
                        "description",
                    ),

                    is_active=cleaned.get(
                        "is_active",
                    ),
                )

                messages.success(
                    request,
                    (
                        f"Category '{category.name}' "
                        "updated successfully."
                    ),
                )

                return redirect(
                    "finance:categories",
                )

            except ValidationError as error:
                _handle_validation_error(
                    request,
                    error,
                )

    else:
        form = FinancialCategoryForm(
            instance=category,
        )

    return render(
        request,
        "category_form.html",
        {
            "form": form,
            "category": category,
            "title": "Update Financial Category",
        },
    )


# =============================================================================
# TOGGLE CATEGORY
# =============================================================================

@login_required
def category_toggle(request, pk):
    """
    Deactivate an active financial category.

    System categories are protected by the service layer.
    """

    _require_permission(
        request.user,
        can_manage_categories,
    )

    if request.method != "POST":
        return redirect(
            "finance:categories",
        )

    category = get_object_or_404(
        FinancialCategory,
        pk=pk,
    )

    if not category.is_active:
        messages.info(
            request,
            "This category is already inactive.",
        )

        return redirect(
            "finance:categories",
        )

    try:
        category = deactivate_category(
            user=request.user,
            category=category,
        )

        messages.success(
            request,
            (
                f"Category '{category.name}' "
                "has been deactivated."
            ),
        )

    except ValidationError as error:
        _handle_validation_error(
            request,
            error,
        )

    return redirect(
        "finance:categories",
    )


# =============================================================================
# RECONCILIATION
# =============================================================================

@login_required
def reconciliation(request):
    """
    Display financial reconciliations.
    """

    _require_permission(
        request.user,
        can_view_reconciliation,
    )

    reconciliations = (
        FinancialReconciliation.objects
        .select_related(
            "prepared_by",
            "reconciled_by",
        )
        .order_by(
            "-period_end",
            "-created_at",
        )
    )

    return render(
        request,
        "reconciliation.html",
        {
            "reconciliations": reconciliations,

            "total_reconciliations": (
                reconciliations.count()
            ),

            "reconciled_count": reconciliations.filter(
                status=FinancialReconciliation.Status.RECONCILED,
            ).count(),

            "in_progress_count": reconciliations.filter(
                status=FinancialReconciliation.Status.IN_PROGRESS,
            ).count(),

            "discrepancy_count": reconciliations.filter(
                status=FinancialReconciliation.Status.DISCREPANCY,
            ).count(),

            "draft_count": reconciliations.filter(
                status=FinancialReconciliation.Status.DRAFT,
            ).count(),
        },
    )


# =============================================================================
# RECONCILIATION DETAIL
# =============================================================================

@login_required
def reconciliation_detail(request, pk):
    """
    Display one reconciliation and its audit history.
    """

    _require_permission(
        request.user,
        can_view_reconciliation,
    )

    reconciliation_record = get_object_or_404(
        FinancialReconciliation.objects.select_related(
            "prepared_by",
            "reconciled_by",
        ),
        pk=pk,
    )

    audit_logs = (
        reconciliation_record.audit_logs
        .select_related("user")
        .order_by("-created_at")
    )

    return render(
        request,
        "reconciliation_detail.html",
        {
            "reconciliation": reconciliation_record,
            "audit_logs": audit_logs,
        },
    )


# =============================================================================
# RECONCILIATION CREATE
# =============================================================================

@login_required
def reconciliation_create(request):
    """
    Create a financial reconciliation record.
    """

    _require_permission(
        request.user,
        can_view_reconciliation,
    )

    if request.method == "POST":
        form = FinancialReconciliationForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            cleaned = form.cleaned_data

            try:
                reconciliation_record = create_reconciliation(
                    user=request.user,

                    source=cleaned["source"],

                    statement_reference=cleaned.get(
                        "statement_reference",
                        "",
                    ),

                    period_start=cleaned["period_start"],

                    period_end=cleaned["period_end"],

                    system_income=cleaned.get(
                        "system_income",
                        ZERO,
                    ),

                    system_expenses=cleaned.get(
                        "system_expenses",
                        ZERO,
                    ),

                    external_income=cleaned.get(
                        "external_income",
                        ZERO,
                    ),

                    external_expenses=cleaned.get(
                        "external_expenses",
                        ZERO,
                    ),

                    file=cleaned.get(
                        "file",
                    ),

                    notes=cleaned.get(
                        "notes",
                        "",
                    ),
                )

                messages.success(
                    request,
                    "Financial reconciliation created successfully.",
                )

                return _redirect_to_reconciliation_detail(
                    reconciliation_record,
                )

            except ValidationError as error:
                _handle_validation_error(
                    request,
                    error,
                )

    else:
        form = FinancialReconciliationForm()

    return render(
        request,
        "reconciliation_form.html",
        {
            "form": form,
            "reconciliation": None,
            "page_title": "Create Financial Reconciliation",
        },
    )


# =============================================================================
# RECONCILIATION UPDATE
# =============================================================================

@login_required
def reconciliation_update(request, pk):
    """
    Update a draft or in-progress reconciliation.
    """

    _require_permission(
        request.user,
        can_view_reconciliation,
    )

    reconciliation_record = get_object_or_404(
        FinancialReconciliation,
        pk=pk,
    )

    if reconciliation_record.status == (
        FinancialReconciliation.Status.RECONCILED
    ):
        messages.error(
            request,
            "A completed reconciliation cannot be edited.",
        )

        return _redirect_to_reconciliation_detail(
            reconciliation_record,
        )

    if request.method == "POST":
        form = FinancialReconciliationForm(
            request.POST,
            request.FILES,
            instance=reconciliation_record,
        )

        if form.is_valid():
            updated_record = form.save(
                commit=False,
            )

            updated_record.prepared_by = (
                reconciliation_record.prepared_by
            )

            updated_record.status = (
                reconciliation_record.status
            )

            try:
                updated_record.full_clean()
                updated_record.save()

                messages.success(
                    request,
                    "Financial reconciliation updated successfully.",
                )

                return _redirect_to_reconciliation_detail(
                    updated_record,
                )

            except ValidationError as error:
                _handle_validation_error(
                    request,
                    error,
                )

    else:
        form = FinancialReconciliationForm(
            instance=reconciliation_record,
        )

    return render(
        request,
        "reconciliation_form.html",
        {
            "form": form,
            "reconciliation": reconciliation_record,
            "page_title": "Update Financial Reconciliation",
        },
    )


# =============================================================================
# RECONCILIATION COMPLETE
# =============================================================================

@login_required
def reconciliation_complete(request, pk):
    """
    Complete a financial reconciliation.

    The service determines whether it becomes:

        RECONCILED

    or:

        DISCREPANCY
    """

    _require_permission(
        request.user,
        can_manage_finance,
    )

    reconciliation_record = get_object_or_404(
        FinancialReconciliation,
        pk=pk,
    )

    if reconciliation_record.status == (
        FinancialReconciliation.Status.RECONCILED
    ):
        messages.info(
            request,
            "This reconciliation has already been completed.",
        )

        return _redirect_to_reconciliation_detail(
            reconciliation_record,
        )

    if request.method == "POST":
        form = ReconciliationCompleteForm(
            request.POST,
        )

        if form.is_valid():
            try:
                # Apply submitted completion data to the record
                # before the service performs final validation.
                cleaned = form.cleaned_data

                for field in (
                    "external_income",
                    "external_expenses",
                    "notes",
                ):
                    if field in cleaned:
                        setattr(
                            reconciliation_record,
                            field,
                            cleaned[field],
                        )

                reconciliation_record = reconcile_finance(
                    user=request.user,
                    reconciliation=reconciliation_record,
                )

                if reconciliation_record.status == (
                    FinancialReconciliation.Status.RECONCILED
                ):
                    messages.success(
                        request,
                        (
                            "Financial reconciliation completed "
                            "successfully."
                        ),
                    )
                else:
                    messages.warning(
                        request,
                        (
                            "Reconciliation completed with a "
                            "discrepancy. Please review the figures."
                        ),
                    )

                return _redirect_to_reconciliation_detail(
                    reconciliation_record,
                )

            except ValidationError as error:
                _handle_validation_error(
                    request,
                    error,
                )

    else:
        form = ReconciliationCompleteForm()

    return render(
        request,
        "reconciliation_complete.html",
        {
            "form": form,
            "reconciliation": reconciliation_record,
            "page_title": "Complete Reconciliation",
        },
    )


# =============================================================================
# AUDIT LOGS
# =============================================================================

@login_required
def audit_logs(request):
    """
    Display the complete Finance audit trail.

    Audit logs are read-only.

    IMPORTANT
    ---------

    The Finance audit trail contains actions performed
    by all authorized Finance users.

    Therefore, the default query must NOT be restricted
    to request.user.
    """

    _require_permission(
        request.user,
        can_view_audit_logs,
    )

    action = _get_selected_filter(
        request,
        "action",
    )

    # -------------------------------------------------------------------------
    # Retrieve the complete audit trail from the service layer.
    # -------------------------------------------------------------------------

    logs = get_audit_logs()

    # -------------------------------------------------------------------------
    # Optional action filter.
    # -------------------------------------------------------------------------

    if action:
        logs = logs.filter(
            action=action,
        )

    # -------------------------------------------------------------------------
    # Statistics must describe the displayed queryset.
    #
    # This avoids the common problem where the page is filtered
    # but the cards still display global statistics.
    # -------------------------------------------------------------------------

    audit_stats = get_audit_log_totals(
        queryset=logs,
    )

    return render(
        request,
        "audit_log.html",
        {
            "audit_logs": logs,

            "actions": FinancialAuditLog.Action.choices,

            "selected_action": action,

            "total_logs": audit_stats.get(
                "total_logs",
                0,
            ),

            "created_logs": audit_stats.get(
                "created_logs",
                0,
            ),

            "updated_logs": audit_stats.get(
                "updated_logs",
                0,
            ),

            "workflow_actions": audit_stats.get(
                "workflow_actions",
                0,
            ),
        },
    )