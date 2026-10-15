"""Tests du service d'extraction BAT (LOT BAT AUTOFILL V1).

Tests purs (unittest) : aucune base de données requise, exécutables via
`python manage.py test core.tests.test_bat_extractor`.
"""
import io
import unittest

from django.test import TestCase

from PIL import Image

from ..services.bat_extractor import (analyze_bat, apply_ocr_names,
                                      job_hints_from_text, legend_rows_from_ocr,
                                      ocr_job_hints, pair_ocr_values,
                                      rows_from_text, validate_bat_size)
from ..services.ink_calculator import density_default, validate_coverage


def _synthetic_bat_image():
    """Fiche BAT synthétique : maquette rouge en haut, 4 pastilles en bas."""
    im = Image.new('RGB', (1200, 800), (242, 242, 242))
    px = im.load()
    for x in range(150, 1050):            # maquette (tiers haut)
        for y in range(40, 300):
            px[x, y] = (226, 0, 26)
    swatches = [(236, 0, 140), (255, 242, 0), (40, 40, 40), (0, 174, 239)]
    x0 = 180
    for rgb in swatches:
        for x in range(x0, x0 + 80):
            for y in range(560, 640):
                px[x, y] = rgb
        x0 += 150
    buf = io.BytesIO()
    im.save(buf, format='PNG')
    return buf.getvalue()


class BatExtractorTests(unittest.TestCase):
    def test_image_detecte_quatre_pastilles_nommees(self):
        res = analyze_bat(_synthetic_bat_image(), 'bat.png')
        self.assertNotIn('error', res)
        self.assertEqual(res['mode'], 'Image')
        names = [r['name'] for r in res['rows']]
        self.assertEqual(names, ['MAGENTA', 'JAUNE', 'NOIR', 'CYAN'])
        self.assertTrue(res['preview_data_uri'].startswith('data:image/jpeg;base64,'))
        for row in res['rows']:
            self.assertIsNone(row['coverage_percent'])
            self.assertIsNone(row['coverage_area_cm2'])

    def test_pdf_texte_lignes_et_hints(self):
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        y = 760
        for line in ['LAIZE: 137 mm', 'PAS DE COUPE: 140 mm',
                     'NBR POSES EN LAIZE: 4', 'NBR POSES EN COUPE: 7',
                     'Magenta', 'Yellow',
                     '40.402 cm2', '43.062 cm2',
                     '21.06%', '22.45%']:
            c.drawString(60, y, line)
            y -= 18
        c.save()
        res = analyze_bat(buf.getvalue(), 'bat.pdf')
        self.assertNotIn('error', res)
        self.assertEqual(res['mode'], 'PDF texte')
        self.assertEqual(len(res['rows']), 2)
        self.assertEqual(res['rows'][0]['name'], 'Magenta')
        self.assertEqual(res['rows'][0]['coverage_percent'], 21.06)
        self.assertEqual(res['rows'][0]['coverage_area_cm2'], 40.402)
        # V1.7 : pas de laize totale dans ce texte -> piste × poses (137 × 4)
        self.assertEqual(res['job_hints']['width_mm'], 548.0)
        self.assertEqual(res['job_hints']['repeat_mm'], 140.0)
        self.assertEqual(res['job_hints']['poses_across'], 4)
        self.assertEqual(res['job_hints']['poses_repeat'], 7)

    def test_texte_non_appaire(self):
        rows, warnings = rows_from_text('Magenta Yellow 12.5 cm2')
        self.assertEqual(len(rows), 2)
        self.assertIsNone(rows[0]['coverage_percent'])
        self.assertTrue(warnings)

    def test_hints_texte(self):
        hints = job_hints_from_text('LAIZE: 137 mm PAS DE COUPE: 140 mm LINIATURE: 137.0 LPI')
        self.assertIsNone(hints.get('width_mm'))              # V1.8 : une piste seule n'est pas la laize totale
        self.assertEqual(hints.get('laize_piste_mm'), 137.0)
        self.assertEqual(hints.get('repeat_mm'), 140.0)
        self.assertEqual(hints.get('lineature_lpi'), 137.0)

    def test_fichier_corrompu_gracieux(self):
        res = analyze_bat(b'%PDF-1.4 pas un vrai pdf', 'x.pdf')
        self.assertTrue(res.get('error') or res.get('rows') is not None)

    def test_fichier_vide(self):
        res = analyze_bat(b'', 'x.png')
        self.assertIn('error', res)

    def test_taille_max(self):
        self.assertFalse(validate_bat_size(11 * 1024 * 1024))
        self.assertTrue(validate_bat_size(1024))


