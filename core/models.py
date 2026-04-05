from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import datetime

# ===========================================================================
# --- A. CRM ---
# ===========================================================================

class Client(models.Model):
    STATUS_CHOICES = [
        ('PROSPECT', 'Prospect'),
        ('ACTIVE', 'Actif'),
        ('VIP', 'VIP'),
        ('LOST', 'Perdu'),
    ]
    SEGMENT_CHOICES = [
        ('FLEXO', 'Flexographie'),
        ('HELIO', 'Héliogravure'),
        ('EXTRUSION', 'Extrusion'),
        ('AUTRE', 'Autre'),
    ]
    SIZE_CHOICES = [
        ('TPE', 'TPE (< 10 salariés)'),
        ('PME', 'PME (10-250)'),
        ('ETI', 'ETI (250-5000)'),
        ('GE', 'Grande Entreprise (> 5000)'),
    ]
    REGION_CHOICES = [
        ('NORD', 'Nord'),
        ('SUD', 'Sud'),
        ('EST', 'Est'),
        ('OUEST', 'Ouest'),
        ('CENTRE', 'Centre'),
        ('EXPORT', 'Export'),
    ]

    name = models.CharField("Raison Sociale", max_length=200)
    code_client = models.CharField("Code Client Interne", max_length=50, blank=True, unique=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROSPECT')
    segment = models.CharField("Segment d'activité", max_length=20, choices=SEGMENT_CHOICES, default='FLEXO')
    size = models.CharField("Taille du client", max_length=10, choices=SIZE_CHOICES, blank=True)
    region = models.CharField("Région / Zone", max_length=10, choices=REGION_CHOICES, blank=True)
    ca_estime = models.DecimalField("Volume Estimé (KG/Étiquette)", max_digits=14, decimal_places=2, default=0)
    sector = models.CharField("Secteur d'activité", max_length=100, blank=True)
    city = models.CharField("Ville", max_length=100)
    address = models.TextField("Adresse complète", blank=True)
    phone = models.CharField("Téléphone", max_length=50)
    email = models.EmailField(blank=True)
    website = models.URLField("Site web", blank=True)
    commercial = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Commercial responsable", related_name='clients'
    )
    date_creation = models.DateField("Date d'entrée", default=timezone.now)
    notes = models.TextField("Notes internes", blank=True)

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_nb_contacts(self):
        return self.clientcontact_set.count()

    def get_nb_opportunites(self):
        return self.opportunite_set.count()

    def get_opportunites_actives(self):
        return self.opportunite_set.exclude(status__in=['GAGNE', 'PERDU'])

    def get_dernier_contact(self):
        log = self.interactionlog_set.order_by('-date').first()
        return log.date if log else None


