"""LOT BAT AUTOFILL — lecture des fiches BAT par l'API Gemini (moteur unique, V1.11).

L'OCR local (RapidOCR) et la lecture colorimétrique sont supprimés : la fiche (PNG, JPEG, WEBP
ou PDF rendu en page) est envoyée à Gemini (clé dans GEMINI_API_KEY, voir bat_vision.py).
Le résultat PRÉ-REMPLIT le formulaire ; rien n'est enregistré avant « Calculer et enregistrer ».
Aucune exception ne remonte : `analyze_bat` retourne toujours un dict (clé 'error' si échec).
"""
import base64
import difflib
import io
import re

from PIL import Image

MAX_BAT_BYTES = 10 * 1024 * 1024


_NAME_INK_TYPE = (
    ('vernis', 'VARNISH'), ('varnish', 'VARNISH'),
    ('blanc', 'WHITE'), ('white', 'WHITE'), ('tiO2', 'WHITE'),
)


def _f(value):
    return float(str(value).replace(',', '.'))


def validate_bat_size(size):
    """True si la taille du fichier BAT est acceptable (non vide, <= 10 Mo)."""
    return 0 < size <= MAX_BAT_BYTES


def ink_type_for(name):
    low = (name or '').lower()
    for key, typ in _NAME_INK_TYPE:
        if key.lower() in low:
            return typ
    return 'COLOR'


def _preview_data_uri(im, max_w=1300):
    try:
        im = im.convert('RGB')
        if im.width > max_w:
            im = im.resize((max_w, int(im.height * max_w / im.width)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format='JPEG', quality=72, optimize=True)
        return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ''


def _render_pdf_pages(data, max_pages=3):
    """Rend les premières pages du PDF (pypdfium2, pip seul) ; [] si indisponible.

    Un PDF vectoriel n'a pas d'image embarquée exploitable (un QR code peut être la
    seule image) : on rend donc toujours la page, qui contient la fiche complète.
    """
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(data)
        out = []
        for i in range(min(len(pdf), max_pages)):
            page = pdf[i]
            wpt = float(page.get_width() or 595)
            scale = min(300.0 / 72.0, 2600.0 / wpt)
            out.append(page.render(scale=scale).to_pil().convert('RGB'))
        return out
    except Exception:
        return []


_BLANC_SYNONYMES = {'blanc', 'blane', 'bianc', 'blancs', 'white', 'banc'}


def _clean_ink_name(text):
    t = re.sub(r'\s+', ' ', (text or '').strip())
    if t.lower() in _BLANC_SYNONYMES:
        return 'BLANC'
    m = re.fullmatch(r'(PANTONE\s?\d+(?:\s?[A-Z]{1,4})?|PMS\s?\d+|Magenta|Yellow|Jaune|Black|Noir|Cyan|Blanc|White|Vernis|Varnish)', t, re.I)
    if m:
        return re.sub(r'\s+', ' ', m.group(1)).strip().upper() if t.upper().startswith(('PANTONE', 'PMS')) else m.group(1).capitalize()
    return None


def _clean_job_name(t):
    t = (t or '').strip().strip('|').strip()
    t = re.sub(r'([a-z])([A-Z])', r'\1 \2', t)        # TwinGAUFRETTE -> Twin GAUFRETTE
    t = re.sub(r'([A-Z]{2,})(\d)', r'\1 \2', t)       # GAUFRETTE20 -> GAUFRETTE 20
    t = re.sub(r'([A-Z]{2,})([a-z])', r'\1 \2', t)     # RIFKUSketchup -> RIFKUS ketchup
    t = _JOB_WORDS_RE.sub(' ', t)                        # Chipsmini -> Chips mini
    return re.sub(r'\s+', ' ', t).strip()


_JOB_WORDS_RE = re.compile(r'(?<=[a-z])(?=(?:(?:mini|chips|ketchup|twin|gaufrette|sauce|pizza|couscous|moyen|hamama|djari|rifkus)\b|fin\b|chor(?=khaled)|khaled))', re.I)


def _apply_width_rule(h):
    """Laize du job = laize TOTALE (film) ; à défaut laize piste × poses en laize."""
    tot = h.get('laize_totale_mm')
    piste = h.get('laize_piste_mm')
    pa = h.get('poses_across') or 1
    if tot:
        h['width_mm'] = tot
    elif piste and pa > 1:
        h['width_mm'] = round(piste * pa, 2)      # poses en laize lues : piste × poses
    return h                                       # sinon : laize totale à saisir (pas de valeur inventée)


def _median(values):
    vals = sorted(values)
    if not vals:
        return 0.0
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0


_CANON_NAMES = ['cyan', 'magenta', 'yellow', 'jaune', 'black', 'noir', 'blanc', 'white', 'vernis', 'varnish']


_RE_DEC_NUM = re.compile(r'(\d+[.,]\d{2,3})')


def _fuzzy_canon(word):
    low = (word or '').lower()
    if low in _CANON_NAMES:
        return low
    m = difflib.get_close_matches(low, _CANON_NAMES, n=1, cutoff=0.74)
    return m[0] if m else None


def _legend_name(text):
    """Nom d'encre lisible lisible ; None si ce n'est pas un nom d'encre."""
    nm = _clean_ink_name(text)
    if nm:
        return nm
    t = re.sub(r'\s+', ' ', (text or '').strip())
    if not t or len(t) > 40:
        return None
    if re.match(r'(?i)^(pantone|pms)\b', t):
        rest = re.sub(r'(?i)^(pantone|pms)\s*', '', t).strip()
        return ('PANTONE ' + rest).strip()
    word = re.sub(r'[^A-Za-z]', '', t)
    if word and ' ' not in t and len(word) >= 4:
        canon = _fuzzy_canon(word)
        if canon:
            return _clean_ink_name(canon) or canon.capitalize()
    return None


def _spaced(text):
    """« BlackC » -> « Black C » ; « Reflex Blue C » inchangé."""
    return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', re.sub(r'\s+', ' ', text or '')).strip()


def _pantone_fmt(nm):
    """« PANTONE 7731C » -> « PANTONE 7731 C » (espace avant le suffixe)."""
    m = re.fullmatch(r'(PANTONE\s*\d+)\s*([A-Za-z]{1,3})', (nm or '').strip(), re.I)
    return f'{m.group(1)} {m.group(2).upper()}' if m else nm


_SUPPLIERS = [('STUDIO', 'Studio Flexo'), ('POLYSLIM', 'Poly Slim'),
              ('YAHIAOUI', 'Yahiaoui Photogravure')]


def _supplier_label(text):
    """Fournisseur de clichés (libellé fixe) reconnu dans un texte ; None sinon."""
    t = re.sub(r'[^A-Z]', '', (text or '').upper())
    for key, label in _SUPPLIERS:
        if key in t:
            return label
    return None


def _api_num(v):
    """Nombre renvoyé par l'IA (nombre ou texte) ; None si absent."""
    if isinstance(v, bool) or v is None or v == '':
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r'\d+(?:[.,]\d+)?', str(v))
    return float(m.group(0).replace(',', '.')) if m else None


