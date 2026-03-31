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

    # Infos de base
    name = models.CharField("Raison Sociale", max_length=200)
    code_client = models.CharField("Code Client Interne", max_length=50, blank=True, unique=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROSPECT')

    # Champs avancés (nouveaux)
    segment = models.CharField("Segment d'activité", max_length=20, choices=SEGMENT_CHOICES, default='FLEXO')
    size = models.CharField("Taille du client", max_length=10, choices=SIZE_CHOICES, blank=True)
    region = models.CharField("Région / Zone", max_length=10, choices=REGION_CHOICES, blank=True)
    ca_estime = models.DecimalField("CA Estimé (DA)", max_digits=14, decimal_places=2, default=0)

    # Coordonnées
    sector = models.CharField("Secteur d'activité", max_length=100, blank=True)
    city = models.CharField("Ville", max_length=100)
    address = models.TextField("Adresse complète", blank=True)
    phone = models.CharField("Téléphone", max_length=50)
    email = models.EmailField(blank=True)
    website = models.URLField("Site web", blank=True)

    # Suivi
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
    valeur_estimee = models.DecimalField("Valeur Estimée (DA)", max_digits=14, decimal_places=2, default=0)
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
    name = models.CharField("Nom Machine", max_length=100)
    type = models.CharField(
        max_length=50,
        choices=[('EXT', 'Extrudeuse'), ('IMP', 'Imprimeuse'), ('DEC', 'Découpeuse')]
    )
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
# --- C. PRODUCTION (Planning & OF) ---
# ===========================================================================

class ProductionOrder(models.Model):
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

    # Lien avec opportunité
    opportunite = models.ForeignKey(
        'Opportunite', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Opportunité liée"
    )

    class Meta:
        verbose_name = "Ordre de fabrication"
        verbose_name_plural = "Ordres de fabrication"

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
# --- DEVIS (amélioré) ---
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

    # Conversion en commande
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
