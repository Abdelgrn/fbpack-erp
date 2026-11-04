from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0060_stockdocumentline_receipt_snapshots')]

    operations = [
        migrations.AlterField(
            model_name='stockmovement',
            name='type',
            field=models.CharField(
                choices=[
                    ('ENTREE', 'Entrée (Achat / Réception)'),
                    ('SORTIE', 'Sortie (Production)'),
                    ('TRANSFERT', 'Transfert interne'),
                    ('AJUSTEMENT', 'Ajustement inventaire'),
                    ('RETOUR', 'Retour fournisseur'),
                    ('RETOUR_INTERNE', 'Retour interne (atelier → magasin)'),
                    ('PERTE', 'Perte / Déchet'),
                ],
                max_length=20,
                verbose_name='Type de mouvement',
            ),
        ),
    ]
