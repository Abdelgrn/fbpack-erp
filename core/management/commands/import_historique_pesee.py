"""Importe l'historique de la base de pesée (SQLite) dans l'ERP.

- La base de pesée est ouverte en lecture seule (mode=ro) : elle n'est jamais modifiée.
- Chaque ligne est rejouée par core.services.produit_fini.traiter_evenement, la même
  fonction que l'API de synchronisation : mêmes règles de rattachement client/produit,
  même passage en « à relier » si le nom n'est pas reconnu.
- Idempotent : chaque bobine reçoit un uid stable (HIST-<POSTE>-<id>). Relancer la
  commande ne crée donc aucun doublon.
- Simulation par défaut : rien n'est écrit tant que --apply n'est pas donné.
- V2 : pour un même numéro de lot, client et article sont ramenés à une seule graphie
  (casse et espaces ignorées). Sans cela, « chor khaled » et « CHOR KHALED » créaient
  deux lots distincts pour un même job.

Usage :
    python manage.py import_historique_pesee --source "<chemin>\\fbpack_pesee.db" --poste "Découpe petite"
    python manage.py import_historique_pesee --source "<chemin>\\fbpack_pesee.db" --poste "Découpe petite" --apply
"""
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core.models import Client
from core.models.stock_produit_fini import ProduitFiniLot
from core.services.produit_fini import TYPE_BOBINE, TYPE_CLOTURE, traiter_evenement

POSTES = {
    'Extrudeuse': 'EXTRUDEUSE',
    'Découpe grande': 'DECOUPE_GRANDE',
    'Découpe petite': 'DECOUPE_PETITE',
}

# Statuts de lot de la pesée considérés comme « job terminé » (lots déjà clôturés).
STATUTS_CLOTURE = ('terminé', 'fermé')


def _norm(valeur):
    """Espaces multiples et bords supprimés (même règle que le service ERP)."""
    return ' '.join(str(valeur or '').split())


def _variante_courante(compte):
    """Graphie la plus fréquente ; à égalité, celle qui contient le plus de majuscules."""
    return min(compte, key=lambda v: (-compte[v], -sum(1 for c in str(v) if c.isupper()), str(v)))


def _canoniques(lignes):
    """Une seule graphie par numéro de lot et par (client, article), casse et espaces ignorées.

    Retourne (lot_canon, paire_canon, paire_dominante) :
    - lot_canon[cle_lot] : graphie retenue du numéro de lot ;
    - paire_canon[(cle_lot, cle_client, cle_article)] : (client, article) retenus ;
    - paire_dominante[cle_lot] : (client, article) le plus fréquent du lot (pour la clôture).
    """
    comptes_lot = {}
    comptes_paire = {}
    for lot, client, ref, n in lignes:
        lot_n, client_n, ref_n = _norm(lot), _norm(client), _norm(ref)
        cle_lot = lot_n.casefold()
        comptes_lot.setdefault(cle_lot, {})
        comptes_lot[cle_lot][lot_n] = comptes_lot[cle_lot].get(lot_n, 0) + n
        cle = (cle_lot, client_n.casefold(), ref_n.casefold())
        comptes_paire.setdefault(cle, {})
        comptes_paire[cle][(client_n, ref_n)] = comptes_paire[cle].get((client_n, ref_n), 0) + n

    lot_canon = {k: _variante_courante(v) for k, v in comptes_lot.items()}
    paire_canon = {cle: _variante_courante(v) for cle, v in comptes_paire.items()}

    par_lot = {}
    for cle, v in comptes_paire.items():
        total = sum(v.values())
        dest = par_lot.setdefault(cle[0], {})
        p = paire_canon[cle]
        dest[p] = dest.get(p, 0) + total
    paire_dominante = {k: _variante_courante(v) for k, v in par_lot.items()}
    return lot_canon, paire_canon, paire_dominante


