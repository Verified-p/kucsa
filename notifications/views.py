from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Notification


@login_required
def notification_list(request):
    """
    Display all notifications belonging to the logged-in user.
    """

    notifications = Notification.objects.filter(
        recipient=request.user
    )

    unread_count = notifications.filter(
        is_read=False
    ).count()

    context = {
        "notifications": notifications,
        "unread_count": unread_count,
    }

    return render(
        request,
        "notification_list.html",
        context,
    )


@login_required
def notification_detail(request, pk):
    """
    Display a single notification.

    Opening a notification automatically marks it as read.
    """

    notification = get_object_or_404(
        Notification,
        pk=pk,
        recipient=request.user,
    )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()

        notification.save(
            update_fields=["is_read", "read_at"]
        )

    context = {
        "notification": notification,
    }

    return render(
        request,
        "notification_detail.html",
        context,
    )


@login_required
def mark_notification_read(request, pk):
    """
    Mark a specific notification as read.
    """

    notification = get_object_or_404(
        Notification,
        pk=pk,
        recipient=request.user,
    )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()

        notification.save(
            update_fields=["is_read", "read_at"]
        )

    return redirect("notifications:list")


@login_required
def mark_all_notifications_read(request):
    """
    Mark all unread notifications belonging to the
    logged-in user as read.
    """

    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(
        is_read=True,
        read_at=timezone.now(),
    )

    messages.success(
        request,
        "All notifications have been marked as read.",
    )

    return redirect("notifications:list")