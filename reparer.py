import os

# 1. CORRECTION settings.py (Ajout de DEFAULT_AUTO_FIELD pour les warnings)
settings_path = os.path.join("polypack_erp", "settings.py")
with open(settings_path, "a") as f: # "a" pour append (ajouter à la fin)
    f.write("\n# Correction Warnings\nDEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'\n")
print(f"✅ Settings corrigés : {settings_path}")

# 2. CORRECTION core/admin.py (Ajout de search_fields pour l'erreur bloquante)
admin_content = """
from django.contrib import admin
from django.utils.html import format_html
from .models import *

# --- CRM ---
class ContactInline(admin.TabularInline):
    model = ClientContact
    extra = 1

class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'status_badge', 'city', 'sector')
    list_filter = ('status', 'sector')
    search_fields = ('name', 'city')
    inlines = [ContactInline]
    
    def status_badge(self, obj):
        colors = {'PROSPECT': 'blue', 'ACTIVE': 'green', 'VIP': 'purple', 'LOST': 'red'}
        return format_html(f'<span style="color: {{colors.get(obj.status, "black")}}; font-weight:bold;">{{obj.get_status_display()}}</span>')

# --- STOCK ---
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'quantity', 'unit', 'stock_alert')
    list_filter = ('category', 'supplier')
    search_fields = ('name',)  # <--- C'EST LA LIGNE QUI MANQUAIT !
    
    def stock_alert(self, obj):
        if obj.is_low_stock():
            return format_html('<span style="color:red; font-weight:bold;">⚠️ BAS ({{}})</span>', obj.min_threshold)
        return "OK"

# --- PRODUCTION ---
class ConsumptionInline(admin.TabularInline):
    model = ConsumptionLog
    extra = 1
    autocomplete_fields = ['material']

class OFAdmin(admin.ModelAdmin):
    list_display = ('of_number', 'client', 'product', 'machine', 'start_time', 'status')
    list_filter = ('status', 'machine')
    search_fields = ('of_number', 'client__name')
    inlines = [ConsumptionInline]

# --- PREPRESSE ---
class ToolingAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'product', 'tool_type', 'wear_progress')
    
    def wear_progress(self, obj):
        percent = obj.wear_percent()
        color = 'green'
        if percent > 80: color = 'red'
        elif percent > 50: color = 'orange'
        return format_html(f'<div style="width:100px; background:#ddd; border-radius:4px;"><div style="width:{{percent}}%; background:{{color}}; height:10px; border-radius:4px;"></div></div> {{percent}}%')

# --- MACHINE ---
class MaintenanceInline(admin.TabularInline):
    model = MaintenanceSchedule
    extra = 1

class IncidentInline(admin.TabularInline):
    model = IncidentLog
    extra = 0

class MachineAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'status')
    inlines = [MaintenanceInline, IncidentInline]

admin.site.register(Client, ClientAdmin)
admin.site.register(TechnicalProduct)
admin.site.register(Tooling, ToolingAdmin)
admin.site.register(Material, MaterialAdmin)
admin.site.register(Supplier)
admin.site.register(Machine, MachineAdmin)
admin.site.register(ProductionOrder, OFAdmin)
admin.site.register(InteractionLog)
admin.site.register(PurchaseOrder)
"""

admin_path = os.path.join("core", "admin.py")
with open(admin_path, "w", encoding="utf-8") as f:
    f.write(admin_content.strip())
print(f"✅ Admin corrigé : {admin_path}")