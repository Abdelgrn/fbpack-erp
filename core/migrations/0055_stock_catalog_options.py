from django.db import migrations, models
import django.db.models.deletion

UNITS = ['1', 'BOÎTE', 'ETQ', 'KG', 'L', 'ML', 'PIÈCE', 'SAC', 'U']
DEPOTS = ['ACHAT', 'DECHETS', 'PRODUIT FINI', 'SEMI FINI']
FAMILIES = '''COLLE|DUPLEX IMPRIME|DUPLEX NEUTRE|ENCRES|ETIQUETTES|FILM CPP|FILM OPP|FILM PE|FILM PET|FILM THERMOSOUDABLE|FOIL ALUMINIUM|FOURNITURES|GAINE PERFOREE|INSTRUMENTATION|MONO IMPRIME|MONO NEUTRE|OUTILS D’IMPRESSION|PAPIER|PIECES DE RECHANGE|POLYMERES|PRODUITS SEMI FINIS|SACS COUCHE|SACS KRAFT|SOLVANTS|TRIPLEX IMPRIME|TRIPLEX NEUTRE|VERNIS'''.split('|')
SUBFAMILIES = '''15/15 TRANSPARENT|15/15METALISÉ|20/20 MAT|20/20 MÉTALLISÉ|20/20 TRANSPARENT|20/35 PERLÉ|30/20 MÉTALLISÉ|30/30 TRANSPARENT|80/20|ACÉTATE|ADDITIFS|ADHÉSIFS|ALU/PE|ALU/PET|ALUMINIUM 8 MIC|ANTISTATIQUE|ARGENT|BLANC|BLANC LABEL|BLEU|BLEU REFLEX|BROSSE|CAISSES EN CARTON|CAST 30 TRS|COLD SEAL|COLLE CPX|CYAN|CYLINDRES|DECOLORANT|DURCISSEUR|FILM BLANC PERLE|FILM ETIRABLE|FILM IMPRIMÉ|FILM LAMINÉ|FILM MAT|FILM METALISE|FILM PE LAMINATION|FILM PE LAMINÉ|FILM PE THERMO|FILM TRANSPARENT|GOLD|GOMÉ|INTERCALAIRES|JAUNE|LAMES|LDPE|LESSIVES|LLDPE|MAGENTA|MANDRINS|MARRON|METHOXY|MLLDPE|MOUSSE|NOIR|OPP 15 / 15 TRS|OPP 15 TRS|OPP 15 TRS / OPP 15 TRS|OPP 20 / 20 TRS|OPP 20 / CAST 30|OPP 20 MAT|OPP 20 MATT/MTZ|OPP 20 MTZ|OPP 20 TRS|OPP 20 TRS/MTZ|OPP 30 / 30 TRS|OPP 30 TRS|OPP 30 TRS / CPP 30 TRS|OPP 30 TRS / OPP 20 MTZ|OPP 30/30|OPP 30RTRS / OPP 20 MTZ|OPP 35|OPP 38|OPP TRS/ MTZ|OPP/CAST|OPP/PE|OPP/PET MTZ/PE BLNC|OPP20|OPP30|OPP30-20|OR|ORANGE|PAPIER COUCHÉ|PAPIER KRAFT|PE|PE RECYCLÉ|PEHD|PET 12 / PE 70|PET 12 / PE 80|PET 12 MTZ|PET 12 TRS|PET 12 TRS / MTZ|PET 40|PET MTZ / TRS|PET TRS 12 / PE TRS 68|PET TRS 12 / PE TRS 80|PET/ALU/PE60|PET/ALU/PE75|PET/OPP|PET/OPP MTZ/PE|PET/PE|PET/PET-MET/PE|PET/PET/PE|PET12 / PE 70|PVC|RACLES|RELAIS|RHODAMINE|ROSE|ROUGE|SECURITÉ|VERNIS|VERT|VIOLET'''.split('|')


def seed_catalog(apps, schema_editor):
    Option = apps.get_model('core', 'StockCatalogOption')
    for kind, values in [('UNIT', UNITS), ('DEPOT', DEPOTS), ('FAMILY', FAMILIES), ('SUBFAMILY', SUBFAMILIES)]:
        for i, name in enumerate(values):
            Option.objects.get_or_create(kind=kind, name=name, defaults={'position': i, 'active': True})


class Migration(migrations.Migration):
    dependencies = [('core', '0054_temps_production_job')]
    operations = [
        migrations.CreateModel(
            name='StockCatalogOption',
            fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('kind', models.CharField(choices=[('UNIT', 'Unité'), ('DEPOT', 'Dépôt'), ('FAMILY', 'Famille'), ('SUBFAMILY', 'Sous-famille')], db_index=True, max_length=12, verbose_name='Type de liste')),
                    ('name', models.CharField(max_length=120, verbose_name='Libellé')),
                    ('active', models.BooleanField(default=True, verbose_name='Actif')),
                    ('position', models.PositiveSmallIntegerField(default=0, verbose_name='Ordre'))],
            options={'verbose_name': 'Valeur de catalogue stock', 'verbose_name_plural': 'Valeurs de catalogue stock', 'ordering': ['kind', 'position', 'name']},
        ),
        migrations.AddConstraint(model_name='stockcatalogoption', constraint=models.UniqueConstraint(fields=('kind', 'name'), name='uniq_stock_cat_kind_name')),
        migrations.RunPython(seed_catalog, migrations.RunPython.noop),
        migrations.AlterField(model_name='material', name='unit', field=models.CharField(default='KG', max_length=10, verbose_name='Unité')),
        migrations.AddField(model_name='material', name='depot', field=models.ForeignKey(blank=True, limit_choices_to={'kind': 'DEPOT'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_depot', to='core.stockcatalogoption', verbose_name='Dépôt')),
        migrations.AddField(model_name='material', name='famille', field=models.ForeignKey(blank=True, limit_choices_to={'kind': 'FAMILY'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_family', to='core.stockcatalogoption', verbose_name='Famille')),
        migrations.AddField(model_name='material', name='sous_famille', field=models.ForeignKey(blank=True, limit_choices_to={'kind': 'SUBFAMILY'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_subfamily', to='core.stockcatalogoption', verbose_name='Sous-famille')),
    ]
