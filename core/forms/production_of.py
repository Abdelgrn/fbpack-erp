from django import forms
from django.forms import inlineformset_factory
from core.models import (
    OrdreFabrication, EtapeProduction, SuiviProduction, SemiProduit,
    ConsommationMatiere, ProcessType, Client, TechnicalProduct, Machine, Atelier
)


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
            'numero_of': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Auto-généré si vide'}),
            'numero_lot': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Saisi par le planificateur'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'produit': forms.Select(attrs={'class': 'form-select'}),
            'opportunite': forms.Select(attrs={'class': 'form-select'}),
            'quantite_prevue': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'support': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: OPP 20 TRS'}),
            'dimension_mandrin': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'diametre_bobine_fille': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'laize': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'epaisseur': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'date_lancement': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_prevue_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'priorite': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'observation': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
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
            'date_planifiee', 'heure_debut_planifiee', 'heure_fin_planifiee',
            'shift', 'equipe', 'ordre_passage',
            'genere_semi_produit', 'notes'
        ]
        widgets = {
            'numero_etape': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'nom_etape': forms.TextInput(attrs={'class': 'form-control'}),
            'process_type': forms.Select(attrs={'class': 'form-select'}),
            'atelier': forms.Select(attrs={'class': 'form-select'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'operateur': forms.Select(attrs={'class': 'form-select'}),
            'quantite_entree': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'support': forms.TextInput(attrs={'class': 'form-control'}),
            'developpement': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'quantite_ml': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'nb_bobines': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'numero_lot_etape': forms.TextInput(attrs={'class': 'form-control'}),
            'observation': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'date_planifiee': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            
            # Utilisation de TextInput pour supprimer le contrôle AM/PM Chrome et garantir 24h (ex: 16:00)
            'heure_debut_planifiee': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': '08:00', 'pattern': '^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'}
            ),
            'heure_fin_planifiee': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': '16:00', 'pattern': '^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'}
            ),
            
            'shift': forms.Select(attrs={'class': 'form-select'}),
            'equipe': forms.Select(attrs={'class': 'form-select'}),
            'ordre_passage': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'genere_semi_produit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['heure_debut_planifiee'].input_formats = ['%H:%M', '%H:%M:%S']
        self.fields['heure_fin_planifiee'].input_formats = ['%H:%M', '%H:%M:%S']

        for name in [
            'process_type', 'atelier', 'machine', 'operateur', 'nom_etape',
            'support', 'observation', 'notes', 'date_planifiee',
            'heure_debut_planifiee', 'heure_fin_planifiee', 'shift', 'equipe',
            'numero_lot_etape', 'developpement', 'quantite_ml', 'nb_bobines',
            'numero_etape', 'quantite_entree', 'ordre_passage',
        ]:
            if name in self.fields:
                self.fields[name].required = False

        if 'machine' in self.fields:
            try:
                self.fields['machine'].queryset = Machine.objects.filter(
                    est_active=True
                ).exclude(type__in=['NETT_CL', 'NETT_AN']).order_by('atelier__nom', 'name')
            except Exception:
                self.fields['machine'].queryset = Machine.objects.all().order_by('name')
        if 'atelier' in self.fields:
            try:
                self.fields['atelier'].queryset = Atelier.objects.filter(
                    est_actif=True
                ).order_by('ordre_affichage', 'nom')
            except Exception:
                self.fields['atelier'].queryset = Atelier.objects.all()


EtapeProductionFormSet = inlineformset_factory(
    OrdreFabrication,
    EtapeProduction,
    form=EtapeProductionForm,
    extra=0,
    can_delete=True,
    min_num=0,
    validate_min=False,
)

PlanificationEtapeFormSet = inlineformset_factory(
    OrdreFabrication,
    EtapeProduction,
    form=EtapeProductionForm,
    extra=0,
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
        widget=forms.TextInput(attrs={'class': 'form-control'}),
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
    support_extrusion = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    etape_impression = forms.BooleanField(required=False, initial=True, label="Impression")
    machine_impression = forms.ModelChoiceField(
        queryset=Machine.objects.filter(type__in=['IMP', 'HELIO']),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Machine"
    )
    qte_impression = forms.FloatField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    support_impression = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    developpement_impression = forms.FloatField(required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}))

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