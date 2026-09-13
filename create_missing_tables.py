import sqlite3
import os

# Chemin vers la base de données
DB_PATH = r"C:\Users\User\Desktop\ABDELILEH\FB PACK\logiciel\3 03 2029\fbpack_erp beta - Copie\db.sqlite3"

# Connexion à la base
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("🔧 Création des tables manquantes...")

try:
    # 1. Atelier
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "core_atelier" (
            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "nom" varchar(100) NOT NULL,
            "code" varchar(20) NOT NULL UNIQUE,
            "type_atelier" varchar(20) NOT NULL DEFAULT 'AUTRE',
            "description" text NOT NULL DEFAULT '',
            "ordre_affichage" integer NOT NULL DEFAULT 0,
            "icone" varchar(10) NOT NULL DEFAULT '🏭',
            "couleur" varchar(7) NOT NULL DEFAULT '#3b82f6',
            "est_actif" integer NOT NULL DEFAULT 1,
            "responsable_id" integer,
            FOREIGN KEY ("responsable_id") REFERENCES "core_employee" ("id") DEFERRABLE INITIALLY DEFERRED
        )
    """)
    print("✅ Table core_atelier créée")

    # 2. CategoriePiece
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "core_categoriepiece" (
            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "nom" varchar(100) NOT NULL,
            "code" varchar(20) NOT NULL UNIQUE,
            "description" text NOT NULL DEFAULT '',
            "icone" varchar(10) NOT NULL DEFAULT '🔩'
        )
    """)
    print("✅ Table core_categoriepiece créée")

    # 3. PieceRechange
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "core_piecerechange" (
            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "reference" varchar(100) NOT NULL UNIQUE,
            "designation" varchar(200) NOT NULL,
            "quantite_stock" real NOT NULL DEFAULT 0,
            "unite" varchar(5) NOT NULL DEFAULT 'PCS',
            "stock_minimum" real NOT NULL DEFAULT 1,
            "stock_maximum" real NOT NULL DEFAULT 50,
            "prix_unitaire" decimal(12,2) NOT NULL DEFAULT 0,
            "delai_livraison_jours" integer NOT NULL DEFAULT 7,
            "emplacement_stock" varchar(100) NOT NULL DEFAULT '',
            "marque_piece" varchar(100) NOT NULL DEFAULT '',
            "reference_fournisseur" varchar(100) NOT NULL DEFAULT '',
            "photo" varchar(100) DEFAULT '',
            "notes" text NOT NULL DEFAULT '',
            "est_active" integer NOT NULL DEFAULT 1,
            "date_creation" datetime,
            "categorie_id" integer,
            "fournisseur_id" integer,
            FOREIGN KEY ("categorie_id") REFERENCES "core_categoriepiece" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("fournisseur_id") REFERENCES "core_supplier" ("id") DEFERRABLE INITIALLY DEFERRED
        )
    """)
    print("✅ Table core_piecerechange créée")

    # 4. Ajouter colonnes à Machine (vérifier d'abord si elles existent)
    columns_to_add = [
        ("atelier_id", "integer REFERENCES core_atelier(id) DEFERRABLE INITIALLY DEFERRED"),
        ("annee_fabrication", "integer"),
        ("compteur_heures", "real NOT NULL DEFAULT 0"),
        ("compteur_metres", "real NOT NULL DEFAULT 0"),
        ("compteur_tours", "real NOT NULL DEFAULT 0"),
        ("cout_acquisition", "decimal(14,2) NOT NULL DEFAULT 0"),
        ("cout_horaire", "decimal(10,2) NOT NULL DEFAULT 0"),
        ("criticite", "varchar(1) NOT NULL DEFAULT 'B'"),
        ("date_dernier_releve", "datetime"),
        ("date_mise_en_service", "date"),
        ("documentation", "varchar(100)"),
        ("est_active", "integer NOT NULL DEFAULT 1"),
        ("fournisseur_machine_id", "integer REFERENCES core_supplier(id) DEFERRABLE INITIALLY DEFERRED"),
        ("laize_max", "real DEFAULT 0"),
        ("laize_min", "real DEFAULT 0"),
        ("marque", "varchar(100) NOT NULL DEFAULT ''"),
        ("modele", "varchar(100) NOT NULL DEFAULT ''"),
        ("nb_couleurs", "integer DEFAULT 0"),
        ("numero_serie", "varchar(100) NOT NULL DEFAULT ''"),
        ("photo", "varchar(100)"),
        ("puissance_kw", "real DEFAULT 0"),
        ("vitesse_max", "real DEFAULT 0"),
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f'ALTER TABLE core_machine ADD COLUMN "{col_name}" {col_type}')
            print(f"✅ Colonne {col_name} ajoutée à core_machine")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"ℹ️  Colonne {col_name} existe déjà")
            else:
                print(f"⚠️  Erreur pour {col_name}: {e}")

    # 5. PlanMaintenancePreventive
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "core_planmaintenancepreventive" (
            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "titre" varchar(200) NOT NULL,
            "description" text NOT NULL DEFAULT '',
            "instructions" text NOT NULL DEFAULT '',
            "type_frequence" varchar(10) NOT NULL DEFAULT 'TEMPS',
            "frequence_jours" integer DEFAULT 30,
            "frequence_heures" real DEFAULT 0,
            "frequence_metres" real DEFAULT 0,
            "frequence_tours" real DEFAULT 0,
            "derniere_execution" datetime,
            "prochaine_execution" datetime,
            "compteur_derniere_execution" real NOT NULL DEFAULT 0,
            "duree_estimee_minutes" integer NOT NULL DEFAULT 60,
            "statut" varchar(10) NOT NULL DEFAULT 'ACTIF',
            "priorite" varchar(10) NOT NULL DEFAULT 'NORMALE',
            "notes" text NOT NULL DEFAULT '',
            "date_creation" datetime,
            "machine_id" integer NOT NULL,
            "technicien_defaut_id" integer,
            FOREIGN KEY ("machine_id") REFERENCES "core_machine" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("technicien_defaut_id") REFERENCES "core_employee" ("id") DEFERRABLE INITIALLY DEFERRED
        )
    """)
    print("✅ Table core_planmaintenancepreventive créée")

    # 6. OrdreMaintenance
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "core_ordremaintenance" (
            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "numero_om" varchar(50) UNIQUE,
            "type_maintenance" varchar(20) NOT NULL,
            "priorite" varchar(10) NOT NULL DEFAULT 'NORMALE',
            "statut" varchar(20) NOT NULL DEFAULT 'OUVERT',
            "titre" varchar(200) NOT NULL,
            "description_probleme" text NOT NULL DEFAULT '',
            "actions_realisees" text NOT NULL DEFAULT '',
            "cause_racine" text NOT NULL DEFAULT '',
            "date_creation" datetime NOT NULL,
            "date_planifiee" datetime,
            "date_debut_intervention" datetime,
            "date_fin_intervention" datetime,
            "date_cloture" datetime,
            "temps_arret_minutes" integer NOT NULL DEFAULT 0,
            "temps_intervention_minutes" integer NOT NULL DEFAULT 0,
            "cout_pieces" decimal(12,2) NOT NULL DEFAULT 0,
            "cout_main_oeuvre" decimal(12,2) NOT NULL DEFAULT 0,
            "cout_externe" decimal(12,2) NOT NULL DEFAULT 0,
            "rapport" varchar(100),
            "photos_avant" varchar(100),
            "photos_apres" varchar(100),
            "notes" text NOT NULL DEFAULT '',
            "demandeur_id" integer,
            "machine_id" integer NOT NULL,
            "plan_preventif_id" integer,
            "technicien_principal_id" integer,
            FOREIGN KEY ("demandeur_id") REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("machine_id") REFERENCES "core_machine" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("plan_preventif_id") REFERENCES "core_planmaintenancepreventive" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("technicien_principal_id") REFERENCES "core_employee" ("id") DEFERRABLE INITIALLY DEFERRED
        )
    """)
    print("✅ Table core_ordremaintenance créée")

    # 7. AlerteMaintenance
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "core_alertemaintenance" (
            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "type_alerte" varchar(25) NOT NULL,
            "niveau" varchar(10) NOT NULL DEFAULT 'WARNING',
            "titre" varchar(200) NOT NULL,
            "message" text NOT NULL,
            "date_creation" datetime NOT NULL,
            "est_lue" integer NOT NULL DEFAULT 0,
            "est_traitee" integer NOT NULL DEFAULT 0,
            "date_traitement" datetime,
            "machine_id" integer,
            "piece_id" integer,
            "plan_preventif_id" integer,
            "traite_par_id" integer,
            FOREIGN KEY ("machine_id") REFERENCES "core_machine" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("piece_id") REFERENCES "core_piecerechange" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("plan_preventif_id") REFERENCES "core_planmaintenancepreventive" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("traite_par_id") REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED
        )
    """)
    print("✅ Table core_alertemaintenance créée")

    # 8. Tables Many-to-Many
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "core_piecerechange_machines_compatibles" (
            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "piecerechange_id" integer NOT NULL,
            "machine_id" integer NOT NULL,
            FOREIGN KEY ("piecerechange_id") REFERENCES "core_piecerechange" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("machine_id") REFERENCES "core_machine" ("id") DEFERRABLE INITIALLY DEFERRED,
            UNIQUE ("piecerechange_id", "machine_id")
        )
    """)
    print("✅ Table core_piecerechange_machines_compatibles créée")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "core_planmaintenancepreventive_pieces_necessaires" (
            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "planmaintenancepreventive_id" integer NOT NULL,
            "piecerechange_id" integer NOT NULL,
            FOREIGN KEY ("planmaintenancepreventive_id") REFERENCES "core_planmaintenancepreventive" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("piecerechange_id") REFERENCES "core_piecerechange" ("id") DEFERRABLE INITIALLY DEFERRED,
            UNIQUE ("planmaintenancepreventive_id", "piecerechange_id")
        )
    """)
    print("✅ Table core_planmaintenancepreventive_pieces_necessaires créée")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "core_ordremaintenance_techniciens_secondaires" (
            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "ordremaintenance_id" integer NOT NULL,
            "employee_id" integer NOT NULL,
            FOREIGN KEY ("ordremaintenance_id") REFERENCES "core_ordremaintenance" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("employee_id") REFERENCES "core_employee" ("id") DEFERRABLE INITIALLY DEFERRED,
            UNIQUE ("ordremaintenance_id", "employee_id")
        )
    """)
    print("✅ Table core_ordremaintenance_techniciens_secondaires créée")

    # 9. CompteurMachine
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "core_compteurmachine" (
            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "type_compteur" varchar(10) NOT NULL,
            "valeur" real NOT NULL,
            "date_releve" datetime NOT NULL,
            "notes" text NOT NULL DEFAULT '',
            "machine_id" integer NOT NULL,
            "releve_par_id" integer,
            FOREIGN KEY ("machine_id") REFERENCES "core_machine" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("releve_par_id") REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED
        )
    """)
    print("✅ Table core_compteurmachine créée")

    # 10. ConsommationPiece
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "core_consommationpiece" (
            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "quantite" real NOT NULL DEFAULT 1,
            "date_consommation" datetime NOT NULL,
            "notes" text NOT NULL DEFAULT '',
            "ordre_maintenance_id" integer NOT NULL,
            "piece_id" integer NOT NULL,
            FOREIGN KEY ("ordre_maintenance_id") REFERENCES "core_ordremaintenance" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("piece_id") REFERENCES "core_piecerechange" ("id") DEFERRABLE INITIALLY DEFERRED
        )
    """)
    print("✅ Table core_consommationpiece créée")

    # 11. MouvementPiece
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "core_mouvementpiece" (
            "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
            "type_mouvement" varchar(15) NOT NULL,
            "quantite" real NOT NULL,
            "date_mouvement" datetime NOT NULL,
            "motif" varchar(200) NOT NULL DEFAULT '',
            "notes" text NOT NULL DEFAULT '',
            "ordre_maintenance_id" integer,
            "piece_id" integer NOT NULL,
            "utilisateur_id" integer,
            FOREIGN KEY ("ordre_maintenance_id") REFERENCES "core_ordremaintenance" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("piece_id") REFERENCES "core_piecerechange" ("id") DEFERRABLE INITIALLY DEFERRED,
            FOREIGN KEY ("utilisateur_id") REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED
        )
    """)
    print("✅ Table core_mouvementpiece créée")

    # Sauvegarder les changements
    conn.commit()
    print("\n✅ Toutes les tables ont été créées avec succès!")

except Exception as e:
    print(f"\n❌ Erreur: {e}")
    conn.rollback()

finally:
    conn.close()

print("\n🎯 Vous pouvez maintenant exécuter:")
print("   python manage.py migrate core 0013 --fake")
print("   python manage.py runserver")