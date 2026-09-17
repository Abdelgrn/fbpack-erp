import datetime
import math
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta

class ProductionOrder(models.Model):
    of_number = models.CharField("N° OF", max_length=50, unique=True)
    client = models.ForeignKey('core.Client', on_delete=models.CASCADE)
    product = models.ForeignKey('core.TechnicalProduct', on_delete=models.CASCADE)
    machine = models.ForeignKey('core.Machine', on_delete=models.SET_NULL, null=True)
    quantity_planned = models.FloatField("Qté Prévue (kg/m)")
    start_time = models.DateTimeField("Début Prévu")
    end_time = models.DateTimeField("Fin Prévue")
    status = models.CharField(max_length=20, default='PLANNED', choices=[('PLANNED', 'Planifié'), ('IN_PROGRESS', 'En cours'), ('DONE', 'Terminé'), ('LATE', 'En Retard')])
    bat_file = models.FileField("BAT Validé", upload_to='bat/', blank=True, null=True)
    produced_qty = models.FloatField("Qté Produite", default=0)
    waste_qty = models.FloatField("Déchets (kg)", default=0)
    opportunite = models.ForeignKey('core.Opportunite', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Opportunité liée")

    class Meta:
        app_label = 'core'
        verbose_name = "Ordre de fabrication (ancien)"
        verbose_name_plural = "Ordres de fabrication (anciens)"


class ConsumptionLog(models.Model):
    of = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name='consumptions')
    material = models.ForeignKey('core.Material', on_delete=models.CASCADE)
    quantity_used = models.FloatField("Qté Consommée")


class PurchaseOrder(models.Model):
    supplier = models.ForeignKey('core.Supplier', on_delete=models.CASCADE)
    date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, default='DRAFT', choices=[('DRAFT', 'Brouillon'), ('SENT', 'Envoyée'), ('RECEIVED', 'Reçue')])
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        app_label = 'core'
        verbose_name = "Bon de commande"
        verbose_name_plural = "Bons de commande"