class ClientContact(models.Model):
    ROLE_CHOICES = [
        ('ACHAT', 'Directeur Achat'),
        ('TECH', 'Responsable Technique'),
        ('COMM', 'Commercial'),
        ('LOGI', 'Responsable Logistique'),
        ('DIR', 'Directeur Général'),
        ('COMPTA', 'Comptabilité'),
        ('AUTRE', 'Autre'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Client")
    name = models.CharField("Nom Prénom", max_length=100)
    role = models.CharField("Fonction", max_length=10, choices=ROLE_CHOICES, default='AUTRE')
    role_custom = models.CharField("Fonction personnalisée", max_length=100, blank=True)
    phone = models.CharField("Téléphone direct", max_length=50, blank=True)
    email = models.EmailField("Email direct", blank=True)
    is_primary = models.BooleanField("Contact Principal", default=False)
    notes = models.TextField("Notes", blank=True)

    class Meta:
        verbose_name = "Contact Client"
        verbose_name_plural = "Contacts Clients"

    def __str__(self):
        return f"{self.name} ({self.client.name})"

    def get_role_display_full(self):
        if self.role == 'AUTRE' and self.role_custom:
            return self.role_custom
        return self.get_role_display()


class InteractionLog(models.Model):
    TYPE_CHOICES = [
        ('CALL', 'Appel téléphonique'),
        ('EMAIL', 'Email'),
        ('MEET', 'Rendez-vous'),
        ('NOTE', 'Note interne'),
        ('VISITE', 'Visite client'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    contact = models.ForeignKey(
        ClientContact, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Contact concerné"
    )
    commercial = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Commercial"
    )
    date = models.DateTimeField("Date / Heure", default=timezone.now)
    type = models.CharField("Type", max_length=10, choices=TYPE_CHOICES)
    summary = models.CharField("Objet / Résumé", max_length=200)
    details = models.TextField("Détails complets", blank=True)
    next_action = models.CharField("Prochaine action", max_length=200, blank=True)
    next_action_date = models.DateField("Date prochaine action", null=True, blank=True)

    class Meta:
        verbose_name = "Journal d'interaction"
        verbose_name_plural = "Journaux d'interaction"
        ordering = ['-date']

    def __str__(self):
        return f"{self.get_type_display()} - {self.client.name} ({self.date.strftime('%d/%m/%Y')})"


# ===========================================================================
# --- OPPORTUNITÉS & PIPELINE ---
# ===========================================================================

class Opportunite(models.Model):
    STAGE_CHOICES = [
        ('PROSPECT', 'Prospect'),
        ('QUALIFICATION', 'Qualification'),
        ('PROPOSITION', 'Proposition envoyée'),
        ('NEGOCIATION', 'Négociation'),
        ('GAGNE', 'Gagné ✓'),
        ('PERDU', 'Perdu ✗'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Client")
    commercial = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Commercial responsable"
    )
    titre = models.CharField("Titre de l'opportunité", max_length=200)
    description = models.TextField("Description", blank=True)
    status = models.CharField("Étape", max_length=20, choices=STAGE_CHOICES, default='PROSPECT')
    valeur_estimee = models.DecimalField("Volume Estimé (KG/Étiquette)", max_digits=14, decimal_places=2, default=0)
    probabilite = models.IntegerField("Probabilité de gain (%)", default=20)
    date_ouverture = models.DateField("Date d'ouverture", default=timezone.now)
    date_cloture_prevue = models.DateField("Date de clôture prévue", null=True, blank=True)
    date_cloture_reelle = models.DateField("Date de clôture réelle", null=True, blank=True)
    motif_perte = models.CharField("Motif de perte", max_length=200, blank=True)
    notes = models.TextField("Notes", blank=True)

    class Meta:
        verbose_name = "Opportunité"
        verbose_name_plural = "Opportunités"
        ordering = ['-date_ouverture']

    def __str__(self):
        return f"{self.titre} - {self.client.name}"

    def valeur_ponderee(self):
        return round(float(self.valeur_estimee) * self.probabilite / 100, 2)

    def is_active(self):
        return self.status not in ['GAGNE', 'PERDU']

    def get_status_color(self):
        colors = {
            'PROSPECT': 'gray',
            'QUALIFICATION': 'blue',
            'PROPOSITION': 'yellow',
            'NEGOCIATION': 'orange',
            'GAGNE': 'green',
            'PERDU': 'red',
        }
        return colors.get(self.status, 'gray')


# ===========================================================================
# --- B. PREPRESSE (Fiches Techniques & Outillage) ---
# ===========================================================================

class TechnicalProduct(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    ref_internal = models.CharField("Ref Interne", max_length=50, unique=True)
    name = models.CharField("Désignation", max_length=200)
    structure_type = models.CharField(
        max_length=20,
        choices=[('MONO', 'Mono'), ('DUPLEX', 'Duplex'), ('TRIPLEX', 'Triplex')],
        default='MONO'
    )
    width_mm = models.FloatField("Laize (mm)", default=0)
    cut_length_mm = models.FloatField("Pas de coupe (mm)", default=0, null=True, blank=True)
    num_colors = models.IntegerField("Nb Couleurs", default=0, null=True, blank=True)
    artwork_file = models.FileField("Fichier Graphique (AI/PDF)", upload_to='artwork/', blank=True)
    artwork_version = models.IntegerField(default=1)

    class Meta:
        verbose_name = "Produit technique"
        verbose_name_plural = "Produits techniques"

    def __str__(self):
        return f"{self.ref_internal} - {self.name}"


class Tooling(models.Model):
    TYPE_CHOICES = [('CYL', 'Cylindre Hélio'), ('CLICHE', 'Cliché Flexo')]
    product = models.ForeignKey(TechnicalProduct, on_delete=models.CASCADE)
    tool_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    serial_number = models.CharField("N° Série", max_length=100)
    max_impressions = models.IntegerField("Durée de vie (tours)", default=1000000)
    current_impressions = models.IntegerField("Tours actuels", default=0)

    class Meta:
        verbose_name = "Outillage cliché, cylindre"
        verbose_name_plural = "Outillages cliché, cylindre"

    def wear_percent(self):
        if self.max_impressions == 0:
            return 0
        return round((self.current_impressions / self.max_impressions) * 100, 1)


# ===========================================================================
# --- E. STOCK (Matières Premières) ---
# ===========================================================================

class Supplier(models.Model):
    name = models.CharField("Fournisseur", max_length=200)
    email = models.EmailField()

    class Meta:
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"

    def __str__(self):
        return self.name


class Material(models.Model):
    CAT_CHOICES = [
        ('FILM', 'Film/Papier'),
        ('INK', 'Encre'),
        ('GLUE', 'Colle'),
        ('SOLV', 'Solvant'),
    ]
    name = models.CharField("Désignation", max_length=200)
    category = models.CharField(max_length=10, choices=CAT_CHOICES)
    quantity = models.FloatField("Stock Réel")
    unit = models.CharField("Unité", max_length=10, default='kg')
    min_threshold = models.FloatField("Stock Alerte (Min)")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True)
    price_per_unit = models.DecimalField("Prix Unitaire", max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Matière première"
        verbose_name_plural = "Matières premières"

    def is_low_stock(self):
        return self.quantity <= self.min_threshold

    def __str__(self):
        return self.name


# ===========================================================================
# --- D. MACHINES & MAINTENANCE ---
# ===========================================================================

class Machine(models.Model):
    STATUS_CHOICES = [
        ('RUN', 'En Production'),
        ('STOP', 'Arrêt'),
        ('MAINT', 'Maintenance'),
        ('PANNE', 'En Panne'),
    ]
    TYPE_CHOICES = [
        ('EXT', 'Extrudeuse'),
        ('IMP', 'Imprimeuse'),
        ('DEC', 'Découpeuse'),
        ('COMP', 'Complexeuse'),
        ('REF', 'Refendeuse'),
    ]
    name = models.CharField("Nom Machine", max_length=100)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='STOP')

    class Meta:
        verbose_name = "Machine"
        verbose_name_plural = "Machines"

    def __str__(self):
        return self.name


class MaintenanceSchedule(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    task = models.CharField("Tâche", max_length=200)
    frequency_days = models.IntegerField("Fréquence (jours)")
    last_done = models.DateField("Dernière fois")

    class Meta:
        verbose_name = "Planning Maintenance"
        verbose_name_plural = "Plannings Maintenance"

    @property
    def next_due(self):
        return self.last_done + datetime.timedelta(days=self.frequency_days)


class IncidentLog(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    issue = models.CharField("Panne", max_length=200)
    action_taken = models.TextField("Action Corrective")
    downtime_minutes = models.IntegerField("Temps d'arrêt (min)", default=0)

    class Meta:
        verbose_name = "Journal d'incident"
        verbose_name_plural = "Journaux d'incidents"


# ===========================================================================
# --- GESTION DES EMPLACEMENTS (Multi-magasins) ---
# ===========================================================================

class StockLocation(models.Model):
    TYPE_CHOICES = [
        ('GENERAL', 'Magasin Général'),
        ('TAMPON', 'Stock Tampon'),
        ('PRODUCTION', 'Zone Production'),
        ('DECHET', 'Zone Déchets'),
        ('QUARANTAINE', 'Quarantaine'),
    ]
    name = models.CharField("Nom de l'emplacement", max_length=100)
    type = models.CharField("Type", max_length=20, choices=TYPE_CHOICES, default='GENERAL')
    description = models.TextField("Description", blank=True)
    is_active = models.BooleanField("Actif", default=True)

    class Meta:
        verbose_name = "Emplacement Stock"
        verbose_name_plural = "Emplacements Stock"

    def __str__(self):
        return f"{self.get_type_display()} – {self.name}"


# ===========================================================================
# --- GESTION DES LOTS FOURNISSEURS ---
# ===========================================================================

class StockLot(models.Model):
    STATUT_CHOICES = [
        ('CONFORME', 'Conforme ✓'),
        ('BLOQUE', 'Bloqué ✗'),
        ('EN_ATTENTE', 'En attente contrôle'),
        ('QUARANTAINE', 'Quarantaine'),
    ]

    material = models.ForeignKey(
        'Material', on_delete=models.CASCADE,
        related_name='lots', verbose_name="Matière première"
    )
    numero_lot = models.CharField("N° Lot fournisseur", max_length=100)
    date_reception = models.DateField("Date réception", default=timezone.now)
    fournisseur = models.ForeignKey(
        'Supplier', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Fournisseur"
    )
    emplacement = models.ForeignKey(
        StockLocation, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Emplacement"
    )
    quantite_initiale = models.FloatField("Quantité initiale (kg)", default=0)
    quantite_restante = models.FloatField("Quantité restante (kg)", default=0)
    prix_unitaire = models.DecimalField("Prix unitaire (DA/kg)", max_digits=10, decimal_places=2, default=0)
    statut = models.CharField("Statut qualité", max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    certificat_qualite = models.FileField(
        "Certificat qualité (PDF)", upload_to='certificats/', blank=True, null=True
    )
    notes = models.TextField("Notes / Remarques", blank=True)
    date_expiration = models.DateField("Date expiration", null=True, blank=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Créé par"
    )

    class Meta:
        verbose_name = "Lot de stock"
        verbose_name_plural = "Lots de stock"
        ordering = ['-date_reception']

    def __str__(self):
        return f"Lot {self.numero_lot} — {self.material.name}"

    @property
    def valeur_stock(self):
        return round(float(self.quantite_restante) * float(self.prix_unitaire), 2)

    @property
    def est_expire(self):
        if self.date_expiration:
            return timezone.now().date() > self.date_expiration
        return False

    @property
    def taux_consommation(self):
        if self.quantite_initiale == 0:
            return 0
        return round((1 - self.quantite_restante / self.quantite_initiale) * 100, 1)


# ===========================================================================
# --- C. PRODUCTION (OF MULTI-PROCESSUS AMÉLIORÉ) ---
# ===========================================================================

class ProcessType(models.Model):
    """Types de processus disponibles (Extrusion, Impression, etc.)"""
    
    code = models.CharField("Code", max_length=20, unique=True)
    nom = models.CharField("Nom du processus", max_length=100)
    description = models.TextField("Description", blank=True)
    ordre_defaut = models.IntegerField("Ordre par défaut", default=0)
    icone = models.CharField("Icône (emoji)", max_length=10, default='⚙️')
    couleur = models.CharField("Couleur (hex)", max_length=7, default='#6c757d')
    est_actif = models.BooleanField("Actif", default=True)

    class Meta:
        verbose_name = "Type de processus"
        verbose_name_plural = "Types de processus"
        ordering = ['ordre_defaut', 'nom']

    def __str__(self):
        return f"{self.icone} {self.nom}"


class OrdreFabrication(models.Model):
    """Ordre de Fabrication principal - Multi-processus"""
    
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('LANCE', 'Lancé'),
        ('EN_COURS', 'En cours'),
        ('TERMINE', 'Terminé'),
        ('ANNULE', 'Annulé'),
    ]
    
    PRIORITE_CHOICES = [
        ('BASSE', 'Basse'),
        ('NORMALE', 'Normale'),
        ('HAUTE', 'Haute'),
        ('URGENTE', 'Urgente'),
    ]
    
    numero_of = models.CharField("N° OF", max_length=50, unique=True)
    numero_lot = models.CharField("N° Lot", max_length=100, blank=True)
    
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE,
        verbose_name="Client", related_name='ordres_fabrication'
    )
    produit = models.ForeignKey(
        TechnicalProduct, on_delete=models.CASCADE,
        verbose_name="Produit fini", related_name='ordres_fabrication'
    )
    opportunite = models.ForeignKey(
        Opportunite, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Opportunité liée"
    )
    
    quantite_prevue = models.FloatField("Quantité prévue (kg)", default=0)
    quantite_produite = models.FloatField("Quantité produite (kg)", default=0)
    quantite_conforme = models.FloatField("Quantité conforme (kg)", default=0)
    quantite_rebut = models.FloatField("Rebuts (kg)", default=0)
    
    dimension_mandrin = models.FloatField("Dimension mandrin (mm)", default=76, null=True, blank=True)
    diametre_bobine_fille = models.FloatField("Diamètre bobine fille (mm)", default=0, null=True, blank=True)
    laize = models.FloatField("Laize (mm)", default=0, null=True, blank=True)
    epaisseur = models.FloatField("Épaisseur (μm)", default=0, null=True, blank=True)
    
    date_creation = models.DateTimeField("Date création", auto_now_add=True)
    date_lancement = models.DateField("Date lancement", null=True, blank=True)
    date_prevue_fin = models.DateField("Date prévue fin", null=True, blank=True)
    date_fin_reelle = models.DateField("Date fin réelle", null=True, blank=True)
    
    statut = models.CharField(
        "Statut", max_length=20,
        choices=STATUT_CHOICES, default='BROUILLON'
    )
    priorite = models.CharField(
        "Priorité", max_length=10,
        choices=PRIORITE_CHOICES, default='NORMALE'
    )
    
    bat_file = models.FileField("BAT Validé", upload_to='bat/', blank=True, null=True)
    fiche_technique = models.FileField("Fiche technique", upload_to='fiches_techniques/', blank=True, null=True)
    
    cree_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='of_crees', verbose_name="Créé par"
    )
    notes = models.TextField("Notes / Instructions", blank=True)

    class Meta:
        verbose_name = "Ordre de Fabrication"
        verbose_name_plural = "Ordres de Fabrication"
        ordering = ['-date_creation']

    def __str__(self):
        return f"OF-{self.numero_of} | {self.produit.name} | {self.client.name}"

    def save(self, *args, **kwargs):
        if not self.numero_of:
            from datetime import datetime
            prefix = datetime.now().strftime('%Y%m')
            last = OrdreFabrication.objects.filter(
                numero_of__startswith=prefix
            ).order_by('-numero_of').first()
            if last:
                try:
                    num = int(last.numero_of[-4:]) + 1
                except ValueError:
                    num = 1
            else:
                num = 1
            self.numero_of = f"{prefix}{num:04d}"
        super().save(*args, **kwargs)

    @property
    def progression(self):
        if self.quantite_prevue == 0:
            return 0
        return round((self.quantite_produite / self.quantite_prevue) * 100, 1)

    @property
    def taux_rebut(self):
        total = self.quantite_produite + self.quantite_rebut
        if total == 0:
            return 0
        return round((self.quantite_rebut / total) * 100, 2)

    @property
    def nb_etapes(self):
        return self.etapes.count()

    @property
    def etapes_terminees(self):
        return self.etapes.filter(statut='TERMINE').count()

    @property
    def etape_en_cours(self):
        return self.etapes.filter(statut='EN_COURS').first()

    @property
    def est_en_retard(self):
        if self.date_prevue_fin and self.statut not in ['TERMINE', 'ANNULE']:
            return timezone.now().date() > self.date_prevue_fin
        return False

    def get_statut_color(self):
        colors = {
            'BROUILLON': 'secondary',
            'LANCE': 'info',
            'EN_COURS': 'primary',
            'TERMINE': 'success',
            'ANNULE': 'danger',
        }
        return colors.get(self.statut, 'secondary')

    def get_priorite_color(self):
        colors = {
            'BASSE': 'secondary',
            'NORMALE': 'info',
            'HAUTE': 'warning',
            'URGENTE': 'danger',
        }
        return colors.get(self.priorite, 'info')


class EtapeProduction(models.Model):
    """Étape de production dans un OF - Chaque étape = 1 processus"""
    
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('PRET', 'Prêt à lancer'),
        ('EN_COURS', 'En cours'),
        ('PAUSE', 'En pause'),
        ('TERMINE', 'Terminé'),
        ('ANNULE', 'Annulé'),
    ]
    
    of = models.ForeignKey(
        OrdreFabrication, on_delete=models.CASCADE,
        related_name='etapes', verbose_name="Ordre de Fabrication"
    )
    process_type = models.ForeignKey(
        ProcessType, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Type de processus"
    )
    machine = models.ForeignKey(
        Machine, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Machine"
    )
    operateur = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Opérateur",
        related_name='etapes_assignees'
    )
    
    numero_etape = models.IntegerField("N° Étape", default=1)
    nom_etape = models.CharField("Nom étape", max_length=100, blank=True)
    
    quantite_entree = models.FloatField("Quantité entrée (kg)", default=0)
    quantite_sortie = models.FloatField("Quantité sortie (kg)", default=0)
    quantite_rebut = models.FloatField("Rebuts (kg)", default=0)
    
    date_prevue_debut = models.DateTimeField("Début prévu", null=True, blank=True)
    date_prevue_fin = models.DateTimeField("Fin prévue", null=True, blank=True)
    date_debut_reel = models.DateTimeField("Début réel", null=True, blank=True)
    date_fin_reel = models.DateTimeField("Fin réelle", null=True, blank=True)
    temps_arret_minutes = models.IntegerField("Temps d'arrêt (min)", default=0)
    
    statut = models.CharField(
        "Statut", max_length=20,
        choices=STATUT_CHOICES, default='EN_ATTENTE'
    )
    
    genere_semi_produit = models.BooleanField("Génère semi-produit", default=True)
    notes = models.TextField("Notes / Instructions", blank=True)

    class Meta:
        verbose_name = "Étape de production"
        verbose_name_plural = "Étapes de production"
        ordering = ['of', 'numero_etape']
        unique_together = ['of', 'numero_etape']

    def __str__(self):
        return f"OF-{self.of.numero_of} | Étape {self.numero_etape}: {self.get_nom_display()}"

    def get_nom_display(self):
        if self.nom_etape:
            return self.nom_etape
        if self.process_type:
            return self.process_type.nom
        return f"Étape {self.numero_etape}"

    @property
    def progression(self):
        if self.quantite_entree == 0:
            return 0
        return round((self.quantite_sortie / self.quantite_entree) * 100, 1)

    @property
    def rendement(self):
        if self.quantite_entree == 0:
            return 0
        return round(((self.quantite_sortie) / self.quantite_entree) * 100, 2)

    @property
    def taux_rebut(self):
        total = self.quantite_sortie + self.quantite_rebut
        if total == 0:
            return 0
        return round((self.quantite_rebut / total) * 100, 2)

    @property
    def duree_prevue_heures(self):
        if self.date_prevue_debut and self.date_prevue_fin:
            diff = self.date_prevue_fin - self.date_prevue_debut
            return round(diff.total_seconds() / 3600, 1)
        return 0

    @property
    def duree_reelle_heures(self):
        if self.date_debut_reel and self.date_fin_reel:
            diff = self.date_fin_reel - self.date_debut_reel
            return round(diff.total_seconds() / 3600, 1)
        return 0

    def get_statut_color(self):
        colors = {
            'EN_ATTENTE': 'secondary',
            'PRET': 'info',
            'EN_COURS': 'primary',
            'PAUSE': 'warning',
            'TERMINE': 'success',
            'ANNULE': 'danger',
        }
        return colors.get(self.statut, 'secondary')


class SemiProduit(models.Model):
    """Gestion des produits semi-finis entre étapes"""
    
    STATUT_CHOICES = [
        ('DISPONIBLE', 'Disponible'),
        ('RESERVE', 'Réservé'),
        ('CONSOMME', 'Consommé'),
        ('BLOQUE', 'Bloqué qualité'),
        ('REBUT', 'Rebut'),
    ]
    
    TYPE_CHOICES = [
        ('FILM_EXTRUDE', 'Film extrudé'),
        ('FILM_IMPRIME', 'Film imprimé'),
        ('FILM_COMPLEXE', 'Film complexé'),
        ('BOBINE_MERE', 'Bobine mère'),
        ('BOBINE_FILLE', 'Bobine fille'),
        ('AUTRE', 'Autre'),
    ]
    
    reference = models.CharField("Référence", max_length=100, unique=True)
    designation = models.CharField("Désignation", max_length=200)
    type_semi_produit = models.CharField(
        "Type", max_length=20,
        choices=TYPE_CHOICES, default='AUTRE'
    )
    
    of_origine = models.ForeignKey(
        OrdreFabrication, on_delete=models.SET_NULL,
        null=True, related_name='semi_produits_generes',
        verbose_name="OF d'origine"
    )
    etape_origine = models.ForeignKey(
        EtapeProduction, on_delete=models.SET_NULL,
        null=True, related_name='semi_produits_generes',
        verbose_name="Étape d'origine"
    )
    etape_destination = models.ForeignKey(
        EtapeProduction, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='semi_produits_consommes',
        verbose_name="Étape de consommation"
    )
    
    quantite = models.FloatField("Quantité (kg)", default=0)
    unite = models.CharField("Unité", max_length=10, default='kg')
    emplacement = models.ForeignKey(
        StockLocation, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Emplacement"
    )
    
    laize = models.FloatField("Laize (mm)", default=0, null=True, blank=True)
    longueur = models.FloatField("Longueur (m)", default=0, null=True, blank=True)
    poids_bobine = models.FloatField("Poids bobine (kg)", default=0, null=True, blank=True)
    numero_bobine = models.CharField("N° Bobine", max_length=50, blank=True)
    
    date_creation = models.DateTimeField("Date création", auto_now_add=True)
    date_peremption = models.DateField("Date péremption", null=True, blank=True)
    statut = models.CharField(
        "Statut", max_length=20,
        choices=STATUT_CHOICES, default='DISPONIBLE'
    )
    
    conforme = models.BooleanField("Conforme", default=True)
    notes_qualite = models.TextField("Notes qualité", blank=True)

    class Meta:
        verbose_name = "Semi-produit"
        verbose_name_plural = "Semi-produits"
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.reference} | {self.designation} | {self.quantite} {self.unite}"

    def save(self, *args, **kwargs):
        if not self.reference:
            from datetime import datetime
            prefix = f"SP-{datetime.now().strftime('%Y%m%d')}"
            last = SemiProduit.objects.filter(
                reference__startswith=prefix
            ).order_by('-reference').first()
            if last:
                try:
                    num = int(last.reference[-4:]) + 1
                except ValueError:
                    num = 1
            else:
                num = 1
            self.reference = f"{prefix}-{num:04d}"
        super().save(*args, **kwargs)

    def get_statut_color(self):
        colors = {
            'DISPONIBLE': 'success',
            'RESERVE': 'info',
            'CONSOMME': 'secondary',
            'BLOQUE': 'warning',
            'REBUT': 'danger',
        }
        return colors.get(self.statut, 'secondary')


class SuiviProduction(models.Model):
    """Suivi en temps réel de la production par étape"""
    
    TYPE_EVENEMENT = [
        ('DEMARRAGE', 'Démarrage'),
        ('ARRET', 'Arrêt'),
        ('REPRISE', 'Reprise'),
        ('FIN', 'Fin'),
        ('PAUSE', 'Pause'),
        ('INCIDENT', 'Incident'),
        ('CONTROLE', 'Contrôle qualité'),
        ('CHANGEMENT', 'Changement série'),
        ('REGLAGE', 'Réglage'),
    ]
    
    CAUSE_ARRET = [
        ('PANNE', 'Panne machine'),
        ('REGLAGE', 'Réglage'),
        ('PAUSE', 'Pause opérateur'),
        ('MATIERE', 'Attente matière'),
        ('QUALITE', 'Problème qualité'),
        ('MAINTENANCE', 'Maintenance préventive'),
        ('CHANGEMENT', 'Changement de série'),
        ('AUTRE', 'Autre'),
    ]
    
    etape = models.ForeignKey(
        EtapeProduction, on_delete=models.CASCADE,
        related_name='suivis', verbose_name="Étape"
    )
    operateur = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Opérateur"
    )
    
    date_heure = models.DateTimeField("Date/Heure", default=timezone.now)
    type_evenement = models.CharField(
        "Type", max_length=20,
        choices=TYPE_EVENEMENT
    )
    cause_arret = models.CharField(
        "Cause arrêt", max_length=20,
        choices=CAUSE_ARRET, blank=True
    )
    
    quantite_produite = models.FloatField("Quantité produite (kg)", default=0)
    quantite_rebut = models.FloatField("Rebut (kg)", default=0)
    vitesse_machine = models.FloatField("Vitesse machine (m/min)", default=0, null=True, blank=True)
    
    commentaire = models.TextField("Commentaire", blank=True)

    class Meta:
        verbose_name = "Suivi de production"
        verbose_name_plural = "Suivis de production"
        ordering = ['-date_heure']

    def __str__(self):
        return f"{self.etape} | {self.get_type_evenement_display()} | {self.date_heure.strftime('%d/%m %H:%M')}"


