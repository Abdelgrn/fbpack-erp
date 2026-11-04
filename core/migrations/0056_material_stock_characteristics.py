from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0055_stock_catalog_options')]
    operations = [
        migrations.AddField(
            model_name='material', name='laize_mm',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Laize (mm)'),
        ),
        migrations.AddField(
            model_name='material', name='origine',
            field=models.CharField(blank=True, choices=[('IMPORTATION', 'Importation'), ('LOCAL', 'Local')], default='', max_length=15, verbose_name='Origine'),
        ),
        migrations.AddField(
            model_name='material', name='poids_kg',
            field=models.FloatField(blank=True, null=True, verbose_name='Poids (kg)'),
        ),
        migrations.AddField(
            model_name='material', name='nombre_unites',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Nombre d’unités'),
        ),
    ]
