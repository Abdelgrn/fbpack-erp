from django import forms
from core.models import ConsommationEncre

class ConsommationEncreForm(forms.ModelForm):
    class Meta:
        model = ConsommationEncre
        fields = [
            'job_name', 'date', 'process_type', 'support', 'laize',
            'bobine_in', 'bobine_out', 'metrage',
            'encre_noir', 'encre_magenta', 'encre_jaune', 'encre_cyan',
            'encre_dore', 'encre_silver', 'encre_orange', 'encre_blanc', 'encre_vernis',
            'solvant_metoxyn', 'solvant_2080'
        ]
        widgets = {
            'job_name': forms.TextInput(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'process_type': forms.Select(attrs={'class': 'form-select'}),
            'support': forms.TextInput(attrs={'class': 'form-control'}),
            'laize': forms.NumberInput(attrs={'class': 'form-control'}),
            'bobine_in': forms.NumberInput(attrs={'class': 'form-control'}),
            'bobine_out': forms.NumberInput(attrs={'class': 'form-control'}),
            'metrage': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_noir': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_magenta': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_jaune': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_cyan': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_dore': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_silver': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_orange': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_blanc': forms.NumberInput(attrs={'class': 'form-control'}),
            'encre_vernis': forms.NumberInput(attrs={'class': 'form-control'}),
            'solvant_metoxyn': forms.NumberInput(attrs={'class': 'form-control'}),
            'solvant_2080': forms.NumberInput(attrs={'class': 'form-control'}),
        }
