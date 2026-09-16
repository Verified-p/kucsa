from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    Stores notifications that are displayed inside the KUCSA platform
    and optionally delivered to the user's email.
    """

    class NotificationType(models.TextChoices):
        INFO = "INFO", "Information"
        SUCCESS = "SUCCESS", "Success"
        WARNING = "WARNING", "Warning"
        ERROR = "ERROR", "Error"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    title = models.CharField(
        max_length=255
    )

    message = models.TextField()

    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.INFO,
    )

    # Optional URL to the related page/action.
    # Example: /payments/15/
    action_url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
    )

    is_read = models.BooleanField(
        default=False
    )

    email_sent = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    read_at = models.DateTimeField(
        blank=True,
        null=True
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["recipient", "is_read"]
            ),
            models.Index(
                fields=["recipient", "-created_at"]
            ),
        ]

    def __str__(self):
        return f"{self.title} - {self.recipient}"

    @property
    def is_unread(self):
        return not self.is_read