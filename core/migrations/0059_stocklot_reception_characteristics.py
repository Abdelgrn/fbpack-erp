from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0058_stock_documentline_characteristics')]

    operations = [
        migrations.AddField(
            model_name='stocklot',
            name='micronage',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Micronage (µm)'),
        ),
        migrations.AddField(
            model_name='stocklot',
            name='grammage',
            field=models.FloatField(blank=True, null=True, verbose_name='Grammage (g/m²)'),
        ),
        migrations.AddField(
            model_name='stocklot',
            name='metrage',
            field=models.FloatField(blank=True, null=True, verbose_name='Métrage (m)'),
        ),
        migrations.AddField(
            model_name='stocklot',
            name='poids_kg',
            field=models.FloatField(blank=True, null=True, verbose_name='Poids net (kg)'),
        ),
        migrations.AddField(
            model_name='stocklot',
            name='nombre_unites',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Nombre d’unités'),
        ),
        migrations.AddField(
            model_name='stocklot',
            name='origine',
            field=models.CharField(blank=True, choices=[('IMPORTATION', 'Importation'), ('LOCAL', 'Local')], default='', max_length=15, verbose_name='Origine'),
        ),
    ]
