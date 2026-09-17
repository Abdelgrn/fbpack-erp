import datetime
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta

class FicheProductionJournaliere(models.Model):
    TYPE_FICHE_CHOICES = [
        ('EXTRUSION', "Fiche Fabrication Journalière d'Extrusion"),
        ('FLEXO', 'Fiche Impression Journalière FLEXO'),
        ('HELIO', 'Fiche Impression Journalière HÉLIO'),
        ('COMPLEXAGE', 'Fiche Journalière Complexage (Duplex/Triplex)'),
        ('FONDS_CARRES', 'Fiche Fabrication Fonds Carrés'),
        ('DECOUPE', 'Fiche Journalière Découpe 1'),
        ('DECOUPE2', 'Fiche Journalière Découpe 2'),
    ]
    POSTE_CHOICES = [('NUIT', 'Nuit'), ('MATIN', 'Matin'), ('SOIR', 'Soir')]
    EQUIPE_CHOICES = [('A', 'Équipe A'), ('B', 'Équipe B'), ('C', 'Équipe C')]

    type_fiche = models.CharField("Type de Fiche", max_length=20, choices=TYPE_FICHE_CHOICES, default='FLEXO')
    numero_fiche = models.CharField("N° Fiche", max_length=50, blank=True, unique=True)
    numero_doc = models.CharField("N° Doc / Lot de commande", max_length=100, blank=True, db_index=True)
    numero_lot = models.CharField("N° Lot (Traçabilité ERP)", max_length=100, blank=True, db_index=True)
    date_fabrication = models.DateField("Date de Fabrication", default=timezone.now)
    heure_debut = models.TimeField("Heure Début", null=True, blank=True)
    heure_fin = models.TimeField("Heure Fin", null=True, blank=True)
    poste = models.CharField("Poste", max_length=10, choices=POSTE_CHOICES, default='MATIN')
    equipe = models.CharField("N° Équipe", max_length=5, choices=EQUIPE_CHOICES, default='A')

    machine = models.ForeignKey('core.Machine', on_delete=models.SET_NULL, null=True, blank=True, related_name='fiches_journalieres', verbose_name="Machine")
    conducteur = models.CharField("Conducteur / Opérateur", max_length=150, blank=True)
    aide_conducteur_1 = models.CharField("Aide Conducteur 1", max_length=150, blank=True)
    aide_conducteur_2 = models.CharField("Aide Conducteur 2", max_length=150, blank=True)
    chef_de_quart = models.CharField("Chef de Quart", max_length=150, blank=True)

    client = models.ForeignKey('core.Client', on_delete=models.SET_NULL, null=True, blank=True, related_name='fiches_journalieres', verbose_name="Client / Motif")
    designation_produit = models.CharField("Désignation du produit / Motif", max_length=250, blank=True)
    support = models.CharField("Support", max_length=150, blank=True)
    couleur = models.CharField("Couleur", max_length=100, blank=True)
    epaisseur_um = models.FloatField("Épaisseur (μm)", default=0, null=True, blank=True)
    laize_mm = models.FloatField("Laize (mm)", default=0, null=True, blank=True)
    qte_programmee = models.FloatField("Qté Programmée (Qp) / Commandée", default=0, null=True, blank=True)
    nbr_rouleaux_programmes = models.IntegerField("Nbr. Rouleaux Programmés", default=0, null=True, blank=True)

    t_preparation_min = models.FloatField("T préparation commande (min)", default=0, null=True, blank=True)
    t_fonctionnement_min = models.FloatField("T Fonctionnement (min)", default=0, null=True, blank=True)
    t_nettoyage_min = models.FloatField("T Nettoyage (min)", default=0, null=True, blank=True)
    vitesse_machine = models.FloatField("Vitesse Machine (m/min)", default=0, null=True, blank=True)
    debit_production_kghr = models.FloatField("Débit Production (Kg/hr)", default=0, null=True, blank=True)

    poids_mandrin_kg = models.FloatField("Poids du mandrin (kg)", default=0, null=True, blank=True)
    mandrin_longueur_mm = models.FloatField("Longueur Mandrin (mm)", default=0, null=True, blank=True)
    mandrin_epaisseur_mm = models.FloatField("Épaisseur Mandrin (mm)", default=0, null=True, blank=True)

    dechet_bloc_b = models.FloatField("Déchet Bloc B (kg)", default=0, null=True, blank=True)
    dechet_b_demarrage_r = models.FloatField("B. Démarrage + R (kg)", default=0, null=True, blank=True)
    dechet_film = models.FloatField("Déchet Film (kg)", default=0, null=True, blank=True)
    dechet_purge = models.FloatField("Purge (kg)", default=0, null=True, blank=True)
    dechet_lisiere = models.FloatField("Lisière (kg)", default=0, null=True, blank=True)
    total_dechets_kg = models.FloatField("Total Déchets (kg)", default=0, null=True, blank=True)
    total_qte_lancee = models.FloatField("Total Qté Lancée (kg)", default=0, null=True, blank=True)

    reste_bobines_dr1 = models.FloatField("Reste Bobines DR1", default=0, null=True, blank=True)
    reste_bobines_dr2 = models.FloatField("Reste Bobines DR2", default=0, null=True, blank=True)
    durcisseur_ref = models.CharField("Référence Colle / Durcisseur", max_length=100, blank=True)
    durcisseur_poids = models.FloatField("Poids/Qté Durcisseur (kg)", default=0, null=True, blank=True)
    resine_ref = models.CharField("Référence Résine", max_length=100, blank=True)
    resine_poids = models.FloatField("Poids/Qté Résine (kg)", default=0, null=True, blank=True)
    solvant_ref = models.CharField("Référence Solvant", max_length=100, blank=True)
    solvant_poids = models.FloatField("Poids/Qté Solvant (kg)", default=0, null=True, blank=True)

    total_bobines_filles = models.IntegerField("Total Bobines Filles", default=0, null=True, blank=True)
    total_metrage_ml = models.FloatField("Total Métrage (ML)", default=0, null=True, blank=True)
    total_poids_produit_kg = models.FloatField("Total Poids Produit (kg)", default=0, null=True, blank=True)
    etiquettes_pos = models.CharField("Étiquettes Pos.", max_length=100, blank=True)

    autocontrole_laize = models.CharField("Autocontrôle Laize", max_length=100, blank=True)
    autocontrole_epaisseur = models.CharField("Autocontrôle Épaisseur", max_length=100, blank=True)
    autocontrole_aspect_visuel = models.CharField("Autocontrôle Aspect Visuel", max_length=100, blank=True)
    autocontrole_autres = models.TextField("Autocontrôle Autres", blank=True)
    observations = models.TextField("Observations et Remarques", blank=True)
    visa_resp_production = models.CharField("Visa Responsable Production", max_length=100, blank=True)
    visa_qualite = models.CharField("Visa C. Qualité", max_length=100, blank=True)
    ok_demarrage = models.CharField("OK Démarrage", max_length=100, blank=True)

    of_lie = models.ForeignKey(
        'core.OrdreFabrication', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fiches_journalieres', verbose_name="OF lié"
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='fiches_creees')

    class Meta:
        app_label = 'core'
        verbose_name = "Fiche de Production Journalière"
        verbose_name_plural = "Fiches de Production Journalières"
        ordering = ['-date_fabrication', '-heure_debut']

    def __str__(self):
        return f"{self.get_type_fiche_display()} N°{self.numero_fiche or self.id} ({self.date_fabrication})"

    def save(self, *args, **kwargs):
        if not self.numero_fiche:
            annee = timezone.now().year
            prefix_map = {
                'EXTRUSION': 'FEXT', 'FLEXO': 'FFLX', 'HELIO': 'FHEL',
                'COMPLEXAGE': 'FCPX', 'FONDS_CARRES': 'FFCR',
                'DECOUPE': 'FDEC', 'DECOUPE2': 'FDEC2',
            }
            prefix = prefix_map.get(self.type_fiche, 'FICH')
            last = FicheProductionJournaliere.objects.filter(numero_fiche__startswith=f"{prefix}{annee}").order_by('-numero_fiche').first()
            if last and last.numero_fiche:
                try: num = int(last.numero_fiche.replace(f"{prefix}{annee}-", '')) + 1
                except (ValueError, IndexError): num = 1
            else: num = 1
            self.numero_fiche = f"{prefix}{annee}-{num:04d}"
        
        if not self.of_lie and self.numero_lot:
            OrdreFabrication = models.apps.get_model('core', 'OrdreFabrication')
            of = OrdreFabrication.chercher_par_lot(self.numero_lot)
            if of:
                self.of_lie = of
                if not self.client: self.client = of.client
                if not self.designation_produit: self.designation_produit = str(of.produit) if of.produit else ''
                if not self.support: self.support = of.support or ''
        
        if self.of_lie and not self.numero_lot:
            self.numero_lot = self.of_lie.numero_lot
        
        if not self.numero_doc and self.numero_lot:
            self.numero_doc = self.numero_lot
        
        super().save(*args, **kwargs)

    @property
    def temps_ouverture_minutes(self):
        if self.heure_debut and self.heure_fin:
            dt_debut = datetime.datetime.combine(self.date_fabrication, self.heure_debut)
            dt_fin = datetime.datetime.combine(self.date_fabrication, self.heure_fin)
            if dt_fin < dt_debut: dt_fin += timedelta(days=1)
            return (dt_fin - dt_debut).total_seconds() / 60
        return 0

    @property
    def total_prod_kg_calcul(self):
        if self.type_fiche == 'EXTRUSION':
            return sum(m.qte_realisee_net_kg for m in self.matieres_extrusion.all())
        elif self.type_fiche in ['FLEXO', 'HELIO']:
            return sum(b.poids_kg for b in self.bobines_imprimees.all())
        elif self.type_fiche == 'COMPLEXAGE':
            return sum(e.poids_kg for e in self.enrouleur_items.all())
        elif self.type_fiche in ['DECOUPE', 'DECOUPE2']:
            return sum(b.poids_filles_kg for b in self.bobines_filles_decoupe.all())
        elif self.type_fiche == 'FONDS_CARRES':
            return sum(e.poids_sacs_kg for e in self.fonds_carres_equipes.all())
        return 0

    @property
    def taux_dechets_calcul(self):
        prod = self.total_prod_kg_calcul
        if prod <= 0: return 0
        return round((self.total_dechets_kg or 0) / prod * 100, 2)


