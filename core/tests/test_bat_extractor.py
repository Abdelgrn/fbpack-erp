"""Contrat de analyze_bat (moteur OCR local) : clés attendues, erreurs sans exception."""
import io
import unittest
from unittest import mock

from PIL import Image

from core.services import bat_extractor


def _png(w=300, h=200):
    buf = io.BytesIO()
    Image.new('RGB', (w, h), 'white').save(buf, format='PNG')
    return buf.getvalue()


class AnalyzeContractTests(unittest.TestCase):
    def test_fichier_vide(self):
        res = bat_extractor.analyze_bat(b'', 'x.png')
        self.assertEqual(res['error'], 'Fichier vide.')
        self.assertEqual(res['rows'], [])

    def test_fichier_trop_lourd(self):
        res = bat_extractor.analyze_bat(b'0' * (bat_extractor.MAX_BAT_BYTES + 1), 'x.pdf')
        self.assertIn('10 Mo', res['error'])

    def test_format_non_reconnu(self):
        res = bat_extractor.analyze_bat(b'pas une image', 'x.txt')
        self.assertTrue(res['error'])
        self.assertEqual(res['rows'], [])

    def test_image_sans_cartouche(self):
        res = bat_extractor.analyze_bat(_png(), 'vide.png')
        self.assertEqual(res['mode'], 'Image + OCR')
        self.assertTrue(res['error'])
        self.assertIn('Renseignez', res['error'])

    def test_resultat_mocke_mappe_les_lignes(self):
        fake = {'fields': {'laize_piste_mm': 385.0, 'laize_totale_mm': 1155.0, 'repeat_mm': 240.0,
                           'poses_across': 3, 'job_raw': 'Chips RIFKUS spaghetti bolonaise AMALGAME:',
                           'nombre_couleurs': 2},
                'supplier': 'Studio Flexo',
                'rows': [{'name': 'Cyan', 'name_raw': 'Cyan', 'cm2': 310.875, 'pct': 33.64, 'check': ''},
                         {'name': 'Encre n°2 (nom à saisir)', 'name_raw': '', 'cm2': None,
                          'pct': 5.78, 'check': 'nom illisible : à saisir'}]}
        with mock.patch.object(bat_extractor.bat_ocr, 'analyze_pages', return_value=fake):
            res = bat_extractor.analyze_bat(_png(), 'fiche.png')
        self.assertEqual(res['mode'], 'Image + OCR')
        self.assertEqual(res['job_hints']['name'], 'Chips RIFKUS spaghetti bolonaise')
        self.assertEqual(res['job_hints']['width_mm'], 1155.0)
        self.assertEqual(res['cliche_supplier'], 'Studio Flexo')
        self.assertEqual(res['rows'][0]['ink_type'], 'COLOR')
        self.assertEqual(res['rows'][0]['values_source'], 'OCR')
        self.assertEqual(res['rows'][1]['coverage_area_cm2'], None)
        self.assertTrue(any('2 couleur' in w or 'couleur(s)' in w for w in res['warnings']))
        self.assertTrue(any('illisibles' in w for w in res['warnings']))

    def test_erreur_interne_ne_remonte_pas(self):
        with mock.patch.object(bat_extractor.bat_ocr, 'analyze_pages', side_effect=RuntimeError('boom')):
            res = bat_extractor.analyze_bat(_png(), 'fiche.png')
        self.assertIn('Lecture OCR impossible', res['error'])

    def test_ink_type_blanc_et_vernis(self):
        self.assertEqual(bat_extractor.ink_type_for('Blanc'), 'WHITE')
        self.assertEqual(bat_extractor.ink_type_for('Vernis'), 'VARNISH')
        self.assertEqual(bat_extractor.ink_type_for('PANTONE 485 C'), 'COLOR')


if __name__ == '__main__':
    unittest.main()