class OcrPairingTests(unittest.TestCase):
    """Appairage OCR déterministe (fausses zones, aucune dépendance RapidOCR)."""

    def _rows(self):
        r1 = {'name': 'MAGENTA', 'ink_type': 'COLOR', 'coverage_percent': None,
              'coverage_area_cm2': None, 'swatch_hex': '#EC008C',
              'patch': {'ox0': 196, 'ox1': 251, 'oy0': 665, 'oy1': 709}}
        r2 = {'name': 'Couleur BAT #AAF6E3', 'ink_type': 'COLOR',
              'coverage_percent': None, 'coverage_area_cm2': None,
              'swatch_hex': '#AAF6E3',
              'patch': {'ox0': 654, 'ox1': 720, 'oy0': 654, 'oy1': 720}}
        return [r1, r2]

    def test_pair_ocr_values_colonne(self):
        items = [
            (185, 249, 744, 761, '40.402 cm'),      # cm² sous pastille 1
            (185, 230, 757, 774, '21.06%'),         # % sous pastille 1
            (264, 326, 742, 759, '43.062 cmb'),     # colonne VOISINE : ignorée
            (261, 308, 756, 776, '22.45%'),         # colonne VOISINE : ignorée
            (660, 726, 743, 760, '191.800 crr*'),   # cm² sous pastille 2
            (657, 709, 755, 776, '100.00%'),        # % sous pastille 2
        ]
        rows = self._rows()
        self.assertEqual(pair_ocr_values(rows, items), 2)
        self.assertEqual(rows[0]['coverage_percent'], 21.06)
        self.assertEqual(rows[0]['coverage_area_cm2'], 40.402)
        self.assertEqual(rows[1]['coverage_percent'], 100.0)
        self.assertEqual(rows[1]['coverage_area_cm2'], 191.8)
        self.assertEqual(rows[0]['values_source'], 'OCR')

    def test_apply_ocr_names_blanc(self):
        items = [(679, 714, 718, 733, 'blane')]
        rows = self._rows()
        self.assertEqual(apply_ocr_names(rows, items), 1)
        self.assertEqual(rows[1]['name'], 'BLANC')
        self.assertEqual(rows[1]['ink_type'], 'WHITE')
        self.assertEqual(rows[0]['name'], 'MAGENTA')  # nom référentiel préservé


class OcrJobHintsTests(unittest.TestCase):
    def test_hints_scan_complets(self):
        items = [
            (823, 1088, 476, 501, 'JoB:TwinGAUFRETTE20gr'),
            (120, 260, 520, 545, 'LAIZE:137mm'),
            (300, 470, 520, 545, 'LAIZETotale:959mm'),
            (500, 700, 520, 545, 'PASDECOUPE:140mm'),
            (900, 1000, 600, 620, 'NBR.POSES EN LAIZE:'), (1010, 1030, 600, 620, '4'),
            (900, 1000, 630, 650, 'NBR.POSES EN COUPE:'), (1010, 1030, 630, 650, '7'),
            (929, 1018, 706, 727, '137.0LPI'), (826, 949, 708, 731, 'LINIEATURE:'),
        ]
        hints = ocr_job_hints(items)
        self.assertEqual(hints['name'], 'Twin GAUFRETTE 20gr')
        # V1.7 : la laize du job = laize TOTALE (toutes pistes), la piste reste à part
        self.assertEqual(hints['laize_piste_mm'], 137.0)
        self.assertEqual(hints['width_mm'], 959.0)
        self.assertEqual(hints['repeat_mm'], 140.0)
        self.assertEqual(hints['poses_across'], 4)
        self.assertEqual(hints['poses_repeat'], 7)
        self.assertEqual(hints['lineature_lpi'], 137.0)

    def test_hints_zones_decoupees(self):
        items = [
            (186, 419, 468, 500, 'KODAKFLEXCEL'),
            (186, 260, 495, 510, 'FLEXOSOLUTIONS'),
            (823, 860, 476, 500, 'JoB:'),
            (865, 1088, 476, 500, 'TwinGAUFRETTE20gr'),
            (120, 260, 520, 545, 'LAIZE:137mm'),
            (500, 700, 520, 545, 'PASDECOUPE:'),
            (705, 780, 520, 545, '140mm'),
            (900, 1000, 600, 620, 'NBR.POSES ENLAIZE:'),
            (1010, 1030, 600, 620, '4'),
            (900, 1000, 630, 650, 'NBR.POSES EN COUPE:'),
            (1010, 1030, 630, 650, '7'),
        ]
        hints = ocr_job_hints(items)
        self.assertEqual(hints['name'], 'Twin GAUFRETTE 20gr')
        self.assertEqual(hints['repeat_mm'], 140.0)
        self.assertEqual(hints['poses_across'], 4)
        self.assertEqual(hints['poses_repeat'], 7)


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


