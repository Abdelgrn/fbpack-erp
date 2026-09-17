from django import forms
from core.models import (
    CategoriePiece, PieceRechange, OrdreMaintenance, ConsommationPiece,
    PlanMaintenancePreventive, MouvementPiece
)

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