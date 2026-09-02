# accounts/signals.py

from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import User


@receiver(pre_save, sender=User)
def set_default_user_values(sender, instance, **kwargs):
    """
    Set default values before saving a new user.
    """

    if instance._state.adding:

        if not instance.role:
            instance.role = User.Role.STUDENT

        if instance.is_verified is None:
            instance.is_verified = False