from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("course_partnerships", "0014_homepageannouncement"),
    ]

    operations = [
        migrations.AddField(
            model_name="homepageannouncement",
            name="tone",
            field=models.CharField(
                choices=[
                    ("info", "Info"),
                    ("success", "Success"),
                    ("warning", "Warning"),
                    ("alert", "Alert"),
                ],
                default="info",
                help_text="Info is a calm reminder, Success is positive, Warning is caution, and Alert is urgent.",
                max_length=16,
            ),
        ),
    ]
