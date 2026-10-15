from django.db import migrations


def set_weight_default(apps, schema_editor):
    """Проставить DB-level default для weight там, где СУБД это поддерживает.

    SQLite не поддерживает ALTER COLUMN ... SET DEFAULT, поэтому для него
    операция пропускается — на уровне модели default=1 уже задан.
    """
    vendor = schema_editor.connection.vendor
    if vendor in ('mysql', 'postgresql'):
        schema_editor.execute(
            "ALTER TABLE events_vote ALTER COLUMN weight SET DEFAULT 1.00;"
        )


def drop_weight_default(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor in ('mysql', 'postgresql'):
        schema_editor.execute(
            "ALTER TABLE events_vote ALTER COLUMN weight DROP DEFAULT;"
        )


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0005_vote_weight'),
    ]

    operations = [
        migrations.RunPython(set_weight_default, drop_weight_default),
    ]
