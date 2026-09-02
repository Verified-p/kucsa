# events/apps.py

from django.apps import AppConfig


class EventsConfig(AppConfig):
    """
    Configuration for the KUCSA Events application.
    """

    default_auto_field = "django.db.models.BigAutoField"

    name = "events"

    verbose_name = "KUCSA Events"