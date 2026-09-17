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

    class Meta:
        app_label = 'core'
        verbose_name = "Opportunité"
        verbose_name_plural = "Opportunités"
        ordering = ['-date_ouverture']

    def __str__(self):
        return f"{self.titre} - {self.client.name}"

    def valeur_ponderee(self):
        return round(float(self.valeur_estimee) * self.probabilite / 100, 2)
