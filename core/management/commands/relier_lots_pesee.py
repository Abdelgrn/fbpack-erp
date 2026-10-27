"""Rattache les lots « à relier » aux clients et produits de l'ERP.

- Ne fait que des mises à jour : aucune création, aucune suppression.
- Un lot est rattaché au client dont le nom correspond (casse et espaces ignorées),
  puis au produit de ce client portant le même nom.
- Simulation par défaut : rien n'est écrit tant que --apply n'est pas donné.

Usage :
    python manage.py relier_lots_pesee
    python manage.py relier_lots_pesee --apply
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Client, TechnicalProduct
from core.models.stock_produit_fini import ProduitFiniLot


def _norm(valeur):
    return ' '.join(str(valeur or '').split())


class Command(BaseCommand):
    help = "Rattache les lots « à relier » aux clients et produits de l'ERP (simulation par défaut)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Écrire réellement. Sans cette option : simulation.')

    def handle(self, *args, **options):
        apply = options['apply']
        examines = 0
        lots_maj = 0
        clients_rattaches = 0
        produits_rattaches = 0
        clients_inconnus = set()

        with transaction.atomic():
            for lot in ProduitFiniLot.objects.filter(a_relier=True).select_related('client', 'produit'):
                examines += 1
                changes = []
                client = lot.client
                if client is None:
                    nom = _norm(lot.client_nom)
                    client = Client.objects.filter(name__iexact=nom).first() if nom else None
                    if client is not None:
                        lot.client = client
                        changes.append('client')
                        clients_rattaches += 1
                    else:
                        clients_inconnus.add(nom)
                nom_produit = _norm(lot.produit_nom)
                if lot.produit is None and client is not None and nom_produit:
                    produit = TechnicalProduct.objects.filter(
                        client=client, name__iexact=nom_produit).first()
                    if produit is not None:
                        lot.produit = produit
                        changes.append('produit')
                        produits_rattaches += 1
                # Même règle que le service de réception.
                a_relier = lot.client_id is None or (bool(nom_produit) and lot.produit_id is None)
                if lot.a_relier != a_relier:
                    lot.a_relier = a_relier
                    changes.append('a_relier')
                if changes:
                    lot.save(update_fields=changes)
                    lots_maj += 1

            restent = ProduitFiniLot.objects.filter(a_relier=True).count()
            if not apply:
                transaction.set_rollback(True)

        self.stdout.write('== ÉCRITURE ==' if apply else '== SIMULATION : rien n’a été écrit ==')
        self.stdout.write(f'lots examinés : {examines}')
        self.stdout.write(f'lots mis à jour : {lots_maj}')
        self.stdout.write(f'clients rattachés : {clients_rattaches} · produits rattachés : {produits_rattaches}')
        self.stdout.write(f'lots restant « à relier » : {restent}')
        if clients_inconnus:
            self.stdout.write('clients toujours absents de l’ERP : ' + ', '.join(sorted(clients_inconnus)))
        if not apply:
            self.stdout.write('Relance avec --apply pour écrire.')
