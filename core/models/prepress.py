from django.db import models
from django.utils import timezone


class TechnicalProduct(models.Model):
    client = models.ForeignKey(
        'core.Client', on_delete=models.CASCADE,
        related_name='produits_techniques',
        related_query_name='technicalproduct',
        verbose_name="Client"
    )
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
    artwork_file = models.FileField("Fichier Graphique / Fiche (AI/PDF)", upload_to='artwork/', blank=True)
    artwork_version = models.IntegerField(default=1)

    # Workflow BAT & Versionning
    BAT_STATUS_CHOICES = [
        ('ATTENTE', '⏳ En attente de BAT'),
        ('VALIDE', '✅ BAT Validé (Prêt)'),
        ('REFUSE', '❌ Suspendu / Obsolète'),
    ]
    bat_status = models.CharField("Statut BAT", max_length=20, choices=BAT_STATUS_CHOICES, default='ATTENTE')
    version = models.CharField("Version", max_length=20, default="V1.0")
    is_obsolete = models.BooleanField("Fiche Obsolète (Archivée)", default=False)

    date_creation = models.DateField("Date de création", default=timezone.now)
    tech_sheet_file = models.FileField("Fiche Technique Originale (PDF)", upload_to='tech_sheets/', blank=True, null=True)

    graveur = models.CharField("Graveur", max_length=150, blank=True, null=True)
    ref_graveur = models.CharField("Référence Graveur", max_length=150, blank=True, null=True)

    TYPE_DOSSIER_CHOICES = [
        ('NOUVEAU', 'Nouveau Dossier'),
        ('REGRAVURE_SIMPLE', 'Regravure Simple'),
        ('REGRAVURE_MODIF', 'Regravure Avec Modification'),
    ]
    type_dossier = models.CharField("Type de dossier", max_length=50, choices=TYPE_DOSSIER_CHOICES, default='NOUVEAU')

    nb_poses_pas = models.IntegerField("Nombre de poses (Pas)", default=1, null=True, blank=True)
    nb_poses_laize = models.IntegerField("Nombre de poses (Laize)", default=1, null=True, blank=True)
    developpement_mm = models.FloatField("Développement (mm)", default=0, null=True, blank=True)
    laize_gravure_mm = models.FloatField("Laize Gravure (mm)", default=0, null=True, blank=True)

    support_impression = models.CharField("Support d'impression", max_length=200, blank=True, null=True)
    impression = models.CharField("Impression", max_length=150, blank=True, null=True)
    spot = models.CharField("Spot (mm x mm)", max_length=100, blank=True, null=True)

    SENS_BOBINE_CHOICES = [(str(i), f"Sens {i}") for i in range(1, 9)]
    sens_bobine = models.CharField("Sens d'enroulement", max_length=2, choices=SENS_BOBINE_CHOICES, blank=True, null=True)

    SPOT_PLACEMENT_CHOICES = [
        ('1', 'Bas Gauche'),
        ('2', 'Bas Centre'),
        ('3', 'Bas Droite'),
        ('4', 'Haut Droite'),
    ]
    spot_placement = models.CharField(
        "Placement Spot", max_length=2, choices=SPOT_PLACEMENT_CHOICES, blank=True, null=True
    )

    class Meta:
        app_label = 'core'
        verbose_name = "Produit technique"
        verbose_name_plural = "Produits techniques"

    def __str__(self):
        return f"{self.ref_internal} - {self.name}"


class PrepressColor(models.Model):
    product = models.ForeignKey(TechnicalProduct, on_delete=models.CASCADE, related_name='couleurs_flexo')
    ordre = models.IntegerField("N°", default=1)
    nom_couleur = models.CharField("Couleurs (Ex: CYAN, MAGENTA...)", max_length=100)
    anilox = models.CharField("Anilox", max_length=100, blank=True, null=True)
    adhesif = models.CharField("Adhésif", max_length=100, blank=True, null=True)
    viscosite = models.CharField("Viscosité", max_length=100, blank=True, null=True)
    type_encre = models.CharField("Type Encre", max_length=150, blank=True, null=True)
    formule_encre = models.CharField("Formule Encre", max_length=250, blank=True, null=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Couleur Fiche Technique"
        verbose_name_plural = "Couleurs Fiche Technique"
        ordering = ['ordre']

    def __str__(self):
        return f"{self.ordre} - {self.nom_couleur} ({self.product.ref_internal})"


class Tooling(models.Model):
    TYPE_CHOICES = [('CYL', 'Cylindre Hélio'), ('CLICHE', 'Cliché Flexo')]
    product = models.ForeignKey(TechnicalProduct, on_delete=models.CASCADE)
    tool_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    serial_number = models.CharField("Code (Cliché/Cylindre)", max_length=100)
    max_impressions = models.IntegerField("Durée de vie théorique (tours)", default=1000000)
    date_creation = models.DateField("Date d'enregistrement", default=timezone.now)
    metrage_realise = models.FloatField("Métrage cumulé (ML)", default=0)
    current_impressions = models.IntegerField("Nombre de Tours (Calcul auto)", default=0)
    observations = models.TextField("Observations", blank=True, null=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Outillage cliché, cylindre"
        verbose_name_plural = "Outillages cliché, cylindre"

    def save(self, *args, **kwargs):
        # Formule Excel : Tours = Métrage / (Développement_mm * 0.001)
        if self.metrage_realise and self.product and self.product.developpement_mm:
            dev_en_metres = float(self.product.developpement_mm) * 0.001
            if dev_en_metres > 0:
                self.current_impressions = int(float(self.metrage_realise) / dev_en_metres)
        super().save(*args, **kwargs)

    @property
    def wear_percent(self):
        if self.max_impressions > 0:
            pct = (self.current_impressions / self.max_impressions) * 100
            return min(int(pct), 100)
        return 0