from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    # Keep it super safe: these will always exist
    list_display = ("id", "__str__")
