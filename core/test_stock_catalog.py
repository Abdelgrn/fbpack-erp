from django.test import SimpleTestCase

from core.services import stock_catalog as c


class StockCatalogRulesTests(SimpleTestCase):
    def test_units(self):
        self.assertEqual(c.canonical_unit_name('kg'), 'KG')
        self.assertEqual(c.canonical_unit_name(' Etiquette '), 'ETQ')
        self.assertEqual(c.canonical_unit_name(None), '')
        self.assertTrue(c.is_mass_unit('KG'))
        self.assertFalse(c.is_mass_unit('SAC'))

    def test_category_from_family(self):
        self.assertEqual(c.technical_category('ENCRES'), 'INK')
        self.assertEqual(c.technical_category('COLLE'), 'GLUE')
        self.assertEqual(c.technical_category('SOLVANTS'), 'SOLV')
        self.assertEqual(c.technical_category('FOURNITURES'), 'FILM')
        self.assertEqual(c.technical_category('', designation='ENCRE BLEUE'), 'INK')

    def test_film_specs_only_for_rolls_in_kg(self):
        self.assertTrue(c.needs_film_specs('FILM', 'FILM OPP', 'KG'))
        self.assertFalse(c.needs_film_specs('FILM', 'FOURNITURES', 'KG'))
        self.assertFalse(c.needs_film_specs('FILM', 'FILM OPP', 'SAC'))
        self.assertFalse(c.needs_film_specs('INK', 'ENCRES', 'KG'))

    def test_clean_cell(self):
        self.assertEqual(c.clean_cell(123.0), '123')
        self.assertEqual(c.clean_cell('  A   B '), 'A B')

    def test_parse_film_dimensions(self):
        self.assertEqual(c.parse_film_dimensions('BOPP METALLISE BIAXIAL 760MM 20MIC'), (760, 20))
        self.assertEqual(c.parse_film_dimensions('FILM BOPP BLANC ETIQ 38\u00b5 LAIZE 800'), (800, 38))
        self.assertEqual(c.parse_film_dimensions('DUPLEX BIMBIM'), (None, None))

    def test_paper_grammage_and_laize(self):
        self.assertEqual(c.parse_grammage('PAPIER KRAFT MOSAICO 80 GRS LAIZE 420MM'), 80)
        self.assertEqual(c.parse_grammage('PAPIER PACK PRO ROXEL 50G/830'), 50)
        self.assertEqual(c.parse_grammage('PAPIER NIKLASELECT SD 1090MM 90G ROXEL'), 90)
        self.assertEqual(c.parse_film_dimensions('PAPIER PACK PRO ROXEL 50G/830')[0], 830)
        self.assertEqual(c.parse_film_dimensions('PAPIER STARKRAFT 80G/420MM')[0], 420)
        self.assertTrue(c.is_paper('PAPIER', 'PAPIER KRAFT', 'X'))
        self.assertFalse(c.is_paper('FILM OPP', '', 'PAPIER'))
        self.assertTrue(c.is_paper('', '', 'PAPIER KRAFT BLANCHI MG 75GR LAIZE 730MM'))
