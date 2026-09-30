from django import forms
from core.models import Supplier, Material

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'email']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'email': forms.EmailInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
        }


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['name', 'code', 'category', 'initial_quantity', 'quantity', 'unit', 'min_threshold', 'supplier', 'price_per_unit']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'code': forms.TextInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500', 'placeholder': 'Ex: HSAU200019'}),
            'category': forms.Select(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'initial_quantity': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500', 'placeholder': 'Stock de départ'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'unit': forms.TextInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'min_threshold': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'supplier': forms.Select(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
            'price_per_unit': forms.NumberInput(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500'}),
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
    import_type = forms.ChoiceField(choices=IMPORT_TYPE_CHOICES, widget=forms.Select(attrs={'class': 'w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-cyan-500', 'id': 'typeSelector'}))
    excel_file = forms.FileField(label="Fichier Excel (.xlsx, .xls)")