class ConsommationMatiere(models.Model):
    """Consommation de matières premières par étape"""
    
    etape = models.ForeignKey(
        EtapeProduction, on_delete=models.CASCADE,
        related_name='consommations', verbose_name="Étape"
    )
    material = models.ForeignKey(
        Material, on_delete=models.CASCADE,
        verbose_name="Matière première"
    )
    lot = models.ForeignKey(
        StockLot, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Lot"
    )
    
    quantite_prevue = models.FloatField("Quantité prévue", default=0)
    quantite_reelle = models.FloatField("Quantité réelle", default=0)
    date_consommation = models.DateTimeField("Date", default=timezone.now)

    class Meta:
        verbose_name = "Consommation matière"
        verbose_name_plural = "Consommations matières"

    def __str__(self):
        return f"{self.etape} | {self.material.name} | {self.quantite_reelle} {self.material.unit}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and self.quantite_reelle > 0:
            self.material.quantity -= self.quantite_reelle
            self.material.save()
            if self.lot:
                self.lot.quantite_restante = max(0, self.lot.quantite_restante - self.quantite_reelle)
                self.lot.save()


# Ancien modèle pour compatibilité
class ProductionOrder(models.Model):
    """DÉPRÉCIÉ - Utiliser OrdreFabrication à la place"""
    of_number = models.CharField("N° OF", max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    product = models.ForeignKey(TechnicalProduct, on_delete=models.CASCADE)
    machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True)

    quantity_planned = models.FloatField("Qté Prévue (kg/m)")
    start_time = models.DateTimeField("Début Prévu")
    end_time = models.DateTimeField("Fin Prévue")

    status = models.CharField(
        max_length=20, default='PLANNED',
        choices=[
            ('PLANNED', 'Planifié'),
            ('IN_PROGRESS', 'En cours'),
            ('DONE', 'Terminé'),
            ('LATE', 'En Retard'),
        ]
    )

    bat_file = models.FileField("BAT Validé", upload_to='bat/', blank=True, null=True)
    produced_qty = models.FloatField("Qté Produite", default=0)
    waste_qty = models.FloatField("Déchets (kg)", default=0)

    opportunite = models.ForeignKey(
        'Opportunite', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Opportunité liée"
    )

    class Meta:
        verbose_name = "Ordre de fabrication (ancien)"
        verbose_name_plural = "Ordres de fabrication (anciens)"

    def __str__(self):
        return f"OF {self.of_number} - {self.product.name}"


class ConsumptionLog(models.Model):
    of = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name='consumptions')
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    quantity_used = models.FloatField("Qté Consommée")

    def save(self, *args, **kwargs):
        self.material.quantity -= self.quantity_used
        self.material.save()
        super().save(*args, **kwargs)


