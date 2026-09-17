from django import forms
from django.forms import inlineformset_factory
from .models import (
    Client, ClientContact, InteractionLog, Opportunite,
    TechnicalProduct, Tooling, Quote,
    ProductionOrder, Supplier, Material, ConsommationEncre,
    Machine, ProductionEntry, CalculTempsProduction,
    OrdreFabrication, EtapeProduction, SemiProduit,
    SuiviProduction, ConsommationMatiere, ProcessType,
    Department, Position, Employee, EmployeeDocument,
    Skill, EmployeeSkill, MachineAuthorization,
    Shift, Attendance, LeaveType, LeaveRequest,
    Payslip, WorkSchedule, ShiftAssignment,
    MedicalVisit, WorkIncident, ProtectiveEquipment,
    Atelier, CompteurMachine, CategoriePiece, PieceRechange,
    MouvementPiece, OrdreMaintenance, ConsommationPiece,
    PlanMaintenancePreventive, AlerteMaintenance,
    # === NOUVEAUX MODELES ===
    FicheProductionJournaliere, FicheExtrusionMatiere, FicheExtrusionArret,
    FicheImpressionBobineEntree, FicheImpressionBobineImprimee, FicheImpressionEncreGroupe,
    FicheComplexageDerouleur1, FicheComplexageDerouleur2, FicheComplexageEnrouleur,
    FicheFondCarreEquipe, FicheDecoupeBobineMere, FicheDecoupeBobineFille
)


