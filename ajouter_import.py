import os

# 1. CRÉATION DU TEMPLATE D'IMPORT
import_html = """
{% extends 'base.html' %}
{% block content %}
<div class="max-w-xl mx-auto mt-10">
    <h2 class="text-2xl font-bold text-white mb-6">Importer Stock (Excel)</h2>
    
    <div class="glass p-8 rounded-xl">
        <p class="text-gray-400 mb-4 text-sm">
            Le fichier Excel doit contenir les colonnes suivantes : <br>
            <span class="text-neon font-mono">Designation, Categorie, Quantite, Unite, Seuil_Min, Prix</span>
        </p>

        {% if message %}
        <div class="p-4 mb-4 text-sm rounded-lg {% if success %}bg-green-900 text-green-300{% else %}bg-red-900 text-red-300{% endif %}">
            {{ message }}
        </div>
        {% endif %}

        <form method="post" enctype="multipart/form-data" class="space-y-6">
            {% csrf_token %}
            <div class="border-2 border-dashed border-slate-600 rounded-lg p-8 text-center hover:border-neon transition bg-slate-800/50">
                <input type="file" name="excel_file" accept=".xlsx, .xls" required
                       class="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-neon file:text-black hover:file:bg-cyan-400"/>
            </div>
            
            <div class="flex justify-between">
                <a href="/admin/core/material/" class="text-gray-400 hover:text-white py-2">Annuler</a>
                <button type="submit" class="bg-neon text-black font-bold py-2 px-6 rounded shadow-lg hover:bg-cyan-300 transition">
                    Lancer l'Import 📥
                </button>
            </div>
        </form>
    </div>
</div>
{% endblock %}
"""

os.makedirs("templates/stock", exist_ok=True)
with open("templates/stock/import_stock.html", "w", encoding="utf-8") as f:
    f.write(import_html)
print("✅ Template import créé.")

# 2. MISE À JOUR DE URLS.PY
urls_content = """
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('production/planning/', views.production_gantt, name='planning'),
    path('reporting/', views.reporting, name='reporting'),
    path('stock/import/', views.import_stock_view, name='import_stock'), # NOUVELLE ROUTE
]
"""
with open("core/urls.py", "w", encoding="utf-8") as f:
    f.write(urls_content)
print("✅ URLs mises à jour.")

# 3. MISE À JOUR DE VIEWS.PY (Ajout logique Pandas)
views_path = "core/views.py"
# On lit le fichier actuel
with open(views_path, "r", encoding="utf-8") as f:
    content = f.read()

# On ajoute l'import pandas et la nouvelle vue si elle n'existe pas
if "def import_stock_view" not in content:
    new_imports = "import pandas as pd\nfrom django.core.files.storage import FileSystemStorage\n"
    
    new_view = """

def import_stock_view(request):
    context = {}
    if request.method == 'POST' and request.FILES['excel_file']:
        try:
            excel_file = request.FILES['excel_file']
            fs = FileSystemStorage()
            filename = fs.save(excel_file.name, excel_file)
            file_path = fs.path(filename)
            
            # Lecture Excel avec Pandas
            df = pd.read_excel(file_path)
            
            count = 0
            for index, row in df.iterrows():
                # Mapping des colonnes (Gestion des erreurs si colonne manquante)
                name = row.get('Designation', f"Produit {index}")
                cat_map = {'Film': 'FILM', 'Encre': 'INK', 'Colle': 'GLUE', 'Solvant': 'SOLV'}
                cat_raw = row.get('Categorie', 'FILM')
                category = cat_map.get(cat_raw, 'FILM')
                
                Material.objects.update_or_create(
                    name=name,
                    defaults={
                        'category': category,
                        'quantity': row.get('Quantite', 0),
                        'unit': row.get('Unite', 'kg'),
                        'min_threshold': row.get('Seuil_Min', 100),
                        'price_per_unit': row.get('Prix', 0)
                    }
                )
                count += 1
            
            context = {'message': f'Succès ! {count} articles importés/mis à jour.', 'success': True}
            
        except Exception as e:
            context = {'message': f'Erreur lors de l import : {str(e)}', 'success': False}
            
    return render(request, 'stock/import_stock.html', context)
"""
    # On insère les imports en haut et la vue en bas
    final_content = new_imports + content + new_view
    with open(views_path, "w", encoding="utf-8") as f:
        f.write(final_content)
    print("✅ Vue Import Excel ajoutée.")
else:
    print("ℹ️ La vue existe déjà.")


# 4. AJOUT DU BOUTON DANS LA SIDEBAR
base_path = "templates/base.html"
with open(base_path, "r", encoding="utf-8") as f:
    base_content = f.read()

# On cherche le lien "Stocks & Achats" pour ajouter le bouton juste en dessous
target = 'admin/core/material/" class="nav-link flex items-center px-6 py-2 transition text-sm">📦 Stocks & Achats</a>'
replacement = target + '\n            <a href="{% url \'import_stock\' %}" class="nav-link flex items-center px-6 py-2 transition text-sm text-green-400 hover:text-green-300">📥 Importer Excel</a>'

if "Importer Excel" not in base_content:
    base_content = base_content.replace(target, replacement)
    with open(base_path, "w", encoding="utf-8") as f:
        f.write(base_content)
    print("✅ Bouton ajouté dans le menu.")
else:
    print("ℹ️ Bouton déjà présent.")

print("\n🚀 Correctif terminé. Relancez le serveur !")