from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class Department(models.Model):
    name = models.CharField("Nom du département", max_length=100)
    code = models.CharField("Code", max_length=20, unique=True)
    description = models.TextField("Description", blank=True)
    responsable = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='departements_geres', verbose_name="Responsable")
    is_active = models.BooleanField("Actif", default=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Département"
        verbose_name_plural = "Départements"

    def __str__(self):
        return self.name


class Position(models.Model):
    CATEGORY_CHOICES = [
        ('PRODUCTION', 'Production'), ('MAINTENANCE', 'Maintenance'),
        ('QUALITE', 'Qualité'), ('LOGISTIQUE', 'Logistique'),
        ('ADMIN', 'Administratif'), ('DIRECTION', 'Direction'),
    ]

    name = models.CharField("Intitulé du poste", max_length=100)
    code = models.CharField("Code poste", max_length=20, unique=True)
    category = models.CharField("Catégorie", max_length=20, choices=CATEGORY_CHOICES, default='PRODUCTION')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='positions', verbose_name="Département")
    description = models.TextField("Description du poste", blank=True)
    salaire_min = models.DecimalField("Salaire minimum (DA)", max_digits=12, decimal_places=2, default=0)
    salaire_max = models.DecimalField("Salaire maximum (DA)", max_digits=12, decimal_places=2, default=0)
    requires_machine_auth = models.BooleanField("Nécessite autorisation machine", default=False)
    is_active = models.BooleanField("Actif", default=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Poste"
        verbose_name_plural = "Postes"

    def __str__(self):
        return self.name


class Employee(models.Model):
    GENDER_CHOICES = [('M', 'Masculin'), ('F', 'Féminin')]
    STATUT_CHOICES = [
        ('ACTIF', 'Actif'), ('CONGE', 'En congé'),
        ('SUSPENDU', 'Suspendu'), ('DEMISSION', 'Démissionnaire'),
        ('LICENCIE', 'Licencié'), ('RETRAITE', 'Retraité'),
    ]
    CONTRAT_CHOICES = [
        ('CDI', 'CDI'), ('CDD', 'CDD'), ('INTERIM', 'Intérimaire'),
        ('STAGE', 'Stagiaire'), ('APPRENTI', 'Apprenti'),
    ]
    SITUATION_CHOICES = [
        ('CELIBATAIRE', 'Célibataire'), ('MARIE', 'Marié(e)'),
        ('DIVORCE', 'Divorcé(e)'), ('VEUF', 'Veuf/Veuve'),
    ]

    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='employee_profile', verbose_name="Compte utilisateur")
    matricule = models.CharField("Matricule", max_length=50, unique=True)
    nom = models.CharField("Nom", max_length=100)
    prenom = models.CharField("Prénom", max_length=100)
    nom_arabe = models.CharField("الإسم بالعربية", max_length=200, blank=True)
    date_naissance = models.DateField("Date de naissance", null=True, blank=True)
    lieu_naissance = models.CharField("Lieu de naissance", max_length=100, blank=True)
    genre = models.CharField("Genre", max_length=1, choices=GENDER_CHOICES, default='M')
    situation_familiale = models.CharField("Situation familiale", max_length=20, choices=SITUATION_CHOICES, default='CELIBATAIRE')
    nb_enfants = models.IntegerField("Nombre d'enfants", default=0)
    cin = models.CharField("N° CIN (Carte d'identité)", max_length=50, blank=True)
    num_securite_sociale = models.CharField("N° Sécurité Sociale (CNAS)", max_length=50, blank=True)
    num_carte_chifa = models.CharField("N° Carte Chifa", max_length=50, blank=True)
    adresse = models.TextField("Adresse complète", blank=True)
    wilaya = models.CharField("Wilaya", max_length=50, blank=True)
    commune = models.CharField("Commune", max_length=50, blank=True)
    telephone = models.CharField("Téléphone", max_length=50, blank=True)
    telephone_urgence = models.CharField("Téléphone urgence", max_length=50, blank=True)
    email = models.EmailField("Email", blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees', verbose_name="Département")
    position = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees', verbose_name="Poste")
    superieur = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subordonnes', verbose_name="Supérieur hiérarchique")
    machine_affectee = models.ForeignKey('core.Machine', on_delete=models.SET_NULL, null=True, blank=True, related_name='operateurs', verbose_name="Machine/Ligne affectée")
    atelier = models.CharField("Atelier", max_length=50, blank=True)
    type_contrat = models.CharField("Type de contrat", max_length=20, choices=CONTRAT_CHOICES, default='CDI')
    date_embauche = models.DateField("Date d'embauche")
    date_fin_contrat = models.DateField("Date fin de contrat", null=True, blank=True)
    date_depart = models.DateField("Date de départ", null=True, blank=True)
    motif_depart = models.TextField("Motif de départ", blank=True)
    salaire_base = models.DecimalField("Salaire de base (DA)", max_digits=12, decimal_places=2, default=0)
    solde_conge = models.FloatField("Solde congé (jours)", default=30)
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='ACTIF')
    photo = models.ImageField("Photo", upload_to='employees/photos/', blank=True, null=True)
    date_creation = models.DateTimeField("Date création", auto_now_add=True)
    date_modification = models.DateTimeField("Dernière modification", auto_now=True)
    notes = models.TextField("Notes", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Employé"
        verbose_name_plural = "Employés"

    def __str__(self):
        return f"{self.nom} {self.prenom}"


class EmployeeDocument(models.Model):
    TYPE_CHOICES = [
        ('CONTRAT', 'Contrat de travail'), ('CIN', 'Copie CIN'),
        ('DIPLOME', 'Diplôme'), ('CERTIFICAT', 'Certificat'),
        ('ATTESTATION', 'Attestation'), ('CV', 'CV'),
        ('PHOTO', 'Photo'), ('AUTRE', 'Autre'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='documents', verbose_name="Employé")
    type_document = models.CharField("Type", max_length=20, choices=TYPE_CHOICES)
    nom = models.CharField("Nom du document", max_length=200)
    fichier = models.FileField("Fichier", upload_to='employees/documents/')
    date_upload = models.DateTimeField("Date upload", auto_now_add=True)
    date_expiration = models.DateField("Date d'expiration", null=True, blank=True)
    notes = models.TextField("Notes", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Document employé"
        verbose_name_plural = "Documents employés"


class Skill(models.Model):
    CATEGORY_CHOICES = [
        ('MACHINE', 'Conduite machine'), ('TECHNIQUE', 'Technique'),
        ('QUALITE', 'Qualité'), ('SECURITE', 'Sécurité'), ('SOFT', 'Soft skills'),
    ]

    name = models.CharField("Nom de la compétence", max_length=100)
    code = models.CharField("Code", max_length=20, unique=True)
    category = models.CharField("Catégorie", max_length=20, choices=CATEGORY_CHOICES, default='MACHINE')
    description = models.TextField("Description", blank=True)
    machine_associee = models.ForeignKey('core.Machine', on_delete=models.SET_NULL, null=True, blank=True, related_name='competences_requises', verbose_name="Machine associée")
    is_active = models.BooleanField("Active", default=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Compétence"
        verbose_name_plural = "Compétences"

    def __str__(self):
        return self.name


class EmployeeSkill(models.Model):
    LEVEL_CHOICES = [
        (1, '⭐ Débutant'), (2, '⭐⭐ Intermédiaire'),
        (3, '⭐⭐⭐ Confirmé'), (4, '⭐⭐⭐⭐ Expert'),
        (5, '⭐⭐⭐⭐⭐ Formateur'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='competences', verbose_name="Employé")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='employees', verbose_name="Compétence")
    level = models.IntegerField("Niveau", choices=LEVEL_CHOICES, default=1)
    date_acquisition = models.DateField("Date d'acquisition", default=timezone.now)
    date_validation = models.DateField("Date de validation", null=True, blank=True)
    validateur = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='competences_validees', verbose_name="Validé par")
    certificat = models.FileField("Certificat", upload_to='employees/certificats/', blank=True, null=True)
    notes = models.TextField("Notes", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Compétence employé"
        verbose_name_plural = "Compétences employés"


class MachineAuthorization(models.Model):
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'), ('VALIDE', 'Validé ✓'),
        ('REFUSE', 'Refusé ✗'), ('EXPIRE', 'Expiré'), ('SUSPENDU', 'Suspendu'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='autorisations_machine', verbose_name="Employé")
    machine = models.ForeignKey('core.Machine', on_delete=models.CASCADE, related_name='operateurs_autorises', verbose_name="Machine")
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    date_demande = models.DateField("Date de demande", default=timezone.now)
    date_validation = models.DateField("Date de validation", null=True, blank=True)
    date_expiration = models.DateField("Date d'expiration", null=True, blank=True)
    validateur = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='autorisations_validees', verbose_name="Validé par")
    niveau_autorisation = models.CharField("Niveau", max_length=20, choices=[('OPERATEUR', 'Opérateur'), ('REGLEUR', 'Régleur'), ('FORMATEUR', 'Formateur')], default='OPERATEUR')
    notes = models.TextField("Notes", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Autorisation machine"
        verbose_name_plural = "Autorisations machines"


class Shift(models.Model):
    name = models.CharField("Nom de l'équipe", max_length=50)
    code = models.CharField("Code", max_length=10, unique=True)
    heure_debut = models.TimeField("Heure début")
    heure_fin = models.TimeField("Heure fin")
    pause_debut = models.TimeField("Début pause", null=True, blank=True)
    pause_fin = models.TimeField("Fin pause", null=True, blank=True)
    heures_travail = models.FloatField("Heures de travail", default=8)
    couleur = models.CharField("Couleur", max_length=7, default='#3b82f6')
    is_active = models.BooleanField("Actif", default=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Équipe (Shift)"
        verbose_name_plural = "Équipes (Shifts)"

    def __str__(self):
        return self.name


class Attendance(models.Model):
    STATUT_CHOICES = [
        ('PRESENT', 'Présent ✓'), ('ABSENT', 'Absent'),
        ('RETARD', 'Retard'), ('CONGE', 'En congé'),
        ('MALADIE', 'Maladie'), ('MISSION', 'Mission'),
        ('FERIE', 'Jour férié'), ('REPOS', 'Jour de repos'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='pointages', verbose_name="Employé")
    date = models.DateField("Date")
    shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Équipe")
    heure_arrivee = models.TimeField("Heure d'arrivée", null=True, blank=True)
    heure_depart = models.TimeField("Heure de départ", null=True, blank=True)
    heures_normales = models.FloatField("Heures normales", default=0)
    heures_supplementaires = models.FloatField("Heures supplémentaires", default=0)
    heures_nuit = models.FloatField("Heures de nuit", default=0)
    minutes_retard = models.IntegerField("Minutes de retard", default=0)
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='PRESENT')
    machine = models.ForeignKey('core.Machine', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Machine")
    atelier = models.CharField("Atelier", max_length=50, blank=True)
    valide = models.BooleanField("Validé", default=False)
    valide_par = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='pointages_valides', verbose_name="Validé par")
    notes = models.TextField("Notes / Remarques", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Pointage"
        verbose_name_plural = "Pointages"


class LeaveType(models.Model):
    name = models.CharField("Type de congé", max_length=100)
    code = models.CharField("Code", max_length=20, unique=True)
    jours_par_an = models.IntegerField("Jours par an", default=0)
    paye = models.BooleanField("Congé payé", default=True)
    justificatif_requis = models.BooleanField("Justificatif requis", default=False)
    couleur = models.CharField("Couleur", max_length=7, default='#6b7280')
    is_active = models.BooleanField("Actif", default=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Type de congé"
        verbose_name_plural = "Types de congés"

    def __str__(self):
        return self.name


class LeaveRequest(models.Model):
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'), ('SOUMISE', 'Soumise'),
        ('VALIDEE_N1', 'Validée N+1'), ('VALIDEE_RH', 'Validée RH ✓'),
        ('REFUSEE', 'Refusée ✗'), ('ANNULEE', 'Annulée'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='demandes_conge', verbose_name="Employé")
    type_conge = models.ForeignKey(LeaveType, on_delete=models.CASCADE, verbose_name="Type de congé")
    date_debut = models.DateField("Date début")
    date_fin = models.DateField("Date fin")
    nb_jours = models.FloatField("Nombre de jours", default=1)
    motif = models.TextField("Motif", blank=True)
    justificatif = models.FileField("Justificatif", upload_to='leaves/justificatifs/', blank=True, null=True)
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    date_demande = models.DateTimeField("Date de demande", auto_now_add=True)
    validateur_n1 = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='conges_valides_n1', verbose_name="Validateur N+1")
    date_validation_n1 = models.DateTimeField("Date validation N+1", null=True, blank=True)
    validateur_rh = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='conges_valides_rh', verbose_name="Validateur RH")
    date_validation_rh = models.DateTimeField("Date validation RH", null=True, blank=True)
    motif_refus = models.TextField("Motif de refus", blank=True)
    notes = models.TextField("Notes", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Demande de congé"
        verbose_name_plural = "Demandes de congés"


class SalaryGrid(models.Model):
    name = models.CharField("Nom de la grille", max_length=100)
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='grilles_salariales', verbose_name="Poste")
    echelon = models.IntegerField("Échelon", default=1)
    salaire_base = models.DecimalField("Salaire de base", max_digits=12, decimal_places=2)
    date_effet = models.DateField("Date d'effet")
    is_active = models.BooleanField("Active", default=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Grille salariale"
        verbose_name_plural = "Grilles salariales"


class Payslip(models.Model):
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'), ('CALCULE', 'Calculé'),
        ('VALIDE', 'Validé ✓'), ('PAYE', 'Payé'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='bulletins_paie', verbose_name="Employé")
    mois = models.IntegerField("Mois")
    annee = models.IntegerField("Année")
    reference = models.CharField("Référence", max_length=50, unique=True)
    jours_travailles = models.FloatField("Jours travaillés", default=26)
    jours_absence = models.FloatField("Jours d'absence", default=0)
    jours_conge = models.FloatField("Jours de congé", default=0)
    heures_normales = models.FloatField("Heures normales", default=0)
    heures_supplementaires_25 = models.FloatField("HS 25%", default=0)
    heures_supplementaires_50 = models.FloatField("HS 50%", default=0)
    heures_supplementaires_100 = models.FloatField("HS 100%", default=0)
    heures_nuit = models.FloatField("Heures de nuit", default=0)
    salaire_base = models.DecimalField("Salaire de base", max_digits=12, decimal_places=2, default=0)
    prime_rendement = models.DecimalField("Prime de rendement", max_digits=12, decimal_places=2, default=0)
    prime_presence = models.DecimalField("Prime de présence", max_digits=12, decimal_places=2, default=0)
    prime_nuit = models.DecimalField("Prime de nuit", max_digits=12, decimal_places=2, default=0)
    prime_anciennete = models.DecimalField("Prime d'ancienneté", max_digits=12, decimal_places=2, default=0)
    prime_transport = models.DecimalField("Indemnité transport", max_digits=12, decimal_places=2, default=0)
    prime_panier = models.DecimalField("Indemnité panier", max_digits=12, decimal_places=2, default=0)
    heures_sup_montant = models.DecimalField("Montant HS", max_digits=12, decimal_places=2, default=0)
    autres_primes = models.DecimalField("Autres primes", max_digits=12, decimal_places=2, default=0)
    salaire_brut = models.DecimalField("Salaire brut", max_digits=12, decimal_places=2, default=0)
    cotisation_cnas = models.DecimalField("CNAS (9%)", max_digits=12, decimal_places=2, default=0)
    cotisation_cnr = models.DecimalField("CNR Retraite (6.75%)", max_digits=12, decimal_places=2, default=0)
    cotisation_cnac = models.DecimalField("CNAC Chômage (0.5%)", max_digits=12, decimal_places=2, default=0)
    total_cotisations = models.DecimalField("Total cotisations", max_digits=12, decimal_places=2, default=0)
    salaire_imposable = models.DecimalField("Salaire imposable", max_digits=12, decimal_places=2, default=0)
    irg = models.DecimalField("IRG", max_digits=12, decimal_places=2, default=0)
    retenue_absence = models.DecimalField("Retenue absence", max_digits=12, decimal_places=2, default=0)
    avance_salaire = models.DecimalField("Avance sur salaire", max_digits=12, decimal_places=2, default=0)
    pret = models.DecimalField("Remboursement prêt", max_digits=12, decimal_places=2, default=0)
    autres_retenues = models.DecimalField("Autres retenues", max_digits=12, decimal_places=2, default=0)
    total_retenues = models.DecimalField("Total retenues", max_digits=12, decimal_places=2, default=0)
    salaire_net = models.DecimalField("Salaire net", max_digits=12, decimal_places=2, default=0)
    charge_cnas_patronale = models.DecimalField("CNAS patronale (26%)", max_digits=12, decimal_places=2, default=0)
    charge_cnr_patronale = models.DecimalField("CNR patronale (17.25%)", max_digits=12, decimal_places=2, default=0)
    charge_cnac_patronale = models.DecimalField("CNAC patronale (1%)", max_digits=12, decimal_places=2, default=0)
    total_charges_patronales = models.DecimalField("Total charges patronales", max_digits=12, decimal_places=2, default=0)
    cout_total_employeur = models.DecimalField("Coût total employeur", max_digits=12, decimal_places=2, default=0)
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    date_creation = models.DateTimeField("Date création", auto_now_add=True)
    date_validation = models.DateTimeField("Date validation", null=True, blank=True)
    valide_par = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='bulletins_valides', verbose_name="Validé par")
    date_paiement = models.DateField("Date de paiement", null=True, blank=True)
    mode_paiement = models.CharField("Mode de paiement", max_length=20, choices=[('VIREMENT', 'Virement'), ('CHEQUE', 'Chèque'), ('ESPECES', 'Espèces')], default='VIREMENT')
    notes = models.TextField("Notes", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Bulletin de paie"
        verbose_name_plural = "Bulletins de paie"


class WorkSchedule(models.Model):
    name = models.CharField("Nom du planning", max_length=100)
    date_debut = models.DateField("Date début")
    date_fin = models.DateField("Date fin")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Département")
    machine = models.ForeignKey('core.Machine', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Machine")
    notes = models.TextField("Notes", blank=True)
    is_active = models.BooleanField("Actif", default=True)
    cree_par = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Créé par")
    date_creation = models.DateTimeField("Date création", auto_now_add=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Planning de travail"
        verbose_name_plural = "Plannings de travail"


class ShiftAssignment(models.Model):
    schedule = models.ForeignKey(WorkSchedule, on_delete=models.CASCADE, related_name='affectations', verbose_name="Planning")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='affectations_shift', verbose_name="Employé")
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, verbose_name="Équipe")
    date = models.DateField("Date")
    machine = models.ForeignKey('core.Machine', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Machine")
    poste = models.CharField("Poste", max_length=50, blank=True)
    est_remplacement = models.BooleanField("Remplacement", default=False)
    remplace = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='remplacements', verbose_name="Remplace")
    notes = models.TextField("Notes", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Affectation shift"
        verbose_name_plural = "Affectations shifts"


class MedicalVisit(models.Model):
    TYPE_CHOICES = [
        ('EMBAUCHE', 'Visite d\'embauche'), ('PERIODIQUE', 'Visite périodique'),
        ('REPRISE', 'Visite de reprise'), ('SPONTANEE', 'Visite spontanée'),
    ]
    RESULTAT_CHOICES = [
        ('APTE', 'Apte'), ('APTE_RESTRICTION', 'Apte avec restrictions'),
        ('INAPTE_TEMPORAIRE', 'Inapte temporaire'), ('INAPTE', 'Inapte'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='visites_medicales', verbose_name="Employé")
    type_visite = models.CharField("Type de visite", max_length=20, choices=TYPE_CHOICES)
    date_visite = models.DateField("Date de visite")
    medecin = models.CharField("Médecin", max_length=100, blank=True)
    resultat = models.CharField("Résultat", max_length=20, choices=RESULTAT_CHOICES, default='APTE')
    restrictions = models.TextField("Restrictions", blank=True)
    date_prochaine_visite = models.DateField("Prochaine visite", null=True, blank=True)
    certificat = models.FileField("Certificat médical", upload_to='medical/', blank=True, null=True)
    notes = models.TextField("Notes", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Visite médicale"
        verbose_name_plural = "Visites médicales"


class WorkIncident(models.Model):
    TYPE_CHOICES = [
        ('ACCIDENT', 'Accident de travail'), ('INCIDENT', 'Incident sans blessure'),
        ('PRESQUACCIDENT', 'Presqu\'accident'), ('MALADIE_PRO', 'Maladie professionnelle'),
    ]
    GRAVITE_CHOICES = [
        ('MINEURE', 'Mineure'), ('MODEREE', 'Modérée'),
        ('GRAVE', 'Grave'), ('TRES_GRAVE', 'Très grave'), ('MORTELLE', 'Mortelle'),
    ]

    reference = models.CharField("Référence", max_length=50, unique=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='incidents', verbose_name="Employé concerné")
    type_incident = models.CharField("Type", max_length=20, choices=TYPE_CHOICES)
    gravite = models.CharField("Gravité", max_length=20, choices=GRAVITE_CHOICES, default='MINEURE')
    date_incident = models.DateTimeField("Date et heure de l'incident")
    lieu = models.CharField("Lieu", max_length=200)
    machine = models.ForeignKey('core.Machine', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Machine impliquée")
    description = models.TextField("Description de l'incident")
    cause = models.TextField("Cause(s) identifiée(s)", blank=True)
    temoins = models.TextField("Témoins", blank=True)
    jours_arret = models.IntegerField("Jours d'arrêt", default=0)
    blessure = models.TextField("Nature de la blessure", blank=True)
    soins_prodigues = models.TextField("Soins prodigués", blank=True)
    actions_immediates = models.TextField("Actions immédiates", blank=True)
    actions_correctives = models.TextField("Actions correctives", blank=True)
    declare_cnas = models.BooleanField("Déclaré CNAS", default=False)
    date_declaration_cnas = models.DateField("Date déclaration CNAS", null=True, blank=True)
    num_declaration = models.CharField("N° déclaration", max_length=50, blank=True)
    rapport = models.FileField("Rapport d'accident", upload_to='incidents/', blank=True, null=True)
    photos = models.FileField("Photos", upload_to='incidents/photos/', blank=True, null=True)
    cloture = models.BooleanField("Clôturé", default=False)
    date_cloture = models.DateField("Date de clôture", null=True, blank=True)
    date_creation = models.DateTimeField("Date création", auto_now_add=True)
    cree_par = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents_declares', verbose_name="Déclaré par")

    class Meta:
        app_label = 'core'
        verbose_name = "Incident de travail"
        verbose_name_plural = "Incidents de travail"


class ProtectiveEquipment(models.Model):
    TYPE_CHOICES = [
        ('CASQUE', 'Casque'), ('LUNETTES', 'Lunettes de protection'),
        ('GANTS', 'Gants'), ('CHAUSSURES', 'Chaussures de sécurité'),
        ('GILET', 'Gilet de sécurité'), ('MASQUE', 'Masque'),
        ('BOUCHONS', 'Bouchons d\'oreilles'), ('COMBINAISON', 'Combinaison'),
        ('AUTRE', 'Autre'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='equipements_protection', verbose_name="Employé")
    type_equipement = models.CharField("Type", max_length=20, choices=TYPE_CHOICES)
    designation = models.CharField("Désignation", max_length=200)
    date_attribution = models.DateField("Date d'attribution", default=timezone.now)
    date_expiration = models.DateField("Date d'expiration", null=True, blank=True)
    quantite = models.IntegerField("Quantité", default=1)
    taille = models.CharField("Taille", max_length=20, blank=True)
    notes = models.TextField("Notes", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "EPI"
        verbose_name_plural = "EPI"