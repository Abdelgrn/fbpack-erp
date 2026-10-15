"""Tests du service d'extraction BAT (LOT BAT AUTOFILL V1.11 : Gemini seul).

Tests purs (unittest) : aucun appel réseau réel (Gemini est mocké). Les tests
d'historique (base Django) restent dans la classe InkHistoryViewTests.
Exécution : `python manage.py test core.tests.test_bat_extractor`.
"""
import io
import os
import unittest
from unittest import mock

from django.test import TestCase

from PIL import Image

from ..services import bat_vision
from ..services.bat_extractor import analyze_bat, validate_bat_size
from ..services.ink_calculator import density_default, validate_coverage

FAKE_KEY = 'TEST-KEY-123'


def _png_bytes(w=400, h=300):
    buf = io.BytesIO()
    Image.new('RGB', (w, h), (255, 255, 255)).save(buf, 'PNG')
    return buf.getvalue()


_REPONSE = {
    'nom_job': 'Chips mini RIFKUS ketchup', 'laize_totale_mm': 1035, 'laize_piste_mm': 345,
    'pas_coupe_mm': 190, 'poses_en_laize': 3, 'nombre_couleurs_annonce': 2,
    'fournisseur_cliches': 'Studio Flexo',
    'encres': [
        {'nom': 'Cyan', 'cm2': 315.3, 'pourcent': 48.11},
        {'nom': 'Blanc', 'cm2': 655.5, 'pourcent': 100.0},
    ],
}


class AnalyseGeminiSeulTests(unittest.TestCase):
    def test_sans_cle_erreur_claire_sans_appel(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(bat_vision, 'read_bat') as spy:
            r = analyze_bat(_png_bytes(), 'fiche.png')
        spy.assert_not_called()
        self.assertIn('GEMINI_API_KEY', r['error'])
        self.assertEqual(r['rows'], [])

    def test_image_lue_par_gemini(self):
        with mock.patch.dict(os.environ, {'GEMINI_API_KEY': FAKE_KEY}, clear=False), \
                mock.patch.object(bat_vision, 'read_bat', return_value=_REPONSE):
            r = analyze_bat(_png_bytes(), 'fiche.png')
        self.assertNotIn('error', r)
        self.assertEqual(r['mode'], 'Image + IA Gemini')
        self.assertEqual([x['name'] for x in r['rows']], ['Cyan', 'BLANC'])
        self.assertEqual(r['job_hints']['name'], 'Chips mini RIFKUS ketchup')
        self.assertEqual(r['cliche_supplier'], 'Studio Flexo')
        self.assertTrue(r['preview_data_uri'].startswith('data:image/jpeg'))

    def test_pdf_rendu_puis_lu_par_gemini(self):
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(60, 760, 'Chips mini RIFKUS ketchup')
        c.save()
        with mock.patch.dict(os.environ, {'GEMINI_API_KEY': FAKE_KEY}, clear=False), \
                mock.patch.object(bat_vision, 'read_bat', return_value=_REPONSE) as spy:
            r = analyze_bat(buf.getvalue(), 'fiche.pdf')
        self.assertTrue(spy.called)
        self.assertEqual(r['mode'], 'PDF + IA Gemini')
        self.assertEqual(len(r['rows']), 2)

    def test_echec_ia_signale_sans_donnees_inventees(self):
        err = bat_vision.VisionError('délai dépassé')
        with mock.patch.dict(os.environ, {'GEMINI_API_KEY': FAKE_KEY}, clear=False), \
                mock.patch.object(bat_vision, 'read_bat', side_effect=err):
            r = analyze_bat(_png_bytes(), 'fiche.png')
        self.assertIn('Analyse IA impossible', r['error'])
        self.assertEqual(r['rows'], [])
        self.assertNotIn(FAKE_KEY, r['error'])

    def test_aucune_couleur_renvoyee_message_explicite(self):
        with mock.patch.dict(os.environ, {'GEMINI_API_KEY': FAKE_KEY}, clear=False), \
                mock.patch.object(bat_vision, 'read_bat', return_value={'encres': []}):
            r = analyze_bat(_png_bytes(), 'fiche.png')
        self.assertIn('aucune couleur', r['error'])
        self.assertEqual(r['rows'], [])

    def test_fichier_corrompu_gracieux(self):
        with mock.patch.dict(os.environ, {'GEMINI_API_KEY': FAKE_KEY}, clear=False), \
                mock.patch.object(bat_vision, 'read_bat') as spy:
            r = analyze_bat(b'pas une image du tout', 'x.png')
        spy.assert_not_called()
        self.assertIn('error', r)

    def test_fichier_vide(self):
        r = analyze_bat(b'', 'vide.png')
        self.assertEqual(r['error'], 'Fichier vide.')

    def test_taille_max(self):
        self.assertFalse(validate_bat_size(0))
        self.assertTrue(validate_bat_size(1024))
        self.assertFalse(validate_bat_size(10 * 1024 * 1024 + 1))


class DensityDefaultTests(unittest.TestCase):
    """Densités FB PACK V1.3 : 1,3 encres/vernis, 1,5 blanc TiO2."""

    def test_densites(self):
        self.assertEqual(density_default('FLEXO', 'COLOR'), 1.3)
        self.assertEqual(density_default('HELIO', 'VARNISH'), 1.3)
        self.assertEqual(density_default('FLEXO', 'WHITE'), 1.5)

    def test_validate_coverage_pourcent(self):
        # 40.402 cm2 sur un repeat 140 x 137 mm = 21.06 %
        ok, calc = validate_coverage(40.402, 21.06, 140.0, 137.0)
        self.assertTrue(ok)
        self.assertAlmostEqual(calc, 21.06, places=2)
        ok, calc = validate_coverage(None, 21.06, 140.0, 137.0)
        self.assertTrue(ok)


class InkHistoryViewTests(TestCase):
    """V1.5 : l'historique liste bien les jobs enregistrés."""

    def test_liste_jobs(self):
        from django.contrib.auth import get_user_model
        from django.test import RequestFactory
        from ..models import AniloxRoll, InkCalculationColor, InkCalculationJob
        from ..views.ink_calculator import ink_calculation_list
        # V1.5.1 : certain projets seedent anilox/utilisateurs par migration ->
        # on réutilise l'existant plutôt que de violer la contrainte UNIQUE
        U = get_user_model()
        u = U.objects.filter(username='admin_test_bat').first() or \
            U.objects.create_superuser('admin_test_bat', 'a@a.a', 'pwd!')
        an = AniloxRoll.objects.filter(lineature=420, volume_cm3_m2=5.0).first() or \
            AniloxRoll.objects.create(lineature=420, volume_cm3_m2=5.0)
        job = InkCalculationJob.objects.create(name='JobTestHistorique', width_mm=137,
                                               length_m=1000, transfer_percent=90, created_by=u)
        InkCalculationColor.objects.create(job=job, name='Magenta', coverage_percent=21.06,
                                           anilox=an, density=1.3)
        req = RequestFactory().get('/ink/history/')
        req.user = u
        resp = ink_calculation_list(req)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'JobTestHistorique')
        self.assertContains(resp, 'Magenta')


if __name__ == '__main__':
    unittest.main()
