from django import forms
from .models import (
    Client, ClientContact, InteractionLog, Opportunite,
    TechnicalProduct, Tooling, Quote,
    ProductionOrder, Machine, Supplier, Material, ConsommationEncre,
    ProductionEntry
)

# --- STYLES ---
INPUT_STYLE = 'w-full bg-slate-700 border border-slate-600 text-white rounded p-2 focus:outline-none focus:border-yellow-500 placeholder-gray-400'
SELECT_STYLE = 'w-full bg-slate-700 border border-slate-600 text-white rounded p-2 focus:outline-none focus:border-yellow-500'
FILE_STYLE = 'w-full bg-slate-700 text-gray-300 border border-slate-600 rounded p-1 cursor-pointer file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-yellow-500 file:text-slate-900 hover:file:bg-yellow-400'
TEXTAREA_STYLE = 'w-full bg-slate-700 border border-slate-600 text-white rounded p-2 focus:outline-none focus:border-yellow-500 placeholder-gray-400 h-24'


# ===========================================================================
# --- MODULE CRM ---
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
            'name':        forms.TextInput(attrs={'class': INPUT_STYLE, 'placeholder': 'Raison sociale'}),
            'code_client': forms.TextInput(attrs={'class': INPUT_STYLE, 'placeholder': 'Ex: CLT-001'}),
            'status':      forms.Select(attrs={'class': SELECT_STYLE}),
            'segment':     forms.Select(attrs={'class': SELECT_STYLE}),
            'size':        forms.Select(attrs={'class': SELECT_STYLE}),
            'region':      forms.Select(attrs={'class': SELECT_STYLE}),
            'ca_estime':   forms.NumberInput(attrs={'class': INPUT_STYLE, 'step': '1000'}),
            'sector':      forms.TextInput(attrs={'class': INPUT_STYLE, 'placeholder': "Ex: Agroalimentaire"}),
            'city':        forms.TextInput(attrs={'class': INPUT_STYLE}),
            'address':     forms.Textarea(attrs={'class': TEXTAREA_STYLE, 'rows': 2}),
            'phone':       forms.TextInput(attrs={'class': INPUT_STYLE}),
            'email':       forms.EmailInput(attrs={'class': INPUT_STYLE}),
            'website':     forms.URLInput(attrs={'class': INPUT_STYLE, 'placeholder': 'https://'}),
            'commercial':  forms.Select(attrs={'class': SELECT_STYLE}),
            'notes':       forms.Textarea(attrs={'class': TEXTAREA_STYLE, 'rows': 3}),
        }


class ClientContactForm(forms.ModelForm):
    class Meta:
        model = ClientContact
        fields = ['name', 'role', 'role_custom', 'phone', 'email', 'is_primary', 'notes']
        widgets = {
            'name':        forms.TextInput(attrs={'class': INPUT_STYLE, 'placeholder': 'Nom Prénom'}),
            'role':        forms.Select(attrs={'class': SELECT_STYLE}),
            'role_custom': forms.TextInput(attrs={'class': INPUT_STYLE, 'placeholder': 'Si Autre, précisez...'}),
            'phone':       forms.TextInput(attrs={'class': INPUT_STYLE}),
            'email':       forms.EmailInput(attrs={'class': INPUT_STYLE}),
            'is_primary':  forms.CheckboxInput(attrs={'class': 'h-4 w-4 accent-yellow-500'}),
            'notes':       forms.Textarea(attrs={'class': TEXTAREA_STYLE, 'rows': 2}),
        }


class InteractionLogForm(forms.ModelForm):
    class Meta:
        model = InteractionLog
        fields = ['contact', 'commercial', 'date', 'type', 'summary', 'details', 'next_action', 'next_action_date']
        widgets = {
            'contact':          forms.Select(attrs={'class': SELECT_STYLE}),
            'commercial':       forms.Select(attrs={'class': SELECT_STYLE}),
            'date':             forms.DateTimeInput(attrs={'class': INPUT_STYLE, 'type': 'datetime-local'}),
            'type':             forms.Select(attrs={'class': SELECT_STYLE}),
            'summary':          forms.TextInput(attrs={'class': INPUT_STYLE, 'placeholder': 'Objet de l\'interaction'}),
            'details':          forms.Textarea(attrs={'class': TEXTAREA_STYLE, 'rows': 4}),
            'next_action':      forms.TextInput(attrs={'class': INPUT_STYLE, 'placeholder': 'Prochaine étape à faire'}),
            'next_action_date': forms.DateInput(attrs={'class': INPUT_STYLE, 'type': 'date'}),
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
            'valeur_estimee', 'probabilite', 'date_ouverture',
            'date_cloture_prevue', 'motif_perte', 'notes'
        ]
        widgets = {
            'client':             forms.Select(attrs={'class': SELECT_STYLE}),
            'commercial':         forms.Select(attrs={'class': SELECT_STYLE}),
            'titre':              forms.TextInput(attrs={'class': INPUT_STYLE, 'placeholder': 'Ex: Fourniture films OPP – Lot 2025'}),
            'description':        forms.Textarea(attrs={'class': TEXTAREA_STYLE, 'rows': 3}),
            'status':             forms.Select(attrs={'class': SELECT_STYLE}),
            'valeur_estimee':     forms.NumberInput(attrs={'class': INPUT_STYLE, 'step': '1000'}),
            'probabilite':        forms.NumberInput(attrs={'class': INPUT_STYLE, 'min': 0, 'max': 100}),
            'date_ouverture':     forms.DateInput(attrs={'class': INPUT_STYLE, 'type': 'date'}),
            'date_cloture_prevue': forms.DateInput(attrs={'class': INPUT_STYLE, 'type': 'date'}),
            'motif_perte':        forms.TextInput(attrs={'class': INPUT_STYLE}),
            'notes':              forms.Textarea(attrs={'class': TEXTAREA_STYLE, 'rows': 2}),
        }


