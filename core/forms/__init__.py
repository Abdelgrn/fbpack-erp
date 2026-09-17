# CRM
from .crm import (
    ClientForm, ClientContactForm, InteractionLogForm, OpportuniteForm, QuoteForm,
    CommandeClientForm, LigneCommandeClientForm, LigneCommandeClientFormSet,
    DemandePrixForm,
)

# Prepress
from .prepress import ProductForm, ToolForm

# Stock
from .stock import SupplierForm, MaterialForm

# Machines
from .machines import MachineForm, MachineMaintenanceForm, CompteurMachineForm, AtelierForm

# Production OF
from .production_of import (
    OrdreFabricationForm, EtapeProductionForm, EtapeProductionFormSet,
    PlanificationEtapeFormSet,
    SuiviProductionForm, SemiProduitForm, ConsommationMatiereForm,
    ProcessTypeForm, OFLancementRapideForm
)

# Production Spéciale
from .production_speciale import (
    ProductionEntryForm, CalculTempsProductionForm, ProductionOrderForm
)

# Encre
from .encre import ConsommationEncreForm

# Fiches
from .fiches import (
    FicheProductionJournaliereForm, FicheExtrusionMatiereFormSet, FicheExtrusionArretFormSet,
    FicheFlexoBobineEntreeFormSet, FicheFlexoBobineImprimeeFormSet, FicheFlexoEncreGroupeFormSet,
    FicheComplexageDerouleur1FormSet, FicheComplexageDerouleur2FormSet, FicheComplexageEnrouleurFormSet,
    FicheFondCarreEquipeFormSet, FicheDecoupeBobineMereFormSet, FicheDecoupeBobineFilleFormSet,
    FicheDecoupeArretFormSet, FicheDecoupeControleForm
)

# Maintenance
from .maintenance import (
    CategoriePieceForm, PieceRechangeForm, OrdreMaintenanceForm,
    ClotureOrdreMaintenanceForm, ConsommationPieceForm,
    PlanMaintenancePreventiveForm, MouvementPieceForm
)

# DRH
from .drh import (
    DepartmentForm, PositionForm, EmployeeForm, EmployeeDocumentForm,
    SkillForm, EmployeeSkillForm, MachineAuthorizationForm, ShiftForm,
    AttendanceForm, AttendanceBulkForm, LeaveTypeForm, LeaveRequestForm,
    PayslipForm, WorkScheduleForm, ShiftAssignmentForm, MedicalVisitForm,
    WorkIncidentForm, ProtectiveEquipmentForm
)

__all__ = [
    # CRM
    "ClientForm", "ClientContactForm", "InteractionLogForm", "OpportuniteForm", "QuoteForm",
    "CommandeClientForm", "LigneCommandeClientForm", "LigneCommandeClientFormSet",
    "DemandePrixForm",
    # Prepress
    "ProductForm", "ToolForm",
    # Stock
    "SupplierForm", "MaterialForm",
    # Machines
    "MachineForm", "MachineMaintenanceForm", "CompteurMachineForm", "AtelierForm",
    # Production OF
    "OrdreFabricationForm", "EtapeProductionForm", "EtapeProductionFormSet",
    "PlanificationEtapeFormSet",
    "SuiviProductionForm", "SemiProduitForm", "ConsommationMatiereForm",
    "ProcessTypeForm", "OFLancementRapideForm",
    # Production Spéciale
    "ProductionEntryForm", "CalculTempsProductionForm", "ProductionOrderForm",
    # Encre
    "ConsommationEncreForm",
    # Fiches
    "FicheProductionJournaliereForm", "FicheExtrusionMatiereFormSet", "FicheExtrusionArretFormSet",
    "FicheFlexoBobineEntreeFormSet", "FicheFlexoBobineImprimeeFormSet", "FicheFlexoEncreGroupeFormSet",
    "FicheComplexageDerouleur1FormSet", "FicheComplexageDerouleur2FormSet", "FicheComplexageEnrouleurFormSet",
    "FicheFondCarreEquipeFormSet", "FicheDecoupeBobineMereFormSet", "FicheDecoupeBobineFilleFormSet",
    "FicheDecoupeArretFormSet", "FicheDecoupeControleForm",
    # Maintenance
    "CategoriePieceForm", "PieceRechangeForm", "OrdreMaintenanceForm",
    "ClotureOrdreMaintenanceForm", "ConsommationPieceForm",
    "PlanMaintenancePreventiveForm", "MouvementPieceForm",
    # DRH
    "DepartmentForm", "PositionForm", "EmployeeForm", "EmployeeDocumentForm",
    "SkillForm", "EmployeeSkillForm", "MachineAuthorizationForm", "ShiftForm",
    "AttendanceForm", "AttendanceBulkForm", "LeaveTypeForm", "LeaveRequestForm",
    "PayslipForm", "WorkScheduleForm", "ShiftAssignmentForm", "MedicalVisitForm",
    "WorkIncidentForm", "ProtectiveEquipmentForm",
]