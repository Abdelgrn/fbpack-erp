from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Sum

class Atelier(models.Model):
    ATELIER_CHOICES = [
        ('EXTRUSION', 'Atelier Extrusion'), ('IMPRESSION', 'Atelier Impression'),
        ('COMPLEXAGE', 'Atelier Complexage'), ('DECOUPE', 'Atelier Découpe'),
        ('SACS', 'Atelier Sacs'), ('NETTOYAGE', 'Atelier Nettoyage'),
        ('AUTRE', 'Autre'),
    ]

    nom = models.CharField("Nom de l'atelier", max_length=100)
    code = models.CharField("Code", max_length=20, unique=True)
    type_atelier = models.CharField("Type", max_length=20, choices=ATELIER_CHOICES, default='AUTRE')
    description = models.TextField("Description", blank=True)
    responsable = models.ForeignKey('core.Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='ateliers_geres', verbose_name="Responsable")
    ordre_affichage = models.IntegerField("Ordre d'affichage", default=0)
    icone = models.CharField("Icône", max_length=10, default='🏭')
    couleur = models.CharField("Couleur", max_length=7, default='#3b82f6')
    est_actif = models.BooleanField("Actif", default=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Atelier"
        verbose_name_plural = "Ateliers"
        ordering = ['ordre_affichage', 'nom']

    def __str__(self):
        return f"{self.icone} {self.nom}"


class Machine(models.Model):
    STATUS_CHOICES = [
        ('RUN', 'En Production'), ('STOP', 'Arrêt'),
        ('MAINT', 'Maintenance'), ('PANNE', 'En Panne'),
    ]
    TYPE_CHOICES = [
        ('EXT', 'Extrudeuse'), ('IMP', 'Imprimeuse Flexo'),
        ('HELIO', 'Imprimeuse Hélio'), ('COMP', 'Complexeuse'),
        ('DEC', 'Grande Découpe'), ('DEC2', 'Petite Découpe'),
        ('SAC_FC', 'Machine Fond Carré'), ('SAC_SO', 'Machine Soudure'),
        ('NETT_CL', 'Nettoyage Cliché'), ('NETT_AN', 'Nettoyage Anilox'),
        ('AUTRE', 'Autre'),
    ]
    CRITICITE_CHOICES = [
        ('A', 'Critique (A)'), ('B', 'Important (B)'), ('C', 'Standard (C)'),
    ]

    code_machine = models.CharField("Code Machine", max_length=50, unique=True, blank=True)
    name = models.CharField("Nom Machine", max_length=100)
    type = models.CharField("Type", max_length=50, choices=TYPE_CHOICES)
    atelier = models.ForeignKey(Atelier, on_delete=models.SET_NULL, null=True, blank=True, related_name='machines_atelier', verbose_name="Atelier")

    marque = models.CharField("Marque", max_length=100, blank=True)
    modele = models.CharField("Modèle", max_length=100, blank=True)
    numero_serie = models.CharField("N° Série", max_length=100, blank=True)
    annee_fabrication = models.IntegerField("Année de fabrication", null=True, blank=True)
    date_mise_en_service = models.DateField("Date de mise en service", null=True, blank=True)
    fournisseur_machine = models.ForeignKey('core.Supplier', on_delete=models.SET_NULL, null=True, blank=True, related_name='machines_fournies', verbose_name="Fournisseur machine")

    compteur_heures = models.FloatField("Compteur heures machine", default=0)
    compteur_metres = models.FloatField("Compteur mètres produits", default=0)
    compteur_tours = models.FloatField("Compteur tours/cycles", default=0)
    date_dernier_releve = models.DateTimeField("Dernier relevé compteur", null=True, blank=True)

    puissance_kw = models.FloatField("Puissance (kW)", default=0, null=True, blank=True)
    vitesse_max = models.FloatField("Vitesse max (m/min)", default=0, null=True, blank=True)
    laize_max = models.FloatField("Laize max (mm)", default=0, null=True, blank=True)
    laize_min = models.FloatField("Laize min (mm)", default=0, null=True, blank=True)
    nb_couleurs = models.IntegerField("Nb couleurs (impression)", default=0, null=True, blank=True)

    status = models.CharField("Statut", max_length=10, choices=STATUS_CHOICES, default='STOP')
    criticite = models.CharField("Criticité", max_length=1, choices=CRITICITE_CHOICES, default='B')

    photo = models.ImageField("Photo", upload_to='machines/photos/', blank=True, null=True)
    documentation = models.FileField("Documentation technique", upload_to='machines/docs/', blank=True, null=True)

    cout_acquisition = models.DecimalField("Coût d'acquisition (DA)", max_digits=14, decimal_places=2, default=0)
    cout_horaire = models.DecimalField("Coût horaire (DA/h)", max_digits=10, decimal_places=2, default=0)

    notes = models.TextField("Notes", blank=True)
    est_active = models.BooleanField("Active", default=True)
    date_creation = models.DateTimeField("Date création fiche", auto_now_add=True, null=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Machine"
        verbose_name_plural = "Machines"
        ordering = ['atelier', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.code_machine:
            prefix = self.type if self.type else 'MCH'
            last = Machine.objects.filter(code_machine__startswith=prefix).order_by('-code_machine').first()
            if last and last.code_machine:
                try: num = int(last.code_machine.replace(prefix + '-', '')) + 1
                except (ValueError, IndexError): num = 1
            else: num = 1
            self.code_machine = f"{prefix}-{num:03d}"
        super().save(*args, **kwargs)

    @property
    def age_annees(self):
        if self.date_mise_en_service:
            delta = timezone.now().date() - self.date_mise_en_service
            return round(delta.days / 365, 1)
        return None

    @property
    def nb_pannes_total(self):
        return self.ordres_maintenance.filter(type_maintenance='CORRECTIVE').count()

    @property
    def nb_pannes_mois(self):
        debut_mois = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.ordres_maintenance.filter(type_maintenance='CORRECTIVE', date_creation__gte=debut_mois).count()

    @property
    def temps_arret_total_heures(self):
        total_min = self.ordres_maintenance.aggregate(t=Sum('temps_arret_minutes'))['t'] or 0
        return round(total_min / 60, 1)

    @property
    def peut_creer_of(self):
        if self.status == 'PANNE':
            return False, "🔴 MACHINE EN PANNE — Impossible de créer un OF"
        om_ameliorative = self.ordres_maintenance.filter(type_maintenance='AMELIORATIVE', statut__in=['OUVERT', 'EN_COURS']).first()
        if om_ameliorative:
            return False, f"🔴 MAINTENANCE AMÉLIORATIVE EN COURS (OM-{om_ameliorative.numero_om})"
        om_preventif = self.ordres_maintenance.filter(type_maintenance__in=['PREVENTIVE', 'PREDICTIVE'], statut__in=['OUVERT', 'EN_COURS']).first()
        if om_preventif:
            return True, f"⚠️ AVERTISSEMENT : Maintenance {om_preventif.get_type_maintenance_display()} en cours."
        return True, ""

    @property
    def om_actif(self):
        return self.ordres_maintenance.filter(statut__in=['OUVERT', 'EN_COURS', 'EN_ATTENTE_PIECE']).order_by('-date_creation').first()


class CompteurMachine(models.Model):
    TYPE_COMPTEUR = [
        ('HEURES', 'Heures machine'),
        ('METRES', 'Mètres produits'),
        ('TOURS', 'Tours / Cycles'),
    ]
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='releves_compteur', verbose_name="Machine")
    type_compteur = models.CharField("Type", max_length=10, choices=TYPE_COMPTEUR)
    valeur = models.FloatField("Valeur du compteur")
    date_releve = models.DateTimeField("Date du relevé", default=timezone.now)
    releve_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Relevé par")
    notes = models.TextField("Notes", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Relevé compteur"
        verbose_name_plural = "Relevés compteurs"
        ordering = ['-date_releve']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.type_compteur == 'HEURES': self.machine.compteur_heures = self.valeur
        elif self.type_compteur == 'METRES': self.machine.compteur_metres = self.valeur
        elif self.type_compteur == 'TOURS': self.machine.compteur_tours = self.valeur
        self.machine.date_dernier_releve = self.date_releve
        self.machine.save(update_fields=['compteur_heures', 'compteur_metres', 'compteur_tours', 'date_dernier_releve'])