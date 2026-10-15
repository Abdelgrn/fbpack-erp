"""V1.10 : fournisseur de clichés et tableau de consommation (sans base de données)."""
import unittest

from core.services.cliche_suppliers import NON_RENSEIGNE, summarize, supplier_or_blank


class SupplierTests(unittest.TestCase):
    def test_valeur_postee_filtree(self):
        self.assertEqual(supplier_or_blank('Poly Slim'), 'Poly Slim')
        self.assertEqual(supplier_or_blank('  Studio Flexo '), 'Studio Flexo')
        self.assertEqual(supplier_or_blank('n importe quoi'), '')
        self.assertEqual(supplier_or_blank(None), '')


class SummarizeTests(unittest.TestCase):
    def test_totaux_et_tri(self):
        rows = summarize([('Poly Slim', 10, 50), ('Poly Slim', 6, 30),
                          ('Studio Flexo', 4, 20), ('', 2, 10)])
        self.assertEqual([r['supplier'] for r in rows], ['Poly Slim', 'Studio Flexo', NON_RENSEIGNE])
        poly = rows[0]
        self.assertEqual(poly['jobs'], 2)
        self.assertAlmostEqual(poly['total_kg'], 16)
        self.assertAlmostEqual(poly['avg_kg'], 8)
        self.assertAlmostEqual(poly['g_per_m2'], 200)          # 16 000 g / 80 m²
        self.assertAlmostEqual(rows[1]['g_per_m2'], 200)       # 4 000 g / 20 m²

    def test_liste_vide(self):
        self.assertEqual(summarize([]), [])


if __name__ == '__main__':
    unittest.main()
