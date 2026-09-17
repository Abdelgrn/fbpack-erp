from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class CategoriePiece(models.Model):
    nom = models.CharField("Nom catégorie", max_length=100)
    code = models.CharField("Code", max_length=20, unique=True)
    description = models.TextField("Description", blank=True)
    icone = models.CharField("Icône", max_length=10, default='🔩')

    class Meta:
        app_label = 'core'
        verbose_name = "Catégorie de pièce"
        verbose_name_plural = "Catégories de pièces"
        ordering = ['nom']

    def __str__(self):
        return f"{self.icone} {self.nom}"


class PieceRechange(models.Model):
    UNITE_CHOICES = [
        ('PCS', 'Pièce(s)'), ('M', 'Mètre(s)'), ('L', 'Litre(s)'),
        ('KG', 'Kilogramme(s)'), ('SET', 'Jeu / Set'),
    ]

    reference = models.CharField("Référence", max_length=100, unique=True)
    designation = models.CharField("Désignation", max_length=200)
    categorie = models.ForeignKey(CategoriePiece, on_delete=models.SET_NULL, null=True, blank=True, related_name='pieces', verbose_name="Catégorie")
    machines_compatibles = models.ManyToManyField('core.Machine', blank=True, related_name='pieces_compatibles', verbose_name="Machines compatibles")
    quantite_stock = models.FloatField("Quantité en stock", default=0)
    unite = models.CharField("Unité", max_length=5, choices=UNITE_CHOICES, default='PCS')
    stock_minimum = models.FloatField("Stock minimum (alerte)", default=1)
    stock_maximum = models.FloatField("Stock maximum", default=50)
    prix_unitaire = models.DecimalField("Prix unitaire (DA)", max_digits=12, decimal_places=2, default=0)
    fournisseur = models.ForeignKey('core.Supplier', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Fournisseur")
    delai_livraison_jours = models.IntegerField("Délai livraison (jours)", default=7)
    emplacement_stock = models.CharField("Emplacement (étagère, casier)", max_length=100, blank=True)
    marque_piece = models.CharField("Marque", max_length=100, blank=True)
    reference_fournisseur = models.CharField("Réf. fournisseur", max_length=100, blank=True)
    photo = models.ImageField("Photo", upload_to='pieces/photos/', blank=True, null=True)
    notes = models.TextField("Notes", blank=True)
    est_active = models.BooleanField("Active", default=True)
    date_creation = models.DateTimeField("Date création", auto_now_add=True, null=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Pièce de rechange"
        verbose_name_plural = "Pièces de rechange"
        ordering = ['designation']

    def __str__(self):
        return f"{self.reference} — {self.designation}"


class MouvementPiece(models.Model):
    TYPE_CHOICES = [
        ('ENTREE', 'Entrée (Achat)'), ('SORTIE', 'Sortie (Intervention)'),
        ('AJUSTEMENT', 'Ajustement inventaire'), ('RETOUR', 'Retour'),
    ]

    piece = models.ForeignKey(PieceRechange, on_delete=models.CASCADE, related_name='mouvements_piece', verbose_name="Pièce")
    type_mouvement = models.CharField("Type", max_length=15, choices=TYPE_CHOICES)
    quantite = models.FloatField("Quantité")
    date_mouvement = models.DateTimeField("Date", default=timezone.now)
    ordre_maintenance = models.ForeignKey('core.OrdreMaintenance', on_delete=models.SET_NULL, null=True, blank=True, related_name='mouvements_pieces', verbose_name="Ordre de maintenance")
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Utilisateur")
    motif = models.CharField("Motif", max_length=200, blank=True)
    notes = models.TextField("Notes", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Mouvement pièce"
        verbose_name_plural = "Mouvements pièces"
        ordering = ['-date_mouvement']

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            if self.type_mouvement in ['ENTREE', 'RETOUR']: self.piece.quantite_stock += self.quantite
            elif self.type_mouvement == 'SORTIE': self.piece.quantite_stock = max(0, self.piece.quantite_stock - self.quantite)
            elif self.type_mouvement == 'AJUSTEMENT': self.piece.quantite_stock = self.quantite
            self.piece.save(update_fields=['quantite_stock'])


class PlanMaintenancePreventive(models.Model):
    FREQUENCE_TYPE_CHOICES = [
        ('TEMPS', 'Basée sur le temps (jours)'), ('HEURES', 'Basée sur les heures machine'),
        ('METRES', 'Basée sur les mètres produits'), ('TOURS', 'Basée sur les tours/cycles'),
    ]
    STATUT_CHOICES = [('ACTIF', 'Actif'), ('INACTIF', 'Inactif'), ('SUSPENDU', 'Suspendu')]

    machine = models.ForeignKey('core.Machine', on_delete=models.CASCADE, related_name='plans_preventifs', verbose_name="Machine")
    titre = models.CharField("Titre de la tâche", max_length=200)
    description = models.TextField("Description détaillée", blank=True)
    instructions = models.TextField("Instructions / Procédure", blank=True)
    type_frequence = models.CharField("Type de fréquence", max_length=10, choices=FREQUENCE_TYPE_CHOICES, default='TEMPS')
    frequence_jours = models.IntegerField("Fréquence (jours)", default=30, null=True, blank=True)
    frequence_heures = models.FloatField("Fréquence (heures machine)", default=0, null=True, blank=True)
    frequence_metres = models.FloatField("Fréquence (mètres)", default=0, null=True, blank=True)
    frequence_tours = models.FloatField("Fréquence (tours)", default=0, null=True, blank=True)
    derniere_execution = models.DateTimeField("Dernière exécution", null=True, blank=True)
    prochaine_execution = models.DateTimeField("Prochaine exécution", null=True, blank=True)
    compteur_derniere_execution = models.FloatField("Compteur à dernière exécution", default=0)
    duree_estimee_minutes = models.IntegerField("Durée estimée (min)", default=60)
    technicien_defaut = models.ForeignKey('core.Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='plans_preventifs_assignes', verbose_name="Technicien par défaut")
    pieces_necessaires = models.ManyToManyField(PieceRechange, blank=True, related_name='plans_preventifs', verbose_name="Pièces nécessaires")
    statut = models.CharField("Statut", max_length=10, choices=STATUT_CHOICES, default='ACTIF')
    priorite = models.CharField("Priorité", max_length=10, choices=[('BASSE', 'Basse'), ('NORMALE', 'Normale'), ('HAUTE', 'Haute'), ('URGENTE', 'Urgente !!')], default='NORMALE')
    notes = models.TextField("Notes", blank=True)
    date_creation = models.DateTimeField("Date création", auto_now_add=True, null=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Plan maintenance préventive"
        verbose_name_plural = "Plans maintenance préventive"


class OrdreMaintenance(models.Model):
    TYPE_CHOICES = [
        ('CORRECTIVE', 'Corrective (Panne)'), ('PREVENTIVE', 'Préventive'),
        ('PREDICTIVE', 'Prédictive'), ('AMELIORATIVE', 'Améliorative'),
    ]
    PRIORITE_CHOICES = [('BASSE', 'Basse'), ('NORMALE', 'Normale'), ('HAUTE', 'Haute'), ('URGENTE', 'Urgente !!')]
    STATUT_CHOICES = [
        ('OUVERT', 'Ouvert'), ('EN_COURS', 'En cours'),
        ('EN_ATTENTE_PIECE', 'En attente pièce'), ('TERMINE', 'Terminé'), ('ANNULE', 'Annulé'),
    ]

    numero_om = models.CharField("N° OM", max_length=50, unique=True, blank=True)
    type_maintenance = models.CharField("Type", max_length=20, choices=TYPE_CHOICES)
    priorite = models.CharField("Priorité", max_length=10, choices=PRIORITE_CHOICES, default='NORMALE')
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='OUVERT')
    machine = models.ForeignKey('core.Machine', on_delete=models.CASCADE, related_name='ordres_maintenance', verbose_name="Machine")
    plan_preventif = models.ForeignKey(PlanMaintenancePreventive, on_delete=models.SET_NULL, null=True, blank=True, related_name='ordres_generes', verbose_name="Plan préventif source")
    titre = models.CharField("Titre / Résumé panne", max_length=200)
    description_probleme = models.TextField("Description du problème", blank=True)
    actions_realisees = models.TextField("Actions réalisées", blank=True)
    cause_racine = models.TextField("Cause racine identifiée", blank=True)
    demandeur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='om_demandes', verbose_name="Demandeur")
    technicien_principal = models.ForeignKey('core.Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='om_technicien', verbose_name="Technicien principal")
    techniciens_secondaires = models.ManyToManyField('core.Employee', blank=True, related_name='om_support', verbose_name="Techniciens support")
    date_creation = models.DateTimeField("Date création", auto_now_add=True)
    date_planifiee = models.DateTimeField("Date planifiée", null=True, blank=True)
    date_debut_intervention = models.DateTimeField("Début intervention", null=True, blank=True)
    date_fin_intervention = models.DateTimeField("Fin intervention", null=True, blank=True)
    date_cloture = models.DateTimeField("Date clôture", null=True, blank=True)
    temps_arret_minutes = models.IntegerField("Temps d'arrêt machine (min)", default=0)
    temps_intervention_minutes = models.IntegerField("Temps intervention (min)", default=0)
    cout_pieces = models.DecimalField("Coût pièces (DA)", max_digits=12, decimal_places=2, default=0)
    cout_main_oeuvre = models.DecimalField("Coût main d'œuvre (DA)", max_digits=12, decimal_places=2, default=0)
    cout_externe = models.DecimalField("Coût intervention externe (DA)", max_digits=12, decimal_places=2, default=0)
    rapport = models.FileField("Rapport d'intervention", upload_to='maintenance/rapports/', blank=True, null=True)
    photos_avant = models.ImageField("Photos avant", upload_to='maintenance/photos/', blank=True, null=True)
    photos_apres = models.ImageField("Photos après", upload_to='maintenance/photos_apres/', blank=True, null=True)
    notes = models.TextField("Notes", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Ordre de maintenance"
        verbose_name_plural = "Ordres de maintenance"
        ordering = ['-date_creation']

    def __str__(self):
        return f"OM-{self.numero_om} | {self.machine.name}"


class ConsommationPiece(models.Model):
    ordre_maintenance = models.ForeignKey(OrdreMaintenance, on_delete=models.CASCADE, related_name='consommations_pieces', verbose_name="Ordre de maintenance")
    piece = models.ForeignKey(PieceRechange, on_delete=models.CASCADE, related_name='consommations_piece', verbose_name="Pièce")
    quantite = models.FloatField("Quantité utilisée", default=1)
    date_consommation = models.DateTimeField("Date", default=timezone.now)
    notes = models.TextField("Notes", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Consommation pièce"
        verbose_name_plural = "Consommations pièces"


class AlerteMaintenance(models.Model):
    TYPE_CHOICES = [
        ('PREVENTIVE_DUE', 'Maintenance préventive à faire'),
        ('PANNE', 'Panne machine'),
        ('STOCK_PIECE_BAS', 'Stock pièce bas'),
        ('STOCK_PIECE_RUPTURE', 'Rupture stock pièce'),
        ('COMPTEUR_SEUIL', 'Seuil compteur atteint'),
        ('OM_EN_RETARD', 'OM en retard'),
    ]
    NIVEAU_CHOICES = [('INFO', 'Information'), ('WARNING', 'Avertissement'), ('CRITICAL', 'Critique')]

    type_alerte = models.CharField("Type", max_length=25, choices=TYPE_CHOICES)
    niveau = models.CharField("Niveau", max_length=10, choices=NIVEAU_CHOICES, default='WARNING')
    titre = models.CharField("Titre", max_length=200)
    message = models.TextField("Message")
    machine = models.ForeignKey('core.Machine', on_delete=models.CASCADE, null=True, blank=True, related_name='alertes', verbose_name="Machine")
    piece = models.ForeignKey(PieceRechange, on_delete=models.CASCADE, null=True, blank=True, related_name='alertes', verbose_name="Pièce")
    plan_preventif = models.ForeignKey(PlanMaintenancePreventive, on_delete=models.CASCADE, null=True, blank=True, related_name='alertes', verbose_name="Plan préventif")
    date_creation = models.DateTimeField("Date création", auto_now_add=True)
    est_lue = models.BooleanField("Lue", default=False)
    est_traitee = models.BooleanField("Traitée", default=False)
    date_traitement = models.DateTimeField("Date traitement", null=True, blank=True)
    traite_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Traité par")

    class Meta:
        app_label = 'core'
        verbose_name = "Alerte maintenance"
        verbose_name_plural = "Alertes maintenance"
        ordering = ['-date_creation']