# Fiche réelle « Chips mini RIFKUS ketchup » (scan, 7 C) : zones OCR relevées tel quel.
_FICHE_RIFKUS = [
    (684, 887, 62, 81, 'ChipsminiRIFKUSketchup'), (934, 1000, 64, 78, 'AMALGAME:'),
    (657, 679, 66, 80, 'JOB:'), (656, 746, 92, 109, 'LAIZE:345mm'),
    (775, 911, 91, 110, 'LAIZETotale:1035mm'), (924, 1047, 92, 109, 'PASDECOUPE:190mm'),
    (1040, 1140, 137, 151, 'NBR .POSES EN LAIZE:'), (1041, 1144, 159, 171, 'NBR.POSES EN COUPE:'),
    (178, 262, 178, 191, 'Nbr de couleurs :'), (295, 324, 173, 191, '7 C'),
    (196, 220, 242, 256, 'Cyan'), (247, 285, 242, 255, 'Magenta'), (311, 339, 243, 254, 'Yellow'),
    (369, 396, 242, 255, 'Black'), (415, 467, 242, 253, 'PANTONE 485'),
    (473, 526, 242, 253, 'PANTONE 654'), (546, 572, 242, 255, 'blanc'),
    (179, 232, 261, 275, '315.388 cm'), (238, 284, 263, 274, '51.078 cm²'),
    (297, 343, 263, 274, '74.559 cm*'), (355, 400, 263, 274, '66.841 cma'),
    (414, 463, 263, 274, '184.849 cm²'), (471, 523, 262, 275, '303.977.cm²'),
    (532, 582, 263, 274, '655.500 cm²'),
    (180, 212, 273, 285, '48.11%'), (239, 265, 273, 285, '7.79%'), (297, 328, 273, 285, '11.37%'),
    (355, 386, 273, 285, '10.20%'), (413, 445, 273, 285, '20.0%'),   # 20.0 = erreur OCR (28.20)
    (473, 504, 273, 285, '46.37%'), (532, 567, 273, 284, '100.00%'),
    (734, 802, 236, 250, '137.0LPI'), (658, 717, 239, 252, 'LINIEATURE :'),
    (657, 749, 276, 291, 'AVEC QUINCONCE:'), (190, 246, 295, 308, 'REMARQUE:'),
]


