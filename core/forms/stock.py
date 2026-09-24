from django import forms
from core.models import Supplier, Material

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'email']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['name', 'code', 'category', 'initial_quantity', 'quantity', 'unit', 'min_threshold', 'supplier', 'price_per_unit']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: HSAU200019'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'initial_quantity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Stock au départ'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'min_threshold': forms.NumberInput(attrs={'class': 'form-control'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'price_per_unit': forms.NumberInput(attrs={'class': 'form-control'}),
        }


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
    import_type = forms.ChoiceField(choices=IMPORT_TYPE_CHOICES, widget=forms.Select(attrs={'class': 'form-select', 'id': 'typeSelector'}))
    excel_file = forms.FileField(label="Fichier Excel (.xlsx, .xls)")