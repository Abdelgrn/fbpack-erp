from django import forms
from django.db import models
from core.models import Supplier, Material
from core.models.stock import StockCatalogOption
from core.models.stock import StockLocation

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'email']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'email': forms.EmailInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
        }


class MaterialForm(forms.ModelForm):
    unit = forms.ChoiceField(label='Unité', choices=(), widget=forms.Select(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}))

    class Meta:
        model = Material
        fields = [
            'name', 'code', 'category', 'densite_iso', 'micronage_standard', 'grammage', 'metrage_standard', 'laize_mm', 'origine', 'poids_kg', 'nombre_unites',
            'initial_quantity', 'quantity', 'unit', 'depot', 'famille', 'sous_famille', 'min_threshold', 'supplier', 'price_per_unit'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'code': forms.TextInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500', 'placeholder': 'Ex: HSAU200019'}),
            'category': forms.Select(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'densite_iso': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500', 'step': '0.01'}),
            'micronage_standard': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500', 'placeholder': 'Ex: 12, 20, 30, 40 (µm)'}),
            'grammage': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500', 'placeholder': 'Ex: 70, 80, 90 (g/m²)'}),
            'metrage_standard': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500', 'placeholder': 'Ex: 6000, 10000 (m)'}),
            'laize_mm': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500', 'placeholder': 'Ex: 680 (mm)'}),
            'origine': forms.Select(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'poids_kg': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500', 'step': '0.01'}),
            'nombre_unites': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'initial_quantity': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500', 'placeholder': 'Stock de départ'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'unit': forms.Select(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'depot': forms.Select(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'famille': forms.Select(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'sous_famille': forms.Select(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'min_threshold': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'supplier': forms.Select(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'price_per_unit': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        def options(kind):
            return [(o.name, o.name) for o in StockCatalogOption.objects.filter(kind=kind, active=True)]
        units = options('UNIT')
        current = self.initial.get('unit') or getattr(self.instance, 'unit', '')
        if current and current not in dict(units):
            units.insert(0, (current, current))
        self.fields['unit'].choices = [('', '— Choisir —')] + units
        for field, kind in [('depot', 'DEPOT'), ('famille', 'FAMILY'), ('sous_famille', 'SUBFAMILY')]:
            qs = StockCatalogOption.objects.filter(kind=kind, active=True)
            selected = getattr(self.instance, field, None)
            if selected and not selected.active:
                qs = StockCatalogOption.objects.filter(kind=kind).filter(models.Q(active=True) | models.Q(pk=selected.pk))
            self.fields[field].queryset = qs.order_by('position', 'name')
        self.fields['depot'].required = False
        self.fields['famille'].required = False
        self.fields['sous_famille'].required = False


class MaterialEditForm(MaterialForm):
    """Édition des caractéristiques sans possibilité d'écrire le stock."""
    class Meta(MaterialForm.Meta):
        fields = [field for field in MaterialForm.Meta.fields if field not in {'initial_quantity', 'quantity'}]


class MaterialCreateForm(MaterialForm):
    """Formulaire de création : le stock initial est enregistré comme une réception."""
    emplacement_reception = forms.ModelChoiceField(
        label='Emplacement de réception', queryset=StockLocation.objects.none(), required=True,
        empty_label='— Choisir l’emplacement —',
        widget=forms.Select(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
    )

    class Meta(MaterialForm.Meta):
        fields = [field for field in MaterialForm.Meta.fields if field != 'quantity']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['initial_quantity'].required = True
        self.fields['initial_quantity'].widget.attrs.update({'min': '0.001', 'step': '0.001'})
        self.fields['poids_kg'].required = True
        self.fields['nombre_unites'].required = True
        self.fields['origine'].required = True
        self.fields['emplacement_reception'].queryset = StockLocation.objects.filter(is_active=True).order_by('name')

    def clean_poids_kg(self):
        weight = self.cleaned_data.get('poids_kg')
        if weight is None or weight <= 0:
            raise forms.ValidationError('Saisissez un poids supérieur à zéro.')
        return weight

    def clean_nombre_unites(self):
        units = self.cleaned_data.get('nombre_unites')
        if units is None or units < 1:
            raise forms.ValidationError('Saisissez un nombre d’unités supérieur à zéro.')
        return units

    def clean_initial_quantity(self):
        quantity = self.cleaned_data.get('initial_quantity')
        if quantity is None or quantity <= 0:
            raise forms.ValidationError('Saisissez une quantité reçue supérieure à zéro.')
        return quantity


class StockImportForm(forms.Form):
    IMPORT_TYPE_CHOICES = [
        ('MOUVEMENTS', '🔄 Journal Mouvements (Flexo/Hélio)'),
        ('STOCK', '📦 Stock (Matières Premières)'),
        ('CRM', '🤝 CRM (Clients & Prospects)'),
        ('TOOLS', '⚙️ Outillage (Cylindres & Clichés)'),
        ('PLANNING', '🏭 Planning Production (OF)'),
        ('CONSO', '💧 Consommation (Flexo/Hélio)'),
        ('SPECIAL_PROD', '🔧 Production Spéciale (Découpe/Impression)'),
    ]
    import_type = forms.ChoiceField(choices=IMPORT_TYPE_CHOICES, widget=forms.Select(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500', 'id': 'typeSelector'}))
    excel_file = forms.FileField(label="Fichier Excel (.xlsx, .xls)")