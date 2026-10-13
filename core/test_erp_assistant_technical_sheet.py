from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Client, PrepressColor, TechnicalProduct
from core.models.permissions import UserModulePermission
from core.views.erp_assistant import answer_question


class AssistantTechnicalSheetTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username='assistant-admin',
            email='assistant@example.invalid',
            password=None,
        )
        self.user = get_user_model().objects.create_user(
            username='assistant-prepress',
            password=None,
        )
        self.unauthorized = get_user_model().objects.create_user(
            username='assistant-sans-prepress',
            password=None,
        )
        UserModulePermission.objects.create(
            user=self.user,
            can_access_prepress=True,
        )
        self.customer = Client.objects.create(
            name='BMD ALANYA SNACKS',
            code_client='BMD-01',
            city='Oran',
            phone='0000000000',
        )
        self.product = TechnicalProduct.objects.create(
            client=self.customer,
            ref_internal='25F052',
            name='RIFKUS CORNIX KETCHUP MEXICAIN',
            printing_process='FLEXO',
            width_mm=385,
            cut_length_mm=240,
            nb_poses_pas=3,
            nb_poses_laize=3,
            bat_status='VALIDE',
            version='V2.0',
        )
        PrepressColor.objects.create(
            product=self.product,
            ordre=1,
            couleur_hex='#00AEEF',
            nom_couleur='CYAN',
            anilox='420 / 5',
        )
        self.product.num_colors = 1
        self.product.save(update_fields=['num_colors', 'updated_at'])

    def test_exact_reference_returns_summary_and_direct_actions(self):
        answer, kind, links = answer_question(
            self.admin,
            'Je veux la fiche technique du produit 25F052',
        )
        self.assertEqual(kind, 'SUCCESS')
        self.assertIn('25F052', answer)
        self.assertIn('RIFKUS CORNIX', answer)
        self.assertIn('720 mm', answer)
        self.assertIn('1155 mm', answer)
        self.assertIn('CYAN', answer)
        self.assertEqual(len(links), 3)
        self.assertEqual(links[0]['url'], reverse('prepress_technical_sheet_pdf', args=[self.product.pk]))
        self.assertEqual(links[1]['url'], reverse('prepress_technical_sheet', args=[self.product.pk]))
        self.assertEqual(links[2]['url'], reverse('prepress_technical_sheet_print', args=[self.product.pk]))

    def test_contextual_request_uses_current_product(self):
        answer, _, links = answer_question(
            self.user,
            'Donne-moi la fiche technique de ce produit',
            context=f'/prepress/fiche/{self.product.pk}/',
        )
        self.assertIn('25F052', answer)
        self.assertTrue(any(link['url'].endswith(f'/prepress/fiche/{self.product.pk}/') for link in links))

    def test_client_search_returns_candidates_without_guessing(self):
        second = TechnicalProduct.objects.create(
            client=self.customer,
            ref_internal='25F053',
            name='AUTRE ARTICLE CLIENT',
            width_mm=300,
            cut_length_mm=200,
            nb_poses_pas=1,
            nb_poses_laize=1,
        )
        answer, kind, links = answer_question(
            self.admin,
            'Montre les fiches techniques du client BMD ALANYA',
        )
        self.assertEqual(kind, 'QUESTION')
        self.assertIn('Plusieurs fiches', answer)
        self.assertIn('25F052', answer)
        self.assertIn('25F053', answer)
        urls = {link['url'] for link in links}
        self.assertIn(reverse('prepress_technical_sheet', args=[self.product.pk]), urls)
        self.assertIn(reverse('prepress_technical_sheet', args=[second.pk]), urls)

    def test_user_without_prepress_permission_receives_no_product_data(self):
        answer, kind, links = answer_question(
            self.unauthorized,
            'Fiche technique 25F052',
        )
        self.assertEqual(kind, 'ERROR')
        self.assertIn('autorisation', answer)
        self.assertNotIn('25F052', answer)
        self.assertEqual(links, [])

    def test_assistant_api_returns_pdf_and_sheet_links(self):
        self.client.force_login(self.user)
        home = self.client.get(reverse('assistant_home'))
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, 'fiche technique du produit 25F052')

        response = self.client.post(reverse('assistant_ask'), {
            'question': 'Télécharge la fiche technique 25F052 en PDF',
            'context': '/assistant/',
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertIn('25F052', payload['answer'])
        self.assertEqual(payload['links'][0]['url'], reverse('prepress_technical_sheet_pdf', args=[self.product.pk]))
        self.assertEqual(payload['links'][0]['target'], '_blank')
