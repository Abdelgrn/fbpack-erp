"""Dates par produit (lot) dans le suivi par machine : début = 1re pesée, fin = clôture."""
from django.test import TestCase
from django.utils import timezone

from core.models import Client
from core.services.produit_fini import traiter_evenement
from core.services.suivi_postes import construire_arbre


def bobine(uid, heure, poste='Découpe petite'):
    return {'type': 'BOBINE', 'uid': uid, 'client_nom': 'CHOR KHALED',
            'article': 'Couscous Moyen 1 Kg', 'numero_lot': 'LOT-DT',
            'numero_palette': 'PAL-001', 'numero_bobine': uid, 'poids_kg': 20.0,
            'date_heure': heure, 'operateur': 'Ali', 'equipe': 'A', 'statut': 'ok',
            'poste': poste}


def lots_de(arbre):
    for machine in arbre:
        for client in machine['clients']:
            for lot in client['lots']:
                yield machine, client, lot


class SuiviDatesTests(TestCase):
    def setUp(self):
        Client.objects.create(name='CHOR KHALED')

    def test_debut_est_la_premiere_pesee_et_fin_la_cloture(self):
        traiter_evenement(bobine('b2', '2026-10-20 10:30:00'))
        traiter_evenement(bobine('b1', '2026-10-20 08:00:00'))
        traiter_evenement(bobine('b3', '2026-10-20 09:15:00'))
        traiter_evenement({'type': 'JOB_CLOTURE', 'uid': 'c-dt', 'client_nom': 'CHOR KHALED',
                           'article': 'Couscous Moyen 1 Kg', 'numero_lot': 'LOT-DT',
                           'temps_production_min': 150})
        lots = list(lots_de(construire_arbre()))
        self.assertEqual(len(lots), 1)
        _, _, lot = lots[0]
        self.assertEqual(timezone.localtime(lot['debut']).strftime('%H:%M'), '08:00')
        self.assertIsNotNone(lot['job_clos_le'])
        self.assertEqual(lot['temps_production_min'], 150)

    def test_lot_en_cours_sans_fin(self):
        traiter_evenement(bobine('b1', '2026-10-20 08:00:00'))
        _, _, lot = list(lots_de(construire_arbre()))[0]
        self.assertIsNotNone(lot['debut'])
        self.assertIsNone(lot['job_clos_le'])
