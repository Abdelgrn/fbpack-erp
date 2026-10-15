"""V1.9 : lecture BAT par l'API Gemini (clé GEMINI_API_KEY), sans appel réseau réel."""
import io
import json
import os
import unittest
import urllib.error
from unittest import mock

from PIL import Image

from core.services import bat_extractor as be
from core.services import bat_vision

FAKE_KEY = 'TEST-KEY-123'


def _png_bytes(w=400, h=300):
    buf = io.BytesIO()
    Image.new('RGB', (w, h), (255, 255, 255)).save(buf, 'PNG')
    return buf.getvalue()


_REPONSE_IA = {
    'nom_job': 'la dorée couscous Moyen 1Kg',
    'laize_piste_mm': 325, 'laize_totale_mm': 975, 'pas_coupe_mm': 650,
    'poses_en_laize': 3, 'poses_en_coupe': 2, 'lpi': 137,
    'nombre_couleurs_annonce': 4,
    'fournisseur_cliches': 'POLY SLIM',
    'encres': [
        {'nom': 'Cyan', 'cm2': 33.915, 'pourcent': 3.22},
        {'nom': 'PANTONE 7731C', 'cm2': 232.714, 'pourcent': 33.67},
        {'nom': None, 'cm2': 24.852, 'pourcent': 2.32},          # illisible : jamais « Yellow »
        {'nom': 'blanc', 'cm2': 979.12, 'pourcent': 92.70},
    ],
}


