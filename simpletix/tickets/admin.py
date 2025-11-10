# Register your models here.
from django.contrib import admin
from .models import TicketInfo, Ticket


@admin.register(TicketInfo)
class TicketInfoAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "category", "price", "availability")
    list_filter = ("event", "category")
    search_fields = ("event__title",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "ticketInfo",
        "full_name",
        "email",
        "status",
        "order_id",
        "issued_at",
    )
    list_filter = ("status", "ticketInfo__event")
    search_fields = ("full_name", "email", "order_id")