# ===========================================================================
# --- CRM FORMS ---
# ===========================================================================

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'name', 'code_client', 'status', 'segment', 'size', 'region',
            'ca_estime', 'sector', 'city', 'address', 'phone', 'email',
            'website', 'commercial', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code_client': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'segment': forms.Select(attrs={'class': 'form-select'}),
            'size': forms.Select(attrs={'class': 'form-select'}),
            'region': forms.Select(attrs={'class': 'form-select'}),
            'ca_estime': forms.NumberInput(attrs={'class': 'form-control'}),
            'sector': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'commercial': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ClientContactForm(forms.ModelForm):
    class Meta:
        model = ClientContact
        fields = ['name', 'role', 'role_custom', 'phone', 'email', 'is_primary', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'role_custom': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class InteractionLogForm(forms.ModelForm):
    class Meta:
        model = InteractionLog
        fields = ['contact', 'commercial', 'type', 'summary', 'details', 'next_action', 'next_action_date']
        widgets = {
            'contact': forms.Select(attrs={'class': 'form-select'}),
            'commercial': forms.Select(attrs={'class': 'form-select'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'summary': forms.TextInput(attrs={'class': 'form-control'}),
            'details': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'next_action': forms.TextInput(attrs={'class': 'form-control'}),
            'next_action_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        if client:
            self.fields['contact'].queryset = ClientContact.objects.filter(client=client)


class OpportuniteForm(forms.ModelForm):
    class Meta:
        model = Opportunite
        fields = [
            'client', 'commercial', 'titre', 'description', 'status',
            'valeur_estimee', 'probabilite', 'date_cloture_prevue', 'notes'
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'commercial': forms.Select(attrs={'class': 'form-select'}),
            'titre': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'valeur_estimee': forms.NumberInput(attrs={'class': 'form-control'}),
            'probabilite': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'date_cloture_prevue': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class QuoteForm(forms.ModelForm):
    class Meta:
        model = Quote
        fields = [
            'client', 'opportunite', 'commercial', 'reference', 'version',
            'date_validite', 'total_amount', 'status', 'pdf_file', 'notes'
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'opportunite': forms.Select(attrs={'class': 'form-select'}),
            'commercial': forms.Select(attrs={'class': 'form-select'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'version': forms.NumberInput(attrs={'class': 'form-control'}),
            'date_validite': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


# ===========================================================================
# --- PREPRESSE FORMS ---
# ===========================================================================

class ProductForm(forms.ModelForm):
    class Meta:
        model = TechnicalProduct
        fields = [
            'client', 'ref_internal', 'name', 'structure_type',
            'width_mm', 'cut_length_mm', 'num_colors', 'artwork_file'
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'ref_internal': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'structure_type': forms.Select(attrs={'class': 'form-select'}),
            'width_mm': forms.NumberInput(attrs={'class': 'form-control'}),
            'cut_length_mm': forms.NumberInput(attrs={'class': 'form-control'}),
            'num_colors': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class ToolForm(forms.ModelForm):
    class Meta:
        model = Tooling
        fields = ['product', 'tool_type', 'serial_number', 'max_impressions', 'current_impressions']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'tool_type': forms.Select(attrs={'class': 'form-select'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'max_impressions': forms.NumberInput(attrs={'class': 'form-control'}),
            'current_impressions': forms.NumberInput(attrs={'class': 'form-control'}),
        }


# ===========================================================================
# --- STOCK FORMS ---
# ===========================================================================

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'email']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['name', 'category', 'quantity', 'unit', 'min_threshold', 'supplier', 'price_per_unit']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'min_threshold': forms.NumberInput(attrs={'class': 'form-control'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'price_per_unit': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class MachineForm(forms.ModelForm):
    class Meta:
        model = Machine
        fields = ['name', 'type', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class ConsommationEncreForm(forms.ModelForm):
    class Meta:
        model = ConsommationEncre
        fields = [
            'job_name', 'date', 'process_type', 'support', 'laize',
            'bobine_in', 'bobine_out', 'metrage',
            'encre_noir', 'encre_magenta', 'encre_jaune', 'encre_cyan',
            'encre_dore', 'encre_silver', 'encre_orange', 'encre_blanc', 'encre_vernis',
            'solvant_metoxyn', 'solvant_2080'
        ]
        widgets = {
            'job_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'process_type': forms.Select(attrs={'class': 'form-select'}),
            'support': forms.TextInput(attrs={'class': 'form-control'}),
            'laize': forms.NumberInput(attrs={'class': 'form-control'}),
            'bobine_in': forms.NumberInput(attrs={'class': 'form-control'}),
            'bobine_out': forms.NumberInput(attrs={'class': 'form-control'}),
            'metrage': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_noir': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_magenta': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_jaune': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_cyan': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_dore': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_silver': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_orange': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_blanc': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_vernis': forms.NumberInput(attrs={'class': 'form-control'}),
            'solvant_metoxyn': forms.NumberInput(attrs={'class': 'form-control'}),
            'solvant_2080': forms.NumberInput(attrs={'class': 'form-control'}),
        }


# ===========================================================================
# 🆕 FORMULAIRE SAISIE UNIQUE UNIFIÉE PRODUCTION (ANCIEN - CONSERVÉ)
# ===========================================================================

class ProductionEntryForm(forms.ModelForm):
    class Meta:
        model = ProductionEntry
        fields = [
            'date', 'produit', 'support', 'client', 'equipe', 'machine', 'type_process',
            'unite_commande', 'quantite_commandee_unites', 'grammage_g_m2',
            'quantite_lancee', 'lot', 'laize',
            'pas_mm', 'laize_produit_mm', 'laize_bobine_mere_mm', 'longueur_bobine_mere_m',
            'vitesse_machine_trmin', 'temps_calage_min',
            'heure_debut', 'heure_fin', 'prod_ml', 'prod_kg',
            'dechets_demarrage', 'dechets_lisiere', 'dechets_jonction', 'dechets_transport',
            'rebobinage_kg',
            'of_lie', 'etape_liee',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'produit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: CRISTA 1.5L / SAFINA 1KG'}),
            'support': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: OPP 38 BLNC / PET 12 TRS'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'equipe': forms.Select(attrs={'class': 'form-select'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'type_process': forms.Select(attrs={'class': 'form-select'}),
            'unite_commande': forms.Select(attrs={'class': 'form-select', 'id': 'id_unite_commande'}),
            'quantite_commandee_unites': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 6000000 (Étiquettes/Sacs) ou 2000 (KG) ou 40000 (ML)'}),
            'grammage_g_m2': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 38.0 g/m²', 'step': '0.1'}),
            'quantite_lancee': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'kg'}),
            'lot': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'N° Lot / Ref', 'list': 'lots_existants'}),
            'laize': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'mm'}),
            'pas_mm': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '275'}),
            'laize_produit_mm': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '65'}),
            'laize_bobine_mere_mm': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '825'}),
            'longueur_bobine_mere_m': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '10000'}),
            'vitesse_machine_trmin': forms.NumberInput(attrs={'class': 'form-control', 'min': 100, 'max': 400, 'placeholder': '100 - 400 tr/min'}),
            'temps_calage_min': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'minutes'}),
            'heure_debut': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'prod_ml': forms.NumberInput(attrs={'class': 'form-control'}),
            'prod_kg': forms.NumberInput(attrs={'class': 'form-control'}),
            'dechets_demarrage': forms.NumberInput(attrs={'class': 'form-control'}),
            'dechets_lisiere': forms.NumberInput(attrs={'class': 'form-control'}),
            'dechets_jonction': forms.NumberInput(attrs={'class': 'form-control'}),
            'dechets_transport': forms.NumberInput(attrs={'class': 'form-control'}),
            'rebobinage_kg': forms.NumberInput(attrs={'class': 'form-control'}),
            'of_lie': forms.Select(attrs={'class': 'form-select'}),
            'etape_liee': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'machine' in self.fields:
            self.fields['machine'].queryset = Machine.objects.filter(
                est_active=True
            ).exclude(type__in=['NETT_CL', 'NETT_AN']).order_by('name')
        if 'of_lie' in self.fields:
            self.fields['of_lie'].queryset = OrdreFabrication.objects.exclude(
                statut__in=['TERMINE', 'ANNULE']
            ).order_by('-date_creation')
            self.fields['of_lie'].required = False
        if 'etape_liee' in self.fields:
            self.fields['etape_liee'].required = False


