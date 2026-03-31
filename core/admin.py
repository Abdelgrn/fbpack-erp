from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Client, ClientContact, InteractionLog, Opportunite,
    TechnicalProduct, Tooling,
    Material, Supplier,
    Machine, MaintenanceSchedule, IncidentLog,
    ProductionOrder, ConsumptionLog, PurchaseOrder,
    Quote, ConsommationEncre, ProductionEntry
)


# ===========================================================================
# --- CRM ---
# ===========================================================================

class ContactInline(admin.TabularInline):
    model = ClientContact
    extra = 1
    fields = ['name', 'role', 'role_custom', 'phone', 'email', 'is_primary']


class InteractionInline(admin.TabularInline):
    model = InteractionLog
    extra = 0
    fields = ['date', 'type', 'summary', 'next_action']
    ordering = ['-date']


class OpportuniteInline(admin.TabularInline):
    model = Opportunite
    extra = 0
    fields = ['titre', 'status', 'valeur_estimee', 'probabilite', 'date_cloture_prevue']
    ordering = ['-date_ouverture']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'code_client', 'status_badge', 'segment', 'region', 'city', 'commercial', 'nb_contacts', 'nb_opps')
    list_filter = ('status', 'segment', 'region', 'size')
    search_fields = ('name', 'city', 'code_client')
    inlines = [ContactInline, OpportuniteInline, InteractionInline]

    def status_badge(self, obj):
        colors = {
            'PROSPECT': '#3B82F6',
            'ACTIVE': '#22C55E',
            'VIP': '#A855F7',
            'LOST': '#EF4444',
        }
        color = colors.get(obj.status, '#6B7280')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Statut"

    def nb_contacts(self, obj):
        return obj.clientcontact_set.count()
    nb_contacts.short_description = "Contacts"

    def nb_opps(self, obj):
        return obj.opportunite_set.count()
    nb_opps.short_description = "Opportunités"


@admin.register(ClientContact)
class ClientContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'client', 'role', 'phone', 'email', 'is_primary')
    list_filter = ('role', 'is_primary')
    search_fields = ('name', 'client__name', 'email')


@admin.register(InteractionLog)
class InteractionLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'client', 'type', 'summary', 'commercial')
    list_filter = ('type', 'date')
    search_fields = ('client__name', 'summary')
    ordering = ['-date']


@admin.register(Opportunite)
class OpportuniteAdmin(admin.ModelAdmin):
    list_display = ('titre', 'client', 'status_badge', 'valeur_estimee', 'probabilite', 'commercial', 'date_cloture_prevue')
    list_filter = ('status',)
    search_fields = ('titre', 'client__name')
    ordering = ['-date_ouverture']

    def status_badge(self, obj):
        colors = {
            'PROSPECT': '#3B82F6',
            'QUALIFICATION': '#6366F1',
            'PROPOSITION': '#EAB308',
            'NEGOCIATION': '#F97316',
            'GAGNE': '#22C55E',
            'PERDU': '#EF4444',
        }
        color = colors.get(obj.status, '#6B7280')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Étape"


# ===========================================================================
# --- DEVIS ---
# ===========================================================================

@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ('reference', 'version', 'client', 'total_amount', 'status', 'date', 'date_validite', 'commande_creee')
    list_filter = ('status', 'commande_creee')
    search_fields = ('reference', 'client__name')
    ordering = ['-date']


# ===========================================================================
# --- STOCK ---
# ===========================================================================

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity', 'unit', 'stock_alert', 'supplier')
    list_filter = ('category', 'supplier')
    search_fields = ('name',)

    def stock_alert(self, obj):
        if obj.is_low_stock():
            return format_html('<span style="color: red; font-weight: bold;">⚠️ BAS ({})</span>', obj.min_threshold)
        return "✅ OK"
    stock_alert.short_description = "Alerte"


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'email')
    search_fields = ('name',)


# ===========================================================================
# --- PRODUCTION ---
# ===========================================================================

class ConsumptionInline(admin.TabularInline):
    model = ConsumptionLog
    extra = 1
    autocomplete_fields = ['material']


@admin.register(ProductionOrder)
class OFAdmin(admin.ModelAdmin):
    list_display = ('of_number', 'client', 'product', 'machine', 'start_time', 'status')
    list_filter = ('status', 'machine')
    search_fields = ('of_number', 'client__name')
    inlines = [ConsumptionInline]


# ===========================================================================
# --- PRÉPRESSE ---
# ===========================================================================

@admin.register(TechnicalProduct)
class TechnicalProductAdmin(admin.ModelAdmin):
    list_display = ('ref_internal', 'name', 'client', 'structure_type', 'width_mm', 'num_colors')
    list_filter = ('structure_type',)
    search_fields = ('ref_internal', 'name', 'client__name')


@admin.register(Tooling)
class ToolingAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'product', 'tool_type', 'wear_progress')

    def wear_progress(self, obj):
        percent = obj.wear_percent()
        color = 'green'
        if percent > 80:
            color = 'red'
        elif percent > 50:
            color = 'orange'
        return format_html(
            '<div style="width:100px; background:#334155; border-radius:4px;">'
            '<div style="width:{}%; background:{}; height:10px; border-radius:4px;"></div>'
            '</div> {}%',
            percent, color, percent
        )
    wear_progress.short_description = "Usure"


# ===========================================================================
# --- MACHINES ---
# ===========================================================================

class MaintenanceInline(admin.TabularInline):
    model = MaintenanceSchedule
    extra = 1


class IncidentInline(admin.TabularInline):
    model = IncidentLog
    extra = 0


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'status')
    inlines = [MaintenanceInline, IncidentInline]


# ===========================================================================
# --- CONSOMMATION ENCRES ---
# ===========================================================================

@admin.register(ConsommationEncre)
class ConsommationEncreAdmin(admin.ModelAdmin):
    list_display = (
        'job_name', 'date', 'process_type', 'support',
        'total_encre_display', 'total_solvant_display',
        'gain_de_masse_kg', 'grammage_display'
    )
    list_filter = ('process_type', 'date', 'support')
    search_fields = ('job_name', 'support')

    def total_encre_display(self, obj):
        return f"{obj.total_encre} kg"
    total_encre_display.short_description = "Total Encre"

    def total_solvant_display(self, obj):
        return f"{obj.total_solvant} kg"
    total_solvant_display.short_description = "Total Solvant"

    def grammage_display(self, obj):
        return f"{obj.grammage} g/m²"
    grammage_display.short_description = "Grammage Sec"


# ===========================================================================
# --- PRODUCTION SPÉCIALE ---
# ===========================================================================

@admin.register(ProductionEntry)
class ProductionEntryAdmin(admin.ModelAdmin):
    list_display = ['date', 'produit', 'support', 'equipe', 'machine', 'prod_ml', 'prod_kg', 'total_dechets_kg', 'taux_dechets']
    list_filter = ['date', 'equipe', 'support', 'machine']
    search_fields = ['produit', 'support', 'lot']
    ordering = ['-date']


# ===========================================================================
# --- BONS DE COMMANDE ---
# ===========================================================================

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'date', 'status', 'total_amount')
    list_filter = ('status',)
