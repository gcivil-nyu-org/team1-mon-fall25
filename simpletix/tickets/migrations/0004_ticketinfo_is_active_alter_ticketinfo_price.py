# tickets/migrations/0004_ticketinfo_is_active_alter_ticketinfo_price.py

from django.db import migrations


class Migration(migrations.Migration):

    # Keep this dependency consistent with what you had before.
    # For this filename it is almost certainly 0003:
    dependencies = [
        ("tickets", "0003_alter_ticketinfo_availability_alter_ticketinfo_price"),
    ]

    # NOTE:
    # - TicketInfo.is_active is already defined in 0001_initial.
    # - This migration originally re-added that column, which caused
    #   "DuplicateColumn: ... is_active of relation tickets_ticketinfo already exists"
    #   when migrations were replayed (e.g., in tests).
    # - We convert this to a no-op to keep migration history intact but avoid
    #   trying to add the same column again.
    operations = []
