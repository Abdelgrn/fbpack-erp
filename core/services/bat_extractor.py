"""LOT BAT AUTOFILL V1 — lecture automatique des fiches BAT (multi-fournisseurs).

Objectif : alimenter automatiquement la « Séparation des couleurs » du Calculateur
de consommation d'encre à partir d'une fiche BAT (PDF texte, PDF scanné ou image).

Stratégie V1.9/V1.10 : API Gemini en premier (core/services/bat_vision.py, clé GEMINI_API_KEY) ;
repli 100 % Python sans clé ou en cas d'échec :
  * PDF avec couche texte  -> extraction du texte (pypdf) : noms de couleurs,
    surfaces cm², couvertures %, plus indices job (laize, pas de coupe, poses…) ;
  * PDF scanné / image     -> extraction colorimétrique des pastilles (Pillow +
    numpy) : détection des plages plates, regroupement connexe, correspondance
    au référentiel (process + Pantone usuels + blanc/vernis) ;
  * dans les deux cas, rien n'est enregistré : le résultat PRÉ-REMPLIT le
    formulaire, l'opérateur valide / corrige puis « Calculer et enregistrer ».

Aucune exception ne remonte : `analyze_bat` retourne toujours un dict
(eventuellement avec la clé 'error').
"""
import base64
import difflib
import io
import math
import re

import numpy as np
from PIL import Image

MAX_BAT_BYTES = 10 * 1024 * 1024

# Référentiel de correspondance colorimétrique (process, Pantone usuels flexo,
# blancs/vernis). Distances tolérées : voir _nearest_name.
REF_COLORS = [
    ('CYAN', (0, 174, 239)),
    ('MAGENTA', (236, 0, 140)),
    ('JAUNE', (255, 242, 0)),
    ('NOIR', (35, 31, 32)),
    ('PANTONE 485 C', (226, 0, 26)),
    ('PANTONE 186 C', (200, 16, 46)),
    ('PANTONE 032 C', (239, 51, 64)),
    ('PANTONE WARM RED C', (255, 0, 124)),
    ('PANTONE RUBINE RED C', (202, 0, 123)),
    ('PANTONE RHODAMINE RED C', (227, 0, 114)),
    ('PANTONE REFLEX BLUE C', (0, 20, 137)),
    ('PANTONE 072 C', (10, 6, 144)),
    ('PANTONE VIOLET C', (68, 0, 153)),
    ('PANTONE 2685 C', (86, 0, 140)),
    ('PANTONE 355 C', (0, 151, 71)),
    ('PANTONE 347 C', (0, 154, 68)),
    ('PANTONE GREEN C', (0, 169, 152)),
    ('PANTONE 3272 C', (0, 177, 146)),
    ('PANTONE ORANGE 021 C', (254, 80, 0)),
    ('PANTONE 151 C', (255, 130, 0)),
    ('PANTONE 1235 C', (255, 184, 0)),
    ('PANTONE BROWN C', (110, 49, 0)),
    ('PANTONE 4695 C', (100, 69, 60)),
    ('PANTONE BLACK C', (45, 41, 38)),
    ('BLEU', (37, 99, 235)),
    ('VERT', (22, 163, 74)),
    ('ROUGE', (227, 30, 36)),
    ('ORANGE', (249, 115, 22)),
    ('VIOLET', (124, 58, 237)),
]
_scale = [1.0]
NEAREST_MAX_DIST = 70.0
PROCESS_REF = [('CYAN', (0, 174, 239)), ('MAGENTA', (236, 0, 140)),
               ('JAUNE', (255, 242, 0)), ('NOIR', (35, 31, 32))]
PROCESS_MAX_DIST = 40.0

_NAME_INK_TYPE = (
    ('vernis', 'VARNISH'), ('varnish', 'VARNISH'),
    ('blanc', 'WHITE'), ('white', 'WHITE'), ('tiO2', 'WHITE'),
)

_RE_AREA = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:cm\s*²|cm\s*\^?\s*2)\b', re.I)
_RE_PCT = re.compile(r'(\d+(?:[.,]\d+)?)\s*%')
_RE_NAME = re.compile(
    r'\b(PANTONE\s?\d+(?:\s?[A-Z]{1,4})?|PMS\s?\d+|Magenta|Yellow|Black|Cyan|'
    r'Blanc|White|Vernis|Varnish|Silver|Argent|Gold|Or)\b', re.I)
_RE_LAIZE = re.compile(r'LAIZE\s*(?:TOTALE)?\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*mm', re.I)
_RE_PAS = re.compile(r'PAS\s+DE\s+COUPE\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*mm', re.I)
_RE_POSES_LAIZE = re.compile(r'POSES\s+EN\s+LAIZE\s*[:=]?\s*(\d+)', re.I)
_RE_POSES_COUPE = re.compile(r'POSES\s+EN\s+COUPE\s*[:=]?\s*(\d+)', re.I)
_RE_LAIZE_PISTE = re.compile(r'LAIZE(?!\s*TOTALE)\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*mm', re.I)
_RE_LAIZE_TOT = re.compile(r'LAIZE\s*TOTALE\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*mm', re.I)
_RE_LPI = re.compile(r'(\d+(?:[.,]\d+)?)\s*LPI', re.I)


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


def _nearest_name(rgb):
    """Nom du référentiel le plus proche, ou None si trop éloigné.
    Passe 1 : process (CMJN) avec tolérance serrée ; passe 2 : référentiel complet."""
    best, best_d = None, 1e9
    for name, ref in PROCESS_REF:
        d = math_dist(rgb, ref)
        if d < best_d:
            best, best_d = name, d
    if best_d <= PROCESS_MAX_DIST:
        return best
    best, best_d = None, 1e9
    for name, ref in REF_COLORS:
        d = math_dist(rgb, ref)
        if d < best_d:
            best, best_d = name, d
    if best_d <= NEAREST_MAX_DIST:
        return best
    return None


def math_dist(a, b):
    # distance RGB pondérée (perception approximative)
    r = (a[0] + b[0]) / 2
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return math.sqrt((2 + r / 256) * dr * dr + 4 * dg * dg + (2 + (255 - r) / 256) * db * db)


def _hex(rgb):
    return '#%02X%02X%02X' % tuple(int(c) for c in rgb[:3])


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


