from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0041_notification_center'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OFPrelaunchCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('READY', 'Prêt'), ('WARNING', 'Avertissements'), ('BLOCKED', 'Bloqué')], db_index=True, max_length=10)),
                ('results', models.JSONField(default=list)),
                ('checked_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('launched', models.BooleanField(default=False)),
                ('launched_at', models.DateTimeField(blank=True, null=True)),
                ('override_used', models.BooleanField(default=False)),
                ('override_reason', models.TextField(blank=True)),
                ('override_at', models.DateTimeField(blank=True, null=True)),
                ('checked_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='of_prelaunch_checks', to=settings.AUTH_USER_MODEL)),
                ('of', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prelaunch_checks', to='core.ordrefabrication')),
                ('override_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='of_prelaunch_overrides', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-checked_at']},
        ),
        migrations.AddIndex(model_name='ofprelaunchcheck', index=models.Index(fields=['of', '-checked_at'], name='prelaunch_of_date_idx')),
    ]
