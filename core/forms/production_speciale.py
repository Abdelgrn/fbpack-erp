from django import forms
from core.models import (
    ProductionEntry, CalculTempsProduction, ProductionOrder,
    Machine, OrdreFabrication
)

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