# ===========================================================================
# --- DEVIS ---
# ===========================================================================

class QuoteForm(forms.ModelForm):
    class Meta:
        model = Quote
        fields = [
            'client', 'opportunite', 'commercial', 'reference', 'version',
            'date', 'date_validite', 'total_amount', 'status', 'pdf_file', 'notes'
        ]
        widgets = {
            'client':        forms.Select(attrs={'class': SELECT_STYLE}),
            'opportunite':   forms.Select(attrs={'class': SELECT_STYLE}),
            'commercial':    forms.Select(attrs={'class': SELECT_STYLE}),
            'reference':     forms.TextInput(attrs={'class': INPUT_STYLE, 'placeholder': 'Ex: DEV-2025-001'}),
            'version':       forms.NumberInput(attrs={'class': INPUT_STYLE}),
            'date':          forms.DateInput(attrs={'class': INPUT_STYLE, 'type': 'date'}),
            'date_validite': forms.DateInput(attrs={'class': INPUT_STYLE, 'type': 'date'}),
            'total_amount':  forms.NumberInput(attrs={'class': INPUT_STYLE, 'step': '100'}),
            'status':        forms.Select(attrs={'class': SELECT_STYLE}),
            'pdf_file':      forms.FileInput(attrs={'class': FILE_STYLE}),
            'notes':         forms.Textarea(attrs={'class': TEXTAREA_STYLE, 'rows': 2}),
        }


# ===========================================================================
# --- MODULE PRÉPRESSE ---
# ===========================================================================

class ProductForm(forms.ModelForm):
    class Meta:
        model = TechnicalProduct
        fields = ['client', 'ref_internal', 'name', 'structure_type', 'width_mm', 'cut_length_mm', 'num_colors', 'artwork_file']
        widgets = {
            'client':         forms.Select(attrs={'class': SELECT_STYLE}),
            'ref_internal':   forms.TextInput(attrs={'class': INPUT_STYLE}),
            'name':           forms.TextInput(attrs={'class': INPUT_STYLE}),
            'structure_type': forms.Select(attrs={'class': SELECT_STYLE}),
            'width_mm':       forms.NumberInput(attrs={'class': INPUT_STYLE}),
            'cut_length_mm':  forms.NumberInput(attrs={'class': INPUT_STYLE}),
            'num_colors':     forms.NumberInput(attrs={'class': INPUT_STYLE}),
            'artwork_file':   forms.FileInput(attrs={'class': FILE_STYLE}),
        }


class ToolForm(forms.ModelForm):
    class Meta:
        model = Tooling
        fields = ['product', 'tool_type', 'serial_number', 'max_impressions', 'current_impressions']
        widgets = {
            'product':             forms.Select(attrs={'class': SELECT_STYLE}),
            'tool_type':           forms.Select(attrs={'class': SELECT_STYLE}),
            'serial_number':       forms.TextInput(attrs={'class': INPUT_STYLE}),
            'max_impressions':     forms.NumberInput(attrs={'class': INPUT_STYLE}),
            'current_impressions': forms.NumberInput(attrs={'class': INPUT_STYLE}),
        }


# ===========================================================================
# --- MODULE PRODUCTION (OF) ---
# ===========================================================================

class ProductionOrderForm(forms.ModelForm):
    class Meta:
        model = ProductionOrder
        fields = ['of_number', 'client', 'product', 'machine', 'quantity_planned', 'start_time', 'end_time', 'status', 'bat_file']
        widgets = {
            'of_number':        forms.TextInput(attrs={'class': INPUT_STYLE}),
            'client':           forms.Select(attrs={'class': SELECT_STYLE}),
            'product':          forms.Select(attrs={'class': SELECT_STYLE}),
            'machine':          forms.Select(attrs={'class': SELECT_STYLE}),
            'quantity_planned': forms.NumberInput(attrs={'class': INPUT_STYLE}),
            'start_time':       forms.DateTimeInput(attrs={'class': INPUT_STYLE, 'type': 'datetime-local'}),
            'end_time':         forms.DateTimeInput(attrs={'class': INPUT_STYLE, 'type': 'datetime-local'}),
            'status':           forms.Select(attrs={'class': SELECT_STYLE}),
            'bat_file':         forms.FileInput(attrs={'class': FILE_STYLE}),
        }


