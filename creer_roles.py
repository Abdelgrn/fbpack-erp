import os
import django

# Configuration de l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'polypack_erp.settings') # Ou fbpack_erp.settings selon votre dossier
try:
    django.setup()
except:
    # Si le nom du dossier n'est pas le bon, on cherche auto
    import sys
    current_dir = os.getcwd()
    sys.path.append(current_dir)
    # On cherche le settings.py
    for root, dirs, files in os.walk("."):
        if "settings.py" in files:
            setting_path = os.path.relpath(root).replace(os.sep, '.') + ".settings"
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', setting_path)
            django.setup()
            break

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from core.models import * 

print("🛡️  CONFIGURATION DES RÔLES MÉTIERS...")

# DÉFINITION DES ÉQUIPES ET DE LEURS ACCÈS
# On liste les modèles auxquels ils ont droit
roles = {
    "TEAM_CRM": [Client, ClientContact, InteractionLog, Quote],
    "TEAM_PREPRESSE": [TechnicalProduct, Tooling],
    "TEAM_STOCK": [Material, Supplier, PurchaseOrder],
    "TEAM_PROD": [ProductionOrder, Machine, MaintenanceSchedule, IncidentLog, ConsumptionLog],
}

for role_name, models_list in roles.items():
    # 1. Créer ou récupérer le groupe
    group, created = Group.objects.get_or_create(name=role_name)
    print(f"\n👥 Groupe : {role_name}")
    
    # 2. Vider les anciennes permissions pour repartir propre
    group.permissions.clear()
    
    # 3. Ajouter les permissions pour chaque modèle du groupe
    count = 0
    for model in models_list:
        content_type = ContentType.objects.get_for_model(model)
        # On récupère les droits : Voir (view), Ajouter (add), Modifier (change), Supprimer (delete)
        perms = Permission.objects.filter(content_type=content_type)
        
        for p in perms:
            group.permissions.add(p)
            count += 1
            
    print(f"   ✅ {count} droits assignés (Clients, Ajout, Modif...)")

print("\n✨ TERMINÉ ! Vos groupes sont prêts.")
print("👉 Allez dans l'Admin > Utilisateurs > Choisissez une personne > Cochez son Groupe.")