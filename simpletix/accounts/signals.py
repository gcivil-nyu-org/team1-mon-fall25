# accounts/signals.py
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db.models.signals import post_save

from .models import UserProfile


@receiver(user_logged_in)
def clear_guest_on_login(sender, user, request, **kwargs):
    # Drop the guest flag as soon as a real session is authenticated
    if request and hasattr(request, "session"):
        request.session.pop("guest", None)


@receiver(user_logged_out)
def clear_guest_on_logout(sender, user, request, **kwargs):
    # Clean up on logout too (nice to have)
    if request and hasattr(request, "session"):
        request.session.pop("guest", None)
        # optional: also clear role hint
        # request.session.pop("desired_role", None)


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    # ensure exists
    UserProfile.objects.get_or_create(user=instance)