class FicheExtrusionMatiere(models.Model):
    fiche = models.ForeignKey(FicheProductionJournaliere, on_delete=models.CASCADE, related_name='matieres_extrusion')
    designation = models.CharField("Désignation Matière", max_length=150)
    num_lot_mp = models.CharField("N° Lot MP", max_length=100, blank=True)
    poids_mp_kg = models.FloatField("Poids MP (Kg)", default=0)
    qte_realisee_net_kg = models.FloatField("Quantité Réalisée Nette (Qr Kg)", default=0)
    metrage_m = models.FloatField("Métrage", default=0)
    qte_realisee_nbr_bobines = models.IntegerField("Nbre Bobines", default=0)

    class Meta:
        app_label = 'core'


class FicheExtrusionArret(models.Model):
    CODE_CHOICES = [
        ('T01', 'T01 - Panne E / M'), ('T01B', 'T01 - Chute de tension'),
        ('T02', 'T02 - Rupture Bulle'), ('T03', 'T03 - Changement commande'),
        ('T04', 'T04 - Essais / Échantillon'), ('T05', 'T05 - Problème MP'),
        ('T06', 'T06 - Manque commande'), ('T07', 'T07 - Nettoyage filière'),
        ('T08', 'T08 - Planning Préventif'), ('T09', 'T09 - Temps de préparation'),
        ('T10', 'T10 - Panne N° DI'), ('T11', 'T11 - Divers'),
    ]
    fiche = models.ForeignKey(FicheProductionJournaliere, on_delete=models.CASCADE, related_name='arrets_extrusion')
    code_arret = models.CharField("Code", max_length=10, choices=CODE_CHOICES)
    nature_arret = models.CharField("Nature d'arrêt", max_length=200, blank=True)
    temps_min = models.IntegerField("Temps (min)", default=0)

    class Meta:
        app_label = 'core'


