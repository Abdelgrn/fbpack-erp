from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0061_stockmovement_internal_return')]

    operations = [
        migrations.AddField(
            model_name='stockmovement', name='laize_mm',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Laize mouvement (mm)'),
        ),
        migrations.AddField(
            model_name='stockmovement', name='micronage',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Micronage mouvement (µm)'),
        ),
        migrations.AddField(
            model_name='stockmovement', name='metrage',
            field=models.FloatField(blank=True, null=True, verbose_name='Métrage mouvement (m)'),
        ),
        migrations.AddField(
            model_name='stockmovement', name='poids_kg',
            field=models.FloatField(blank=True, null=True, verbose_name='Poids mouvement (kg)'),
        ),
    ]
