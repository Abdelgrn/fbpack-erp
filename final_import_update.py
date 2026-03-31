import os

# ==============================================================================
# 1. MISE À JOUR DU TEMPLATE HTML (Interface)
# ==============================================================================
import_html = """
{% extends 'base.html' %}
{% block content %}
<div class="max-w-3xl mx-auto mt-6">
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
                    <option value="CONSO">💧 Consommation (Flexo/Hélio)</option>
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
                <p class="text-neon font-bold mb-2">Colonnes Excel requises (En-têtes) :</p>
                <p id="colList" class="font-mono text-gray-300 text-xs leading-relaxed break-words">Select type...</p>
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
        'PLANNING': 'OF_Numero, Client, Produit, Machine, Date_Debut (JJ/MM/AAAA), Qte_Prevue',
        'CONSO': 'Date, Type (Flexo/Helio), Support, Laize, Bobine_In, Bobine_Out, Metrage, Noir, Magenta, Jaune, Cyan, Dore, Silver, Orange, Blanc, Vernis, Metoxyn, 2080'
    };

    function updateInstructions() {
        const type = document.getElementById('typeSelector').value;
        document.getElementById('colList').innerText = colMap[type];
    }
    // Init
    updateInstructions();
</script>
{% endblock %}
"""

os.makedirs("templates/stock", exist_ok=True)
with open("templates/stock/import_stock.html", "w", encoding="utf-8") as f:
    f.write(import_html)
print("✅ Interface Import mise à jour (Avec option Conso).")

# ==============================================================================
# 2. MISE À JOUR DE VIEWS.PY (Logique Backend)
# ==============================================================================
views_path = "core/views.py"

# On lit le fichier actuel
with open(views_path, "r", encoding="utf-8") as f:
    old_content = f.read()

