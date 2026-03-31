import os

print("🔒 VERROUILLAGE DES ACCÈS (VIEWS.PY)...")

file_path = "core/views.py"

# 1. Lecture du fichier
if not os.path.exists(file_path):
    print("❌ ERREUR : Le fichier core/views.py est introuvable.")
    exit()

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 2. Ajout de l'import nécessaire
header = "from django.contrib.auth.decorators import login_required\n"
if "from django.contrib.auth.decorators" not in content:
    content = header + content
    print("✅ Import ajouté.")

# 3. Ajout du décorateur @login_required sur toutes les fonctions
# Liste des pages à protéger
pages = [
    "dashboard", 
    "production_gantt", 
    "reporting", 
    "import_stock_view",
    "client_detail", # Si vous avez la V2
    "crm_list"       # Si vous avez la V2
]

count = 0
for page in pages:
    target = f"def {page}(request):"
    replacement = f"@login_required\ndef {page}(request):"
    
    # On vérifie si la fonction existe et n'est pas déjà protégée
    if target in content and f"@login_required\ndef {page}" not in content:
        content = content.replace(target, replacement)
        count += 1
        print(f"  -> Page protégée : {page}")

# 4. Sauvegarde
if count > 0:
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ SUCCÈS : {count} pages ont été verrouillées.")
else:
    print("ℹ️ Tout semble déjà verrouillé.")

print("\n⚠️ IMPORTANT :")
print("Si vous accédez toujours au Dashboard, c'est parce que vous êtes DÉJÀ connecté en admin.")
print("👉 Testez en navigation PRIVÉE (Incognito) pour voir la page de login.")