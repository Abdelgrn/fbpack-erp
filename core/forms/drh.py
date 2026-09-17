from django import forms
from core.models import (
    Department, Position, Employee, EmployeeDocument, Skill, EmployeeSkill,
    MachineAuthorization, Shift, Attendance, LeaveType, LeaveRequest, Payslip,
    WorkSchedule, ShiftAssignment, MedicalVisit, WorkIncident, ProtectiveEquipment, Machine
)

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Production'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: PROD'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ['name', 'code', 'category', 'department', 'description', 
                  'salaire_min', 'salaire_max', 'requires_machine_auth', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'salaire_min': forms.NumberInput(attrs={'class': 'form-control'}),
            'salaire_max': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            'nom', 'prenom', 'nom_arabe', 'date_naissance', 'lieu_naissance',
            'genre', 'situation_familiale', 'nb_enfants',
            'cin', 'num_securite_sociale', 'num_carte_chifa',
            'adresse', 'wilaya', 'commune', 'telephone', 'telephone_urgence', 'email',
            'department', 'position', 'superieur', 'machine_affectee', 'atelier',
            'type_contrat', 'date_embauche', 'date_fin_contrat', 'salaire_base',
            'statut', 'photo', 'notes',
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de famille'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom'}),
            'nom_arabe': forms.TextInput(attrs={'class': 'form-control', 'dir': 'rtl'}),
            'date_naissance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lieu_naissance': forms.TextInput(attrs={'class': 'form-control'}),
            'genre': forms.Select(attrs={'class': 'form-select'}),
            'situation_familiale': forms.Select(attrs={'class': 'form-select'}),
            'nb_enfants': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'cin': forms.TextInput(attrs={'class': 'form-control'}),
            'num_securite_sociale': forms.TextInput(attrs={'class': 'form-control'}),
            'num_carte_chifa': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'wilaya': forms.TextInput(attrs={'class': 'form-control'}),
            'commune': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone_urgence': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'position': forms.Select(attrs={'class': 'form-select'}),
            'superieur': forms.Select(attrs={'class': 'form-select'}),
            'machine_affectee': forms.Select(attrs={'class': 'form-select'}),
            'atelier': forms.TextInput(attrs={'class': 'form-control'}),
            'type_contrat': forms.Select(attrs={'class': 'form-select'}),
            'date_embauche': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin_contrat': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'salaire_base': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class EmployeeDocumentForm(forms.ModelForm):
    class Meta:
        model = EmployeeDocument
        fields = ['type_document', 'nom', 'fichier', 'date_expiration', 'notes']
        widgets = {
            'type_document': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'date_expiration': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ['name', 'code', 'category', 'description', 'machine_associee', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'machine_associee': forms.Select(attrs={'class': 'form-select'}),
        }


class EmployeeSkillForm(forms.ModelForm):
    class Meta:
        model = EmployeeSkill
        fields = ['skill', 'level', 'date_acquisition', 'certificat', 'notes']
        widgets = {
            'skill': forms.Select(attrs={'class': 'form-select'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'date_acquisition': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class MachineAuthorizationForm(forms.ModelForm):
    class Meta:
        model = MachineAuthorization
        fields = ['machine', 'niveau_autorisation', 'date_expiration', 'notes']
        widgets = {
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'niveau_autorisation': forms.Select(attrs={'class': 'form-select'}),
            'date_expiration': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ShiftForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = ['name', 'code', 'heure_debut', 'heure_fin', 'pause_debut', 
                  'pause_fin', 'heures_travail', 'couleur', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'heure_debut': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'pause_debut': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'pause_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heures_travail': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'couleur': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['employee', 'date', 'shift', 'heure_arrivee', 'heure_depart',
                  'statut', 'machine', 'atelier', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'shift': forms.Select(attrs={'class': 'form-select'}),
            'heure_arrivee': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_depart': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'atelier': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class AttendanceBulkForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    shift = forms.ModelChoiceField(
        queryset=Shift.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class LeaveTypeForm(forms.ModelForm):
    class Meta:
        model = LeaveType
        fields = ['name', 'code', 'jours_par_an', 'paye', 'justificatif_requis', 'couleur', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'jours_par_an': forms.NumberInput(attrs={'class': 'form-control'}),
            'couleur': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }


class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['type_conge', 'date_debut', 'date_fin', 'motif', 'justificatif']
        widgets = {
            'type_conge': forms.Select(attrs={'class': 'form-select'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'motif': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PayslipForm(forms.ModelForm):
    class Meta:
        model = Payslip
        fields = [
            'employee', 'mois', 'annee', 'jours_travailles', 'jours_absence', 'jours_conge',
            'heures_supplementaires_25', 'heures_supplementaires_50', 'heures_supplementaires_100',
            'heures_nuit', 'prime_rendement', 'prime_presence', 'prime_transport', 'prime_panier',
            'autres_primes', 'avance_salaire', 'pret', 'autres_retenues', 'notes'
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'mois': forms.Select(attrs={'class': 'form-select'}, choices=[(i, f"{i:02d}") for i in range(1, 13)]),
            'annee': forms.NumberInput(attrs={'class': 'form-control'}),
            'jours_travailles': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'jours_absence': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'jours_conge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'heures_supplementaires_25': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'heures_supplementaires_50': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'heures_supplementaires_100': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'heures_nuit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'prime_rendement': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'prime_presence': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'prime_transport': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'prime_panier': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'autres_primes': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'avance_salaire': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'pret': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'autres_retenues': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class WorkScheduleForm(forms.ModelForm):
    class Meta:
        model = WorkSchedule
        fields = ['name', 'date_debut', 'date_fin', 'department', 'machine', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ShiftAssignmentForm(forms.ModelForm):
    class Meta:
        model = ShiftAssignment
        fields = ['employee', 'shift', 'date', 'machine', 'poste', 'est_remplacement', 'remplace', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'shift': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'poste': forms.TextInput(attrs={'class': 'form-control'}),
            'remplace': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class MedicalVisitForm(forms.ModelForm):
    class Meta:
        model = MedicalVisit
        fields = ['employee', 'type_visite', 'date_visite', 'medecin', 'resultat',
                  'restrictions', 'date_prochaine_visite', 'certificat', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'type_visite': forms.Select(attrs={'class': 'form-select'}),
            'date_visite': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'medecin': forms.TextInput(attrs={'class': 'form-control'}),
            'resultat': forms.Select(attrs={'class': 'form-select'}),
            'restrictions': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'date_prochaine_visite': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class WorkIncidentForm(forms.ModelForm):
    class Meta:
        model = WorkIncident
        fields = ['employee', 'type_incident', 'gravite', 'date_incident', 'lieu', 'machine',
                  'description', 'cause', 'temoins', 'jours_arret', 'blessure', 'soins_prodigues',
                  'actions_immediates', 'actions_correctives', 'rapport', 'photos']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'type_incident': forms.Select(attrs={'class': 'form-select'}),
            'gravite': forms.Select(attrs={'class': 'form-select'}),
            'date_incident': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'lieu': forms.TextInput(attrs={'class': 'form-control'}),
            'machine': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'cause': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'temoins': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'jours_arret': forms.NumberInput(attrs={'class': 'form-control'}),
            'blessure': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'soins_prodigues': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'actions_immediates': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'actions_correctives': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ProtectiveEquipmentForm(forms.ModelForm):
    class Meta:
        model = ProtectiveEquipment
        fields = ['employee', 'type_equipement', 'designation', 'date_attribution',
                  'date_expiration', 'quantite', 'taille', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'type_equipement': forms.Select(attrs={'class': 'form-select'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'date_attribution': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_expiration': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'taille': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }