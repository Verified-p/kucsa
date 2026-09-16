from django.db.models import QuerySet

from .models import Notification


def notifications_context(request):
    """
    Make notification information available globally to templates.

    This allows the KUCSA navbar and other shared templates to access
    the logged-in user's notifications without adding notification
    queries to every individual view.
    """

    if not request.user.is_authenticated:
        return {
            "kucsa_notifications": Notification.objects.none(),
            "kucsa_unread_notifications_count": 0,
        }

    notifications: QuerySet[Notification] = (
        Notification.objects
        .filter(recipient=request.user)
        .order_by("-created_at")
    )

    unread_notifications_count = notifications.filter(
        is_read=False
    ).count()

    recent_notifications = notifications[:5]

    return {
        "kucsa_notifications": recent_notifications,
        "kucsa_unread_notifications_count": unread_notifications_count,
    }