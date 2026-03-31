import os

# 1. TEMPLATE HTML (Interface avec choix du type)
import_html = """
{% extends 'base.html' %}
{% block content %}
<div class="max-w-2xl mx-auto mt-6">
    <h2 class="text-3xl font-bold text-white mb-2">Station d'Import Universelle</h2>
    <p class="text-gray-400 mb-6">Mettez à jour vos données en masse via Excel.</p>

    <div class="glass p-8 rounded-xl border border-slate-700">
        
        {% if message %}
        <div class="p-4 mb-6 text-sm rounded-lg font-bold border {% if success %}bg-green-900/50 border-green-500 text-green-300{% else %}bg-red-900/50 border-red-500 text-red-300{% endif %}">
            {{ message }}
        </div>
        {% endif %}

        <form method="post" enctype="multipart/form-data" class="space-y-6">
            {% csrf_token %}
            
            <!-- Choix du Type -->
            <div>
                <label class="block text-sm font-bold text-gray-300 mb-2">1. Que voulez-vous importer ?</label>
                <select name="import_type" id="typeSelector" onchange="updateInstructions()" class="w-full bg-slate-800 border border-slate-600 rounded p-3 text-white focus:border-neon focus:outline-none">
                    <option value="STOCK">📦 Stock (Matières Premières)</option>
                    <option value="CRM">🤝 CRM (Clients & Prospects)</option>
                    <option value="TOOLS">⚙️ Outillage (Cylindres & Clichés)</option>
                    <option value="PLANNING">🏭 Planning Production (OF)</option>
                </select>
            </div>

            <!-- Zone Upload -->
            <div>
                <label class="block text-sm font-bold text-gray-300 mb-2">2. Fichier Excel (.xlsx)</label>
                <div class="border-2 border-dashed border-slate-600 rounded-lg p-8 text-center hover:border-neon transition bg-slate-800/30">
                    <input type="file" name="excel_file" accept=".xlsx, .xls" required
                           class="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-neon file:text-black hover:file:bg-cyan-400"/>
                </div>
            </div>

            <!-- Instructions Dynamiques -->
            <div class="bg-slate-900/50 p-4 rounded text-sm border border-slate-700">
                <p class="text-neon font-bold mb-2">Colonnes requises :</p>
                <p id="colList" class="font-mono text-gray-300">Designation, Categorie, Quantite, Unite, Seuil_Min, Prix</p>
            </div>
            
            <button type="submit" class="w-full bg-gradient-to-r from-cyan-600 to-blue-600 text-white font-bold py-3 px-6 rounded shadow-lg hover:brightness-110 transition transform active:scale-95">
                Lancer l'Importation
            </button>
        </form>
    </div>
</div>

<script>
    const colMap = {
        'STOCK': 'Designation, Categorie (Film/Encre/Colle), Quantite, Unite, Seuil_Min, Prix',
        'CRM': 'Nom, Ville, Telephone, Email, Secteur, Statut (Active/Prospect)',
        'TOOLS': 'Ref_Produit, Type (Cylindre/Cliche), Serial, Tours_Max, Tours_Actuels',
        'PLANNING': 'OF_Numero, Client, Produit, Machine, Date_Debut (JJ/MM/AAAA), Qte_Prevue'
    };

    function updateInstructions() {
        const type = document.getElementById('typeSelector').value;
        document.getElementById('colList').innerText = colMap[type];
    }
</script>
{% endblock %}
"""

with open("templates/stock/import_stock.html", "w", encoding="utf-8") as f:
    f.write(import_html)
print("✅ Interface Import mise à jour.")

# 2. LOGIQUE VUE (Views.py)
views_path = "core/views.py"

# On lit le fichier actuel
with open(views_path, "r", encoding="utf-8") as f:
    old_content = f.read()

