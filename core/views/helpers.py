import datetime
import re
import unicodedata

def parse_time_safe(val):
    if val is None or val == 0 or val == '' or str(val).strip() == '':
        return None
    try:
        if hasattr(val, 'hour'): return val
        if hasattr(val, 'time'): return val.time()
        if isinstance(val, float):
            total_seconds = int(val * 24 * 3600)
            return datetime.time(total_seconds // 3600, (total_seconds % 3600) // 60)
        s = str(val).strip().replace('h', ':').replace('H', ':')
        parts = s.split(':')
        if len(parts) >= 2:
            return datetime.time(int(parts[0]), int(parts[1]))
        return None
    except Exception:
        return None

def normalize_header(h):
    if h is None: return ''
    h = str(h).strip()
    h = unicodedata.normalize('NFKD', h).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[\s_]+', '_', h.lower()).strip('_')

COLUMN_CANDIDATES = {
    'Designation': ['designation', 'nom', 'name', 'produit', 'article', 'libelle'],
    'Categorie': ['categorie', 'category', 'type', 'famille', 'type_produit'],
    'Quantite': ['quantite', 'qte', 'stock', 'quantity', 'qte_stock'],
    'Unite': ['unite', 'unit', 'uom'],
    'Seuil_Min': ['seuil_min', 'seuil', 'min', 'seuil_minimum', 'stock_min', 'stock_minimum'],
    'Prix': ['prix', 'prix_unitaire', 'price', 'prix_unite', 'pu'],
}

def build_column_rename_map(columns):
    rename_map = {}
    used_canonicals = set()
    for col in columns:
        norm = normalize_header(col)
        for canonical, aliases in COLUMN_CANDIDATES.items():
            if canonical in used_canonicals: continue
            if norm in aliases:
                rename_map[col] = canonical
                used_canonicals.add(canonical)
                break
    return rename_map

CATEGORY_KEYWORDS = {
    'INK': ['encre', 'ink', 'tinta'],
    'SOLV': ['solvant', 'solv', 'diluant', 'thinner'],
    'GLUE': ['colle', 'glue', 'adhesif', 'adhesive'],
    'FILM': ['film', 'papier', 'support', 'paper', 'bobine'],
}

def detect_material_category(raw_cat, designation):
    def _clean(t):
        return unicodedata.normalize('NFKD', str(t or '')).encode('ascii', 'ignore').decode('ascii').lower()
    
    raw_cat_clean = _clean(raw_cat)
    designation_clean = _clean(designation)
    
    for code, keywords in CATEGORY_KEYWORDS.items():
        if any(k in raw_cat_clean for k in keywords):
            return code, 'colonne Catégorie'
    for code, keywords in CATEGORY_KEYWORDS.items():
        if any(k in designation_clean for k in keywords):
            return code, 'nom du produit (fallback)'
    return 'FILM', 'valeur par défaut (aucune correspondance trouvée)'

def highlight_search(text, query):
    if not query: return text
    pattern = re.compile(f'({re.escape(query)})', re.IGNORECASE)
    return pattern.sub(r'<mark class="bg-yellow-400 text-black px-1 rounded">\1</mark>', text)