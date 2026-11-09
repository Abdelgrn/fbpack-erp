from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Sum, F
from django.db.models.functions import Coalesce

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


class StockCatalogOption(models.Model):
    """Valeurs configurables des listes articles, historisées par désactivation."""
    KIND_CHOICES = [
        ('UNIT', 'Unité'), ('DEPOT', 'Dépôt'),
        ('FAMILY', 'Famille'), ('SUBFAMILY', 'Sous-famille'),
    ]
    kind = models.CharField('Type de liste', max_length=12, choices=KIND_CHOICES, db_index=True)
    name = models.CharField('Libellé', max_length=120)
    active = models.BooleanField('Actif', default=True)
    position = models.PositiveSmallIntegerField('Ordre', default=0)

    class Meta:
        app_label = 'core'
        verbose_name = 'Valeur de catalogue stock'
        verbose_name_plural = 'Valeurs de catalogue stock'
        ordering = ['kind', 'position', 'name']
        constraints = [models.UniqueConstraint(fields=['kind', 'name'], name='uniq_stock_cat_kind_name')]

    def __str__(self):
        return self.name


class Material(models.Model):
    ORIGINE_CHOICES = [('IMPORTATION', 'Importation'), ('LOCAL', 'Local')]
    CAT_CHOICES = [
        ('FILM', 'Film/Papier'),
        ('INK', 'Encre'),
        ('GLUE', 'Colle'),
        ('SOLV', 'Solvant'),
    ]
    name = models.CharField("Désignation", max_length=200)
    code = models.CharField("Code Produit", max_length=100, blank=True, default='', db_index=True)
    category = models.CharField(max_length=10, choices=CAT_CHOICES)
    
    # --- MOTEUR TECHNIQUE & AUTO-CLASSIFICATION ---
    densite_iso = models.FloatField("Densité (g/cm³) ISO", default=1.0, help_text="OPP=0.91, PET=1.39, PE=0.92, ALU=2.70, PAPIER=1.0")
    micronage_standard = models.IntegerField("Micronage (µm)", null=True, blank=True, help_text="Ex: 12, 15, 20, 30, 40...")
    grammage = models.FloatField("Grammage (g/m²)", null=True, blank=True, help_text="Ex: 70, 80, 90 g/m² (Papiers/Cartons)")
    metrage_standard = models.FloatField("Métrage / Longueur (m)", null=True, blank=True, help_text="Métrage standard de la bobine en mètres")
    laize_mm = models.PositiveIntegerField("Laize (mm)", null=True, blank=True)
    origine = models.CharField("Origine", max_length=15, choices=ORIGINE_CHOICES, blank=True, default='')
    poids_kg = models.FloatField("Poids (kg)", null=True, blank=True)
    nombre_unites = models.PositiveIntegerField("Nombre d’unités", null=True, blank=True)
    
    # NOUVEAU CHAMP : Le tag automatique
    sous_categorie = models.CharField("Sous-catégorie (Auto)", max_length=50, blank=True, null=True)
    # ----------------------------------------------

    initial_quantity = models.FloatField("Stock Initial (au départ)", default=0)
    quantity = models.FloatField("Stock Réel")  # Représente le stock physique total en Magasin Général
    unit = models.CharField("Unité", max_length=10, default='KG')
    depot = models.ForeignKey(StockCatalogOption, on_delete=models.SET_NULL, null=True, blank=True, related_name='materials_depot', limit_choices_to={'kind': 'DEPOT'}, verbose_name='Dépôt')
    famille = models.ForeignKey(StockCatalogOption, on_delete=models.SET_NULL, null=True, blank=True, related_name='materials_family', limit_choices_to={'kind': 'FAMILY'}, verbose_name='Famille')
    sous_famille = models.ForeignKey(StockCatalogOption, on_delete=models.SET_NULL, null=True, blank=True, related_name='materials_subfamily', limit_choices_to={'kind': 'SUBFAMILY'}, verbose_name='Sous-famille')
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

    # =========================================================================
    # LE CERVEAU D'AUTO-CLASSIFICATION À CHAQUE SAUVEGARDE
    # =========================================================================
    def save(self, *args, **kwargs):
        if self.category == 'FILM' and self.name:
            n = self.name.upper()
            if 'KRAFT' in n:
                self.sous_categorie = 'KRAFT'
            elif 'COUCH' in n:
                self.sous_categorie = 'COUCHÉ'
            elif 'PAPIER' in n or 'PAPER' in n:
                self.sous_categorie = 'PAPIER'
            elif 'ALU' in n or 'ALUMINIUM' in n:
                self.sous_categorie = 'ALUMINIUM'
            elif 'PET' in n or 'POLYESTER' in n:
                self.sous_categorie = 'PET'
            elif 'PEHD' in n or 'HDPE' in n:
                self.sous_categorie = 'PEHD'
            elif 'PE ' in n or 'LDPE' in n or 'LLDPE' in n or n.startswith('PE-') or n.startswith('PE'):
                self.sous_categorie = 'PE'
            elif 'OPP' in n or 'BOPP' in n:
                self.sous_categorie = 'BOPP'
            else:
                self.sous_categorie = 'AUTRE'
        elif self.category != 'FILM':
            self.sous_categorie = None  # On vide la sous-catégorie si c'est une encre/colle/solvant
            
        super().save(*args, **kwargs)
    # =========================================================================

    def is_low_stock(self):
        """Compare l’alerte au Stock Réel affiché sur la fiche matière.

        Les lots conformes restent la source de vérité pour autoriser une sortie,
        mais un article sans lot ne doit pas être marqué en alerte si son stock
        physique enregistré dépasse le seuil.
        """
        return float(self.quantity or 0) <= float(self.min_threshold or 0)

    @property
    def level_status(self):
        qty = float(self.quantity or 0)
        if qty <= 0:
            return 'RUPTURE'
        if qty <= (self.min_threshold * 0.5):
            return 'CRITIQUE'
        if qty <= self.min_threshold:
            return 'ALERTE'
        return 'OK'

    @property
    def usable_quantity(self):
        # Les vues de listes/KPI annotent le total conforme en une seule requête.
        # On réutilise cette valeur pour éviter une agrégation SQL par article.
        cached_total = getattr(self, 'usable_quantity_cached', None)
        if cached_total is not None:
            return float(cached_total or 0.0)
        total = self.lots.filter(statut='CONFORME').aggregate(total=Sum('quantite_restante'))['total'] or 0.0
        return float(total)

    @property
    def quantite_bloquee(self):
        total = self.lots.exclude(statut='CONFORME').aggregate(total=Sum('quantite_restante'))['total'] or 0.0
        return float(total)

    @property
    def thickness_or_grammage_display(self):
        if self.micronage_standard:
            return f"{self.micronage_standard} µm"
        elif self.grammage:
            return f"{self.grammage:.1f}".rstrip('0').rstrip('.') + " g/m²"
        return "—"

    @property
    def metrage_display(self):
        if self.metrage_standard:
            return f"{int(self.metrage_standard) if self.metrage_standard.is_integer() else self.metrage_standard} m"
        return "—"

    def get_fefo_lots(self):
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
    micronage = models.PositiveIntegerField("Micronage (µm)", null=True, blank=True)
    grammage = models.FloatField("Grammage (g/m²)", null=True, blank=True)
    metrage = models.FloatField("Métrage (m)", null=True, blank=True)
    poids_kg = models.FloatField("Poids net (kg)", null=True, blank=True)
    nombre_unites = models.PositiveIntegerField("Nombre d’unités", null=True, blank=True)
    origine = models.CharField("Origine", max_length=15, choices=Material.ORIGINE_CHOICES, blank=True, default='')
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
        ('RETOUR_INTERNE', 'Retour interne (atelier → magasin)'),
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
    laize_mm = models.PositiveIntegerField('Laize mouvement (mm)', null=True, blank=True)
    micronage = models.PositiveIntegerField('Micronage mouvement (µm)', null=True, blank=True)
    metrage = models.FloatField('Métrage mouvement (m)', null=True, blank=True)
    poids_kg = models.FloatField('Poids par article (kg)', null=True, blank=True)
    nombre_unites = models.PositiveIntegerField('Nombre d’articles', null=True, blank=True)
    notes = models.TextField("Notes", blank=True)
    annule = models.BooleanField("Annulé", default=False)
    motif_annulation = models.CharField("Motif d'annulation", max_length=200, blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ['-date']

    def __str__(self):
        if self.nombre_unites is not None and self.poids_kg is not None:
            return f"{self.type} - {self.nombre_unites} article(s), {self.quantite} kg ({self.material.name})"
        return f"{self.type} - {self.quantite} kg ({self.material.name})"

    @property
    def sens(self):
        if self.annule:
            return 0
        if self.type in ['ENTREE', 'RETOUR_INTERNE']:
            return 1
        elif self.type in ['SORTIE', 'PERTE', 'RETOUR']:
            return -1
        elif self.type == 'AJUSTEMENT':
            return 1 if float(self.quantite or 0) > 0 else -1
        return 0


class StockPrintDocument(models.Model):
    KIND_CHOICES = [
        ('SORTIE_JOURNALIERE', 'Bon de sortie journalier'),
        ('RECEPTION', 'Bon de réception'),
        ('RETOUR_INTERNE', 'Bon de retour interne'),
        ('RETOUR_FOURNISSEUR', 'Bon de retour fournisseur'),
        ('AVARIE', 'Bon d’avarie'),
    ]
    kind = models.CharField('Type de bon', max_length=24, choices=KIND_CHOICES, db_index=True)
    reference = models.CharField('Référence', max_length=40, unique=True, null=True, blank=True)
    document_date = models.DateField('Date du document', default=timezone.now, db_index=True)
    created_at = models.DateTimeField('Créé le', default=timezone.now)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_print_documents')
    supplier = models.ForeignKey('core.Supplier', on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_print_documents')
    bon_commande = models.ForeignKey('core.BonCommande', on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_print_documents')
    movements = models.ManyToManyField('core.StockMovement', blank=True, related_name='print_documents')
    notes = models.TextField('Observations', blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = 'Bon de stock imprimable'
        verbose_name_plural = 'Bons de stock imprimables'
        ordering = ['-document_date', '-id']

    @property
    def display_reference(self):
        """Affiche FB pour les bons de sortie, y compris les anciens BS enregistrés."""
        reference = self.reference or f"Bon #{self.pk}"
        if self.kind == 'SORTIE_JOURNALIERE' and reference.startswith('BS-'):
            return f"FB-{reference[3:]}"
        return reference

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.reference:
            prefixes = {
                'SORTIE_JOURNALIERE': 'FB', 'RECEPTION': 'BR',
                'RETOUR_INTERNE': 'BRT', 'RETOUR_FOURNISSEUR': 'BRS', 'AVARIE': 'BA',
            }
            self.reference = f"{prefixes.get(self.kind, 'BST')}-{self.document_date:%Y}-{self.pk:06d}"
            super().save(update_fields=['reference'])

    def __str__(self):
        return self.display_reference


class StockPrintDocumentLine(models.Model):
    document = models.ForeignKey(StockPrintDocument, on_delete=models.CASCADE, related_name='lines')
    material = models.ForeignKey('core.Material', on_delete=models.PROTECT, related_name='stock_document_lines')
    movement = models.ForeignKey('core.StockMovement', on_delete=models.SET_NULL, null=True, blank=True, related_name='document_lines')
    lot = models.ForeignKey('core.StockLot', on_delete=models.SET_NULL, null=True, blank=True, related_name='document_lines')
    emplacement = models.ForeignKey('core.StockLocation', on_delete=models.SET_NULL, null=True, blank=True, related_name='document_lines')
    quantity = models.FloatField('Quantité')
    univers_snapshot = models.CharField('Univers', max_length=30, blank=True)
    origine_snapshot = models.CharField('Origine', max_length=15, blank=True)
    laize_mm_snapshot = models.PositiveIntegerField('Laize (mm)', null=True, blank=True)
    micronage_snapshot = models.PositiveIntegerField('Micronage (µm)', null=True, blank=True)
    grammage_snapshot = models.FloatField('Grammage (g/m²)', null=True, blank=True)
    metrage = models.FloatField('Métrage (m)', null=True, blank=True)
    poids_kg = models.FloatField('Poids (kg)', null=True, blank=True)
    nombre_unites = models.PositiveIntegerField('Nombre d’unités', null=True, blank=True)
    unit_snapshot = models.CharField('Unité', max_length=20, blank=True)
    notes = models.CharField('Motif / observations', max_length=300, blank=True)

    def save(self, *args, **kwargs):
        material = self.material
        lot = self.lot if self.lot_id else None
        movement = self.movement if self.movement_id else None
        if not self.univers_snapshot:
            self.univers_snapshot = material.category
        if not self.origine_snapshot:
            self.origine_snapshot = (lot.origine if lot and lot.origine else material.origine) or ''
        if self.laize_mm_snapshot is None:
            self.laize_mm_snapshot = movement.laize_mm if movement and movement.laize_mm is not None else (lot.laize if lot and lot.laize is not None else material.laize_mm)
        if self.micronage_snapshot is None:
            self.micronage_snapshot = movement.micronage if movement and movement.micronage is not None else (lot.micronage if lot and lot.micronage is not None else material.micronage_standard)
        if self.grammage_snapshot is None:
            self.grammage_snapshot = lot.grammage if lot and lot.grammage is not None else material.grammage
        if material.category == 'FILM' and self.metrage is None:
            if movement and movement.metrage is not None:
                self.metrage = movement.metrage
            elif lot and lot.metrage is not None:
                self.metrage = lot.metrage
            elif lot and lot.longueur is not None:
                self.metrage = lot.longueur
            else:
                self.metrage = material.metrage_standard
        if self.poids_kg is None:
            self.poids_kg = movement.poids_kg if movement and movement.poids_kg is not None else (lot.poids_kg if lot and lot.poids_kg is not None else material.poids_kg)
            if self.poids_kg is None and str(material.unit or '').strip().upper() in {'KG', 'KGS'}:
                self.poids_kg = self.quantity
        if self.nombre_unites is None:
            if movement and movement.nombre_unites is not None:
                self.nombre_unites = movement.nombre_unites
            else:
                self.nombre_unites = lot.nombre_unites if lot and lot.nombre_unites is not None else material.nombre_unites
        if not self.unit_snapshot:
            self.unit_snapshot = material.unit
        super().save(*args, **kwargs)

    class Meta:
        app_label = 'core'
        verbose_name = 'Ligne de bon de stock'
        verbose_name_plural = 'Lignes de bon de stock'

    def __str__(self):
        return f"{self.material} — {self.quantity} {self.unit_snapshot}"


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