class Quote(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Brouillon'), ('SENT', 'Envoyé'),
        ('ACCEPTED', 'Accepté'), ('REFUSED', 'Refusé'),
        ('EXPIRED', 'Expiré'), ('SIGNED', 'Signé'),
    ]

    client = models.ForeignKey('core.Client', on_delete=models.CASCADE)
    opportunite = models.ForeignKey('core.Opportunite', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Opportunité liée")
    commercial = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Commercial")
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
        app_label = 'core'
        verbose_name = "Devis"
        verbose_name_plural = "Devis"
        ordering = ['-date', '-version']


class ProductionEntry(models.Model):
    EQUIPE_CHOICES = [('A', 'Équipe A'), ('B', 'Équipe B'), ('C', 'Équipe C')]
    TYPE_PROCESS_CHOICES = [
        ('FLEXO', 'Imprimeuse Flexo'),
        ('HELIO', 'Imprimeuse Hélio'),
        ('DECOUPE', 'Grande Découpe (DCM Panther 1350)'),
        ('DECOUPE2', 'Petite Découpe (DCM Panther 1)'),
        ('AUTRE', 'Autre Processus'),
    ]
    UNITE_COMMANDE_CHOICES = [
        ('UNITE', 'Pièces / Étiquettes / Sacs'),
        ('KG', 'Tonnage (KG / Tonnes)'),
        ('ML', 'Mètres Linéaires (ML)'),
    ]

    date = models.DateField("Date", default=timezone.now)
    produit = models.CharField("Produit", max_length=200)
    support = models.CharField("Support", max_length=100)
    quantite_lancee = models.FloatField("Quantité Lancée (kg)", default=0)
    lot = models.CharField("Lot", max_length=100, blank=True, db_index=True)
    laize = models.FloatField("Laize (mm)", default=0)
    client = models.ForeignKey('core.Client', on_delete=models.SET_NULL, null=True, blank=True)
    equipe = models.CharField("Équipe", max_length=5, choices=EQUIPE_CHOICES, default='A')
    machine = models.ForeignKey('core.Machine', on_delete=models.SET_NULL, null=True, blank=True)
    heure_debut = models.TimeField("Heure Début", null=True, blank=True)
    heure_fin = models.TimeField("Heure Fin", null=True, blank=True)
    prod_ml = models.FloatField("Prod ML", default=0)
    
    dechets_demarrage = models.FloatField("Déchets Démarrage (kg)", default=0)
    dechets_lisiere = models.FloatField("Déchets Lisière (kg)", default=0)
    dechets_jonction = models.FloatField("Déchets Jonction (kg)", default=0)
    dechets_transport = models.FloatField("Déchets Transport (kg)", default=0)
    prod_kg = models.FloatField("Prod KG", default=0)
    rebobinage_kg = models.FloatField("Rebobinage KG", default=0)

    unite_commande = models.CharField("Unité de Commande", max_length=10, choices=UNITE_COMMANDE_CHOICES, default='UNITE')
    quantite_commandee_unites = models.FloatField("Quantité Commandée", default=0, null=True, blank=True)
    grammage_g_m2 = models.FloatField("Grammage / Masse surfacique (g/m²)", default=0.0, null=True, blank=True)

    pas_mm = models.FloatField("Pas de coupe / Avance (mm)", default=275.0, null=True, blank=True)
    laize_produit_mm = models.FloatField("Laize Étiquette / Produit (mm)", default=65.0, null=True, blank=True)
    laize_bobine_mere_mm = models.FloatField("Laize Bobine Mère (mm)", default=825.0, null=True, blank=True)
    longueur_bobine_mere_m = models.FloatField("Longueur Bobine Mère (m)", default=10000.0, null=True, blank=True)
    vitesse_machine_trmin = models.FloatField("Vitesse Machine (tr/min ou m/min)", default=200.0, null=True, blank=True)
    temps_calage_min = models.IntegerField("Temps de Calage (min)", default=30, null=True, blank=True)
    type_process = models.CharField("Type Processus", max_length=20, choices=TYPE_PROCESS_CHOICES, default='FLEXO')

    of_lie = models.ForeignKey(
        'core.OrdreFabrication', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='saisies_production_anciennes', verbose_name="OF lié"
    )
    etape_liee = models.ForeignKey(
        'core.EtapeProduction', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='saisies_production_anciennes', verbose_name="Étape liée"
    )

    class Meta:
        app_label = 'core'
        verbose_name = "Saisie Production"
        verbose_name_plural = "Saisies Production"
        ordering = ['-date', '-heure_debut']

    def save(self, *args, **kwargs):
        if self.lot and not self.of_lie:
            OrdreFabrication = models.apps.get_model('core', 'OrdreFabrication')
            of = OrdreFabrication.chercher_par_lot(self.lot)
            if of:
                self.of_lie = of
        super().save(*args, **kwargs)

    @property
    def temps_ouverture(self):
        if self.heure_debut and self.heure_fin:
            dt_debut = datetime.datetime.combine(self.date, self.heure_debut)
            dt_fin = datetime.datetime.combine(self.date, self.heure_fin)
            if dt_fin < dt_debut: dt_fin += timedelta(days=1)
            diff = dt_fin - dt_debut
            total_seconds = int(diff.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}:{minutes:02d}"
        return "0:00"

    @property
    def temps_ouverture_minutes(self):
        if self.heure_debut and self.heure_fin:
            dt_debut = datetime.datetime.combine(self.date, self.heure_debut)
            dt_fin = datetime.datetime.combine(self.date, self.heure_fin)
            if dt_fin < dt_debut: dt_fin += timedelta(days=1)
            return (dt_fin - dt_debut).total_seconds() / 60
        return 0

    @property
    def total_dechets_kg(self):
        return round(
            self.dechets_demarrage + self.dechets_lisiere +
            self.dechets_jonction + self.dechets_transport, 2
        )

    @property
    def taux_dechets(self):
        if self.prod_kg == 0: return 0
        return round((self.total_dechets_kg / self.prod_kg) * 100, 2)

    @property
    def decalage(self):
        return round(self.prod_kg - self.quantite_lancee, 2)

    @property
    def nb_poses_largeur(self):
        laize_m = self.laize_bobine_mere_mm if self.laize_bobine_mere_mm and self.laize_bobine_mere_mm > 0 else self.laize
        laize_p = self.laize_produit_mm if self.laize_produit_mm and self.laize_produit_mm > 0 else 65.0
        if laize_p <= 0 or laize_m <= 0: return 1
        return max(1, math.floor(laize_m / laize_p))

    @property
    def metrage_total_necessaire_m(self):
        qty = self.quantite_commandee_unites if self.quantite_commandee_unites and self.quantite_commandee_unites > 0 else 0
        if self.unite_commande == 'ML':
            return round(qty, 2) if qty > 0 else round(self.prod_ml, 2)
        elif self.unite_commande == 'KG':
            laize_m = (self.laize_bobine_mere_mm if self.laize_bobine_mere_mm and self.laize_bobine_mere_mm > 0 else self.laize) / 1000.0
            grammage = self.grammage_g_m2 if self.grammage_g_m2 and self.grammage_g_m2 > 0 else 0
            qty_kg = qty if qty > 0 else self.quantite_lancee
            if qty_kg > 0 and laize_m > 0 and grammage > 0:
                return round((qty_kg * 1000.0 / grammage) / laize_m, 2)
            elif self.prod_ml > 0:
                return round(self.prod_ml, 2)
            return 0.0
        else:
            if qty > 0:
                pas = self.pas_mm if self.pas_mm and self.pas_mm > 0 else 275.0
                return round((qty / self.nb_poses_largeur) * (pas / 1000.0), 2)
            return round(self.prod_ml, 2)

    @property
    def nb_bobines_meres_necessaires(self):
        longuer_bm = self.longueur_bobine_mere_m if self.longueur_bobine_mere_m and self.longueur_bobine_mere_m > 0 else 10000.0
        if longuer_bm <= 0: return 1
        metrage = self.metrage_total_necessaire_m
        if metrage <= 0: return 1
        return math.ceil(metrage / longuer_bm)

    @property
    def nb_bobines_filles_totales(self):
        return self.nb_bobines_meres_necessaires * self.nb_poses_largeur

    @property
    def temps_estime_min(self):
        vitesse = self.vitesse_machine_trmin if self.vitesse_machine_trmin and self.vitesse_machine_trmin > 0 else 200.0
        calage = self.temps_calage_min if self.temps_calage_min else 30
        return round((self.metrage_total_necessaire_m / vitesse) + calage, 1)

    @property
    def temps_estime_formatted(self):
        tot_m = int(self.temps_estime_min)
        return f"{tot_m // 60}h {tot_m % 60:02d}min"

    @property
    def fin_estimee_24h(self):
        if not self.date: return None
        h_start = self.heure_debut if self.heure_debut else datetime.time(8, 0)
        return datetime.datetime.combine(self.date, h_start) + timedelta(minutes=int(self.temps_estime_min))


class CalculTempsProduction(models.Model):
    TYPE_PRODUIT_CHOICES = [
        ('ETIQUETTE', 'Étiquette (avec Pas & Poses)'),
        ('FILM_MONO', 'Film Mono-couche'),
        ('COMPLEXE', 'Film Complexe / Duplex / Triplex'),
        ('AUTRE', 'Autre produit sur bobine'),
    ]
    PROCESS_IMPRESSION_CHOICES = [
        ('FLEXO', 'Imprimeuse Flexo'),
        ('HELIO', 'Imprimeuse Hélio'),
        ('SANS', 'Sans Impression (Découpe seule)'),
    ]
    UNITE_QUANTITE_CHOICES = [
        ('UNITE', "Nombre d'Étiquettes / Pièces"),
        ('METRE', 'Mètres Linéaires (ML)'),
        ('KG', 'Kilogrammes (KG)'),
    ]

    nom_job = models.CharField("Nom du Job / Commande", max_length=200)
    client = models.ForeignKey('core.Client', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Client")
    type_produit = models.CharField("Type de Produit", max_length=20, choices=TYPE_PRODUIT_CHOICES, default='ETIQUETTE')
    quantite_commandee = models.FloatField("Quantité Commandée", default=1000000)
    unite_quantite = models.CharField("Unité Commandée", max_length=10, choices=UNITE_QUANTITE_CHOICES, default='UNITE')
    pas_mm = models.FloatField("Pas de coupe / Avance (mm)", default=275.0)
    laize_produit_mm = models.FloatField("Laize Produit / Étiquette (mm)", default=65.0)
    grammage_g_m2 = models.FloatField("Grammage / Masse surfacique (g/m²)", default=80.0)
    laize_bobine_mere_mm = models.FloatField("Laize Bobine Mère (mm)", default=825.0)
    longueur_bobine_mere_m = models.FloatField("Longueur Bobine Mère (m)", default=10000.0)
    process_impression = models.CharField("Process Impression", max_length=10, choices=PROCESS_IMPRESSION_CHOICES, default='FLEXO')
    machine_impression = models.ForeignKey('core.Machine', on_delete=models.SET_NULL, null=True, blank=True, related_name='calculs_impression', verbose_name="Machine Impression")
    vitesse_impression_mmin = models.FloatField("Vitesse Impression (m/min ou tr/min)", default=200.0)
    temps_calage_impression_min = models.IntegerField("Temps Calage Impression (min)", default=45)
    temps_decalage_bobine_min = models.IntegerField("Changement/Décalage par Bobine Mère (min)", default=10)
    machine_decoupe = models.ForeignKey('core.Machine', on_delete=models.SET_NULL, null=True, blank=True, related_name='calculs_decoupe', verbose_name="Machine Découpe")
    vitesse_decoupe_mmin = models.FloatField("Vitesse Découpe (m/min ou tr/min)", default=250.0)
    temps_calage_decoupe_min = models.IntegerField("Temps Calage Découpe (min)", default=20)
    temps_rebobinage_fille_min = models.IntegerField("Temps Évacuation/Rebobinage par Bobine Fille (min)", default=3)
    date_debut_prevue = models.DateTimeField("Date & Heure de Démarrage", default=timezone.now)
    date_calcul = models.DateTimeField("Calculé le", auto_now_add=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Créé par")
    notes = models.TextField("Notes / Observations", blank=True)

    class Meta:
        app_label = 'core'
