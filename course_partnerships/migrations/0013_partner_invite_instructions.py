import ckeditor.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("course_partnerships", "0012_alter_herocourse_new_until"),
    ]

    operations = [
        migrations.AddField(
            model_name="partner",
            name="invite_instructions",
            field=ckeditor.fields.RichTextField(blank=True, null=True, verbose_name="Invite Instructions"),
        ),
    ]
