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
        fields = ['name', 'category', 'quantity', 'unit', 'min_threshold', 'supplier', 'price_per_unit']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'min_threshold': forms.NumberInput(attrs={'class': 'form-control'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'price_per_unit': forms.NumberInput(attrs={'class': 'form-control'}),
        }