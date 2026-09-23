from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views
from .views import of_views
from .views import production_speciale as prod_views
from .views.stock import scan_label_ai  # <-- IMPORT DIRECT SÉCURISÉ

urlpatterns = [
    # ==========================================
    # MANIFEST PWA DYNAMIQUE (LOGO AUTOMATIQUE)
    # ==========================================
    path('manifest.json', views.manifest_view, name='manifest_view'),

    # ==========================================
    # DASHBOARD & REPORTING
    # ==========================================
    path('', views.dashboard, name='dashboard'),
    path('reporting/', views.reporting, name='reporting'),
    path('stock/import/', views.import_stock_view, name='import_stock'),

    # ==========================================
    # CRM — CLIENTS
    # ==========================================
    path('crm/', views.crm_view, name='crm_view'),
    path('crm/client/add/', views.add_client, name='add_client'),
    path('crm/client/<int:id>/', views.client_detail, name='client_detail'),
    path('crm/client/<int:id>/edit/', views.edit_client, name='edit_client'),
    path('crm/client/<int:id>/convertir/', views.convertir_prospect, name='convertir_prospect'),

    # ==========================================
    # CRM — CONTACTS
    # ==========================================
    path('crm/client/<int:client_id>/contact/add/', views.add_contact, name='add_contact'),
    path('crm/contact/<int:id>/edit/', views.edit_contact, name='edit_contact'),
    path('crm/contact/<int:id>/delete/', views.delete_contact, name='delete_contact'),

    # ==========================================
    # CRM — INTERACTIONS
    # ==========================================
    path('crm/client/<int:client_id>/interaction/add/', views.add_interaction, name='add_interaction'),

    # ==========================================
    # CRM — OPPORTUNITÉS
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
    # CRM — COMMANDES CLIENTS
    # ==========================================
    path('crm/commandes/', views.commandes_list, name='commandes_list'),
    path('crm/commande/add/', views.add_commande, name='add_commande'),
    path('crm/commande/<int:id>/', views.commande_detail, name='commande_detail'),
    path('crm/commande/<int:id>/edit/', views.edit_commande, name='edit_commande'),
    path('crm/commande/<int:id>/statut/<str:nouveau_statut>/', views.commande_changer_statut, name='commande_changer_statut'),
    path('crm/commande/<int:id>/stock/', views.commande_check_stock, name='commande_check_stock'),
    path('crm/commande/<int:id>/creer-of/', views.commande_creer_of, name='commande_creer_of'),

    # ==========================================
    # CRM — DEMANDES DE PRIX
    # ==========================================
    path('crm/demandes-prix/', views.demandes_prix_list, name='demandes_prix_list'),
    path('crm/demande-prix/add/', views.add_demande_prix, name='add_demande_prix'),
    path('crm/demande-prix/<int:id>/edit/', views.edit_demande_prix, name='edit_demande_prix'),
    path('crm/demande-prix/<int:id>/vers-devis/', views.demande_prix_vers_devis, name='demande_prix_vers_devis'),

    # ==========================================
    # CRM — OF INTÉGRÉ
    # ==========================================
    path('crm/of/', views.crm_of_list, name='crm_of_list'),
    path('crm/of/create/', views.crm_of_create, name='crm_of_create'),
    path('crm/of/<int:of_id>/', views.crm_of_detail, name='crm_of_detail'),
    path('crm/of/<int:of_id>/edit/', views.crm_of_edit, name='crm_of_edit'),
    path('crm/of/<int:of_id>/statut/<str:nouveau_statut>/', views.crm_of_changer_statut, name='crm_of_changer_statut'),
    path('crm/api/stock-check/', views.api_check_material_stock, name='api_check_material_stock'),

    # ==========================================
    # MODULE PLANIFICATION & ORDONNANCEMENT
    # ==========================================
    path('planification/', of_views.planning_atelier_view, name='planning_atelier'),
    path('planification/backlog/', of_views.of_list_view, name='of_list'),
    path('planification/gantt/', of_views.production_gantt, name='planning'),
    path('planification/ordonnancer/<int:of_id>/', of_views.planification_ordonnancer, name='planification_ordonnancer'),
    path('planification/export-excel/', of_views.export_planning_excel, name='export_planning_excel'),

    # Alias de compatibilité
    path('crm/of/alias-list/', views.crm_of_list, name='of_list_alias'),
    path('crm/of/alias-create/', views.crm_of_create, name='of_create'),
    path('crm/of/alias-<int:of_id>/', views.crm_of_detail, name='of_detail'),
    path('crm/of/alias-<int:of_id>/edit/', views.crm_of_edit, name='of_edit'),
    path('crm/of/alias-<int:of_id>/statut/<str:nouveau_statut>/', views.crm_of_changer_statut, name='of_changer_statut'),

    # ==========================================
    # PRÉPRESSE & OUTILS
    # ==========================================
    path('prepress/', views.prepress_view, name='prepress_view'),
    path('prepress/add/', views.add_product, name='add_product'),
    path('prepress/edit/<int:id>/', views.edit_product, name='edit_product'),
    path('tools/add/', views.add_tool, name='add_tool'),
    path('tools/edit/<int:id>/', views.edit_tool, name='edit_tool'),

    # ==========================================
    # PRODUCTION (ANCIEN OF)
    # ==========================================
    path('production/list/', views.production_view, name='production_view'),
    path('production/add/', views.add_production, name='add_production'),
    path('production/edit/<int:id>/', views.edit_production, name='edit_production'),

    # ==========================================
    # OF MULTI-PROCESSUS TECHNIQUE ATELIER
    # ==========================================
    path('of/lancement-rapide/', of_views.of_lancement_rapide, name='of_lancement_rapide'),
    path('of/api/stats/', of_views.of_stats_api, name='of_stats_api'),

    # ==========================================
    # ÉTAPES DE PRODUCTION
    # ==========================================
    path('of/etape/<int:etape_id>/', of_views.etape_detail_view, name='etape_detail'),
    path('of/etape/<int:etape_id>/demarrer/', of_views.etape_demarrer, name='etape_demarrer'),
    path('of/etape/<int:etape_id>/terminer/', of_views.etape_terminer, name='etape_terminer'),

    # ==========================================
    # SEMI-PRODUITS
    # ==========================================
    path('of/semi-produits/', of_views.semi_produit_list, name='semi_produit_list'),
    path('of/semi-produit/<int:sp_id>/', of_views.semi_produit_detail, name='semi_produit_detail'),

    # ==========================================
    # TYPES DE PROCESSUS
    # ==========================================
    path('of/process-types/', of_views.process_type_list, name='process_type_list'),
    path('of/process-type/<int:pt_id>/delete/', of_views.process_type_delete, name='process_type_delete'),

    # ==========================================
    # STOCKS & ACHATS
    # ==========================================
    path('stock/list/', views.stock_view, name='stock_view'),
    path('stock/material/add/', views.add_material, name='add_material'),
    path('stock/supplier/add/', views.add_supplier, name='add_supplier'),
    path('stock/supplier/<int:id>/edit/', views.edit_supplier, name='edit_supplier'),
    path('stock/supplier/<int:id>/delete/', views.delete_supplier, name='delete_supplier'),
    path('stock/consommation/add/', views.add_consommation, name='add_consommation'),
    path('stock/consommation/list/', views.conso_list_view, name='conso_list'),
    path('stock/material/<int:id>/edit/', views.edit_material, name='edit_material'),
    path('stock/material/<int:id>/delete/', views.delete_material, name='delete_material'),
    path('stock/search/api/', views.material_search_api, name='material_search_api'),
    path('stock/export/', views.export_search_results, name='export_search_results'),
    
    # --- API SCANNER IA (NOUVEAU) ---
    path('stock/api/scan-label/', scan_label_ai, name='scan_label_ai'),

    # ==========================================
    # STOCK AVANCÉ
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
    # PARC MACHINE
    # ==========================================
    path('machines/', views.machine_view, name='machine_view'),
    path('machines/add/', views.add_machine, name='add_machine'),

    # ==========================================
    # MODULE PRODUCTION SPÉCIAL
    # ==========================================
    path('prod/', prod_views.prod_dashboard, name='prod_dashboard'),
    path('prod/saisie/', prod_views.prod_saisie, name='prod_saisie'),
    path('prod/saisie/legacy/', prod_views.prod_saisie_legacy, name='prod_saisie_legacy'),
    path('prod/fiche/<int:id>/print/', prod_views.prod_print_fiche, name='prod_print_fiche'),
    path('prod/fiche/<int:id>/delete/', prod_views.prod_delete_fiche, name='prod_delete_fiche'),
    path('prod/fiche/<int:id>/edit/', views.prod_edit_fiche, name='prod_edit_fiche'),
    path('prod/saisie/edit/<int:id>/', prod_views.prod_edit_entry, name='prod_edit_entry'),
    path('prod/saisie/delete/<int:id>/', prod_views.prod_delete_entry, name='prod_delete_entry'),
    path('prod/base/', prod_views.prod_base, name='prod_base'),
    path('prod/qualite/', prod_views.prod_detail_qualite, name='prod_detail_qualite'),
    path('prod/synthese/', prod_views.prod_synthese_temps, name='prod_synthese_temps'),
    
    path('prod/qualite/export/', prod_views.export_qualite_excel, name='export_qualite_excel'),
    path('prod/synthese/export/', prod_views.export_synthese_excel, name='export_synthese_excel'),
    
    path('prod/tracabilite/', prod_views.prod_tracabilite_lot, name='prod_tracabilite_search'),
    path('prod/tracabilite/<str:numero_lot>/', prod_views.prod_tracabilite_lot, name='prod_tracabilite_lot'),
    
    path('prod/synthese/calculer/', prod_views.prod_calculer_temps, name='prod_calculer_temps'),
    path('prod/synthese/calculer/save/', prod_views.prod_calculer_temps_save, name='prod_calculer_temps_save'),
    path('prod/synthese/calculer/<int:id>/delete/', prod_views.prod_calculer_temps_delete, name='prod_calculer_temps_delete'),
    path('import/template-special-prod/', views.download_template_special_prod, name='download_template_special_prod'),

    # ==========================================
    # MODULE ENCRE
    # ==========================================
    path('prod/encre/', views.encre_dashboard, name='encre_dashboard'),
    path('prod/encre/saisie/', views.encre_saisie, name='encre_saisie'),
    path('prod/encre/<int:id>/edit/', views.encre_edit, name='encre_edit'),
    path('prod/encre/<int:id>/delete/', views.encre_delete, name='encre_delete'),
    path('prod/encre/<int:id>/detail/', views.encre_detail, name='encre_detail'),
    path('prod/encre/analyse/', views.encre_analyse, name='encre_analyse'),

    # ==========================================
    # ADMINISTRATION & BACKUP
    # ==========================================
    path('administration/', views.admin_view, name='admin_view'),
    path('administration/user/add/', views.admin_add_user, name='admin_add_user'),
    path('administration/user/<int:user_id>/edit/', views.admin_edit_user, name='admin_edit_user'),
    path('administration/user/<int:user_id>/toggle/', views.admin_toggle_user, name='admin_toggle_user'),
    path('administration/import-data/', views.admin_import_data_view, name='admin_import_data'),
    path('administration/backup/restore/', views.admin_restore_backup_view, name='admin_restore_backup'),
    path('administration/backup/download/', views.export_database_backup, name='admin_export_backup'),

    # ==========================================
    # MODULE DRH
    # ==========================================
    path('drh/', views.drh_dashboard, name='drh_dashboard'),
    path('drh/employees/', views.employee_list, name='employee_list'),
    path('drh/employee/create/', views.employee_create, name='employee_create'),
    path('drh/employee/<int:emp_id>/', views.employee_detail, name='employee_detail'),
    path('drh/employee/<int:emp_id>/edit/', views.employee_edit, name='employee_edit'),
    path('drh/employee/<int:emp_id>/document/add/', views.employee_document_add, name='employee_document_add'),
    path('drh/skills/', views.skill_list, name='skill_list'),
    path('drh/employee/<int:emp_id>/skill/add/', views.employee_skill_add, name='employee_skill_add'),
    path('drh/employee/<int:emp_id>/authorization/add/', views.machine_authorization_add, name='machine_authorization_add'),
    path('drh/authorization/<int:auth_id>/validate/', views.machine_authorization_validate, name='machine_authorization_validate'),
    path('drh/attendance/', views.attendance_list, name='attendance_list'),
    path('drh/attendance/create/', views.attendance_create, name='attendance_create'),
    path('drh/attendance/bulk/', views.attendance_bulk, name='attendance_bulk'),
    path('drh/leaves/', views.leave_list, name='leave_list'),
    path('drh/leave/create/', views.leave_create, name='leave_create'),
    path('drh/leave/create/<int:emp_id>/', views.leave_create, name='leave_create_emp'),
    path('drh/leave/<int:leave_id>/validate-n1/', views.leave_validate_n1, name='leave_validate_n1'),
    path('drh/leave/<int:leave_id>/validate-rh/', views.leave_validate_rh, name='leave_validate_rh'),
    path('drh/leave/<int:leave_id>/reject/', views.leave_reject, name='leave_reject'),
    path('drh/payslips/', views.payslip_list, name='payslip_list'),
    path('drh/payslip/create/', views.payslip_create, name='payslip_create'),
    path('drh/payslip/<int:slip_id>/', views.payslip_detail, name='payslip_detail'),
    path('drh/payslip/<int:slip_id>/calculate/', views.payslip_calculate, name='payslip_calculate'),
    path('drh/payslip/<int:slip_id>/validate/', views.payslip_validate, name='payslip_validate'),
    path('drh/payslips/generate/', views.payslip_bulk_generate, name='payslip_bulk_generate'),
    path('drh/schedules/', views.schedule_list, name='schedule_list'),
    path('drh/schedule/<int:schedule_id>/', views.schedule_detail, name='schedule_detail'),
    path('drh/schedule/<int:schedule_id>/assign/', views.shift_assignment_add, name='shift_assignment_add'),
    path('drh/incidents/', views.incident_list, name='incident_list'),
    path('drh/incident/create/', views.incident_create, name='incident_create'),
    path('drh/incident/<int:incident_id>/', views.incident_detail, name='incident_detail'),
    path('drh/medical/', views.medical_visit_list, name='medical_list'),
    path('drh/medical/create/', views.medical_visit_create, name='medical_create'),
    path('drh/epi/', views.epi_list, name='epi_list'),
    path('drh/epi/create/', views.epi_create, name='epi_create'),
    path('drh/departments/', views.department_list, name='department_list'),
    path('drh/positions/', views.position_list, name='position_list'),
    path('drh/shifts/', views.shift_list, name='shift_list'),
    path('drh/export/employees/', views.export_employees_excel, name='export_employees'),
    path('drh/export/payslips/', views.export_payslips_excel, name='export_payslips'),

    # ==========================================
    # CHAT
    # ==========================================
    path('chat/', views.chat_home, name='chat_home'),
    path('chat/<slug:room_slug>/', views.chat_room, name='chat_room'),
    path('chat/private/<int:user_id>/', views.chat_private_init, name='chat_private_init'),
    path('chat/api/send/', views.chat_send_message, name='chat_send_message'),
    path('chat/api/messages/<slug:room_slug>/', views.chat_get_messages, name='chat_get_messages'),
    path('chat/api/notify/', views.send_system_notification, name='send_system_notification'),
    path('chat/api/notifications/', views.chat_notifications_api, name='chat_notifications_api'),

    # ==========================================
    # MAINTENANCE AVANCÉE
    # ==========================================
    path('maintenance/', views.maintenance_dashboard, name='maintenance_dashboard'),
    path('maintenance/ateliers/', views.atelier_list, name='atelier_list'),
    path('maintenance/atelier/create/', views.atelier_create, name='atelier_create'),
    path('maintenance/machines/', views.maintenance_machine_list, name='maintenance_machine_list'),
    path('maintenance/machine/create/', views.maintenance_machine_create, name='maintenance_machine_create'),
    path('maintenance/machine/<int:machine_id>/', views.maintenance_machine_detail, name='maintenance_machine_detail'),
    path('maintenance/machine/<int:machine_id>/edit/', views.maintenance_machine_edit, name='maintenance_machine_edit'),
    path('maintenance/machine/<int:machine_id>/compteur/', views.machine_compteur_add, name='machine_compteur_add'),
    path('maintenance/om/', views.om_list, name='om_list'),
    path('maintenance/om/create/', views.om_create, name='om_create'),
    path('maintenance/om/create/panne/<int:machine_id>/', views.om_create_panne, name='om_create_panne'),
    path('maintenance/om/<int:om_id>/', views.om_detail, name='om_detail'),
    path('maintenance/om/<int:om_id>/demarrer/', views.om_demarrer, name='om_demarrer'),
    path('maintenance/om/<int:om_id>/cloturer/', views.om_cloturer, name='om_cloturer'),
    path('maintenance/om/<int:om_id>/piece/add/', views.om_ajouter_piece, name='om_ajouter_piece'),
    path('maintenance/preventif/', views.plan_preventif_list, name='plan_preventif_list'),
    path('maintenance/preventif/create/', views.plan_preventif_create, name='plan_preventif_create'),
    path('maintenance/preventif/<int:plan_id>/', views.plan_preventif_detail, name='plan_preventif_detail'),
    path('maintenance/preventif/<int:plan_id>/generer/', views.plan_preventif_generer_om, name='plan_preventif_generer_om'),
    path('maintenance/preventif/generer-auto/', views.generer_om_preventifs_auto, name='generer_om_preventifs_auto'),
    path('maintenance/pieces/', views.piece_list, name='piece_list'),
    path('maintenance/piece/create/', views.piece_create, name='piece_create'),
    path('maintenance/piece/<int:piece_id>/', views.piece_detail, name='piece_detail'),
    path('maintenance/piece/<int:piece_id>/edit/', views.piece_edit, name='piece_edit'),
    path('maintenance/piece/<int:piece_id>/mouvement/', views.piece_mouvement, name='piece_mouvement'),
    path('maintenance/categories-pieces/', views.categorie_piece_list, name='categorie_piece_list'),
    path('maintenance/alertes/', views.alerte_list, name='alerte_list'),
    path('maintenance/alerte/<int:alerte_id>/traiter/', views.alerte_traiter, name='alerte_traiter'),
    path('maintenance/generer-alertes/', views.generer_alertes, name='generer_alertes'),
    path('maintenance/kpi/', views.maintenance_kpi, name='maintenance_kpi'),
    path('maintenance/api/stats/', views.maintenance_stats_api, name='maintenance_stats_api'),
    path('maintenance/machine/<int:machine_id>/delete/', views.maintenance_machine_delete, name='maintenance_machine_delete'),
    path('maintenance/calendrier/', views.maintenance_calendrier, name='maintenance_calendrier'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)