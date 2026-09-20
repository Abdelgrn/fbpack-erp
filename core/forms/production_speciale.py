# core/forms/production_speciale.py
from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet

from core.models import (
    ProductionEntry, CalculTempsProduction, ProductionOrder,
    Machine, OrdreFabrication,
    # --- NOUVEAUX MODELES FICHES ---
    FicheProductionJournaliere,
    FicheExtrusionMatiere, FicheExtrusionArret,
    FicheImpressionBobineEntree, FicheImpressionBobineImprimee, FicheImpressionEncreGroupe,
    FicheComplexageDerouleur1, FicheComplexageDerouleur2, FicheComplexageEnrouleur,
    FicheFondCarreEquipe,
    FicheDecoupeBobineMere, FicheDecoupeBobineFille,
    FicheDecoupeArret, FicheDecoupeControle,
)


# ===========================================================================
# WIDGETS COMMUNS (style dark ERP)
# ===========================================================================

_INPUT = {'class': 'form-control'}
_SELECT = {'class': 'form-select'}
_NUMBER = {'class': 'form-control', 'step': 'any'}
_DATE = {'class': 'form-control', 'type': 'date'}
_TIME = {'class': 'form-control', 'type': 'time'}
_TEXTAREA = {'class': 'form-control', 'rows': 3}


# ===========================================================================
# ANCIENS FORMULAIRES (conservés intacts)
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
# HELPER : Formset qui ignore les lignes totalement vides
# ===========================================================================

class SoftRequiredInlineFormSet(BaseInlineFormSet):
    """
    Formset qui :
    - autorise 0 ligne (min_num=0)
    - ignore silencieusement les lignes 100% vides
    - ne bloque PAS la validation si une ligne extra est vide
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.forms:
            form.empty_permitted = True

    def clean(self):
        """Ne pas lever d'erreur si toutes les lignes extras sont vides."""
        # On laisse Django gérer, mais on s'assure qu'aucune erreur
        # "ce champ est obligatoire" ne bloque une ligne vide.
        super().clean()


def _make_fields_optional(form_class, optional_fields=None):
    """Mixin runtime : force required=False sur les champs numériques/texte."""
    original_init = form_class.__init__

    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        targets = optional_fields or list(self.fields.keys())
        for name in targets:
            if name in self.fields and name not in ('id', 'DELETE', 'fiche'):
                self.fields[name].required = False

    form_class.__init__ = new_init
    return form_class


# ===========================================================================
# 1. FORMULAIRE PRINCIPAL : FicheProductionJournaliere
# ===========================================================================