class PurchaseOrder(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    status = models.CharField(
        max_length=20, default='DRAFT',
        choices=[('DRAFT', 'Brouillon'), ('SENT', 'Envoyée'), ('RECEIVED', 'Reçue')]
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Bon de commande"
        verbose_name_plural = "Bons de commande"


# ===========================================================================
# --- DEVIS ---
# ===========================================================================

class Quote(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Brouillon'),
        ('SENT', 'Envoyé'),
        ('ACCEPTED', 'Accepté'),
        ('REFUSED', 'Refusé'),
        ('EXPIRED', 'Expiré'),
        ('SIGNED', 'Signé'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    opportunite = models.ForeignKey(
        Opportunite, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Opportunité liée"
    )
    commercial = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Commercial"
    )
    reference = models.CharField("Référence", max_length=50)
    version = models.IntegerField("Version", default=1)
    date = models.DateField("Date du devis", default=timezone.now)
    date_validite = models.DateField("Valide jusqu'au", null=True, blank=True)
    total_amount = models.DecimalField("Montant Total (DA)", max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default='DRAFT', choices=STATUS_CHOICES)
    pdf_file = models.FileField("PDF Signé", upload_to='quotes/', blank=True, null=True)
    notes = models.TextField("Notes", blank=True)
    commande_creee = models.BooleanField("Commande créée", default=False)

    class Meta:
        verbose_name = "Devis"
        verbose_name_plural = "Devis"
        ordering = ['-date', '-version']

    def __str__(self):
        return f"{self.reference} v{self.version}"

    def is_expired(self):
        if self.date_validite and self.status == 'SENT':
            return timezone.now().date() > self.date_validite
        return False

    def get_reference_versionnee(self):
        return f"{self.reference}-{str(self.version).zfill(3)}"


# ===========================================================================
# --- CONSOMMATION ENCRE ---
# ===========================================================================

class ConsommationEncre(models.Model):
    PROCESS_CHOICES = [('FLEXO', 'Flexo'), ('HELIO', 'Hélio')]

    job_name = models.CharField("Nom du Job", max_length=200, default="Sans Nom")
    date = models.DateField("Date De Prod", default=timezone.now)
    process_type = models.CharField("Type Process", max_length=10, choices=PROCESS_CHOICES, default='FLEXO')
    support = models.CharField("Support", max_length=100)
    laize = models.FloatField("Laize (mm)", default=0)

    bobine_in = models.FloatField("Total Bobine In (kg)", default=0)
    bobine_out = models.FloatField("Total Bobine Out (kg)", default=0)
    metrage = models.FloatField("Métrage (m)", default=0)

    encre_noir = models.FloatField("Noir", default=0)
    encre_magenta = models.FloatField("Magenta", default=0)
    encre_jaune = models.FloatField("Jaune", default=0)
    encre_cyan = models.FloatField("Cyan", default=0)
    encre_dore = models.FloatField("Doré", default=0)
    encre_silver = models.FloatField("Silver", default=0)
    encre_orange = models.FloatField("Orange", default=0)
    encre_blanc = models.FloatField("Blanc", default=0)
    encre_vernis = models.FloatField("Vernis Anti", default=0)

    solvant_metoxyn = models.FloatField("Metoxyn", default=0)
    solvant_2080 = models.FloatField("20/80", default=0)

    class Meta:
        verbose_name = "Conso. Encre & Solvant"
        verbose_name_plural = "Conso. Encres & Solvants"

    def __str__(self):
        return f"{self.job_name} - {self.date}"

    @property
    def total_encre(self):
        return (self.encre_noir + self.encre_magenta + self.encre_jaune +
                self.encre_cyan + self.encre_dore + self.encre_silver +
                self.encre_orange + self.encre_blanc + self.encre_vernis)

    @property
    def total_solvant(self):
        return self.solvant_metoxyn + self.solvant_2080

    @property
    def gain_de_masse_kg(self):
        return round(self.bobine_out - self.bobine_in, 2)

    @property
    def matiere_evaporee_kg(self):
        total_injecte = self.total_encre + self.total_solvant
        return round(total_injecte - self.gain_de_masse_kg, 2)

    @property
    def gain_de_masse_percent(self):
        total_injecte = self.total_encre + self.total_solvant
        if total_injecte == 0:
            return 0
        return round((self.gain_de_masse_kg / total_injecte) * 100, 2)

    @property
    def matiere_evaporee_percent(self):
        total_injecte = self.total_encre + self.total_solvant
        if total_injecte == 0:
            return 0
        return round((self.matiere_evaporee_kg / total_injecte) * 100, 2)

    @property
    def grammage(self):
        surface = self.metrage * (self.laize / 1000)
        if surface == 0:
            return 0
        return round((self.gain_de_masse_kg * 1000) / surface, 2)


# ===========================================================================
# --- F. MODULE PRODUCTION SPÉCIAL ---
# ===========================================================================

class ProductionEntry(models.Model):
    EQUIPE_CHOICES = [('A', 'Équipe A'), ('B', 'Équipe B'), ('C', 'Équipe C')]

    date = models.DateField("Date", default=timezone.now)
    produit = models.CharField("Produit", max_length=200)
    support = models.CharField("Support", max_length=100)
    quantite_lancee = models.FloatField("Quantité Lancée (kg)", default=0)
    lot = models.CharField("Lot", max_length=100, blank=True)
    laize = models.FloatField("Laize (mm)", default=0)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True)
    equipe = models.CharField("Équipe", max_length=5, choices=EQUIPE_CHOICES, default='A')
    machine = models.ForeignKey(Machine, on_delete=models.SET_NULL, null=True, blank=True)

    heure_debut = models.TimeField("Heure Début", null=True, blank=True)
    heure_fin = models.TimeField("Heure Fin", null=True, blank=True)

    prod_ml = models.FloatField("Prod ML", default=0)

    dechets_demarrage = models.FloatField("Déchets Démarrage (kg)", default=0)
    dechets_lisiere = models.FloatField("Déchets Lisière (kg)", default=0)
    dechets_jonction = models.FloatField("Déchets Jonction (kg)", default=0)
    dechets_transport = models.FloatField("Déchets Transport (kg)", default=0)

    prod_kg = models.FloatField("Prod KG", default=0)
    rebobinage_kg = models.FloatField("Rebobinage KG", default=0)

    class Meta:
        verbose_name = "Saisie Production"
        verbose_name_plural = "Saisies Production"
        ordering = ['-date', '-heure_debut']

    def __str__(self):
        return f"{self.date} - {self.produit} - {self.equipe}"

    @property
    def temps_ouverture(self):
        if self.heure_debut and self.heure_fin:
            from datetime import datetime, timedelta
            dt_debut = datetime.combine(self.date, self.heure_debut)
            dt_fin = datetime.combine(self.date, self.heure_fin)
            if dt_fin < dt_debut:
                dt_fin += timedelta(days=1)
            diff = dt_fin - dt_debut
            total_seconds = int(diff.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}:{minutes:02d}"
        return "0:00"

    @property
    def temps_ouverture_minutes(self):
        if self.heure_debut and self.heure_fin:
            from datetime import datetime, timedelta
            dt_debut = datetime.combine(self.date, self.heure_debut)
            dt_fin = datetime.combine(self.date, self.heure_fin)
            if dt_fin < dt_debut:
                dt_fin += timedelta(days=1)
            diff = dt_fin - dt_debut
            return diff.total_seconds() / 60
        return 0

    @property
    def total_dechets_kg(self):
        return round(
            self.dechets_demarrage + self.dechets_lisiere +
            self.dechets_jonction + self.dechets_transport, 2
        )

    @property
    def taux_dechets(self):
        if self.prod_kg == 0:
            return 0
        return round((self.total_dechets_kg / self.prod_kg) * 100, 2)

    @property
    def decalage(self):
        return round(self.prod_kg - self.quantite_lancee, 2)


# ===========================================================================
# --- JOURNAL DES MOUVEMENTS DE STOCK ---
# ===========================================================================

class StockMovement(models.Model):
    TYPE_CHOICES = [
        ('ENTREE', 'Entrée (Achat / Réception)'),
        ('SORTIE', 'Sortie (Production)'),
        ('TRANSFERT', 'Transfert interne'),
        ('AJUSTEMENT', 'Ajustement inventaire'),
        ('RETOUR', 'Retour fournisseur'),
        ('PERTE', 'Perte / Déchet'),
    ]

    date = models.DateTimeField("Date", default=timezone.now)
    type = models.CharField("Type de mouvement", max_length=20, choices=TYPE_CHOICES)
    material = models.ForeignKey(
        'Material', on_delete=models.CASCADE,
        related_name='mouvements', verbose_name="Matière"
    )
    lot = models.ForeignKey(
        StockLot, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mouvements', verbose_name="Lot"
    )
    quantite = models.FloatField("Quantité (kg)")
    emplacement_source = models.ForeignKey(
        StockLocation, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mouvements_sortie', verbose_name="Emplacement source"
    )
    emplacement_destination = models.ForeignKey(
        StockLocation, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mouvements_entree', verbose_name="Emplacement destination"
    )
    of = models.ForeignKey(
        'ProductionOrder', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="OF lié"
    )
    machine = models.ForeignKey(
        'Machine', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Machine"
    )
    utilisateur = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Utilisateur"
    )
    motif = models.CharField("Motif / Référence", max_length=200, blank=True)
    notes = models.TextField("Notes", blank=True)

    class Meta:
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ['-date']

    def __str__(self):
        return f"{self.get_type_display()} – {self.material.name} – {self.quantite} kg ({self.date.strftime('%d/%m/%Y')})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            mat = self.material
            if self.type in ['ENTREE']:
                mat.quantity += self.quantite
            elif self.type in ['SORTIE', 'PERTE', 'RETOUR']:
                mat.quantity -= self.quantite
            mat.save()
            if self.lot:
                lot = self.lot
                if self.type in ['SORTIE', 'PERTE']:
                    lot.quantite_restante = max(0, lot.quantite_restante - self.quantite)
                elif self.type == 'ENTREE':
                    lot.quantite_restante += self.quantite
                lot.save()


# ===========================================================================
# --- MODULE ACHATS AMÉLIORÉ ---
# ===========================================================================

class DemandeAchat(models.Model):
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('SOUMISE', 'Soumise pour validation'),
        ('VALIDEE', 'Validée ✓'),
        ('REFUSEE', 'Refusée ✗'),
        ('COMMANDEE', 'Bon de commande émis'),
    ]
    URGENCE_CHOICES = [
        ('NORMALE', 'Normale'),
        ('URGENTE', 'Urgente'),
        ('CRITIQUE', 'Critique !!'),
    ]

    reference = models.CharField("Référence DA", max_length=50, unique=True)
    material = models.ForeignKey(
        'Material', on_delete=models.CASCADE, verbose_name="Matière demandée"
    )
    quantite_demandee = models.FloatField("Quantité demandée (kg)")
    motif = models.TextField("Motif de la demande", blank=True)
    urgence = models.CharField("Niveau d'urgence", max_length=10, choices=URGENCE_CHOICES, default='NORMALE')
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    demandeur = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='demandes_achat', verbose_name="Demandeur"
    )
    valideur = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='validations_achat', verbose_name="Validé par"
    )
    date_creation = models.DateField("Date création", default=timezone.now)
    date_validation = models.DateField("Date validation", null=True, blank=True)
    date_besoin = models.DateField("Date besoin souhaitée", null=True, blank=True)
    bon_commande = models.ForeignKey(
        'BonCommande', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="BC généré"
    )

    class Meta:
        verbose_name = "Demande d'achat"
        verbose_name_plural = "Demandes d'achat"
        ordering = ['-date_creation']

    def __str__(self):
        return f"DA-{self.reference} — {self.material.name}"


class BonCommande(models.Model):
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('ENVOYE', 'Envoyé fournisseur'),
        ('CONFIRME', 'Confirmé'),
        ('RECU_PARTIEL', 'Reçu partiellement'),
        ('RECU_TOTAL', 'Reçu totalement'),
        ('ANNULE', 'Annulé'),
    ]

    reference = models.CharField("Référence BC", max_length=50, unique=True)
    fournisseur = models.ForeignKey(
        'Supplier', on_delete=models.CASCADE, verbose_name="Fournisseur"
    )
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    date_commande = models.DateField("Date commande", default=timezone.now)
    date_livraison_prevue = models.DateField("Livraison prévue", null=True, blank=True)
    date_livraison_reelle = models.DateField("Livraison réelle", null=True, blank=True)
    montant_total = models.DecimalField("Montant total (DA)", max_digits=14, decimal_places=2, default=0)
    notes = models.TextField("Notes / Conditions", blank=True)
    cree_par = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Créé par"
    )

    class Meta:
        verbose_name = "Bon de commande"
        verbose_name_plural = "Bons de commande"
        ordering = ['-date_commande']

    def __str__(self):
        return f"BC-{self.reference} — {self.fournisseur.name}"

    @property
    def nb_lignes(self):
        return self.lignes.count()


