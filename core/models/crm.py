from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


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
    SOURCE_CHOICES = [
        ('SITE_WEB', 'Site web'),
        ('SALON', 'Salon / Foire'),
        ('RESEAU', 'Réseau / Recommandation'),
        ('APPEL_ENTRANT', 'Appel entrant'),
        ('PROSPECTION', 'Prospection active'),
        ('EMAILING', 'Emailing'),
        ('RESEAUX_SOCIAUX', 'Réseaux sociaux'),
        ('PARTENAIRE', 'Partenaire'),
        ('AUTRE', 'Autre'),
    ]
    CONDITIONS_PAIEMENT_CHOICES = [
        ('COMPTANT', 'Comptant'),
        ('30J', '30 jours'),
        ('45J', '45 jours'),
        ('60J', '60 jours'),
        ('90J', '90 jours'),
        ('30J_FM', '30 jours fin de mois'),
        ('ACOMPTE_30', 'Acompte 30% + solde'),
        ('ACOMPTE_50', 'Acompte 50% + solde'),
        ('AUTRE', 'Autre'),
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

    # --- AJOUTS CRM MODERNE ---
    source_prospect = models.CharField(
        "Source du prospect", max_length=20, choices=SOURCE_CHOICES, blank=True, default=''
    )
    conditions_paiement = models.CharField(
        "Conditions de paiement", max_length=20, choices=CONDITIONS_PAIEMENT_CHOICES, blank=True, default=''
    )
    delai_livraison_jours = models.IntegerField("Délai de livraison standard (jours)", default=15)
    remise_defaut = models.DecimalField(
        "Remise par défaut (%)", max_digits=5, decimal_places=2, default=0
    )
    limite_credit = models.DecimalField(
        "Limite de crédit (DA)", max_digits=14, decimal_places=2, default=0
    )
    ice_nif = models.CharField("ICE / NIF / RC", max_length=100, blank=True)
    date_conversion = models.DateField(
        "Date conversion prospect → client", null=True, blank=True
    )

    class Meta:
        app_label = 'core'
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

    def get_nb_commandes(self):
        return self.commandes_client.count()

    def get_commandes_en_cours(self):
        return self.commandes_client.exclude(statut__in=['LIVREE', 'ANNULEE'])

    def get_ca_commandes(self):
        total = self.commandes_client.exclude(statut='ANNULEE').aggregate(
            t=models.Sum('montant_total')
        )['t']
        return total or 0

    def est_prospect(self):
        return self.status == 'PROSPECT'

    def convertir_en_client(self):
        """Convertit un prospect en client actif."""
        if self.status == 'PROSPECT':
            self.status = 'ACTIVE'
            self.date_conversion = timezone.now().date()
            self.save(update_fields=['status', 'date_conversion'])
        return self


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
        app_label = 'core'
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
        app_label = 'core'
        verbose_name = "Journal d'interaction"
        verbose_name_plural = "Journaux d'interaction"
        ordering = ['-date']

    def __str__(self):
        return f"{self.get_type_display()} - {self.client.name} ({self.date.strftime('%d/%m/%Y')})"


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

    # --- AJOUTS CRM MODERNE ---
    produit_demande = models.ForeignKey(
        'core.TechnicalProduct', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Produit demandé", related_name='opportunites'
    )
    quantite_estimee = models.FloatField("Quantité estimée (kg)", default=0)
    prix_estime = models.DecimalField(
        "Prix estimé (DA)", max_digits=14, decimal_places=2, default=0
    )
    date_prevue_commande = models.DateField(
        "Date prévue de commande", null=True, blank=True
    )
    devis_lie = models.ForeignKey(
        'core.Quote', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Devis associé", related_name='opportunites_liees'
    )
    material_principal = models.ForeignKey(
        'core.Material', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Matière principale requise", related_name='opportunites'
    )

    class Meta:
        app_label = 'core'
        verbose_name = "Opportunité"
        verbose_name_plural = "Opportunités"
        ordering = ['-date_ouverture']

    def __str__(self):
        return f"{self.titre} - {self.client.name}"

    def valeur_ponderee(self):
        return round(float(self.valeur_estimee) * self.probabilite / 100, 2)

    def stock_disponible_pour_opportunite(self):
        """Vérifie si le stock matière est suffisant pour cette opportunité."""
        if not self.material_principal:
            return {'disponible': None, 'stock': 0, 'besoin': self.quantite_estimee, 'message': 'Aucune matière liée'}
        stock = self.material_principal.quantity or 0
        besoin = self.quantite_estimee or 0
        ok = stock >= besoin
        return {
            'disponible': ok,
            'stock': stock,
            'besoin': besoin,
            'manque': max(0, besoin - stock),
            'material': self.material_principal.name,
            'message': 'Stock OK ✓' if ok else f'Stock insuffisant (manque {besoin - stock:.1f} {self.material_principal.unit})',
        }


class CommandeClient(models.Model):
    """Commande client commerciale — reliée au stock et à la production (OF)."""
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('CONFIRMEE', 'Confirmée'),
        ('EN_PRODUCTION', 'En production'),
        ('PRETE', 'Prête à livrer'),
        ('LIVREE', 'Livrée'),
        ('ANNULEE', 'Annulée'),
    ]
    PRIORITE_CHOICES = [
        ('BASSE', 'Basse'),
        ('NORMALE', 'Normale'),
        ('HAUTE', 'Haute'),
        ('URGENTE', 'Urgente'),
    ]

    reference = models.CharField("Référence commande", max_length=50, unique=True, blank=True)
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, verbose_name="Client", related_name='commandes_client'
    )
    opportunite = models.ForeignKey(
        Opportunite, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Opportunité liée", related_name='commandes'
    )
    devis = models.ForeignKey(
        'core.Quote', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Devis d'origine", related_name='commandes_client'
    )
    commercial = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Commercial", related_name='commandes_client'
    )
    of_lie = models.ForeignKey(
        'core.OrdreFabrication', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="OF lié", related_name='commandes_client'
    )

    date_commande = models.DateField("Date commande", default=timezone.now)
    date_livraison_prevue = models.DateField("Date livraison prévue", null=True, blank=True)
    date_livraison_reelle = models.DateField("Date livraison réelle", null=True, blank=True)

    statut = models.CharField("État", max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    priorite = models.CharField("Priorité", max_length=10, choices=PRIORITE_CHOICES, default='NORMALE')

    conditions_paiement = models.CharField("Conditions de paiement", max_length=20, blank=True)
    delai_livraison_jours = models.IntegerField("Délai livraison (jours)", default=15)
    remise_globale = models.DecimalField("Remise globale (%)", max_digits=5, decimal_places=2, default=0)
    montant_ht = models.DecimalField("Montant HT (DA)", max_digits=14, decimal_places=2, default=0)
    montant_total = models.DecimalField("Montant total (DA)", max_digits=14, decimal_places=2, default=0)

    adresse_livraison = models.TextField("Adresse de livraison", blank=True)
    notes = models.TextField("Notes / Instructions", blank=True)
    cree_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='commandes_creees', verbose_name="Créé par"
    )
    date_creation = models.DateTimeField("Date création", auto_now_add=True)
    date_modification = models.DateTimeField("Dernière modification", auto_now=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Commande Client"
        verbose_name_plural = "Commandes Clients"
        ordering = ['-date_commande']

    def __str__(self):
        return f"{self.reference} — {self.client.name}"

    def save(self, *args, **kwargs):
        if not self.reference:
            annee = timezone.now().year
            last = CommandeClient.objects.filter(
                reference__startswith=f"CMD{annee}"
            ).order_by('-reference').first()
            if last and last.reference:
                try:
                    num = int(last.reference.replace(f"CMD{annee}-", '')) + 1
                except (ValueError, IndexError):
                    num = 1
            else:
                num = 1
            self.reference = f"CMD{annee}-{num:04d}"
        super().save(*args, **kwargs)

    def recalculer_montants(self):
        """Recalcule montant_ht et montant_total à partir des lignes."""
        total = sum(float(l.montant_ligne) for l in self.lignes.all())
        self.montant_ht = total
        remise = float(self.remise_globale or 0)
        self.montant_total = total * (1 - remise / 100)
        self.save(update_fields=['montant_ht', 'montant_total'])

    def verifier_stock_global(self):
        """
        Vérifie la disponibilité stock pour toutes les lignes.
        Retourne un dict résumé pour le commercial.
        """
        resultats = []
        tout_ok = True
        for ligne in self.lignes.select_related('material', 'produit').all():
            info = ligne.verifier_stock()
            resultats.append(info)
            if info.get('disponible') is False:
                tout_ok = False
        return {
            'tout_disponible': tout_ok,
            'lignes': resultats,
            'nb_lignes': len(resultats),
            'nb_ok': sum(1 for r in resultats if r.get('disponible') is True),
            'nb_ko': sum(1 for r in resultats if r.get('disponible') is False),
            'nb_na': sum(1 for r in resultats if r.get('disponible') is None),
        }

    def get_statut_color(self):
        return {
            'BROUILLON': 'gray',
            'CONFIRMEE': 'blue',
            'EN_PRODUCTION': 'yellow',
            'PRETE': 'cyan',
            'LIVREE': 'green',
            'ANNULEE': 'red',
        }.get(self.statut, 'gray')

    def get_priorite_color(self):
        return {
            'BASSE': 'gray',
            'NORMALE': 'blue',
            'HAUTE': 'orange',
            'URGENTE': 'red',
        }.get(self.priorite, 'gray')

    @property
    def nb_lignes(self):
        return self.lignes.count()

    @property
    def quantite_totale(self):
        return sum(l.quantite for l in self.lignes.all())

    def peut_creer_of(self):
        """True si on peut générer un OF depuis cette commande."""
        return self.statut in ('CONFIRMEE', 'EN_PRODUCTION') and not self.of_lie_id


class LigneCommandeClient(models.Model):
    """Ligne de commande client avec vérification stock matière."""

    commande = models.ForeignKey(
        CommandeClient, on_delete=models.CASCADE, related_name='lignes', verbose_name="Commande"
    )
    produit = models.ForeignKey(
        'core.TechnicalProduct', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Produit", related_name='lignes_commande'
    )
    material = models.ForeignKey(
        'core.Material', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Matière première liée", related_name='lignes_commande'
    )
    designation = models.CharField("Désignation", max_length=300)
    quantite = models.FloatField("Quantité", default=0)
    unite = models.CharField("Unité", max_length=20, default='kg')
    prix_unitaire = models.DecimalField("Prix unitaire (DA)", max_digits=12, decimal_places=2, default=0)
    remise = models.DecimalField("Remise ligne (%)", max_digits=5, decimal_places=2, default=0)
    date_livraison = models.DateField("Date livraison ligne", null=True, blank=True)
    notes = models.TextField("Notes", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Ligne commande client"
        verbose_name_plural = "Lignes commandes clients"
        ordering = ['id']

    def __str__(self):
        return f"{self.designation} × {self.quantite} {self.unite}"

    @property
    def montant_ligne(self):
        brut = float(self.quantite) * float(self.prix_unitaire)
        remise = float(self.remise or 0)
        return round(brut * (1 - remise / 100), 2)

    def verifier_stock(self):
        """
        Vérifie si le stock matière est suffisant pour cette ligne.
        Utilisé par le commercial pour voir la dispo en temps réel.
        """
        if not self.material:
            return {
                'ligne_id': self.id,
                'designation': self.designation,
                'disponible': None,
                'stock': 0,
                'besoin': self.quantite,
                'manque': 0,
                'material': None,
                'unit': self.unite,
                'message': 'Pas de matière liée — vérification N/A',
                'badge': 'na',
            }
        stock = float(self.material.quantity or 0)
        besoin = float(self.quantite or 0)
        ok = stock >= besoin
        manque = max(0, besoin - stock)
        return {
            'ligne_id': self.id,
            'designation': self.designation,
            'disponible': ok,
            'stock': stock,
            'besoin': besoin,
            'manque': manque,
            'material': self.material.name,
            'material_id': self.material.id,
            'unit': self.material.unit,
            'message': (
                f'Stock OK ({stock:.1f} {self.material.unit} dispo)'
                if ok else
                f'Stock insuffisant — {stock:.1f} dispo / {besoin:.1f} besoin (manque {manque:.1f})'
            ),
            'badge': 'ok' if ok else 'ko',
            'is_low': self.material.is_low_stock() if hasattr(self.material, 'is_low_stock') else stock <= (self.material.min_threshold or 0),
        }


class DemandePrix(models.Model):
    """Demande de prix client (avant devis formel)."""
    STATUT_CHOICES = [
        ('NOUVELLE', 'Nouvelle'),
        ('EN_ETUDE', 'En étude'),
        ('DEVIS_ENVOYE', 'Devis envoyé'),
        ('ACCEPTEE', 'Acceptée'),
        ('REFUSEE', 'Refusée'),
        ('EXPIREE', 'Expirée'),
    ]

    reference = models.CharField("Référence DP", max_length=50, unique=True, blank=True)
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, verbose_name="Client", related_name='demandes_prix'
    )
    contact = models.ForeignKey(
        ClientContact, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contact"
    )
    commercial = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Commercial", related_name='demandes_prix'
    )
    opportunite = models.ForeignKey(
        Opportunite, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Opportunité", related_name='demandes_prix'
    )
    devis = models.ForeignKey(
        'core.Quote', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Devis généré", related_name='demandes_prix_origine'
    )

    objet = models.CharField("Objet de la demande", max_length=300)
    description = models.TextField("Description détaillée", blank=True)
    produit = models.ForeignKey(
        'core.TechnicalProduct', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Produit concerné"
    )
    quantite_demandee = models.FloatField("Quantité demandée (kg)", default=0)
    budget_indicatif = models.DecimalField(
        "Budget indicatif (DA)", max_digits=14, decimal_places=2, default=0
    )

    date_demande = models.DateField("Date demande", default=timezone.now)
    date_reponse_souhaitee = models.DateField("Réponse souhaitée avant", null=True, blank=True)
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='NOUVELLE')
    notes = models.TextField("Notes internes", blank=True)
    cree_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='demandes_prix_creees'
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Demande de prix"
        verbose_name_plural = "Demandes de prix"
        ordering = ['-date_demande']

    def __str__(self):
        return f"{self.reference} — {self.objet}"

    def save(self, *args, **kwargs):
        if not self.reference:
            annee = timezone.now().year
            last = DemandePrix.objects.filter(
                reference__startswith=f"DP{annee}"
            ).order_by('-reference').first()
            if last and last.reference:
                try:
                    num = int(last.reference.replace(f"DP{annee}-", '')) + 1
                except (ValueError, IndexError):
                    num = 1
            else:
                num = 1
            self.reference = f"DP{annee}-{num:04d}"
        super().save(*args, **kwargs)