class FicheImpressionBobineEntree(models.Model):
    fiche = models.ForeignKey(FicheProductionJournaliere, on_delete=models.CASCADE, related_name='bobines_entrees')
    num_ordre = models.IntegerField("N° Ordre", default=1)
    num_lot_mp = models.CharField("N° Lot MP (Batch number)", max_length=100, blank=True)
    num_bobine = models.CharField("N° Bobine (Roll number)", max_length=100, blank=True)
    fournisseur = models.CharField("Fournisseur", max_length=150, blank=True)
    metrage_m = models.FloatField("Métrage", default=0)
    poids_kg = models.FloatField("Poids (Kg)", default=0)
    dechets_neutre_kg = models.FloatField("Déchets Neutre (Kg)", default=0)

    class Meta:
        app_label = 'core'


class FicheImpressionBobineImprimee(models.Model):
    fiche = models.ForeignKey(FicheProductionJournaliere, on_delete=models.CASCADE, related_name='bobines_imprimees')
    num_ordre = models.IntegerField("N° Ordre", default=1)
    nbre_bobines = models.IntegerField("Nbre Bobines", default=1)
    poids_kg = models.FloatField("Poids (Kg)", default=0)
    metrage_m = models.FloatField("Métrage", default=0)
    dechet_imprime_kg = models.FloatField("Déchet impr (Kg)", default=0)
    observations = models.CharField("Observations & Remarques", max_length=250, blank=True)

    class Meta:
        app_label = 'core'


