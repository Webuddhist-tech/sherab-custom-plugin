from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("course_partnerships", "0013_partner_invite_instructions"),
    ]

    operations = [
        migrations.CreateModel(
            name="HomepageAnnouncement",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.TextField(help_text="Plain text shown in the banner. A URL is shown as text.")),
                (
                    "enabled",
                    models.BooleanField(
                        default=False,
                        help_text="Uncheck to hide the banner immediately, even inside the time window.",
                    ),
                ),
                (
                    "start_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Leave blank to show as soon as the banner is enabled.",
                        null=True,
                    ),
                ),
                (
                    "end_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Leave blank to keep showing until the banner is disabled. Hidden once this time is reached.",
                        null=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "Homepage Announcement",
                "verbose_name_plural": "Homepage Announcements",
                "ordering": ["-id"],
            },
        ),
    ]
