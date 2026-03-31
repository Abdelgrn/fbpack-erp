import os

print("🕵️  RECHERCHE INTELLIGENTE DU DOSSIER DE CONFIGURATION...")

# 1. Trouver le dossier qui contient 'settings.py' et 'urls.py'
project_dir = None
for root, dirs, files in os.walk("."):
    if "settings.py" in files and "urls.py" in files:
        # On a trouvé le dossier de config !
        project_dir = root
        # On retire le "./" du début si présent
        if project_dir.startswith("./") or project_dir.startswith(".\\"):
            project_dir = project_dir[2:]
        break

if not project_dir:
    print("❌ ERREUR FATALE : Impossible de trouver 'settings.py'.")
    print("Êtes-vous sûr d'être dans le dossier qui contient 'manage.py' ?")
    print("Contenu du dossier actuel :", os.listdir())
    exit()

print(f"✅ Dossier de configuration trouvé : '{project_dir}'")

# 2. APPLICATION DU CORRECTIF DE SÉCURITÉ
urls_path = os.path.join(project_dir, "urls.py")

print(f"📝 Modification du fichier : {urls_path}")

new_urls_content = """
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    # AUTHENTIFICATION
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='/accounts/login/'), name='logout'),
    # APPLICATION
    path('', include('core.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
"""

try:
    with open(urls_path, "w", encoding="utf-8") as f:
        f.write(new_urls_content)
    print("✅ URLs mises à jour avec succès.")
except Exception as e:
    print(f"❌ Erreur lors de l'écriture : {e}")

# 3. VÉRIFICATION DU TEMPLATE DE LOGIN
if not os.path.exists("templates/registration/login.html"):
    print("⚠️ Le fichier login.html manque. Régénération...")
    os.makedirs("templates/registration", exist_ok=True)
    # (Code du template login futuriste - version courte)
    login_code = """
{% extends 'base.html' %}
{% block content %}
<div class="flex items-center justify-center h-full">
    <div class="glass p-8 rounded-xl w-96">
        <h2 class="text-2xl font-bold text-white mb-6 text-center">Connexion</h2>
        <form method="post">{% csrf_token %}
            {{ form.as_p }}
            <button type="submit" class="w-full bg-neon mt-4 py-2 rounded font-bold">Entrer</button>
        </form>
    </div>
</div>
{% endblock %}
"""
    with open("templates/registration/login.html", "w") as f: f.write(login_code)
    print("✅ Template login régénéré.")

print("\n🎉 RÉPARATION TERMINÉE.")
print("👉 Relancez le serveur : python manage.py runserver")