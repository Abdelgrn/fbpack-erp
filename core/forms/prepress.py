from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from core.models import PrepressColor, TechnicalProduct, Tooling


_INPUT_CLASS = (
    'w-full rounded-xl border border-slate-600 bg-slate-900 px-3 py-2.5 '
    'text-sm text-white placeholder-slate-500 outline-none transition '
    'focus:border-cyan-400 focus:ring-2 focus:ring-cyan-500/20'
)


class ProductForm(forms.ModelForm):
    class Meta:
        model = TechnicalProduct
        fields = [
            'client',
            'ref_internal',
            'name',
            'printing_process',
            'structure_type',
            'width_mm',
            'cut_length_mm',
            'artwork_file',
            'tech_sheet_file',
            'product_visual',
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
            'technical_notes',
            'sens_bobine',
            'spot_placement',
            'bat_status',
            'version',
            'is_obsolete',
        ]
        widgets = {
            'client': forms.Select(attrs={'class': _INPUT_CLASS}),
            'ref_internal': forms.TextInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'Ex. 25F052'}),
            'name': forms.TextInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'Désignation complète du produit'}),
            'printing_process': forms.Select(attrs={'class': _INPUT_CLASS}),
            'structure_type': forms.Select(attrs={'class': _INPUT_CLASS}),
            'width_mm': forms.NumberInput(attrs={'class': _INPUT_CLASS, 'min': 0, 'step': '0.001'}),
            'cut_length_mm': forms.NumberInput(attrs={'class': _INPUT_CLASS, 'min': 0, 'step': '0.001'}),
            'artwork_file': forms.ClearableFileInput(attrs={'class': _INPUT_CLASS}),
            'tech_sheet_file': forms.ClearableFileInput(attrs={'class': _INPUT_CLASS}),
            'product_visual': forms.ClearableFileInput(attrs={'class': _INPUT_CLASS, 'accept': 'image/png,image/jpeg,image/webp'}),
            'date_creation': forms.DateInput(format='%Y-%m-%d', attrs={'class': _INPUT_CLASS, 'type': 'date'}),
            'graveur': forms.TextInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'Ex. STUDIO FL'}),
            'ref_graveur': forms.TextInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'Référence du graveur'}),
            'type_dossier': forms.Select(attrs={'class': _INPUT_CLASS}),
            'nb_poses_pas': forms.NumberInput(attrs={'class': _INPUT_CLASS, 'min': 1, 'max': 100, 'step': 1}),
            'nb_poses_laize': forms.NumberInput(attrs={'class': _INPUT_CLASS, 'min': 1, 'max': 100, 'step': 1}),
            'developpement_mm': forms.NumberInput(attrs={'class': _INPUT_CLASS, 'readonly': 'readonly', 'step': '0.001'}),
            'laize_gravure_mm': forms.NumberInput(attrs={'class': _INPUT_CLASS, 'readonly': 'readonly', 'step': '0.001'}),
            'support_impression': forms.TextInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'Ex. OPP TRNSP 30 / MTLZ 20'}),
            'impression': forms.TextInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'Ex. CELLO EMAIL'}),
            'spot': forms.TextInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'Ex. 15 mm x 15 mm'}),
            'technical_notes': forms.Textarea(attrs={'class': _INPUT_CLASS, 'rows': 3, 'placeholder': 'Observations techniques complémentaires'}),
            'sens_bobine': forms.Select(attrs={'class': _INPUT_CLASS}),
            'spot_placement': forms.Select(attrs={'class': _INPUT_CLASS}),
            'bat_status': forms.Select(attrs={'class': _INPUT_CLASS}),
            'version': forms.TextInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'V1.0'}),
            'is_obsolete': forms.CheckboxInput(attrs={'class': 'h-5 w-5 rounded border-slate-600 bg-slate-900 accent-red-500'}),
        }

    def clean_ref_internal(self):
        value = (self.cleaned_data.get('ref_internal') or '').strip()
        if not value:
            raise forms.ValidationError('La référence interne est obligatoire.')
        return value

    def clean_product_visual(self):
        uploaded = self.cleaned_data.get('product_visual')
        if not uploaded or not hasattr(uploaded, 'size'):
            return uploaded
        if uploaded.size > 10 * 1024 * 1024:
            raise forms.ValidationError('Le visuel produit ne doit pas dépasser 10 Mo.')
        content_type = (getattr(uploaded, 'content_type', '') or '').lower()
        if content_type and content_type not in {'image/png', 'image/jpeg', 'image/webp'}:
            raise forms.ValidationError('Formats autorisés : PNG, JPG/JPEG ou WEBP.')
        return uploaded

    def clean(self):
        cleaned = super().clean()
        width = cleaned.get('width_mm') or 0
        cut_length = cleaned.get('cut_length_mm') or 0
        poses_pas = cleaned.get('nb_poses_pas') or 0
        poses_laize = cleaned.get('nb_poses_laize') or 0

        if width < 0:
            self.add_error('width_mm', 'La laize ne peut pas être négative.')
        if cut_length < 0:
            self.add_error('cut_length_mm', 'Le pas ne peut pas être négatif.')
        if poses_pas < 1:
            self.add_error('nb_poses_pas', 'Le nombre de poses doit être au moins égal à 1.')
        if poses_laize < 1:
            self.add_error('nb_poses_laize', 'Le nombre de poses doit être au moins égal à 1.')

        cleaned['developpement_mm'] = round(float(cut_length) * int(poses_pas), 3) if cut_length and poses_pas else 0
        cleaned['laize_gravure_mm'] = round(float(width) * int(poses_laize), 3) if width and poses_laize else 0
        return cleaned


