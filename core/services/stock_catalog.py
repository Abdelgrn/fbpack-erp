"""Règles du catalogue articles du module Stock (principe du fichier LISTE_D_ARTICLE.xlsx).

Un article = N°.Produit + Désignation + Unité + Dépôt + Famille + Sous Famille.
La quantité d'un article est toujours exprimée dans SON unité (KG, U, SAC, ML, ETQ...).
Les caractéristiques « bobine » (laize, micronage, métrage, poids par article) ne sont
exigées que pour les articles au kilo qui sont réellement des films / papiers / alu.

Ce module est du Python pur (aucun import Django) pour rester testable et sans effet de bord.
"""
import re
import unicodedata

# Libellés d'unité du classeur ramenés à la valeur du catalogue (clé normalisée -> libellé).
UNIT_ALIASES = {
    'etiquette': 'ETQ', 'etiquettes': 'ETQ', 'etq': 'ETQ',
    'pce': 'Pièce', 'pc': 'Pièce', 'piece': 'Pièce', 'pieces': 'Pièce',
    '1': 'U', 'unite': 'U', 'unites': 'U', 'u': 'U',
    'kgs': 'KG', 'kg': 'KG',
    'boite': 'Boîte', 'boites': 'Boîte',
    'sacs': 'SAC', 'sac': 'SAC',
}

MASS_UNIT_KEYS = {'kg', 'kgs'}

# Familles du classeur qui ne sont PAS des bobines de film/papier même si l'unité est le kilo.
NON_ROLL_FAMILY_KEYS = {
    'fournitures', 'outilsdimpression', 'piecesderechange', 'instrumentation',
    'etiquettes', 'polymeres', 'gaineperforee', 'colle', 'encres', 'solvants', 'vernis',
}

# Famille -> catégorie technique historique (FILM / INK / GLUE / SOLV).
FAMILY_TO_CATEGORY = {
    'encres': 'INK', 'vernis': 'INK',
    'colle': 'GLUE',
    'solvants': 'SOLV',
}


def key(value):
    """Clé de comparaison : sans accents, minuscules, lettres et chiffres uniquement."""
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]', '', text)


def clean_cell(value):
    """Texte d'une cellule Excel : espaces rognés, 123.0 -> '123'."""
    if value is None or (isinstance(value, float) and value != value):
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return re.sub(r'\s+', ' ', str(value)).strip()


def canonical_unit_name(raw):
    """Unité du classeur -> libellé normalisé ('' si vide)."""
    text = clean_cell(raw)
    if not text:
        return ''
    return UNIT_ALIASES.get(key(text), text)


def is_mass_unit(unit):
    return key(unit) in MASS_UNIT_KEYS


def technical_category(famille='', sous_famille='', designation='', raw_category=''):
    """Catégorie technique d'un article à partir du catalogue (et non d'un choix manuel)."""
    raw = key(raw_category)
    if raw in {'encre', 'encres', 'ink'}:
        return 'INK'
    if raw in {'colle', 'glue'}:
        return 'GLUE'
    if raw in {'solvant', 'solvants', 'solv'}:
        return 'SOLV'
    if raw in {'film', 'filmpapier', 'papier'}:
        return 'FILM'
    fam = key(famille)
    if fam in FAMILY_TO_CATEGORY:
        return FAMILY_TO_CATEGORY[fam]
    if not fam:
        # Famille absente du classeur : on se base sur la désignation.
        name = key(designation)
        if name.startswith('encre'):
            return 'INK'
        if name.startswith('colle') or name.startswith('durcisseur'):
            return 'GLUE'
        if name.startswith('solvant'):
            return 'SOLV'
    return 'FILM'


def needs_film_specs(category, famille='', unit='KG'):
    """Laize / micronage / métrage exigés ? Uniquement film-papier-alu vendus au kilo."""
    if category != 'FILM':
        return False
    if not is_mass_unit(unit):
        return False
    return key(famille) not in NON_ROLL_FAMILY_KEYS


def default_unit(category, famille=''):
    """Unité par défaut quand la cellule Unité du classeur est vide."""
    fam = key(famille)
    if fam in {'fournitures', 'outilsdimpression', 'piecesderechange', 'instrumentation', 'etiquettes'}:
        return 'U'
    return 'KG'


_LAIZE_RE = re.compile(r'(?<![\d.,])(\d{2,4})\s*MM\b', re.IGNORECASE)
_LAIZE_WORD_RE = re.compile(r'LAIZE\s*:?\s*(\d{2,4})', re.IGNORECASE)
_MICRON_RE = re.compile(r'(?<![\d.,])(\d{1,3})\s*(?:MICRONS?|MIC|\u00b5M?)(?![A-Za-z])', re.IGNORECASE)


def parse_film_dimensions(designation):
    """Laize (mm) et micronage (µm) lus dans une désignation.

    « BOPP METALLISE BIAXIAL 760MM 20MIC » -> (760, 20). Valeur absente -> None.
    """
    text = str(designation or '')
    laize = micronage = None
    match = _LAIZE_RE.search(text) or _LAIZE_WORD_RE.search(text) or _PAPER_LAIZE_RE.search(text)
    if match and 20 <= int(match.group(1)) <= 2500:
        laize = int(match.group(1))
    match = _MICRON_RE.search(text)
    if match and 5 <= int(match.group(1)) <= 500:
        micronage = int(match.group(1))
    return laize, micronage


_GRAMMAGE_RE = re.compile(r'(?<![\d.,])(\d{2,3})\s*(?:G/M2|GR/M2|GRS|GR|G)(?![A-Za-z])', re.IGNORECASE)
_PAPER_LAIZE_RE = re.compile(r'(?<![\d.,])\d{2,3}\s*G[RS]?\s*/\s*(\d{3,4})(?!\d)', re.IGNORECASE)


def parse_grammage(designation):
    """Grammage (g/m²) lu dans une désignation de papier : « 90G », « 80 GRS », « 50G/830 »."""
    match = _GRAMMAGE_RE.search(str(designation or ''))
    if match and 20 <= int(match.group(1)) <= 400:
        return int(match.group(1))
    return None


def is_paper(famille='', sous_famille='', designation=''):
    """Papier (laize + grammage) plutôt que film (laize + micronage)."""
    fam = key(famille)
    if fam == 'papier':
        return True
    if fam:
        return False
    name = key(designation)
    return name.startswith('papier') or name.startswith('paper')
