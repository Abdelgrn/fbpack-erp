from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('core', '0045_alter_aniloxroll_volume_cm3_m2_and_more'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='usermodulepermission', name='can_access_kpi', field=models.BooleanField(default=False, verbose_name='KPI & Data Analyse')),
        migrations.CreateModel(name='ModuleAdministrator', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('module', models.CharField(choices=[('dashboard','Dashboard'),('planning','Planning Gantt'),('reporting','Reporting'),('kpi','KPI & Data Analyse'),('crm','CRM & Devis'),('prepress','Prépresse & Outils'),('planification','Planification Atelier'),('production','Production'),('stock','Stocks & Achats'),('maintenance','Maintenance'),('drh','Ressources Humaines'),('chat','Chat'),('import','Import Excel')], max_length=30)),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('is_active', models.BooleanField(default=True)),
            ('granted_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='module_admin_grants', to=settings.AUTH_USER_MODEL)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='administered_modules', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering':['module','user__username']}),
        migrations.AddConstraint(model_name='moduleadministrator', constraint=models.UniqueConstraint(fields=('user','module'), name='unique_module_administrator')),
        migrations.CreateModel(name='AdministrationAuditLog', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('action', models.CharField(max_length=40)), ('module', models.CharField(blank=True, max_length=30)),
            ('details', models.TextField(blank=True)), ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='erp_admin_actions', to=settings.AUTH_USER_MODEL)),
            ('target_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='erp_admin_history', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering':['-created_at']}),
    ]