class LigneBonCommande(models.Model):
    bon_commande = models.ForeignKey(
        BonCommande, on_delete=models.CASCADE, related_name='lignes'
    )
    material = models.ForeignKey(
        'Material', on_delete=models.CASCADE, verbose_name="Matière"
    )
    quantite_commandee = models.FloatField("Quantité commandée (kg)")
    quantite_recue = models.FloatField("Quantité reçue (kg)", default=0)
    prix_unitaire = models.DecimalField("Prix unitaire (DA/kg)", max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Ligne BC"

    @property
    def montant_ligne(self):
        return round(self.quantite_commandee * float(self.prix_unitaire), 2)

    @property
    def est_recu(self):
        return self.quantite_recue >= self.quantite_commandee


# ===========================================================================
# --- SEUILS INTELLIGENTS & PRÉVISIONS ---
# ===========================================================================

class StockSeuil(models.Model):
    material = models.OneToOneField(
        'Material', on_delete=models.CASCADE,
        related_name='seuil_intelligent', verbose_name="Matière"
    )
    consommation_journaliere_moy = models.FloatField(
        "Conso. moyenne/jour (kg)", default=0
    )
    delai_fournisseur_jours = models.IntegerField(
        "Délai fournisseur (jours)", default=7
    )
    stock_securite_jours = models.IntegerField(
        "Jours de sécurité supplémentaires", default=3
    )
    derniere_maj = models.DateTimeField("Dernière mise à jour", auto_now=True)

    class Meta:
        verbose_name = "Seuil intelligent"
        verbose_name_plural = "Seuils intelligents"

    @property
    def seuil_calcule(self):
        return round(
            (self.delai_fournisseur_jours + self.stock_securite_jours)
            * self.consommation_journaliere_moy, 2
        )

    @property
    def jours_de_stock(self):
        if self.consommation_journaliere_moy == 0:
            return 999
        return round(self.material.quantity / self.consommation_journaliere_moy, 1)

    @property
    def date_rupture_prevue(self):
        if self.consommation_journaliere_moy == 0:
            return None
        jours = self.jours_de_stock
        return timezone.now().date() + datetime.timedelta(days=int(jours))

    def __str__(self):
        return f"Seuil — {self.material.name}"
    # ===========================================================================
# --- MODULE DRH (RESSOURCES HUMAINES) ---
# ===========================================================================

class Department(models.Model):
    """Départements de l'entreprise"""
    
    name = models.CharField("Nom du département", max_length=100)
    code = models.CharField("Code", max_length=20, unique=True)
    description = models.TextField("Description", blank=True)
    responsable = models.ForeignKey(
        'Employee', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='departements_geres',
        verbose_name="Responsable"
    )
    is_active = models.BooleanField("Actif", default=True)
    
    class Meta:
        verbose_name = "Département"
        verbose_name_plural = "Départements"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def nb_employes(self):
        return self.employees.filter(statut='ACTIF').count()


class Position(models.Model):
    """Postes / Fonctions"""
    
    CATEGORY_CHOICES = [
        ('PRODUCTION', 'Production'),
        ('MAINTENANCE', 'Maintenance'),
        ('QUALITE', 'Qualité'),
        ('LOGISTIQUE', 'Logistique'),
        ('ADMIN', 'Administratif'),
        ('DIRECTION', 'Direction'),
    ]
    
    name = models.CharField("Intitulé du poste", max_length=100)
    code = models.CharField("Code poste", max_length=20, unique=True)
    category = models.CharField("Catégorie", max_length=20, choices=CATEGORY_CHOICES, default='PRODUCTION')
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='positions',
        verbose_name="Département"
    )
    description = models.TextField("Description du poste", blank=True)
    salaire_min = models.DecimalField("Salaire minimum (DA)", max_digits=12, decimal_places=2, default=0)
    salaire_max = models.DecimalField("Salaire maximum (DA)", max_digits=12, decimal_places=2, default=0)
    requires_machine_auth = models.BooleanField("Nécessite autorisation machine", default=False)
    is_active = models.BooleanField("Actif", default=True)
    
    class Meta:
        verbose_name = "Poste"
        verbose_name_plural = "Postes"
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class Employee(models.Model):
    """Employés"""
    
    GENDER_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]
    
    STATUT_CHOICES = [
        ('ACTIF', 'Actif'),
        ('CONGE', 'En congé'),
        ('SUSPENDU', 'Suspendu'),
        ('DEMISSION', 'Démissionnaire'),
        ('LICENCIE', 'Licencié'),
        ('RETRAITE', 'Retraité'),
    ]
    
    CONTRAT_CHOICES = [
        ('CDI', 'CDI'),
        ('CDD', 'CDD'),
        ('INTERIM', 'Intérimaire'),
        ('STAGE', 'Stagiaire'),
        ('APPRENTI', 'Apprenti'),
    ]
    
    SITUATION_CHOICES = [
        ('CELIBATAIRE', 'Célibataire'),
        ('MARIE', 'Marié(e)'),
        ('DIVORCE', 'Divorcé(e)'),
        ('VEUF', 'Veuf/Veuve'),
    ]
    
    # Lien utilisateur Django (optionnel)
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='employee_profile',
        verbose_name="Compte utilisateur"
    )
    
    # Identité
    matricule = models.CharField("Matricule", max_length=50, unique=True)
    nom = models.CharField("Nom", max_length=100)
    prenom = models.CharField("Prénom", max_length=100)
    nom_arabe = models.CharField("الإسم بالعربية", max_length=200, blank=True)
    date_naissance = models.DateField("Date de naissance", null=True, blank=True)
    lieu_naissance = models.CharField("Lieu de naissance", max_length=100, blank=True)
    genre = models.CharField("Genre", max_length=1, choices=GENDER_CHOICES, default='M')
    situation_familiale = models.CharField(
        "Situation familiale", max_length=20,
        choices=SITUATION_CHOICES, default='CELIBATAIRE'
    )
    nb_enfants = models.IntegerField("Nombre d'enfants", default=0)
    
    # Documents officiels
    cin = models.CharField("N° CIN (Carte d'identité)", max_length=50, blank=True)
    num_securite_sociale = models.CharField("N° Sécurité Sociale (CNAS)", max_length=50, blank=True)
    num_carte_chifa = models.CharField("N° Carte Chifa", max_length=50, blank=True)
    
    # Coordonnées
    adresse = models.TextField("Adresse complète", blank=True)
    wilaya = models.CharField("Wilaya", max_length=50, blank=True)
    commune = models.CharField("Commune", max_length=50, blank=True)
    telephone = models.CharField("Tél��phone", max_length=50, blank=True)
    telephone_urgence = models.CharField("Téléphone urgence", max_length=50, blank=True)
    email = models.EmailField("Email", blank=True)
    
    # Informations professionnelles
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='employees',
        verbose_name="Département"
    )
    position = models.ForeignKey(
        Position, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='employees',
        verbose_name="Poste"
    )
    superieur = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='subordonnes',
        verbose_name="Supérieur hiérarchique"
    )
    
    # Affectation machine/ligne
    machine_affectee = models.ForeignKey(
        'Machine', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='operateurs',
        verbose_name="Machine/Ligne affectée"
    )
    atelier = models.CharField("Atelier", max_length=50, blank=True)
    
    # Contrat et dates
    type_contrat = models.CharField(
        "Type de contrat", max_length=20,
        choices=CONTRAT_CHOICES, default='CDI'
    )
    date_embauche = models.DateField("Date d'embauche")
    date_fin_contrat = models.DateField("Date fin de contrat", null=True, blank=True)
    date_depart = models.DateField("Date de départ", null=True, blank=True)
    motif_depart = models.TextField("Motif de départ", blank=True)
    
    # Salaire
    salaire_base = models.DecimalField(
        "Salaire de base (DA)", max_digits=12, decimal_places=2, default=0
    )
    
    # Congés
    solde_conge = models.FloatField("Solde congé (jours)", default=30)
    
    # Statut
    statut = models.CharField(
        "Statut", max_length=20,
        choices=STATUT_CHOICES, default='ACTIF'
    )
    
    # Photo
    photo = models.ImageField("Photo", upload_to='employees/photos/', blank=True, null=True)
    
    # Métadonnées
    date_creation = models.DateTimeField("Date création", auto_now_add=True)
    date_modification = models.DateTimeField("Dernière modification", auto_now=True)
    notes = models.TextField("Notes", blank=True)
    
    class Meta:
        verbose_name = "Employé"
        verbose_name_plural = "Employés"
        ordering = ['nom', 'prenom']
    
    def __str__(self):
        return f"{self.matricule} - {self.nom} {self.prenom}"
    
    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenom}"
    
    @property
    def age(self):
        if self.date_naissance:
            today = timezone.now().date()
            return today.year - self.date_naissance.year - (
                (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day)
            )
        return None
    
    @property
    def anciennete_annees(self):
        if self.date_embauche:
            today = timezone.now().date()
            return today.year - self.date_embauche.year - (
                (today.month, today.day) < (self.date_embauche.month, self.date_embauche.day)
            )
        return 0
    
    @property
    def anciennete_display(self):
        if self.date_embauche:
            delta = timezone.now().date() - self.date_embauche
            years = delta.days // 365
            months = (delta.days % 365) // 30
            if years > 0:
                return f"{years} an(s) et {months} mois"
            return f"{months} mois"
        return "—"
    
    def save(self, *args, **kwargs):
        # Générer matricule automatiquement si vide
        if not self.matricule:
            year = timezone.now().strftime('%Y')
            last = Employee.objects.filter(
                matricule__startswith=f"EMP{year}"
            ).order_by('-matricule').first()
            if last:
                try:
                    num = int(last.matricule[-4:]) + 1
                except ValueError:
                    num = 1
            else:
                num = 1
            self.matricule = f"EMP{year}{num:04d}"
        super().save(*args, **kwargs)


class EmployeeDocument(models.Model):
    """Documents des employés"""
    
    TYPE_CHOICES = [
        ('CONTRAT', 'Contrat de travail'),
        ('CIN', 'Copie CIN'),
        ('DIPLOME', 'Diplôme'),
        ('CERTIFICAT', 'Certificat'),
        ('ATTESTATION', 'Attestation'),
        ('CV', 'CV'),
        ('PHOTO', 'Photo'),
        ('AUTRE', 'Autre'),
    ]
    
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='documents', verbose_name="Employé"
    )
    type_document = models.CharField("Type", max_length=20, choices=TYPE_CHOICES)
    nom = models.CharField("Nom du document", max_length=200)
    fichier = models.FileField("Fichier", upload_to='employees/documents/')
    date_upload = models.DateTimeField("Date upload", auto_now_add=True)
    date_expiration = models.DateField("Date d'expiration", null=True, blank=True)
    notes = models.TextField("Notes", blank=True)
    
    class Meta:
        verbose_name = "Document employé"
        verbose_name_plural = "Documents employés"
        ordering = ['-date_upload']
    
    def __str__(self):
        return f"{self.employee.nom_complet} - {self.nom}"
    
    @property
    def est_expire(self):
        if self.date_expiration:
            return timezone.now().date() > self.date_expiration
        return False


# ===========================================================================
# --- COMPÉTENCES ET AUTORISATIONS ---
# ===========================================================================

