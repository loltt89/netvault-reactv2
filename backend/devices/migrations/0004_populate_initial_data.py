# Generated migration - Populate initial vendors and device types
# NOTE: This migration has been replaced by management command: add_popular_vendors
# Keeping migration file for dependency chain, but operations are now noop
from django.db import migrations


def populate_initial_data(apps, schema_editor):
    """
    This function is now a no-op.
    Vendors are populated via management command: python manage.py add_popular_vendors
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('devices', '0003_add_is_predefined_to_devicetype'),
    ]

    operations = [
        migrations.RunPython(populate_initial_data, migrations.RunPython.noop),
    ]
