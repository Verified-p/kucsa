# attendance/apps.py

from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    """
    Django application configuration for the KUCSA
    Attendance application.

    The Attendance application manages:

        - Event attendance records
        - Attendance sessions
        - Member attendance history
        - Attendance status tracking
        - Attendance statistics
        - Attendance management workflows
        - Attendance audit information
    """

    # =====================================================
    # DEFAULT PRIMARY KEY
    # =====================================================

    default_auto_field = "django.db.models.BigAutoField"

    # =====================================================
    # APPLICATION NAME
    # =====================================================

    name = "attendance"

    # =====================================================
    # HUMAN-READABLE APPLICATION NAME
    # =====================================================

    verbose_name = "KUCSA Attendance"