# Le nouveau code de la vue
new_view_code = """
import pandas as pd
from django.core.files.storage import FileSystemStorage
from django.utils.dateparse import parse_datetime
import datetime
from .models import *  # Assure que tous les modèles sont dispos

def import_stock_view(request):
    context = {}
    if request.method == 'POST' and request.FILES.get('excel_file'):
        try:
            import_type = request.POST.get('import_type')
            excel_file = request.FILES['excel_file']
            fs = FileSystemStorage()
            filename = fs.save(excel_file.name, excel_file)
            file_path = fs.path(filename)
            
            # Remplacement des NaN par 0 ou vide pour éviter les erreurs
            df = pd.read_excel(file_path).fillna(0)
            count = 0
            
            # --- 1. IMPORT STOCK ---
            if import_type == 'STOCK':
                for _, row in df.iterrows():
                    cat_map = {'Film': 'FILM', 'Encre': 'INK', 'Colle': 'GLUE', 'Solvant': 'SOLV'}
                    # On force le cast en string pour category
                    cat_val = row.get('Categorie', 'FILM')
                    if cat_val == 0: cat_val = 'FILM'
                    
                    Material.objects.update_or_create(
                        name=row.get('Designation', 'Inconnu'),
                        defaults={
                            'category': cat_map.get(cat_val, 'FILM'),
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
                    nom = row.get('Nom')
                    if nom and nom != 0:
                        Client.objects.update_or_create(
                            name=nom,
                            defaults={
                                'city': row.get('Ville', ''),
                                'phone': row.get('Telephone', ''),
                                'email': row.get('Email', ''),
                                'sector': row.get('Secteur', ''),
                                'status': status_map.get(row.get('Statut'), 'PROSPECT')
                            }
                        )
                        count += 1

            # --- 3. IMPORT OUTILLAGE ---
            elif import_type == 'TOOLS':
                for _, row in df.iterrows():
                    prod_ref = row.get('Ref_Produit')
                    if prod_ref and prod_ref != 0:
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
                        type_val = row.get('Type', 'CYL')
                        if type_val == 0: type_val = 'CYL'

                        Tooling.objects.update_or_create(
                            serial_number=row.get('Serial'),
                            defaults={
                                'product': product,
                                'tool_type': type_map.get(type_val, 'CYL'),
                                'max_impressions': row.get('Tours_Max', 1000000),
                                'current_impressions': row.get('Tours_Actuels', 0)
                            }
                        )
                        count += 1

            # --- 4. IMPORT PLANNING ---
            elif import_type == 'PLANNING':
                for _, row in df.iterrows():
                    cli_name = row.get('Client')
                    if cli_name and cli_name != 0:
                        client, _ = Client.objects.get_or_create(name=cli_name, defaults={'city': '?', 'phone': '?'})
                        
                        prod_name = row.get('Produit')
                        product, _ = TechnicalProduct.objects.get_or_create(
                            ref_internal=f"REF-{str(prod_name)[:5]}", 
                            defaults={'name': prod_name, 'client': client, 'structure_type': 'MONO', 'width_mm': 500}
                        )
                        
                        mac_name = row.get('Machine')
                        machine = Machine.objects.filter(name__icontains=str(mac_name)).first()
                        
                        try:
                            start_d = pd.to_datetime(row.get('Date_Debut'))
                        except:
                            start_d = datetime.datetime.now()
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

            # --- 5. IMPORT CONSOMMATION (NOUVEAU) ---
            elif import_type == 'CONSO':
                for _, row in df.iterrows():
                    # 1. Gestion de la Date
                    try:
                        d_prod = pd.to_datetime(row.get('Date')).date()
                    except:
                        d_prod = datetime.date.today()

                    # 2. Gestion du Type (Flexo/Helio)
                    raw_type = str(row.get('Type', 'FLEXO')).upper()
                    final_type = 'HELIO' if 'HELIO' in raw_type else 'FLEXO'

                    # 3. Création (On utilise create pour autoriser plusieurs entrées par jour)
                    ConsommationEncre.objects.create(
                        date=d_prod,
                        process_type=final_type,
                        support=row.get('Support', 'Inconnu'),
                        laize=float(row.get('Laize', 0)),
                        
                        bobine_in=float(row.get('Bobine_In', 0)),
                        bobine_out=float(row.get('Bobine_Out', 0)),
                        metrage=float(row.get('Metrage', 0)),
                        
                        encre_noir=float(row.get('Noir', 0)),
                        encre_magenta=float(row.get('Magenta', 0)),
                        encre_jaune=float(row.get('Jaune', 0)),
                        encre_cyan=float(row.get('Cyan', 0)),
                        encre_dore=float(row.get('Dore', 0)),
                        encre_silver=float(row.get('Silver', 0)),
                        encre_orange=float(row.get('Orange', 0)),
                        encre_blanc=float(row.get('Blanc', 0)),
                        encre_vernis=float(row.get('Vernis', 0)),
                        
                        solvant_metoxyn=float(row.get('Metoxyn', 0)),
                        solvant_2080=float(row.get('2080', 0))
                    )
                    count += 1

            context = {'message': f'✅ Succès ! {count} lignes importées dans {import_type}.', 'success': True}
            
        except Exception as e:
            context = {'message': f'❌ Erreur : {str(e)}', 'success': False}
            
    return render(request, 'stock/import_stock.html', context)
"""

# Insertion intelligente du code
if "def import_stock_view" in old_content:
    # On coupe le fichier juste avant l'ancienne fonction
    parts = old_content.split("def import_stock_view")
    # On garde le début (imports, autres vues) + la nouvelle fonction
    final_content = parts[0] + new_view_code
else:
    # Si la fonction n'existe pas, on l'ajoute à la fin
    final_content = old_content + "\n" + new_view_code

with open(views_path, "w", encoding="utf-8") as f:
    f.write(final_content)

print("✅ Logique Python mise à jour avec le module CONSOMMATION.")
print("🚀 Terminé. Relancez le serveur Django !")