class FicheImpressionEncreGroupe(models.Model):
    fiche = models.ForeignKey(FicheProductionJournaliere, on_delete=models.CASCADE, related_name='encres_groupes')
    groupe_numero = models.IntegerField("Groupe N° (1 à 8)")
    designation_encre = models.CharField("Désignation / Couleur Encre", max_length=150, blank=True)
    code_encre = models.CharField("Code Encre / Référence", max_length=100, blank=True)
    viscosite_sec = models.FloatField("Viscosité (sec)", default=0, null=True, blank=True)
    poids_debut_kg = models.FloatField("Poids début (Kg)", default=0)
    poids_fin_kg = models.FloatField("Poids fin (Kg)", default=0)
    conso_encre_kg = models.FloatField("Consommation Encre (Kg)", default=0)
    conso_solvant_kg = models.FloatField("Consommation Solvant (Kg)", default=0)

    class Meta:
        app_label = 'core'
        ordering = ['groupe_numero']
        unique_together = ['fiche', 'groupe_numero']


class FicheComplexageDerouleur1(models.Model):
    fiche = models.ForeignKey(FicheProductionJournaliere, on_delete=models.CASCADE, related_name='derouleur1_items')
    num_ordre = models.IntegerField("N° Ordre", default=1)
    num_lot_mp = models.CharField("N° Lot MP", max_length=100, blank=True)
    num_bobine = models.CharField("N° Bobine", max_length=100, blank=True)
    poids_kg = models.FloatField("Poids (Kg)", default=0)
    ml = models.FloatField("ML", default=0)
    dechets_kg = models.FloatField("Déchets (Kg)", default=0)

    class Meta:
        app_label = 'core'


class FicheComplexageDerouleur2(models.Model):
    fiche = models.ForeignKey(FicheProductionJournaliere, on_delete=models.CASCADE, related_name='derouleur2_items')
    num_ordre = models.IntegerField("N° Ordre", default=1)
    num_lot_mp = models.CharField("N° Lot MP", max_length=100, blank=True)
    num_bobine = models.CharField("N° Bobine", max_length=100, blank=True)
    poids_kg = models.FloatField("Poids (Kg)", default=0)
    ml = models.FloatField("ML", default=0)
    dechets_kg = models.FloatField("Déchets (Kg)", default=0)

    class Meta:
        app_label = 'core'


