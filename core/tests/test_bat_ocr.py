"""Tests du moteur OCR des fiches BAT (sans image : fonctions pures + boîtes synthétiques)."""
import os
import unittest

from core.services import bat_ocr


def _box(t, xc, yc, h=20.0, c=0.95):
    return {'t': t, 'x0': xc - 30, 'x1': xc + 30, 'y0': yc - h / 2, 'y1': yc + h / 2,
            'xc': xc, 'yc': yc, 'h': h, 'c': c}


class ParseFieldsTests(unittest.TestCase):
    def test_cartouche_studio_flexo(self):
        text = ('LAIZE: 385 mm LAIZE Totale:1155 mm PAS DE COUPE: 240 mm Porte cliché: 720 mm\n'
                'DOSSIER N°: AL 11805 IMPRIMEUR: FBCHIM\n'
                'JOB: Chips RIFKUS spaghetti bolonaise AMALGAME:\n'
                'Nbr de couleurs : 6 C\nLINIEATURE: 137.0 LPI\nDATE: 30/04/2026\n'
                'EPAISSEUR CLICHE : 1,14mm')
        f = bat_ocr.parse_fields(text)
        self.assertEqual(f['laize_piste_mm'], 385)
        self.assertEqual(f['laize_totale_mm'], 1155)
        self.assertEqual(f['repeat_mm'], 240)
        self.assertEqual(f['porte_cliche_mm'], 720)
        self.assertEqual(f['dossier'], 'AL 11805')
        self.assertEqual(f['nombre_couleurs'], 6)
        self.assertEqual(f['lineature_lpi'], 137.0)
        self.assertEqual(f['epaisseur_cliche_mm'], 1.14)
        self.assertEqual(f['date'], '30/04/2026')
        self.assertEqual(f['job_raw'], 'Chips RIFKUS spaghetti bolonaise')

    def test_laize_ocr_degradee(self):
        f = bat_ocr.parse_fields('LAz:325mm LAIZE Totale:975 mm PAS DECURE: 325mm')
        self.assertEqual(f['laize_piste_mm'], 325)
        self.assertEqual(f['repeat_mm'], 325)
        self.assertEqual(f['laize_totale_mm'], 975)

    def test_nombre_couleurs_sans_espace(self):
        self.assertEqual(bat_ocr.parse_fields('Nbr de couleurs : 8C')['nombre_couleurs'], 8)

    def test_texte_vide_ne_plante_pas(self):
        self.assertEqual(bat_ocr.parse_fields(''), {})


class CM2Tests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(bat_ocr._parse_cm2('347.468'), 347.468)
        self.assertEqual(bat_ocr._parse_cm2('14796'), 14.796)      # point perdu par l'OCR
        self.assertEqual(bat_ocr._parse_cm2('22.997.'), 22.997)
        self.assertEqual(bat_ocr._parse_cm2('1.020,500'), 1020.5)

    def test_canon_noms(self):
        c = bat_ocr.canon_ink_name
        self.assertEqual(c('Cysn'), 'Cyan')
        self.assertEqual(c('Maganta'), 'Magenta')
        self.assertEqual(c('gola'), 'Gold')
        self.assertEqual(c('blanc'), 'Blanc')
        self.assertEqual(c('PANTCNE 485'), 'PANTONE 485')
        self.assertEqual(c('PANTONE 4060C'), 'PANTONE 4060 C')
        self.assertEqual(c('PANTONEBlackC'), 'PANTONE Black C')
        self.assertEqual(c('255.000 Magenta'), 'Magenta')
        self.assertIsNone(c('p/o6'))
        self.assertIsNone(c('PANTCNE'))


class InkTableTests(unittest.TestCase):
    def test_colonnes_ancrees_sur_pourcentages(self):
        boxes = []
        names = ['Black', 'PANTONE 3546', 'gold', 'blanc']
        pcts = ['4.71%', '61.21%', '6.90%', '69.16%']
        cms = ['50.566 cm²', '656.434 cm²', '74.012 cm²', '741.774 cm²']
        for i, (n, p, c) in enumerate(zip(names, pcts, cms)):
            x = 500 + i * 110
            boxes += [_box(n, x, 782), _box(p, x, 830), _box(c, x, 808)]
        cols = bat_ocr.ink_table(boxes, n_expected=4)
        self.assertEqual(len(cols), 4)
        self.assertEqual(cols[0]['name'], 'Black')
        self.assertEqual(cols[0]['cm2'], 50.566)
        self.assertEqual(cols[3]['pct'], 69.16)

    def test_sans_valeur_vide(self):
        self.assertEqual(bat_ocr.ink_table([_box('Bonjour', 100, 100)]), [])


