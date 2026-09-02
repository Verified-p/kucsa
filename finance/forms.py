
# finance/forms.py

"""
KUCSA Finance Forms
===================

Forms for the KUCSA Finance application.

Responsibilities
----------------

This module is responsible for:

    - collecting financial input
    - validating form input
    - restricting category choices
    - applying Bootstrap styling
    - providing user-friendly form errors

Business workflow logic belongs in:

    - finance/services.py
    - finance/permissions.py

The forms must NOT:

    - verify M-Pesa payments
    - approve expenses
    - pay expenses
    - post transactions
    - void transactions
    - perform reconciliation
    - create audit records

Those operations belong to the service layer.
"""

from django import forms
from django.core.exceptions import ValidationError

from .models import (
    Expense,
    FinancialCategory,
    FinancialReconciliation,
    FinancialTransaction,
)


# =============================================================================
# COMMON FORM MIXIN
# =============================================================================

class FinanceFormMixin:
    """
    Common Bootstrap styling for Finance forms.
    """

    def apply_bootstrap_classes(self):
        for field in self.fields.values():

            widget = field.widget

            # -------------------------------------------------------------
            # CHECKBOX
            # -------------------------------------------------------------

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault(
                    "class",
                    "form-check-input",
                )

            # -------------------------------------------------------------
            # SELECT
            # -------------------------------------------------------------

            elif isinstance(
                widget,
                (
                    forms.Select,
                    forms.SelectMultiple,
                ),
            ):
                widget.attrs.setdefault(
                    "class",
                    "form-select",
                )

            # -------------------------------------------------------------
            # FILE
            # -------------------------------------------------------------

            elif isinstance(
                widget,
                forms.ClearableFileInput,
            ):
                widget.attrs.setdefault(
                    "class",
                    "form-control",
                )

            # -------------------------------------------------------------
            # OTHER INPUTS
            # -------------------------------------------------------------

            else:
                existing_class = widget.attrs.get(
                    "class",
                    "",
                )

                widget.attrs["class"] = (
                    f"{existing_class} form-control"
                ).strip()

            # -------------------------------------------------------------
            # AUTOCOMPLETE
            # -------------------------------------------------------------

            if not isinstance(
                widget,
                forms.CheckboxInput,
            ):
                widget.attrs.setdefault(
                    "autocomplete",
                    "off",
                )


# =============================================================================
# FINANCIAL CATEGORY FORM
# =============================================================================