class LegendeOcrTests(unittest.TestCase):
    """V1.7 : couleurs lues dans la légende, jamais dans la maquette ; laize totale."""

    def test_sept_couleurs_legende_et_pourcentage_recalcule(self):
        hints = ocr_job_hints(_FICHE_RIFKUS)
        rows, expected = legend_rows_from_ocr(_FICHE_RIFKUS, (1381, 386), hints)
        self.assertEqual(expected, 7)
        self.assertEqual([r['name'] for r in rows],
                         ['Cyan', 'Magenta', 'Yellow', 'Black', 'PANTONE 485', 'PANTONE 654', 'BLANC'])
        self.assertEqual(len(rows), 7)
        pan485 = rows[4]
        self.assertEqual(pan485['coverage_area_cm2'], 184.849)
        self.assertEqual(pan485['coverage_percent'], 28.2)      # 20.0 OCR corrigé d'après la surface
        self.assertIn('corrigé', pan485['check'])
        self.assertEqual(rows[5]['coverage_area_cm2'], 303.977)  # point parasite « .cm² » accepté
        blanc = rows[6]
        self.assertEqual(blanc['ink_type'], 'WHITE')
        self.assertEqual(blanc['coverage_percent'], 100.0)

    def test_job_nom_sans_amalgame_et_laize_totale(self):
        hints = ocr_job_hints(_FICHE_RIFKUS)
        self.assertEqual(hints['name'], 'Chips mini RIFKUS ketchup')
        self.assertNotIn('AMALGAME', hints['name'])
        self.assertEqual(hints['laize_piste_mm'], 345.0)
        self.assertEqual(hints['laize_totale_mm'], 1035.0)
        self.assertEqual(hints['width_mm'], 1035.0)              # surface sur toutes les pistes
        self.assertEqual(hints['repeat_mm'], 190.0)
        self.assertEqual(hints['lineature_lpi'], 137.0)

    def test_maquette_ignoree(self):
        # textes de maquette hors légende (haut de page, nom de couleur isolé) : ignorés
        bruit = _FICHE_RIFKUS + [(400, 440, 40, 60, 'PANTONE 186 C'), (100, 140, 140, 160, 'Magenta')]
        hints = ocr_job_hints(bruit)
        rows, _ = legend_rows_from_ocr(bruit, (1381, 386), hints)
        self.assertEqual(len(rows), 7)
        self.assertNotIn('PANTONE 186', [r['name'] for r in rows])

    def test_sans_legende_aucune_couleur_inventee(self):
        rows, expected = legend_rows_from_ocr([(10, 60, 10, 25, 'Bonjour')], (500, 500), {})
        self.assertEqual(rows, [])
        self.assertIsNone(expected)

# Fiche réelle « La Dorée couscous Moyen 1Kg » (scan, 8 C, 975 mm = 3 × 325) : zones OCR relevées.
_FICHE_DOREE = [
    (688, 935, 61, 76, 'JoB:ladorrcccouscousMoycn1Kg'), (958, 1024, 59, 74, 'AMALGAME:'),
    (686, 776, 86, 105, 'LAIZE:325mm'), (803, 927, 87, 104, 'LAIZETotale:975mm'),
    (948, 1069, 88, 104, 'PASDECOUPE.650 mm'), (1089, 1211, 86, 105, 'Porte cliche: 650 mm'),
    (1062, 1159, 131, 144, 'NBR .POSES EN LAIZE:'), (1062, 1163, 152, 165, 'NBR.POSES EN COUPE:'),
    (335, 365, 164, 184, '8C'), (221, 305, 169, 185, 'Nbr de couleurs :'),
    (764, 829, 227, 241, '137.0LPI'),
    (240, 264, 234, 247, 'Cyan'), (290, 327, 234, 246, 'Magenta'), (351, 380, 233, 246, 'MO)IPA'),
    (409, 434, 233, 246, 'Biack'), (452, 504, 233, 245, 'PANTONE 425'), (517, 556, 233, 245, 'PANTONE'),
    (572, 614, 233, 245, 'PANTONE'), (637, 661, 234, 247, 'blane'),
    (521, 552, 244, 255, 'BlackC'), (568, 617, 244, 255, 'Reflex Blue C'),
    (225, 269, 253, 265, '33.985 cm'), (282, 326, 252, 265, '50.762 cm'),
    (339, 387, 253, 265, '178.047 CTP'), (397, 443, 252, 265, '123.051 cm'),
    (452, 500, 252, 265, '674.831 cm'), (509, 552, 253, 265, '11.432 cm'),
    (566, 610, 253, 265, '47.826 cm'), (622, 671, 253, 265, '979.120 cml'),
    (223, 251, 262, 276, '3.22%'), (281, 309, 263, 276, '4.81%'), (339, 369, 263, 276, '16.86%'),
    (395, 426, 263, 275, '11.65%'), (452, 483, 263, 275, '63.89%'), (509, 536, 263, 276, '1.05%'),
    (564, 592, 261, 277, '4.53%'), (621, 653, 262, 276, '92.70%'),
    (688, 780, 263, 281, 'AVEC QUINCON E:'), (234, 288, 285, 297, 'REMARQUE:'),
]


