from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0040_tooling_supplier_colors'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ERPNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dedup_key', models.CharField(db_index=True, max_length=190, unique=True, verbose_name='Clé anti-doublon')),
                ('module', models.CharField(choices=[('stock', 'Stocks & Achats'), ('planning', 'Planning'), ('planification', 'Planification'), ('production', 'Production'), ('prepress', 'Prépresse'), ('maintenance', 'Maintenance'), ('crm', 'CRM'), ('dashboard', 'Général')], db_index=True, max_length=20)),
                ('level', models.CharField(choices=[('INFO', 'Information'), ('WARNING', 'Attention'), ('CRITICAL', 'Critique'), ('SUCCESS', 'Succès')], db_index=True, default='INFO', max_length=10)),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField(blank=True)),
                ('url', models.CharField(blank=True, max_length=500)),
                ('icon', models.CharField(default='🔔', max_length=10)),
                ('source_model', models.CharField(blank=True, max_length=100)),
                ('source_id', models.PositiveBigIntegerField(blank=True, null=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('first_seen_at', models.DateTimeField(auto_now_add=True)),
                ('last_seen_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-level', '-last_seen_at']},
        ),
        migrations.CreateModel(
            name='ERPNotificationState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_read', models.BooleanField(db_index=True, default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('is_processed', models.BooleanField(db_index=True, default=False)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('notification', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_states', to='core.erpnotification')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='erp_notification_states', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(model_name='erpnotification', index=models.Index(fields=['is_active', 'module', 'level'], name='notif_active_module_idx')),
        migrations.AddConstraint(model_name='erpnotificationstate', constraint=models.UniqueConstraint(fields=('user', 'notification'), name='unique_notification_state_user')),
        migrations.AddIndex(model_name='erpnotificationstate', index=models.Index(fields=['user', 'is_read', 'is_processed'], name='notif_state_user_idx')),
    ]
