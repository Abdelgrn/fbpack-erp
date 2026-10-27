"""Stock produit fini (LOT PRODUIT_FINI_SYNC V1).

Alimenté par la pesée : une bobine pesée = une ligne de bobine + un mouvement d'entrée.
Les totaux (palettes, bobines, kg, statut) sont CALCULÉS, jamais stockés.
Un mouvement d'entrée ne s'efface pas : la traçabilité reste complète.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class ProduitFiniLot(models.Model):
    # Clé métier : client_nom + produit_nom + numero_lot (comme la pesée les envoie)
    client = models.ForeignKey(
        'core.Client', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='produits_finis_lots', verbose_name='Client ERP')
    client_nom = models.CharField('Client (nom pesée)', max_length=200)
    produit = models.ForeignKey(
        'core.TechnicalProduct', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='produits_finis_lots', verbose_name='Produit technique')
    produit_nom = models.CharField('Produit (nom pesée)', max_length=200, blank=True)
    numero_lot = models.CharField('N° lot', max_length=100, db_index=True)
    a_relier = models.BooleanField('À relier', default=False,
                                   help_text='Client ou produit non reconnu dans l’ERP.')
    job_clos_le = models.DateTimeField('Job clôturé le', null=True, blank=True)
    # Temps de production du job (minutes, pauses déduites) envoyé par la pesée à la clôture.
    temps_production_min = models.PositiveIntegerField(
        'Temps de production (min)', null=True, blank=True)
    # Entrée en stock produit fini : décidée à la main depuis le module « Suivi par poste ».
    # Tant que ce champ est vide, le lot reste visible dans le suivi mais pas dans le stock.
    entree_stock_le = models.DateTimeField('Entré en stock le', null=True, blank=True)
    entree_stock_par = models.CharField('Entré en stock par', max_length=150, blank=True)
    cree_le = models.DateTimeField('Créé le', default=timezone.now)

    class Meta:
        app_label = 'core'
        ordering = ['client_nom', 'produit_nom', 'numero_lot']
        constraints = [
            models.UniqueConstraint(fields=['client_nom', 'produit_nom', 'numero_lot'],
                                    name='uniq_pf_lot_cle'),
        ]
        verbose_name = 'Lot produit fini'

    def __str__(self):
        return f'{self.client_nom} · {self.produit_nom} · {self.numero_lot}'


class ProduitFiniPalette(models.Model):
    lot = models.ForeignKey(ProduitFiniLot, on_delete=models.CASCADE,
                            related_name='palettes')
    # Poste de production (ex. « Extrudeuse », « Découpe grande »). Chaque poste numérote
    # ses palettes : PAL-001 peut donc exister une fois par poste pour un même lot.
    poste = models.CharField('Poste', max_length=100, blank=True, default='', db_index=True)
    numero_palette = models.CharField('N° palette', max_length=50)
    cree_le = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = 'core'
        ordering = ['poste', 'numero_palette']
        constraints = [
            models.UniqueConstraint(fields=['lot', 'poste', 'numero_palette'],
                                    name='uniq_pf_palette_poste'),
        ]

    def __str__(self):
        return self.numero_palette


class ProduitFiniMouvement(models.Model):
    TYPE_CHOICES = [
        ('ENTREE', 'Entrée (pesée)'),
        ('SORTIE', 'Sortie (déstockage)'),
    ]
    lot = models.ForeignKey(ProduitFiniLot, on_delete=models.CASCADE,
                            related_name='mouvements')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    nb_bobines = models.PositiveIntegerField(default=0)
    poids_kg = models.FloatField(default=0)
    palettes_libelle = models.CharField('Palettes', max_length=500, blank=True)
    date = models.DateTimeField('Date', default=timezone.now)
    motif = models.CharField('Motif / référence', max_length=200, blank=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mouvements_produit_fini', verbose_name='Utilisateur')
    annule = models.BooleanField('Annulé', default=False)
    motif_annulation = models.CharField('Motif d’annulation', max_length=200, blank=True)

    class Meta:
        app_label = 'core'
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.get_type_display()} · {self.lot} · {self.nb_bobines} bobine(s)'


class ProduitFiniBobine(models.Model):
    palette = models.ForeignKey(ProduitFiniPalette, on_delete=models.CASCADE,
                                related_name='bobines')
    numero_bobine = models.CharField('N° bobine', max_length=20)
    poids_kg = models.FloatField('Poids net (kg)')
    date_heure = models.DateTimeField('Pesée le')
    operateur = models.CharField('Opérateur', max_length=150, blank=True)
    equipe = models.CharField('Équipe', max_length=20, blank=True)
    statut_pesee = models.CharField('Statut pesée', max_length=20, default='ok')
    # Identifiant unique venant de la pesée : empêche les doublons à la resynchronisation
    uid = models.CharField('Identifiant pesée', max_length=80, unique=True)
    date_sortie = models.DateTimeField('Sortie le', null=True, blank=True)
    mouvement_sortie = models.ForeignKey(
        ProduitFiniMouvement, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='bobines_sorties')

    class Meta:
        app_label = 'core'
        ordering = ['date_heure', 'id']

    def __str__(self):
        return f'Bobine {self.numero_bobine} · {self.poids_kg} kg'