class LegendeFicheDoreeTests(unittest.TestCase):
    """V1.7 : 8 colonnes annoncées, noms partiels recollés, surface déduite des couleurs."""

    def test_huit_colonnes_valeurs_et_surface(self):
        rows, expected = legend_rows_from_ocr(_FICHE_DOREE, (1362, 433), ocr_job_hints(_FICHE_DOREE))
        self.assertEqual(expected, 8)
        self.assertEqual(len(rows), 8)
        self.assertEqual([r['coverage_percent'] for r in rows],
                         [3.22, 4.81, 16.86, 11.65, 63.89, 1.08, 4.53, 92.7])
        self.assertEqual(rows[0]['coverage_area_cm2'], 33.985)
        self.assertEqual(rows[2]['coverage_area_cm2'], 178.047)   # « CTP » au lieu de « cm² »
        self.assertEqual(rows[7]['ink_type'], 'WHITE')

    def test_noms_recuperes_et_avertis(self):
        rows, _ = legend_rows_from_ocr(_FICHE_DOREE, (1362, 433), ocr_job_hints(_FICHE_DOREE))
        names = [r['name'] for r in rows]
        self.assertEqual(names[0], 'Cyan')
        self.assertEqual(names[3], 'Black')                       # « Biack » reconnu
        self.assertTrue(names[2].startswith('Encre n°3'))        # « MO)IPA » : jamais de nom par position
        self.assertIn('nom illisible', rows[2]['check'])
        self.assertNotIn('Yellow', names)                         # V1.8 : aucun nom déduit de la position
        self.assertEqual(names[5], 'PANTONE Black C')             # « PANTONE » + « BlackC » recollés
        self.assertEqual(names[6], 'PANTONE Reflex Blue C')
        self.assertIn('numéro Pantone', rows[4]['check'])

    def test_laize_totale_et_poses_non_lues_signalees(self):
        hints = ocr_job_hints(_FICHE_DOREE)
        self.assertEqual(hints['width_mm'], 975.0)                # laize totale affichée
        self.assertEqual(hints['repeat_mm'], 650.0)
        self.assertNotIn('poses_across', hints)                   # poses non lues : pas inventées


class V18NomsEtJobTests(unittest.TestCase):
    """V1.8 : noms jamais déduits par position ; Pantone et job lisibles."""

    def test_pantone_suffixe_et_job_couscous(self):
        from core.services.bat_extractor import _clean_job_name, _pantone_fmt
        self.assertEqual(_pantone_fmt('PANTONE 7731C'), 'PANTONE 7731 C')
        self.assertEqual(_pantone_fmt('PANTONE 485'), 'PANTONE 485')
        self.assertEqual(_clean_job_name('COUSCOUSMOYEN 1KGCHORKHALED'), 'COUSCOUS MOYEN 1KG CHOR KHALED')
        self.assertEqual(_clean_job_name('Chipsmini'), 'Chips mini')

    def test_motif_robuste_a_une_valeur_fausse(self):
        hints = ocr_job_hints(_FICHE_RIFKUS)
        rows, _ = legend_rows_from_ocr(_FICHE_RIFKUS, (1381, 386), hints)
        self.assertEqual(rows[4]['coverage_percent'], 28.2)      # la ligne à 20.0 % ne fausse pas le motif

    def test_aucun_nom_positionnel(self):
        rows, _ = legend_rows_from_ocr(_FICHE_DOREE, (1362, 433), ocr_job_hints(_FICHE_DOREE))
        for r in rows:
            if r['name'].startswith('Encre n°'):
                self.assertIn('nom à saisir', r['name'])
        self.assertFalse(any(r['name'] in ('Magenta',) and 'Magenta' not in ' '.join(
            str(it[4]) for it in _FICHE_DOREE) for r in rows))
