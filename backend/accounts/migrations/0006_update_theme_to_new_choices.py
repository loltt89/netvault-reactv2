# Generated migration to update theme choices and migrate old values

from django.db import migrations, models


def migrate_themes_to_new(apps, schema_editor):
    """Migrate old theme values to new theme system"""
    User = apps.get_model('accounts', 'User')

    # Mapping old theme names to new ones
    theme_mapping = {
        'light': 'neumorphism',
        'dark_blue': 'industrial',
        'teal_light': 'isometric',
        'deep_dark': 'blueprint',
    }

    for old_theme, new_theme in theme_mapping.items():
        User.objects.filter(theme=old_theme).update(theme=new_theme)


def reverse_migrate_themes(apps, schema_editor):
    """Reverse migration: convert new themes back to old"""
    User = apps.get_model('accounts', 'User')

    theme_mapping = {
        'neumorphism': 'light',
        'industrial': 'dark_blue',
        'isometric': 'teal_light',
        'glassmorphism': 'light',
        'blueprint': 'deep_dark',
    }

    for new_theme, old_theme in theme_mapping.items():
        User.objects.filter(theme=new_theme).update(theme=old_theme)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_sync_theme_choices'),
    ]

    operations = [
        # First migrate existing data
        migrations.RunPython(migrate_themes_to_new, reverse_code=reverse_migrate_themes),

        # Then update field with new choices and default
        migrations.AlterField(
            model_name='user',
            name='theme',
            field=models.CharField(
                choices=[
                    ('industrial', 'Industrial'),
                    ('neumorphism', 'Neumorphism'),
                    ('isometric', 'Isometric'),
                    ('glassmorphism', 'Glassmorphism'),
                    ('blueprint', 'Blueprint'),
                ],
                default='industrial',
                max_length=20
            ),
        ),
    ]