class FicheProductionJournaliereForm(forms.ModelForm):
    class Meta:
        model = FicheProductionJournaliere
        fields = [
            # Type & machine (cachés, gérés par JS)
            'type_fiche', 'machine',
            # En-tête
            'numero_doc', 'numero_lot', 'date_fabrication',
            'heure_debut', 'heure_fin',
            'client', 'designation_produit',
            'poste', 'equipe', 'support',
            'laize_mm', 'vitesse_machine',
            'conducteur', 'aide_conducteur_1', 'aide_conducteur_2',
            # Complexage consommables
            'durcisseur_poids', 'resine_poids', 'solvant_poids',
            # Observations
            'observations', 'visa_resp_production',
            # Optionnel OF
            'of_lie', 'qte_programmee',
        ]
        widgets = {
            'type_fiche': forms.Select(attrs={**_SELECT, 'id': 'id_type_fiche'}),
            'machine': forms.Select(attrs=_SELECT),
            'numero_doc': forms.TextInput(attrs={**_INPUT, 'placeholder': 'N° Doc / Lot de commande'}),
            'numero_lot': forms.TextInput(attrs={**_INPUT, 'placeholder': 'N° Lot (auto si vide)'}),
            'date_fabrication': forms.DateInput(attrs=_DATE),
            'heure_debut': forms.TimeInput(attrs=_TIME),
            'heure_fin': forms.TimeInput(attrs=_TIME),
            'client': forms.Select(attrs=_SELECT),
            'designation_produit': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Motif / Désignation Produit'}),
            'poste': forms.Select(attrs=_SELECT),
            'equipe': forms.Select(attrs=_SELECT),
            'support': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Ex: BOPP 20 TRS, PE 9'}),
            'laize_mm': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'vitesse_machine': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'conducteur': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Nom du conducteur'}),
            'aide_conducteur_1': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Aide conducteur 1'}),
            'aide_conducteur_2': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Aide conducteur 2'}),
            'durcisseur_poids': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'resine_poids': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'solvant_poids': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'observations': forms.Textarea(attrs=_TEXTAREA),
            'visa_resp_production': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Visa / Signature'}),
            'of_lie': forms.Select(attrs=_SELECT),
            'qte_programmee': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Champs non bloquants
        for name in (
            'machine', 'numero_doc', 'numero_lot', 'client', 'designation_produit',
            'poste', 'equipe', 'support', 'laize_mm', 'vitesse_machine',
            'conducteur', 'aide_conducteur_1', 'aide_conducteur_2',
            'heure_debut', 'heure_fin', 'date_fabrication',
            'durcisseur_poids', 'resine_poids', 'solvant_poids',
            'observations', 'visa_resp_production', 'of_lie', 'qte_programmee',
        ):
            if name in self.fields:
                self.fields[name].required = False

        # type_fiche obligatoire (géré par le JS)
        if 'type_fiche' in self.fields:
            self.fields['type_fiche'].required = True

        if 'machine' in self.fields:
            try:
                self.fields['machine'].queryset = Machine.objects.filter(
                    est_active=True
                ).exclude(type__in=['NETT_CL', 'NETT_AN']).order_by('name')
            except Exception:
                pass

        if 'of_lie' in self.fields:
            try:
                self.fields['of_lie'].queryset = OrdreFabrication.objects.exclude(
                    statut__in=['TERMINE', 'ANNULE']
                ).order_by('-date_creation')
            except Exception:
                pass
            self.fields['of_lie'].required = False


# ===========================================================================
# 2. EXTRUSION
# ===========================================================================

class FicheExtrusionMatiereForm(forms.ModelForm):
    class Meta:
        model = FicheExtrusionMatiere
        fields = ['designation', 'num_lot_mp', 'poids_mp_kg', 'qte_realisee_net_kg', 'metrage_m']
        widgets = {
            'designation': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Désignation MP'}),
            'num_lot_mp': forms.TextInput(attrs={**_INPUT, 'placeholder': 'N° Lot MP'}),
            'poids_mp_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'qte_realisee_net_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'metrage_m': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False


class FicheExtrusionArretForm(forms.ModelForm):
    class Meta:
        model = FicheExtrusionArret
        fields = ['code_arret', 'nature_arret', 'temps_min']
        widgets = {
            'code_arret': forms.TextInput(attrs={**_INPUT, 'placeholder': 'T01'}),
            'nature_arret': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Nature'}),
            'temps_min': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False


FicheExtrusionMatiereFormSet = inlineformset_factory(
    FicheProductionJournaliere,
    FicheExtrusionMatiere,
    form=FicheExtrusionMatiereForm,
    formset=SoftRequiredInlineFormSet,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)

FicheExtrusionArretFormSet = inlineformset_factory(
    FicheProductionJournaliere,
    FicheExtrusionArret,
    form=FicheExtrusionArretForm,
    formset=SoftRequiredInlineFormSet,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


# ===========================================================================
# 3. FLEXO / HÉLIO (IMPRESSION)
# ===========================================================================

class FicheFlexoBobineEntreeForm(forms.ModelForm):
    class Meta:
        model = FicheImpressionBobineEntree
        fields = ['num_lot_mp', 'metrage_m', 'poids_kg', 'dechets_neutre_kg']
        widgets = {
            'num_lot_mp': forms.TextInput(attrs={**_INPUT, 'placeholder': 'N° Lot / Bobine'}),
            'metrage_m': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'poids_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'dechets_neutre_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False


class FicheFlexoBobineImprimeeForm(forms.ModelForm):
    class Meta:
        model = FicheImpressionBobineImprimee
        fields = ['nbre_bobines', 'metrage_m', 'poids_kg', 'dechet_imprime_kg']
        widgets = {
            'nbre_bobines': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'metrage_m': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'poids_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'dechet_imprime_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False


class FicheFlexoEncreGroupeForm(forms.ModelForm):
    class Meta:
        model = FicheImpressionEncreGroupe
        fields = ['groupe_numero', 'designation_encre', 'conso_encre_kg', 'conso_solvant_kg']
        widgets = {
            'groupe_numero': forms.HiddenInput(),
            'designation_encre': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Couleur'}),
            'conso_encre_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'conso_solvant_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False


FicheFlexoBobineEntreeFormSet = inlineformset_factory(
    FicheProductionJournaliere,
    FicheImpressionBobineEntree,
    form=FicheFlexoBobineEntreeForm,
    formset=SoftRequiredInlineFormSet,
    fk_name='fiche',
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)

FicheFlexoBobineImprimeeFormSet = inlineformset_factory(
    FicheProductionJournaliere,
    FicheImpressionBobineImprimee,
    form=FicheFlexoBobineImprimeeForm,
    formset=SoftRequiredInlineFormSet,
    fk_name='fiche',
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)

FicheFlexoEncreGroupeFormSet = inlineformset_factory(
    FicheProductionJournaliere,
    FicheImpressionEncreGroupe,
    form=FicheFlexoEncreGroupeForm,
    formset=SoftRequiredInlineFormSet,
    fk_name='fiche',
    extra=8,          # 8 groupes d'encre
    can_delete=False,
    min_num=0,
    validate_min=False,
    max_num=8,
)


# ===========================================================================
# 4. COMPLEXAGE
# ===========================================================================

class FicheComplexageDerouleur1Form(forms.ModelForm):
    class Meta:
        model = FicheComplexageDerouleur1
        fields = ['num_lot_mp', 'poids_kg', 'dechets_kg']
        widgets = {
            'num_lot_mp': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Lot MP'}),
            'poids_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'dechets_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False


class FicheComplexageDerouleur2Form(forms.ModelForm):
    class Meta:
        model = FicheComplexageDerouleur2
        fields = ['num_lot_mp', 'poids_kg', 'dechets_kg']
        widgets = {
            'num_lot_mp': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Lot MP'}),
            'poids_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'dechets_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False


class FicheComplexageEnrouleurForm(forms.ModelForm):
    class Meta:
        model = FicheComplexageEnrouleur
        fields = ['num_lot', 'poids_kg', 'dechets_kg', 'ml']
        widgets = {
            'num_lot': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Lot'}),
            'poids_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'dechets_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'ml': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False


FicheComplexageDerouleur1FormSet = inlineformset_factory(
    FicheProductionJournaliere,
    FicheComplexageDerouleur1,
    form=FicheComplexageDerouleur1Form,
    formset=SoftRequiredInlineFormSet,
    extra=1, can_delete=True, min_num=0, validate_min=False,
)

FicheComplexageDerouleur2FormSet = inlineformset_factory(
    FicheProductionJournaliere,
    FicheComplexageDerouleur2,
    form=FicheComplexageDerouleur2Form,
    formset=SoftRequiredInlineFormSet,
    extra=1, can_delete=True, min_num=0, validate_min=False,
)

FicheComplexageEnrouleurFormSet = inlineformset_factory(
    FicheProductionJournaliere,
    FicheComplexageEnrouleur,
    form=FicheComplexageEnrouleurForm,
    formset=SoftRequiredInlineFormSet,
    extra=1, can_delete=True, min_num=0, validate_min=False,
)


# ===========================================================================
# 5. FONDS CARRÉS
# ===========================================================================

class FicheFondCarreEquipeForm(forms.ModelForm):
    class Meta:
        model = FicheFondCarreEquipe
        fields = [
            'equipe_num', 'shift_code', 'operateur',
            'nb_sacs', 'poids_sacs_kg', 'dechets_sacs_kg',
            'poids_initial_kg', 'dechets_bob_kg',
        ]
        widgets = {
            'equipe_num': forms.HiddenInput(),
            'shift_code': forms.HiddenInput(),
            'operateur': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Opérateur'}),
            'nb_sacs': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'poids_sacs_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'dechets_sacs_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'poids_initial_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'dechets_bob_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False


FicheFondCarreEquipeFormSet = inlineformset_factory(
    FicheProductionJournaliere,
    FicheFondCarreEquipe,
    form=FicheFondCarreEquipeForm,
    formset=SoftRequiredInlineFormSet,
    extra=3,          # 3 shifts
    can_delete=False,
    min_num=0,
    validate_min=False,
    max_num=3,
)


# ===========================================================================
# 6. DÉCOUPE (Bobines Mères / Filles / Arrêts / Contrôle)
# ===========================================================================

class FicheDecoupeBobineMereForm(forms.ModelForm):
    class Meta:
        model = FicheDecoupeBobineMere
        fields = ['reference_lot', 'poids_kg', 'metrage_ml']
        widgets = {
            'reference_lot': forms.TextInput(attrs={**_INPUT, 'placeholder': 'Réf / N° Lot'}),
            'poids_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'metrage_ml': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False


class FicheDecoupeBobineFilleForm(forms.ModelForm):
    class Meta:
        model = FicheDecoupeBobineFille
        fields = [
            'nombre_filles', 'poids_filles_kg',
            'nombre_a_reviser', 'poids_a_reviser_kg',
            # Déchets globaux (injectés via JS sur la ligne 0)
            'dechets_demarrage_kg', 'dechets_lisiere_kg',
            'dechets_jonction_kg', 'dechets_transport_kg',
            'rouleaux_non_conforme_kg',
        ]
        widgets = {
            'nombre_filles': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'poids_filles_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'nombre_a_reviser': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'poids_a_reviser_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'dechets_demarrage_kg': forms.HiddenInput(),
            'dechets_lisiere_kg': forms.HiddenInput(),
            'dechets_jonction_kg': forms.HiddenInput(),
            'dechets_transport_kg': forms.HiddenInput(),
            'rouleaux_non_conforme_kg': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False


class FicheDecoupeArretForm(forms.ModelForm):
    class Meta:
        model = FicheDecoupeArret
        fields = ['cause', 'temps_min', 'dechets_kg']
        widgets = {
            'cause': forms.HiddenInput(),
            'temps_min': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
            'dechets_kg': forms.NumberInput(attrs={**_NUMBER, 'placeholder': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False


class FicheDecoupeControleForm(forms.ModelForm):
    class Meta:
        model = FicheDecoupeControle
        # Adapte les champs selon ton modèle réel
        fields = '__all__'
        exclude = ['fiche']
        widgets = {
            # Widgets par défaut ; complète si besoin
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = False


FicheDecoupeBobineMereFormSet = inlineformset_factory(
    FicheProductionJournaliere,
    FicheDecoupeBobineMere,
    form=FicheDecoupeBobineMereForm,
    formset=SoftRequiredInlineFormSet,
    fk_name='fiche',
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)

FicheDecoupeBobineFilleFormSet = inlineformset_factory(
    FicheProductionJournaliere,
    FicheDecoupeBobineFille,
    form=FicheDecoupeBobineFilleForm,
    formset=SoftRequiredInlineFormSet,
    fk_name='fiche',
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)

FicheDecoupeArretFormSet = inlineformset_factory(
    FicheProductionJournaliere,
    FicheDecoupeArret,
    form=FicheDecoupeArretForm,
    formset=SoftRequiredInlineFormSet,
    fk_name='fiche',
    extra=14,         # 14 causes pré-chargées
    can_delete=False,
    min_num=0,
    validate_min=False,
)