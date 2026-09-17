from django import forms
from django.forms import inlineformset_factory
from core.models import (
    FicheProductionJournaliere, FicheExtrusionMatiere, FicheExtrusionArret,
    FicheImpressionBobineEntree, FicheImpressionBobineImprimee, FicheImpressionEncreGroupe,
    FicheComplexageDerouleur1, FicheComplexageDerouleur2, FicheComplexageEnrouleur,
    FicheFondCarreEquipe, FicheDecoupeBobineMere, FicheDecoupeBobineFille, OrdreFabrication,
    FicheDecoupeArret, FicheDecoupeControle,
)

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
        self.fields['of_lie'].queryset = OrdreFabrication.objects.exclude(
            statut__in=['TERMINE', 'ANNULE']
        ).order_by('-date_creation')
        self.fields['of_lie'].empty_label = "— Lier à un OF existant (optionnel) —"


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

# ✂️ Bobines Filles complètes (fiche papier : filles + à réviser + 4 déchets + non conforme)
FicheDecoupeBobineFilleFormSet = inlineformset_factory(
    FicheProductionJournaliere, FicheDecoupeBobineFille,
    fields=[
        'num_ordre',
        'nombre_filles', 'poids_filles_kg',
        'nombre_a_reviser', 'poids_a_reviser_kg',
        'dechets_demarrage_kg', 'dechets_lisiere_kg',
        'dechets_jonction_kg', 'dechets_transport_kg',
        'rouleaux_non_conforme_kg',
    ],
    extra=1, can_delete=True
)

# 🛑 14 causes d'arrêts de la fiche papier Découpe
FicheDecoupeArretFormSet = inlineformset_factory(
    FicheProductionJournaliere, FicheDecoupeArret,
    fields=['cause', 'temps_min', 'dechets_kg'],
    extra=14, max_num=14, can_delete=False
)


# 🔬 Formulaire Autocontrôle Avant/Après Découpe
class FicheDecoupeControleForm(forms.ModelForm):
    class Meta:
        model = FicheDecoupeControle
        exclude = ['fiche']
        widgets = {
            'laize_mere_avant': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '✔ / ❌'}),
            'laize_fille_apres': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '✔ / ❌'}),
            'impression_avant': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '✔ / ❌'}),
            'impression_apres': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '✔ / ❌'}),
            'etat_bobine_avant': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '✔ / ❌'}),
            'etat_bobine_apres': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '✔ / ❌'}),
            'froissage_avant': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '✔ / ❌'}),
            'froissage_apres': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '✔ / ❌'}),
            'alignement_mandrin_avant': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '✔ / ❌'}),
            'alignement_mandrin_apres': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '✔ / ❌'}),
            'nbr_jonction_avant': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nbr'}),
            'decalage_impress_avant': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '✔ / ❌'}),
        }