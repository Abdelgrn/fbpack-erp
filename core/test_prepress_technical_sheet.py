import shutil
import tempfile
from datetime import date
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.forms.prepress import ProductForm
from core.models import Client, PrepressColor, TechnicalProduct, TechnicalProductRevision


TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='fbpack-prepress-tests-')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class PrepressTechnicalSheetTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='prepress-admin',
            email='prepress@example.invalid',
            password=None,
        )
        self.client.force_login(self.user)
        self.customer = Client.objects.create(
            name='Client Test',
            code_client='T-001',
            city='Oran',
            phone='0000000000',
        )

    def _product_payload(self, **overrides):
        data = {
            'client': str(self.customer.pk),
            'ref_internal': 'ft-001',
            'name': 'Emballage test',
            'printing_process': 'FLEXO',
            'structure_type': 'DUPLEX',
            'width_mm': '250.5',
            'cut_length_mm': '180',
            'date_creation': date.today().isoformat(),
            'graveur': 'Studio Test',
            'ref_graveur': 'GR-42',
            'type_dossier': 'NOUVEAU',
            'nb_poses_pas': '2',
            'nb_poses_laize': '3',
            'developpement_mm': '0',
            'laize_gravure_mm': '0',
            'support_impression': 'OPP transparent 30',
            'impression': 'Cello email',
            'spot': '15 x 15',
            'technical_notes': 'Essai métier.',
            'sens_bobine': '1',
            'spot_placement': '1',
            'bat_status': 'ATTENTE',
            'version': 'V1.0',
            'revision_reason': 'Création par test automatisé',
            'colors-TOTAL_FORMS': '8',
            'colors-INITIAL_FORMS': '0',
            'colors-MIN_NUM_FORMS': '0',
            'colors-MAX_NUM_FORMS': '8',
            'colors-0-couleur_hex': '#00AEEF',
            'colors-0-nom_couleur': 'CYAN',
            'colors-0-anilox': '420 / 5',
            'colors-0-adhesif': 'Mousse 0,55',
            'colors-0-viscosite': '22 s',
            'colors-0-type_encre': 'Solvant',
            'colors-0-formule_encre': 'Base cyan',
        }
        data.update(overrides)
        return data

    def test_model_recalculates_derived_dimensions(self):
        product = TechnicalProduct.objects.create(
            client=self.customer,
            ref_internal='CALC-001',
            name='Calcul dimensions',
            width_mm=250.5,
            cut_length_mm=180,
            nb_poses_pas=2,
            nb_poses_laize=3,
        )
        self.assertEqual(product.developpement_mm, 360)
        self.assertEqual(product.laize_gravure_mm, 751.5)

    def test_form_never_trusts_posted_calculated_values(self):
        payload = self._product_payload(
            developpement_mm='999999',
            laize_gravure_mm='999999',
        )
        form = ProductForm(payload)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['developpement_mm'], 360)
        self.assertEqual(form.cleaned_data['laize_gravure_mm'], 751.5)

    def test_creation_is_atomic_and_creates_a_revision(self):
        response = self.client.post(reverse('add_product'), self._product_payload())
        self.assertEqual(response.status_code, 302)
        product = TechnicalProduct.objects.get(ref_internal='ft-001')
        self.assertEqual(product.num_colors, 1)
        self.assertEqual(product.developpement_mm, 360)
        self.assertEqual(product.laize_gravure_mm, 751.5)
        self.assertEqual(product.last_modified_by, self.user)
        self.assertEqual(PrepressColor.objects.filter(product=product).count(), 1)

        revision = TechnicalProductRevision.objects.get(product=product)
        self.assertEqual(revision.revision_number, 1)
        self.assertEqual(revision.snapshot['colors'][0]['nom_couleur'], 'CYAN')
        forbidden_keys = {'password', 'cookie', 'csrf', 'token', 'session'}
        serialized = str(revision.snapshot).lower()
        self.assertFalse(any(key in serialized for key in forbidden_keys))

    def test_invalid_color_does_not_create_orphan_product(self):
        payload = self._product_payload(**{
            'ref_internal': 'FT-BAD',
            'colors-0-couleur_hex': 'not-a-color',
        })
        response = self.client.post(reverse('add_product'), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TechnicalProduct.objects.filter(ref_internal='FT-BAD').exists())

    def test_product_visual_is_validated_saved_and_embedded(self):
        from PIL import Image
        from core.services.prepress_technical_sheet import build_print_context

        buffer = BytesIO()
        Image.new('RGB', (24, 24), '#00AEEF').save(buffer, format='PNG')
        upload = SimpleUploadedFile(
            'visuel-produit.png',
            buffer.getvalue(),
            content_type='image/png',
        )
        payload = self._product_payload(ref_internal='VIS-001')
        payload['product_visual'] = upload
        response = self.client.post(reverse('add_product'), payload)
        self.assertEqual(response.status_code, 302)
        product = TechnicalProduct.objects.get(ref_internal='VIS-001')
        self.assertTrue(product.product_visual.name.endswith('.png'))
        self.assertTrue(product.product_visual.storage.exists(product.product_visual.name))
        context = build_print_context(product)
        self.assertTrue(context['product_visual_data_uri'].startswith('data:image/png;base64,'))

    def test_pdf_engines_generate_valid_documents(self):
        product = TechnicalProduct.objects.create(
            client=self.customer,
            ref_internal='PDF-001',
            name='Produit PDF',
            width_mm=120,
            cut_length_mm=200,
            nb_poses_pas=1,
            nb_poses_laize=2,
            last_modified_by=self.user,
        )
        response = self.client.get(reverse('prepress_technical_sheet_pdf', args=[product.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(response['X-PDF-Engine'], {'weasyprint', 'reportlab'})
        self.assertTrue(response.content.startswith(b'%PDF'))

        from core.services.prepress_technical_sheet import build_print_context, generate_reportlab_pdf
        fallback_pdf = generate_reportlab_pdf(product, build_print_context(product))
        self.assertTrue(fallback_pdf.startswith(b'%PDF'))
        self.assertGreater(len(fallback_pdf), 1000)

    def test_detail_print_and_history_routes_are_protected_and_render(self):
        product = TechnicalProduct.objects.create(
            client=self.customer,
            ref_internal='VIEW-001',
            name='Produit affiché',
            width_mm=120,
            cut_length_mm=200,
            nb_poses_pas=1,
            nb_poses_laize=2,
            last_modified_by=self.user,
        )
        list_response = self.client.get(reverse('prepress_technical_sheet_list'))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, 'VIEW-001')

        form_response = self.client.get(reverse('add_product'))
        self.assertEqual(form_response.status_code, 200)
        self.assertContains(form_response, 'Sens de défilement')
        self.assertContains(form_response, 'roll-picto')
        self.assertContains(form_response, 'spot-picto')

        for route_name in (
            'prepress_technical_sheet',
            'prepress_technical_sheet_print',
            'prepress_technical_sheet_revisions',
        ):
            response = self.client.get(reverse(route_name, args=[product.pk]))
            self.assertEqual(response.status_code, 200, route_name)

        self.client.logout()
        response = self.client.get(reverse('prepress_technical_sheet', args=[product.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)

        unauthorized_user = get_user_model().objects.create_user(
            username='sans-prepress',
            password=None,
        )
        self.client.force_login(unauthorized_user)
        response = self.client.get(reverse('prepress_technical_sheet', args=[product.pk]))
        self.assertEqual(response.status_code, 403)
