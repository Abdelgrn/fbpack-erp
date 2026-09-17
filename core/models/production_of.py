import datetime
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q
from django.apps import apps

class ProcessType(models.Model):
    code = models.CharField("Code", max_length=20, unique=True)
    nom = models.CharField("Nom du processus", max_length=100)
    description = models.TextField("Description", blank=True)
    ordre_defaut = models.IntegerField("Ordre par défaut", default=0)
    icone = models.CharField("Icône (emoji)", max_length=10, default='⚙️')
    couleur = models.CharField("Couleur (hex)", max_length=7, default='#6c757d')
    atelier_lie = models.ForeignKey(
        'core.Atelier', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='process_types', verbose_name="Atelier associé"
    )
    est_actif = models.BooleanField("Actif", default=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Type de processus"
        verbose_name_plural = "Types de processus"
        ordering = ['ordre_defaut', 'nom']

    def __str__(self):
        return f"{self.icone} {self.nom}"


class OrdreFabrication(models.Model):
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'), ('LANCE', 'Lancé'),
        ('EN_COURS', 'En cours'), ('TERMINE', 'Terminé'), ('ANNULE', 'Annulé'),
    ]
    PRIORITE_CHOICES = [
        ('BASSE', 'Basse'), ('NORMALE', 'Normale'),
        ('HAUTE', 'Haute'), ('URGENTE', 'Urgente'),
    ]

    numero_of = models.CharField("N° OF", max_length=50, unique=True, blank=True)
    numero_lot = models.CharField("N° Lot", max_length=100, blank=True, db_index=True)
    client = models.ForeignKey('core.Client', on_delete=models.CASCADE, verbose_name="Client", related_name='ordres_fabrication')
    produit = models.ForeignKey('core.TechnicalProduct', on_delete=models.CASCADE, verbose_name="Produit fini", related_name='ordres_fabrication')
    opportunite = models.ForeignKey('core.Opportunite', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Opportunité liée")

    quantite_prevue = models.FloatField("Quantité prévue (kg)", default=0)
    quantite_produite = models.FloatField("Quantité produite (kg)", default=0)
    quantite_conforme = models.FloatField("Quantité conforme (kg)", default=0)
    quantite_rebut = models.FloatField("Rebuts (kg)", default=0)

    support = models.CharField("Support global (ex: OPP 20 TRS)", max_length=100, blank=True)
    dimension_mandrin = models.FloatField("Dimension mandrin (mm)", default=76, null=True, blank=True)
    diametre_bobine_fille = models.FloatField("Diamètre bobine fille (mm)", default=0, null=True, blank=True)
    laize = models.FloatField("Laize (mm)", default=0, null=True, blank=True)
    epaisseur = models.FloatField("Épaisseur (μm)", default=0, null=True, blank=True)

    date_creation = models.DateTimeField("Date création", auto_now_add=True)
    date_lancement = models.DateField("Date lancement", null=True, blank=True)
    date_prevue_fin = models.DateField("Date prévue fin", null=True, blank=True)
    date_fin_reelle = models.DateField("Date fin réelle", null=True, blank=True)

    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    priorite = models.CharField("Priorité", max_length=10, choices=PRIORITE_CHOICES, default='NORMALE')

    bat_file = models.FileField("BAT Validé", upload_to='bat/', blank=True, null=True)
    fiche_technique = models.FileField("Fiche technique", upload_to='fiches_techniques/', blank=True, null=True)

    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='of_crees', verbose_name="Créé par")
    notes = models.TextField("Notes / Instructions", blank=True)
    observation = models.TextField("Observation (Excel style)", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Ordre de Fabrication"
        verbose_name_plural = "Ordres de Fabrication"
        ordering = ['-date_creation']

    def __str__(self):
        return f"OF-{self.numero_of} | {self.client.name}"

    def save(self, *args, **kwargs):
        if not self.numero_of:
            annee = timezone.now().year
            last = OrdreFabrication.objects.filter(numero_of__startswith=f"OF{annee}").order_by('-numero_of').first()
            if last and last.numero_of:
                try: num = int(last.numero_of.replace(f"OF{annee}-", '')) + 1
                except (ValueError, IndexError): num = 1
            else: num = 1
            self.numero_of = f"OF{annee}-{num:04d}"

        if not self.numero_lot:
            annee = timezone.now().year
            last = OrdreFabrication.objects.filter(numero_lot__startswith=f"LOT{annee}").exclude(pk=self.pk).order_by('-numero_lot').first()
            if last and last.numero_lot:
                try: num = int(last.numero_lot.replace(f"LOT{annee}-", '')) + 1
                except (ValueError, IndexError): num = 1
            else: num = 1
            self.numero_lot = f"LOT{annee}-{num:04d}"
        super().save(*args, **kwargs)

    @property
    def nb_etapes(self):
        return self.etapes.count()

    @property
    def etapes_terminees(self):
        return self.etapes.filter(statut='TERMINE').count()

    @property
    def progression(self):
        total = self.nb_etapes
        if total == 0: return 0
        return round((self.etapes_terminees / total) * 100)

    @property
    def est_en_retard(self):
        if self.statut in ['TERMINE', 'ANNULE']: return False
        if not self.date_prevue_fin: return False
        return self.date_prevue_fin < timezone.now().date()

    @property
    def taux_rebut(self):
        if self.quantite_produite == 0: return 0
        return round((self.quantite_rebut / self.quantite_produite) * 100, 2)

    def get_statut_color(self):
        return {
            'BROUILLON': 'gray', 'LANCE': 'cyan',
            'EN_COURS': 'yellow', 'TERMINE': 'green', 'ANNULE': 'red',
        }.get(self.statut, 'gray')

    def get_priorite_color(self):
        return {
            'BASSE': 'gray', 'NORMALE': 'blue',
            'HAUTE': 'orange', 'URGENTE': 'red',
        }.get(self.priorite, 'gray')

    # === METHODES TRACABILITE LOT (Résolution dynamique via Django app registry) ===
    def get_fiches_journalieres(self):
        FicheProductionJournaliere = apps.get_model('core', 'FicheProductionJournaliere')
        return FicheProductionJournaliere.objects.filter(
            Q(of_lie=self) | Q(numero_lot=self.numero_lot) | Q(numero_doc=self.numero_lot)
        ).distinct().order_by('date_fabrication', 'heure_debut')

    def get_saisies_anciennes(self):
        ProductionEntry = apps.get_model('core', 'ProductionEntry')
        return ProductionEntry.objects.filter(
            Q(of_lie=self) | Q(lot=self.numero_lot)
        ).distinct().order_by('date', 'heure_debut')

    def get_fiches_par_type(self):
        fiches = self.get_fiches_journalieres()
        groupes = {
            'EXTRUSION': [], 'FLEXO': [], 'HELIO': [],
            'COMPLEXAGE': [], 'FONDS_CARRES': [],
            'DECOUPE': [], 'DECOUPE2': [],
        }
        for f in fiches:
            if f.type_fiche in groupes:
                groupes[f.type_fiche].append(f)
        return groupes

    def get_consommations_encres(self):
        fiches = self.get_fiches_journalieres().filter(type_fiche__in=['FLEXO', 'HELIO'])
        FicheImpressionEncreGroupe = apps.get_model('core', 'FicheImpressionEncreGroupe')
        encres = FicheImpressionEncreGroupe.objects.filter(fiche__in=fiches).order_by('fiche__date_fabrication', 'groupe_numero')
        return encres

    def get_totaux_lot(self):
        fiches = self.get_fiches_journalieres()
        saisies_old = self.get_saisies_anciennes()
        
        total_prod_kg = 0
        total_dechets_kg = 0
        total_encre_kg = 0
        total_solvant_kg = 0
        total_temps_min = 0
        total_bobines_meres = 0
        total_bobines_filles = 0
        
        for f in fiches:
            total_prod_kg += f.total_prod_kg_calcul or 0
            total_dechets_kg += f.total_dechets_kg or 0
            total_temps_min += f.temps_ouverture_minutes or 0
            
            if f.type_fiche in ['FLEXO', 'HELIO']:
                for enc in f.encres_groupes.all():
                    total_encre_kg += enc.conso_encre_kg or 0
                    total_solvant_kg += enc.conso_solvant_kg or 0
                total_bobines_meres += f.bobines_entrees.count()
                total_bobines_filles += sum(b.nbre_bobines for b in f.bobines_imprimees.all())
            
            elif f.type_fiche in ['DECOUPE', 'DECOUPE2']:
                total_bobines_meres += f.bobines_meres_decoupe.count()
                total_bobines_filles += sum(b.nombre_filles for b in f.bobines_filles_decoupe.all())
        
        for e in saisies_old:
            total_prod_kg += e.prod_kg or 0
            total_dechets_kg += e.total_dechets_kg or 0
            total_temps_min += e.temps_ouverture_minutes or 0

        taux_rebut = round((total_dechets_kg / total_prod_kg * 100), 2) if total_prod_kg > 0 else 0
        rendement = round((total_prod_kg / float(self.quantite_prevue) * 100), 2) if self.quantite_prevue > 0 else 0
        
        heures = int(total_temps_min // 60)
        minutes = int(total_temps_min % 60)
        
        return {
            'total_prod_kg': round(total_prod_kg, 2),
            'total_dechets_kg': round(total_dechets_kg, 2),
            'total_encre_kg': round(total_encre_kg, 2),
            'total_solvant_kg': round(total_solvant_kg, 2),
            'total_temps_min': int(total_temps_min),
            'total_temps_formatted': f"{heures}h {minutes:02d}min",
            'total_bobines_meres': total_bobines_meres,
            'total_bobines_filles': total_bobines_filles,
            'taux_rebut': taux_rebut,
            'rendement': rendement,
            'nb_fiches': fiches.count(),
            'nb_saisies_anciennes': saisies_old.count(),
        }

    def get_chat_messages_lot(self):
        ChatMessage = apps.get_model('core', 'ChatMessage')
        return ChatMessage.objects.filter(of_lie=self).order_by('-date_envoi')

    @property
    def has_fiches(self):
        return self.get_fiches_journalieres().exists()

    @property
    def workflow_visualisation(self):
        fiches_reelles = list(self.get_fiches_journalieres())
        workflow = []
        type_map = {
            'EXTRUSION': {'icone': '🌀', 'couleur': 'purple', 'ordre': 1},
            'FLEXO': {'icone': '🖨️', 'couleur': 'blue', 'ordre': 2},
            'HELIO': {'icone': '🔄', 'couleur': 'cyan', 'ordre': 2},
            'COMPLEXAGE': {'icone': '🔗', 'couleur': 'pink', 'ordre': 3},
            'DECOUPE': {'icone': '✂️', 'couleur': 'orange', 'ordre': 4},
            'DECOUPE2': {'icone': '✂️', 'couleur': 'orange', 'ordre': 4},
            'FONDS_CARRES': {'icone': '🛍️', 'couleur': 'yellow', 'ordre': 5},
        }
        
        for f in fiches_reelles:
            info = type_map.get(f.type_fiche, {'icone': '⚙️', 'couleur': 'gray', 'ordre': 99})
            workflow.append({
                'type': f.type_fiche,
                'display': f.get_type_fiche_display(),
                'icone': info['icone'],
                'couleur': info['couleur'],
                'date': f.date_fabrication,
                'heure_debut': f.heure_debut,
                'heure_fin': f.heure_fin,
                'machine': f.machine.name if f.machine else '—',
                'conducteur': f.conducteur or '—',
                'poids_produit': f.total_prod_kg_calcul,
                'total_dechets': f.total_dechets_kg or 0,
                'fiche_id': f.id,
                'fiche_numero': f.numero_fiche,
            })
        
        return sorted(workflow, key=lambda x: (x['date'], x['heure_debut'] or datetime.time.min))

    @classmethod
    def chercher_par_lot(cls, numero_lot):
        if not numero_lot:
            return None
        return cls.objects.filter(
            Q(numero_lot__iexact=numero_lot) | Q(numero_of__iexact=numero_lot)
        ).first()


class EtapeProduction(models.Model):
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'), ('PRET', 'Prêt à lancer'),
        ('EN_COURS', 'En cours'), ('PAUSE', 'En pause'),
        ('TERMINE', 'Terminé'), ('ANNULE', 'Annulé'),
    ]

    of = models.ForeignKey(OrdreFabrication, on_delete=models.CASCADE, related_name='etapes', verbose_name="Ordre de Fabrication")
    process_type = models.ForeignKey(ProcessType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Type de processus")
    atelier = models.ForeignKey('core.Atelier', on_delete=models.SET_NULL, null=True, blank=True, related_name='etapes_planifiees', verbose_name="Atelier")
    machine = models.ForeignKey('core.Machine', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Machine")
    operateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Opérateur", related_name='etapes_assignees')

    numero_etape = models.IntegerField("N° Étape", default=1)
    nom_etape = models.CharField("Nom étape", max_length=100, blank=True)

    support = models.CharField("Support (ex: OPP 20 TRS 920MM)", max_length=200, blank=True)
    developpement = models.FloatField("Développement (mm)", default=0, null=True, blank=True)
    quantite_ml = models.FloatField("Quantité ML (mètres linéaires)", default=0, null=True, blank=True)
    nb_bobines = models.IntegerField("Nombre de bobines", default=0, null=True, blank=True)
    numero_lot_etape = models.CharField("N° Lot étape (ex: 90PE440-8)", max_length=100, blank=True)
    observation = models.TextField("Observation (RELIQUAT, BAT+PROD...)", blank=True)

    quantite_entree = models.FloatField("Quantité entrée (kg)", default=0)
    quantite_sortie = models.FloatField("Quantité sortie (kg)", default=0)
    quantite_rebut = models.FloatField("Rebuts (kg)", default=0)

    date_prevue_debut = models.DateTimeField("Début prévu", null=True, blank=True)
    date_prevue_fin = models.DateTimeField("Fin prévue", null=True, blank=True)
    date_debut_reel = models.DateTimeField("Début réel", null=True, blank=True)
    date_fin_reel = models.DateTimeField("Fin réelle", null=True, blank=True)
    temps_arret_minutes = models.IntegerField("Temps d'arrêt (min)", default=0)

    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    genere_semi_produit = models.BooleanField("Génère semi-produit", default=True)
    notes = models.TextField("Notes / Instructions", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Étape de production"
        verbose_name_plural = "Étapes de production"
        ordering = ['of', 'numero_etape']
        unique_together = ['of', 'numero_etape']

    def __str__(self):
        return f"Étape {self.numero_etape} - {self.get_nom_display()} - {self.of.numero_of}"

    def save(self, *args, **kwargs):
        if self.machine and not self.atelier and self.machine.atelier:
            self.atelier = self.machine.atelier
        if self.process_type and not self.atelier and self.process_type.atelier_lie:
            self.atelier = self.process_type.atelier_lie
        if not self.numero_lot_etape and self.of and self.of.numero_lot:
            self.numero_lot_etape = self.of.numero_lot
        super().save(*args, **kwargs)

    def get_nom_display(self):
        if self.nom_etape: return self.nom_etape
        if self.process_type: return self.process_type.nom
        return f"Étape {self.numero_etape}"

    @property
    def progression(self):
        if self.statut == 'TERMINE': return 100
        if self.statut in ['EN_ATTENTE', 'PRET']: return 0
        if self.quantite_entree > 0:
            return min(100, round((self.quantite_sortie / self.quantite_entree) * 100))
        return 50 if self.statut == 'EN_COURS' else 0

    @property
    def rendement(self):
        if self.quantite_entree == 0: return 0
        return round((self.quantite_sortie / self.quantite_entree) * 100, 2)


class SemiProduit(models.Model):
    STATUT_CHOICES = [
        ('DISPONIBLE', 'Disponible'), ('RESERVE', 'Réservé'),
        ('CONSOMME', 'Consommé'), ('BLOQUE', 'Bloqué qualité'),
        ('REBUT', 'Rebut'),
    ]
    TYPE_CHOICES = [
        ('FILM_EXTRUDE', 'Film extrudé'), ('FILM_IMPRIME', 'Film imprimé'),
        ('FILM_COMPLEXE', 'Film complexé'), ('BOBINE_MERE', 'Bobine mère'),
        ('BOBINE_FILLE', 'Bobine fille'), ('AUTRE', 'Autre'),
    ]

    reference = models.CharField("Référence", max_length=100, unique=True, blank=True)
    designation = models.CharField("Désignation", max_length=200)
    type_semi_produit = models.CharField("Type", max_length=20, choices=TYPE_CHOICES, default='AUTRE')
    of_origine = models.ForeignKey(OrdreFabrication, on_delete=models.SET_NULL, null=True, related_name='semi_produits_generes', verbose_name="OF d'origine")
    etape_origine = models.ForeignKey(EtapeProduction, on_delete=models.SET_NULL, null=True, related_name='semi_produits_generes', verbose_name="Étape d'origine")
    etape_destination = models.ForeignKey(EtapeProduction, on_delete=models.SET_NULL, null=True, blank=True, related_name='semi_produits_consommes', verbose_name="Étape de consommation")
    quantite = models.FloatField("Quantité (kg)", default=0)
    unite = models.CharField("Unité", max_length=10, default='kg')
    emplacement = models.ForeignKey('core.StockLocation', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Emplacement")
    laize = models.FloatField("Laize (mm)", default=0, null=True, blank=True)
    longueur = models.FloatField("Longueur (m)", default=0, null=True, blank=True)
    poids_bobine = models.FloatField("Poids bobine (kg)", default=0, null=True, blank=True)
    numero_bobine = models.CharField("N° Bobine", max_length=50, blank=True)
    date_creation = models.DateTimeField("Date création", auto_now_add=True)
    date_peremption = models.DateField("Date péremption", null=True, blank=True)
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='DISPONIBLE')
    conforme = models.BooleanField("Conforme", default=True)
    notes_qualite = models.TextField("Notes qualité", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Semi-produit"
        verbose_name_plural = "Semi-produits"
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.reference} - {self.designation}"

    def save(self, *args, **kwargs):
        if not self.reference:
            annee = timezone.now().year
            prefix = 'SP'
            if self.type_semi_produit == 'FILM_EXTRUDE': prefix = 'SPE'
            elif self.type_semi_produit == 'FILM_IMPRIME': prefix = 'SPI'
            elif self.type_semi_produit == 'FILM_COMPLEXE': prefix = 'SPC'
            elif self.type_semi_produit == 'BOBINE_MERE': prefix = 'BM'
            elif self.type_semi_produit == 'BOBINE_FILLE': prefix = 'BF'

            last = SemiProduit.objects.filter(reference__startswith=f"{prefix}{annee}").order_by('-reference').first()
            if last and last.reference:
                try: num = int(last.reference.replace(f"{prefix}{annee}-", '')) + 1
                except (ValueError, IndexError): num = 1
            else: num = 1
            self.reference = f"{prefix}{annee}-{num:05d}"
        super().save(*args, **kwargs)


class SuiviProduction(models.Model):
    TYPE_EVENEMENT = [
        ('DEMARRAGE', 'Démarrage'), ('ARRET', 'Arrêt'), ('REPRISE', 'Reprise'),
        ('FIN', 'Fin'), ('PAUSE', 'Pause'), ('INCIDENT', 'Incident'),
        ('CONTROLE', 'Contrôle qualité'), ('CHANGEMENT', 'Changement série'), ('REGLAGE', 'Réglage'),
    ]
    CAUSE_ARRET = [
        ('PANNE', 'Panne machine'), ('REGLAGE', 'Réglage'), ('PAUSE', 'Pause opérateur'),
        ('MATIERE', 'Attente matière'), ('QUALITE', 'Problème qualité'),
        ('MAINTENANCE', 'Maintenance préventive'), ('CHANGEMENT', 'Changement de série'), ('AUTRE', 'Autre'),
    ]

    etape = models.ForeignKey(EtapeProduction, on_delete=models.CASCADE, related_name='suivis', verbose_name="Étape")
    operateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Opérateur")
    date_heure = models.DateTimeField("Date/Heure", default=timezone.now)
    type_evenement = models.CharField("Type", max_length=20, choices=TYPE_EVENEMENT)
    cause_arret = models.CharField("Cause arrêt", max_length=20, choices=CAUSE_ARRET, blank=True)
    quantite_produite = models.FloatField("Quantité produite (kg)", default=0)
    quantite_rebut = models.FloatField("Rebut (kg)", default=0)
    vitesse_machine = models.FloatField("Vitesse machine (m/min)", default=0, null=True, blank=True)
    commentaire = models.TextField("Commentaire", blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Suivi de production"
        verbose_name_plural = "Suivis de production"
        ordering = ['-date_heure']


class ConsommationMatiere(models.Model):
    etape = models.ForeignKey(EtapeProduction, on_delete=models.CASCADE, related_name='consommations', verbose_name="Étape")
    material = models.ForeignKey('core.Material', on_delete=models.CASCADE, verbose_name="Matière première")
    lot = models.ForeignKey('core.StockLot', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Lot")
    quantite_prevue = models.FloatField("Quantité prévue", default=0)
    quantite_reelle = models.FloatField("Quantité réelle", default=0)
    date_consommation = models.DateTimeField("Date", default=timezone.now)

    class Meta:
        app_label = 'core'
        verbose_name = "Consommation matière"
        verbose_name_plural = "Consommations matières"