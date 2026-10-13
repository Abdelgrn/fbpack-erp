import unicodedata

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import migrations, models
from django.db.models.deletion import CASCADE, SET_NULL
import django.utils.timezone


def initialize_color_previews(apps, schema_editor):
    PrepressColor = apps.get_model('core', 'PrepressColor')
    known_colors = {
        'cyan': '#00AEEF',
        'magenta': '#EC008C',
        'jaune': '#FFF200',
        'yellow': '#FFF200',
        'noir': '#1F2937',
        'black': '#1F2937',
        'blanc': '#F8FAFC',
        'white': '#F8FAFC',
        'rouge': '#E31E24',
        'red': '#E31E24',
        'vert': '#16A34A',
        'green': '#16A34A',
        'bleu': '#2563EB',
        'blue': '#2563EB',
        'orange': '#F97316',
        'violet': '#7C3AED',
    }
    for color in PrepressColor.objects.all().only('pk', 'nom_couleur').iterator():
        normalized = unicodedata.normalize('NFKD', color.nom_couleur or '')
        normalized = ''.join(char for char in normalized if not unicodedata.combining(char)).lower()
        selected = '#FFFFFF'
        for name, hex_value in known_colors.items():
            if name in normalized:
                selected = hex_value
                break
        PrepressColor.objects.filter(pk=color.pk).update(couleur_hex=selected)


def reverse_color_previews(apps, schema_editor):
    # La suppression du champ lors d'un retour arrière suffit ; aucune donnée
    # historique existante n'est modifiée par cette fonction.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0047_security_connection_monitoring'),
    ]

    operations = [
        migrations.AddField(
            model_name='prepresscolor',
            name='couleur_hex',
            field=models.CharField(
                default='#FFFFFF',
                max_length=7,
                validators=[RegexValidator(
                    '^#[0-9A-Fa-f]{6}$',
                    'Saisissez une couleur au format #RRGGBB.',
                )],
                verbose_name='Aperçu couleur',
            ),
        ),
        migrations.AddField(
            model_name='technicalproduct',
            name='last_modified_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=SET_NULL,
                related_name='technical_products_modified',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Dernière modification par',
            ),
        ),
        migrations.AddField(
            model_name='technicalproduct',
            name='printing_process',
            field=models.CharField(
                choices=[('FLEXO', 'Flexographie'), ('HELIO', 'Héliogravure'), ('AUTRE', 'Autre')],
                default='FLEXO',
                max_length=20,
                verbose_name="Procédé d'impression",
            ),
        ),
        migrations.AddField(
            model_name='technicalproduct',
            name='product_visual',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='technical_products/visuals/%Y/%m/',
                verbose_name='Visuel du produit',
            ),
        ),
        migrations.AddField(
            model_name='technicalproduct',
            name='technical_notes',
            field=models.TextField(blank=True, default='', verbose_name='Observations techniques'),
        ),
        migrations.AddField(
            model_name='technicalproduct',
            name='updated_at',
            field=models.DateTimeField(
                auto_now=True,
                default=django.utils.timezone.now,
                verbose_name='Dernière modification',
            ),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name='TechnicalProductRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revision_number', models.PositiveIntegerField(verbose_name='Révision')),
                ('snapshot', models.JSONField(default=dict, verbose_name='Données sauvegardées')),
                ('reason', models.CharField(blank=True, max_length=250, verbose_name='Motif')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=SET_NULL,
                    related_name='technical_product_revisions',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('product', models.ForeignKey(
                    on_delete=CASCADE,
                    related_name='revisions',
                    to='core.technicalproduct',
                )),
            ],
            options={
                'verbose_name': 'Révision de fiche technique',
                'verbose_name_plural': 'Révisions de fiches techniques',
                'ordering': ['-revision_number'],
                'indexes': [
                    models.Index(
                        fields=['product', '-revision_number'],
                        name='prepress_revision_product_idx',
                    ),
                ],
                'constraints': [
                    models.UniqueConstraint(
                        fields=('product', 'revision_number'),
                        name='unique_product_technical_revision',
                    ),
                ],
            },
        ),
        migrations.RunPython(initialize_color_previews, reverse_color_previews),
    ]
