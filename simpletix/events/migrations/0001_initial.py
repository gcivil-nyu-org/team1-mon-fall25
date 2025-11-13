from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0004_userprofile"),
    ]

    operations = [
        migrations.RunSQL(
            sql="SELECT 1;",  # No-op SQL that always succeeds
            reverse_sql="SELECT 1;",
            state_operations=[
                migrations.CreateModel(
                    name="Event",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("title", models.CharField(max_length=200)),
                        ("description", models.TextField(blank=True)),
                        ("date", models.DateField(blank=True, null=True)),
                        ("time", models.TimeField(blank=True, null=True)),
                        ("location", models.CharField(max_length=255)),
                        ("formatted_address", models.CharField(blank=True, max_length=255)),
                        ("latitude", models.FloatField(blank=True, null=True)),
                        ("longitude", models.FloatField(blank=True, null=True)),
                        ("banner", models.ImageField(blank=True, null=True, upload_to="banners/")),
                        ("video", models.FileField(blank=True, null=True, upload_to="event_videos/")),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        ("organizer", models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name="creates", to="accounts.organizerprofile")),
                    ],
                ),
                migrations.CreateModel(
                    name="EventTimeSlot",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("date", models.DateField()),
                        ("start_time", models.TimeField()),
                        ("end_time", models.TimeField()),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="time_slots", to="events.event")),
                    ],
                    options={"ordering": ["date", "start_time"]},
                ),
            ],
        ),
    ]