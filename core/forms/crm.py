from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.models import User
from django.db.models import Q

from core.models import (
    Client, ClientContact, InteractionLog, Opportunite, Quote,
    CommandeClient, LigneCommandeClient, DemandePrix,
    Material, TechnicalProduct,
)


# ===========================================================================
# --- HELPER : Queryset des utilisateurs ayant accès au module CRM ---
# ===========================================================================

def get_crm_users_queryset():
    """
    Retourne uniquement les utilisateurs actifs ayant la permission 
    d'accéder au module CRM (ou les super-administrateurs).
    """
    return User.objects.filter(
        Q(is_active=True) & 
        (Q(is_superuser=True) | Q(module_permissions__can_access_crm=True))
    ).distinct().order_by('first_name', 'username')


def format_user_label(obj):
    """Format d'affichage : Prénom Nom (username)"""
    return f"{obj.get_full_name()} ({obj.username})" if obj.get_full_name().strip() else obj.username


# ===========================================================================
# --- FORMULAIRE CLIENT ---
# ===========================================================================

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'name', 'code_client', 'status', 'segment', 'size', 'region',
            'ca_estime', 'sector', 'city', 'address', 'phone', 'email',
            'website', 'commercial', 'notes',
            # AJOUTS CRM MODERNE
            'source_prospect', 'conditions_paiement', 'delai_livraison_jours',
            'remise_defaut', 'limite_credit', 'ice_nif',
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
            'source_prospect': forms.Select(attrs={'class': 'form-select'}),
            'conditions_paiement': forms.Select(attrs={'class': 'form-select'}),
            'delai_livraison_jours': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'remise_defaut': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0, 'max': 100}),
            'limite_credit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'ice_nif': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ICE / NIF / RC'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Charge uniquement les utilisateurs ayant accès au CRM
        self.fields['commercial'].queryset = get_crm_users_queryset()
        self.fields['commercial'].label_from_instance = format_user_label


# ===========================================================================
# --- FORMULAIRE CONTACT CLIENT ---
# ===========================================================================

class ClientContactForm(forms.ModelForm):
    class Meta:
        model = ClientContact
        fields = ['name', 'role', 'role_custom', 'phone', 'email', 'is_primary', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom et Prénom'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'role_custom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Si rôle "Autre"'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Téléphone direct'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email direct'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observations...'}),
        }


# FORMSET POUR LES INTERLOCUTEURS DU CLIENT
ClientContactFormSet = inlineformset_factory(
    Client,
    ClientContact,
    form=ClientContactForm,
    extra=1,          # Proposer au moins une ligne vide
    can_delete=True,  # Permettre la suppression d'une ligne
)


# ===========================================================================
# --- FORMULAIRE INTERACTION ---
# ===========================================================================

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
        # Filtre les commerciaux avec accès CRM
        self.fields['commercial'].queryset = get_crm_users_queryset()
        self.fields['commercial'].label_from_instance = format_user_label


# ===========================================================================
# --- FORMULAIRE OPPORTUNITÉ ---
# ===========================================================================

