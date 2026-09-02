# finance/views.py

"""
KUCSA Finance Views
===================

HTTP views for the KUCSA Finance application.

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
"""


from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

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
    deactivate_category,
    get_audit_logs,
    get_financial_totals,
    post_transaction,
    reject_expense,
    submit_expense,
    update_category,
    update_expense,
    void_expense,
    void_transaction,
    pay_expense,
)


# =============================================================================
# HELPERS
# =============================================================================

def _require_permission(user, permission):
    """
    Raise HTTP 403 when the current user does not have
    the required finance permission.
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

    Supports both:

        ValidationError("message")

    and:

        ValidationError({
            "field": "message"
        })
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
    value = request.GET.get(name, "").strip()

    return value or None


# =============================================================================
# DASHBOARD
# =============================================================================

@login_required
def dashboard(request):
    """
    Display the main finance dashboard.

    Financial totals are obtained from the service layer.
    """
    _require_permission(
        request.user,
        can_access_finance_dashboard,
    )

    totals = get_financial_totals()

    context = {
        "posted_income": totals.get(
            "income",
            Decimal("0.00"),
        ),
        "posted_expenses": totals.get(
            "expenses",
            Decimal("0.00"),
        ),
        "balance": totals.get(
            "balance",
            Decimal("0.00"),
        ),

        "transaction_count": (
            FinancialTransaction.objects.count()
        ),

        "expense_count": (
            Expense.objects.count()
        ),

        "pending_expenses": (
            Expense.objects.filter(
                status__in=[
                    Expense.Status.SUBMITTED,
                    Expense.Status.APPROVED,
                ]
            ).count()
        ),

        "category_count": (
            FinancialCategory.objects.filter(
                is_active=True,
            ).count()
        ),

        "recent_transactions": (
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
            )[:10]
        ),

        "recent_expenses": (
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
        ),
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
    }

    return render(
        request,
        "transactions.html",
        context,
    )


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

    The transaction is initially created as a DRAFT.

    Posting is handled separately through the service layer.
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
            transaction = form.save(
                commit=False,
            )

            transaction.recorded_by = request.user
            transaction.status = (
                FinancialTransaction.Status.DRAFT
            )

            try:
                transaction.full_clean()
                transaction.save()

                messages.success(
                    request,
                    "Financial transaction created successfully.",
                )

                return _redirect_to_transaction_detail(
                    transaction,
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

    Only POST requests are accepted.
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

    Voiding preserves the financial history rather than
    deleting the transaction.
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
    Display income transactions.

    Only POSTED income contributes to the displayed
    financial total.
    """
    _require_permission(
        request.user,
        can_view_financial_transactions,
    )

    income_transactions = (
        FinancialTransaction.objects
        .filter(
            transaction_type=(
                FinancialTransaction.TransactionType.INCOME
            )
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

    total_income = (
        income_transactions
        .filter(
            status=FinancialTransaction.Status.POSTED,
        )
        .aggregate(
            total=Sum("amount"),
        )
        .get("total")
        or Decimal("0.00")
    )

    return render(
        request,
        "income.html",
        {
            "income_transactions": income_transactions,
            "total_income": total_income,
        },
    )


# =============================================================================
# EXPENSES
# =============================================================================

@login_required
def expenses(request):
    """
    Display expenses with an optional status filter.
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
            "rejected_by",
            "paid_by",
            "voided_by",
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

    if status:
        queryset = queryset.filter(
            status=status,
        )

    return render(
        request,
        "expenses.html",
        {
            "expenses": queryset,

            "expense_statuses": (
                Expense.Status.choices
            ),

            "selected_status": status,
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
            "rejected_by",
            "paid_by",
            "voided_by",
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
    Create a new draft expense.

    The expense workflow is handled by services.py.
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

    IMPORTANT:

    The correct model enum is:

        Expense.Status.DRAFT

    not:

        Expense.ExpenseStatus.DRAFT
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

    Rejection reason is collected through
    ExpenseRejectionForm.
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

    The service layer is responsible for:

        1. Validating the expense.
        2. Recording the payer.
        3. Recording the payment reference.
        4. Marking the expense as PAID.
        5. Creating the ledger transaction.
        6. Posting the ledger transaction.
        7. Linking the transaction to the expense.
        8. Creating the audit record.
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

    The service layer is responsible for maintaining
    consistency between the expense and its ledger
    transaction.
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
    Display all financial categories.
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

    return render(
        request,
        "categories.html",
        {
            "categories": category_queryset,
        },
    )


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

    System-category creation is controlled by the
    service layer rather than being exposed through
    the normal form.
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
                    category_type=cleaned[
                        "category_type"
                    ],
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

    The service layer determines whether the category
    is allowed to be modified.
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

    Category activation is deliberately not implemented
    here because the current service layer only exposes
    deactivate_category().
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

    The current model stores the user who prepared
    the reconciliation in prepared_by.
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
            reconciliation_record = form.save(
                commit=False,
            )

            reconciliation_record.prepared_by = (
                request.user
            )

            reconciliation_record.status = (
                FinancialReconciliation.Status.DRAFT
            )

            try:
                reconciliation_record.full_clean()
                reconciliation_record.save()

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

    Final reconciliation authorization remains
    controlled by the service layer.
    """
    _require_permission(
        request.user,
        can_view_reconciliation,
    )

    reconciliation_record = get_object_or_404(
        FinancialReconciliation,
        pk=pk,
    )

    if reconciliation_record.status in [
        FinancialReconciliation.Status.RECONCILED,
    ]:
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

    NOTE:

    Final authorization and reconciliation state
    transitions should be implemented in services.py.

    This view therefore validates the completion form
    and delegates the actual state change to the service
    layer when that service is available.
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
            notes = form.cleaned_data.get(
                "notes",
                "",
            )

            # The current services import list does not
            # expose a reconciliation completion service.
            #
            # Therefore we deliberately do not mutate the
            # reconciliation here. This prevents the view
            # from bypassing the service architecture.
            messages.error(
                request,
                (
                    "Reconciliation completion is not yet "
                    "implemented in the finance service layer."
                ),
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
    Display the financial audit trail.

    Audit logs are read-only.
    """
    _require_permission(
        request.user,
        can_view_audit_logs,
    )

    action = _get_selected_filter(
        request,
        "action",
    )

    logs = get_audit_logs(
        user=request.user,
    )

    if action:
        logs = logs.filter(
            action=action,
        )

    return render(
        request,
        "audit_log.html",
        {
            "audit_logs": logs,
            "actions": (
                FinancialAuditLog.Action.choices
            ),
            "selected_action": action,
        },
    )