def construire_evenements(con, poste_nom):
    """Transforme la base de pesée en événements de l'API. Ne fait aucune écriture."""
    slug = POSTES[poste_nom]
    evenements = []

    lignes = con.execute(
        'SELECT id, client, reference, numero_lot, numero_palette, numero_bobine, '
        'poids, date_heure, operateur_nom, equipe, statut '
        'FROM pesees ORDER BY id'
    ).fetchall()
    groupes = con.execute(
        'SELECT numero_lot, client, reference, COUNT(*) FROM pesees '
        'GROUP BY numero_lot, client, reference'
    ).fetchall()
    lot_canon, paire_canon, paire_dominante = _canoniques(groupes)

    for (pid, client, reference, lot, palette, bobine, poids,
         date_heure, operateur, equipe, statut) in lignes:
        lot_n = _norm(lot)
        cle_lot = lot_n.casefold()
        client_n, ref_n = paire_canon[(cle_lot, _norm(client).casefold(),
                                       _norm(reference).casefold())]
        evenements.append({
            'type': TYPE_BOBINE,
            'uid': f'HIST-{slug}-{pid}',
            'client_nom': client_n,
            'article': ref_n,
            'numero_lot': lot_canon[cle_lot],
            'numero_palette': palette or '',
            'numero_bobine': str(bobine or ''),
            'poids_kg': poids,
            'unite_origine': 'KG',
            'date_heure': date_heure or '',
            'operateur': operateur or '',
            'equipe': equipe or '',
            'statut': statut or 'ok',
            'poste': poste_nom,
        })

    lots = con.execute(
        'SELECT id, numero_lot FROM lots WHERE statut IN (?, ?) ORDER BY id',
        STATUTS_CLOTURE,
    ).fetchall()
    for lot_id, numero_lot in lots:
        cle_lot = _norm(numero_lot).casefold()
        # Client et article du lot : ceux qui apparaissent le plus souvent dans ses pesées.
        client, reference = paire_dominante.get(cle_lot, ('', ''))
        evenements.append({
            'type': TYPE_CLOTURE,
            'uid': f'HIST-{slug}-CLOT-{lot_id}',
            'client_nom': client,
            'article': reference,
            'numero_lot': lot_canon.get(cle_lot, _norm(numero_lot)),
            'poste': poste_nom,
        })
    return evenements


class Command(BaseCommand):
    help = "Importe l'historique de la base de pesée dans l'ERP (simulation par défaut)."

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True,
                            help='Chemin de la base SQLite de la pesée (lue en lecture seule).')
        parser.add_argument('--poste', required=True, choices=list(POSTES),
                            help='Poste d’origine de cette base.')
        parser.add_argument('--apply', action='store_true',
                            help='Écrire réellement. Sans cette option : simulation.')

    def handle(self, *args, **options):
        source = Path(options['source'])
        if not source.is_file():
            raise CommandError('Base de pesée introuvable : vérifiez le chemin.')

        uri = f"file:{source.resolve().as_posix()}?mode=ro"
        try:
            con = sqlite3.connect(uri, uri=True)
        except sqlite3.Error as exc:
            raise CommandError(f'Impossible d’ouvrir la base de pesée en lecture seule : {exc}')
        try:
            evenements = construire_evenements(con, options['poste'])
        except sqlite3.Error as exc:
            raise CommandError(f'Lecture de la base de pesée impossible : {exc}')
        finally:
            con.close()

        apply = options['apply']
        db = settings.DATABASES['default']
        self.stdout.write(f"Base cible : {connection.vendor} · {db.get('NAME', '')}")
        self.stdout.write(f"Poste : {options['poste']} · événements à traiter : {len(evenements)}")

        # Clients de la pesée absents de l'ERP (ils iront dans « à relier »).
        noms = {' '.join(e['client_nom'].split())
                for e in evenements if e['type'] == TYPE_BOBINE and e['client_nom']}
        inconnus = sorted(n for n in noms if not Client.objects.filter(name__iexact=n).exists())

        compteurs = {}
        erreurs = []
        with transaction.atomic():
            for evt in evenements:
                res = traiter_evenement(evt)
                compteurs[res['statut']] = compteurs.get(res['statut'], 0) + 1
                if res['statut'] == 'erreur' and len(erreurs) < 10:
                    erreurs.append(f"{res['uid']} : {res['detail']}")
            a_relier = ProduitFiniLot.objects.filter(a_relier=True).count()
            if not apply:
                transaction.set_rollback(True)

        self.stdout.write('== ÉCRITURE ==' if apply else '== SIMULATION : rien n’a été écrit ==')
        for statut in sorted(compteurs):
            self.stdout.write(f'{statut}: {compteurs[statut]}')
        self.stdout.write(f'lots « à relier » après import: {a_relier}')
        self.stdout.write(f'clients de la pesée absents de l’ERP ({len(inconnus)}): '
                          + (', '.join(inconnus) if inconnus else 'aucun'))
        for ligne in erreurs:
            self.stdout.write(f'erreur: {ligne}')
        if not apply:
            self.stdout.write('Relance avec --apply pour écrire.')
