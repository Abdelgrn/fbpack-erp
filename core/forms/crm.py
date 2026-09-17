from django import forms
from core.models import Client, ClientContact, InteractionLog, Opportunite, Quote

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'name', 'code_client', 'status', 'segment', 'size', 'region',
            'ca_estime', 'sector', 'city', 'address', 'phone', 'email',
            'website', 'commercial', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code_client': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'segment': forms.Select(attrs={'class': 'form-select'}),
            'size': forms.Select(attrs={'class': 'form-select'}),
            'region': forms.Select(attrs={'class': 'form-select'}),
            'ca_estime': forms.NumberInput(attrs={'class': 'form-control'}),
            'sector': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'commercial': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class ClientContactForm(forms.ModelForm):
    class Meta:
        model = ClientContact
        fields = ['name', 'role', 'role_custom', 'phone', 'email', 'is_primary', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'role_custom': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class InteractionLogForm(forms.ModelForm):
    class Meta:
        model = InteractionLog
        fields = ['contact', 'commercial', 'type', 'summary', 'details', 'next_action', 'next_action_date']
        widgets = {
            'contact': forms.Select(attrs={'class': 'form-select'}),
            'commercial': forms.Select(attrs={'class': 'form-select'}),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'summary': forms.TextInput(attrs={'class': 'form-control'}),
            'details': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'next_action': forms.TextInput(attrs={'class': 'form-control'}),
            'next_action_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        if client:
            self.fields['contact'].queryset = ClientContact.objects.filter(client=client)

class OpportuniteForm(forms.ModelForm):
    class Meta:
        model = Opportunite
        fields = [
            'client', 'commercial', 'titre', 'description', 'status',
            'valeur_estimee', 'probabilite', 'date_cloture_prevue', 'notes'
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'commercial': forms.Select(attrs={'class': 'form-select'}),
            'titre': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'valeur_estimee': forms.NumberInput(attrs={'class': 'form-control'}),
            'probabilite': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100}),
            'date_cloture_prevue': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class QuoteForm(forms.ModelForm):
    class Meta:
        model = Quote
        fields = [
            'client', 'opportunite', 'commercial', 'reference', 'version',
            'date_validite', 'total_amount', 'status', 'pdf_file', 'notes'
        ]
        widgets = {
            'client': forms.Select(attrs={'class': 'form-select'}),
            'opportunite': forms.Select(attrs={'class': 'form-select'}),
            'commercial': forms.Select(attrs={'class': 'form-select'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'version': forms.NumberInput(attrs={'class': 'form-control'}),
            'date_validite': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
