"""
Convert the free-text columns to utf8mb4 so emoji can be stored.

Creators may paste emoji into the instructor, tools or notes fields. The
default MySQL charset on Open edX is 3-byte ``utf8``, which rejects them with
"Incorrect string value" (Tibetan is 3-byte and fine either way). This widens
those columns to ``utf8mb4`` on MySQL; it is a no-op on other backends (e.g.
SQLite in tests). Same approach as ai_course_creator/migrations/0002_utf8mb4.py.
"""

from django.db import migrations

UTF8MB4 = "utf8mb4"
COLLATION = "utf8mb4_unicode_ci"

# (table, column, column definition) tuples to convert.
COLUMNS = [
    ("course_schedule_sectionschedule", "instructor", "VARCHAR(255)"),
    ("course_schedule_sectionschedule", "tools_required", "LONGTEXT"),
    ("course_schedule_sectionschedule", "notes", "LONGTEXT"),
]


def to_utf8mb4(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table, column, definition in COLUMNS:
            cursor.execute(
                f"ALTER TABLE {table} MODIFY {column} {definition} "
                f"CHARACTER SET {UTF8MB4} COLLATE {COLLATION} NOT NULL"
            )


def noop_reverse(apps, schema_editor):
    # We intentionally do not convert back to utf8 (would lose data / serve no purpose).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("course_schedule", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(to_utf8mb4, noop_reverse),
    ]
