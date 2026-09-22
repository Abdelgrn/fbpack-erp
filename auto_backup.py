import os
import datetime
import urllib.request
import ssl

# URL officielle de votre ERP Render pour le backup
ERP_URL = "https://fbpack-erp-cxdf.onrender.com/administration/backup/download/"
TOKEN = "django-ultimate-erp-secret-key"

# Chemin exact et absolu du dossier de votre ERP sur votre PC
BASE_DIR = r"C:\Users\ACER ASPIRE\Documents\fbpack_erp beta - Copie"
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

# Création forcée du sous-dossier "backups" s'il n'existe pas
os.makedirs(BACKUP_DIR, exist_ok=True)

# Nom du fichier avec la date et l'heure exactes
timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
filename = f"backup_fbpack_{timestamp}.json"
filepath = os.path.join(BACKUP_DIR, filename)

print("🔄 Connexion à Render pour télécharger la sauvegarde TOTALE de l'ERP...")

full_url = f"{ERP_URL}?token={TOKEN}"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

try:
    req = urllib.request.Request(full_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx) as response:
        if response.status == 200:
            data = response.read()
            with open(filepath, 'wb') as f:
                f.write(data)
            print("\n==================================================")
            print("✅ SAUVEGARDE RÉUSSIE AVEC SUCCÈS !")
            print(f"📁 Fichier créé : {filename}")
            print(f"👉 Emplacement : {filepath}")
            print("==================================================\n")
        else:
            print(f"❌ Erreur HTTP : {response.status}")
except Exception as e:
    print(f"❌ Erreur de connexion au serveur ERP : {e}")