# Generated for Django 4.2.29 — FB PACK security connection monitoring.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0046_module_administration'),
    ]

    operations = [
        migrations.CreateModel(
            name='AccountSecurityState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('temporarily_disabled_until', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('disabled_reason', models.CharField(blank=True, max_length=255)),
                ('was_active_before_disable', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('disabled_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='temporary_account_disables', to=settings.AUTH_USER_MODEL)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='security_state', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'État de sécurité du compte',
                'verbose_name_plural': 'États de sécurité des comptes',
            },
        ),
        migrations.CreateModel(
            name='SecuritySession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_fingerprint', models.CharField(db_index=True, help_text='HMAC-SHA-256 de la clé de session, jamais la clé brute.', max_length=64, unique=True)),
                ('status', models.CharField(choices=[('ACTIVE', 'Ouverte'), ('LOGGED_OUT', 'Déconnectée'), ('EXPIRED', 'Expirée'), ('REVOKED', 'Révoquée')], db_index=True, default='ACTIVE', max_length=16)),
                ('initial_client_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('client_ip', models.GenericIPAddressField(blank=True, db_index=True, null=True)),
                ('proxy_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=512)),
                ('device', models.CharField(blank=True, max_length=80)),
                ('browser', models.CharField(blank=True, max_length=80)),
                ('operating_system', models.CharField(blank=True, max_length=80)),
                ('device_fingerprint', models.CharField(blank=True, db_index=True, max_length=64)),
                ('first_login_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('last_activity_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('recent_path', models.CharField(blank=True, max_length=255)),
                ('ended_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('revoked_reason', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('revoked_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='revoked_security_sessions', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='security_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Session de sécurité',
                'verbose_name_plural': 'Sessions de sécurité',
                'ordering': ['-last_activity_at'],
                'indexes': [models.Index(fields=['user', 'status', 'last_activity_at'], name='sec_sess_user_status_idx'), models.Index(fields=['status', 'last_activity_at'], name='sec_sess_status_seen_idx')],
            },
        ),
        migrations.CreateModel(
            name='SecurityEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('LOGIN_SUCCESS', 'Connexion réussie'), ('LOGIN_FAILED', 'Échec de connexion'), ('LOGIN_LOCKED', 'Connexion verrouillée'), ('LOGOUT', 'Déconnexion'), ('SESSION_EXPIRED', 'Session expirée'), ('SESSION_REVOKED', 'Session révoquée'), ('ACCESS_DENIED', 'Accès refusé'), ('IP_CHANGED', 'IP changée en session'), ('NEW_IP', 'Nouvelle IP'), ('NEW_DEVICE', 'Nouvel appareil'), ('ACCOUNT_DISABLED_ATTEMPT', 'Tentative sur compte désactivé'), ('SUSPICIOUS_ACTIVITY', 'Activité suspecte'), ('SECURITY_ACTION', 'Action de sécurité')], db_index=True, max_length=32)),
                ('submitted_identity_hash', models.CharField(blank=True, db_index=True, help_text="Empreinte HMAC du nom saisi lors d'un échec.", max_length=64)),
                ('occurred_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('client_ip', models.GenericIPAddressField(blank=True, db_index=True, null=True)),
                ('proxy_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=512)),
                ('device', models.CharField(blank=True, max_length=80)),
                ('browser', models.CharField(blank=True, max_length=80)),
                ('operating_system', models.CharField(blank=True, max_length=80)),
                ('route', models.CharField(blank=True, db_index=True, max_length=255)),
                ('risk_level', models.CharField(choices=[('NORMAL', 'Normal'), ('WARNING', 'Avertissement'), ('SUSPICIOUS', 'Suspect'), ('CRITICAL', 'Critique')], db_index=True, default='NORMAL', max_length=16)),
                ('reason', models.CharField(blank=True, max_length=500)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('session', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events', to='core.securitysession')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='security_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Événement de sécurité',
                'verbose_name_plural': 'Événements de sécurité',
                'ordering': ['-occurred_at', '-id'],
                'indexes': [models.Index(fields=['event_type', 'occurred_at'], name='sec_evt_type_date_idx'), models.Index(fields=['risk_level', 'occurred_at'], name='sec_evt_risk_date_idx'), models.Index(fields=['user', 'occurred_at'], name='sec_evt_user_date_idx')],
            },
        ),
        migrations.CreateModel(
            name='KnownAccessSignature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('IP', 'Adresse IP'), ('DEVICE', 'Appareil')], max_length=12)),
                ('fingerprint', models.CharField(max_length=64)),
                ('display_value', models.CharField(blank=True, max_length=255)),
                ('is_recognized', models.BooleanField(db_index=True, default=False)),
                ('first_seen_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_seen_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('recognized_at', models.DateTimeField(blank=True, null=True)),
                ('recognized_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recognized_access_signatures', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='known_access_signatures', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': "Signature d'accès connue",
                'verbose_name_plural': "Signatures d'accès connues",
                'ordering': ['user__username', 'kind', '-last_seen_at'],
                'indexes': [models.Index(fields=['user', 'kind', 'last_seen_at'], name='sec_sig_user_kind_idx')],
                'constraints': [models.UniqueConstraint(fields=('user', 'kind', 'fingerprint'), name='unique_user_security_signature')],
            },
        ),
    ]