class Skill(models.Model):
    """Compétences disponibles"""
    
    CATEGORY_CHOICES = [
        ('MACHINE', 'Conduite machine'),
        ('TECHNIQUE', 'Technique'),
        ('QUALITE', 'Qualité'),
        ('SECURITE', 'Sécurité'),
        ('SOFT', 'Soft skills'),
    ]
    
    name = models.CharField("Nom de la compétence", max_length=100)
    code = models.CharField("Code", max_length=20, unique=True)
    category = models.CharField("Catégorie", max_length=20, choices=CATEGORY_CHOICES, default='MACHINE')
    description = models.TextField("Description", blank=True)
    machine_associee = models.ForeignKey(
        'Machine', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='competences_requises',
        verbose_name="Machine associée"
    )
    is_active = models.BooleanField("Active", default=True)
    
    class Meta:
        verbose_name = "Compétence"
        verbose_name_plural = "Compétences"
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class EmployeeSkill(models.Model):
    """Compétences d'un employé"""
    
    LEVEL_CHOICES = [
        (1, '⭐ Débutant'),
        (2, '⭐⭐ Intermédiaire'),
        (3, '⭐⭐⭐ Confirmé'),
        (4, '⭐⭐⭐⭐ Expert'),
        (5, '⭐⭐⭐⭐⭐ Formateur'),
    ]
    
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='competences', verbose_name="Employé"
    )
    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE,
        related_name='employees', verbose_name="Compétence"
    )
    level = models.IntegerField("Niveau", choices=LEVEL_CHOICES, default=1)
    date_acquisition = models.DateField("Date d'acquisition", default=timezone.now)
    date_validation = models.DateField("Date de validation", null=True, blank=True)
    validateur = models.ForeignKey(
        Employee, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='competences_validees',
        verbose_name="Validé par"
    )
    certificat = models.FileField("Certificat", upload_to='employees/certificats/', blank=True, null=True)
    notes = models.TextField("Notes", blank=True)
    
    class Meta:
        verbose_name = "Compétence employé"
        verbose_name_plural = "Compétences employés"
        unique_together = ['employee', 'skill']
        ordering = ['employee', '-level']
    
    def __str__(self):
        return f"{self.employee.nom_complet} - {self.skill.name} (Niv.{self.level})"


class MachineAuthorization(models.Model):
    """Autorisations machine pour les employés"""
    
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('VALIDE', 'Validé ✓'),
        ('REFUSE', 'Refusé ✗'),
        ('EXPIRE', 'Expiré'),
        ('SUSPENDU', 'Suspendu'),
    ]
    
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='autorisations_machine', verbose_name="Employé"
    )
    machine = models.ForeignKey(
        'Machine', on_delete=models.CASCADE,
        related_name='operateurs_autorises', verbose_name="Machine"
    )
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    date_demande = models.DateField("Date de demande", default=timezone.now)
    date_validation = models.DateField("Date de validation", null=True, blank=True)
    date_expiration = models.DateField("Date d'expiration", null=True, blank=True)
    validateur = models.ForeignKey(
        Employee, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='autorisations_validees',
        verbose_name="Validé par"
    )
    niveau_autorisation = models.CharField(
        "Niveau", max_length=20,
        choices=[('OPERATEUR', 'Opérateur'), ('REGLEUR', 'Régleur'), ('FORMATEUR', 'Formateur')],
        default='OPERATEUR'
    )
    notes = models.TextField("Notes", blank=True)
    
    class Meta:
        verbose_name = "Autorisation machine"
        verbose_name_plural = "Autorisations machines"
        unique_together = ['employee', 'machine']
    
    def __str__(self):
        return f"{self.employee.nom_complet} → {self.machine.name}"
    
    @property
    def est_valide(self):
        if self.statut != 'VALIDE':
            return False
        if self.date_expiration and timezone.now().date() > self.date_expiration:
            return False
        return True


# ===========================================================================
# --- POINTAGE ET PRÉSENCES ---
# ===========================================================================

class Shift(models.Model):
    """Équipes de travail (shifts)"""
    
    name = models.CharField("Nom de l'équipe", max_length=50)
    code = models.CharField("Code", max_length=10, unique=True)
    heure_debut = models.TimeField("Heure début")
    heure_fin = models.TimeField("Heure fin")
    pause_debut = models.TimeField("Début pause", null=True, blank=True)
    pause_fin = models.TimeField("Fin pause", null=True, blank=True)
    heures_travail = models.FloatField("Heures de travail", default=8)
    couleur = models.CharField("Couleur", max_length=7, default='#3b82f6')
    is_active = models.BooleanField("Actif", default=True)
    
    class Meta:
        verbose_name = "Équipe (Shift)"
        verbose_name_plural = "Équipes (Shifts)"
        ordering = ['heure_debut']
    
    def __str__(self):
        return f"{self.name} ({self.heure_debut.strftime('%H:%M')} - {self.heure_fin.strftime('%H:%M')})"


class Attendance(models.Model):
    """Pointage journalier"""
    
    STATUT_CHOICES = [
        ('PRESENT', 'Présent ✓'),
        ('ABSENT', 'Absent'),
        ('RETARD', 'Retard'),
        ('CONGE', 'En congé'),
        ('MALADIE', 'Maladie'),
        ('MISSION', 'Mission'),
        ('FERIE', 'Jour férié'),
        ('REPOS', 'Jour de repos'),
    ]
    
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='pointages', verbose_name="Employé"
    )
    date = models.DateField("Date")
    shift = models.ForeignKey(
        Shift, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Équipe"
    )
    
    # Pointage
    heure_arrivee = models.TimeField("Heure d'arrivée", null=True, blank=True)
    heure_depart = models.TimeField("Heure de départ", null=True, blank=True)
    
    # Calculs
    heures_normales = models.FloatField("Heures normales", default=0)
    heures_supplementaires = models.FloatField("Heures supplémentaires", default=0)
    heures_nuit = models.FloatField("Heures de nuit", default=0)
    minutes_retard = models.IntegerField("Minutes de retard", default=0)
    
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='PRESENT')
    
    # Machine/atelier
    machine = models.ForeignKey(
        'Machine', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Machine"
    )
    atelier = models.CharField("Atelier", max_length=50, blank=True)
    
    # Validation
    valide = models.BooleanField("Validé", default=False)
    valide_par = models.ForeignKey(
        Employee, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pointages_valides',
        verbose_name="Validé par"
    )
    
    notes = models.TextField("Notes / Remarques", blank=True)
    
    class Meta:
        verbose_name = "Pointage"
        verbose_name_plural = "Pointages"
        unique_together = ['employee', 'date']
        ordering = ['-date', 'employee']
    
    def __str__(self):
        return f"{self.employee.nom_complet} - {self.date} - {self.get_statut_display()}"
    
    @property
    def heures_totales(self):
        return self.heures_normales + self.heures_supplementaires
    
    def calculer_heures(self):
        """Calcule les heures travaillées"""
        if self.heure_arrivee and self.heure_depart:
            from datetime import datetime, timedelta
            
            debut = datetime.combine(self.date, self.heure_arrivee)
            fin = datetime.combine(self.date, self.heure_depart)
            
            # Si départ après minuit
            if fin < debut:
                fin += timedelta(days=1)
            
            diff = fin - debut
            heures_totales = diff.total_seconds() / 3600
            
            # Heures normales vs supplémentaires (base 8h)
            if heures_totales <= 8:
                self.heures_normales = heures_totales
                self.heures_supplementaires = 0
            else:
                self.heures_normales = 8
                self.heures_supplementaires = heures_totales - 8
            
            # Calcul retard
            if self.shift and self.heure_arrivee > self.shift.heure_debut:
                retard = datetime.combine(self.date, self.heure_arrivee) - datetime.combine(self.date, self.shift.heure_debut)
                self.minutes_retard = int(retard.total_seconds() / 60)
            
            self.save()


# ===========================================================================
# --- CONGÉS ET ABSENCES ---
# ===========================================================================

class LeaveType(models.Model):
    """Types de congés"""
    
    name = models.CharField("Type de congé", max_length=100)
    code = models.CharField("Code", max_length=20, unique=True)
    jours_par_an = models.IntegerField("Jours par an", default=0)
    paye = models.BooleanField("Congé payé", default=True)
    justificatif_requis = models.BooleanField("Justificatif requis", default=False)
    couleur = models.CharField("Couleur", max_length=7, default='#6b7280')
    is_active = models.BooleanField("Actif", default=True)
    
    class Meta:
        verbose_name = "Type de congé"
        verbose_name_plural = "Types de congés"
    
    def __str__(self):
        return self.name


class LeaveRequest(models.Model):
    """Demandes de congé"""
    
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('SOUMISE', 'Soumise'),
        ('VALIDEE_N1', 'Validée N+1'),
        ('VALIDEE_RH', 'Validée RH ✓'),
        ('REFUSEE', 'Refusée ✗'),
        ('ANNULEE', 'Annulée'),
    ]
    
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='demandes_conge', verbose_name="Employé"
    )
    type_conge = models.ForeignKey(
        LeaveType, on_delete=models.CASCADE,
        verbose_name="Type de congé"
    )
    
    date_debut = models.DateField("Date début")
    date_fin = models.DateField("Date fin")
    nb_jours = models.FloatField("Nombre de jours", default=1)
    
    motif = models.TextField("Motif", blank=True)
    justificatif = models.FileField("Justificatif", upload_to='leaves/justificatifs/', blank=True, null=True)
    
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    
    # Workflow validation
    date_demande = models.DateTimeField("Date de demande", auto_now_add=True)
    validateur_n1 = models.ForeignKey(
        Employee, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='conges_valides_n1',
        verbose_name="Validateur N+1"
    )
    date_validation_n1 = models.DateTimeField("Date validation N+1", null=True, blank=True)
    validateur_rh = models.ForeignKey(
        Employee, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='conges_valides_rh',
        verbose_name="Validateur RH"
    )
    date_validation_rh = models.DateTimeField("Date validation RH", null=True, blank=True)
    
    motif_refus = models.TextField("Motif de refus", blank=True)
    notes = models.TextField("Notes", blank=True)
    
    class Meta:
        verbose_name = "Demande de congé"
        verbose_name_plural = "Demandes de congés"
        ordering = ['-date_demande']
    
    def __str__(self):
        return f"{self.employee.nom_complet} - {self.type_conge.name} ({self.date_debut} → {self.date_fin})"
    
    def save(self, *args, **kwargs):
        # Calculer automatiquement le nombre de jours
        if self.date_debut and self.date_fin:
            delta = self.date_fin - self.date_debut
            self.nb_jours = delta.days + 1
        super().save(*args, **kwargs)
    
    def valider_n1(self, validateur):
        """Validation par le supérieur hiérarchique"""
        self.statut = 'VALIDEE_N1'
        self.validateur_n1 = validateur
        self.date_validation_n1 = timezone.now()
        self.save()
    
    def valider_rh(self, validateur):
        """Validation par les RH - Déduit du solde"""
        self.statut = 'VALIDEE_RH'
        self.validateur_rh = validateur
        self.date_validation_rh = timezone.now()
        self.save()
        
        # Déduire du solde de congé si congé payé
        if self.type_conge.paye:
            self.employee.solde_conge -= self.nb_jours
            self.employee.save()
    
    def refuser(self, validateur, motif):
        """Refuser la demande"""
        self.statut = 'REFUSEE'
        self.motif_refus = motif
        self.save()


# ===========================================================================
# --- PAIE (SYSTÈME ALGÉRIEN) ---
# ===========================================================================

