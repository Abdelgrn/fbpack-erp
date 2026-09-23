from .imports_export import (
    import_stock_view, download_template_special_prod, download_template_stock
)

from .dashboard import (
    dashboard, production_gantt, reporting
)

from .crm import (
    crm_view, client_detail, add_client, edit_client, import_clients,
    add_contact, edit_contact, delete_contact, add_interaction,
    opportunites_view, add_opportunite, edit_opportunite, delete_opportunite,
    quotes_view, add_quote, edit_quote, convert_quote_to_order,
    convertir_prospect,
    commandes_list, commande_detail, add_commande, edit_commande,
    commande_changer_statut, commande_check_stock, commande_creer_of,
    demandes_prix_list, add_demande_prix, edit_demande_prix, demande_prix_vers_devis,
    api_check_material_stock, crm_of_list, crm_of_create, crm_of_detail,
    crm_of_edit, crm_of_changer_statut,
)

from .prepress import (
    prepress_view, add_product, edit_product, add_tool, edit_tool
)

from .production_of import (
    production_view, add_production, edit_production,
    of_list_view, of_create_view, of_detail_view, of_edit_view, of_delete_view,
    of_changer_statut, of_lancement_rapide, etape_detail_view,
    etape_demarrer, etape_terminer, semi_produit_list, semi_produit_detail,
    process_type_list, process_type_delete, of_stats_api
)

from .stock import (
    stock_view, add_material, edit_material, delete_material, clear_all_stock,
    add_supplier, edit_supplier, delete_supplier, add_consommation, conso_list_view,
    stock_advanced_view, material_search_api, export_search_results,
    location_list, location_add, location_delete, lot_list, lot_add,
    lot_valider, lot_bloquer, lot_detail, mouvement_add, da_add, da_valider, da_refuser,
    bc_add, bc_envoyer, bc_reception, seuil_update, stock_dashboard_data
)

from .machines import (
    machine_view, add_machine
)

from .production_speciale import (
    prod_dashboard, prod_saisie, prod_edit_entry, prod_delete_entry,
    prod_edit_fiche,
    prod_base, prod_detail_qualite, prod_synthese_temps,
    prod_calculer_temps, prod_calculer_temps_save, prod_calculer_temps_delete
)

from .encre import (
    encre_dashboard, encre_saisie, encre_edit, encre_delete, encre_detail, encre_analyse
)

from .admin_custom import (
    admin_view, admin_add_user, admin_edit_user, admin_toggle_user, admin_import_data_view,
    admin_restore_backup_view, export_database_backup, manifest_view
)

from .drh import (
    drh_dashboard, employee_list, employee_detail, employee_create, employee_edit,
    employee_document_add, skill_list, employee_skill_add, machine_authorization_add,
    machine_authorization_validate, attendance_list, attendance_create, attendance_bulk,
    leave_list, leave_create, leave_validate_n1, leave_validate_rh, leave_reject,
    payslip_list, payslip_create, payslip_detail, payslip_calculate, payslip_validate,
    payslip_bulk_generate, schedule_list, schedule_detail, shift_assignment_add,
    incident_list, incident_create, incident_detail, medical_visit_list,
    medical_visit_create, epi_list, epi_create, department_list, position_list,
    shift_list, export_employees_excel, export_payslips_excel
)

from .chat import (
    chat_home, chat_room, chat_send_message, chat_get_messages, send_system_notification, chat_private_init, chat_notifications_api
)

from .maintenance import (
    maintenance_dashboard, atelier_list, atelier_create, maintenance_machine_list,
    maintenance_machine_create, maintenance_machine_detail, maintenance_machine_edit,
    maintenance_machine_delete, machine_compteur_add, om_list, om_create,
    om_create_panne, om_detail, om_demarrer, om_cloturer, om_ajouter_piece,
    plan_preventif_list, plan_preventif_create, plan_preventif_detail,
    plan_preventif_generer_om, generer_om_preventifs_auto, piece_list, piece_create,
    piece_detail, piece_edit, piece_mouvement, categorie_piece_list, alerte_list,
    alerte_traiter, generer_alertes, maintenance_kpi, maintenance_stats_api, maintenance_calendrier
)