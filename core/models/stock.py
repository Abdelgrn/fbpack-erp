from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Sum, F

class Supplier(models.Model):
    name = models.CharField("Fournisseur", max_length=200)
    email = models.EmailField(blank=True, default='')
    is_archived = models.BooleanField("Archivé", default=False)

    class Meta:
        app_label = 'core'
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"

    def __str__(self):
        return self.name

    @property
    def nb_lots(self):
        return self.stocklot_set.filter(quantite_restante__gt=0).count()


class SupplierContact(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='contacts')
    nom = models.CharField("Nom Complet", max_length=150)
    poste = models.CharField("Poste / Rôle", max_length=100, blank=True)
    telephone = models.CharField("Téléphone", max_length=50, blank=True)
    email = models.EmailField("Email Direct", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Contact Fournisseur"
        verbose_name_plural = "Contacts Fournisseurs"

    def __str__(self):
        return f"{self.nom} ({self.supplier.name})"


class Material(models.Model):
    CAT_CHOICES = [
        ('FILM', 'Film/Papier'),
        ('INK', 'Encre'),
        ('GLUE', 'Colle'),
        ('SOLV', 'Solvant'),
    ]
    name = models.CharField("Désignation", max_length=200)
    code = models.CharField("Code Produit", max_length=100, blank=True, default='', db_index=True)
    category = models.CharField(max_length=10, choices=CAT_CHOICES)
    initial_quantity = models.FloatField("Stock Initial (au départ)", default=0)
    quantity = models.FloatField("Stock Réel")  # Représente le stock physique total en Magasin Général
    unit = models.CharField("Unité", max_length=10, default='kg')
    min_threshold = models.FloatField("Stock Alerte (Min)")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    price_per_unit = models.DecimalField("Prix Unitaire", max_digits=10, decimal_places=2, default=0)
    is_archived = models.BooleanField("Archivé", default=False)
    created_at = models.DateTimeField("Date de création", default=timezone.now)

    class Meta:
        app_label = 'core'
        verbose_name = "Matière première"
        verbose_name_plural = "Matières premières"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name

    def is_low_stock(self):
        return self.usable_quantity <= self.min_threshold

    @property
    def level_status(self):
        qty = self.usable_quantity
        if qty <= 0:
            return 'RUPTURE'
        if qty <= (self.min_threshold * 0.5):
            return 'CRITIQUE'
        if qty <= self.min_threshold:
            return 'ALERTE'
        return 'OK'

    @property
    def usable_quantity(self):
        # Uniquement les lots CONFORMES sont utilisables par la production
        total = self.lots.filter(statut='CONFORME').aggregate(total=Sum('quantite_restante'))['total'] or 0.0
        return float(total)

    @property
    def quantite_bloquee(self):
        # Lots bloqués, en quarantaine ou en attente de contrôle
        total = self.lots.exclude(statut='CONFORME').aggregate(total=Sum('quantite_restante'))['total'] or 0.0
        return float(total)

    def get_fefo_lots(self):
        # FEFO: Expire le plus tôt en premier. Si pas de date d'expiration, FIFO (date de réception)
        return self.lots.filter(statut='CONFORME', quantite_restante__gt=0).order_by(
            F('date_expiration').asc(nulls_last=True),
            'date_reception'
        )


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
        app_label = 'core'
        verbose_name = "Emplacement Stock"
        verbose_name_plural = "Emplacements Stock"

    def __str__(self):
        return self.name


class StockLot(models.Model):
    STATUT_CHOICES = [
        ('CONFORME', 'Conforme ✓'), 
        ('BLOQUE', 'Bloqué ✗'),
        ('EN_ATTENTE', 'En attente contrôle'), 
        ('QUARANTAINE', 'Quarantaine'),
    ]

    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='lots', verbose_name="Matière première")
    numero_lot = models.CharField("N° Lot fournisseur", max_length=100)
    date_reception = models.DateField("Date réception", default=timezone.now)
    fournisseur = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Fournisseur")
    emplacement = models.ForeignKey(StockLocation, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Emplacement")
    quantite_initiale = models.FloatField("Quantité initiale (kg)", default=0)
    quantite_restante = models.FloatField("Quantité restante (kg)", default=0)
    laize = models.IntegerField("Laize / Width (mm)", null=True, blank=True)
    longueur = models.IntegerField("Longueur / Length (m)", null=True, blank=True)
    prix_unitaire = models.DecimalField("Prix unitaire (DA/kg)", max_digits=10, decimal_places=2, default=0)
    statut = models.CharField("Statut qualité", max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    certificat_qualite = models.FileField("Certificat qualité (PDF)", upload_to='certificats/', blank=True, null=True)
    notes = models.TextField("Notes / Remarques", blank=True)
    date_expiration = models.DateField("Date expiration", null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Créé par")

    class Meta:
        app_label = 'core'
        verbose_name = "Lot de stock"
        verbose_name_plural = "Lots de stock"
        ordering = ['-date_reception']

    def __str__(self):
        return f"Lot {self.numero_lot} ({self.material.name})"

    @property
    def taux_consommation(self):
        if self.quantite_initiale <= 0:
            return 100
        taux = ((self.quantite_initiale - self.quantite_restante) / self.quantite_initiale) * 100
        return round(max(0, min(100, taux)), 1)

    @property
    def valeur_stock(self):
        return round(float(self.quantite_restante) * float(self.prix_unitaire), 2)

    @property
    def jours_avant_expiration(self):
        if not self.date_expiration:
            return 9999
        delta = self.date_expiration - timezone.now().date()
        return delta.days

    @property
    def is_expire(self):
        if not self.date_expiration:
            return False
        return self.date_expiration < timezone.now().date()


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
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='mouvements', verbose_name="Matière")
    lot = models.ForeignKey(StockLot, on_delete=models.SET_NULL, null=True, blank=True, related_name='mouvements', verbose_name="Lot")
    quantite = models.FloatField("Quantité (kg)")
    emplacement_source = models.ForeignKey(StockLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name='mouvements_sortie', verbose_name="Emplacement source")
    emplacement_destination = models.ForeignKey(StockLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name='mouvements_entree', verbose_name="Emplacement destination")
    of = models.ForeignKey('core.OrdreFabrication', on_delete=models.SET_NULL, null=True, blank=True, related_name='mouvements_stock', verbose_name="OF lié")
    machine = models.ForeignKey('core.Machine', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Machine")
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Utilisateur")
    motif = models.CharField("Motif / Référence", max_length=200, blank=True)
    notes = models.TextField("Notes", blank=True)
    annule = models.BooleanField("Annulé", default=False)
    motif_annulation = models.CharField("Motif d'annulation", max_length=200, blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ['-date']

    def __str__(self):
        return f"{self.type} - {self.quantite} kg ({self.material.name})"

    @property
    def sens(self):
        if self.annule:
            return 0
        if self.type in ['ENTREE']:
            return 1
        elif self.type in ['SORTIE', 'PERTE', 'RETOUR']:
            return -1
        return 0


class DemandeAchat(models.Model):
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'), 
        ('SOUMISE', 'Soumise pour validation'),
        ('VALIDEE', 'Validée ✓'), 
        ('REFUSEE', 'Refusée ✗'),
        ('COMMANDEE', 'Bon de commande émis'),
    ]
    URGENCE_CHOICES = [('NORMALE', 'Normale'), ('URGENTE', 'Urgente'), ('CRITIQUE', 'Critique !!')]

    reference = models.CharField("Référence DA", max_length=50, unique=True)
    material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name="Matière demandée")
    quantite_demandee = models.FloatField("Quantité demandée (kg)")
    motif = models.TextField("Motif de la demande", blank=True)
    urgence = models.CharField("Niveau d'urgence", max_length=10, choices=URGENCE_CHOICES, default='NORMALE')
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    demandeur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='demandes_achat', verbose_name="Demandeur")
    valideur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='validations_achat', verbose_name="Validé par")
    date_creation = models.DateField("Date création", default=timezone.now)
    date_validation = models.DateField("Date validation", null=True, blank=True)
    date_besoin = models.DateField("Date besoin souhaitée", null=True, blank=True)
    bon_commande = models.ForeignKey('core.BonCommande', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="BC généré")

    class Meta:
        app_label = 'core'
        verbose_name = "Demande d'achat"
        verbose_name_plural = "Demandes d'achat"
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.reference} - {self.material.name}"


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
    fournisseur = models.ForeignKey(Supplier, on_delete=models.CASCADE, verbose_name="Fournisseur")
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    date_commande = models.DateField("Date commande", default=timezone.now)
    date_livraison_prevue = models.DateField("Livraison prévue", null=True, blank=True)
    date_livraison_reelle = models.DateField("Livraison réelle", null=True, blank=True)
    montant_total = models.DecimalField("Montant total (DA)", max_digits=14, decimal_places=2, default=0)
    notes = models.TextField("Notes / Conditions", blank=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Créé par")

    class Meta:
        app_label = 'core'
        verbose_name = "Bon de commande"
        verbose_name_plural = "Bons de commande"
        ordering = ['-date_commande']

    def __str__(self):
        return f"{self.reference} - {self.fournisseur.name}"

    @property
    def nb(self):
        return self.lignes.count()


class LigneBonCommande(models.Model):
    bon_commande = models.ForeignKey(BonCommande, on_delete=models.CASCADE, related_name='lignes')
    material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name="Matière")
    quantite_commandee = models.FloatField("Quantité commandée (kg)")
    quantite_recue = models.FloatField("Quantité reçue (kg)", default=0)
    prix_unitaire = models.DecimalField("Prix unitaire (DA/kg)", max_digits=10, decimal_places=2, default=0)

    class Meta:
        app_label = 'core'
        verbose_name = "Ligne BC"

    def __str__(self):
        return f"{self.material.name} ({self.quantite_commandee} kg)"


class StockSeuil(models.Model):
    material = models.OneToOneField(Material, on_delete=models.CASCADE, related_name='seuil_intelligent', verbose_name="Matière")
    consommation_journaliere_moy = models.FloatField("Conso. moyenne/jour (kg)", default=0)
    delai_fournisseur_jours = models.IntegerField("Délai fournisseur (jours)", default=7)
    stock_securite_jours = models.IntegerField("Jours de sécurité supplémentaires", default=3)
    derniere_maj = models.DateTimeField("Dernière mise à jour", auto_now=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Seuil intelligent"
        verbose_name_plural = "Seuils intelligents"

    @property
    def seuil_calcule(self):
        res = (self.delai_fournisseur_jours + self.stock_securite_jours) * self.consommation_journaliere_moy
        return round(res, 1)

    @property
    def jours_de_stock(self):
        if self.consommation_journaliere_moy <= 0:
            return 999.0
        return round(self.material.usable_quantity / self.consommation_journaliere_moy, 1)

    @property
    def date_rupture_prevue(self):
        j = self.jours_de_stock
        if j >= 999.0:
            return None
        return timezone.now().date() + timezone.timedelta(days=int(j))