def _swatch_patches(im):
    """Détecte les pastilles BAT : blocs purs + composantes connexes carrées."""
    im = im.convert('RGB')
    orig_w = im.width
    im.thumbnail((900, 900), Image.LANCZOS)
    _scale[:] = [orig_w / max(im.width, 1)]
    arr = np.asarray(im, dtype=np.float32)
    H, W, _ = arr.shape
    b = 6
    hb, wb = H // b, W // b
    if hb < 6 or wb < 6:
        return []
    blocks = arr[:hb * b, :wb * b].reshape(hb, b, wb, b, 3)
    means = blocks.mean(axis=(1, 3))                                   # (hb, wb, 3)
    stds = blocks.reshape(hb, wb, b * b, 3).std(axis=2).mean(axis=-1)  # pureté
    sats = means.max(axis=-1) - means.min(axis=-1)
    lum = means.mean(axis=-1)
    # palier 1 : plages parfaitement plates ; palier 2 : pastilles vives striées
    # (photo) ; palier 3 : pastilles foncées (noirs) au bord légèrement bruité
    pure = (stds < 14) | ((stds < 85) & (sats > 140)) | ((stds < 70) & (lum < 110))
    edge = np.concatenate([means[0], means[-1], means[:, 0], means[:, -1]])
    bg = np.median(edge, axis=0)
    labels = -np.ones((hb, wb), dtype=int)
    patches = []
    nid = 0
    for y in range(hb):
        for x in range(wb):
            if not pure[y, x] or labels[y, x] >= 0:
                continue
            start = means[y, x]
            if np.abs(start - bg).mean() < 26:
                continue
            stack = [(y, x)]
            labels[y, x] = nid
            comp = [(y, x)]
            while stack:
                cy, cx = stack.pop()
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < hb and 0 <= nx < wb and pure[ny, nx] and labels[ny, nx] < 0:
                        if np.abs(means[ny, nx] - start).mean() < 26:
                            labels[ny, nx] = nid
                            stack.append((ny, nx))
                            comp.append((ny, nx))
            size = len(comp)
            total = hb * wb
            if not (max(5, 0.0004 * total) <= size <= 0.12 * total):
                nid += 1
                continue
            ys0 = [c[0] for c in comp]
            xs0 = [c[1] for c in comp]
            # une pastille BAT ne touche jamais les bords de l'image
            if min(ys0) <= 0 or max(ys0) >= hb - 1 or min(xs0) <= 0 or max(xs0) >= wb - 1:
                nid += 1
                continue
            ys = [c[0] for c in comp]
            xs = [c[1] for c in comp]
            h_bl = max(ys) - min(ys) + 1
            w_bl = max(xs) - min(xs) + 1
            # pastille = petite plage quasi carrée (ni bandeau, ni filet, ni fond)
            if not (0.5 <= w_bl / max(h_bl, 1) <= 2.2):
                nid += 1
                continue
            if w_bl > 0.12 * wb or h_bl > 0.12 * hb:
                nid += 1
                continue
            col = np.mean([means[c[0], c[1]] for c in comp], axis=0)
            sat = float(col.max() - col.min())
            lum_c = float(col.mean())
            # gris clair / blancs de fond / teintes délavées de maquette
            if (sat < 12 and lum_c > 120) or (sat < 60 and lum_c > 200):
                nid += 1
                continue
            sc = _scale[0]
            patches.append({
                'x': min(xs), 'y': min(ys), 'w': w_bl,
                'cy': (min(ys) + max(ys)) / 2, 'cx': (min(xs) + max(xs)) / 2,
                'rgb': tuple(int(round(c)) for c in col),
                'ox0': min(xs) * b * sc, 'oy0': min(ys) * b * sc,
                'ox1': (max(xs) + 1) * b * sc, 'oy1': (max(ys) + 1) * b * sc,
            })
            nid += 1
    band = max(4, hb // 14)
    patches.sort(key=lambda p: (round(p['cy'] / band), p['cx']))
    return patches


def _hb_of(im):
    im = im.convert('RGB')
    im.thumbnail((900, 900), Image.LANCZOS)
    return (im.height // 6) * 6 // 6


def rows_from_image(im, patches=None):
    if patches is None:
        patches = _swatch_patches(im)
    # règle structurelle : une rangée de pastilles BAT = plusieurs plages alignées ;
    # les composantes isolées (maquette, logos, textes) sont écartées
    bands = {}
    band_h = 6
    for p in patches:
        bands.setdefault(round(p['cy'] / band_h), []).append(p)
    kept = []
    for key, grp in bands.items():
        if len(grp) >= 2:
            kept.extend(grp)
    patches = kept
    # le tiers haut d'une fiche BAT porte la maquette, jamais les pastilles
    patches = [p for p in patches if p['cy'] >= 0.45 * _hb_of(im)]
    # ombres/filets gris chevauchant une pastille colorée de la même rangée
    def _overlaps(a, b2):
        return abs(a['cx'] - b2['cx']) < max(a['w'], b2['w'])
    drop = set()
    for a in patches:
        sa = max(a['rgb']) - min(a['rgb'])
        la = sum(a['rgb']) / 3
        if sa < 25 and la < 160:
            for b2 in patches:
                sb = max(b2['rgb']) - min(b2['rgb'])
                if b2 is not a and sb > 60 and _overlaps(a, b2):
                    drop.add(id(a))
    patches = [p for p in patches if id(p) not in drop]
    rows, seen = [], set()
    for p in patches:
        rgb = p['rgb']
        name = _nearest_name(rgb)
        if name is None:
            name = 'Couleur BAT ' + _hex(rgb)
        key = (name, round(p['cx'] / 4), round(p['cy'] / 4))
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            'name': name,
            'ink_type': ink_type_for(name),
            'coverage_percent': None,
            'coverage_area_cm2': None,
            'swatch_hex': _hex(rgb),
            'confidence': 'COLORIMETRIC',
            'patch': p,
        })
    return rows


