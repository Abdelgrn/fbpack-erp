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
    # PRODUCTION (OF ANCIEN)
    # ==========================================
    path('production/list/', views.production_view, name='production_view'),
    path('production/add/', views.add_production, name='add_production'),
    path('production/edit/<int:id>/', views.edit_production, name='edit_production'),

    # ==========================================
    # OF MULTI-PROCESSUS (NOUVEAU)
    # ==========================================
    path('of/', views.of_list_view, name='of_list'),
    path('of/create/', views.of_create_view, name='of_create'),
    path('of/<int:of_id>/', views.of_detail_view, name='of_detail'),
    path('of/<int:of_id>/edit/', views.of_edit_view, name='of_edit'),
    path('of/<int:of_id>/delete/', views.of_delete_view, name='of_delete'),
    path('of/<int:of_id>/statut/<str:nouveau_statut>/', views.of_changer_statut, name='of_changer_statut'),
    path('of/lancement-rapide/', views.of_lancement_rapide, name='of_lancement_rapide'),
    path('of/api/stats/', views.of_stats_api, name='of_stats_api'),

    # ==========================================
    # ÉTAPES DE PRODUCTION
    # ==========================================
    path('of/etape/<int:etape_id>/', views.etape_detail_view, name='etape_detail'),
    path('of/etape/<int:etape_id>/demarrer/', views.etape_demarrer, name='etape_demarrer'),
    path('of/etape/<int:etape_id>/terminer/', views.etape_terminer, name='etape_terminer'),

    # ==========================================
    # SEMI-PRODUITS
    # ==========================================
    path('of/semi-produits/', views.semi_produit_list, name='semi_produit_list'),
    path('of/semi-produit/<int:sp_id>/', views.semi_produit_detail, name='semi_produit_detail'),

    # ==========================================
    # TYPES DE PROCESSUS
    # ==========================================
    path('of/process-types/', views.process_type_list, name='process_type_list'),
    path('of/process-type/<int:pt_id>/delete/', views.process_type_delete, name='process_type_delete'),

    # ==========================================
    # STOCKS, ACHATS & CONSO
    # ==========================================
    path('stock/list/', views.stock_view, name='stock_view'),
    path('stock/material/add/', views.add_material, name='add_material'),
    path('stock/supplier/add/', views.add_supplier, name='add_supplier'),
    path('stock/consommation/add/', views.add_consommation, name='add_consommation'),
    path('stock/consommation/list/', views.conso_list_view, name='conso_list'),
    
    # RECHERCHE INTELLIGENTE (CORRIGÉ)
    path('stock/search/api/', views.material_search_api, name='material_search_api'),
    path('stock/export/', views.export_search_results, name='export_search_results'),

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
    
    # ==========================================
    # MODULE PRODUCTION SPÉCIAL — ENCRE
    # ==========================================
    path('prod/encre/', views.encre_dashboard, name='encre_dashboard'),
    path('prod/encre/saisie/', views.encre_saisie, name='encre_saisie'),
    path('prod/encre/<int:id>/edit/', views.encre_edit, name='encre_edit'),
    path('prod/encre/<int:id>/delete/', views.encre_delete, name='encre_delete'),
    path('prod/encre/<int:id>/detail/', views.encre_detail, name='encre_detail'),
    path('prod/encre/analyse/', views.encre_analyse, name='encre_analyse'),
    
    # ==========================================
    # MODULE STOCK AVANCÉ
    # ==========================================
    path('stock/', views.stock_advanced_view, name='stock_advanced'),
    path('stock/location/add/', views.location_add, name='location_add'),
    path('stock/location/<int:id>/delete/', views.location_delete, name='location_delete'),
    path('stock/lot/add/', views.lot_add, name='lot_add'),
    path('stock/lot/<int:id>/', views.lot_detail, name='lot_detail'),
    path('stock/lot/<int:id>/valider/', views.lot_valider, name='lot_valider'),
    path('stock/lot/<int:id>/bloquer/', views.lot_bloquer, name='lot_bloquer'),
    path('stock/mouvement/add/', views.mouvement_add, name='mouvement_add'),
    path('stock/da/add/', views.da_add, name='da_add'),
    path('stock/da/<int:id>/valider/', views.da_valider, name='da_valider'),
    path('stock/da/<int:id>/refuser/', views.da_refuser, name='da_refuser'),
    path('stock/bc/add/', views.bc_add, name='bc_add'),
    path('stock/bc/<int:id>/envoyer/', views.bc_envoyer, name='bc_envoyer'),
    path('stock/bc/<int:id>/reception/', views.bc_reception, name='bc_reception'),
    path('stock/seuil/<int:material_id>/update/', views.seuil_update, name='seuil_update'),
    path('stock/api/dashboard/', views.stock_dashboard_data, name='stock_dashboard_data'),

    # ==========================================
    # ADMINISTRATION
    # ==========================================
    path('administration/', views.admin_view, name='admin_view'),
    path('administration/user/add/', views.admin_add_user, name='admin_add_user'),
    path('administration/user/<int:user_id>/edit/', views.admin_edit_user, name='admin_edit_user'),
    path('administration/user/<int:user_id>/toggle/', views.admin_toggle_user, name='admin_toggle_user'),
    
    # ==========================================python manage.py runserver
    # CHAT EN TEMPS RÉEL
    # ==========================================
    path('chat/', views.chat_home, name='chat_home'),
    path('chat/<slug:room_slug>/', views.chat_room, name='chat_room'),
    path('chat/api/send/', views.chat_send_message, name='chat_send_message'),
    path('chat/api/messages/<slug:room_slug>/', views.chat_get_messages, name='chat_get_messages'),
    path('chat/api/notify/', views.send_system_notification, name='send_system_notification'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)