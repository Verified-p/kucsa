# finance/apps.py

from django.apps import AppConfig


class FinanceConfig(AppConfig):
    """
    KUCSA Finance Application Configuration.

    The Finance application is responsible for:

        - Financial ledger
        - Income
        - Expenses
        - Transactions
        - Financial categories
        - Reconciliation
        - Audit records

    Payment synchronization is registered through
    the application's signal handlers.
    """

    default_auto_field = "django.db.models.BigAutoField"

    name = "finance"

    verbose_name = "KUCSA Finance"

    def ready(self):
        """
        Import Finance signal handlers when Django
        initializes the application.

        This ensures that:

            Payment COMPLETED
                    ↓
              post_save signal
                    ↓
              Finance sync
        """

        from . import signals  # noqa: F401