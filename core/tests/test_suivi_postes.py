"""Tests du suivi par poste (extrudeuse, découpes) et du cloisonnement des palettes par poste."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Client, TechnicalProduct, UserModulePermission
from core.models.stock_produit_fini import ProduitFiniBobine, ProduitFiniLot, ProduitFiniPalette
from core.services.produit_fini import enregistrer_bobine, traiter_evenement
from core.services.suivi_postes import (
    MACHINES, POSTE_VIDE, construire_arbre, liste_postes, lots_par_numero, palettes_a_plat, totaux,
    totaux_par_machine,
)


def evt(uid, poste, palette='PAL-001', bobine='1', poids=10.0, heure='2026-10-19 10:00:00',
        client='CHOR KHALED', article='Couscous Moyen 1 Kg', lot='LOT-041'):
    return {
        'type': 'BOBINE', 'uid': uid, 'poste': poste, 'client_nom': client, 'article': article,
        'numero_lot': lot, 'numero_palette': palette, 'numero_bobine': bobine,
        'poids_kg': poids, 'date_heure': heure, 'operateur': 'Ali', 'equipe': 'A', 'statut': 'ok',
    }


class CloisonnementParPosteTests(TestCase):
    def setUp(self):
        Client.objects.create(name='CHOR KHALED')

    def test_meme_numero_palette_sur_deux_postes_donne_deux_palettes(self):
        enregistrer_bobine(evt('a1', 'Extrudeuse', palette='PAL-001'))
        enregistrer_bobine(evt('b1', 'Découpe grande', palette='PAL-001'))
        self.assertEqual(ProduitFiniPalette.objects.filter(numero_palette='PAL-001').count(), 2)
        self.assertEqual(ProduitFiniBobine.objects.count(), 2)

    def test_meme_poste_et_palette_reste_une_seule_palette(self):
        enregistrer_bobine(evt('a1', 'Extrudeuse', palette='PAL-001', bobine='1'))
        enregistrer_bobine(evt('a2', 'Extrudeuse', palette='PAL-001', bobine='2'))
        self.assertEqual(ProduitFiniPalette.objects.count(), 1)
        self.assertEqual(ProduitFiniBobine.objects.count(), 2)

    def test_poste_absent_donne_palette_sans_poste(self):
        p = dict(evt('x1', ''))
        del p['poste']
        enregistrer_bobine(p)
        self.assertEqual(ProduitFiniPalette.objects.get().poste, '')


class ArbrePosteTests(TestCase):
    def setUp(self):
        Client.objects.create(name='CHOR KHALED')
        Client.objects.create(name='SULTANA')
        enregistrer_bobine(evt('a1', 'Extrudeuse', poids=20.0))
        enregistrer_bobine(evt('a2', 'Extrudeuse', bobine='2', poids=30.0))
        enregistrer_bobine(evt('b1', 'Découpe grande', palette='PAL-001', poids=5.0))
        enregistrer_bobine(evt('c1', 'Découpe petite', palette='PAL-001', poids=2.5,
                               client='SULTANA', article='Sultana 1', lot='LOT-077'))

    def test_postes_listes(self):
        self.assertEqual(liste_postes(), MACHINES)

    def test_les_trois_machines_affichees_meme_sans_pesee(self):
        ProduitFiniPalette.objects.all().delete()
        ProduitFiniBobine.objects.all().delete()
        self.assertEqual([p['nom'] for p in construire_arbre()], MACHINES)
        self.assertEqual(totaux(construire_arbre())['nb_bobines'], 0)

    def test_filtre_machine_vide_montre_seulement_elle(self):
        ProduitFiniPalette.objects.filter(poste='Découpe petite').delete()
        arbre = construire_arbre(poste='Découpe petite')
        self.assertEqual([p['nom'] for p in arbre], ['Découpe petite'])
        self.assertEqual(arbre[0]['clients'], [])

    def test_totaux_par_poste(self):
        arbre = construire_arbre()
        par_nom = {p['nom']: p for p in arbre}
        self.assertEqual(par_nom['Extrudeuse']['res']['nb_bobines'], 2)
        self.assertAlmostEqual(par_nom['Extrudeuse']['res']['kg'], 50.0)
        self.assertAlmostEqual(totaux(arbre)['kg'], 57.5)
        self.assertEqual(totaux(arbre)['nb_bobines'], 4)

    def test_filtre_par_poste(self):
        arbre = construire_arbre(poste='Découpe grande')
        self.assertEqual([p['nom'] for p in arbre], ['Découpe grande'])
        self.assertEqual(arbre[0]['clients'][0]['res']['nb_bobines'], 1)

    def test_filtre_recherche_client(self):
        arbre = construire_arbre(recherche='sultana')
        self.assertEqual(totaux(arbre)['nb_bobines'], 1)

    def test_palette_sans_poste_affichee_comme_non_renseigne(self):
        enregistrer_bobine(evt('z1', '', palette='PAL-900', lot='LOT-999'))
        noms = [p['nom'] for p in construire_arbre(poste=POSTE_VIDE)]
        self.assertEqual(noms, [POSTE_VIDE])


class VueSuiviPostesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user('chef', password='x-test-123')
        UserModulePermission.objects.create(user=self.user, can_access_suivi_postes=True)
        Client.objects.create(name='CHOR KHALED')
        enregistrer_bobine(evt('a1', 'Extrudeuse', poids=20.0))

    def test_acces_refuse_sans_permission(self):
        other = get_user_model().objects.create_user('visiteur', password='x-test-123')
        self.client.force_login(other)
        resp = self.client.get(reverse('suivi_postes'))
        self.assertEqual(resp.status_code, 302)

    def test_permission_stock_seule_ne_donne_pas_le_suivi(self):
        magasin = get_user_model().objects.create_user('magasin', password='x-test-123')
        UserModulePermission.objects.create(user=magasin, can_access_stock=True)
        self.client.force_login(magasin)
        resp = self.client.get(reverse('suivi_postes'))
        self.assertEqual(resp.status_code, 302)

    def test_bouton_entree_seulement_quand_job_termine(self):
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(reverse('suivi_postes')), 'Entrer en stock produit fini')
        traiter_evenement({'type': 'JOB_CLOTURE', 'uid': 'fin1', 'client_nom': 'CHOR KHALED',
                           'article': 'Couscous Moyen 1 Kg', 'numero_lot': 'LOT-041'})
        resp = self.client.get(reverse('suivi_postes'))
        self.assertContains(resp, 'Entrer en stock produit fini')
        self.assertContains(resp, 'à entrer en stock')

    def test_entree_depuis_le_suivi(self):
        traiter_evenement({'type': 'JOB_CLOTURE', 'uid': 'fin2', 'client_nom': 'CHOR KHALED',
                           'article': 'Couscous Moyen 1 Kg', 'numero_lot': 'LOT-041'})
        lot = ProduitFiniLot.objects.get()
        self.client.force_login(self.user)
        resp = self.client.post(reverse('entrer_en_stock_produit_fini', args=[lot.id]), follow=True)
        self.assertContains(resp, 'entré en stock produit fini')
        lot.refresh_from_db()
        self.assertIsNotNone(lot.entree_stock_le)
        self.assertContains(self.client.get(reverse('suivi_postes')), 'en stock produit fini')

    def test_page_affiche_arbre_et_filtres(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('suivi_postes'), {'poste': 'Extrudeuse'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Extrudeuse')
        self.assertContains(resp, 'CHOR KHALED')
        self.assertContains(resp, 'LOT-041')

    def test_page_montre_les_machines_sans_pesee(self):
        ProduitFiniBobine.objects.all().delete()
        self.client.force_login(self.user)
        resp = self.client.get(reverse('suivi_postes'))
        for machine in MACHINES:
            self.assertContains(resp, machine)
        self.assertContains(resp, 'Aucune pesée sur cette machine')

    def test_page_vide_ne_plante_pas(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('suivi_postes'), {'poste': 'Inexistant'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Aucune pesée')


class VuePaletteEtTuilesTests(TestCase):
    def setUp(self):
        Client.objects.create(name='CHOR KHALED')
        enregistrer_bobine(evt('p1', 'Extrudeuse', palette='PAL-001', bobine='1', poids=20.0))
        enregistrer_bobine(evt('p2', 'Extrudeuse', palette='PAL-001', bobine='2', poids=30.0))
        enregistrer_bobine(evt('p3', 'Découpe grande', palette='PAL-002', poids=5.0))
        User = get_user_model()
        self.user = User.objects.create_user('chef2', password='x-test-123')
        UserModulePermission.objects.create(user=self.user, can_access_suivi_postes=True)

    def test_palette_a_plat_regroupe_les_bobines(self):
        lignes = palettes_a_plat()
        par_num = {l['numero']: l for l in lignes}
        self.assertEqual(par_num['PAL-001']['nb_bobines'], 2)
        self.assertAlmostEqual(par_num['PAL-001']['kg'], 50.0)
        self.assertAlmostEqual(par_num['PAL-001']['moy'], 25.0)
        self.assertEqual(par_num['PAL-002']['machine'], 'Découpe grande')

    def test_totaux_par_machine_donne_les_trois_machines(self):
        t = {x['nom']: x['res'] for x in totaux_par_machine()}
        self.assertEqual(list(t), MACHINES)
        self.assertEqual(t['Extrudeuse']['nb_bobines'], 2)
        self.assertEqual(t['Découpe petite']['nb_bobines'], 0)

    def test_vue_palettes_affiche_une_ligne_par_palette(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('suivi_postes'), {'vue': 'palettes'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Poids total (kg)')
        self.assertContains(resp, 'PAL-001')
        self.assertContains(resp, 'PAL-002')

    def test_tuiles_gardent_les_filtres(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('suivi_postes'), {'q': 'CHOR', 'vue': 'palettes'})
        self.assertContains(resp, 'poste=Extrudeuse')
        self.assertContains(resp, 'q=CHOR')

    def test_clic_machine_ne_montre_que_cette_machine(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('suivi_postes'), {'poste': 'Découpe grande'})
        self.assertContains(resp, 'PAL-002')
        self.assertNotContains(resp, 'PAL-001')


class VueParNumeroDeLotTests(TestCase):
    def setUp(self):
        Client.objects.create(name='CHOR KHALED')
        # Même numéro de lot, deux machines : c'est le cas d'un job qui passe par plusieurs postes
        enregistrer_bobine(evt('l1', 'Extrudeuse', palette='PAL-001', bobine='1', poids=20.0, lot='LOT-041'))
        enregistrer_bobine(evt('l2', 'Découpe grande', palette='PAL-010', bobine='2', poids=7.0, lot='LOT-041'))
        enregistrer_bobine(evt('l3', 'Extrudeuse', palette='PAL-002', bobine='3', poids=9.0, lot='LOT-099'))
        User = get_user_model()
        self.user = User.objects.create_user('chef3', password='x-test-123')
        UserModulePermission.objects.create(user=self.user, can_access_suivi_postes=True)

    def test_un_numero_de_lot_regroupe_toutes_les_machines(self):
        groupes = {g['numero_lot']: g for g in lots_par_numero()}
        self.assertEqual(set(groupes), {'LOT-041', 'LOT-099'})
        g = groupes['LOT-041']
        self.assertEqual(g['res']['nb_bobines'], 2)
        self.assertAlmostEqual(g['res']['kg'], 27.0)
        machines = {m['nom']: m['res']['kg'] for m in g['par_machine']}
        self.assertAlmostEqual(machines['Extrudeuse'], 20.0)
        self.assertAlmostEqual(machines['Découpe grande'], 7.0)
        self.assertEqual(sorted(p['numero'] for p in g['palettes']), ['PAL-001', 'PAL-010'])

    def test_page_vue_lots(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('suivi_postes'), {'vue': 'lots'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Lot LOT-041')
        self.assertContains(resp, 'Répartition par machine')
        self.assertContains(resp, 'Aucun ordre de fabrication relié')

    def test_onglet_numero_de_lot_present(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('suivi_postes'))
        self.assertContains(resp, 'Vue par numéro de lot')
        self.assertContains(resp, 'Vue par client')
        self.assertContains(resp, 'Vue palettes')

    def test_of_relie_au_numero_de_lot(self):
        """Quand un OF porte le même numéro de lot, la vue le relie (simulé, sans modèle OF ici)."""
        from unittest import mock
        from core.services import suivi_postes as svc

        class FauxOF:
            id = 7
            numero_of = 'OF-2026-007'
            client = 'CHOR KHALED'
            produit = 'Couscous Moyen 1 Kg'

            def get_statut_display(self):
                return 'En cours'

        class FauxModele:
            @staticmethod
            def chercher_par_lot(numero):
                return FauxOF() if numero == 'LOT-041' else None

        with mock.patch.object(svc.apps, 'get_model', return_value=FauxModele):
            groupes = {g['numero_lot']: g for g in lots_par_numero()}
        self.assertEqual(groupes['LOT-041']['of']['numero'], 'OF-2026-007')
        self.assertIsNone(groupes['LOT-099']['of'])


class AffichageMachineTests(TestCase):
    """Quand une machine est choisie dans les filtres, les tuiles du haut la nomment déjà :
    le bloc machine n'est pas répété. En « Toutes les machines », il reste (un niveau par machine)."""

    def setUp(self):
        Client.objects.create(name='CHOR KHALED')
        enregistrer_bobine(evt('a1', 'Extrudeuse', palette='PAL-001', bobine='1', poids=20.0, lot='LOT-041'))
        User = get_user_model()
        self.user = User.objects.create_user('chef4', password='x-test-123')
        UserModulePermission.objects.create(user=self.user, can_access_suivi_postes=True)
        self.client.force_login(self.user)

    def test_machine_choisie_sans_bloc_repete(self):
        resp = self.client.get(reverse('suivi_postes'), {'poste': 'Découpe petite'})
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Aucune pesée sur cette machine')
        self.assertContains(resp, 'Aucune pesée pour ces filtres.')
        self.assertNotContains(resp, '<summary class="cursor-pointer font-black text-xl">\n        🏭 Découpe petite')

    def test_machine_choisie_affiche_ses_clients(self):
        resp = self.client.get(reverse('suivi_postes'), {'poste': 'Extrudeuse'})
        self.assertContains(resp, 'CHOR KHALED')
        self.assertNotContains(resp, 'Aucune pesée pour ces filtres.')

    def test_toutes_les_machines_garde_le_niveau_machine(self):
        resp = self.client.get(reverse('suivi_postes'))
        self.assertContains(resp, 'Aucune pesée sur cette machine pour ces filtres.')
        self.assertContains(resp, 'CHOR KHALED')

