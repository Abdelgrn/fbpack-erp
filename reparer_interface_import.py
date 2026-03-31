import os

print("🧹 Nettoyage complet de la page d'import...")

html_content = """
{% extends 'base.html' %}
{% block content %}
<div class="max-w-2xl mx-auto mt-6">
    <div class="flex items-center justify-between mb-6">
        <h2 class="text-3xl font-bold text-white">Station d'Import</h2>
        <span class="text-xs bg-slate-800 text-gray-400 px-2 py-1 rounded border border-slate-700">v4.0 Final</span>
    </div>

    <div class="glass p-8 rounded-xl border border-slate-700 relative overflow-hidden">
        
        <!-- Messages Résultat -->
        {% if message %}
        <div class="p-4 mb-6 text-sm rounded-lg font-bold border flex items-center gap-3 {% if success %}bg-green-900/50 border-green-500 text-green-300{% else %}bg-red-900/50 border-red-500 text-red-300{% endif %}">
            <span class="text-xl">{% if success %}✅{% else %}❌{% endif %}</span>
            {{ message }}
        </div>
        {% endif %}

        <form method="post" enctype="multipart/form-data" class="space-y-6">
            {% csrf_token %}
            
            <!-- 1. QUOI IMPORTER ? -->
            <div>
                <label class="block text-sm font-bold text-gray-300 mb-2">1. Type de données</label>
                <select name="import_type" id="typeSelector" onchange="updateUI()" class="w-full bg-slate-800 border border-slate-600 rounded-lg p-3 text-white focus:border-neon focus:ring-1 focus:ring-neon outline-none transition">
                    <option value="STOCK">📦 Stock (Matières Premières)</option>
                    <option value="CRM">🤝 CRM (Clients & Prospects)</option>
                    <option value="TOOLS">⚙️ Outillage (Cylindres & Clichés)</option>
                    <option value="PLANNING">🏭 Planning Production (OF)</option>
                </select>
            </div>

            <!-- 2. OPTION SPÉCIALE OUTILS (Cachée par défaut) -->
            <div id="toolOption" class="hidden bg-indigo-900/20 p-4 rounded-lg border border-indigo-500/30 animate-fade-in-down">
                <div class="flex items-start gap-3">
                    <span class="text-2xl">🔧</span>
                    <div class="w-full">
                        <label class="block text-sm font-bold text-indigo-300 mb-1">Mode d'import Outillage</label>
                        <p class="text-[10px] text-gray-400 mb-2">Si le type (Flexo/Hélio) n'est pas précisé dans Excel, forcer en :</p>
                        <select name="default_tool_type" class="w-full bg-slate-900 border border-slate-700 rounded p-2 text-white text-sm">
                            <option value="CYL">🔵 Tout en Hélio (Cylindres)</option>
                            <option value="CLICHE">🟣 Tout en Flexo (Clichés)</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- 3. FICHIER -->
            <div>
                <label class="block text-sm font-bold text-gray-300 mb-2">2. Fichier Excel (.xlsx)</label>
                <div class="relative group">
                    <input type="file" name="excel_file" accept=".xlsx, .xls" required
                           class="block w-full text-sm text-slate-500 file:mr-4 file:py-3 file:px-6 file:rounded-lg file:border-0 file:text-sm file:font-bold file:bg-neon file:text-black hover:file:bg-cyan-300 file:transition cursor-pointer bg-slate-800/50 rounded-lg border border-slate-600 group-hover:border-neon transition"/>
                </div>
            </div>

            <!-- INFO COLONNES -->
            <div class="bg-slate-950/50 p-4 rounded-lg text-sm border border-slate-800">
                <p class="text-neon font-bold mb-1 text-xs uppercase tracking-wider">Colonnes Excel attendues :</p>
                <p id="colList" class="font-mono text-gray-400 text-xs break-words leading-relaxed">Designation, Categorie, Quantite, Unite, Seuil_Min, Prix</p>
            </div>
            
            <button type="submit" class="w-full bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-bold py-4 rounded-lg shadow-lg shadow-cyan-500/20 transition transform active:scale-[0.98]">
                LANCER L'IMPORTATION 🚀
            </button>
        </form>
    </div>
</div>

<script>
    const colMap = {
        'STOCK': 'Designation, Categorie, Quantite, Unite, Seuil_Min, Prix',
        'CRM': 'Nom, Ville, Telephone, Email, Secteur, Statut',
        'TOOLS': 'CODE, CLIENT, DESIGNATIONS, CODE Clyché, CLR, DEV (mm), METRAGE (ML) (+ optionnel: TYPE)',
        'PLANNING': 'OF_Numero, Client, Produit, Machine, Date_Debut, Qte_Prevue'
    };

    function updateUI() {
        const type = document.getElementById('typeSelector').value;
        const toolDiv = document.getElementById('toolOption');
        const helpText = document.getElementById('colList');

        // Mise à jour du texte d'aide
        if(helpText) helpText.innerText = colMap[type];

        // Afficher/Cacher le menu Flexo/Hélio
        if (type === 'TOOLS') {
            toolDiv.classList.remove('hidden');
        } else {
            toolDiv.classList.add('hidden');
        }
    }
    
    // Initialisation au chargement
    document.addEventListener('DOMContentLoaded', updateUI);
</script>

<style>
    /* Petite animation fluide */
    @keyframes fadeInDown {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .animate-fade-in-down {
        animation: fadeInDown 0.3s ease-out forwards;
    }
</style>
{% endblock %}
"""

# Écriture du fichier propre
os.makedirs("templates/stock", exist_ok=True)
with open("templates/stock/import_stock.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("✅ Page d'import entièrement régénérée.")
print("👉 Rafraîchissez votre page web (F5) pour voir la différence.")