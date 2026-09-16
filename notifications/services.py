from django.conf import settings
from django.core.mail import send_mail

from .models import Notification


def create_notification(
    *,
    recipient,
    title,
    message,
    notification_type=Notification.NotificationType.INFO,
    action_url=None,
    send_email=True,
):
    """
    Create an in-system notification and optionally send
    an email notification to the recipient.

    This is the main function that other KUCSA apps should use
    when they need to notify a user.
    """

    notification = Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
        action_url=action_url,
    )

    if send_email and recipient.email:
        try:
            send_mail(
                subject=title,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                fail_silently=False,
            )

            notification.email_sent = True
            notification.save(update_fields=["email_sent"])

        except Exception:
            # The in-system notification should still exist
            # even if email delivery fails.
            pass

    return notification