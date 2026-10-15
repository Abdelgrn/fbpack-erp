"""Analyse des fiches BAT (PDF ou image) par OCR local : RapidOCR, sans API ni Tesseract.

Le moteur (core/services/bat_ocr.py) lit le cartouche technique : laize, laize totale, pas de
coupe, poses, dossier, nombre de couleurs, puis les encres (nom, cm², %). Les cm² et % sont
contrôlés l'un par l'autre (surface = laize × pas). Rien n'est enregistré : le résultat
PRÉ-REMPLIT le formulaire et l'opérateur valide avant « Calculer et enregistrer ».

analyze_bat retourne toujours un dict (clé 'error' si échec), sans exception.
"""
import base64
import io
import re

from PIL import Image

from . import bat_ocr

MAX_BAT_BYTES = 10 * 1024 * 1024
MAX_PAGE_WIDTH = 2400          # px : borne la mémoire (plan Render 512 Mo)


def validate_bat_size(size):
    """True si la taille du fichier BAT est acceptable (non vide, <= 10 Mo)."""
    return 0 < size <= MAX_BAT_BYTES


_NAME_INK_TYPE = (
    ('vernis', 'VARNISH'), ('varnish', 'VARNISH'),
    ('blanc', 'WHITE'), ('white', 'WHITE'), ('tiO2', 'WHITE'),
)


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


def _render_pdf_pages(data, max_pages=2):
    """Rend les premières pages du PDF (pypdfium2) ; [] si indisponible."""
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(data)
        out = []
        for i in range(min(len(pdf), max_pages)):
            page = pdf[i]
            wpt = float(page.get_width() or 595)
            scale = min(300.0 / 72.0, MAX_PAGE_WIDTH / wpt)
            out.append(page.render(scale=scale).to_pil().convert('RGB'))
        return out
    except Exception:
        return []


def _clean_job_name(text):
    t = re.sub(r'\s+', ' ', (text or '')).strip(' |:;,-')
    t = re.sub(r'\bAMALGAME\b.*$', '', t, flags=re.I).strip()   # jamais « AMALGAME: »
    return t


def _rows_from_ocr(cols):
    rows = []
    for c in cols:
        name = c['name']
        ink_type = ink_type_for(name)
        rows.append({'name': name, 'ink_type': ink_type,
                     'coverage_percent': c['pct'], 'coverage_area_cm2': c['cm2'],
                     'swatch_hex': '', 'confidence': 'OCR', 'values_source': 'OCR',
                     'check': c.get('check', ''), 'patch': None})
    return rows


def _hints(fields):
    h = {}
    job = _clean_job_name(fields.get('job_raw'))
    if job:
        h['name'] = job
    for key in ('laize_piste_mm', 'laize_totale_mm', 'repeat_mm', 'porte_cliche_mm',
                'lineature_lpi', 'epaisseur_cliche_mm'):
        if fields.get(key):
            h[key] = fields[key]
    for key in ('poses_across', 'poses_repeat'):
        if fields.get(key):
            h[key] = int(fields[key])
    if fields.get('dossier'):
        h['dossier'] = fields['dossier']
    if h.get('laize_totale_mm'):
        h['width_mm'] = h['laize_totale_mm']
    elif h.get('laize_piste_mm') and h.get('poses_across', 1) > 1:
        h['width_mm'] = round(h['laize_piste_mm'] * h['poses_across'], 2)
    return h


def analyze_bat(data, filename=''):
    """Analyse une fiche BAT par OCR ; retourne toujours un dict (jamais d'exception)."""
    result = {'mode': '', 'source': filename or 'fiche BAT', 'preview_data_uri': '',
              'rows': [], 'job_hints': {}, 'warnings': [], 'cliche_supplier': None}
    if not data:
        result['error'] = 'Fichier vide.'
        return result
    if len(data) > MAX_BAT_BYTES:
        result['error'] = 'Fiche BAT trop lourde (10 Mo max).'
        return result
    try:
        if data[:5] == b'%PDF-':
            pages = _render_pdf_pages(data)
            if not pages:
                result['error'] = 'PDF illisible : exportez la fiche en PNG ou JPEG.'
                return result
            result['mode'] = 'PDF + OCR'
        else:
            im = Image.open(io.BytesIO(data))
            im.load()
            pages = [im.convert('RGB')]
            if pages[0].width > MAX_PAGE_WIDTH:
                w = MAX_PAGE_WIDTH
                pages[0] = pages[0].resize((w, int(pages[0].height * w / pages[0].width)), Image.LANCZOS)
            result['mode'] = 'Image + OCR'
    except Exception:
        result['error'] = 'Fichier non reconnu : PDF, PNG, JPEG ou WEBP attendu.'
        return result

    result['preview_data_uri'] = _preview_data_uri(pages[0])
    try:
        ocr = bat_ocr.analyze_pages(pages)
    except Exception:
        result['error'] = ('Lecture OCR impossible sur ce fichier. '
                           'Renseignez les lignes à la main.')
        return result

    fields = ocr.get('fields') or {}
    if not ocr.get('rows'):
        result['error'] = ("Aucun cartouche technique reconnu sur cette fiche (laize, pas, encres). "
                           'Renseignez les lignes à la main ou envoyez la fiche complète.')
        return result

    result['rows'] = _rows_from_ocr(ocr['rows'])
    result['job_hints'] = _hints(fields)
    result['cliche_supplier'] = ocr.get('supplier')
    warn = result['warnings']
    n = len(result['rows'])
    expected = fields.get('nombre_couleurs')
    warn.append(f'Lecture OCR : {n} couleur(s)'
                + (f' (la fiche annonce {expected} C)' if expected else '')
                + '. Vérifiez chaque valeur avant « Calculer et enregistrer ».')
    if expected and expected != n:
        warn.append('Nombre de couleurs différent de la mention « Nbr de couleurs » : vérifiez les lignes.')
    if result['cliche_supplier']:
        warn.append(f"Fournisseur de clichés lu : {result['cliche_supplier']}. Vérifiez.")
    if result['job_hints'].get('name'):
        warn.append(f"Job lu : « {result['job_hints']['name']} ». Vérifiez le nom.")
    if result['job_hints'].get('laize_totale_mm'):
        warn.append(f"Laize totale lue : {result['job_hints']['laize_totale_mm']:g} mm (toutes pistes).")
    elif result['job_hints'].get('laize_piste_mm'):
        warn.append('Laize totale non lue : saisissez-la.')
    if not (result['job_hints'].get('laize_piste_mm') or result['job_hints'].get('repeat_mm')):
        warn.insert(0, 'Cartouche non reconnu (gabarit différent) : laize et pas de coupe à saisir. '
                       'Lecture partielle : vérifiez chaque ligne.')
    if ocr.get('gabarit') == 'polyslim':
        warn.append('Gabarit Poly Slim : surfaces calculées sur piste × développement cylindre '
                    f"({result['job_hints'].get('laize_piste_mm', '?'):g} × {result['job_hints'].get('repeat_mm', '?'):g} mm). "
                    'Vérifiez la base de calcul.')
    if any('à saisir' in r['name'] for r in result['rows']):
        warn.append('Certains noms d\'encre sont illisibles : saisissez-les (aucun nom n\'est deviné).')
    return result
