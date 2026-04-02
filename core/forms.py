from django import forms
from django.forms import inlineformset_factory
from .models import (
    Client, ClientContact, InteractionLog, Opportunite,
    TechnicalProduct, Tooling, Quote,
    ProductionOrder, Supplier, Material, ConsommationEncre,
    Machine, ProductionEntry,
    OrdreFabrication, EtapeProduction, SemiProduit,
    SuiviProduction, ConsommationMatiere, ProcessType,
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


class ProductionEntryForm(forms.ModelForm):
    class Meta:
        model = ProductionEntry
        fields = [
            'date', 'produit', 'support', 'quantite_lancee', 'lot', 'laize',
            'client', 'equipe', 'machine', 'heure_debut', 'heure_fin',
            'prod_ml', 'dechets_demarrage', 'dechets_lisiere',
            'dechets_jonction', 'dechets_transport', 'prod_kg', 'rebobinage_kg'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'produit': forms.TextInput(attrs={'class': 'form-control'}),
            'support': forms.TextInput(attrs={'class': 'form-control'}),
            'quantite_lancee': forms.NumberInput(attrs={'class': 'form-control'}),
            'lot': forms.TextInput(attrs={'class': 'form-control'}),
            'laize': forms.NumberInput(attrs={'class': 'form-control'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'equipe': forms.Select(attrs={'class': 'form-select'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'heure_debut': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'prod_ml': forms.NumberInput(attrs={'class': 'form-control'}),
            'dechets_demarrage': forms.NumberInput(attrs={'class': 'form-control'}),
            'dechets_lisiere': forms.NumberInput(attrs={'class': 'form-control'}),
            'dechets_jonction': forms.NumberInput(attrs={'class': 'form-control'}),
            'dechets_transport': forms.NumberInput(attrs={'class': 'form-control'}),
            'prod_kg': forms.NumberInput(attrs={'class': 'form-control'}),
            'rebobinage_kg': forms.NumberInput(attrs={'class': 'form-control'}),
        }


# Ancien formulaire pour compatibilité
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
# --- OF MULTI-PROCESSUS FORMS ---
# ===========================================================================

class OrdreFabricationForm(forms.ModelForm):
    class Meta:
        model = OrdreFabrication
        fields = [
            'numero_of', 'numero_lot', 'client', 'produit', 'opportunite',
            'quantite_prevue', 'dimension_mandrin', 'diametre_bobine_fille',
            'laize', 'epaisseur', 'date_lancement', 'date_prevue_fin',
            'priorite', 'bat_file', 'fiche_technique', 'notes'
        ]
        widgets = {
            'numero_of': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Auto-généré si vide'
            }),
            'numero_lot': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: LOT-2025-001'
            }),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'produit': forms.Select(attrs={'class': 'form-select'}),
            'opportunite': forms.Select(attrs={'class': 'form-select'}),
            'quantite_prevue': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'dimension_mandrin': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1'
            }),
            'diametre_bobine_fille': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1'
            }),
            'laize': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1'
            }),
            'epaisseur': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1'
            }),
            'date_lancement': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'date_prevue_fin': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'priorite': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Instructions spéciales...'
            }),
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
            'numero_etape', 'nom_etape', 'process_type', 'machine',
            'operateur', 'quantite_entree', 'date_prevue_debut',
            'date_prevue_fin', 'genere_semi_produit', 'notes'
        ]
        widgets = {
            'numero_etape': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'nom_etape': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Impression Flexo'
            }),
            'process_type': forms.Select(attrs={'class': 'form-select'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'operateur': forms.Select(attrs={'class': 'form-select'}),
            'quantite_entree': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'date_prevue_debut': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'date_prevue_fin': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'genere_semi_produit': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
        }


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
            'quantite_produite': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'quantite_rebut': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'vitesse_machine': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1'
            }),
            'commentaire': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2
            }),
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
        fields = ['code', 'nom', 'description', 'ordre_defaut', 'icone', 'couleur', 'est_actif']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'ordre_defaut': forms.NumberInput(attrs={'class': 'form-control'}),
            'icone': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 10}),
            'couleur': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
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

    etape_impression = forms.BooleanField(required=False, initial=True, label="Impression")
    machine_impression = forms.ModelChoiceField(
        queryset=Machine.objects.filter(type='IMP'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Machine"
    )
    qte_impression = forms.FloatField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control'}))

    etape_decoupe = forms.BooleanField(required=False, initial=True, label="Découpe")
    machine_decoupe = forms.ModelChoiceField(
        queryset=Machine.objects.filter(type='DEC'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Machine"
    )
    qte_decoupe = forms.FloatField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control'}))