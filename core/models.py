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