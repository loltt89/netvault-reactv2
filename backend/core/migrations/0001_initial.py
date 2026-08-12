# Generated migration for SystemSettings model

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SystemSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                # Email Settings
                ('email_host', models.CharField(blank=True, default='smtp.gmail.com', max_length=255)),
                ('email_port', models.IntegerField(default=587)),
                ('email_use_tls', models.BooleanField(default=True)),
                ('email_host_user', models.CharField(blank=True, max_length=255)),
                ('email_host_password_encrypted', models.TextField(blank=True, help_text='Encrypted email password')),
                ('email_from_address', models.EmailField(blank=True, default='noreply@netvault.local', max_length=254)),
                # Telegram Settings
                ('telegram_enabled', models.BooleanField(default=False)),
                ('telegram_bot_token_encrypted', models.TextField(blank=True, help_text='Encrypted Telegram bot token')),
                ('telegram_chat_id', models.CharField(blank=True, max_length=100)),
                # Notification Settings
                ('notify_on_backup_success', models.BooleanField(default=False)),
                ('notify_on_backup_failure', models.BooleanField(default=True)),
                ('notify_schedule_summary', models.BooleanField(default=False)),
                # LDAP Settings
                ('ldap_enabled', models.BooleanField(default=False)),
                ('ldap_server_uri', models.CharField(blank=True, help_text='e.g., ldap://ldap.example.com:389', max_length=255)),
                ('ldap_bind_dn', models.CharField(blank=True, help_text='e.g., cn=admin,dc=example,dc=com', max_length=255)),
                ('ldap_bind_password_encrypted', models.TextField(blank=True, help_text='Encrypted LDAP bind password')),
                ('ldap_user_search_base', models.CharField(blank=True, help_text='e.g., ou=users,dc=example,dc=com', max_length=255)),
                ('ldap_user_search_filter', models.CharField(blank=True, default='(uid=%(user)s)', max_length=255)),
                # Backup Settings
                ('backup_retention_days', models.IntegerField(default=90, help_text='Number of days to keep old backups')),
                ('backup_parallel_workers', models.IntegerField(default=5, help_text='Number of parallel backup workers')),
                # JWT Settings
                ('jwt_access_token_lifetime', models.IntegerField(default=60, help_text='Access token lifetime in minutes')),
                ('jwt_refresh_token_lifetime', models.IntegerField(default=1440, help_text='Refresh token lifetime in minutes (24h)')),
                # Metadata
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'System Settings',
                'verbose_name_plural': 'System Settings',
                'db_table': 'system_settings',
            },
        ),
    ]
