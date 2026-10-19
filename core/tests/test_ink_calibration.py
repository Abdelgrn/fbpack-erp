"""Tests du calage (INK_CALIBRATION V1.3). Hors Django.

Réglages de référence : transfert 32 %, densité 0,87 (couleurs et blanc).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.services import ink_calibration as ic  # noqa: E402

# passage des réglages 40 % / 1,3 (couleurs) et 40 % / 1,5 (blanc) vers 32 % / 0,87
S_COL = (0.32 * 0.87) / (0.40 * 1.3)
S_WH = (0.32 * 0.87) / (0.40 * 1.5)


class FamilyTests(unittest.TestCase):
    def test_alias(self):
        self.assertEqual(ic.family_for('Blanc'), 'Blanc')
        self.assertEqual(ic.family_for('PANTONE 485 C'), 'PANTONE 485')
        self.assertEqual(ic.family_for('  Cyan '), 'Cyan')
        self.assertEqual(ic.family_for('PANTONE 7442C'), 'PANTONE 7442C')

    def test_non_calee(self):
        self.assertIsNone(ic.family_for('Bleu reflex'))
        r = ic.calibrated_estimate('Bleu reflex', 2.8)
        self.assertEqual(r['statut'], 'non calé')
        self.assertEqual(r['estime_kg'], 2.8)
        self.assertIsNone(r['bas_kg'])

    def test_indicative(self):
        r = ic.calibrated_estimate('PANTONE 7442C', 100.0)
        self.assertEqual(r['statut'], 'indicatif (1 job)')
        self.assertAlmostEqual(r['estime_kg'], 134.0, places=2)
        self.assertIsNone(r['bas_kg'])


class EstimateTests(unittest.TestCase):
    def test_blanc_mediane_et_fourchette(self):
        r = ic.calibrated_estimate('Blanc', 100.0)
        self.assertAlmostEqual(r['estime_kg'], 84.0, places=2)
        self.assertAlmostEqual(r['bas_kg'], 73.0, places=2)
        self.assertAlmostEqual(r['haut_kg'], 123.0, places=2)

    def test_fourchette_ordonnee(self):
        for name in ['Cyan', 'Magenta', 'Yellow', 'Black', 'PANTONE 485', 'Blanc']:
            r = ic.calibrated_estimate(name, 10.0)
            self.assertLessEqual(r['bas_kg'], r['estime_kg'])
            self.assertLessEqual(r['estime_kg'], r['haut_kg'])

    def test_total_job(self):
        rows, tot = ic.estimate_job([('Blanc', 100.0), ('Bleu reflex', 10.0)])
        self.assertAlmostEqual(tot['estime_kg'], 94.0, places=2)
        self.assertAlmostEqual(tot['theorique_kg'], 110.0, places=2)


class G_m2Tests(unittest.TestCase):
    def test_g_m2_blanc(self):
        r = ic.calibrated_g_m2('Blanc', 6.216)
        self.assertAlmostEqual(r['estime_g_m2'], 5.221, places=3)
        self.assertAlmostEqual(r['bas_g_m2'], 4.538, places=3)
        self.assertAlmostEqual(r['haut_g_m2'], 7.646, places=3)

    def test_g_m2_non_calee(self):
        r = ic.calibrated_g_m2('Bleu reflex', 0.144)
        self.assertEqual(r['estime_g_m2'], 0.144)
        self.assertIsNone(r['bas_g_m2'])


class InSampleTests(unittest.TestCase):
    """Contrôle dans l'échantillon (les jobs ont servi au calage : optimiste).
    Entrées : prévu ERP à préparer (réglages 40 %/1,3/1,5), converti en théorique net 32 %/0,87.
    Tolérance : 30 % sur le total. MAMAMIA (blanc) est exclu : c'est le cas limite signalé."""

    JOBS = {
        'CHOR': [('Cyan', 2.718, 5), ('Magenta', 4.232, 10), ('Yellow', 4.931, 6), ('Black', 4.523, 10),
                 ('PANTONE 485', 181.036, 100), ('Blanc', 393.839, 140)],
        'SULTANA': [('Cyan', 1.892, 5), ('Magenta', 5.693, 5), ('Yellow', 20.540, 15), ('Black', 18.0, 10),
                    ('PANTONE 485', 161.267, 70), ('Blanc', 407.517, 125)],
        'RIFKUS ZVITI': [('Cyan', 3.056, 8), ('Magenta', 150.061, 90), ('Yellow', 164.791, 75),
                         ('Black', 221.437, 100), ('Blanc', 558.050, 195)],
        'DULCESO': [('Magenta', 35.807, 25), ('Yellow', 37.734, 25), ('Black', 47.698, 13),
                    ('PANTONE 485', 12.303, 15)],
    }

    def test_totaux_dans_30_pour_cent(self):
        for job, inks in self.JOBS.items():
            lines = [(n, prep / 1.1 * (S_WH if n == 'Blanc' else S_COL)) for n, prep, real in inks]
            _, tot = ic.estimate_job(lines)
            real = sum(r for _, _, r in inks)
            ecart = tot['estime_kg'] / real - 1
            self.assertLess(abs(ecart), 0.30, f'{job} : écart {ecart:+.0%}')


if __name__ == '__main__':
    unittest.main()
