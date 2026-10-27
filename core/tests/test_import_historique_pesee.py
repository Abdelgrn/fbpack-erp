"""Tests de la commande import_historique_pesee (historique de la pesée -> ERP)."""
import sqlite3
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.models import Client
from core.models.stock_produit_fini import ProduitFiniBobine, ProduitFiniLot


def _creer_base_pesee(chemin):
    """Petite base de pesée de test, avec les mêmes colonnes que la vraie."""
    con = sqlite3.connect(chemin)
    con.executescript("""
        CREATE TABLE pesees (
            id INTEGER PRIMARY KEY, client TEXT, reference TEXT, numero_lot TEXT,
            numero_palette TEXT, numero_bobine INTEGER, poids REAL, date_heure TEXT,
            operateur_nom TEXT, equipe TEXT, statut TEXT);
        CREATE TABLE lots (
            id INTEGER PRIMARY KEY, client_id INTEGER, numero_lot TEXT, statut TEXT,
            date_creation TEXT, date_fermeture TEXT);
        INSERT INTO pesees VALUES
            (1, 'chor khaled', 'Couscous Moyen 1 Kg', 'LOT-A', 'PAL-001', 1, 20.5,
             '2026-09-06 12:39:36', 'Ali', 'A', 'ok'),
            (2, 'CHOR  KHALED', 'Couscous Moyen 1 Kg', 'LOT-A', 'PAL-001', 2, 21.0,
             '2026-09-06 12:45:00', 'Ali', 'A', 'ok'),
            (3, 'CLIENT INCONNU', 'Produit X', 'LOT-B', 'PAL-002', 1, 9.5,
             '2026-09-07 08:00:00', 'Sara', 'B', 'ok');
        INSERT INTO lots VALUES (1, NULL, 'LOT-A', 'terminé', '2026-09-06', '2026-09-08');
        INSERT INTO lots VALUES (2, NULL, 'LOT-B', 'actif', '2026-09-07', NULL);
    """)
    con.commit()
    con.close()


class ImportHistoriquePeseeTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = str(Path(self.tmp.name) / 'pesee_test.db')
        _creer_base_pesee(self.source)
        Client.objects.create(name='CHOR KHALED')

    def _lancer(self, *args):
        sortie = StringIO()
        call_command('import_historique_pesee', '--source', self.source,
                     '--poste', 'Découpe petite', *args, stdout=sortie)
        return sortie.getvalue()

    def test_simulation_n_ecrit_rien(self):
        sortie = self._lancer()
        self.assertIn('SIMULATION', sortie)
        self.assertEqual(ProduitFiniBobine.objects.count(), 0)
        self.assertEqual(ProduitFiniLot.objects.count(), 0)

    def test_import_cree_les_bobines_et_les_clotures(self):
        sortie = self._lancer('--apply')
        self.assertIn('ÉCRITURE', sortie)
        self.assertEqual(ProduitFiniBobine.objects.count(), 3)
        lot_a = ProduitFiniLot.objects.get(numero_lot='LOT-A')
        self.assertIsNotNone(lot_a.client)                 # « chor khaled » reconnu
        self.assertIsNotNone(lot_a.job_clos_le)            # lot terminé dans la pesée
        lot_b = ProduitFiniLot.objects.get(numero_lot='LOT-B')
        self.assertIsNone(lot_b.job_clos_le)               # lot actif : pas clôturé
        self.assertTrue(lot_b.a_relier)                    # client inconnu -> à relier

    def test_relance_ne_cree_aucun_doublon(self):
        self._lancer('--apply')
        sortie = self._lancer('--apply')
        self.assertEqual(ProduitFiniBobine.objects.count(), 3)
        self.assertIn('deja_recue: 3', sortie)

    def test_base_introuvable_refusee(self):
        with self.assertRaises(CommandError):
            call_command('import_historique_pesee', '--source', 'n_existe_pas.db',
                         '--poste', 'Découpe petite', stdout=StringIO())

    def test_poste_inconnu_refuse(self):
        with self.assertRaises(CommandError):
            call_command('import_historique_pesee', '--source', self.source,
                         '--poste', 'Autre', stdout=StringIO())