def rows_from_text(text):
    warnings = []
    names = [re.sub(r'\s+', ' ', n).strip().upper() if n.upper().startswith(('PANTONE', 'PMS'))
             else n.strip().capitalize() for n in _RE_NAME.findall(text)]
    areas = [_f(a) for a in _RE_AREA.findall(text)]
    pcts = [p for p in (_f(x) for x in _RE_PCT.findall(text)) if 0 <= p <= 100]
    rows = []
    if names and len(names) == len(areas) == len(pcts):
        for n, a, c in zip(names, areas, pcts):
            rows.append({'name': n, 'ink_type': ink_type_for(n),
                         'coverage_percent': c, 'coverage_area_cm2': a,
                         'swatch_hex': '', 'confidence': 'TEXT'})
    elif names:
        warnings.append(
            'Valeurs chiffrées non appairées automatiquement '
            f'({len(names)} noms, {len(areas)} surfaces, {len(pcts)} %) : '
            'compliquez/corrigez les lignes pré-remplies.')
        for n in names:
            rows.append({'name': n, 'ink_type': ink_type_for(n),
                         'coverage_percent': None, 'coverage_area_cm2': None,
                         'swatch_hex': '', 'confidence': 'TEXT'})
    else:
        warnings.append('Aucun nom de couleur reconnu dans le texte du PDF.')
    return rows, warnings


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


def _bottom_strip(im):
    """Bande basse de la fiche (55 % de la hauteur) : légende, job et laize y sont."""
    return im.crop((0, int(im.height * 0.55), im.width, im.height))


def _first_embedded_image(reader):
    """Plus grande image embarquée de la 1re page (repli si pypdfium2 est absent)."""
    best = None
    try:
        for img in reader.pages[0].images:
            try:
                im = Image.open(io.BytesIO(img.data))
                im.load()
            except Exception:
                continue
            if im.width >= 200 and im.height >= 200:
                if best is None or im.width * im.height > best.width * best.height:
                    best = im
    except Exception:
        return None
    return best


_RE_CM_LOOSE = re.compile(r'(\d+(?:[.,]\d+)?)\.?\s*c[mr]\w*', re.I)
_BLANC_SYNONYMES = {'blanc', 'blane', 'bianc', 'blancs', 'white', 'banc'}


def ocr_available():
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except Exception:
        return False


def _ocr_items(im, crop_bottom=False):
    """Zones OCR (x0, x1, y0, y1, texte) sur l'image ; None si OCR absent.

    L'image entière est lue (la ligne JOB et la légende peuvent être à mi-hauteur sur une
    capture). Au-delà de 2600 px de large, l'image est réduite avant OCR et les zones sont
    ramenées à l'échelle d'origine. crop_bottom=True : bande basse seulement (option).
    """
    if not ocr_available():
        return None
    try:
        W, H = im.size
        y_off = int(H * 0.55) if crop_bottom else 0
        src = im.crop((0, y_off, W, H)) if y_off else im
        k = 1.0
        if src.width > 2600:
            k = src.width / 2600.0
            src = src.resize((2600, int(round(src.height / k))), Image.LANCZOS)
        arr = np.asarray(src.convert('RGB'))[:, :, ::-1]
        res, _ = _get_ocr()(arr)
        items = []
        for box, text, _score in res or []:
            xs = [float(pt[0]) * k for pt in box]
            ys = [float(pt[1]) * k + y_off for pt in box]
            items.append((min(xs), max(xs), min(ys), max(ys), str(text)))
        return items
    except Exception:
        return None


def _ocr_items_merged(im):
    """Image entière + bande basse (si l'image est large), zones fusionnées sans doublon.

    La capture peut porter la légende à mi-hauteur (lecture pleine image) ou en bas
    (ancienne bande basse) : les deux lectures sont combinées.
    """
    full = _ocr_items(im, crop_bottom=False)
    if full is None or im.width <= 1500:
        return full
    if len(legend_rows_from_ocr(full, im.size)[0]) >= 4:   # légende nette : pas de 2e passe (plus rapide)
        return full
    bottom = _ocr_items(im, crop_bottom=True) or []
    merged = list(full)
    for it in bottom:
        cx, cy = (it[0] + it[1]) / 2.0, (it[2] + it[3]) / 2.0
        dup = any(abs(cx - (f[0] + f[1]) / 2.0) < 6 and abs(cy - (f[2] + f[3]) / 2.0) < 6
                  and (f[4] or '').strip() == (it[4] or '').strip() for f in full)
        if not dup:
            merged.append(it)
    return merged


def _clean_ocr_name(text):
    t = re.sub(r'\s+', ' ', (text or '').strip())
    if t.lower() in _BLANC_SYNONYMES:
        return 'BLANC'
    m = re.fullmatch(r'(PANTONE\s?\d+(?:\s?[A-Z]{1,4})?|PMS\s?\d+|Magenta|Yellow|Jaune|Black|Noir|Cyan|Blanc|White|Vernis|Varnish)', t, re.I)
    if m:
        return re.sub(r'\s+', ' ', m.group(1)).strip().upper() if t.upper().startswith(('PANTONE', 'PMS')) else m.group(1).capitalize()
    return None


