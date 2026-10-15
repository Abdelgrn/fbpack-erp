"""Lecture OCR des fiches BAT (RapidOCR, sans API, sans Tesseract).

Principe :
1. rendu de la fiche (PDF -> page, image -> image) ;
2. recherche du cartouche technique (bandeau haut ou bas) par mots-clés ;
3. OCR du cartouche seul (mémoire maîtrisée) ;
4. extraction des champs par expressions régulières tolérantes ;
5. colonnes d'encre rattachées par position horizontale (nom / cm² / %) ;
6. contrôle croisé : cm² = % × laize × pas de coupe (à 3 % près).
Tout ce qui n'est pas lu reste vide ; rien n'est inventé.
"""
import difflib
import re

import numpy as np
from PIL import Image

_ENGINE = None


def _engine():
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR()
    return _ENGINE


def _num(s):
    return float(str(s).replace(',', '.'))


def ocr_boxes(img):
    """Liste de boîtes OCR : texte, centre, hauteur, confiance."""
    res, _ = _engine()(np.array(img.convert('RGB')))
    out = []
    for box, txt, conf in (res or []):
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        out.append({'t': str(txt).strip(), 'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1,
                    'xc': (x0 + x1) / 2, 'yc': (y0 + y1) / 2, 'h': max(1.0, y1 - y0),
                    'c': float(conf)})
    return out


def group_lines(boxes):
    """Regroupe les boîtes en lignes (même bande verticale), triées de gauche à droite."""
    lines = []
    for b in sorted(boxes, key=lambda b: b['yc']):
        for ln in lines:
            if abs(ln['yc'] - b['yc']) < 0.55 * max(ln['h'], b['h']):
                ln['items'].append(b)
                ln['yc'] = sum(i['yc'] for i in ln['items']) / len(ln['items'])
                ln['h'] = max(ln['h'], b['h'])
                break
        else:
            lines.append({'yc': b['yc'], 'h': b['h'], 'items': [b]})
    for ln in lines:
        ln['items'].sort(key=lambda i: i['x0'])
        ln['text'] = ' '.join(i['t'] for i in ln['items'])
    return sorted(lines, key=lambda l: l['yc'])


# ---------------------------------------------------------------- cartouche
_ANCHOR_RE = re.compile(r'(LAIZE|DOSSIER|IMPRIMEUR|PAS\s*DE\s*COUPE|couleurs|Nbr\s*de|CLIENT|LINI|EPAISSEUR)', re.I)


def _anchor_score(boxes):
    return sum(1 for b in boxes if _ANCHOR_RE.search(b['t']))


def find_cartouche(page):
    """Recherche le cartouche dans le haut puis le bas de la page. Retourne (image, boîtes)."""
    w, h = page.size
    if w < 2000:                       # petite image : agrandie pour la lecture des petits caractères
        k = 2000.0 / w
        page = page.resize((2000, int(h * k)), Image.LANCZOS)
        w, h = page.size
    best = None
    for top, bottom in ((0.0, 0.34), (0.66, 1.0)):
        crop = page.crop((0, int(h * top), w, int(h * bottom)))
        boxes = ocr_boxes(crop)
        score = _anchor_score(boxes)
        if best is None or score > best[0]:
            best = (score, crop, boxes, top)
    score, crop, boxes, top = best
    return crop, boxes, score


