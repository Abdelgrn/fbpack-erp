from django import forms
from core.models import Machine, Atelier, CompteurMachine

class MachineForm(forms.ModelForm):
    class Meta:
        model = Machine
        fields = ['name', 'type', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
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