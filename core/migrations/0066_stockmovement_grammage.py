from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0065_stock_document_catalog_snapshots'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockmovement',
            name='grammage',
            field=models.FloatField(blank=True, null=True, verbose_name='Grammage mouvement (g/m²)'),
        ),
    ]
