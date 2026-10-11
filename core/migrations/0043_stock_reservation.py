from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('core', '0042_prelaunch_verification'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='OFMaterialRequirement', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('quantity_required', models.FloatField(validators=[django.core.validators.MinValueValidator(1e-06)])),
            ('notes', models.CharField(blank=True, max_length=250)), ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_material_requirements', to=settings.AUTH_USER_MODEL)),
            ('material', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='of_requirements', to='core.material')),
            ('of', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='material_requirements', to='core.ordrefabrication')),
        ], options={'ordering': ['material__name']}),
        migrations.CreateModel(name='StockReservation', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('quantity_reserved', models.FloatField(validators=[django.core.validators.MinValueValidator(1e-06)])), ('quantity_consumed', models.FloatField(default=0)), ('quantity_released', models.FloatField(default=0)),
            ('status', models.CharField(choices=[('ACTIVE','Active'),('CONSUMED','Consommée'),('RELEASED','Libérée'),('CANCELLED','Annulée')], db_index=True, default='ACTIVE', max_length=10)),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_stock_reservations', to=settings.AUTH_USER_MODEL)),
            ('lot', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='of_reservations', to='core.stocklot')),
            ('requirement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reservations', to='core.ofmaterialrequirement')),
        ], options={'ordering': ['lot__date_reception','id']}),
        migrations.CreateModel(name='StockReservationEvent', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('action', models.CharField(choices=[('RESERVE','Réservation'),('RELEASE','Libération'),('CONSUME','Consommation'),('CANCEL','Annulation')], max_length=10)),
            ('quantity', models.FloatField(validators=[django.core.validators.MinValueValidator(1e-06)])), ('reason', models.CharField(blank=True, max_length=250)), ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ('reservation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='events', to='core.stockreservation')),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stock_reservation_events', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering':['-created_at']}),
        migrations.AddConstraint(model_name='ofmaterialrequirement', constraint=models.UniqueConstraint(fields=('of','material'), name='unique_of_material_requirement')),
        migrations.AddConstraint(model_name='stockreservation', constraint=models.UniqueConstraint(fields=('requirement','lot'), name='unique_requirement_lot_reservation')),
        migrations.AddIndex(model_name='stockreservation', index=models.Index(fields=['lot','status'], name='reservation_lot_status_idx')),
    ]
