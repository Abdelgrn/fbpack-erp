from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0057_stock_print_documents')]

    operations = [
        migrations.AddField(
            model_name='stockprintdocumentline',
            name='metrage',
            field=models.FloatField(blank=True, null=True, verbose_name='Métrage (m)'),
        ),
        migrations.AddField(
            model_name='stockprintdocumentline',
            name='poids_kg',
            field=models.FloatField(blank=True, null=True, verbose_name='Poids (kg)'),
        ),
        migrations.AddField(
            model_name='stockprintdocumentline',
            name='nombre_unites',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Nombre d’unités'),
        ),
    ]