class PrepressColorForm(forms.ModelForm):
    class Meta:
        model = PrepressColor
        fields = [
            'couleur_hex',
            'nom_couleur',
            'anilox',
            'adhesif',
            'viscosite',
            'type_encre',
            'formule_encre',
        ]
        widgets = {
            'couleur_hex': forms.TextInput(attrs={
                'class': 'h-10 w-14 cursor-pointer rounded border border-slate-500 bg-transparent p-0.5',
                'type': 'color',
                'title': 'Aperçu de la couleur',
            }),
            'nom_couleur': forms.TextInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'CYAN, MAGENTA, P 485 C…'}),
            'anilox': forms.TextInput(attrs={'class': _INPUT_CLASS, 'placeholder': 'Ex. 420 / 5'}),
            'adhesif': forms.TextInput(attrs={'class': _INPUT_CLASS}),
            'viscosite': forms.TextInput(attrs={'class': _INPUT_CLASS}),
            'type_encre': forms.TextInput(attrs={'class': _INPUT_CLASS}),
            'formule_encre': forms.TextInput(attrs={'class': _INPUT_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Une ligne totalement vide doit rester facultative même si le navigateur
        # soumet la valeur par défaut du sélecteur de couleur.
        self.fields['nom_couleur'].required = False
        self.fields['couleur_hex'].required = False

    def clean(self):
        cleaned = super().clean()
        name = (cleaned.get('nom_couleur') or '').strip()
        technical_values = [
            cleaned.get('anilox'), cleaned.get('adhesif'), cleaned.get('viscosite'),
            cleaned.get('type_encre'), cleaned.get('formule_encre'),
        ]
        if not name and any(str(value or '').strip() for value in technical_values):
            self.add_error('nom_couleur', 'Indiquez le nom de la couleur pour cette ligne.')
        if name:
            cleaned['nom_couleur'] = name
            cleaned['couleur_hex'] = (cleaned.get('couleur_hex') or '#FFFFFF').upper()
        return cleaned


class BasePrepressColorFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        active_count = 0
        for form in self.forms:
            data = getattr(form, 'cleaned_data', {})
            if not data or data.get('DELETE'):
                continue
            if (data.get('nom_couleur') or '').strip():
                active_count += 1
        if active_count > 8:
            raise forms.ValidationError('Une fiche technique peut contenir au maximum 8 couleurs.')


PrepressColorFormSet = inlineformset_factory(
    TechnicalProduct,
    PrepressColor,
    form=PrepressColorForm,
    formset=BasePrepressColorFormSet,
    fields=[
        'couleur_hex', 'nom_couleur', 'anilox', 'adhesif',
        'viscosite', 'type_encre', 'formule_encre',
    ],
    extra=8,
    max_num=8,
    validate_max=True,
    can_delete=True,
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