class SalaryGrid(models.Model):
    """Grille salariale"""
    
    name = models.CharField("Nom de la grille", max_length=100)
    position = models.ForeignKey(
        Position, on_delete=models.CASCADE,
        related_name='grilles_salariales', verbose_name="Poste"
    )
    echelon = models.IntegerField("Échelon", default=1)
    salaire_base = models.DecimalField("Salaire de base", max_digits=12, decimal_places=2)
    date_effet = models.DateField("Date d'effet")
    is_active = models.BooleanField("Active", default=True)
    
    class Meta:
        verbose_name = "Grille salariale"
        verbose_name_plural = "Grilles salariales"
        ordering = ['position', 'echelon']
    
    def __str__(self):
        return f"{self.position.name} - Échelon {self.echelon} : {self.salaire_base} DA"


class Payslip(models.Model):
    """Bulletin de paie"""
    
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('CALCULE', 'Calculé'),
        ('VALIDE', 'Validé ✓'),
        ('PAYE', 'Payé'),
    ]
    
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='bulletins_paie', verbose_name="Employé"
    )
    
    # Période
    mois = models.IntegerField("Mois")
    annee = models.IntegerField("Année")
    reference = models.CharField("Référence", max_length=50, unique=True)
    
    # Jours travaillés
    jours_travailles = models.FloatField("Jours travaillés", default=26)
    jours_absence = models.FloatField("Jours d'absence", default=0)
    jours_conge = models.FloatField("Jours de congé", default=0)
    
    # Heures
    heures_normales = models.FloatField("Heures normales", default=0)
    heures_supplementaires_25 = models.FloatField("HS 25%", default=0)
    heures_supplementaires_50 = models.FloatField("HS 50%", default=0)
    heures_supplementaires_100 = models.FloatField("HS 100%", default=0)
    heures_nuit = models.FloatField("Heures de nuit", default=0)
    
    # === GAINS ===
    salaire_base = models.DecimalField("Salaire de base", max_digits=12, decimal_places=2, default=0)
    prime_rendement = models.DecimalField("Prime de rendement", max_digits=12, decimal_places=2, default=0)
    prime_presence = models.DecimalField("Prime de présence", max_digits=12, decimal_places=2, default=0)
    prime_nuit = models.DecimalField("Prime de nuit", max_digits=12, decimal_places=2, default=0)
    prime_anciennete = models.DecimalField("Prime d'ancienneté", max_digits=12, decimal_places=2, default=0)
    prime_transport = models.DecimalField("Indemnité transport", max_digits=12, decimal_places=2, default=0)
    prime_panier = models.DecimalField("Indemnité panier", max_digits=12, decimal_places=2, default=0)
    heures_sup_montant = models.DecimalField("Montant HS", max_digits=12, decimal_places=2, default=0)
    autres_primes = models.DecimalField("Autres primes", max_digits=12, decimal_places=2, default=0)
    
    # Total brut
    salaire_brut = models.DecimalField("Salaire brut", max_digits=12, decimal_places=2, default=0)
    
    # === COTISATIONS SALARIALES ===
    cotisation_cnas = models.DecimalField("CNAS (9%)", max_digits=12, decimal_places=2, default=0)
    cotisation_cnr = models.DecimalField("CNR Retraite (6.75%)", max_digits=12, decimal_places=2, default=0)
    cotisation_cnac = models.DecimalField("CNAC Chômage (0.5%)", max_digits=12, decimal_places=2, default=0)
    total_cotisations = models.DecimalField("Total cotisations", max_digits=12, decimal_places=2, default=0)
    
    # Salaire imposable
    salaire_imposable = models.DecimalField("Salaire imposable", max_digits=12, decimal_places=2, default=0)
    
    # IRG
    irg = models.DecimalField("IRG", max_digits=12, decimal_places=2, default=0)
    
    # === DÉDUCTIONS ===
    retenue_absence = models.DecimalField("Retenue absence", max_digits=12, decimal_places=2, default=0)
    avance_salaire = models.DecimalField("Avance sur salaire", max_digits=12, decimal_places=2, default=0)
    pret = models.DecimalField("Remboursement prêt", max_digits=12, decimal_places=2, default=0)
    autres_retenues = models.DecimalField("Autres retenues", max_digits=12, decimal_places=2, default=0)
    total_retenues = models.DecimalField("Total retenues", max_digits=12, decimal_places=2, default=0)
    
    # === SALAIRE NET ===
    salaire_net = models.DecimalField("Salaire net", max_digits=12, decimal_places=2, default=0)
    
    # === CHARGES PATRONALES (pour info) ===
    charge_cnas_patronale = models.DecimalField("CNAS patronale (26%)", max_digits=12, decimal_places=2, default=0)
    charge_cnr_patronale = models.DecimalField("CNR patronale (17.25%)", max_digits=12, decimal_places=2, default=0)
    charge_cnac_patronale = models.DecimalField("CNAC patronale (1%)", max_digits=12, decimal_places=2, default=0)
    total_charges_patronales = models.DecimalField("Total charges patronales", max_digits=12, decimal_places=2, default=0)
    
    # Coût total employeur
    cout_total_employeur = models.DecimalField("Coût total employeur", max_digits=12, decimal_places=2, default=0)
    
    # Statut
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    date_creation = models.DateTimeField("Date création", auto_now_add=True)
    date_validation = models.DateTimeField("Date validation", null=True, blank=True)
    valide_par = models.ForeignKey(
        Employee, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='bulletins_valides',
        verbose_name="Validé par"
    )
    date_paiement = models.DateField("Date de paiement", null=True, blank=True)
    mode_paiement = models.CharField(
        "Mode de paiement", max_length=20,
        choices=[('VIREMENT', 'Virement'), ('CHEQUE', 'Chèque'), ('ESPECES', 'Espèces')],
        default='VIREMENT'
    )
    
    notes = models.TextField("Notes", blank=True)
    
    class Meta:
        verbose_name = "Bulletin de paie"
        verbose_name_plural = "Bulletins de paie"
        unique_together = ['employee', 'mois', 'annee']
        ordering = ['-annee', '-mois', 'employee']
    
    def __str__(self):
        return f"{self.employee.nom_complet} - {self.mois:02d}/{self.annee}"
    
    def save(self, *args, **kwargs):
        # Générer référence
        if not self.reference:
            self.reference = f"BP-{self.annee}{self.mois:02d}-{self.employee.matricule}"
        super().save(*args, **kwargs)
    
    def calculer_irg(self, salaire_imposable):
        """Calcul de l'IRG selon le barème algérien 2024"""
        irg = 0
        reste = float(salaire_imposable)
        
        # Barème IRG mensuel
        tranches = [
            (20000, 0.00),      # 0 - 20 000 : 0%
            (20000, 0.23),      # 20 001 - 40 000 : 23%
            (40000, 0.27),      # 40 001 - 80 000 : 27%
            (80000, 0.30),      # 80 001 - 160 000 : 30%
            (160000, 0.33),     # 160 001 - 320 000 : 33%
            (float('inf'), 0.35),  # > 320 000 : 35%
        ]
        
        cumul = 0
        for plafond, taux in tranches:
            if reste <= 0:
                break
            
            montant_tranche = min(reste, plafond)
            irg += montant_tranche * taux
            reste -= montant_tranche
            cumul += plafond
        
        return round(irg, 2)
    
    def calculer(self):
        """Calcul complet du bulletin de paie"""
        from decimal import Decimal
        
        # === SALAIRE BRUT ===
        self.salaire_base = self.employee.salaire_base
        
        # Calcul heures supplémentaires
        taux_horaire = float(self.salaire_base) / 173.33  # 173.33h par mois
        self.heures_sup_montant = Decimal(str(round(
            (self.heures_supplementaires_25 * taux_horaire * 1.25) +
            (self.heures_supplementaires_50 * taux_horaire * 1.50) +
            (self.heures_supplementaires_100 * taux_horaire * 2.00),
            2
        )))
        
        # Prime de nuit (25% du taux horaire)
        self.prime_nuit = Decimal(str(round(self.heures_nuit * taux_horaire * 0.25, 2)))
        
        # Prime d'ancienneté (1% par an, max 15%)
        taux_anciennete = min(self.employee.anciennete_annees, 15) / 100
        self.prime_anciennete = Decimal(str(round(float(self.salaire_base) * taux_anciennete, 2)))
        
        # Salaire brut
        self.salaire_brut = (
            self.salaire_base +
            self.prime_rendement +
            self.prime_presence +
            self.prime_nuit +
            self.prime_anciennete +
            self.prime_transport +
            self.prime_panier +
            self.heures_sup_montant +
            self.autres_primes
        )
        
        # === COTISATIONS SALARIALES (16.25%) ===
        brut = float(self.salaire_brut)
        self.cotisation_cnas = Decimal(str(round(brut * 0.09, 2)))      # 9%
        self.cotisation_cnr = Decimal(str(round(brut * 0.0675, 2)))    # 6.75%
        self.cotisation_cnac = Decimal(str(round(brut * 0.005, 2)))    # 0.5%
        self.total_cotisations = self.cotisation_cnas + self.cotisation_cnr + self.cotisation_cnac
        
        # Salaire imposable
        self.salaire_imposable = self.salaire_brut - self.total_cotisations
        
        # === IRG ===
        self.irg = Decimal(str(self.calculer_irg(self.salaire_imposable)))
        
        # === RETENUES ===
        # Retenue pour absence
        if self.jours_absence > 0:
            salaire_journalier = float(self.salaire_base) / 26
            self.retenue_absence = Decimal(str(round(self.jours_absence * salaire_journalier, 2)))
        
        self.total_retenues = (
            self.retenue_absence +
            self.avance_salaire +
            self.pret +
            self.autres_retenues
        )
        
        # === SALAIRE NET ===
        self.salaire_net = (
            self.salaire_brut -
            self.total_cotisations -
            self.irg -
            self.total_retenues
        )
        
        # === CHARGES PATRONALES (34.5%) ===
        self.charge_cnas_patronale = Decimal(str(round(brut * 0.26, 2)))     # 26%
        self.charge_cnr_patronale = Decimal(str(round(brut * 0.1725, 2)))   # 17.25%
        self.charge_cnac_patronale = Decimal(str(round(brut * 0.01, 2)))    # 1%
        self.total_charges_patronales = (
            self.charge_cnas_patronale +
            self.charge_cnr_patronale +
            self.charge_cnac_patronale
        )
        
        # Coût total employeur
        self.cout_total_employeur = self.salaire_brut + self.total_charges_patronales
        
        self.statut = 'CALCULE'
        self.save()


# ===========================================================================
# --- PLANNING ET AFFECTATIONS ---
# ===========================================================================

class WorkSchedule(models.Model):
    """Planning de travail"""
    
    name = models.CharField("Nom du planning", max_length=100)
    date_debut = models.DateField("Date début")
    date_fin = models.DateField("Date fin")
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Département"
    )
    machine = models.ForeignKey(
        'Machine', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Machine"
    )
    notes = models.TextField("Notes", blank=True)
    is_active = models.BooleanField("Actif", default=True)
    cree_par = models.ForeignKey(
        Employee, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Créé par"
    )
    date_creation = models.DateTimeField("Date création", auto_now_add=True)
    
    class Meta:
        verbose_name = "Planning de travail"
        verbose_name_plural = "Plannings de travail"
        ordering = ['-date_debut']
    
    def __str__(self):
        return f"{self.name} ({self.date_debut} → {self.date_fin})"


