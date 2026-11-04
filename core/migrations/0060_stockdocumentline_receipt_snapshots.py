from django.db import migrations, models


def populate_receipt_snapshots(apps, schema_editor):
    Line = apps.get_model('core', 'StockPrintDocumentLine')
    for line in Line.objects.select_related('material', 'lot', 'movement').iterator():
        material = line.material
        lot = line.lot
        line.univers_snapshot = material.category or ''
        line.origine_snapshot = (getattr(lot, 'origine', '') if lot else '') or material.origine or ''
        line.laize_mm_snapshot = (getattr(lot, 'laize', None) if lot else None)
        if line.laize_mm_snapshot is None:
            line.laize_mm_snapshot = material.laize_mm
        line.micronage_snapshot = (getattr(lot, 'micronage', None) if lot else None)
        if line.micronage_snapshot is None:
            line.micronage_snapshot = material.micronage_standard
        line.grammage_snapshot = (getattr(lot, 'grammage', None) if lot else None)
        if line.grammage_snapshot is None:
            line.grammage_snapshot = material.grammage
        if material.category == 'FILM' and line.metrage is None:
            line.metrage = (getattr(lot, 'metrage', None) if lot else None)
            if line.metrage is None and lot:
                line.metrage = lot.longueur
            if line.metrage is None:
                line.metrage = material.metrage_standard
        if line.poids_kg is None:
            line.poids_kg = (getattr(lot, 'poids_kg', None) if lot else None)
            if line.poids_kg is None:
                line.poids_kg = material.poids_kg
            if line.poids_kg is None and str(material.unit or '').strip().upper() in {'KG', 'KGS'}:
                line.poids_kg = line.quantity
        if line.nombre_unites is None:
            line.nombre_unites = (getattr(lot, 'nombre_unites', None) if lot else None)
            if line.nombre_unites is None:
                line.nombre_unites = material.nombre_unites
        if line.emplacement_id is None and line.movement_id:
            line.emplacement_id = line.movement.emplacement_destination_id
        line.save(update_fields=[
            'univers_snapshot', 'origine_snapshot', 'laize_mm_snapshot',
            'micronage_snapshot', 'grammage_snapshot', 'metrage', 'poids_kg',
            'nombre_unites', 'emplacement',
        ])


class Migration(migrations.Migration):
    dependencies = [('core', '0059_stocklot_reception_characteristics')]

    operations = [
        migrations.AddField(
            model_name='stockprintdocumentline',
            name='univers_snapshot',
            field=models.CharField(blank=True, max_length=30, verbose_name='Univers'),
        ),
        migrations.AddField(
            model_name='stockprintdocumentline',
            name='origine_snapshot',
            field=models.CharField(blank=True, max_length=15, verbose_name='Origine'),
        ),
        migrations.AddField(
            model_name='stockprintdocumentline',
            name='laize_mm_snapshot',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Laize (mm)'),
        ),
        migrations.AddField(
            model_name='stockprintdocumentline',
            name='micronage_snapshot',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Micronage (µm)'),
        ),
        migrations.AddField(
            model_name='stockprintdocumentline',
            name='grammage_snapshot',
            field=models.FloatField(blank=True, null=True, verbose_name='Grammage (g/m²)'),
        ),
        migrations.RunPython(populate_receipt_snapshots, migrations.RunPython.noop),
    ]
