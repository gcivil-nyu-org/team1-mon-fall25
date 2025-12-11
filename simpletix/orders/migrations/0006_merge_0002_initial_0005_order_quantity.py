from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_initial"),
        ("orders", "0005_order_quantity"),
    ]

    # IMPORTANT: no AddField here – just a no-op merge migration.
    operations = []