class ShiftAssignment(models.Model):
    """Affectation employé à un shift"""
    
    schedule = models.ForeignKey(
        WorkSchedule, on_delete=models.CASCADE,
        related_name='affectations', verbose_name="Planning"
    )
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='affectations_shift', verbose_name="Employé"
    )
    shift = models.ForeignKey(
        Shift, on_delete=models.CASCADE,
        verbose_name="Équipe"
    )
    date = models.DateField("Date")
    machine = models.ForeignKey(
        'Machine', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Machine"
    )
    poste = models.CharField("Poste", max_length=50, blank=True)
    est_remplacement = models.BooleanField("Remplacement", default=False)
    remplace = models.ForeignKey(
        Employee, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='remplacements',
        verbose_name="Remplace"
    )
    notes = models.TextField("Notes", blank=True)
    
    class Meta:
        verbose_name = "Affectation shift"
        verbose_name_plural = "Affectations shifts"
        unique_together = ['employee', 'date']
        ordering = ['date', 'shift']
    
    def __str__(self):
        return f"{self.employee.nom_complet} - {self.date} - {self.shift.name}"


# ===========================================================================
# --- SANTÉ, SÉCURITÉ & INCIDENTS ---
# ===========================================================================

class MedicalVisit(models.Model):
    """Visites médicales"""
    
    TYPE_CHOICES = [
        ('EMBAUCHE', 'Visite d\'embauche'),
        ('PERIODIQUE', 'Visite périodique'),
        ('REPRISE', 'Visite de reprise'),
        ('SPONTANEE', 'Visite spontanée'),
    ]
    
    RESULTAT_CHOICES = [
        ('APTE', 'Apte'),
        ('APTE_RESTRICTION', 'Apte avec restrictions'),
        ('INAPTE_TEMPORAIRE', 'Inapte temporaire'),
        ('INAPTE', 'Inapte'),
    ]
    
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='visites_medicales', verbose_name="Employé"
    )
    type_visite = models.CharField("Type de visite", max_length=20, choices=TYPE_CHOICES)
    date_visite = models.DateField("Date de visite")
    medecin = models.CharField("Médecin", max_length=100, blank=True)
    resultat = models.CharField("Résultat", max_length=20, choices=RESULTAT_CHOICES, default='APTE')
    restrictions = models.TextField("Restrictions", blank=True)
    date_prochaine_visite = models.DateField("Prochaine visite", null=True, blank=True)
    certificat = models.FileField("Certificat médical", upload_to='medical/', blank=True, null=True)
    notes = models.TextField("Notes", blank=True)
    
    class Meta:
        verbose_name = "Visite médicale"
        verbose_name_plural = "Visites médicales"
        ordering = ['-date_visite']
    
    def __str__(self):
        return f"{self.employee.nom_complet} - {self.get_type_visite_display()} - {self.date_visite}"


class WorkIncident(models.Model):
    """Incidents de travail et accidents"""
    
    TYPE_CHOICES = [
        ('ACCIDENT', 'Accident de travail'),
        ('INCIDENT', 'Incident sans blessure'),
        ('PRESQUACCIDENT', 'Presqu\'accident'),
        ('MALADIE_PRO', 'Maladie professionnelle'),
    ]
    
    GRAVITE_CHOICES = [
        ('MINEURE', 'Mineure'),
        ('MODEREE', 'Modérée'),
        ('GRAVE', 'Grave'),
        ('TRES_GRAVE', 'Très grave'),
        ('MORTELLE', 'Mortelle'),
    ]
    
    reference = models.CharField("Référence", max_length=50, unique=True)
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='incidents', verbose_name="Employé concerné"
    )
    type_incident = models.CharField("Type", max_length=20, choices=TYPE_CHOICES)
    gravite = models.CharField("Gravité", max_length=20, choices=GRAVITE_CHOICES, default='MINEURE')
    
    date_incident = models.DateTimeField("Date et heure de l'incident")
    lieu = models.CharField("Lieu", max_length=200)
    machine = models.ForeignKey(
        'Machine', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Machine impliquée"
    )
    
    description = models.TextField("Description de l'incident")
    cause = models.TextField("Cause(s) identifiée(s)", blank=True)
    temoins = models.TextField("Témoins", blank=True)
    
    # Conséquences
    jours_arret = models.IntegerField("Jours d'arrêt", default=0)
    blessure = models.TextField("Nature de la blessure", blank=True)
    soins_prodigues = models.TextField("Soins prodigués", blank=True)
    
    # Actions
    actions_immediates = models.TextField("Actions immédiates", blank=True)
    actions_correctives = models.TextField("Actions correctives", blank=True)
    
    # Déclaration
    declare_cnas = models.BooleanField("Déclaré CNAS", default=False)
    date_declaration_cnas = models.DateField("Date déclaration CNAS", null=True, blank=True)
    num_declaration = models.CharField("N° déclaration", max_length=50, blank=True)
    
    # Documents
    rapport = models.FileField("Rapport d'accident", upload_to='incidents/', blank=True, null=True)
    photos = models.FileField("Photos", upload_to='incidents/photos/', blank=True, null=True)
    
    # Suivi
    cloture = models.BooleanField("Clôturé", default=False)
    date_cloture = models.DateField("Date de clôture", null=True, blank=True)
    
    date_creation = models.DateTimeField("Date création", auto_now_add=True)
    cree_par = models.ForeignKey(
        Employee, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='incidents_declares',
        verbose_name="Déclaré par"
    )
    
    class Meta:
        verbose_name = "Incident de travail"
        verbose_name_plural = "Incidents de travail"
        ordering = ['-date_incident']
    
    def __str__(self):
        return f"{self.reference} - {self.employee.nom_complet} - {self.get_type_incident_display()}"
    
    def save(self, *args, **kwargs):
        if not self.reference:
            year = timezone.now().strftime('%Y')
            last = WorkIncident.objects.filter(
                reference__startswith=f"INC{year}"
            ).order_by('-reference').first()
            if last:
                try:
                    num = int(last.reference[-4:]) + 1
                except ValueError:
                    num = 1
            else:
                num = 1
            self.reference = f"INC{year}{num:04d}"
        super().save(*args, **kwargs)


class ProtectiveEquipment(models.Model):
    """Équipements de protection individuelle (EPI)"""
    
    TYPE_CHOICES = [
        ('CASQUE', 'Casque'),
        ('LUNETTES', 'Lunettes de protection'),
        ('GANTS', 'Gants'),
        ('CHAUSSURES', 'Chaussures de sécurité'),
        ('GILET', 'Gilet de sécurité'),
        ('MASQUE', 'Masque'),
        ('BOUCHONS', 'Bouchons d\'oreilles'),
        ('COMBINAISON', 'Combinaison'),
        ('AUTRE', 'Autre'),
    ]
    
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE,
        related_name='equipements_protection', verbose_name="Employé"
    )
    type_equipement = models.CharField("Type", max_length=20, choices=TYPE_CHOICES)
    designation = models.CharField("Désignation", max_length=200)
    date_attribution = models.DateField("Date d'attribution", default=timezone.now)
    date_expiration = models.DateField("Date d'expiration", null=True, blank=True)
    quantite = models.IntegerField("Quantité", default=1)
    taille = models.CharField("Taille", max_length=20, blank=True)
    notes = models.TextField("Notes", blank=True)
    
    class Meta:
        verbose_name = "EPI"
        verbose_name_plural = "EPI"
        ordering = ['-date_attribution']
    
    def __str__(self):
        return f"{self.employee.nom_complet} - {self.designation}"
    
    @property
    def est_expire(self):
        if self.date_expiration:
            return timezone.now().date() > self.date_expiration
        return False
    
    # ===========================================================================
# --- CHAT EN TEMPS RÉEL ---
# ===========================================================================

class ChatRoom(models.Model):
    """Salons de discussion"""
    
    TYPE_CHOICES = [
        ('GENERAL', 'Général'),
        ('PRODUCTION', 'Production'),
        ('COMMERCIAL', 'Commercial'),
        ('TECHNIQUE', 'Technique'),
        ('URGENCE', 'Urgences'),
    ]
    
    name = models.CharField("Nom du salon", max_length=100)
    slug = models.SlugField("Slug", unique=True)
    type = models.CharField("Type", max_length=20, choices=TYPE_CHOICES, default='GENERAL')
    description = models.TextField("Description", blank=True)
    icone = models.CharField("Icône", max_length=10, default='💬')
    est_actif = models.BooleanField("Actif", default=True)
    date_creation = models.DateTimeField("Créé le", auto_now_add=True)
    membres = models.ManyToManyField(
        User, related_name='chat_rooms', blank=True,
        verbose_name="Membres"
    )
    
    class Meta:
        verbose_name = "Salon de chat"
        verbose_name_plural = "Salons de chat"
        ordering = ['type', 'name']
    
    def __str__(self):
        return f"{self.icone} {self.name}"
    
    def get_last_messages(self, limit=50):
        return self.messages.order_by('-date_envoi')[:limit][::-1]
    
    def get_online_users(self):
        """Retourne les utilisateurs connectés (simplifié)"""
        return self.membres.filter(is_active=True)


class ChatMessage(models.Model):
    """Messages du chat"""
    
    TYPE_CHOICES = [
        ('TEXT', 'Texte'),
        ('SYSTEM', 'Système'),
        ('ALERT', 'Alerte'),
        ('FILE', 'Fichier'),
    ]
    
    room = models.ForeignKey(
        ChatRoom, on_delete=models.CASCADE,
        related_name='messages', verbose_name="Salon"
    )
    auteur = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='chat_messages', verbose_name="Auteur"
    )
    contenu = models.TextField("Message")
    type_message = models.CharField(
        "Type", max_length=10,
        choices=TYPE_CHOICES, default='TEXT'
    )
    date_envoi = models.DateTimeField("Envoyé le", auto_now_add=True)
    lu_par = models.ManyToManyField(
        User, related_name='messages_lus', blank=True,
        verbose_name="Lu par"
    )
    fichier = models.FileField(
        "Fichier joint", upload_to='chat_files/',
        blank=True, null=True
    )
    
    # Lien optionnel vers un OF ou autre objet
    of_lie = models.ForeignKey(
        'OrdreFabrication', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="OF lié"
    )
    
    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['date_envoi']
    
    def __str__(self):
        return f"{self.auteur.username}: {self.contenu[:30]}..."
    
    def get_time_display(self):
        return self.date_envoi.strftime('%H:%M')
    
    def get_date_display(self):
        return self.date_envoi.strftime('%d/%m/%Y %H:%M')


class UserPresence(models.Model):
    """Présence des utilisateurs en ligne"""
    
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='presence', verbose_name="Utilisateur"
    )
    is_online = models.BooleanField("En ligne", default=False)
    last_seen = models.DateTimeField("Dernière activité", auto_now=True)
    current_room = models.ForeignKey(
        ChatRoom, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Salon actuel"
    )
    
    class Meta:
        verbose_name = "Présence utilisateur"
        verbose_name_plural = "Présences utilisateurs"
    
    def __str__(self):
        status = "🟢" if self.is_online else "⚫"
        return f"{status} {self.user.username}"