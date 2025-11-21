# events/admin.py - UPDATE to add notification model

from django.contrib import admin
from .models import Event, EventNotificationSubscription


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "__str__")


# NEW: Admin for notification subscriptions
@admin.register(EventNotificationSubscription)
class EventNotificationSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "email", "name", "created_at")
    list_filter = ("event", "created_at")
    search_fields = ("email", "name", "event__title")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    
    def has_add_permission(self, request):
        # Prevent manual adding from admin
        return False