# ---------------------------------------------------------------- champs
def _first(pattern, text, flags=re.I):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def parse_fields(text):
    """Champs de la fiche à partir du texte OCR complet du cartouche."""
    t = re.sub(r'\s+', ' ', text)
    f = {}
    lz = _first(r'LA[IZz1l]{1,2}E?\s*:?\s*(\d{3}(?:[.,]\d+)?)\s*(?:mm\b|$|\s[A-Z])', t)
    if lz:
        f['laize_piste_mm'] = _num(lz)
    tot = _first(r'LAIZE\s*TOTA\w*\s*:?\s*(\d{3,4}(?:[.,]\d+)?)', t)
    if tot:
        f['laize_totale_mm'] = _num(tot)
    pas = _first(r'PAS\s*D\w{0,3}\s*C\w{0,4}\s*:?\s*(\d{2,4}(?:[.,]\d+)?)', t)
    if pas:
        f['repeat_mm'] = _num(pas)
    porte = _first(r'Porte\s*cli\w*\s*:?\s*(\d{2,4})', t)
    if porte:
        f['porte_cliche_mm'] = _num(porte)
    if 'laize_piste_mm' not in f or 'repeat_mm' not in f:
        m = re.search(r'LAIZE\s*DEV\.?\s*LAIZE.*?(?:\n|\s{2,})(?:[^\d\n]{0,20})(\d{3}(?:[.,]\d{3})?)\s+(\d{3}(?:[.,]\d{3})?)\s', text, re.I | re.S)
        if m:
            f.setdefault('laize_piste_mm', _num(m.group(1)))
            f.setdefault('repeat_mm', _num(m.group(2)))
            f['gabarit_entete'] = True
    pf = _first(r'Format\s*\(?H\s*x\s*V\)?\s*:?\s*(\d{2,4}(?:[.,]\d+)?)\s*[x×]', t)
    if pf and 'laize_piste_mm' not in f:
        f['laize_piste_mm'] = _num(pf)
        f['gabarit'] = 'polyslim'
    lb = _first(r'Laize\s*Bobine\s*:?\s*(\d{3,4}(?:[.,]\d+)?)', t)
    if lb and 'laize_totale_mm' not in f:
        f['laize_totale_mm'] = _num(lb)
    dc = _first(r'Dev\w*\s*Cylindre\s*:?\s*(\d{3}(?:[.,]\d+)?)', t)
    if dc and 'repeat_mm' not in f:
        f['repeat_mm'] = _num(dc)
    np_ = _first(r'N\S{0,2}\s*Piste\s*:?\s*(\d)', t)
    if np_ and 'poses_across' not in f:
        f['poses_across'] = int(np_)
    npo = _first(r'N\S{0,2}\s*Pose\s*:?\s*(\d)\b', t)
    if npo and 'poses_repeat' not in f:
        f['poses_repeat'] = int(npo)
    cu = _first(r'Couleurs\s*Utilis\S*\s*:?\s*(\d{1,2})', t)
    if cu and 'nombre_couleurs' not in f:
        f['nombre_couleurs'] = int(cu)
    dos = _first(r'DOSSIER\s*N\S*\s*:?\s*(AL\s*\d{4,6})', t) or _first(r'\b(AL\s?\d{5})\b', t)
    if dos:
        f['dossier'] = re.sub(r'\s+', ' ', dos.upper().replace('AL', 'AL ', 1)).replace('AL  ', 'AL ')
    nb = _first(r'(?:couleurs?|ceuleurs?|Nbr)\b.{0,25}?(\d{1,2})\s*C\b', t)
    if nb:
        f['nombre_couleurs'] = int(nb)
    pl = _first(r'POSES?\s*EN\s*LAIZE\s*:?\s*(\d)', t)
    if pl:
        f['poses_across'] = int(pl)
    pc = _first(r'POSES?\s*EN\s*COUPE\s*:?\s*(\d)', t)
    if pc:
        f['poses_repeat'] = int(pc)
    lpi = _first(r'(\d{2,3}[.,]\d)\s*LPI', t)
    if lpi:
        f['lineature_lpi'] = _num(lpi)
    ep = _first(r'CLICH\w*\s*:?\s*(\d[.,]\d{1,2})\s*mm', t)
    if ep:
        f['epaisseur_cliche_mm'] = _num(ep)
    date = _first(r'DATE\s*:?\s*(\d{2}/\d{2}/\d{4})', t)
    if date:
        f['date'] = date
    job = _first(r'JOB\s*:?\s*(.+?)(?=\s*(?:AMALGAME|LAIZE|EPAISSEUR|Ep|$))', t)
    if job:
        f['job_raw'] = job.strip(' |:')
    return f


def supplier_from_text(text):
    up = re.sub(r'[^A-Z]', '', (text or '').upper())
    if 'YAHIAOUI' in up or 'PHOTOGRAVURE' in up:
        return 'Yahiaoui Photogravure'
    if 'POLYSLIM' in up:
        return 'Poly Slim'
    if 'STUDIO' in up:
        return 'Studio Flexo'
    return None


# ---------------------------------------------------------------- encres
_PCT_RE = re.compile(r'(\d{1,3}(?:[.,]\d{1,2})?)\s*%')
_CM2_RE = re.compile(r'(\d[\d.,]*)\s*\.?\s*(?:cm|em|crn|om|orn|cn|cr)', re.I)
_LABEL_RE = re.compile(r'(couleur|nbr|remarque|client|frontal|cello|date|signature|linie|spot|dim|'
                       r'impress|valid|poses|continue|epaisseur|laize|pas de|porte|job|imprim|'
                       r'infograph|dossier|avec|quincon|lpi)', re.I)
_CANON_COLORS = ['Cyan', 'Magenta', 'Yellow', 'Black', 'Gold', 'Blanc', 'B.Ref', 'Vernis']


def _parse_cm2(raw):
    s = raw.strip().rstrip('.')
    if s.count('.') + s.count(',') > 1 or ('.' in s and ',' in s):
        s = re.sub(r'[.,](?=\d{3}$)', '#', s).replace('.', '').replace(',', '').replace('#', '.')
    else:
        s = s.replace(',', '.')
    if '.' not in s and len(s) >= 4:          # « 14796 » -> 14.796 (3 décimales)
        s = s[:-3] + '.' + s[-3:]
    try:
        return float(s)
    except ValueError:
        return None


