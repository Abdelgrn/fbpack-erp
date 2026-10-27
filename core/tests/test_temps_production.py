"""Tests du temps de production par job (envoyé par la pesée à la clôture)."""
from django.test import TestCase

from core.models import Client
from core.models.stock_produit_fini import ProduitFiniLot
from core.services.produit_fini import traiter_evenement


def cloture(uid, lot='LOT-TP', client='CHOR KHALED', article='Couscous Moyen 1 Kg', **extra):
    evt = {'type': 'JOB_CLOTURE', 'uid': uid, 'client_nom': client,
           'article': article, 'numero_lot': lot}
    evt.update(extra)
    return traiter_evenement(evt)


class TempsProductionTests(TestCase):
    def setUp(self):
        Client.objects.create(name='CHOR KHALED')

    def test_temps_enregistre_a_la_cloture(self):
        res = cloture('t1', temps_production_min=155)
        self.assertEqual(res['statut'], 'cloture')
        lot = ProduitFiniLot.objects.get(numero_lot='LOT-TP')
        self.assertIsNotNone(lot.job_clos_le)
        self.assertEqual(lot.temps_production_min, 155)

    def test_sans_temps_le_champ_reste_vide(self):
        self.assertEqual(cloture('t2')['statut'], 'cloture')
        lot = ProduitFiniLot.objects.get(numero_lot='LOT-TP')
        self.assertIsNotNone(lot.job_clos_le)
        self.assertIsNone(lot.temps_production_min)

    def test_temps_null_ou_vide_ignore(self):
        cloture('t3', lot='LOT-N', temps_production_min=None)
        cloture('t4', lot='LOT-V', temps_production_min='')
        self.assertIsNone(ProduitFiniLot.objects.get(numero_lot='LOT-N').temps_production_min)
        self.assertIsNone(ProduitFiniLot.objects.get(numero_lot='LOT-V').temps_production_min)

    def test_temps_illisible_ne_bloque_pas_la_cloture(self):
        res = cloture('t5', lot='LOT-X', temps_production_min='beaucoup')
        self.assertEqual(res['statut'], 'cloture')
        lot = ProduitFiniLot.objects.get(numero_lot='LOT-X')
        self.assertIsNotNone(lot.job_clos_le)
        self.assertIsNone(lot.temps_production_min)

    def test_temps_negatif_ramene_a_zero(self):
        cloture('t6', lot='LOT-NEG', temps_production_min=-5)
        self.assertEqual(ProduitFiniLot.objects.get(numero_lot='LOT-NEG').temps_production_min, 0)

    def test_recloture_ne_modifie_pas_le_temps(self):
        cloture('t7', lot='LOT-R', temps_production_min=100)
        cloture('t8', lot='LOT-R', temps_production_min=999)
        self.assertEqual(ProduitFiniLot.objects.get(numero_lot='LOT-R').temps_production_min, 100)
