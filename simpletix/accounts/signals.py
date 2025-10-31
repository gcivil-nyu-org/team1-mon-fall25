# accounts/signals.py
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile



@receiver(user_logged_in)
def clear_guest_on_login(sender, user, request, **kwargs):
    """
    When a real user logs in, drop any anonymous/guest/session role hints
    that may have been set earlier in the same browser.
    """
    if request is not None and hasattr(request, "session"):
        sess = request.session
        sess.pop("guest", None)
        sess.pop("desired_role", None)
        sess.cycle_key()


@receiver(user_logged_out)
def clear_guest_on_logout(sender, user, request, **kwargs):
    """
    On logout, also drop the transient flags so the next user in the same
    browser doesn't inherit them.
    """
    if request is not None and hasattr(request, "session"):
        sess = request.session
        sess.pop("guest", None)
        sess.pop("desired_role", None)
        sess.cycle_key()


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    """
    Always make sure a UserProfile exists.
    """
    if created:
        UserProfile.objects.create(user=instance)
    else:
        # in case something deleted it manually
        UserProfile.objects.get_or_create(user=instance)