class FinancialCategoryForm(
    FinanceFormMixin,
    forms.ModelForm,
):
    """
    Create or update a financial category.

    System categories are intentionally NOT exposed through
    this form. They should be created and protected by the
    finance service/data initialization layer.
    """

    class Meta:
        model = FinancialCategory

        fields = [
            "name",
            "category_type",
            "description",
            "is_active",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Membership Fees",
                }
            ),
            "category_type": forms.Select(),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": (
                        "Describe what this category is used for."
                    ),
                }
            ),
            "is_active": forms.CheckboxInput(),
        }

        labels = {
            "name": "Category Name",
            "category_type": "Category Type",
            "description": "Description",
            "is_active": "Active",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()

    def clean_name(self):
        name = (
            self.cleaned_data.get("name") or ""
        ).strip()

        if not name:
            raise ValidationError(
                "Category name cannot be empty."
            )

        return name

    def clean(self):
        cleaned_data = super().clean()

        category_type = cleaned_data.get(
            "category_type"
        )

        name = (
            cleaned_data.get("name") or ""
        ).strip()

        # -------------------------------------------------------------
        # PREVENT DUPLICATE CATEGORY NAMES
        # -------------------------------------------------------------

        if name:
            queryset = FinancialCategory.objects.filter(
                name__iexact=name,
            )

            if self.instance.pk:
                queryset = queryset.exclude(
                    pk=self.instance.pk,
                )

            if queryset.exists():
                self.add_error(
                    "name",
                    "A financial category with this name "
                    "already exists.",
                )

        # -------------------------------------------------------------
        # VALID CATEGORY TYPE
        # -------------------------------------------------------------

        if category_type not in {
            FinancialCategory.CategoryType.INCOME,
            FinancialCategory.CategoryType.EXPENSE,
        }:
            self.add_error(
                "category_type",
                "Select a valid financial category type.",
            )

        return cleaned_data


# =============================================================================
# FINANCIAL TRANSACTION FORM
# =============================================================================

class FinancialTransactionForm(
    FinanceFormMixin,
    forms.ModelForm,
):
    """
    Create or update a manual financial transaction.

    Payment-linked transactions should normally be created
    by the finance service after the Payments application
    confirms a completed payment.
    """

    class Meta:
        model = FinancialTransaction

        fields = [
            "transaction_type",
            "category",
            "amount",
            "description",
            "reference",
            "payment_source",
            "member",
            "transaction_date",
            "notes",
        ]

        widgets = {
            "transaction_type": forms.Select(),

            "category": forms.Select(
                attrs={
                    "data-category-select": "true",
                }
            ),

            "amount": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0.01",
                    "placeholder": "0.00",
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": (
                        "Describe the financial transaction."
                    ),
                }
            ),

            "reference": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Internal or external reference"
                    ),
                }
            ),

            "payment_source": forms.Select(),

            "member": forms.Select(),

            "transaction_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                }
            ),

            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Optional notes.",
                }
            ),
        }

        labels = {
            "transaction_type": "Transaction Type",
            "category": "Category",
            "amount": "Amount (KES)",
            "description": "Description",
            "reference": "Reference",
            "payment_source": "Payment Source",
            "member": "Member",
            "transaction_date": "Transaction Date",
            "notes": "Notes",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()

        # -------------------------------------------------------------
        # ONLY ACTIVE CATEGORIES
        # -------------------------------------------------------------

        self.fields["category"].queryset = (
            FinancialCategory.objects
            .filter(
                is_active=True,
            )
            .order_by(
                "category_type",
                "name",
            )
        )

        self.fields["category"].empty_label = (
            "Select a financial category"
        )

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")

        if amount is None:
            return amount

        if amount <= 0:
            raise ValidationError(
                "Transaction amount must be greater than zero."
            )

        return amount

    def clean(self):
        cleaned_data = super().clean()

        transaction_type = cleaned_data.get(
            "transaction_type"
        )

        category = cleaned_data.get(
            "category"
        )

        # -------------------------------------------------------------
        # CATEGORY TYPE MUST MATCH TRANSACTION TYPE
        # -------------------------------------------------------------

        if transaction_type and category:

            if (
                transaction_type
                == FinancialTransaction.TransactionType.INCOME
                and category.category_type
                != FinancialCategory.CategoryType.INCOME
            ):
                self.add_error(
                    "category",
                    "Income transactions must use "
                    "an income category.",
                )

            elif (
                transaction_type
                == FinancialTransaction.TransactionType.EXPENSE
                and category.category_type
                != FinancialCategory.CategoryType.EXPENSE
            ):
                self.add_error(
                    "category",
                    "Expense transactions must use "
                    "an expense category.",
                )

            # ---------------------------------------------------------
            # CATEGORY MUST BE ACTIVE
            # ---------------------------------------------------------

            if not category.is_active:
                self.add_error(
                    "category",
                    "The selected financial category is inactive.",
                )

        return cleaned_data


# =============================================================================
# EXPENSE FORM
# =============================================================================

class ExpenseForm(
    FinanceFormMixin,
    forms.ModelForm,
):
    """
    Create or edit a KUCSA expense.

    Only active EXPENSE categories are available.

    Workflow operations such as:

        Submit
        Approve
        Reject
        Pay
        Void

    belong to finance.services.
    """

    class Meta:
        model = Expense

        fields = [
            "category",
            "amount",
            "title",
            "description",
            "payee",
            "payment_source",
            "payment_reference",
            "expense_date",
            "receipt",
            "notes",
        ]

        widgets = {
            "category": forms.Select(
                attrs={
                    "data-category-select": "true",
                }
            ),

            "amount": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0.01",
                    "placeholder": "0.00",
                }
            ),

            "title": forms.TextInput(
                attrs={
                    "placeholder": (
                        "e.g. Printing of KUCSA posters"
                    ),
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "Explain the purpose of this expense."
                    ),
                }
            ),

            "payee": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Person, supplier, organization, "
                        "or service provider"
                    ),
                }
            ),

            "payment_source": forms.Select(),

            "payment_reference": forms.TextInput(
                attrs={
                    "placeholder": (
                        "M-Pesa receipt, bank reference, "
                        "cheque number, voucher number, etc."
                    ),
                }
            ),

            "expense_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                }
            ),

            "receipt": forms.ClearableFileInput(),

            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": (
                        "Optional financial notes."
                    ),
                }
            ),
        }

        labels = {
            "category": "Expense Category",
            "amount": "Amount (KES)",
            "title": "Expense Title",
            "description": "Description",
            "payee": "Payee",
            "payment_source": "Payment Source",
            "payment_reference": "Payment Reference",
            "expense_date": "Expense Date",
            "receipt": "Receipt / Supporting Document",
            "notes": "Notes",
        }

        help_texts = {
            "category": (
                "Select the appropriate active KUCSA expense category."
            ),
            "amount": (
                "Enter the total expense amount in Kenyan Shillings."
            ),
            "description": (
                "Provide a clear explanation of what the money "
                "was or will be used for."
            ),
            "payment_reference": (
                "Enter the M-Pesa receipt, bank reference, "
                "cheque number, voucher number, or other "
                "available payment reference."
            ),
            "receipt": (
                "Upload a receipt, invoice, payment evidence, "
                "or other relevant supporting document."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()

        # -------------------------------------------------------------
        # CRITICAL:
        #
        # ONLY ACTIVE EXPENSE CATEGORIES ARE AVAILABLE.
        # -------------------------------------------------------------

        self.fields["category"].queryset = (
            FinancialCategory.objects
            .filter(
                category_type=(
                    FinancialCategory.CategoryType.EXPENSE
                ),
                is_active=True,
            )
            .order_by("name")
        )

        self.fields["category"].empty_label = (
            "Select an expense category"
        )

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")

        if amount is None:
            return amount

        if amount <= 0:
            raise ValidationError(
                "Expense amount must be greater than zero."
            )

        return amount

    def clean_title(self):
        title = (
            self.cleaned_data.get("title") or ""
        ).strip()

        if not title:
            raise ValidationError(
                "Expense title cannot be empty."
            )

        return title

    def clean_description(self):
        description = (
            self.cleaned_data.get("description") or ""
        ).strip()

        if not description:
            raise ValidationError(
                "Expense description cannot be empty."
            )

        return description

    def clean_payee(self):
        payee = (
            self.cleaned_data.get("payee") or ""
        ).strip()

        return payee

    def clean_payment_reference(self):
        reference = (
            self.cleaned_data.get("payment_reference")
            or ""
        ).strip()

        return reference

    def clean(self):
        cleaned_data = super().clean()

        category = cleaned_data.get("category")

        # -------------------------------------------------------------
        # CATEGORY MUST EXIST
        # -------------------------------------------------------------

        if not category:
            self.add_error(
                "category",
                "Please select an expense category.",
            )

        # -------------------------------------------------------------
        # CATEGORY MUST BE EXPENSE CATEGORY
        # -------------------------------------------------------------

        elif (
            category.category_type
            != FinancialCategory.CategoryType.EXPENSE
        ):
            self.add_error(
                "category",
                "An expense must use an expense category.",
            )

        # -------------------------------------------------------------
        # CATEGORY MUST BE ACTIVE
        # -------------------------------------------------------------

        elif not category.is_active:
            self.add_error(
                "category",
                "The selected expense category is inactive.",
            )

        return cleaned_data


# =============================================================================
# EXPENSE REJECTION FORM
# =============================================================================

class ExpenseRejectionForm(
    FinanceFormMixin,
    forms.Form,
):
    """
    Form used when rejecting an expense.
    """

    rejection_reason = forms.CharField(
        label="Rejection Reason",
        required=True,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Explain why this expense is being rejected."
                ),
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()

    def clean_rejection_reason(self):
        reason = (
            self.cleaned_data.get(
                "rejection_reason"
            )
            or ""
        ).strip()

        if not reason:
            raise ValidationError(
                "A rejection reason is required."
            )

        return reason


# =============================================================================
# EXPENSE VOID FORM
# =============================================================================

class ExpenseVoidForm(
    FinanceFormMixin,
    forms.Form,
):
    """
    Form used when voiding an expense.
    """

    void_reason = forms.CharField(
        label="Void Reason",
        required=True,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Explain why this expense is being voided."
                ),
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean_void_reason(self):
        reason = (
            self.cleaned_data.get(
                "void_reason"
            )
            or ""
        ).strip()

        if not reason:
            raise ValidationError(
                "A void reason is required."
            )

        return reason


# =============================================================================
# FINANCIAL RECONCILIATION FORM
# =============================================================================

class FinancialReconciliationForm(
    FinanceFormMixin,
    forms.ModelForm,
):
    """
    Create or update a financial reconciliation.

    The model field is:

        source

    The form therefore uses:

        source
    """

    class Meta:
        model = FinancialReconciliation

        fields = [
            "source",
            "statement_reference",
            "period_start",
            "period_end",
            "system_income",
            "system_expenses",
            "external_income",
            "external_expenses",
            "notes",
            "statement_file",
        ]

        widgets = {
            "source": forms.Select(),

            "statement_reference": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Statement or reconciliation reference"
                    ),
                }
            ),

            "period_start": forms.DateInput(
                attrs={
                    "type": "date",
                }
            ),

            "period_end": forms.DateInput(
                attrs={
                    "type": "date",
                }
            ),

            "system_income": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0.00",
                }
            ),

            "system_expenses": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0.00",
                }
            ),

            "external_income": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0.00",
                }
            ),

            "external_expenses": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0.00",
                }
            ),

            "notes": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "Reconciliation notes or explanation "
                        "of discrepancies."
                    ),
                }
            ),

            "statement_file": forms.ClearableFileInput(),
        }

        labels = {
            "source": "Statement Source",
            "statement_reference": "Statement Reference",
            "period_start": "Period Start",
            "period_end": "Period End",
            "system_income": "System Income (KES)",
            "system_expenses": "System Expenses (KES)",
            "external_income": "External Income (KES)",
            "external_expenses": "External Expenses (KES)",
            "notes": "Notes",
            "statement_file": "Supporting Statement",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()

    def clean(self):
        cleaned_data = super().clean()

        period_start = cleaned_data.get(
            "period_start"
        )

        period_end = cleaned_data.get(
            "period_end"
        )

        if (
            period_start
            and period_end
            and period_end < period_start
        ):
            self.add_error(
                "period_end",
                "Period end cannot be earlier than "
                "period start.",
            )

        return cleaned_data

    def _clean_non_negative_amount(
        self,
        field_name,
    ):
        value = self.cleaned_data.get(
            field_name
        )

        if value is not None and value < 0:
            raise ValidationError(
                f"{field_name.replace('_', ' ').title()} "
                "cannot be negative."
            )

        return value

    def clean_system_income(self):
        return self._clean_non_negative_amount(
            "system_income"
        )

    def clean_system_expenses(self):
        return self._clean_non_negative_amount(
            "system_expenses"
        )

    def clean_external_income(self):
        return self._clean_non_negative_amount(
            "external_income"
        )

    def clean_external_expenses(self):
        return self._clean_non_negative_amount(
            "external_expenses"
        )


# =============================================================================
# RECONCILIATION COMPLETION FORM
# =============================================================================

class ReconciliationCompleteForm(
    FinanceFormMixin,
    forms.Form,
):
    """
    Form used when completing a reconciliation.

    Authorization and status changes belong in services.py.
    """

    notes = forms.CharField(
        label="Reconciliation Notes",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Add any final reconciliation notes."
                ),
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.apply_bootstrap_classes()