class CalculTempsProductionForm(forms.ModelForm):
    class Meta:
        model = CalculTempsProduction
        fields = [
            'nom_job', 'client', 'type_produit',
            'quantite_commandee', 'unite_quantite',
            'pas_mm', 'laize_produit_mm', 'grammage_g_m2',
            'laize_bobine_mere_mm', 'longueur_bobine_mere_m',
            'process_impression', 'machine_impression', 'vitesse_impression_mmin',
            'temps_calage_impression_min', 'temps_decalage_bobine_min',
            'machine_decoupe', 'vitesse_decoupe_mmin',
            'temps_calage_decoupe_min', 'temps_rebobinage_fille_min',
            'date_debut_prevue', 'notes'
        ]
        widgets = {
            'nom_job': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Commande 2 Mllions Étiquettes'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'type_produit': forms.Select(attrs={'class': 'form-select'}),
            'quantite_commandee': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'unite_quantite': forms.Select(attrs={'class': 'form-select'}),
            'pas_mm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': '275'}),
            'laize_produit_mm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': '65'}),
            'grammage_g_m2': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': '80'}),
            'laize_bobine_mere_mm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': '825'}),
            'longueur_bobine_mere_m': forms.NumberInput(attrs={'class': 'form-control', 'step': '10', 'placeholder': '10000'}),
            'process_impression': forms.Select(attrs={'class': 'form-select'}),
            'machine_impression': forms.Select(attrs={'class': 'form-select'}),
            'vitesse_impression_mmin': forms.NumberInput(attrs={'class': 'form-control', 'min': 100, 'max': 400, 'step': '5', 'placeholder': '200'}),
            'temps_calage_impression_min': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'temps_decalage_bobine_min': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'machine_decoupe': forms.Select(attrs={'class': 'form-select'}),
            'vitesse_decoupe_mmin': forms.NumberInput(attrs={'class': 'form-control', 'min': 100, 'max': 400, 'step': '5', 'placeholder': '250'}),
            'temps_calage_decoupe_min': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'temps_rebobinage_fille_min': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'date_debut_prevue': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observations complémentaires...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'machine_impression' in self.fields:
            self.fields['machine_impression'].queryset = Machine.objects.filter(
                est_active=True
            ).exclude(type__in=['NETT_CL', 'NETT_AN']).order_by('name')
        if 'machine_decoupe' in self.fields:
            self.fields['machine_decoupe'].queryset = Machine.objects.filter(
                est_active=True
            ).exclude(type__in=['NETT_CL', 'NETT_AN']).order_by('name')


