from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Event, Ticket

class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 1

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    inlines = [TicketInline]