class OpportuniteForm(forms.ModelForm):
    class Meta:
        model = Opportunite
        fields = [
            'client', 'commercial', 'titre', 'description', 'status',
            'valeur_estimee', 'probabilite', 'date_cloture_prevue', 'notes',
            # AJOUTS CRM MODERNE
            'produit_demande', 'quantite_estimee', 'prix_estime',
            'date_prevue_commande', 'devis_lie', 'material_principal',
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
            'produit_demande': forms.Select(attrs={'class': 'form-select'}),
            'quantite_estimee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'prix_estime': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'date_prevue_commande': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'devis_lie': forms.Select(attrs={'class': 'form-select'}),
            'material_principal': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['produit_demande'].required = False
        self.fields['devis_lie'].required = False
        self.fields['material_principal'].required = False
        self.fields['produit_demande'].queryset = TechnicalProduct.objects.all().order_by('name')
        self.fields['material_principal'].queryset = Material.objects.all().order_by('name')
        self.fields['devis_lie'].queryset = Quote.objects.all().order_by('-date')
        # Filtre les commerciaux avec accès CRM
        self.fields['commercial'].queryset = get_crm_users_queryset()
        self.fields['commercial'].label_from_instance = format_user_label


# ===========================================================================
# --- FORMULAIRE DEVIS ---
# ===========================================================================

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtre les commerciaux avec accès CRM
        self.fields['commercial'].queryset = get_crm_users_queryset()
        self.fields['commercial'].label_from_instance = format_user_label


# ===========================================================================
# --- FORMULAIRE COMMANDE CLIENT ---
# ===========================================================================

class CommandeClientForm(forms.ModelForm):
    class Meta:
        model = CommandeClient
        fields = [
            'client', 'opportunite', 'devis', 'commercial',
            'date_commande', 'date_livraison_prevue', 'statut', 'priorite',
            'conditions_paiement', 'delai_livraison_jours', 'remise_globale',
            'adresse_livraison', 'notes',
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'opportunite': forms.Select(attrs={'class': 'form-select'}),
            'devis': forms.Select(attrs={'class': 'form-select'}),
            'commercial': forms.Select(attrs={'class': 'form-select'}),
            'date_commande': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_livraison_prevue': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'priorite': forms.Select(attrs={'class': 'form-select'}),
            'conditions_paiement': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 30 jours, Acompte 30%...'}),
            'delai_livraison_jours': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'remise_globale': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0, 'max': 100}),
            'adresse_livraison': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['opportunite'].required = False
        self.fields['devis'].required = False
        self.fields['commercial'].required = False
        self.fields['opportunite'].queryset = Opportunite.objects.exclude(
            status__in=['PERDU']
        ).select_related('client').order_by('-date_ouverture')
        self.fields['devis'].queryset = Quote.objects.all().order_by('-date')
        # Filtre les commerciaux avec accès CRM
        self.fields['commercial'].queryset = get_crm_users_queryset()
        self.fields['commercial'].label_from_instance = format_user_label


# ===========================================================================
# --- FORMULAIRE LIGNE COMMANDE CLIENT ---
# ===========================================================================

class LigneCommandeClientForm(forms.ModelForm):
    class Meta:
        model = LigneCommandeClient
        fields = [
            'produit', 'material', 'designation', 'quantite', 'unite',
            'prix_unitaire', 'remise', 'date_livraison', 'notes',
        ]
        widgets = {
            'produit': forms.Select(attrs={'class': 'form-select'}),
            'material': forms.Select(attrs={'class': 'form-select'}),
            'designation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Désignation article'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'unite': forms.TextInput(attrs={'class': 'form-control'}),
            'prix_unitaire': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'remise': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0, 'max': 100}),
            'date_livraison': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['produit'].required = False
        self.fields['material'].required = False
        self.fields['produit'].queryset = TechnicalProduct.objects.all().order_by('name')
        self.fields['material'].queryset = Material.objects.all().order_by('name')
        self.fields['material'].label_from_instance = lambda obj: (
            f"{obj.name} — Stock: {obj.quantity:.1f} {obj.unit}"
            f"{' ⚠️ BAS' if obj.is_low_stock() else ''}"
        )


LigneCommandeClientFormSet = inlineformset_factory(
    CommandeClient,
    LigneCommandeClient,
    form=LigneCommandeClientForm,
    extra=3,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


# ===========================================================================
# --- FORMULAIRE DEMANDE DE PRIX ---
# ===========================================================================

class DemandePrixForm(forms.ModelForm):
    class Meta:
        model = DemandePrix
        fields = [
            'client', 'contact', 'commercial', 'opportunite',
            'objet', 'description', 'produit', 'quantite_demandee',
            'budget_indicatif', 'date_demande', 'date_reponse_souhaitee',
            'statut', 'notes',
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'contact': forms.Select(attrs={'class': 'form-select'}),
            'commercial': forms.Select(attrs={'class': 'form-select'}),
            'opportunite': forms.Select(attrs={'class': 'form-select'}),
            'objet': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'produit': forms.Select(attrs={'class': 'form-select'}),
            'quantite_demandee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'budget_indicatif': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': 0}),
            'date_demande': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_reponse_souhaitee': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contact'].required = False
        self.fields['opportunite'].required = False
        self.fields['produit'].required = False
        self.fields['commercial'].required = False
        self.fields['produit'].queryset = TechnicalProduct.objects.all().order_by('name')
        # Filtre les commerciaux avec accès CRM
        self.fields['commercial'].queryset = get_crm_users_queryset()
        self.fields['commercial'].label_from_instance = format_user_label


# ===========================================================================
# --- FORMULAIRE IMPORT CLIENTS ---
# ===========================================================================

class ClientImportForm(forms.Form):
    fichier = forms.FileField(
        label="Fichier Excel (.xlsx) ou CSV",
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control bg-slate-800 border-slate-700 text-white',
            'accept': '.xlsx, .xls, .csv'
        })
    )