class ProductionOrderForm(forms.ModelForm):
    class Meta:
        model = ProductionOrder
        fields = [
            'of_number', 'client', 'product', 'machine',
            'quantity_planned', 'start_time', 'end_time',
            'status', 'bat_file', 'produced_qty', 'waste_qty', 'opportunite'
        ]
        widgets = {
            'of_number': forms.TextInput(attrs={'class': 'form-control'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'product': forms.Select(attrs={'class': 'form-select'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'quantity_planned': forms.NumberInput(attrs={'class': 'form-control'}),
            'start_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'produced_qty': forms.NumberInput(attrs={'class': 'form-control'}),
            'waste_qty': forms.NumberInput(attrs={'class': 'form-control'}),
            'opportunite': forms.Select(attrs={'class': 'form-select'}),
        }


# ===========================================================================
# --- FORMULAIRES DRH ---
# ===========================================================================

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Production'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: PROD'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ['name', 'code', 'category', 'department', 'description', 
                  'salaire_min', 'salaire_max', 'requires_machine_auth', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'salaire_min': forms.NumberInput(attrs={'class': 'form-control'}),
            'salaire_max': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            'nom', 'prenom', 'nom_arabe', 'date_naissance', 'lieu_naissance',
            'genre', 'situation_familiale', 'nb_enfants',
            'cin', 'num_securite_sociale', 'num_carte_chifa',
            'adresse', 'wilaya', 'commune', 'telephone', 'telephone_urgence', 'email',
            'department', 'position', 'superieur', 'machine_affectee', 'atelier',
            'type_contrat', 'date_embauche', 'date_fin_contrat', 'salaire_base',
            'statut', 'photo', 'notes',
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de famille'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom'}),
            'nom_arabe': forms.TextInput(attrs={'class': 'form-control', 'dir': 'rtl'}),
            'date_naissance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lieu_naissance': forms.TextInput(attrs={'class': 'form-control'}),
            'genre': forms.Select(attrs={'class': 'form-select'}),
            'situation_familiale': forms.Select(attrs={'class': 'form-select'}),
            'nb_enfants': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'cin': forms.TextInput(attrs={'class': 'form-control'}),
            'num_securite_sociale': forms.TextInput(attrs={'class': 'form-control'}),
            'num_carte_chifa': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'wilaya': forms.TextInput(attrs={'class': 'form-control'}),
            'commune': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone_urgence': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'position': forms.Select(attrs={'class': 'form-select'}),
            'superieur': forms.Select(attrs={'class': 'form-select'}),
            'machine_affectee': forms.Select(attrs={'class': 'form-select'}),
            'atelier': forms.TextInput(attrs={'class': 'form-control'}),
            'type_contrat': forms.Select(attrs={'class': 'form-select'}),
            'date_embauche': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin_contrat': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'salaire_base': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class EmployeeDocumentForm(forms.ModelForm):
    class Meta:
        model = EmployeeDocument
        fields = ['type_document', 'nom', 'fichier', 'date_expiration', 'notes']
        widgets = {
            'type_document': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'date_expiration': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ['name', 'code', 'category', 'description', 'machine_associee', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'machine_associee': forms.Select(attrs={'class': 'form-select'}),
        }


class EmployeeSkillForm(forms.ModelForm):
    class Meta:
        model = EmployeeSkill
        fields = ['skill', 'level', 'date_acquisition', 'certificat', 'notes']
        widgets = {
            'skill': forms.Select(attrs={'class': 'form-select'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'date_acquisition': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class MachineAuthorizationForm(forms.ModelForm):
    class Meta:
        model = MachineAuthorization
        fields = ['machine', 'niveau_autorisation', 'date_expiration', 'notes']
        widgets = {
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'niveau_autorisation': forms.Select(attrs={'class': 'form-select'}),
            'date_expiration': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ShiftForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = ['name', 'code', 'heure_debut', 'heure_fin', 'pause_debut', 
                  'pause_fin', 'heures_travail', 'couleur', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'heure_debut': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'pause_debut': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'pause_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heures_travail': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'couleur': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['employee', 'date', 'shift', 'heure_arrivee', 'heure_depart',
                  'statut', 'machine', 'atelier', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'shift': forms.Select(attrs={'class': 'form-select'}),
            'heure_arrivee': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_depart': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'atelier': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class AttendanceBulkForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    shift = forms.ModelChoiceField(
        queryset=Shift.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class LeaveTypeForm(forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = ['name', 'code', 'jours_par_an', 'paye', 'justificatif_requis', 'couleur', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'jours_par_an': forms.NumberInput(attrs={'class': 'form-control'}),
            'couleur': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['type_conge', 'date_debut', 'date_fin', 'motif', 'justificatif']
        widgets = {
            'type_conge': forms.Select(attrs={'class': 'form-select'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'motif': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PayslipForm(forms.ModelForm):
    class Meta:
        model = Payslip
        fields = [
            'employee', 'mois', 'annee', 'jours_travailles', 'jours_absence', 'jours_conge',
            'heures_supplementaires_25', 'heures_supplementaires_50', 'heures_supplementaires_100',
            'heures_nuit', 'prime_rendement', 'prime_presence', 'prime_transport', 'prime_panier',
            'autres_primes', 'avance_salaire', 'pret', 'autres_retenues', 'notes'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'mois': forms.Select(attrs={'class': 'form-select'}, choices=[(i, f"{i:02d}") for i in range(1, 13)]),
            'annee': forms.NumberInput(attrs={'class': 'form-control'}),
            'jours_travailles': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'jours_absence': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'jours_conge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'heures_supplementaires_25': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'heures_supplementaires_50': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'heures_supplementaires_100': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'heures_nuit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'prime_rendement': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'prime_presence': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'prime_transport': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'prime_panier': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'autres_primes': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'avance_salaire': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'pret': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'autres_retenues': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class WorkScheduleForm(forms.ModelForm):
    class Meta:
        model = WorkSchedule
        fields = ['name', 'date_debut', 'date_fin', 'department', 'machine', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ShiftAssignmentForm(forms.ModelForm):
    class Meta:
        model = ShiftAssignment
        fields = ['employee', 'shift', 'date', 'machine', 'poste', 'est_remplacement', 'remplace', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'shift': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'poste': forms.TextInput(attrs={'class': 'form-control'}),
            'remplace': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class MedicalVisitForm(forms.ModelForm):
    class Meta:
        model = MedicalVisit
        fields = ['employee', 'type_visite', 'date_visite', 'medecin', 'resultat',
                  'restrictions', 'date_prochaine_visite', 'certificat', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'type_visite': forms.Select(attrs={'class': 'form-select'}),
            'date_visite': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'medecin': forms.TextInput(attrs={'class': 'form-control'}),
            'resultat': forms.Select(attrs={'class': 'form-select'}),
            'restrictions': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'date_prochaine_visite': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class WorkIncidentForm(forms.ModelForm):
    class Meta:
        model = WorkIncident
        fields = ['employee', 'type_incident', 'gravite', 'date_incident', 'lieu', 'machine',
                  'description', 'cause', 'temoins', 'jours_arret', 'blessure', 'soins_prodigues',
                  'actions_immediates', 'actions_correctives', 'rapport', 'photos']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'type_incident': forms.Select(attrs={'class': 'form-select'}),
            'gravite': forms.Select(attrs={'class': 'form-select'}),
            'date_incident': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'lieu': forms.TextInput(attrs={'class': 'form-control'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'cause': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'temoins': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'jours_arret': forms.NumberInput(attrs={'class': 'form-control'}),
            'blessure': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'soins_prodigues': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'actions_immediates': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'actions_correctives': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ProtectiveEquipmentForm(forms.ModelForm):
    class Meta:
        model = ProtectiveEquipment
        fields = ['employee', 'type_equipement', 'designation', 'date_attribution',
                  'date_expiration', 'quantite', 'taille', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'type_equipement': forms.Select(attrs={'class': 'form-select'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'date_attribution': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_expiration': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'taille': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


# ===========================================================================
# --- OF MULTI-PROCESSUS FORMS ---
# ===========================================================================

class OrdreFabricationForm(forms.ModelForm):
    class Meta:
        model = OrdreFabrication
        fields = [
            'numero_of', 'numero_lot', 'client', 'produit', 'opportunite',
            'quantite_prevue', 'support',
            'dimension_mandrin', 'diametre_bobine_fille',
            'laize', 'epaisseur', 'date_lancement', 'date_prevue_fin',
            'priorite', 'bat_file', 'fiche_technique', 'notes', 'observation'
        ]
        widgets = {
            'numero_of': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Auto-généré si vide (ex: OF2025-0001)'}),
            'numero_lot': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Auto-généré si vide (ex: LOT2025-0001)'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'produit': forms.Select(attrs={'class': 'form-select'}),
            'opportunite': forms.Select(attrs={'class': 'form-select'}),
            'quantite_prevue': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'support': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: OPP 20 TRS, PE 90μ...'}),
            'dimension_mandrin': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'diametre_bobine_fille': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'laize': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'epaisseur': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'date_lancement': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_prevue_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'priorite': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Instructions spéciales...'}),
            'observation': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Ex: BAT SEULEMENT, RELIQUAT, BAT+PROD...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['numero_of'].required = False
        self.fields['numero_lot'].required = False
        self.fields['opportunite'].required = False
        self.fields['bat_file'].required = False
        self.fields['fiche_technique'].required = False


class EtapeProductionForm(forms.ModelForm):
    class Meta:
        model = EtapeProduction
        fields = [
            'numero_etape', 'nom_etape', 'process_type', 'atelier', 'machine',
            'operateur', 'quantite_entree',
            'support', 'developpement', 'quantite_ml', 'nb_bobines',
            'numero_lot_etape', 'observation',
            'date_prevue_debut', 'date_prevue_fin', 'genere_semi_produit', 'notes'
        ]
        widgets = {
            'numero_etape': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'nom_etape': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Impression Flexo'}),
            'process_type': forms.Select(attrs={'class': 'form-select'}),
            'atelier': forms.Select(attrs={'class': 'form-select'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'operateur': forms.Select(attrs={'class': 'form-select'}),
            'quantite_entree': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'support': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: OPP 20 TRS 920MM'}),
            'developpement': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Ex: 680'}),
            'quantite_ml': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Mètres linéaires'}),
            'nb_bobines': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'numero_lot_etape': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 90PE440-8, 08CN70'}),
            'observation': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Ex: RELIQUAT, BAT+PROD, BAT SEULEMENT'}),
            'date_prevue_debut': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'date_prevue_fin': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'genere_semi_produit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'machine' in self.fields:
            self.fields['machine'].queryset = Machine.objects.filter(
                est_active=True
            ).exclude(type__in=['NETT_CL', 'NETT_AN']).order_by('atelier__nom', 'name')
        if 'atelier' in self.fields:
            self.fields['atelier'].queryset = Atelier.objects.filter(est_actif=True).order_by('ordre_affichage', 'nom')
            self.fields['atelier'].required = False


EtapeProductionFormSet = inlineformset_factory(
    OrdreFabrication,
    EtapeProduction,
    form=EtapeProductionForm,
    extra=3,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


class SuiviProductionForm(forms.ModelForm):
    class Meta:
        model = SuiviProduction
        fields = [
            'type_evenement', 'cause_arret', 'quantite_produite',
            'quantite_rebut', 'vitesse_machine', 'commentaire'
        ]
        widgets = {
            'type_evenement': forms.Select(attrs={'class': 'form-select'}),
            'cause_arret': forms.Select(attrs={'class': 'form-select'}),
            'quantite_produite': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'quantite_rebut': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'vitesse_machine': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'commentaire': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class SemiProduitForm(forms.ModelForm):
    class Meta:
        model = SemiProduit
        fields = [
            'designation', 'type_semi_produit', 'quantite', 'unite',
            'emplacement', 'laize', 'longueur', 'poids_bobine',
            'numero_bobine', 'statut', 'conforme', 'notes_qualite'
        ]
        widgets = {
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'type_semi_produit': forms.Select(attrs={'class': 'form-select'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'unite': forms.TextInput(attrs={'class': 'form-control'}),
            'emplacement': forms.Select(attrs={'class': 'form-select'}),
            'laize': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'longueur': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'poids_bobine': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'numero_bobine': forms.TextInput(attrs={'class': 'form-control'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'conforme': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes_qualite': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ConsommationMatiereForm(forms.ModelForm):
    class Meta:
        model = ConsommationMatiere
        fields = ['material', 'lot', 'quantite_prevue', 'quantite_reelle']
        widgets = {
            'material': forms.Select(attrs={'class': 'form-select'}),
            'lot': forms.Select(attrs={'class': 'form-select'}),
            'quantite_prevue': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'quantite_reelle': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class ProcessTypeForm(forms.ModelForm):
    class Meta:
        model = ProcessType
        fields = ['code', 'nom', 'description', 'ordre_defaut', 'icone', 'couleur', 'atelier_lie', 'est_actif']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'ordre_defaut': forms.NumberInput(attrs={'class': 'form-control'}),
            'icone': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 10}),
            'couleur': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'atelier_lie': forms.Select(attrs={'class': 'form-select'}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class OFLancementRapideForm(forms.Form):
    client = forms.ModelChoiceField(
        queryset=Client.objects.filter(status='ACTIVE'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Client"
    )
    produit = forms.ModelChoiceField(
        queryset=TechnicalProduct.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Produit"
    )
    quantite = forms.FloatField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
        label="Quantité (kg)"
    )
    support = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: OPP 20 TRS'}),
        label="Support"
    )
    priorite = forms.ChoiceField(
        choices=OrdreFabrication.PRIORITE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='NORMALE',
        label="Priorité"
    )
    date_lancement = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Date lancement"
    )

    etape_extrusion = forms.BooleanField(required=False, initial=True, label="Extrusion")
    machine_extrusion = forms.ModelChoiceField(
        queryset=Machine.objects.filter(type='EXT'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Machine"
    )
    qte_extrusion = forms.FloatField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    support_extrusion = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Support extrusion'}))

    etape_impression = forms.BooleanField(required=False, initial=True, label="Impression")
    machine_impression = forms.ModelChoiceField(
        queryset=Machine.objects.filter(type__in=['IMP', 'HELIO']),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Machine"
    )
    qte_impression = forms.FloatField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    support_impression = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Support impression'}))
    developpement_impression = forms.FloatField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Ex: 680'}))

    etape_complexage = forms.BooleanField(required=False, initial=False, label="Complexage")
    machine_complexage = forms.ModelChoiceField(
        queryset=Machine.objects.filter(type='COMP'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Machine"
    )
    qte_complexage = forms.FloatField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control'}))

    etape_decoupe = forms.BooleanField(required=False, initial=True, label="Découpe")
    machine_decoupe = forms.ModelChoiceField(
        queryset=Machine.objects.filter(type__in=['DEC', 'DEC2']),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Machine"
    )
    qte_decoupe = forms.FloatField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control'}))

    etape_fond_carre = forms.BooleanField(required=False, initial=False, label="Fond Carré")
    machine_fond_carre = forms.ModelChoiceField(
        queryset=Machine.objects.filter(type__in=['SAC_FC', 'SAC_SO']),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Machine"
    )
    qte_fond_carre = forms.FloatField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control'}))


# ===========================================================================
# --- FORMULAIRES MAINTENANCE ---
# ===========================================================================

class AtelierForm(forms.ModelForm):
    class Meta:
        model = Atelier
        fields = ['nom', 'code', 'type_atelier', 'description', 'responsable',
                  'ordre_affichage', 'icone', 'couleur', 'est_actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Atelier Impression'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: IMP'}),
            'type_atelier': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'responsable': forms.Select(attrs={'class': 'form-select'}),
            'ordre_affichage': forms.NumberInput(attrs={'class': 'form-control'}),
            'icone': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 10}),
            'couleur': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }


class MachineMaintenanceForm(forms.ModelForm):
    class Meta:
        model = Machine
        fields = [
            'code_machine', 'name', 'type', 'atelier',
            'marque', 'modele', 'numero_serie', 'annee_fabrication',
            'date_mise_en_service', 'fournisseur_machine',
            'puissance_kw', 'vitesse_max', 'laize_max', 'laize_min', 'nb_couleurs',
            'status', 'criticite',
            'cout_acquisition', 'cout_horaire',
            'photo', 'documentation', 'notes',
        ]
        widgets = {
            'code_machine': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Auto si vide'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Flexo 8 couleurs'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'atelier': forms.Select(attrs={'class': 'form-select'}),
            'marque': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Windmöller'}),
            'modele': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Miraflex II'}),
            'numero_serie': forms.TextInput(attrs={'class': 'form-control'}),
            'annee_fabrication': forms.NumberInput(attrs={'class': 'form-control', 'min': 1950, 'max': 2030}),
            'date_mise_en_service': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fournisseur_machine': forms.Select(attrs={'class': 'form-select'}),
            'puissance_kw': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'vitesse_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'laize_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'laize_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'nb_couleurs': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'criticite': forms.Select(attrs={'class': 'form-select'}),
            'cout_acquisition': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cout_horaire': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code_machine'].required = False


class CompteurMachineForm(forms.ModelForm):
    class Meta:
        model = CompteurMachine
        fields = ['machine', 'type_compteur', 'valeur', 'notes']
        widgets = {
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'type_compteur': forms.Select(attrs={'class': 'form-select'}),
            'valeur': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class CategoriePieceForm(forms.ModelForm):
    class Meta:
        model = CategoriePiece
        fields = ['nom', 'code', 'description', 'icone']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'icone': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 10}),
        }


class PieceRechangeForm(forms.ModelForm):
    class Meta:
        model = PieceRechange
        fields = [
            'reference', 'designation', 'categorie',
            'machines_compatibles', 'quantite_stock', 'unite',
            'stock_minimum', 'stock_maximum',
            'prix_unitaire', 'fournisseur', 'delai_livraison_jours',
            'emplacement_stock', 'marque_piece', 'reference_fournisseur',
            'photo', 'notes',
        ]
        widgets = {
            'reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: ROUL-6205'}),
            'designation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Roulement 6205'}),
            'categorie': forms.Select(attrs={'class': 'form-select'}),
            'machines_compatibles': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 5}),
            'quantite_stock': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'unite': forms.Select(attrs={'class': 'form-select'}),
            'stock_minimum': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'stock_maximum': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'prix_unitaire': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fournisseur': forms.Select(attrs={'class': 'form-select'}),
            'delai_livraison_jours': forms.NumberInput(attrs={'class': 'form-control'}),
            'emplacement_stock': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Étagère A3-C2'}),
            'marque_piece': forms.TextInput(attrs={'class': 'form-control'}),
            'reference_fournisseur': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class OrdreMaintenanceForm(forms.ModelForm):
    class Meta:
        model = OrdreMaintenance
        fields = [
            'type_maintenance', 'priorite', 'machine',
            'titre', 'description_probleme',
            'technicien_principal', 'date_planifiee',
            'notes',
        ]
        widgets = {
            'type_maintenance': forms.Select(attrs={'class': 'form-select'}),
            'priorite': forms.Select(attrs={'class': 'form-select'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'titre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Arrêt extrudeuse — surchauffe'}),
            'description_probleme': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'technicien_principal': forms.Select(attrs={'class': 'form-select'}),
            'date_planifiee': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ClotureOrdreMaintenanceForm(forms.ModelForm):
    class Meta:
        model = OrdreMaintenance
        fields = [
            'actions_realisees', 'cause_racine',
            'temps_arret_minutes', 'temps_intervention_minutes',
            'cout_main_oeuvre', 'cout_externe',
            'rapport', 'photos_avant', 'photos_apres', 'notes',
        ]
        widgets = {
            'actions_realisees': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Décrivez ce qui a été fait...'}),
            'cause_racine': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Cause identifiée...'}),
            'temps_arret_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'temps_intervention_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'cout_main_oeuvre': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cout_externe': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ConsommationPieceForm(forms.ModelForm):
    class Meta:
        model = ConsommationPiece
        fields = ['piece', 'quantite', 'notes']
        widgets = {
            'piece': forms.Select(attrs={'class': 'form-select'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': 0.1}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class PlanMaintenancePreventiveForm(forms.ModelForm):
    class Meta:
        model = PlanMaintenancePreventive
        fields = [
            'machine', 'titre', 'description', 'instructions',
            'type_frequence', 'frequence_jours', 'frequence_heures',
            'frequence_metres', 'frequence_tours',
            'duree_estimee_minutes', 'technicien_defaut',
            'pieces_necessaires', 'priorite', 'statut', 'notes',
        ]
        widgets = {
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'titre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Graissage roulements'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': '1. Arrêter la machine\n2. Démonter le carter\n3. ...'}),
            'type_frequence': forms.Select(attrs={'class': 'form-select'}),
            'frequence_jours': forms.NumberInput(attrs={'class': 'form-control'}),
            'frequence_heures': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'frequence_metres': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'frequence_tours': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'duree_estimee_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
            'technicien_defaut': forms.Select(attrs={'class': 'form-select'}),
            'pieces_necessaires': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 5}),
            'priorite': forms.Select(attrs={'class': 'form-select'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class MouvementPieceForm(forms.ModelForm):
    class Meta:
        model = MouvementPiece
        fields = ['piece', 'type_mouvement', 'quantite', 'motif', 'notes']
        widgets = {
            'piece': forms.Select(attrs={'class': 'form-select'}),
            'type_mouvement': forms.Select(attrs={'class': 'form-select'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'motif': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


# ===========================================================================
# 🚀 FORMULAIRE UNIFIÉ FICHES DE PRODUCTION + TRAÇABILITÉ LOT
# ===========================================================================

class FicheProductionJournaliereForm(forms.ModelForm):
    class Meta:
        model = FicheProductionJournaliere
        fields = [
            'type_fiche', 'numero_doc', 'numero_lot', 'date_fabrication', 'heure_debut', 'heure_fin',
            'poste', 'equipe', 'machine', 'conducteur', 'aide_conducteur_1',
            'aide_conducteur_2', 'chef_de_quart', 'client', 'designation_produit',
            'support', 'couleur', 'epaisseur_um', 'laize_mm', 'qte_programmee',
            'nbr_rouleaux_programmes', 't_preparation_min', 't_fonctionnement_min',
            't_nettoyage_min', 'vitesse_machine', 'debit_production_kghr',
            'poids_mandrin_kg', 'mandrin_longueur_mm', 'mandrin_epaisseur_mm',
            'dechet_bloc_b', 'dechet_b_demarrage_r', 'dechet_film', 'dechet_purge',
            'dechet_lisiere', 'total_dechets_kg', 'total_qte_lancee', 'reste_bobines_dr1', 'reste_bobines_dr2',
            'durcisseur_ref', 'durcisseur_poids', 'resine_ref', 'resine_poids',
            'solvant_ref', 'solvant_poids', 'total_bobines_filles', 'total_metrage_ml', 
            'total_poids_produit_kg', 'etiquettes_pos',
            'autocontrole_laize', 'autocontrole_epaisseur',
            'autocontrole_aspect_visuel', 'autocontrole_autres', 'observations', 'visa_resp_production',
            'visa_qualite', 'ok_demarrage', 'of_lie'
        ]
        widgets = {
            'type_fiche': forms.Select(attrs={'class': 'form-select', 'id': 'select_type_fiche', 'onchange': 'changerTypeFiche(this.value)'}),
            'numero_doc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'N° Doc / Lot de commande'}),
            # 🚀 CHAMP LOT INTELLIGENT avec datalist pour l'autocomplete
            'numero_lot': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: LOT2025-0001 (auto-remplit client/produit)',
                'list': 'lots_existants',
                'id': 'id_numero_lot',
                'autocomplete': 'off',
            }),
            'date_fabrication': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'heure_debut': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'poste': forms.Select(attrs={'class': 'form-select'}),
            'equipe': forms.Select(attrs={'class': 'form-select'}),
            'machine': forms.Select(attrs={'class': 'form-select hidden'}),
            'conducteur': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du conducteur'}),
            'aide_conducteur_1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Aide conducteur 1'}),
            'aide_conducteur_2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Aide conducteur 2'}),
            'chef_de_quart': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Chef de quart'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'designation_produit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Motif / Désignation Produit'}),
            'support': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: BOPP 20 TRS, PE 90μ'}),
            'couleur': forms.TextInput(attrs={'class': 'form-control'}),
            'epaisseur_um': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'μm'}),
            'laize_mm': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'mm'}),
            'qte_programmee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'nbr_rouleaux_programmes': forms.NumberInput(attrs={'class': 'form-control'}),
            't_preparation_min': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'min'}),
            't_fonctionnement_min': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'min'}),
            't_nettoyage_min': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'min'}),
            'vitesse_machine': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'm/min'}),
            'debit_production_kghr': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Kg/hr'}),
            'poids_mandrin_kg': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Kg'}),
            'mandrin_longueur_mm': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'mm'}),
            'mandrin_epaisseur_mm': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'mm'}),
            'dechet_bloc_b': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Kg'}),
            'dechet_b_demarrage_r': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Kg'}),
            'dechet_film': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Kg'}),
            'dechet_purge': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Kg'}),
            'dechet_lisiere': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Kg'}),
            'total_dechets_kg': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Kg'}),
            'total_qte_lancee': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Kg'}),
            'reste_bobines_dr1': forms.NumberInput(attrs={'class': 'form-control'}),
            'reste_bobines_dr2': forms.NumberInput(attrs={'class': 'form-control'}),
            'durcisseur_ref': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Réf. Colle / Durcisseur'}),
            'durcisseur_poids': forms.NumberInput(attrs={'class': 'form-control'}),
            'resine_ref': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Réf. Résine'}),
            'resine_poids': forms.NumberInput(attrs={'class': 'form-control'}),
            'solvant_ref': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Réf. Solvant'}),
            'solvant_poids': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_bobines_filles': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_metrage_ml': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_poids_produit_kg': forms.NumberInput(attrs={'class': 'form-control'}),
            'etiquettes_pos': forms.TextInput(attrs={'class': 'form-control'}),
            'autocontrole_laize': forms.TextInput(attrs={'class': 'form-control'}),
            'autocontrole_epaisseur': forms.TextInput(attrs={'class': 'form-control'}),
            'autocontrole_aspect_visuel': forms.TextInput(attrs={'class': 'form-control'}),
            'autocontrole_autres': forms.TextInput(attrs={'class': 'form-control'}),
            'observations': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'visa_resp_production': forms.TextInput(attrs={'class': 'form-control'}),
            'visa_qualite': forms.TextInput(attrs={'class': 'form-control'}),
            'ok_demarrage': forms.TextInput(attrs={'class': 'form-control'}),
            'of_lie': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['machine'].required = False
        self.fields['numero_lot'].required = False
        self.fields['of_lie'].required = False
        # Liste des OF actifs pour le select
        self.fields['of_lie'].queryset = OrdreFabrication.objects.exclude(
            statut__in=['TERMINE', 'ANNULE']
        ).order_by('-date_creation')
        self.fields['of_lie'].empty_label = "— Lier à un OF existant (optionnel) —"


# --- FORMSETS DES SOUS-TABLES ---

FicheExtrusionMatiereFormSet = inlineformset_factory(
    FicheProductionJournaliere, FicheExtrusionMatiere,
    fields=['designation', 'num_lot_mp', 'poids_mp_kg', 'qte_realisee_net_kg', 'metrage_m', 'qte_realisee_nbr_bobines'],
    extra=1, can_delete=True
)

FicheExtrusionArretFormSet = inlineformset_factory(
    FicheProductionJournaliere, FicheExtrusionArret,
    fields=['code_arret', 'nature_arret', 'temps_min'],
    extra=1, can_delete=True
)

FicheFlexoBobineEntreeFormSet = inlineformset_factory(
    FicheProductionJournaliere, FicheImpressionBobineEntree,
    fields=['num_ordre', 'num_lot_mp', 'num_bobine', 'fournisseur', 'metrage_m', 'poids_kg', 'dechets_neutre_kg'],
    extra=1, can_delete=True
)

FicheFlexoBobineImprimeeFormSet = inlineformset_factory(
    FicheProductionJournaliere, FicheImpressionBobineImprimee,
    fields=['num_ordre', 'nbre_bobines', 'poids_kg', 'metrage_m', 'dechet_imprime_kg', 'observations'],
    extra=1, can_delete=True
)

FicheFlexoEncreGroupeFormSet = inlineformset_factory(
    FicheProductionJournaliere, FicheImpressionEncreGroupe,
    fields=['groupe_numero', 'designation_encre', 'code_encre', 'viscosite_sec', 'poids_debut_kg', 'poids_fin_kg', 'conso_encre_kg', 'conso_solvant_kg'],
    extra=8, max_num=8, can_delete=False
)

FicheComplexageDerouleur1FormSet = inlineformset_factory(
    FicheProductionJournaliere, FicheComplexageDerouleur1,
    fields=['num_ordre', 'num_lot_mp', 'num_bobine', 'poids_kg', 'ml', 'dechets_kg'],
    extra=1, can_delete=True
)

FicheComplexageDerouleur2FormSet = inlineformset_factory(
    FicheProductionJournaliere, FicheComplexageDerouleur2,
    fields=['num_ordre', 'num_lot_mp', 'num_bobine', 'poids_kg', 'ml', 'dechets_kg'],
    extra=1, can_delete=True
)

FicheComplexageEnrouleurFormSet = inlineformset_factory(
    FicheProductionJournaliere, FicheComplexageEnrouleur,
    fields=['num_ordre', 'num_lot', 'poids_kg', 'ml', 'dechets_kg'],
    extra=1, can_delete=True
)

FicheFondCarreEquipeFormSet = inlineformset_factory(
    FicheProductionJournaliere, FicheFondCarreEquipe,
    fields=[
        'equipe_num', 'shift_code', 'date_fabrication', 'num_equipe', 'operateur',
        'aide_operateur', 'debut_pro', 'fin_pro', 'fournisseur_mp', 'matiere_nature', 
        'grm2', 'laize', 'metre_l_initial', 'poids_initial_kg', 'metre_l_decoupe', 
        'nb_sacs', 'poids_sacs_kg', 'dechets_sacs_kg', 'dechets_bob_kg', 'restes_bob_kg', 'observation'
    ],
    extra=3, max_num=3, can_delete=False
)

FicheDecoupeBobineMereFormSet = inlineformset_factory(
    FicheProductionJournaliere, FicheDecoupeBobineMere,
    fields=['num_ordre', 'reference_lot', 'poids_kg', 'metrage_ml'],
    extra=1, can_delete=True
)

FicheDecoupeBobineFilleFormSet = inlineformset_factory(
    FicheProductionJournaliere, FicheDecoupeBobineFille,
    fields=['num_ordre', 'nombre_filles', 'poids_filles_kg', 'nombre_a_reviser', 'poids_a_reviser_kg', 'dechets_demarrage_kg', 'dechets_lisiere_kg', 'dechets_jonction_kg', 'dechets_transport_kg', 'rouleaux_non_conforme_kg'],
    extra=1, can_delete=True
)