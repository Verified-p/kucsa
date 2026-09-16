from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "recipient",
        "notification_type",
        "is_read",
        "email_sent",
        "created_at",
    )

    list_filter = (
        "notification_type",
        "is_read",
        "email_sent",
        "created_at",
    )

    search_fields = (
        "title",
        "message",
        "recipient__email",
        "recipient__first_name",
        "recipient__last_name",
    )

    readonly_fields = (
        "created_at",
        "read_at",
        "email_sent",
    )

    ordering = (
        "-created_at",
    )

    list_per_page = 25