class BatVisionConfigTests(unittest.TestCase):
    def test_sans_cle_pas_d_appel(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(bat_vision.api_configured())
            with self.assertRaises(bat_vision.VisionError):
                bat_vision.call_gemini({'contents': []})

    def test_parse_json_avec_balises(self):
        data = bat_vision.parse_json_text('```json\n{"encres": []}\n```')
        self.assertEqual(data, {'encres': []})
        with self.assertRaises(bat_vision.VisionError):
            bat_vision.parse_json_text('pas du json')


class BatVisionCallTests(unittest.TestCase):
    def test_cle_dans_entete_jamais_dans_url(self):
        reponse = {'candidates': [{'content': {'parts': [{'text': '{"encres": []}'}]}}]}
        cm = mock.MagicMock()
        cm.__enter__.return_value.read.return_value = json.dumps(reponse).encode()
        with mock.patch.dict(os.environ, {'GEMINI_API_KEY': FAKE_KEY}, clear=False), \
                mock.patch('urllib.request.urlopen', return_value=cm) as opener:
            bat_vision.call_gemini({'contents': []})
        req = opener.call_args[0][0]
        self.assertNotIn(FAKE_KEY, req.full_url)
        self.assertEqual(req.get_header('X-goog-api-key'), FAKE_KEY)
        self.assertIn('gemini-3.8-flash', req.full_url)

    def test_erreur_http_sans_cle_dans_le_message(self):
        err = urllib.error.HTTPError('https://x', 404, 'Not Found', {}, None)
        with mock.patch.dict(os.environ, {'GEMINI_API_KEY': FAKE_KEY}, clear=False), \
                mock.patch('urllib.request.urlopen', side_effect=err):
            with self.assertRaises(bat_vision.VisionError) as ctx:
                bat_vision.call_gemini({'contents': []})
        self.assertIn('404', str(ctx.exception))
        self.assertNotIn(FAKE_KEY, str(ctx.exception))


class BatVisionMappingTests(unittest.TestCase):
    def test_lignes_sans_nom_positionnel(self):
        rows = be._rows_from_api(_REPONSE_IA)
        names = [r['name'] for r in rows]
        self.assertEqual(names[0], 'Cyan')
        self.assertEqual(names[1], 'PANTONE 7731 C')
        self.assertTrue(names[2].startswith('Encre n°3'))
        self.assertNotIn('Yellow', names)
        self.assertEqual(names[3], 'BLANC')
        self.assertIn('nom illisible', rows[2]['check'])
        self.assertEqual(rows[1]['coverage_percent'], 33.67)
        self.assertEqual(rows[0]['values_source'], 'API')

    def test_indices_job_et_laize(self):
        h = be._hints_from_api(_REPONSE_IA)
        self.assertEqual(h['name'], 'la dorée couscous Moyen 1Kg')
        self.assertEqual(h['width_mm'], 975)
        self.assertEqual(h['repeat_mm'], 650)
        self.assertEqual(h['poses_across'], 3)

    def test_laize_totale_egale_piste_rejetee(self):
        h = be._hints_from_api({'laize_piste_mm': 325, 'laize_totale_mm': 325})
        self.assertNotIn('width_mm', h)
        self.assertTrue(h.get('laize_douteuse'))


class FournisseurTests(unittest.TestCase):
    def test_libelles_fixes(self):
        self.assertEqual(be._supplier_label('POLY SLIM'), 'Poly Slim')
        self.assertEqual(be._supplier_label('YAHIAOUI PHOTOGRAVURE'), 'Yahiaoui Photogravure')
        self.assertEqual(be._supplier_label('STUDIO FLEXO'), 'Studio Flexo')
        self.assertIsNone(be._supplier_label('inconnu'))

    def test_fournisseur_lu_par_ia(self):
        with mock.patch.dict(os.environ, {'GEMINI_API_KEY': FAKE_KEY}, clear=False), \
                mock.patch.object(bat_vision, 'read_bat', return_value=_REPONSE_IA):
            r = be.analyze_bat(_png_bytes(), 'fiche.png')
        self.assertEqual(r['cliche_supplier'], 'Poly Slim')


class BatVisionAnalyseTests(unittest.TestCase):
    def test_image_lue_par_ia(self):
        with mock.patch.dict(os.environ, {'GEMINI_API_KEY': FAKE_KEY}, clear=False), \
                mock.patch.object(bat_vision, 'read_bat', return_value=_REPONSE_IA):
            r = be.analyze_bat(_png_bytes(), 'fiche.png')
        self.assertIn('IA Gemini', r['mode'])
        self.assertEqual(len(r['rows']), 4)
        self.assertEqual(r['job_hints']['name'], 'la dorée couscous Moyen 1Kg')
        self.assertTrue(any('Lecture IA Gemini' in w for w in r['warnings']))

    def test_erreur_ia_repli_avec_avertissement(self):
        err = bat_vision.VisionError('réseau indisponible ou délai dépassé')
        with mock.patch.dict(os.environ, {'GEMINI_API_KEY': FAKE_KEY}, clear=False), \
                mock.patch.object(bat_vision, 'read_bat', side_effect=err):
            r = be.analyze_bat(_png_bytes(), 'fiche.png')
        self.assertNotIn('IA Gemini', r['mode'])
        self.assertTrue(any('IA Gemini indisponible' in w for w in r['warnings']))
        self.assertNotIn(FAKE_KEY, json.dumps(r['warnings']))

    def test_sans_cle_aucun_appel(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(bat_vision, 'read_bat') as spy:
            r = be.analyze_bat(_png_bytes(), 'fiche.png')
        spy.assert_not_called()
        self.assertEqual(r['mode'], 'Image')


def _pdf_texte_bytes():
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 760
    for line in ['Chips mini RIFKUS ketchup', 'LAIZE TOTALE: 1035 mm', 'PAS DE COUPE: 190 mm',
                 'Cyan 48,11 %', 'Magenta 7,79 %', 'Blanc 100 %']:
        c.drawString(60, y, line)
        y -= 18
    c.save()
    return buf.getvalue()


class BatVisionPdfTexteTests(unittest.TestCase):
    def test_pdf_texte_lu_par_ia_d_abord(self):
        with mock.patch.dict(os.environ, {'GEMINI_API_KEY': FAKE_KEY}, clear=False), \
                mock.patch.object(bat_vision, 'read_bat', return_value=_REPONSE_IA) as spy:
            r = be.analyze_bat(_pdf_texte_bytes(), 'fiche.pdf')
        self.assertTrue(spy.called)
        self.assertIn('IA Gemini', r['mode'])
        self.assertEqual(len(r['rows']), 4)

    def test_pdf_texte_ia_en_echec_repli_texte(self):
        err = bat_vision.VisionError('délai dépassé')
        with mock.patch.dict(os.environ, {'GEMINI_API_KEY': FAKE_KEY}, clear=False), \
                mock.patch.object(bat_vision, 'read_bat', side_effect=err):
            r = be.analyze_bat(_pdf_texte_bytes(), 'fiche.pdf')
        self.assertNotIn('IA Gemini', r['mode'])
        self.assertIn('PDF texte', r['mode'])
        self.assertTrue(any('IA Gemini indisponible' in w for w in r['warnings']))
        self.assertNotIn('error', r)

    def test_pdf_texte_sans_cle_aucun_appel(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(bat_vision, 'read_bat') as spy:
            r = be.analyze_bat(_pdf_texte_bytes(), 'fiche.pdf')
        spy.assert_not_called()
        self.assertEqual(r['mode'], 'PDF texte')


if __name__ == '__main__':
    unittest.main()
