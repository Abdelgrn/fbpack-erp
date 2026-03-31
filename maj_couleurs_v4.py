import os
import re

print("🎨 Mise à jour : Gestion des Couleurs et Calculs Précis...")

# --- 1. MODIFICATION DE MODELS.PY (Ajout du champ Couleurs) ---
models_path = "core/models.py"
with open(models_path, "r", encoding="utf-8") as f:
    content = f.read()

# On ajoute le champ num_colors dans TechnicalProduct si pas déjà présent
if "num_colors =" not in content:
    target = "cut_length_mm = models.FloatField(\"Pas de coupe (mm)\", default=0)"
    new_line = f"\n    {target}\n    num_colors = models.IntegerField(\"Nb Couleurs\", default=0)"
    content = content.replace(target, new_line)
    
    with open(models_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ Champ 'Nb Couleurs' ajouté au modèle.")
else:
    print("ℹ️ Champ 'Nb Couleurs' déjà présent.")

# --- 2. MODIFICATION DE VIEWS.PY (Logique d'Import Améliorée) ---
views_path = "core/views.py"

# Le nouveau code pour la section TOOLS uniquement
new_tools_logic = """
            # --- 3. IMPORT OUTILLAGE (CYLINDRES & CLICHES) ---
            elif import_type == 'TOOLS':
                import re
                for _, row in df.iterrows():
                    # A. Récupération des Données Excel
                    code_interne = row.get('CODE')
                    client_name = row.get('CLIENT')
                    designation = row.get('DESIGNATIONS')
                    serial = row.get('CODE Clyché') # Le numéro de série du cylindre/cliché
                    
                    # B. Nettoyage Nombre de Couleurs (ex: "8 clrs" -> 8)
                    raw_clr = str(row.get('CLR', '0'))
                    try:
                        # On cherche le premier nombre trouvé dans le texte
                        nb_colors = int(re.search(r'\d+', raw_clr).group())
                    except:
                        nb_colors = 0
                    
                    # C. Données techniques pour calcul
                    dev_mm = row.get('DEV (mm)', 0)
                    metrage_ml = row.get('METRAGE (ML)', 0)
                    
                    # D. Création/Lien Client
                    client, _ = Client.objects.get_or_create(name=client_name, defaults={'city': 'Inconnue', 'phone': '-'})

                    # E. Création Produit Technique avec Couleurs
                    product, _ = TechnicalProduct.objects.get_or_create(
                        ref_internal=code_interne,
                        defaults={
                            'name': designation,
                            'client': client,
                            'structure_type': 'MONO',
                            'width_mm': row.get('LAIZE', 0),
                            'cut_length_mm': dev_mm,
                            'num_colors': nb_colors # <--- On sauvegarde le nombre de couleurs
                        }
                    )
                    # Si le produit existait déjà, on met à jour ses couleurs et dev
                    product.num_colors = nb_colors
                    product.cut_length_mm = dev_mm
                    product.save()

                    # F. LE CALCUL D'USURE (Formule: ML / (DEV_mm * 0.001))
                    tours_calcules = 0
                    try:
                        dev_float = float(dev_mm)
                        metrage_float = float(metrage_ml)
                        if dev_float > 0:
                            tours_calcules = int(metrage_float / (dev_float * 0.001))
                    except:
                        tours_calcules = 0

                    # G. Mise à jour de l'outil (Cylindre/Cliché)
                    # On suppose que c'est un Cylindre Hélio par défaut vu le fichier, 
                    # mais le code marche pareil pour un cliché Flexo si les colonnes sont les mêmes.
                    Tooling.objects.update_or_create(
                        serial_number=serial,
                        defaults={
                            'product': product,
                            'tool_type': 'CYL', 
                            'current_impressions': tours_calcules,
                            'max_impressions': 2000000 # Durée de vie standard (modifiable)
                        }
                    )
                    count += 1
"""

# Injection chirurgicale dans views.py
with open(views_path, "r", encoding="utf-8") as f:
    full_view = f.read()

# On repère le bloc TOOLS et on le remplace
start_marker = "# --- 3. IMPORT OUTILLAGE"
end_marker = "# --- 4. IMPORT PLANNING ---"

if start_marker in full_view and end_marker in full_view:
    # On découpe
    part1 = full_view.split(start_marker)[0]
    part2 = full_view.split(end_marker)[1]
    
    # On recolle avec le nouveau code au milieu
    final_content = part1 + new_tools_logic + "\n            " + end_marker + part2
    
    with open(views_path, "w", encoding="utf-8") as f:
        f.write(final_content)
    print("✅ Logique de calcul et extraction couleurs (CLR) mise à jour.")
else:
    print("⚠️ Impossible de remplacer le code automatiquement. markers introuvables.")


# --- 3. MODIFICATION DE ADMIN.PY (Pour voir les couleurs) ---
admin_path = "core/admin.py"
with open(admin_path, "r", encoding="utf-8") as f:
    adm_content = f.read()

if "num_colors" not in adm_content:
    # On ajoute le champ dans l'affichage admin
    adm_content = adm_content.replace("'structure_type', 'proforma_image'", "'structure_type', 'num_colors', 'proforma_image'")
    with open(admin_path, "w", encoding="utf-8") as f:
        f.write(adm_content)
    print("✅ Interface Admin mise à jour.")

# --- 4. MISE À JOUR INSTRUCTIONS HTML ---
html_path = "templates/stock/import_stock.html"
with open(html_path, "r", encoding="utf-8") as f:
    html_c = f.read()
    
new_js = "'TOOLS': 'CODE, CLIENT, DESIGNATIONS, CODE Clyché, CLR, DEV (mm), METRAGE (ML)',"
# On remplace l'ancienne ligne JS par la nouvelle qui inclut CLR
# (On utilise une regex simple pour remplacer la ligne TOOLS quelle qu'elle soit)
html_c = re.sub(r"'TOOLS': .+,", new_js, html_c)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_c)
print("✅ Instructions HTML (colonne CLR ajoutée).")

print("\n⚠️ ACTION REQUISE :")
print("Comme nous avons modifié la structure de la base de données (ajout Nb Couleurs),")
print("vous devez exécuter ces commandes dans le terminal :")
print("1. python manage.py makemigrations")
print("2. python manage.py migrate")
print("3. python manage.py runserver")