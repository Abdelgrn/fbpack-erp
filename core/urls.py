from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # ==========================================
    # DASHBOARD & REPORTING
    # ==========================================
    path('', views.dashboard, name='dashboard'),
    path('production/planning/', views.production_gantt, name='planning'),
    path('reporting/', views.reporting, name='reporting'),
    path('stock/import/', views.import_stock_view, name='import_stock'),

    # ==========================================
    # CRM — CLIENTS
    # ==========================================
    path('crm/', views.crm_view, name='crm_view'),
    path('crm/client/add/', views.add_client, name='add_client'),
    path('crm/client/<int:id>/', views.client_detail, name='client_detail'),
    path('crm/client/<int:id>/edit/', views.edit_client, name='edit_client'),

    # ==========================================
    # CRM — CONTACTS
    # ==========================================
    path('crm/client/<int:client_id>/contact/add/', views.add_contact, name='add_contact'),
    path('crm/contact/<int:id>/edit/', views.edit_contact, name='edit_contact'),
    path('crm/contact/<int:id>/delete/', views.delete_contact, name='delete_contact'),

    # ==========================================
    # CRM — INTERACTIONS / JOURNAL
    # ==========================================
    path('crm/client/<int:client_id>/interaction/add/', views.add_interaction, name='add_interaction'),

    # ==========================================
    # CRM — OPPORTUNITÉS & PIPELINE
    # ==========================================
    path('crm/opportunites/', views.opportunites_view, name='opportunites_view'),
    path('crm/opportunite/add/', views.add_opportunite, name='add_opportunite'),
    path('crm/opportunite/<int:id>/edit/', views.edit_opportunite, name='edit_opportunite'),
    path('crm/opportunite/<int:id>/delete/', views.delete_opportunite, name='delete_opportunite'),

    # ==========================================
    # CRM — DEVIS
    # ==========================================
    path('crm/devis/', views.quotes_view, name='quotes_view'),
    path('crm/devis/add/', views.add_quote, name='add_quote'),
    path('crm/devis/<int:id>/edit/', views.edit_quote, name='edit_quote'),
    path('crm/devis/<int:id>/convert/', views.convert_quote_to_order, name='convert_quote'),

    # ==========================================
    # PRÉPRESSE & OUTILS
    # ==========================================
    path('prepress/', views.prepress_view, name='prepress_view'),
    path('prepress/add/', views.add_product, name='add_product'),
    path('prepress/edit/<int:id>/', views.edit_product, name='edit_product'),
    path('tools/add/', views.add_tool, name='add_tool'),
    path('tools/edit/<int:id>/', views.edit_tool, name='edit_tool'),

    # ==========================================
    # PRODUCTION (OF)
    # ==========================================
    path('production/list/', views.production_view, name='production_view'),
    path('production/add/', views.add_production, name='add_production'),
    path('production/edit/<int:id>/', views.edit_production, name='edit_production'),

    # ==========================================
    # STOCKS, ACHATS & CONSO
    # ==========================================
    path('stock/list/', views.stock_view, name='stock_view'),
    path('stock/material/add/', views.add_material, name='add_material'),
    path('stock/supplier/add/', views.add_supplier, name='add_supplier'),
    path('stock/consommation/add/', views.add_consommation, name='add_consommation'),
    path('stock/consommation/list/', views.conso_list_view, name='conso_list'),

    # ==========================================
    # PARC MACHINE
    # ==========================================
    path('machines/', views.machine_view, name='machine_view'),
    path('machines/add/', views.add_machine, name='add_machine'),

    # ==========================================
    # MODULE PRODUCTION SPÉCIAL
    # ==========================================
    path('prod/', views.prod_dashboard, name='prod_dashboard'),
    path('prod/saisie/', views.prod_saisie, name='prod_saisie'),
    path('prod/saisie/edit/<int:id>/', views.prod_edit_entry, name='prod_edit_entry'),
    path('prod/saisie/delete/<int:id>/', views.prod_delete_entry, name='prod_delete_entry'),
    path('prod/base/', views.prod_base, name='prod_base'),
    path('prod/qualite/', views.prod_detail_qualite, name='prod_detail_qualite'),
    path('prod/synthese/', views.prod_synthese_temps, name='prod_synthese_temps'),
    path('import/template-special-prod/', views.download_template_special_prod, name='download_template_special_prod'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
