"""Tests du stock produit fini (PRODUIT_FINI_SYNC V1)."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Client, TechnicalProduct, UserModulePermission
from core.models.stock_produit_fini import (
    ProduitFiniBobine, ProduitFiniLot, ProduitFiniMouvement, ProduitFiniPalette,
)
from core.services.produit_fini import (
    annuler_mouvement, destocker, enregistrer_bobine, entrer_en_stock, resume_bobines,
    traiter_evenement,
)

TOKEN = 'jeton-de-test-123'


def evt(uid, bobine='1', palette='PAL-001', poids=20.5, client='CHOR KHALED',
        article='Couscous Moyen 1 Kg', lot='LOT-041', heure='2026-10-19 10:15:00'):
    return {
        'type': 'BOBINE', 'uid': uid, 'client_nom': client, 'article': article,
        'numero_lot': lot, 'numero_palette': palette, 'numero_bobine': bobine,
        'poids_kg': poids, 'date_heure': heure, 'operateur': 'Ali', 'equipe': 'A',
        'statut': 'ok',
    }


def cloturer_et_entrer(lot_nom='LOT-041', client='CHOR KHALED', article='Couscous Moyen 1 Kg'):
    """Le job est clôturé dans la pesée, puis le lot est entré en stock (action manuelle)."""
    traiter_evenement({'type': 'JOB_CLOTURE', 'uid': f'c-{lot_nom}', 'client_nom': client,
                       'article': article, 'numero_lot': lot_nom})
    return entrer_en_stock(ProduitFiniLot.objects.get(numero_lot=lot_nom))


class ReceptionTests(TestCase):
    def setUp(self):
        self.client_erp = Client.objects.create(name='CHOR KHALED')
        self.prod = TechnicalProduct.objects.create(
            client=self.client_erp, ref_internal='REF-1', name='Couscous Moyen 1 Kg')

    def test_creation_lot_palette_bobine_et_mouvement(self):
        self.assertEqual(enregistrer_bobine(evt('u1')), 'creee')
        lot = ProduitFiniLot.objects.get()
        self.assertEqual(lot.client, self.client_erp)
        self.assertEqual(lot.produit, self.prod)
        self.assertFalse(lot.a_relier)
        self.assertEqual(ProduitFiniPalette.objects.get().numero_palette, 'PAL-001')
        self.assertEqual(ProduitFiniBobine.objects.get().poids_kg, 20.5)
        mv = ProduitFiniMouvement.objects.get()
        self.assertEqual((mv.type, mv.nb_bobines), ('ENTREE', 1))

    def test_doublon_ignore(self):
        enregistrer_bobine(evt('u1'))
        self.assertEqual(enregistrer_bobine(evt('u1')), 'deja_recue')
        self.assertEqual(ProduitFiniBobine.objects.count(), 1)
        self.assertEqual(ProduitFiniMouvement.objects.count(), 1)

    def test_nom_client_insensible_a_la_casse_et_aux_espaces(self):
        enregistrer_bobine(evt('u1', client='  chor   khaled '))
        self.assertEqual(ProduitFiniLot.objects.get().client, self.client_erp)

    def test_client_inconnu_marque_a_relier(self):
        enregistrer_bobine(evt('u1', client='Client Inconnu'))
        lot = ProduitFiniLot.objects.get()
        self.assertIsNone(lot.client)
        self.assertTrue(lot.a_relier)
        self.assertEqual(lot.client_nom, 'Client Inconnu')

    def test_evenement_invalide_ne_bloque_pas_les_autres(self):
        res = [traiter_evenement(evt('u1')),
               traiter_evenement(evt('u2', poids=-1)),
               traiter_evenement({'type': 'BIZARRE', 'uid': 'u3'}),
               traiter_evenement(evt('u4', bobine='2'))]
        self.assertEqual([r['statut'] for r in res], ['creee', 'erreur', 'erreur', 'creee'])
        self.assertEqual(ProduitFiniBobine.objects.count(), 2)

    def test_cloture_job_marque_le_lot(self):
        enregistrer_bobine(evt('u1'))
        r = traiter_evenement({'type': 'JOB_CLOTURE', 'uid': 'c1', 'client_nom': 'CHOR KHALED',
                               'article': 'Couscous Moyen 1 Kg', 'numero_lot': 'LOT-041'})
        self.assertEqual(r['statut'], 'cloture')
        self.assertIsNotNone(ProduitFiniLot.objects.get().job_clos_le)


class DestockageTests(TestCase):
    def setUp(self):
        for i, pal in enumerate(['PAL-001', 'PAL-001', 'PAL-002'], start=1):
            enregistrer_bobine(evt(f'b{i}', bobine=str(i), palette=pal, poids=10 + i))
        self.lot = cloturer_et_entrer()

    def test_totaux(self):
        bob = list(ProduitFiniBobine.objects.all())
        r = resume_bobines(bob)
        self.assertEqual((r['nb_bobines'], r['nb_restantes'], r['statut']), (3, 3, 'EN_STOCK'))
        self.assertAlmostEqual(r['kg_total'], 36.0, places=3)

    def test_destockage_palette_puis_partiel_puis_sorti(self):
        pal1 = ProduitFiniPalette.objects.get(numero_palette='PAL-001')
        mv = destocker(self.lot, palette_ids=[pal1.id], motif='BL-1')
        self.assertEqual((mv.type, mv.nb_bobines, mv.palettes_libelle), ('SORTIE', 2, 'PAL-001'))
        r = resume_bobines(list(ProduitFiniBobine.objects.all()))
        self.assertEqual((r['nb_restantes'], r['statut']), (1, 'PARTIEL'))
        destocker(self.lot, motif='BL-2')  # tout le reste
        r = resume_bobines(list(ProduitFiniBobine.objects.all()))
        self.assertEqual(r['statut'], 'SORTI')

    def test_rien_a_destocker_leve_une_erreur(self):
        destocker(self.lot)
        with self.assertRaises(ValueError):
            destocker(self.lot)

    def test_annulation_remet_en_stock(self):
        mv = destocker(self.lot, motif='erreur')
        annuler_mouvement(mv, motif='saisie erronée')
        self.assertEqual(ProduitFiniBobine.objects.filter(date_sortie__isnull=True).count(), 3)
        mv.refresh_from_db()
        self.assertTrue(mv.annule)
        with self.assertRaises(ValueError):
            annuler_mouvement(mv)

    def test_entree_ne_s_annule_pas(self):
        entree = ProduitFiniMouvement.objects.filter(type='ENTREE').first()
        with self.assertRaises(ValueError):
            annuler_mouvement(entree)


@override_settings(PESEE_SYNC_TOKEN=TOKEN)
class ApiTests(TestCase):
    url = '/api/pesee/sync/'

    def post(self, body, token=TOKEN):
        headers = {} if token is None else {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        return self.client.post(self.url, data=json.dumps(body), content_type='application/json', **headers)

    def test_sans_jeton_refuse(self):
        self.assertEqual(self.post({'evenements': []}, token=None).status_code, 401)

    def test_mauvais_jeton_refuse(self):
        self.assertEqual(self.post({'evenements': []}, token='faux').status_code, 401)

    def test_json_invalide(self):
        r = self.client.post(self.url, data='pas du json', content_type='application/json',
                             HTTP_AUTHORIZATION=f'Bearer {TOKEN}')
        self.assertEqual(r.status_code, 400)

    def test_envoi_et_doublon(self):
        r1 = self.post({'evenements': [evt('a1'), evt('a2', bobine='2')]})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual([x['statut'] for x in r1.json()['resultats']], ['creee', 'creee'])
        r2 = self.post({'evenements': [evt('a1')]})
        self.assertEqual(r2.json()['resultats'][0]['statut'], 'deja_recue')
        self.assertEqual(ProduitFiniBobine.objects.count(), 2)

    def test_trop_d_evenements_refuse(self):
        self.assertEqual(self.post({'evenements': [evt(f'x{i}') for i in range(501)]}).status_code, 400)

    def test_token_vide_donne_503(self):
        from django.test import override_settings
        with override_settings(PESEE_SYNC_TOKEN=''):
            self.assertEqual(self.post({'evenements': []}).status_code, 503)


class VueTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser('boss', 'b@x.dz', 'motdepasse-test-123')
        self.simple = User.objects.create_user('ouvrier', 'o@x.dz', 'motdepasse-test-123')
        UserModulePermission.objects.create(user=self.simple, can_access_stock=False)
        UserModulePermission.objects.create(user=self.admin, can_access_stock=True,
                                            can_access_suivi_postes=True)
        enregistrer_bobine(evt('v1'))
        cloturer_et_entrer()

    def test_anonyme_redirige(self):
        r = self.client.get(reverse('stock_produit_fini'))
        self.assertEqual(r.status_code, 302)

    def test_sans_permission_refuse(self):
        self.client.force_login(self.simple)
        r = self.client.get(reverse('stock_produit_fini'))
        self.assertEqual(r.status_code, 302)

    def test_arbre_affiche_client_lot_palette(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse('stock_produit_fini'))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('CHOR KHALED', html)
        self.assertIn('LOT-041', html)
        self.assertIn('PAL-001', html)

    def test_destockage_par_vue(self):
        self.client.force_login(self.admin)
        lot = ProduitFiniLot.objects.get()
        r = self.client.post(reverse('destocker_produit_fini', args=[lot.id]),
                             {'action': 'tout', 'motif': 'Livraison test'}, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ProduitFiniBobine.objects.filter(date_sortie__isnull=True).count(), 0)

    def test_lot_non_entre_absent_du_stock(self):
        enregistrer_bobine(evt('v2', lot='LOT-NON-ENTRE', palette='PAL-009'))
        self.client.force_login(self.admin)
        html = self.client.get(reverse('stock_produit_fini')).content.decode()
        self.assertNotIn('LOT-NON-ENTRE', html)
        self.assertIn('LOT-041', html)


class EntreeEnStockTests(TestCase):
    def setUp(self):
        Client.objects.create(name='CHOR KHALED')
        enregistrer_bobine(evt('e1'))

    def test_refus_si_job_non_termine(self):
        with self.assertRaises(ValueError):
            entrer_en_stock(ProduitFiniLot.objects.get())
        self.assertIsNone(ProduitFiniLot.objects.get().entree_stock_le)

    def test_entree_puis_refus_du_second_passage(self):
        lot = cloturer_et_entrer()
        self.assertIsNotNone(lot.entree_stock_le)
        with self.assertRaises(ValueError):
            entrer_en_stock(lot)

    def test_destockage_refuse_avant_entree(self):
        with self.assertRaises(ValueError):
            destocker(ProduitFiniLot.objects.get(), motif='test')
        self.assertEqual(ProduitFiniBobine.objects.filter(date_sortie__isnull=True).count(), 1)

    def test_vue_entree_reservee_au_suivi(self):
        User = get_user_model()
        stock_seul = User.objects.create_user('magasin', password='motdepasse-test-123')
        UserModulePermission.objects.create(user=stock_seul, can_access_stock=True)
        traiter_evenement({'type': 'JOB_CLOTURE', 'uid': 'c9', 'client_nom': 'CHOR KHALED',
                           'article': 'Couscous Moyen 1 Kg', 'numero_lot': 'LOT-041'})
        lot = ProduitFiniLot.objects.get()
        self.client.force_login(stock_seul)
        self.client.post(reverse('entrer_en_stock_produit_fini', args=[lot.id]))
        lot.refresh_from_db()
        self.assertIsNone(lot.entree_stock_le)

    def test_vue_entree_par_utilisateur_du_suivi(self):
        User = get_user_model()
        suivi = User.objects.create_user('suivi', password='motdepasse-test-123')
        UserModulePermission.objects.create(user=suivi, can_access_suivi_postes=True)
        traiter_evenement({'type': 'JOB_CLOTURE', 'uid': 'c10', 'client_nom': 'CHOR KHALED',
                           'article': 'Couscous Moyen 1 Kg', 'numero_lot': 'LOT-041'})
        lot = ProduitFiniLot.objects.get()
        self.client.force_login(suivi)
        r = self.client.post(reverse('entrer_en_stock_produit_fini', args=[lot.id]), follow=True)
        self.assertEqual(r.status_code, 200)
        lot.refresh_from_db()
        self.assertIsNotNone(lot.entree_stock_le)
        self.assertEqual(lot.entree_stock_par, 'suivi')
