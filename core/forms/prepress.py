from django import forms
from core.models import TechnicalProduct, Tooling

class ProductForm(forms.ModelForm):
    class Meta:
        model = TechnicalProduct
        fields = [
            'client', 'ref_internal', 'name', 'structure_type',
            'width_mm', 'cut_length_mm', 'num_colors', 'artwork_file'
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'ref_internal': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'structure_type': forms.Select(attrs={'class': 'form-select'}),
            'width_mm': forms.NumberInput(attrs={'class': 'form-control'}),
            'cut_length_mm': forms.NumberInput(attrs={'class': 'form-control'}),
            'num_colors': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class ToolForm(forms.ModelForm):
    class Meta:
        model = Tooling
        fields = ['product', 'tool_type', 'serial_number', 'max_impressions', 'current_impressions']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'tool_type': forms.Select(attrs={'class': 'form-select'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'max_impressions': forms.NumberInput(attrs={'class': 'form-control'}),
            'current_impressions': forms.NumberInput(attrs={'class': 'form-control'}),
        }