from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0056_material_stock_characteristics'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='StockPrintDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('SORTIE_JOURNALIERE', 'Bon de sortie journalier'), ('RECEPTION', 'Bon de réception'), ('RETOUR_INTERNE', 'Bon de retour interne'), ('RETOUR_FOURNISSEUR', 'Bon de retour fournisseur'), ('AVARIE', 'Bon d’avarie')], db_index=True, max_length=24, verbose_name='Type de bon')),
                ('reference', models.CharField(blank=True, max_length=40, null=True, unique=True, verbose_name='Référence')),
                ('document_date', models.DateField(db_index=True, default=django.utils.timezone.now, verbose_name='Date du document')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Créé le')),
                ('notes', models.TextField(blank=True, verbose_name='Observations')),
                ('bon_commande', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_print_documents', to='core.boncommande')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_print_documents', to=settings.AUTH_USER_MODEL)),
                ('movements', models.ManyToManyField(blank=True, related_name='print_documents', to='core.stockmovement')),
                ('supplier', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stock_print_documents', to='core.supplier')),
            ],
            options={'verbose_name': 'Bon de stock imprimable', 'verbose_name_plural': 'Bons de stock imprimables', 'ordering': ['-document_date', '-id']},
        ),
        migrations.CreateModel(
            name='StockPrintDocumentLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.FloatField(verbose_name='Quantité')),
                ('unit_snapshot', models.CharField(blank=True, max_length=20, verbose_name='Unité')),
                ('notes', models.CharField(blank=True, max_length=300, verbose_name='Motif / observations')),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='core.stockprintdocument')),
                ('emplacement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='document_lines', to='core.stocklocation')),
                ('lot', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='document_lines', to='core.stocklot')),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stock_document_lines', to='core.material')),
                ('movement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='document_lines', to='core.stockmovement')),
            ],
            options={'verbose_name': 'Ligne de bon de stock', 'verbose_name_plural': 'Lignes de bon de stock'},
        ),
    ]