# On prépare la nouvelle fonction view complète
new_view_code = """
import pandas as pd
from django.core.files.storage import FileSystemStorage
from django.utils.dateparse import parse_datetime
import datetime

def import_stock_view(request):
    context = {}
    if request.method == 'POST' and request.FILES.get('excel_file'):
        try:
            import_type = request.POST.get('import_type')
            excel_file = request.FILES['excel_file']
            fs = FileSystemStorage()
            filename = fs.save(excel_file.name, excel_file)
            file_path = fs.path(filename)
            
            df = pd.read_excel(file_path)
            count = 0
            
            # --- 1. IMPORT STOCK ---
            if import_type == 'STOCK':
                for _, row in df.iterrows():
                    cat_map = {'Film': 'FILM', 'Encre': 'INK', 'Colle': 'GLUE', 'Solvant': 'SOLV'}
                    Material.objects.update_or_create(
                        name=row.get('Designation', 'Inconnu'),
                        defaults={
                            'category': cat_map.get(row.get('Categorie'), 'FILM'),
                            'quantity': row.get('Quantite', 0),
                            'unit': row.get('Unite', 'kg'),
                            'min_threshold': row.get('Seuil_Min', 0),
                            'price_per_unit': row.get('Prix', 0)
                        }
                    )
                    count += 1

            # --- 2. IMPORT CRM ---
            elif import_type == 'CRM':
                for _, row in df.iterrows():
                    status_map = {'Active': 'ACTIVE', 'Prospect': 'PROSPECT', 'VIP': 'VIP'}
                    Client.objects.update_or_create(
                        name=row.get('Nom'),
                        defaults={
                            'city': row.get('Ville', ''),
                            'phone': row.get('Telephone', ''),
                            'email': row.get('Email', ''),
                            'sector': row.get('Secteur', ''),
                            'status': status_map.get(row.get('Statut'), 'PROSPECT')
                        }
                    )
                    count += 1

            # --- 3. IMPORT OUTILLAGE (Durée de vie) ---
            elif import_type == 'TOOLS':
                for _, row in df.iterrows():
                    # On cherche le produit lié, sinon on le crée à la volée
                    prod_ref = row.get('Ref_Produit')
                    # Astuce: Création d'un client fictif si besoin pour le produit
                    cli, _ = Client.objects.get_or_create(name="Client Divers", defaults={'city': 'Interne', 'phone': '000'})
                    
                    product, _ = TechnicalProduct.objects.get_or_create(
                        ref_internal=prod_ref,
                        defaults={
                            'name': f"Produit {prod_ref}", 
                            'client': cli, 
                            'structure_type': 'MONO', 
                            'width_mm': 100
                        }
                    )
                    
                    type_map = {'Cylindre': 'CYL', 'Cliche': 'CLICHE'}
                    Tooling.objects.update_or_create(
                        serial_number=row.get('Serial'),
                        defaults={
                            'product': product,
                            'tool_type': type_map.get(row.get('Type'), 'CYL'),
                            'max_impressions': row.get('Tours_Max', 1000000),
                            'current_impressions': row.get('Tours_Actuels', 0)
                        }
                    )
                    count += 1

            # --- 4. IMPORT PLANNING ---
            elif import_type == 'PLANNING':
                for _, row in df.iterrows():
                    # 1. Trouver/Créer Client
                    cli_name = row.get('Client')
                    client, _ = Client.objects.get_or_create(name=cli_name, defaults={'city': '?', 'phone': '?'})
                    
                    # 2. Trouver/Créer Produit
                    prod_name = row.get('Produit')
                    product, _ = TechnicalProduct.objects.get_or_create(
                        ref_internal=f"REF-{prod_name[:5]}", 
                        defaults={'name': prod_name, 'client': client, 'structure_type': 'MONO', 'width_mm': 500}
                    )
                    
                    # 3. Trouver Machine
                    mac_name = row.get('Machine')
                    machine = Machine.objects.filter(name__icontains=mac_name).first()
                    
                    # 4. Dates
                    start_d = pd.to_datetime(row.get('Date_Debut'))
                    # On estime la fin à +4h par défaut
                    end_d = start_d + datetime.timedelta(hours=4)
                    
                    ProductionOrder.objects.update_or_create(
                        of_number=str(row.get('OF_Numero')),
                        defaults={
                            'client': client,
                            'product': product,
                            'machine': machine,
                            'start_time': start_d,
                            'end_time': end_d,
                            'quantity_planned': row.get('Qte_Prevue', 0),
                            'status': 'PLANNED'
                        }
                    )
                    count += 1

            context = {'message': f'✅ Succès ! {count} lignes importées dans {import_type}.', 'success': True}
            
        except Exception as e:
            context = {'message': f'❌ Erreur : {str(e)}', 'success': False}
            
    return render(request, 'stock/import_stock.html', context)
"""

# Remplacement bourrin mais efficace de la fonction existante
# On coupe le fichier avant "def import_stock_view" et on colle le nouveau code
if "def import_stock_view" in old_content:
    parts = old_content.split("def import_stock_view")
    final_content = parts[0] + new_view_code
else:
    final_content = old_content + "\n" + new_view_code

with open(views_path, "w", encoding="utf-8") as f:
    f.write(final_content)

print("✅ Logique Python Multi-Import injectée.")
print("🚀 Terminé. Relancez le serveur !")