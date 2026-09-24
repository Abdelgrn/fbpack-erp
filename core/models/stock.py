from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class Supplier(models.Model):
    name = models.CharField("Fournisseur", max_length=200)
    email = models.EmailField()

    class Meta:
        app_label = 'core'
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
    code = models.CharField("Code Produit", max_length=100, blank=True, default='', db_index=True)
    category = models.CharField(max_length=10, choices=CAT_CHOICES)
    quantity = models.FloatField("Stock Réel")
    unit = models.CharField("Unité", max_length=10, default='kg')
    min_threshold = models.FloatField("Stock Alerte (Min)")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    price_per_unit = models.DecimalField("Prix Unitaire", max_digits=10, decimal_places=2, default=0)

    class Meta:
        app_label = 'core'
        verbose_name = "Matière première"
        verbose_name_plural = "Matières premières"

    def is_low_stock(self):
        return self.quantity <= self.min_threshold

    def __str__(self):
        return self.name


class StockLocation(models.Model):
    TYPE_CHOICES = [
        ('GENERAL', 'Magasin Général'), ('TAMPON', 'Stock Tampon'),
        ('PRODUCTION', 'Zone Production'), ('DECHET', 'Zone Déchets'),
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
        ('CONFORME', 'Conforme ✓'), ('BLOQUE', 'Bloqué ✗'),
        ('EN_ATTENTE', 'En attente contrôle'), ('QUARANTAINE', 'Quarantaine'),
    ]

    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='lots', verbose_name="Matière première")
    numero_lot = models.CharField("N° Lot fournisseur", max_length=100)
    date_reception = models.DateField("Date réception", default=timezone.now)
    fournisseur = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Fournisseur")
    emplacement = models.ForeignKey(StockLocation, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Emplacement")
    quantite_initiale = models.FloatField("Quantité initiale (kg)", default=0)
    quantite_restante = models.FloatField("Quantité restante (kg)", default=0)
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

    class Meta:
        app_label = 'core'
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ['-date']

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


class DemandeAchat(models.Model):
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'), ('SOUMISE', 'Soumise pour validation'),
        ('VALIDEE', 'Validée ✓'), ('REFUSEE', 'Refusée ✗'),
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


class BonCommande(models.Model):
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'), ('ENVOYE', 'Envoyé fournisseur'),
        ('CONFIRME', 'Confirmé'), ('RECU_PARTIEL', 'Reçu partiellement'),
        ('RECU_TOTAL', 'Reçu totalement'), ('ANNULE', 'Annulé'),
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


class LigneBonCommande(models.Model):
    bon_commande = models.ForeignKey(BonCommande, on_delete=models.CASCADE, related_name='lignes')
    material = models.ForeignKey(Material, on_delete=models.CASCADE, verbose_name="Matière")
    quantite_commandee = models.FloatField("Quantité commandée (kg)")
    quantite_recue = models.FloatField("Quantité reçue (kg)", default=0)
    prix_unitaire = models.DecimalField("Prix unitaire (DA/kg)", max_digits=10, decimal_places=2, default=0)

    class Meta:
        app_label = 'core'
        verbose_name = "Ligne BC"


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