def pair_ocr_values(rows, ocr_items):
    """Appaire cm² / % lus par OCR sous chaque pastille (colonne par colonne).

    `patches` et `rows` sont alignés (même ordre). Retourne le nombre de lignes
    complétées. Repli global : tri gauche→droite si l'appairage colonne échoue.
    """
    if not ocr_items or not rows:
        return 0
    filled = 0
    for row in rows:
        patch = row.get('patch')
        if not patch:
            continue
        pcx = (patch['ox0'] + patch['ox1']) / 2
        mx = 0.35 * max(patch['ox1'] - patch['ox0'], 1)
        h = max(patch['oy1'] - patch['oy0'], 1)
        # valeurs imprimées SOUS la pastille, dans sa colonne étroite
        col = [it for it in ocr_items
               if patch['ox0'] - mx <= (it[0] + it[1]) / 2 <= patch['ox1'] + mx
               and patch['oy1'] <= it[2] <= patch['oy1'] + 2.5 * h]
        area = pct = None
        for want in ('cm', 'pct'):
            best, best_d = None, 1e9
            for x0, x1, y0, y1, text in col:
                m = (_RE_CM_LOOSE if want == 'cm' else _RE_PCT).search(text)
                if not m:
                    continue
                val = _f(m.group(1))
                if want == 'pct' and not 0 <= val <= 100:
                    continue
                d = abs((x0 + x1) / 2 - pcx)
                if d < best_d:
                    best, best_d = val, d
            if want == 'cm':
                area = best
            else:
                pct = best
        if area is not None or pct is not None:
            row['coverage_area_cm2'] = area
            row['coverage_percent'] = pct
            row['values_source'] = 'OCR'
            filled += 1
    if filled and filled < max(1, len(rows) // 2):
        # repli : ordres de lecture globaux
        areas = [_f(m.group(1)) for _x0, _x1, _y0, _y1, t in sorted(ocr_items, key=lambda i: (i[0]))
                 for m in [_RE_CM_LOOSE.search(t)] if m]
        pcts = [_f(m.group(1)) for _x0, _x1, _y0, _y1, t in sorted(ocr_items, key=lambda i: (i[0]))
                for m in [_RE_PCT.search(t)] if m and 0 <= _f(m.group(1)) <= 100]
        if len(areas) == len(rows) == len(pcts):
            for row, a, c in zip(rows, areas, pcts):
                row['coverage_area_cm2'] = a
                row['coverage_percent'] = c
                row['values_source'] = 'OCR'
            filled = len(rows)
    return filled


def apply_ocr_names(rows, ocr_items):
    """Nomme par OCR les pastilles que la colorimétrie n'avait pas su nommer."""
    if not ocr_items or not rows:
        return 0
    done = 0
    for row in rows:
        patch = row.get('patch')
        if not patch:
            continue
        if not row['name'].startswith('Couleur BAT'):
            continue
        mx = 0.35 * max(patch['ox1'] - patch['ox0'], 1)
        h = max(patch['oy1'] - patch['oy0'], 1)
        col = [it for it in ocr_items
               if patch['ox0'] - mx <= (it[0] + it[1]) / 2 <= patch['ox1'] + mx
               and patch['oy0'] * 0.85 <= it[2] <= patch['oy1'] + 1.5 * h]
        for _x0, _x1, _y0, _y1, text in sorted(col, key=lambda it: it[2]):
            name = _clean_ocr_name(text)
            if name:
                row['name'] = name
                row['ink_type'] = ink_type_for(name)
                done += 1
                break
    return done


def _clean_job_name(t):
    t = (t or '').strip().strip('|').strip()
    t = re.sub(r'([a-z])([A-Z])', r'\1 \2', t)        # TwinGAUFRETTE -> Twin GAUFRETTE
    t = re.sub(r'([A-Z]{2,})(\d)', r'\1 \2', t)       # GAUFRETTE20 -> GAUFRETTE 20
    t = re.sub(r'([A-Z]{2,})([a-z])', r'\1 \2', t)     # RIFKUSketchup -> RIFKUS ketchup
    t = _JOB_WORDS_RE.sub(' ', t)                        # Chipsmini -> Chips mini
    return re.sub(r'\s+', ' ', t).strip()


def _band(y):
    return round(y / 15)


def _right_neighbor(items, zone):
    """Zone la plus proche à droite, sur la même ligne visuelle."""
    b = _band(zone[2])
    cand = [it for it in items if it is not zone and _band(it[2]) == b
            and it[0] >= zone[1] - 5]
    return min(cand, key=lambda it: it[0]) if cand else None


def _num(text):
    m = re.search(r'(\d+(?:[.,]\d+)?)', text or '')
    return _f(m.group(1)) if m else None


_OCR_ENGINE = [None]


def _get_ocr():
    """Moteur RapidOCR mis en cache (chargé une seule fois par processus)."""
    if _OCR_ENGINE[0] is None:
        from rapidocr_onnxruntime import RapidOCR
        _OCR_ENGINE[0] = RapidOCR()
    return _OCR_ENGINE[0]


_RX_LAIZE_PISTE = re.compile(r'\bLAIZE(?!\s*TOTALE)\s*:?', re.I)
_RX_LAIZE_TOT = re.compile(r'\bLAIZE\s*TOTALE\s*:?', re.I)
_RX_PAS = re.compile(r'\bPAS\s*DE\s*COUPE\s*:?', re.I)
_RX_POSES_L = re.compile(r'\bPOSES?\s*EN\s*LAIZE\s*:?', re.I)
_RX_POSES_C = re.compile(r'\bPOSES?\s*EN\s*COUPE\s*:?', re.I)
_RX_JOB = re.compile(r'\bJ\s*O\s*B\s*:', re.I)
_RX_NBR_COULEURS = re.compile(r'NBR\s*DE\s*COULEUR', re.I)
_RX_NB_C = re.compile(r'\s*(\d{1,2})\s*C\s*', re.I)
_LABEL_WORDS = re.compile(
    r'\b(AMALGAME|LAIZE\w*|PAS\s*DE|PORTE|POSES?|NBR|IMPRIMEUR|CLIENT|DOSSIER|'
    r'LINI\w*|SPOT|DIM|CONTINUE|FRONTAL|CELLO|IMPRESSION|INFOGRAPHE|EPAISSEUR)\b', re.I)
# mots fréquents des noms de job : restaure les espaces que l'OCR fusionne
_JOB_WORDS_RE = re.compile(r'(?<=[a-z])(?=(?:(?:mini|chips|ketchup|twin|gaufrette|sauce|pizza|couscous|moyen|hamama|djari|rifkus)\b|fin\b|chor(?=khaled)|khaled))', re.I)


def _is_label_like(text):
    t = (text or '').strip()
    return ':' in t or bool(_LABEL_WORDS.search(t))


def _has_poses(text):
    return 'POSE' in (text or '').upper()


def _cut_name(text):
    """Coupe une valeur de JOB quand l'OCR a fusionné l'étiquette suivante."""
    t = re.split(r'\s+(?:AMALGAME|LAIZE|PAS\s*DE|PORTE|POSES?|NBR)\b', text or '', maxsplit=1, flags=re.I)[0]
    return t.split(':')[0].strip()


def _row_neighbor(items, zone, max_gap=300):
    """Valeur voisine : à droite, même ligne (chevauchement vertical), jamais une étiquette."""
    x1, y0, y1 = zone[1], zone[2], zone[3]
    h = max(y1 - y0, 1)
    best = None
    for it in items:
        if it is zone or _is_label_like(it[4]):
            continue
        ov = min(y1, it[3]) - max(y0, it[2])
        if ov < 0.4 * min(h, max(it[3] - it[2], 1)):
            continue
        if it[0] < x1 - 6 or it[0] - x1 > max_gap:
            continue
        if best is None or it[0] < best[0]:
            best = it
    return best


def _value_crop(im, zone, span=90):
    """Relecture OCR agrandie de la zone juste à droite d'une étiquette (ex. un chiffre isolé)."""
    if im is None:
        return None
    x1, y0, y1 = zone[1], zone[2], zone[3]
    try:
        box = im.crop((int(max(0, x1 + 3)), int(max(0, y0 - 3)),
                       int(min(im.width, x1 + span)), int(min(im.height, y1 + 3))))
        if box.width < 4 or box.height < 4:
            return None
        box = box.convert('RGB').resize((box.width * 4, box.height * 4), Image.LANCZOS)
        res, _ = _get_ocr()(np.asarray(box)[:, :, ::-1])
        for _b, text, _s in res or []:
            v = _num(str(text))
            if v is not None:
                return v
    except Exception:
        return None
    return None


def _labelled_number(items, rx, im=None, max_gap=300, reject=None):
    """Nombre associé à une étiquette : même zone, puis voisine, puis relecture de zone."""
    for zone in items:
        text = zone[4] or ''
        m = rx.search(text)
        if not m or (reject and reject(text)):
            continue
        v = _num(text[m.end():])
        if v is None:
            nb = _row_neighbor(items, zone, max_gap)
            v = _num(nb[4]) if nb else None
        if v is None:
            v = _value_crop(im, zone)
        if v is not None:
            return v
    return None


def _job_name(items, im=None, max_gap=300):
    for zone in items:
        text = zone[4] or ''
        m = _RX_JOB.search(text)
        if not m:
            continue
        tail = _cut_name(text[m.end():])
        if not tail:
            nb = _row_neighbor(items, zone, max_gap)
            tail = _cut_name(nb[4]) if nb else ''
        name = _clean_job_name(tail)
        if (name and not _is_label_like(name)
                and 'KODAK' not in name.upper() and 'FLEXCEL' not in name.upper()):
            return name
    return None


def ocr_job_hints(ocr_items, im=None):
    """Indices job lus par OCR, étiquette par étiquette.

    Ordre de lecture : même zone -> valeur voisine à droite (même ligne, hors étiquettes)
    -> relecture agrandie de la zone à droite. Laize : la laize TOTALE (toutes pistes)
    est retenue pour la surface ; la laize d'une piste reste disponible pour le contrôle.
    """
    hints = {}
    if not ocr_items:
        return hints
    im_w = im.width if im is not None else 1400
    max_gap = max(120.0, 0.25 * im_w)
    name = _job_name(ocr_items, im, max_gap)
    if name:
        hints['name'] = name
    piste = _labelled_number(ocr_items, _RX_LAIZE_PISTE, im, max_gap, reject=_has_poses)
    if piste:
        hints['laize_piste_mm'] = piste
    tot = _labelled_number(ocr_items, _RX_LAIZE_TOT, im, max_gap)
    if tot:
        hints['laize_totale_mm'] = tot
    rep = _labelled_number(ocr_items, _RX_PAS, im, max_gap)
    if rep:
        hints['repeat_mm'] = rep
    pa = _labelled_number(ocr_items, _RX_POSES_L, im, max_gap)
    if pa:
        hints['poses_across'] = int(pa)
    pc = _labelled_number(ocr_items, _RX_POSES_C, im, max_gap)
    if pc:
        hints['poses_repeat'] = int(pc)
    for zone in ocr_items:
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*LPI', zone[4] or '', re.I)
        if m:
            hints['lineature_lpi'] = _f(m.group(1))
            break
    # garde-fou : une « laize totale » égale à la laize d'une piste est une mauvaise lecture
    if hints.get('laize_totale_mm') and hints.get('laize_piste_mm') \
            and abs(hints['laize_totale_mm'] - hints['laize_piste_mm']) < 1:
        hints.pop('laize_totale_mm')
        hints['laize_douteuse'] = True
    _apply_width_rule(hints)
    return hints


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


_DEFAULT_SWATCH = {
    'cyan': (0, 174, 239), 'magenta': (236, 0, 140), 'yellow': (255, 242, 0),
    'jaune': (255, 242, 0), 'black': (35, 31, 32), 'noir': (35, 31, 32),
    'blanc': (255, 255, 255), 'white': (255, 255, 255),
}


_CANON_NAMES = ['cyan', 'magenta', 'yellow', 'jaune', 'black', 'noir', 'blanc', 'white', 'vernis', 'varnish']
_RE_DEC_NUM = re.compile(r'(\d+[.,]\d{2,3})')


def _fuzzy_canon(word):
    low = (word or '').lower()
    if low in _CANON_NAMES:
        return low
    m = difflib.get_close_matches(low, _CANON_NAMES, n=1, cutoff=0.74)
    return m[0] if m else None


def _legend_name(text):
    """Nom d'encre lisible dans une zone OCR ; None si ce n'est pas un nom d'encre."""
    nm = _clean_ocr_name(text)
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
            return _clean_ocr_name(canon) or canon.capitalize()
    return None


def _spaced(text):
    """« BlackC » -> « Black C » ; « Reflex Blue C » inchangé."""
    return re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', re.sub(r'\s+', ' ', text or '')).strip()


def _pantone_fmt(nm):
    """« PANTONE 7731C » -> « PANTONE 7731 C » (espace avant le suffixe)."""
    m = re.fullmatch(r'(PANTONE\s*\d+)\s*([A-Za-z]{1,3})', (nm or '').strip(), re.I)
    return f'{m.group(1)} {m.group(2).upper()}' if m else nm


def legend_rows_from_ocr(items, im_size, hints=None, patches=None):
    """Couleurs lues dans la LÉGENDE : une colonne par valeur cm² / % (la maquette est exclue).

    1. La rangée des valeurs (% et cm²) donne les colonnes : une par encre annoncée.
    2. Le nom de chaque colonne est lu dans la rangée juste au-dessus (PANTONE + ligne suivante
       recollée). Nom illisible : « Encre n°k (nom à saisir) » + avertissement. Jamais de
       nom attribué par position (un nom faux est pire qu'un nom à saisir).
    3. La surface de référence (100 %) = Σ cm² ÷ Σ % × 100 sur les colonnes complètes ;
       elle recalcule les % et corrige les erreurs OCR.
    Retourne (lignes, nombre annoncé sur la fiche ou None). Lignes [] si aucune colonne.
    """
    hints = hints or {}
    if not items:
        return [], None
    pct_items, area_items = [], []
    for it in items:
        t = it[4] or ''
        cx, cy = (it[0] + it[1]) / 2.0, (it[2] + it[3]) / 2.0
        if _RE_PCT.search(t):
            m = _RE_PCT.search(t)
            v = _f(m.group(1))
            if v is not None and 0 <= v <= 100 and not re.search(r'LPI|mm', t, re.I):
                pct_items.append((cx, cy, it, v))
            continue
        if re.search(r'LPI|mm\b|POSE|LAIZE|PAS|COUPE|\d\s*C\b', t, re.I):
            continue
        m = _RE_DEC_NUM.search(t)
        if m and (re.search(r'c', t, re.I) or re.search(r'\d+[.,]\d{3}\b', t)):
            area_items.append((cx, cy, it, _f(m.group(1))))
    if not pct_items and not area_items:
        return [], None
    hgt = max(_median([it[3] - it[2] for it in items]), 8.0)

    # 1. rangée de valeurs : la plus peuplée (% prioritaires)
    base = pct_items or area_items
    rows_v = []
    for c in sorted(base, key=lambda p: p[1]):
        for r in rows_v:
            if abs(r['cy'] - c[1]) <= 0.8 * hgt:
                r['items'].append(c)
                break
        else:
            rows_v.append({'cy': c[1], 'items': [c]})
    best = max(rows_v, key=lambda r: (len(r['items']), -r['cy']))
    row_cy = _median([c[1] for c in best['items']])
    pct_row = [c for c in pct_items if abs(c[1] - row_cy) <= 2.2 * hgt]
    area_row = [c for c in area_items if abs(c[1] - row_cy) <= 2.2 * hgt]

    # 2. colonnes = positions x des valeurs de la rangée
    xs = sorted([c[0] for c in pct_row] + [c[0] for c in area_row])
    xp = sorted(c[0] for c in (pct_row or area_row))   # espacement calculé sur les % (une par colonne)
    gaps = [b - a for a, b in zip(xp, xp[1:]) if b - a > 2]
    spacing = _median(gaps) if gaps else max(hgt * 4.5, 40.0)
    cols = []
    for x in xs:
        if cols and x - cols[-1][-1] < 0.45 * spacing:
            cols[-1].append(x)
        else:
            cols.append([x])
    centres = [sum(c) / len(c) for c in cols]
    half = 0.5 * spacing
    col_area = [None] * len(centres)
    col_pct = [None] * len(centres)
    for cx, _cy, _it, v in area_row:
        k = min(range(len(centres)), key=lambda i: abs(centres[i] - cx))
        if abs(centres[k] - cx) <= half and col_area[k] is None:
            col_area[k] = v
    for cx, _cy, _it, v in pct_row:
        k = min(range(len(centres)), key=lambda i: abs(centres[i] - cx))
        if abs(centres[k] - cx) <= half and col_pct[k] is None:
            col_pct[k] = v

    # 3. noms : zone de noms juste au-dessus de la rangée de valeurs
    name_items = []
    for it in items:
        cy = (it[2] + it[3]) / 2.0
        if row_cy - 4.0 * hgt <= cy < row_cy - 0.3 * hgt:
            nm = _legend_name(it[4])
            if nm:
                name_items.append(((it[0] + it[1]) / 2.0, cy, it, nm))
    cont_items = []
    for it in items:
        cy = (it[2] + it[3]) / 2.0
        t = (it[4] or '').strip()
        if row_cy - 4.0 * hgt <= cy < row_cy - 0.3 * hgt and t and not _RE_PCT.search(t) \
                and not _RE_DEC_NUM.search(t):
            cont_items.append(((it[0] + it[1]) / 2.0, cy, it, t))

    rows = []
    for i, cx in enumerate(centres):
        name = None
        cand = [n for n in name_items if abs(n[0] - cx) <= half]
        if cand:
            cxn, cyn, _it, nm = min(cand, key=lambda n: abs(n[0] - cx))
            if nm.upper() == 'PANTONE' or nm.upper().endswith('PANTONE'):
                tail = [c for c in cont_items if abs(c[0] - cx) <= half and c[1] > cyn]
                if tail:
                    nm = ('PANTONE ' + _spaced(min(tail, key=lambda c: c[1])[3])).strip()
            elif re.fullmatch(r'PANTONE\s*\d+\s*[A-Za-z]{0,3}', nm, re.I):
                # « PANTONE234 » / « PANTONE7731C » : espaces rétablis ; sinon suffixe lu sous le nom
                m = re.fullmatch(r'PANTONE\s*(\d+)\s*([A-Za-z]{0,3})', nm, re.I)
                base, suffix = m.group(1), m.group(2).upper()
                if not suffix:
                    tail = [c for c in cont_items if abs(c[0] - cx) <= half and c[1] > cyn
                            and len(c[3].strip()) <= 4]
                    suffix = _spaced(min(tail, key=lambda c: c[1])[3]).upper() if tail else ''
                nm = ('PANTONE ' + base + (' ' + suffix if suffix else '')).strip()
            name = _pantone_fmt(nm)
        check = []
        if name is None:
            name = f'Encre n°{i + 1} (nom à saisir)'
            check.append('nom illisible : à saisir')
        elif name.upper().startswith('PANTONE'):
            check.append('vérifiez le numéro Pantone lu par OCR')
        rows.append({'name': name, 'ink_type': ink_type_for(name), 'cx': cx,
                     'area': col_area[i], 'pct': col_pct[i], 'check': check})

    # 4. surface de référence = médiane cm² / % (colonnes complètes)
    full = [r for r in rows if r['area'] is not None and r['pct'] not in (None, 0)]
    pattern = None
    if full:
        # une valeur % mal lue ne doit pas fausser le motif : on écarte les lignes dont
        # cm² / % s'écarte de plus de 3 % de la médiane, puis Σ cm² ÷ Σ % sur le reste
        ratio = {id(r): r['area'] / r['pct'] * 100.0 for r in full}
        med = _median(list(ratio.values()))
        inliers = [r for r in full if abs(ratio[id(r)] - med) <= 0.03 * med] or full
        pattern = sum(r['area'] for r in inliers) / sum(r['pct'] for r in inliers) * 100.0
    if pattern is None:
        piste, pas = hints.get('laize_piste_mm'), hints.get('repeat_mm')
        if piste and pas:
            pattern = piste * pas / 100.0
    if pattern:
        for r in rows:
            if r['area'] is not None:
                calc = 100.0 * r['area'] / pattern
                if r['pct'] is None or abs(r['pct'] - calc) > 0.02:
                    if r['pct'] is not None:
                        r['check'].append(f"% OCR {r['pct']} corrigé d'après la surface")
                    r['pct'] = round(calc, 2)
            elif r['pct'] is not None:
                r['area'] = round(pattern * r['pct'] / 100.0, 3)

    # 5. numéros de colonnes de l'annonce « Nbr de couleurs » (8 C)
    expected = None
    for it in items:
        m = _RX_NB_C.fullmatch(it[4] or '')
        if m:
            expected = int(m.group(1))
            break

    # 6. pastilles couleur (pixels) juste au-dessus de chaque colonne
    y_top = row_cy - 1.5 * hgt
    out = []
    for r in rows:
        best_p, best_d = None, None
        for p in patches or []:
            pcx = (p['ox0'] + p['ox1']) / 2
            pcy = (p['oy0'] + p['oy1']) / 2
            d = abs(pcx - r['cx'])
            if d < half and y_top - 3.5 * hgt <= pcy <= y_top:
                if best_d is None or d < best_d:
                    best_p, best_d = p, d
        rgb = best_p['rgb'] if best_p else _DEFAULT_SWATCH.get(r['name'].lower())
        out.append({
            'name': r['name'], 'ink_type': r['ink_type'],
            'coverage_percent': r['pct'], 'coverage_area_cm2': r['area'],
            'swatch_hex': _hex(rgb) if rgb else '',
            'confidence': 'LEGENDE_OCR', 'values_source': 'OCR',
            'check': ' ; '.join(r['check']), 'patch': None,
        })
    return out, expected


def job_hints_from_text(text):
    hints = {}
    m = _RE_PAS.search(text)
    if m:
        hints['repeat_mm'] = _f(m.group(1))
    m = _RE_LAIZE_PISTE.search(text)
    if m:
        hints['laize_piste_mm'] = _f(m.group(1))
    m = _RE_LAIZE_TOT.search(text)
    if m:
        hints['laize_totale_mm'] = _f(m.group(1))
    m = _RE_POSES_LAIZE.search(text)
    if m:
        hints['poses_across'] = int(m.group(1))
    m = _RE_POSES_COUPE.search(text)
    if m:
        hints['poses_repeat'] = int(m.group(1))
    m = _RE_LPI.search(text)
    if m:
        hints['lineature_lpi'] = _f(m.group(1))
    return _apply_width_rule(hints)


_PROCESS_NAMES = {'CYAN', 'MAGENTA', 'JAUNE', 'NOIR', 'BLANC'}


def _bottom_band_rows(rows, im):
    """Repli sans légende lisible : encres process seulement, dans le bandeau bas.

    La maquette occupe le haut de la page ; seules les encres process (nom exact) sont
    gardées, jamais les tons Pantone ou « Couleur BAT » issus de l'illustration.
    """
    h = max(im.height, 1)
    keep = []
    for r in rows:
        p = r.get('patch')
        if (r.get('name', '').upper() in _PROCESS_NAMES and p
                and (p['oy0'] + p['oy1']) / 2.0 >= 0.70 * h):
            keep.append(r)
    return keep


def _enrich_ocr(im, result, items):
    """Complète lignes et indices job via OCR optionnelle (rapidocr-onnxruntime).

    im : image sur laquelle les zones OCR ont été lues (bande basse pour un PDF rendu).
    Priorité : légende de la fiche (7 C annoncées) ; repli sur les pastilles seulement
    si la légende n'est pas repérée, avec avertissement explicite.
    """
    if items is None:
        result['rows'] = _bottom_band_rows(result['rows'], im)
        result['warnings'].append(
            'Option OCR non installée : seules les encres process du bandeau bas sont proposées, '
            'surfaces/couvertures à saisir. (pip install rapidocr-onnxruntime pour lecture automatique.)')
        return
    sup = _supplier_label(' '.join(str(it[4]) for it in items))
    if sup:
        result['cliche_supplier'] = sup
        result['warnings'].append(f'Fournisseur de clichés lu : {sup}. Vérifiez.')
    ocr_hints = ocr_job_hints(items, im)
    if ocr_hints:
        merged = dict(ocr_hints)
        merged.update(result.get('job_hints') or {})   # le texte PDF reste prioritaire
        result['job_hints'] = merged
    hints = result.get('job_hints') or {}
    legend, expected = legend_rows_from_ocr(items, im.size, hints, _swatch_patches(im))
    if legend:
        result['rows'] = legend
        n = len(legend)
        result['warnings'].append(
            f'Légende lue sur la fiche : {n} couleur(s)'
            + (f' (la fiche annonce {expected} C)' if expected else '')
            + '. Valeurs cm² / % lues par OCR : vérifiez avant « Calculer et enregistrer ».')
        if expected and expected != n:
            result['warnings'].append(
                'Nombre de couleurs différent de la mention « Nbr de couleurs » : '
                'vérifiez les lignes (une couleur peut manquer ou être en trop).')
        for r in legend:
            if r.get('check'):
                result['warnings'].append(f"{r['name']} : {r['check']}.")
    else:
        # légende illisible : seules les encres process du bandeau bas sont proposées
        result['rows'] = _bottom_band_rows(result['rows'], im)
        result['warnings'].append(
            'Légende non lisible automatiquement : seules les encres process repérées en bas '
            'de fiche sont proposées (aucun ton de maquette). Complétez les Pantone et le blanc, '
            'ou envoyez une image plus nette / le PDF d’origine.')
    if hints.get('name'):
        result['warnings'].append(
            f"Job lu par OCR : « {hints['name']} ». Vérifiez le nom avant d'enregistrer.")
    if hints.get('laize_totale_mm'):
        result['warnings'].append(
            f"Laize totale lue : {hints['laize_totale_mm']:g} mm (toutes pistes). "
            'La surface et le métrage utilisent cette laize.')
    if hints.get('laize_douteuse'):
        result['warnings'].append('Laize totale illisible (lue égale à une piste) : saisissez la laize totale.')
    elif hints.get('laize_piste_mm') and not hints.get('width_mm'):
        result['warnings'].append(
            f"Laize totale non lue : saisissez-la (laize d'une piste lue : {hints['laize_piste_mm']:g} mm).")
    elif hints.get('laize_piste_mm') and hints.get('width_mm'):
        result['warnings'].append(
            f"Laize d'une piste : {hints['laize_piste_mm']:g} mm ; laize totale calculée : "
            f"{hints['width_mm']:g} mm (piste × poses). Vérifiez.")

    tot, pis = hints.get('laize_totale_mm'), hints.get('laize_piste_mm')
    if tot and pis:
        pa = hints.get('poses_across')
        if pa != round(tot / pis):
            result['warnings'].append(
                f"Laize totale {tot:g} mm = {tot / pis:g} × {pis:g} mm : poses en laize "
                f"{'non lues' if not pa else 'lues ' + str(pa)} — vérifiez et saisissez les poses.")


def _pick_legend_page(pages):
    """Retourne (page, bande basse, zones OCR) de la 1re page dont la légende est lisible.

    Sinon la 1re page. Le OCR de chaque page n'est fait qu'une fois.
    """
    first = None
    for pg in pages:
        strip = _bottom_strip(pg)
        items = _ocr_items(strip, crop_bottom=False)
        if first is None:
            first = (pg, strip, items)
        if items and legend_rows_from_ocr(items, strip.size)[0]:
            return pg, strip, items
    return first


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
    """Lignes couleur depuis la réponse IA (même format que la légende OCR).

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
    """Lecture par l'API Gemini (GEMINI_API_KEY). True si des couleurs ont été lues.

    pages : images à lire, page 1 d'abord (2 pages au plus). Sans clé ou en cas d'erreur,
    retourne False et l'analyse locale (OCR) prend le relais, avec un avertissement.
    """
    from . import bat_vision
    if not pages or not bat_vision.api_configured():
        return False
    for pg in pages[:2]:
        try:
            data = bat_vision.read_bat(pg)
        except bat_vision.VisionError as exc:
            result['warnings'].append(f'IA Gemini indisponible ({exc}) : lecture locale utilisée.')
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
    result['warnings'].append('IA Gemini : aucune encre trouvée sur la fiche : lecture locale utilisée.')
    return False


def analyze_bat(data, filename=''):
    """Analyse une fiche BAT ; retourne un dict jamais levant d'exception."""
    result = {'mode': '', 'source': filename or 'fiche BAT', 'preview_data_uri': '',
              'rows': [], 'job_hints': {}, 'warnings': [], 'cliche_supplier': None}
    if not data:
        result['error'] = 'Fichier vide.'
        return result
    if len(data) > MAX_BAT_BYTES:
        result['error'] = 'Fiche BAT trop lourde (10 Mo max).'
        return result
    head = data[:5]
    try:
        if head == b'%PDF-':
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
            text = '\n'.join((page.extract_text() or '') for page in reader.pages)
            if text.strip() and _RE_NAME.search(text):
                result['mode'] = 'PDF texte'
                # V1.11 : l'IA passe en premier aussi pour les PDF avec texte (règle identique aux autres
                # fiches). Sans clé, ou si l'IA échoue (avertissement ajouté), la lecture texte reprend.
                from . import bat_vision
                if bat_vision.api_configured():
                    pages = _render_pdf_pages(data)
                    if pages and _read_with_api(pages, result):
                        result['preview_data_uri'] = _preview_data_uri(pages[0])
                        return result
                    result['mode'] = 'PDF texte'
                rows, warnings = rows_from_text(text)
                result['rows'] = rows
                result['warnings'] = result.get('warnings', []) + warnings  # garde l'avis IA éventuel
                result['job_hints'] = job_hints_from_text(text)
                im = _first_embedded_image(reader)
                if im is not None:
                    result['preview_data_uri'] = _preview_data_uri(im)
                    if not rows:
                        result['rows'] = rows_from_image(im)
                        result['mode'] = 'PDF texte + pastilles'
                return result
            pages = _render_pdf_pages(data)
            if pages:
                result['mode'] = 'PDF scanné'
                result['preview_data_uri'] = _preview_data_uri(pages[0])
                # V1.11 : page entière (la légende des couleurs peut être en haut, comme sur la fiche
                # Yahiaoui) ; la bande basse ne servait qu'au repli OCR.
                if _read_with_api(pages, result):
                    return result
                page, strip, items = _pick_legend_page(pages)
                result['preview_data_uri'] = _preview_data_uri(page)
                result['rows'] = rows_from_image(strip)
                _enrich_ocr(strip, result, items)
                return result
            im = _first_embedded_image(reader)     # pypdfium2 absent : plus grande image
            if im is None:
                result['error'] = ('PDF illisible (rendu et image indisponibles) : '
                                   'exportez la fiche en PNG/JPEG ou installez pypdfium2.')
                return result
            result['mode'] = 'PDF scanné'
            result['preview_data_uri'] = _preview_data_uri(im)
            result['rows'] = rows_from_image(im)
            _enrich_ocr(im, result, _ocr_items_merged(im))
            return result
        im = Image.open(io.BytesIO(data))
        im.load()
        result['mode'] = 'Image'
        result['preview_data_uri'] = _preview_data_uri(im)
        if _read_with_api([im], result):
            return result
        result['rows'] = rows_from_image(im)
        _enrich_ocr(im, result, _ocr_items_merged(im))
        return result
    except Exception as exc:  # fichier illisible, PDF chiffré…
        result['error'] = f'Lecture impossible : {exc.__class__.__name__}.'
        return result