class FicheComplexageEnrouleur(models.Model):
    fiche = models.ForeignKey(FicheProductionJournaliere, on_delete=models.CASCADE, related_name='enrouleur_items')
    num_ordre = models.IntegerField("N° Ordre", default=1)
    num_lot = models.CharField("N° Lot", max_length=100, blank=True)
    poids_kg = models.FloatField("Poids (Kg)", default=0)
    ml = models.FloatField("ML", default=0)
    dechets_kg = models.FloatField("Déchets (Kg)", default=0)

    class Meta:
        app_label = 'core'


class FicheFondCarreEquipe(models.Model):
    SHIFT_CHOICES = [('08_16', '08h - 16h'), ('16_00', '16h - 00h'), ('00_08', '00h - 08h')]
    fiche = models.ForeignKey(FicheProductionJournaliere, on_delete=models.CASCADE, related_name='fonds_carres_equipes')
    equipe_num = models.IntegerField("Équipe N° (1, 2 ou 3)")
    shift_code = models.CharField("Shift", max_length=10, choices=SHIFT_CHOICES, default='08_16')
    date_fabrication = models.DateField("Date", default=timezone.now)
    num_equipe = models.CharField("N° Equipe", max_length=50, blank=True)
    operateur = models.CharField("Opérateur", max_length=100, blank=True)
    aide_operateur = models.CharField("Aide Opérateur", max_length=100, blank=True)
    debut_pro = models.TimeField("Début Prod", null=True, blank=True)
    fin_pro = models.TimeField("Fin Prod", null=True, blank=True)
    fournisseur_mp = models.CharField("Fournisseur MP", max_length=100, blank=True)
    matiere_nature = models.CharField("Matière (Nature)", max_length=100, blank=True)
    grm2 = models.FloatField("gr/m2", default=0)
    laize = models.FloatField("Laize", default=0)
    metre_l_initial = models.FloatField("Mètre L Initial", default=0)
    poids_initial_kg = models.FloatField("Poids I (Kg)", default=0)
    metre_l_decoupe = models.FloatField("Mètre L Découpe", default=0)
    nb_sacs = models.IntegerField("NB Sacs", default=0)
    poids_sacs_kg = models.FloatField("Poids Sacs (Kg)", default=0)
    dechets_sacs_kg = models.FloatField("Déchets Sacs (Kg)", default=0)
    dechets_bob_kg = models.FloatField("Déchets Bob (Kg)", default=0)
    restes_bob_kg = models.FloatField("Restes Bob (Kg)", default=0)
    observation = models.TextField("Observation", blank=True)

    class Meta:
        app_label = 'core'


class FicheDecoupeBobineMere(models.Model):
    fiche = models.ForeignKey(FicheProductionJournaliere, on_delete=models.CASCADE, related_name='bobines_meres_decoupe')
    num_ordre = models.IntegerField("N° Ordre", default=1)
    reference_lot = models.CharField("Référence / N° Lot", max_length=100, blank=True)
    poids_kg = models.FloatField("Poids (Kg)", default=0)
    metrage_ml = models.FloatField("Métrage (ML)", default=0)

    class Meta:
        app_label = 'core'


class FicheDecoupeBobineFille(models.Model):
    fiche = models.ForeignKey(FicheProductionJournaliere, on_delete=models.CASCADE, related_name='bobines_filles_decoupe')
    num_ordre = models.IntegerField("N° Ordre", default=1)
    nombre_filles = models.IntegerField("Nombre Filles", default=0)
    poids_filles_kg = models.FloatField("Poids Filles (Kg)", default=0)
    nombre_a_reviser = models.IntegerField("Nombre à réviser", default=0)
    poids_a_reviser_kg = models.FloatField("Poids à réviser (Kg)", default=0)
    dechets_demarrage_kg = models.FloatField("Déchets Démarrage (Kg)", default=0)
    dechets_lisiere_kg = models.FloatField("Déchets Lisière (Kg)", default=0)
    dechets_jonction_kg = models.FloatField("Déchets Jonction (Kg)", default=0)
    dechets_transport_kg = models.FloatField("Déchets Transport (Kg)", default=0)
    rouleaux_non_conforme_kg = models.FloatField("Rouleaux Non Conforme (Kg)", default=0)

    class Meta:
        app_label = 'core'