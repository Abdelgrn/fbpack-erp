from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0062_stockmovement_characteristics')]

    operations = [
        migrations.AddField(
            model_name='stockmovement',
            name='nombre_unites',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Nombre d’articles'),
        ),
        migrations.AlterField(
            model_name='stockmovement',
            name='poids_kg',
            field=models.FloatField(blank=True, null=True, verbose_name='Poids par article (kg)'),
        ),
    ]
