import os
import datetime
import urllib.request
import ssl

ERP_URL = "https://fbpack-erp-cxdf.onrender.com/administration/backup/download/"
TOKEN = "django-ultimate-erp-secret-key"

BASE_DIR = r"C:\Users\ACER ASPIRE\Documents\fbpack_erp beta - Copie"
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
filename = f"backup_fbpack_{timestamp}.json"
filepath = os.path.join(BACKUP_DIR, filename)
logpath = os.path.join(BACKUP_DIR, "backup_log.txt")

def log(msg):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now_str}] {msg}\n"
    print(line, end="")
    try:
        with open(logpath, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

log("🔄 Connexion à Render pour télécharger la sauvegarde TOTALE...")

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
            log(f"✅ SAUVEGARDE RÉUSSIE ! Fichier créé : {filename}")
        else:
            log(f"❌ Erreur HTTP : {response.status}")
except Exception as e:
    log(f"❌ Erreur de connexion au serveur ERP : {e}")