def _rows_from_api(data):
    """Lignes couleur depuis la réponse IA (format de la légende).

    Un nom absent reste « à saisir » : aucun nom n'est déduit de la position.
    """
    rows = []
    encres = data.get('encres') or []
    if not isinstance(encres, list):
        return rows
    for i, e in enumerate(encres):
        if not isinstance(e, dict):
            continue
        nom = re.sub(r'\s+', ' ', str(e.get('nom') or '')).strip()
        check = []
        name = _legend_name(nom) if nom else None
        if name is None and nom:
            name = nom
            check.append('nom à vérifier')
        if not name:
            name = f'Encre n°{i + 1} (nom à saisir)'
            check.append('nom illisible : à saisir')
        name = _pantone_fmt(name)
        pct = _api_num(e.get('pourcent'))
        if pct is not None and not 0 <= pct <= 100:
            pct = None
        rows.append({'name': name, 'ink_type': ink_type_for(name),
                     'coverage_percent': pct, 'coverage_area_cm2': _api_num(e.get('cm2')),
                     'swatch_hex': '', 'confidence': 'API_GEMINI', 'values_source': 'API',
                     'check': ' ; '.join(check), 'patch': None})
    return rows


def _hints_from_api(data):
    """Indices job (nom, laize, pas, poses, LPI) depuis la réponse IA."""
    h = {}
    if data.get('nom_job'):
        name = _clean_job_name(str(data['nom_job']))
        if name:
            h['name'] = name
    for key, out in (('laize_piste_mm', 'laize_piste_mm'), ('laize_totale_mm', 'laize_totale_mm'),
                     ('pas_coupe_mm', 'repeat_mm'), ('lpi', 'lineature_lpi')):
        v = _api_num(data.get(key))
        if v:
            h[out] = v
    for key, out in (('poses_en_laize', 'poses_across'), ('poses_en_coupe', 'poses_repeat')):
        v = _api_num(data.get(key))
        if v:
            h[out] = int(v)
    if h.get('laize_totale_mm') and h.get('laize_piste_mm') \
            and abs(h['laize_totale_mm'] - h['laize_piste_mm']) < 1:
        h.pop('laize_totale_mm')
        h['laize_douteuse'] = True
    return _apply_width_rule(h)