def canon_ink_name(raw):
    """Nom d'encre ramené à un vocabulaire fixe ; texte d'origine sinon (signalé à vérifier)."""
    t = re.sub(r'\s+', ' ', (raw or '')).strip()
    t = re.sub(r'^[\d.,\s]+(?=[A-Za-z])', '', t)              # « 255.000 Magenta » -> « Magenta »
    if not t:
        return None
    if re.match(r'(?i)^pantone', t):
        rest = re.sub(r'(?i)^pantone\s*', '', t).strip()
        if re.fullmatch(r'(?i)black\s*c', rest.replace(' ', '')):
            return 'PANTONE Black C'
        m2 = re.match(r'(\d{3,4})\s*([A-Za-z]{1,2})?$', rest.replace(' ', ''))
        if m2:
            return 'PANTONE ' + m2.group(1) + (' ' + m2.group(2).upper() if m2.group(2) else '')
    low = t.lower()
    m = re.search(r'\bP\w{2,7}\s*(\d{3,4})\s*([A-Za-z]{1,2})?\b', t, re.I) or \
        re.fullmatch(r'\s*(\d{3,4})\s*([A-Za-z]{1,2})\s*', t)
    if m:
        suffix = (m.group(2) or '').upper()
        return f'PANTONE {m.group(1)}' + (f' {suffix}' if suffix else '')
    mp = re.fullmatch(r'P\s?(\d{3,4})\s*([CU])?', t, re.I)
    if mp:
        return 'PANTONE ' + mp.group(1) + (' ' + mp.group(2).upper() if mp.group(2) else '')
    if 'white' in low or 'blanc' in low:
        return 'Blanc'
    word = re.sub(r'[^a-z.]', '', low.split(' ')[0])
    if word in ('blanc', 'blane', 'bianc', 'white', 'banc'):
        return 'Blanc'
    if word.startswith('cy') or word.startswith('cn'):
        return 'Cyan'
    if word.startswith('ma') and len(word) >= 4:
        return 'Magenta'
    if word.startswith(('ye', 'ja', 'yel')):
        return 'Yellow'
    if word.startswith('gol') or word == 'gola':
        return 'Gold'
    if word in ('b.ref', 'bref', 'b.rel', 'b.re'):
        return 'B.Ref'
    if word.startswith('bl') or word.startswith('bla'):
        return 'Black' if 'l' in word and word[-1] != 'c' else 'Blanc'
    if word.startswith('vern'):
        return 'Vernis'
    best = difflib.get_close_matches(word.capitalize(), _CANON_COLORS, n=1, cutoff=0.6)
    if best:
        return best[0]
    return None


