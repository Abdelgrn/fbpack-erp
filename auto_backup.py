import os
import datetime
import urllib.request
import ssl

# Configuration de votre ERP en ligne
ERP_URL = "https://fbpack-erp-cxdf.onrender.com/administration/backup/download/"
TOKEN = "django-ultimate-erp-secret-key"

# Dossier où enregistrer les sauvegardes sur votre PC (sur le Bureau)
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")
BACKUP_DIR = os.path.join(DESKTOP_PATH, "ERP_Backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
filename = f"backup_fbpack_{timestamp}.json"
filepath = os.path.join(BACKUP_DIR, filename)

print(f"🔄 Connexion à Render pour télécharger la sauvegarde ERP...")

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
            print(f"✅ SAUVEGARDE RÉUSSIE ! Fichier enregistré dans :\n👉 {filepath}")
        else:
            print(f"❌ Erreur HTTP : {response.status}")
except Exception as e:
    print(f"❌ Erreur de connexion au serveur ERP : {e}")