# ===========================================================================
# --- MODULE STOCKS & ACHATS ---
# ===========================================================================

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'email']
        widgets = {
            'name':  forms.TextInput(attrs={'class': INPUT_STYLE}),
            'email': forms.EmailInput(attrs={'class': INPUT_STYLE}),
        }


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['name', 'category', 'quantity', 'unit', 'min_threshold', 'supplier', 'price_per_unit']
        widgets = {
            'name':           forms.TextInput(attrs={'class': INPUT_STYLE}),
            'category':       forms.Select(attrs={'class': SELECT_STYLE}),
            'quantity':       forms.NumberInput(attrs={'class': INPUT_STYLE}),
            'unit':           forms.TextInput(attrs={'class': INPUT_STYLE}),
            'min_threshold':  forms.NumberInput(attrs={'class': INPUT_STYLE}),
            'supplier':       forms.Select(attrs={'class': SELECT_STYLE}),
            'price_per_unit': forms.NumberInput(attrs={'class': INPUT_STYLE, 'step': '0.01'}),
        }


class ConsommationEncreForm(forms.ModelForm):
    class Meta:
        model = ConsommationEncre
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = SELECT_STYLE
            elif isinstance(field.widget, forms.DateInput) or 'date' in field_name.lower():
                field.widget.attrs['class'] = INPUT_STYLE
                field.widget.input_type = 'date'
            else:
                field.widget.attrs['class'] = INPUT_STYLE


# ===========================================================================
# --- MODULE PARC MACHINE ---
# ===========================================================================

class MachineForm(forms.ModelForm):
    class Meta:
        model = Machine
        fields = ['name', 'type', 'status']
        widgets = {
            'name':   forms.TextInput(attrs={'class': INPUT_STYLE}),
            'type':   forms.Select(attrs={'class': SELECT_STYLE}),
            'status': forms.Select(attrs={'class': SELECT_STYLE}),
        }


# ===========================================================================
# --- MODULE PRODUCTION SPÉCIAL ---
# ===========================================================================

class ProductionEntryForm(forms.ModelForm):
    class Meta:
        model = ProductionEntry
        fields = [
            'date', 'produit', 'support', 'quantite_lancee', 'lot', 'laize',
            'client', 'equipe', 'machine',
            'heure_debut', 'heure_fin',
            'prod_ml',
            'dechets_demarrage', 'dechets_lisiere', 'dechets_jonction', 'dechets_transport',
            'prod_kg', 'rebobinage_kg',
        ]
        widgets = {
            'date':              forms.DateInput(attrs={'class': INPUT_STYLE, 'type': 'date'}),
            'produit':           forms.TextInput(attrs={'class': INPUT_STYLE, 'placeholder': 'Ex: SAC FARINE 1KG'}),
            'support':           forms.TextInput(attrs={'class': INPUT_STYLE, 'placeholder': 'Ex: KRAFT 75G'}),
            'quantite_lancee':   forms.NumberInput(attrs={'class': INPUT_STYLE, 'step': '0.1'}),
            'lot':               forms.TextInput(attrs={'class': INPUT_STYLE}),
            'laize':             forms.NumberInput(attrs={'class': INPUT_STYLE, 'step': '0.1'}),
            'client':            forms.Select(attrs={'class': SELECT_STYLE}),
            'equipe':            forms.Select(attrs={'class': SELECT_STYLE}),
            'machine':           forms.Select(attrs={'class': SELECT_STYLE}),
            'heure_debut':       forms.TimeInput(attrs={'class': INPUT_STYLE, 'type': 'time'}),
            'heure_fin':         forms.TimeInput(attrs={'class': INPUT_STYLE, 'type': 'time'}),
            'prod_ml':           forms.NumberInput(attrs={'class': INPUT_STYLE, 'step': '0.1'}),
            'dechets_demarrage': forms.NumberInput(attrs={'class': INPUT_STYLE, 'step': '0.01'}),
            'dechets_lisiere':   forms.NumberInput(attrs={'class': INPUT_STYLE, 'step': '0.01'}),
            'dechets_jonction':  forms.NumberInput(attrs={'class': INPUT_STYLE, 'step': '0.01'}),
            'dechets_transport': forms.NumberInput(attrs={'class': INPUT_STYLE, 'step': '0.01'}),
            'prod_kg':           forms.NumberInput(attrs={'class': INPUT_STYLE, 'step': '0.01'}),
            'rebobinage_kg':     forms.NumberInput(attrs={'class': INPUT_STYLE, 'step': '0.01'}),
        }