def _read_with_api(pages, result):
    """Lecture par Gemini. True si des couleurs ont été lues.

    pages : images à lire, page 1 d'abord (2 pages au plus). En cas d'échec, result['error']
    explique la cause ; aucune couleur n'est inventée.
    """
    from . import bat_vision
    for pg in pages[:2]:
        try:
            data = bat_vision.read_bat(pg)
        except bat_vision.VisionError as exc:
            result['error'] = f'Analyse IA impossible ({exc}). Renseignez les lignes à la main.'
            return False
        rows = _rows_from_api(data)
        if not rows:
            continue
        hints = _hints_from_api(data)
        result['rows'] = rows
        result['job_hints'] = hints
        sup_text = str(data.get('fournisseur_cliches') or '')
        result['cliche_supplier'] = _supplier_label(sup_text) or (sup_text.strip() or None)
        if result['cliche_supplier']:
            result['warnings'].append(f"Fournisseur de clichés lu : {result['cliche_supplier']}. Vérifiez.")
        result['mode'] = (result.get('mode') or 'Image') + ' + IA Gemini'
        n = len(rows)
        expected = _api_num(data.get('nombre_couleurs_annonce'))
        result['warnings'].append(
            f'Lecture IA Gemini : {n} couleur(s)'
            + (f' (la fiche annonce {int(expected)} C)' if expected else '')
            + '. Vérifiez chaque valeur avant « Calculer et enregistrer ».')
        if expected and int(expected) != n:
            result['warnings'].append(
                'Nombre de couleurs différent de la mention « Nbr de couleurs » : vérifiez les lignes.')
        if hints.get('name'):
            result['warnings'].append(f"Job lu par IA : « {hints['name']} ». Vérifiez le nom.")
        if hints.get('laize_douteuse'):
            result['warnings'].append('Laize totale illisible : saisissez la laize totale.')
        elif hints.get('laize_totale_mm'):
            result['warnings'].append(f"Laize totale lue : {hints['laize_totale_mm']:g} mm (toutes pistes).")
        elif hints.get('laize_piste_mm'):
            result['warnings'].append('Laize totale non lue : saisissez-la.')
        pattern = None
        if hints.get('laize_piste_mm') and hints.get('repeat_mm'):
            pattern = hints['laize_piste_mm'] * hints['repeat_mm'] / 100.0
        if pattern:
            for r in rows:
                if r['coverage_area_cm2'] is not None and r['coverage_percent'] is not None:
                    calc = 100.0 * r['coverage_area_cm2'] / pattern
                    if abs(calc - r['coverage_percent']) > 1.0:
                        r['check'] = (r['check'] + ' ; ' if r['check'] else '') + \
                            f"% lu {r['coverage_percent']} incohérent avec la surface (calculé {calc:.1f} %)"
        return True
    result['error'] = ('Gemini n\'a trouvé aucune couleur sur la fiche. '
                       'Vérifiez le fichier ou renseignez les lignes à la main.')
    return False


def analyze_bat(data, filename=''):
    """Analyse une fiche BAT avec Gemini ; retourne toujours un dict (jamais d'exception)."""
    result = {'mode': '', 'source': filename or 'fiche BAT', 'preview_data_uri': '',
              'rows': [], 'job_hints': {}, 'warnings': [], 'cliche_supplier': None}
    if not data:
        result['error'] = 'Fichier vide.'
        return result
    if len(data) > MAX_BAT_BYTES:
        result['error'] = 'Fiche BAT trop lourde (10 Mo max).'
        return result
    from . import bat_vision
    if not bat_vision.api_configured():
        result['error'] = ("Analyse IA indisponible : la variable GEMINI_API_KEY n'est pas définie "
                           "sur le serveur. Renseignez les lignes à la main.")
        return result
    try:
        if data[:5] == b'%PDF-':
            pages = _render_pdf_pages(data)
            if not pages:
                result['error'] = 'PDF illisible : exportez la fiche en PNG ou JPEG.'
                return result
            result['mode'] = 'PDF'
        else:
            im = Image.open(io.BytesIO(data))
            im.load()
            pages = [im]
            result['mode'] = 'Image'
        result['preview_data_uri'] = _preview_data_uri(pages[0])
        _read_with_api(pages, result)
        return result
    except Exception as exc:  # fichier illisible, PDF chiffré…
        result['error'] = f'Lecture impossible : {exc.__class__.__name__}.'
        return result
