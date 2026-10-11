from django import forms
from django.forms import inlineformset_factory
from core.models import TechnicalProduct, Tooling, PrepressColor


class ProductForm(forms.ModelForm):
    class Meta:
        model = TechnicalProduct
        fields = [
            'client',
            'ref_internal',
            'name',
            'structure_type',
            'width_mm',
            'cut_length_mm',
            'num_colors',
            'artwork_file',
            'tech_sheet_file',
            'date_creation',
            'graveur',
            'ref_graveur',
            'type_dossier',
            'nb_poses_pas',
            'nb_poses_laize',
            'developpement_mm',
            'laize_gravure_mm',
            'support_impression',
            'impression',
            'spot',
            'sens_bobine',
            'spot_placement',
            'bat_status',
            'version',
            'is_obsolete',
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'ref_internal': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'structure_type': forms.Select(attrs={'class': 'form-select'}),
            'width_mm': forms.NumberInput(attrs={'class': 'form-control'}),
            'cut_length_mm': forms.NumberInput(attrs={'class': 'form-control'}),
            'num_colors': forms.NumberInput(attrs={'class': 'form-control'}),
            'artwork_file': forms.FileInput(attrs={'class': 'form-control'}),
            'tech_sheet_file': forms.FileInput(attrs={'class': 'form-control'}),
            'date_creation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'graveur': forms.TextInput(attrs={'class': 'form-control'}),
            'ref_graveur': forms.TextInput(attrs={'class': 'form-control'}),
            'type_dossier': forms.Select(attrs={'class': 'form-select'}),
            'nb_poses_pas': forms.NumberInput(attrs={'class': 'form-control'}),
            'nb_poses_laize': forms.NumberInput(attrs={'class': 'form-control'}),
            'developpement_mm': forms.NumberInput(attrs={'class': 'form-control'}),
            'laize_gravure_mm': forms.NumberInput(attrs={'class': 'form-control'}),
            'support_impression': forms.TextInput(attrs={'class': 'form-control'}),
            'impression': forms.TextInput(attrs={'class': 'form-control'}),
            'spot': forms.TextInput(attrs={'class': 'form-control'}),
            'sens_bobine': forms.Select(attrs={'class': 'form-select'}),
            'spot_placement': forms.Select(attrs={'class': 'form-select'}),
            'bat_status': forms.Select(attrs={'class': 'form-select font-bold'}),
            'version': forms.TextInput(attrs={'class': 'form-control'}),
            'is_obsolete': forms.CheckboxInput(attrs={'class': 'w-5 h-5 accent-red-500 rounded border-slate-700 bg-slate-900 cursor-pointer'}),
        }


class PrepressColorForm(forms.ModelForm):
    class Meta:
        model = PrepressColor
        fields = [
            'ordre',
            'nom_couleur',
            'anilox',
            'adhesif',
            'viscosite',
            'type_encre',
            'formule_encre',
        ]
        widgets = {
            'ordre': forms.NumberInput(attrs={'class': 'form-control'}),
            'nom_couleur': forms.TextInput(attrs={'class': 'form-control'}),
            'anilox': forms.TextInput(attrs={'class': 'form-control'}),
            'adhesif': forms.TextInput(attrs={'class': 'form-control'}),
            'viscosite': forms.TextInput(attrs={'class': 'form-control'}),
            'type_encre': forms.TextInput(attrs={'class': 'form-control'}),
            'formule_encre': forms.TextInput(attrs={'class': 'form-control'}),
        }


PrepressColorFormSet = inlineformset_factory(
    TechnicalProduct,
    PrepressColor,
    form=PrepressColorForm,
    extra=8,
    can_delete=True
)


class ToolForm(forms.ModelForm):
    class Meta:
        model = Tooling
        fields = [
            'product',
            'tool_type',
            'serial_number',
            'date_creation',
            'max_impressions',
            'current_impressions',
            'metrage_realise',
            'observations',
            'supplier_name', 'color_count',
            'color_1', 'color_2', 'color_3', 'color_4',
            'color_5', 'color_6', 'color_7', 'color_8',
        ]
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'tool_type': forms.Select(attrs={'class': 'form-select'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'date_creation': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'max_impressions': forms.NumberInput(attrs={'class': 'form-control'}),
            'current_impressions': forms.NumberInput(attrs={'class': 'form-control'}),
            'metrage_realise': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'observations': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'supplier_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : FL Studio, Yahiaoui...'}),
            'color_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 8, 'step': 1, 'oninput': 'updateToolColorFields()'}),
            'color_1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Cyan'}),
            'color_2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Magenta'}),
            'color_3': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Jaune'}),
            'color_4': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Noir'}),
            'color_5': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Bleu Reflex'}),
            'color_6': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Orange'}),
            'color_7': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Violet'}),
            'color_8': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Blanc'}),
        }

    def clean_color_count(self):
        value = self.cleaned_data.get('color_count') or 0
        if value < 0 or value > 8:
            raise forms.ValidationError('Le nombre de couleurs doit être compris entre 0 et 8.')
        return value

    def clean(self):
        cleaned_data = super().clean()
        count = cleaned_data.get('color_count') or 0
        for index in range(1, 9):
            field_name = f'color_{index}'
            value = (cleaned_data.get(field_name) or '').strip()
            if index <= count and not value:
                self.add_error(field_name, f'Veuillez renseigner la couleur n°{index}.')
            if index > count:
                cleaned_data[field_name] = ''
        return cleaned_data