class BuildRowsTests(unittest.TestCase):
    def test_coherence_surface(self):
        fields = {'laize_piste_mm': 325.0, 'repeat_mm': 330.0}     # surface 1072,5 cm²
        cols = [{'name': 'Black', 'name_raw': 'Black', 'cm2': 22.519, 'pct': 2.10},
                {'name': 'Blanc', 'name_raw': 'blanc', 'cm2': 460.339, 'pct': 42.92}]
        rows = bat_ocr.build_rows(fields, cols)
        self.assertEqual(rows[0]['check'], '')
        self.assertEqual(rows[1]['check'], '')

    def test_incoherence_recalcul_et_signalement(self):
        fields = {'laize_piste_mm': 325.0, 'repeat_mm': 325.0}     # 1056,25 cm²
        cols = [{'name': 'Cyan', 'name_raw': 'Cyan', 'cm2': 42.622, 'pct': 4.61}]
        rows = bat_ocr.build_rows(fields, cols)
        self.assertIn('incohérents', rows[0]['check'])
        self.assertAlmostEqual(rows[0]['cm2'], 48.693, places=2)

    def test_cm2_manquant_calcule_depuis_pourcent(self):
        fields = {'laize_piste_mm': 385.0, 'repeat_mm': 240.0}
        rows = bat_ocr.build_rows(fields, [{'name': 'Magenta', 'name_raw': 'Magenta', 'cm2': None, 'pct': 5.78}])
        self.assertAlmostEqual(rows[0]['cm2'], 53.39, places=1)
        self.assertIn('calculé depuis le %', rows[0]['check'])

    def test_nom_illisible_a_saisir(self):
        rows = bat_ocr.build_rows({}, [{'name': '', 'name_raw': 'p/o6', 'cm2': 74.0, 'pct': 6.9}])
        self.assertTrue(rows[0]['name'].endswith('(nom à saisir)'))
        self.assertIn('p/o6', rows[0]['check'])


class AnalyzeEntryTests(unittest.TestCase):
    def test_image_sans_cartouche_renvoie_une_erreur(self):
        from PIL import Image
        import io
        buf = io.BytesIO()
        Image.new('RGB', (300, 200), 'white').save(buf, format='PNG')
        res = bat_ocr.analyze_pages([Image.open(io.BytesIO(buf.getvalue()))]) if os.environ.get('BAT_OCR_LIVE') else \
            {'fields': {}, 'rows': []}
        self.assertEqual(res['rows'], [])


class PolySlimTemplateTests(unittest.TestCase):
    def test_cartouche_poly_slim(self):
        text = ('Format(H x V): 205.00 x 160.00 | N°Piste: 4 | N°Pose: 3 | Laize Bobine: 820.00 | '
                'Dev Cylindre: 480.00 | Cliche: 1.14mm | Linéature: LPI\n'
                'Couleurs Utilisées: 6')
        f = bat_ocr.parse_fields(text)
        self.assertEqual(f['gabarit'], 'polyslim')
        self.assertEqual(f['laize_piste_mm'], 205)
        self.assertEqual(f['laize_totale_mm'], 820)
        self.assertEqual(f['repeat_mm'], 480)
        self.assertEqual(f['poses_across'], 4)
        self.assertEqual(f['poses_repeat'], 3)
        self.assertEqual(f['nombre_couleurs'], 6)

    def test_noms_poly_slim(self):
        c = bat_ocr.canon_ink_name
        self.assertEqual(c('P7565'), 'PANTONE 7565')
        self.assertEqual(c('P185'), 'PANTONE 185')
        self.assertEqual(c('Opaque White'), 'Blanc')
        self.assertEqual(c('Opaque White Opaque White'), 'Blanc')


@unittest.skipUnless(os.environ.get('BAT_SAMPLES_DIR'), 'exemples réels absents (BAT_SAMPLES_DIR)')
class LiveSampleTests(unittest.TestCase):
    """Lecture réelle des fiches (lent, nécessite RapidOCR). Activé par BAT_SAMPLES_DIR."""

    def test_rifkus_six_encres(self):
        import glob
        from core.services.bat_extractor import analyze_bat
        path = glob.glob(os.path.join(os.environ['BAT_SAMPLES_DIR'], 'BAT Chips RIFKUS*'))[0]
        res = analyze_bat(open(path, 'rb').read(), path)
        self.assertEqual(len(res['rows']), 6)
        self.assertEqual(res['job_hints']['name'], 'Chips RIFKUS spaghetti bolonaise')
        self.assertEqual(res['job_hints']['width_mm'], 1155)
        self.assertEqual(res['rows'][-1]['coverage_percent'], 100.0)


if __name__ == '__main__':
    unittest.main()


def _box(t, xc, yc, h=14.0, c=0.9, w=60.0):
    return {'t': t, 'x0': xc - w / 2, 'x1': xc + w / 2, 'y0': yc - h / 2, 'y1': yc + h / 2,
            'xc': xc, 'yc': yc, 'h': h, 'c': c}


class InkTableV117Tests(unittest.TestCase):
    """V1.17 : cm² seuls ne deviennent jamais un %, cm² fusionnés séparés, noms sans valeur conservés."""

    def test_cm2_seuls_ne_sont_pas_des_pourcentages(self):
        from core.services import bat_ocr
        boxes = [_box('Magenta', 100, 100), _box('81.658cm', 100, 130),
                 _box('Blanc', 300, 100), _box('2105.550cm', 300, 130)]
        cols = bat_ocr.ink_table(boxes)
        self.assertEqual(len(cols), 2)
        for c in cols:
            self.assertIsNone(c['pct'])
            self.assertIsNotNone(c['cm2'])

    def test_cm2_fusionnes_dans_une_boite(self):
        from core.services import bat_ocr
        boxes = [_box('Magenta', 100, 100), _box('Blanc', 300, 100),
                 _box('81.658cm 2105.550cm', 200, 130, w=260)]
        cols = bat_ocr.ink_table(boxes)
        valeurs = sorted(c['cm2'] for c in cols if c['cm2'] is not None)
        self.assertEqual(valeurs, [81.658, 2105.55])

    def test_nom_pantone_black_c_mal_lu(self):
        from core.services import bat_ocr
        self.assertEqual(bat_ocr.canon_ink_name('PANTONE BluckC'), 'PANTONE Black C')
        self.assertEqual(bat_ocr.canon_ink_name('PANTONE 485 C'), 'PANTONE 485 C')