def ink_table(boxes, n_expected=None):
    """Colonnes d'encre : nom au-dessus, cm² et % sous le nom.

    Les colonnes sont ancrées sur les pourcentages (plus fiables), puis chaque cm²
    est rattaché à la colonne la plus proche. Retourne des dicts brut par colonne.
    """
    pct_tok = []
    for b in boxes:
        for m in _PCT_RE.finditer(b['t']):
            pct_tok.append({'xc': b['xc'], 'yc': b['yc'], 'h': b['h'], 'v': _num(m.group(1)), 'c': b['c']})
    cm_tok = []
    for b in boxes:
        m = _CM2_RE.search(b['t'])
        if m:
            v = _parse_cm2(m.group(1))
            if v is not None:
                cm_tok.append({'xc': b['xc'], 'yc': b['yc'], 'h': b['h'], 'v': v, 'c': b['c']})
    anchors_src = pct_tok if len(pct_tok) >= 2 else cm_tok
    if not anchors_src:
        return []
    anchors_src = sorted(anchors_src, key=lambda t: t['xc'])
    ys = sorted(t['yc'] for t in anchors_src)
    row_y = ys[len(ys) // 2]
    row_h = sorted(t['h'] for t in anchors_src)[len(anchors_src) // 2]
    row = [t for t in anchors_src if abs(t['yc'] - row_y) < 1.2 * row_h]
    if n_expected and len(row) > n_expected:
        row = sorted(row, key=lambda t: abs(t['yc'] - row_y))[:n_expected]
    anchors = sorted(row, key=lambda t: t['xc'])
    xs = [a['xc'] for a in anchors]
    spacing = (xs[-1] - xs[0]) / max(1, len(xs) - 1) if len(xs) > 1 else 200.0
    cols = [{'xc': x, 'cm2': None, 'pct': a['v'], 'yc': a['yc'], 'pct_conf': a['c'], 'cm2_conf': None} for x, a in zip(xs, anchors)]
    for t in cm_tok:
        j = min(range(len(cols)), key=lambda k: abs(cols[k]['xc'] - t['xc']))
        if abs(cols[j]['xc'] - t['xc']) < 0.6 * spacing and abs(t['yc'] - row_y) < 2.5 * row_h \
                and cols[j]['cm2'] is None:
            cols[j]['cm2'] = t['v']
            cols[j]['cm2_conf'] = t['c']
    # noms : texte situé au-dessus de la rangée, dans la bande de la colonne
    values_ids = {id(b) for b in boxes if _CM2_RE.search(b['t']) or _PCT_RE.search(b['t'])}
    name_boxes = [b for b in boxes if id(b) not in values_ids and not _LABEL_RE.search(b['t'])
                  and row_y - 4.0 * row_h < b['yc'] < row_y - 0.3 * row_h]
    buckets = {i: [] for i in range(len(cols))}
    for b in name_boxes:
        j = min(range(len(xs)), key=lambda k: abs(xs[k] - b['xc']))
        if abs(xs[j] - b['xc']) < 0.6 * spacing:
            buckets[j].append(b)
    for j, c in enumerate(cols):
        parts = sorted(buckets[j], key=lambda b: (b['yc'], b['x0']))
        c['name_raw'] = re.sub(r'^[\d.,\s]+(?=[A-Za-z])', '', ' '.join(p['t'] for p in parts).strip())
        c['name'] = canon_ink_name(c['name_raw']) or ''
        c['name_unknown'] = not c['name']
    return cols


# ---------------------------------------------------------------- analyse
def _surface_cm2(laize_mm, repeat_mm):
    if laize_mm and repeat_mm:
        return laize_mm * repeat_mm / 100.0
    return None


def build_rows(fields, cols):
    """Lignes d'encre validées : cm² et % reconstruits l'un depuis l'autre si besoin.

    Surface de référence = laize piste × pas de coupe (ex. 325 × 330 = 1072,5 cm²).
    """
    lz = fields.get('laize_piste_mm')
    rp = fields.get('repeat_mm')
    surf = _surface_cm2(lz, rp)
    rows = []
    for i, c in enumerate(cols):
        check = []
        name = c.get('name') or ''
        raw = c.get('name_raw') or ''
        if not name:
            name = f'Encre n°{i + 1} (nom à saisir)'
            check.append('nom illisible : à saisir' + (f' (lu : « {raw} »)' if raw else ''))
        elif raw and re.sub(r'[^a-z0-9]', '', name.lower()) != re.sub(r'[^a-z0-9]', '', raw.lower()):
            check.append(f'nom lu « {raw} » : vérifiez')
        cm2, pct = c.get('cm2'), c.get('pct')
        low = [k for k, v in (('%', c.get('pct_conf')), ('cm²', c.get('cm2_conf'))) if v is not None and v < 0.7]
        if low:
            check.append('lecture OCR incertaine (' + ', '.join(low) + ') : vérifiez')
        if surf:
            if cm2 is not None and pct is not None:
                calc = surf * pct / 100.0
                if abs(calc - cm2) > 0.03 * max(calc, 1.0):
                    check.append(f'cm² {cm2} et % {pct} incohérents (surface {surf:g} cm²)')
                    cm2 = round(calc, 3)
                    check.append('cm² recalculé depuis le %')
            elif cm2 is None and pct is not None:
                cm2 = round(surf * pct / 100.0, 3)
                check.append('cm² calculé depuis le %')
            elif pct is None and cm2 is not None:
                pct = round(100.0 * cm2 / surf, 2)
                check.append('% calculé depuis les cm²')
        if re.fullmatch(r'PANTONE \d{3,4}', name):
            check.append('suffixe C ou U à vérifier')
        rows.append({'name': name, 'cm2': cm2, 'pct': pct, 'check': ' ; '.join(check)})
    return rows


def analyze_pages(pages):
    """Analyse une liste d'images de fiche. Retourne un dict de résultat (sans preview)."""
    out = {'fields': {}, 'rows': [], 'supplier': None, 'warnings': [], 'error': ''}
    for page in pages[:2]:
        crop, boxes, score = find_cartouche(page)
        if score < 2:
            continue
        lines = group_lines(boxes)
        text = '\n'.join(ln['text'] for ln in lines)
        fields = parse_fields(text)
        out['fields'] = fields
        out['gabarit'] = fields.get('gabarit')
        out['supplier'] = supplier_from_text(text)
        out['rows_raw'] = ink_table(boxes, fields.get('nombre_couleurs'))
        out['rows'] = build_rows(fields, out['rows_raw'])
        if fields.get('nombre_couleurs') and len(out['rows']) != fields['nombre_couleurs']:
            out['warnings'].append('nombre de colonnes lues différent de « Nbr de couleurs »')
        out['text'] = text
        break
    return out
