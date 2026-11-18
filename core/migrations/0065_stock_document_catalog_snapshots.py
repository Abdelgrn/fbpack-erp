from django.db import migrations, models


def fill_snapshots(apps, schema_editor):
    Line = apps.get_model('core', 'StockPrintDocumentLine')
    for line in Line.objects.select_related('material', 'material__depot', 'material__famille', 'material__sous_famille').iterator():
        m = line.material
        line.code_snapshot = m.code or ''
        line.depot_snapshot = m.depot.name if m.depot_id else ''
        line.famille_snapshot = m.famille.name if m.famille_id else ''
        line.sous_famille_snapshot = m.sous_famille.name if m.sous_famille_id else ''
        line.save(update_fields=['code_snapshot', 'depot_snapshot', 'famille_snapshot', 'sous_famille_snapshot'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0064_usermodulepermission_poste'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockprintdocumentline',
            name='code_snapshot',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='N°.Produit'),
        ),
        migrations.AddField(
            model_name='stockprintdocumentline',
            name='depot_snapshot',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='Dépôt'),
        ),
        migrations.AddField(
            model_name='stockprintdocumentline',
            name='famille_snapshot',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='Famille'),
        ),
        migrations.AddField(
            model_name='stockprintdocumentline',
            name='sous_famille_snapshot',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='Sous-famille'),
        ),
        migrations.RunPython(fill_snapshots, migrations.RunPython.noop),
    ]
