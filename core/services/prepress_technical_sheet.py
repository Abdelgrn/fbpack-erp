"""Services de sauvegarde et d'impression des fiches techniques prépresse.

Lot Design Bobine V4 : composition serveur du visuel « bobine d'impression »
(rouleau enroulé + web en S portant les répétitions jointives de la maquette),
orientation cohérente avec le sens d'enroulement historique, et logo servi
sur fond blanc (logo_blanc.png, repli logo.png).
Moteur image sans dépendance hors Pillow (homographies résolues en interne).
"""

import base64
import math
import mimetypes
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageEnhance

from django.contrib.staticfiles import finders
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from ..models.prepress import TechnicalProduct, TechnicalProductRevision


SNAPSHOT_FIELDS = (
    'client_id', 'ref_internal', 'name', 'printing_process', 'structure_type',
    'width_mm', 'cut_length_mm', 'num_colors', 'artwork_file', 'artwork_version',
    'bat_status', 'version', 'is_obsolete', 'date_creation', 'tech_sheet_file',
    'product_visual', 'graveur', 'ref_graveur', 'type_dossier', 'nb_poses_pas',
    'nb_poses_laize', 'developpement_mm', 'laize_gravure_mm',
    'support_impression', 'impression', 'spot', 'technical_notes',
    'sens_bobine', 'spot_placement', 'last_modified_by_id',
)


def _json_value(value):
    if hasattr(value, 'name'):
        return value.name or ''
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def build_product_snapshot(product):
    colors = [
        {
            'ordre': color.ordre,
            'couleur_hex': color.couleur_hex,
            'nom_couleur': color.nom_couleur,
            'anilox': color.anilox or '',
            'adhesif': color.adhesif or '',
            'viscosite': color.viscosite or '',
            'type_encre': color.type_encre or '',
            'formule_encre': color.formule_encre or '',
        }
        for color in product.couleurs_flexo.all().order_by('ordre', 'pk')
    ]
    return {
        'schema_version': 1,
        'product': {
            field_name: _json_value(getattr(product, field_name))
            for field_name in SNAPSHOT_FIELDS
        },
        'client': {
            'id': product.client_id,
            'name': product.client.name if product.client_id else '',
            'code': getattr(product.client, 'code_client', '') if product.client_id else '',
        },
        'colors': colors,
    }


@transaction.atomic
def create_product_revision(product, user=None, reason=''):
    """Crée une révision séquentielle après une sauvegarde valide."""
    locked_product = TechnicalProduct.objects.select_for_update().select_related('client').get(pk=product.pk)
    locked_product = TechnicalProduct.objects.prefetch_related('couleurs_flexo').get(pk=locked_product.pk)
    last_number = (
        TechnicalProductRevision.objects.filter(product=locked_product)
        .aggregate(value=Max('revision_number'))['value']
        or 0
    )
    return TechnicalProductRevision.objects.create(
        product=locked_product,
        revision_number=last_number + 1,
        snapshot=build_product_snapshot(locked_product),
        reason=(reason or '').strip()[:250],
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )


def _bytes_to_data_uri(data, filename='image.png'):
    if not data:
        return ''
    mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    encoded = base64.b64encode(data).decode('ascii')
    return f'data:{mime_type};base64,{encoded}'


def _field_file_data_uri(field_file):
    if not field_file or not getattr(field_file, 'name', ''):
        return ''
    try:
        field_file.open('rb')
        try:
            data = field_file.read(12 * 1024 * 1024)
        finally:
            field_file.close()
        return _bytes_to_data_uri(data, field_file.name)
    except Exception:
        # Une pièce média indisponible ne doit pas empêcher l'affichage de la fiche.
        return ''


def _logo_data_uri():
    """Logo FB Pack sur fond blanc prioritaire, repli historique logo.png."""
    logo_path = finders.find('logo_blanc.png') or finders.find('logo.png')
    if not logo_path:
        return ''
    try:
        path = Path(logo_path)
        return _bytes_to_data_uri(path.read_bytes(), path.name)
    except Exception:
        return ''


# ============================================================
# LOT DESIGN BOBINE V4.1 — COMPOSITION DU VISUEL BOBINE D'IMPRESSION
# ============================================================
# Géométrie symétrique : rouleau centré dont la longueur (laize) est égale à la
# largeur du web ; traverses horizontales exactement partagées entre segments
# (continuité parfaite, étiquettes alignées) ; caps identiques aux deux bouts.
# Rotation de l'étiquette cohérente avec le pictogramme « sens » historique.
SENS_ROTATION = {'1': 180, '2': 0, '3': 90, '4': -90, '5': 180, '6': 0, '7': 90, '8': -90}
SENS_PICTO_DEG = {'1': 180, '2': 0, '3': 90, '4': -90, '5': 180, '6': 0, '7': 90, '8': -90}
SPOT_PICTO_CSS = {
    '1': 'left:3px;bottom:3px;',
    '2': 'left:50%;margin-left:-3px;bottom:3px;',
    '3': 'right:3px;bottom:3px;',
    '4': 'right:3px;top:3px;',
}

ROLL_CANVAS_W, ROLL_CANVAS_H = 560, 860
ROLL_WEB_WIDTH = 300          # laize du web
ROLL_LEN = 300                # longueur du cylindre == laize du web
ROLL_D = 120                  # diamètre du rouleau
ROLL_CX = ROLL_CANVAS_W // 2  # axe de symétrie
ROLL_AMPLITUDE = 26           # amplitude du S
_ROLL_SEGMENTS = 80


def _overlay(base, im, pos):
    """Compose une image RGBA sur une couche de même taille (alpha-blending réel)."""
    layer = Image.new('RGBA', base.size, (0, 0, 0, 0))
    layer.paste(im, pos, im.getchannel('A'))
    base.alpha_composite(layer)


def _trim_light_borders(image, threshold=238):
    """Rogne une éventuelle marge claire autour de la maquette scannée."""
    rgb = image.convert('RGB')
    bbox = rgb.convert('L').point(lambda p: 255 if p < threshold else 0).getbbox()
    return rgb.crop(bbox) if bbox else rgb


def _gauss_solve(matrix, vector):
    """Résolution 8x8 par élimination de Gauss avec pivot partiel."""
    n = len(vector)
    aug = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise ValueError('système perspectif singulier')
        aug[col], aug[pivot] = aug[pivot], aug[col]
        for row in range(col + 1, n):
            factor = aug[row][col] / aug[col][col]
            for k in range(col, n + 1):
                aug[row][k] -= factor * aug[col][k]
    result = [0.0] * n
    for row in range(n - 1, -1, -1):
        total = aug[row][n] - sum(aug[row][k] * result[k] for k in range(row + 1, n))
        result[row] = total / aug[row][row]
    return result


def _perspective_coeffs(dest_quad, src_quad):
    """Coefficients PIL (dest -> source) pour mapper src_quad dans dest_quad."""
    matrix, vector = [], []
    for (x, y), (u, v) in zip(dest_quad, src_quad):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        vector.append(u)
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        vector.append(v)
    return _gauss_solve(matrix, vector)


def _cylinder_shading(width, height):
    """Dégradé vertical simulant la rotondité du cylindre enroulé."""
    shade = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    px = shade.load()
    for y in range(height):
        t = abs(y - height / 2) / (height / 2)
        dark = int(115 * (t ** 1.9))
        highlight = int(72 * max(0.0, 1 - abs(t - 0.30) / 0.24))
        color = (255, 255, 255, highlight) if highlight else (18, 20, 30, dark)
        for x in range(width):
            px[x, y] = color
    return shade


def _centerline(web_y0, span, amplitude, cx, steps=_ROLL_SEGMENTS):
    """Ligne centrale du web en S (une période complète, départ et retour au centre)."""
    return [
        (cx + amplitude * math.sin(i / steps * 2 * math.pi), web_y0 + span * i / steps)
        for i in range(steps + 1)
    ]


def _ribbon_mask(size, points, width, clip_top):
    """Masque ruban à traverses horizontales, dessiné en supersampling 2x."""
    half = width / 2
    scale = 2
    big = Image.new('L', (size[0] * scale, size[1] * scale), 0)
    left = [((x - half) * scale, y * scale) for (x, y) in points]
    right = [((x + half) * scale, y * scale) for (x, y) in points]
    ImageDraw.Draw(big).polygon(left + right[::-1], fill=255)
    mask = big.resize(size, Image.LANCZOS)
    if clip_top > 0:
        mask.paste(0, (0, 0, size[0], clip_top))
    return mask


def _tile_horizontally(maq, k):
    """Répète la maquette k fois côte à côte (poses en laize)."""
    if k <= 1:
        return maq
    tiled = Image.new('RGB', (maq.width * k, maq.height))
    for i in range(k):
        tiled.paste(maq, (maq.width * i, 0))
    return tiled


def compose_roll_image(maquette_bytes, sens='1', poses_laize=1):
    """Compose le visuel bobine (octets PNG) depuis la seule maquette fournie.

    Rouleau centré (longueur == laize du web, caps identiques), web en S
    symétrique portant 3 à 6 répétitions jointives de la maquette, poses en
    laize côte à côte, orientation des étiquettes dictée par le sens
    d'enroulement historique (1 à 8 ; 5 à 8 = web miroir).
    Retourne b'' si la composition est impossible (image illisible).
    """
    try:
        maquette = Image.open(BytesIO(maquette_bytes))
        maquette.load()
    except Exception:
        return b''
    maq = _trim_light_borders(maquette)
    canvas = Image.new('RGBA', (ROLL_CANVAS_W, ROLL_CANVAS_H), (0, 0, 0, 0))

    mirror = -1 if str(sens) in {'5', '6', '7', '8'} else 1
    rot = SENS_ROTATION.get(str(sens), 0)
    poses = max(1, min(3, int(poses_laize or 1)))

    roll_x0 = ROLL_CX - ROLL_LEN // 2
    roll_y0 = 26
    cap_rx = 20
    web_y0 = roll_y0 + ROLL_D - 22
    span_max = (ROLL_CANVAS_H - 12) - web_y0

    maq_web = _tile_horizontally(maq, poses)
    aspect = maq_web.height / max(maq_web.width, 1)
    if rot in (90, -90):
        ideal = ROLL_WEB_WIDTH / max(aspect, 0.2)
    else:
        ideal = ROLL_WEB_WIDTH * aspect
    ideal = max(90, min(260, ideal))
    n = max(3, min(6, int(span_max // ideal)))
    span = n * ideal
    amplitude = ROLL_AMPLITUDE * mirror
    points = _centerline(web_y0, span, amplitude, ROLL_CX)
    clip_top = max(0, web_y0 - 30)

    # Ombre symétrique sous le rouleau, puis liseré du ruban.
    shadow = Image.new('RGBA', (ROLL_CANVAS_W, ROLL_CANVAS_H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow, 'RGBA').ellipse(
        [roll_x0 + 18, roll_y0 + ROLL_D - 12, roll_x0 + ROLL_LEN - 18, roll_y0 + ROLL_D + 14],
        fill=(30, 35, 45, 40),
    )
    canvas.alpha_composite(shadow)

    border = Image.new('RGBA', (ROLL_CANVAS_W, ROLL_CANVAS_H), (0, 0, 0, 0))
    border.paste((150, 156, 165, 235), (0, 0, ROLL_CANVAS_W, ROLL_CANVAS_H))
    canvas.alpha_composite(Image.composite(
        border, Image.new('RGBA', (ROLL_CANVAS_W, ROLL_CANVAS_H), (0, 0, 0, 0)),
        _ribbon_mask((ROLL_CANVAS_W, ROLL_CANVAS_H), points, ROLL_WEB_WIDTH + 6, clip_top),
    ))

    # Web : homographies par demi-répétition sur traverses horizontales partagées.
    base_tile = maq_web.rotate(rot, expand=True, resample=Image.BICUBIC).convert('RGBA')
    web_layer = Image.new('RGBA', (ROLL_CANVAS_W, ROLL_CANVAS_H), (0, 0, 0, 0))
    sub = 2
    for i in range(n):
        for j in range(sub):
            t0 = (i + j / sub) / n
            t1 = (i + (j + 1) / sub) / n
            y0 = web_y0 + span * t0
            y1 = web_y0 + span * t1
            x0 = ROLL_CX + amplitude * math.sin(t0 * 2 * math.pi)
            x1 = ROLL_CX + amplitude * math.sin(t1 * 2 * math.pi)
            half = (ROLL_WEB_WIDTH + 16) / 2
            over = 0.0 if (j == sub - 1 and i == n - 1) else 1.0
            quad = [
                (x0 - half, y0), (x0 + half, y0),
                (x1 + half, y1 + over), (x1 - half, y1 + over),
            ]
            sy0 = int(base_tile.height * (j / sub))
            sy1 = min(base_tile.height, int(base_tile.height * ((j + 1) / sub)) + (1 if over else 0))
            slice_tile = base_tile.crop((0, sy0, base_tile.width, sy1))
            src = [(0, 0), (slice_tile.width, 0), (slice_tile.width, slice_tile.height), (0, slice_tile.height)]
            coeffs = _perspective_coeffs(quad, src)
            segment = slice_tile.transform(
                (ROLL_CANVAS_W, ROLL_CANVAS_H), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fill=1,
            )
            web_layer.alpha_composite(segment)

    canvas.alpha_composite(Image.composite(
        web_layer, Image.new('RGBA', (ROLL_CANVAS_W, ROLL_CANVAS_H), (0, 0, 0, 0)),
        _ribbon_mask((ROLL_CANVAS_W, ROLL_CANVAS_H), points, ROLL_WEB_WIDTH, clip_top),
    ))

    # Rouleau centré : corps enroulé + deux caps identiques (symétrie).
    # V4.3d : le cylindre est REMPLI ENTIÈREMENT par le même visuel que le
    # ruban (mêmes poses en laize, même orientation dictée par le sens) :
    # la transition ruban → rouleau est fluide, sans bord flou ni vide.
    body = base_tile.resize((ROLL_LEN, ROLL_D), Image.LANCZOS).convert('RGBA')
    body = ImageEnhance.Brightness(body).enhance(0.94).convert('RGBA')
    body.alpha_composite(_cylinder_shading(ROLL_LEN, ROLL_D))
    _overlay(canvas, body, (roll_x0, roll_y0))

    draw = ImageDraw.Draw(canvas, 'RGBA')
    for cap_cx in (roll_x0, roll_x0 + ROLL_LEN):
        draw.ellipse(
            [cap_cx - cap_rx, roll_y0, cap_cx + cap_rx, roll_y0 + ROLL_D],
            fill=(228, 231, 235, 255), outline=(148, 153, 161, 255), width=2,
        )
        for i in range(1, 4):
            draw.ellipse(
                [cap_cx - cap_rx + i * 4, roll_y0 + i * 10,
                 cap_cx + cap_rx - i * 4, roll_y0 + ROLL_D - i * 10],
                outline=(176, 181, 189, 210), width=1,
            )
        draw.ellipse(
            [cap_cx - 8, roll_y0 + ROLL_D // 2 - 22, cap_cx + 8, roll_y0 + ROLL_D // 2 + 22],
            fill=(36, 38, 43, 255),
        )

    output = BytesIO()
    canvas.save(output, format='PNG', optimize=True)
    return output.getvalue()


def build_roll_visual_data_uri(product):
    """Data-URI PNG du visuel bobine ; chaîne vide en cas d'indisponibilité.

    Aucune exception ne remonte : sans maquette, sans Pillow ou sur image
    illisible, la fiche retombe sur le visuel plat puis sur le placeholder.
    """
    field_file = getattr(product, 'product_visual', None)
    if not field_file or not getattr(field_file, 'name', ''):
        return ''
    try:
        field_file.open('rb')
        try:
            data = field_file.read(12 * 1024 * 1024)
        finally:
            field_file.close()
    except Exception:
        return ''
    try:
        png = compose_roll_image(
            data,
            getattr(product, 'sens_bobine', '') or '1',
            getattr(product, 'nb_poses_laize', 1) or 1,
        )
    except Exception:
        return ''
    return _bytes_to_data_uri(png, 'bobine.png') if png else ''


def build_print_context(product):
    colors = list(product.couleurs_flexo.all().order_by('ordre', 'pk')[:8])
    color_rows = [
        {
            'ordre': color.ordre,
            'couleur_hex': color.couleur_hex or '#FFFFFF',
            'nom_couleur': color.nom_couleur,
            'anilox': color.anilox or '',
            'adhesif': color.adhesif or '',
            'viscosite': color.viscosite or '',
            'type_encre': color.type_encre or '',
            'formule_encre': color.formule_encre or '',
            'is_empty': False,
        }
        for color in colors
    ]
    while len(color_rows) < 8:
        color_rows.append({
            'ordre': len(color_rows) + 1,
            'couleur_hex': '#FFFFFF',
            'nom_couleur': '',
            'anilox': '',
            'adhesif': '',
            'viscosite': '',
            'type_encre': '',
            'formule_encre': '',
            'is_empty': True,
        })

    latest_revision = product.revisions.order_by('-revision_number').first()
    return {
        'product': product,
        'color_rows': color_rows,
        'logo_data_uri': _logo_data_uri(),
        'product_visual_data_uri': _field_file_data_uri(product.product_visual),
        'roll_visual_data_uri': build_roll_visual_data_uri(product),
        'sens_rotation_deg': SENS_PICTO_DEG.get(str(product.sens_bobine or ''), 0),
        'spot_css': SPOT_PICTO_CSS.get(str(product.spot_placement or ''), ''),
        'latest_revision': latest_revision,
        'generated_at': timezone.localtime(),
    }


def _image_from_data_uri(data_uri, width=None, height=None):
    if not data_uri:
        return None
    try:
        from reportlab.lib.utils import ImageReader
        from reportlab.platypus import Image

        raw = base64.b64decode(data_uri.split(',', 1)[1])
        reader = ImageReader(BytesIO(raw))
        original_width, original_height = reader.getSize()
        ratio = min(
            (width / original_width) if width else 1,
            (height / original_height) if height else 1,
        )
        return Image(
            BytesIO(raw),
            width=original_width * ratio,
            height=original_height * ratio,
        )
    except Exception:
        return None


def generate_reportlab_pdf(product, context):
    """PDF métier de secours, dessiné directement avec ReportLab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    output = BytesIO()
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(output, pagesize=(page_width, page_height))
    pdf.setTitle(f'Fiche technique {product.ref_internal}')
    pdf.setAuthor('FB Pack ERP')

    navy = colors.HexColor('#16243A')
    red = colors.HexColor('#B5121B')
    blue = colors.HexColor('#0862B5')
    pink = colors.HexColor('#ECA9C7')
    black = colors.HexColor('#292929')
    grey = colors.HexColor('#DDE2E7')

    def image_reader(data_uri):
        if not data_uri:
            return None
        try:
            return ImageReader(BytesIO(base64.b64decode(data_uri.split(',', 1)[1])))
        except Exception:
            return None

    def fit_size(text, font_name, max_size, max_width, min_size=5.5):
        value = str(text or '—')
        size = max_size
        while size > min_size and stringWidth(value, font_name, size) > max_width:
            size -= .25
        return size

    def centered_text(text, x, y, width, height, color=blue, size=9, font='Helvetica-BoldOblique'):
        value = str(text if text not in (None, '') else '—')
        actual = fit_size(value, font, size, max(width - 8, 5))
        pdf.setFillColor(color)
        pdf.setFont(font, actual)
        pdf.drawCentredString(x + width / 2, y + (height - actual) / 2 + 1.6, value)

    def label(text, x, baseline, size=8.5):
        pdf.setFillColor(black)
        pdf.setFont('Helvetica-BoldOblique', size)
        pdf.drawString(x, baseline, str(text).upper())

    def value_box(text, x, y, width, height=22, fill=None, color=blue, size=9.5):
        if fill:
            pdf.setFillColor(fill)
            pdf.roundRect(x, y, width, height, 7, fill=1, stroke=0)
        pdf.setStrokeColor(black)
        pdf.setLineWidth(1.6)
        pdf.roundRect(x, y, width, height, 7, fill=0, stroke=1)
        centered_text(text, x, y, width, height, color=color, size=size)

    def draw_image(reader, x, y, max_width, max_height):
        if not reader:
            return False
        try:
            image_width, image_height = reader.getSize()
            ratio = min(max_width / image_width, max_height / image_height)
            width, height = image_width * ratio, image_height * ratio
            pdf.drawImage(
                reader,
                x + (max_width - width) / 2,
                y + (max_height - height) / 2,
                width=width,
                height=height,
                preserveAspectRatio=True,
                mask='auto',
            )
            return True
        except Exception:
            return False

    # En-tête métier : logo FB Pack sur fond blanc (lot Design Bobine V4).
    logo = image_reader(context.get('logo_data_uri'))
    if not draw_image(logo, 28, 524, 132, 36):
        centered_text('FB PACK', 28, 522, 132, 40, color=navy, size=16)

    pdf.setStrokeColor(red)
    pdf.setLineWidth(2)
    pdf.roundRect(176, 523, 310, 38, 8, fill=0, stroke=1)
    centered_text('FICHE TECHNIQUE PRÉPRESSE', 176, 523, 310, 38, color=black, size=16)
    pdf.setFillColor(red)
    pdf.rect(502, 523, 100, 38, fill=1, stroke=0)
    centered_text(product.printing_process or 'FLEXO', 502, 523, 100, 38, color=colors.white, size=16)

    # Bloc d'identification, sans effet formulaire administratif.
    label('Code', 30, 505)
    value_box(product.ref_internal, 78, 493, 100)
    label('Date', 238, 505)
    value_box(product.date_creation.strftime('%d / %m / %Y'), 278, 493, 98)

    label('Client', 30, 470)
    value_box(product.client.name, 88, 458, 184)
    label('Article', 283, 470)
    value_box(product.name, 335, 458, 267)

    label('Graveur', 30, 435)
    value_box(product.graveur, 96, 423, 176)
    label('Référence graveur', 283, 435)
    value_box(product.ref_graveur, 404, 423, 132)

    dossier_options = [
        ('NOUVEAU DOSSIER', 'NOUVEAU', 30),
        ('REGRAVURE SIMPLE', 'REGRAVURE_SIMPLE', 190),
        ('REGRAVURE AVEC MODIFICATION', 'REGRAVURE_MODIF', 345),
    ]
    for text, value, x in dossier_options:
        label(text, x, 397, size=7.8)
        box_x = x + (122 if value != 'REGRAVURE_MODIF' else 187)
        pdf.setStrokeColor(black)
        pdf.setLineWidth(1.4)
        pdf.roundRect(box_x, 388, 12, 12, 3, fill=0, stroke=1)
        if product.type_dossier == value:
            pdf.setFillColor(blue)
            pdf.setFont('Helvetica-Bold', 15)
            pdf.drawString(box_x + 1, 386.5, '×')

    # Dimensions calculées et paramètres.
    label('Pas', 30, 365)
    value_box(f'{product.cut_length_mm or 0:g} mm', 78, 353, 98, fill=pink, color=black, size=10.5)
    label('Nombre de poses', 186, 365)
    value_box(product.nb_poses_pas or 0, 292, 353, 55, color=black)
    label('Développement', 357, 365)
    value_box(f'{product.developpement_mm or 0:g} mm', 450, 353, 102, fill=pink, color=black, size=10.5)

    label('Laize', 30, 335)
    value_box(f'{product.width_mm or 0:g} mm', 78, 323, 98, fill=pink, color=black, size=10.5)
    label('Nombre de poses', 186, 335)
    value_box(product.nb_poses_laize or 0, 292, 323, 55, color=black)
    label('Laize gravure', 357, 335)
    value_box(f'{product.laize_gravure_mm or 0:g} mm', 450, 323, 102, fill=pink, color=black, size=10.5)

    label("Support d'impression", 30, 300)
    value_box(product.support_impression, 154, 288, 310)
    label('Impression', 30, 270)
    value_box(product.impression, 106, 258, 155)
    label('Spot', 30, 240)
    value_box(product.spot, 72, 228, 145)

    # Grand visuel produit à droite.
    visual_x, visual_y, visual_w, visual_h = 625, 278, 188, 284
    roll_visual = image_reader(context.get('roll_visual_data_uri'))
    product_visual = roll_visual or image_reader(context.get('product_visual_data_uri'))
    if not draw_image(product_visual, visual_x, visual_y, visual_w, visual_h):
        pdf.setStrokeColor(grey)
        pdf.setLineWidth(7)
        path = pdf.beginPath()
        path.moveTo(665, 545)
        path.curveTo(625, 505, 635, 332, 682, 298)
        path.curveTo(720, 272, 790, 286, 796, 340)
        path.lineTo(806, 520)
        path.curveTo(807, 548, 790, 558, 760, 558)
        path.close()
        pdf.drawPath(path, fill=0, stroke=1)
        centered_text('VISUEL / MAQUETTE', 650, 405, 138, 16, color=colors.HexColor('#888888'), size=8)
        centered_text('PRODUIT', 650, 391, 138, 16, color=colors.HexColor('#888888'), size=8)

    # Pictogrammes sélectionnés.
    label(f'Sens {product.sens_bobine or "—"}', 650, 255, size=6.5)
    pdf.setStrokeColor(black)
    pdf.setLineWidth(1.2)
    pdf.roundRect(696, 241, 24, 28, 4, fill=0, stroke=1)
    pdf.setFillColor(colors.HexColor('#EF4444') if str(product.sens_bobine or '') in {'1','2','3','4'} else colors.HexColor('#0284C7'))
    pdf.rect(703, 243, 10, 21, fill=1, stroke=0)
    pdf.saveState()
    transforms = {'1': 180, '2': 0, '3': 90, '4': -90, '5': 180, '6': 0, '7': 90, '8': -90}
    angle = transforms.get(str(product.sens_bobine or ''), 0)
    pdf.translate(708, 253)
    pdf.rotate(angle)
    pdf.setFillColor(colors.white)
    pdf.setFont('Helvetica-Bold', 7)
    pdf.drawCentredString(0, -2.5, 'A')
    pdf.restoreState()

    label(f'Spot {product.spot_placement or "—"}', 735, 255, size=6.5)
    spot_x, spot_y = 779, 241
    pdf.setStrokeColor(black)
    pdf.roundRect(spot_x, spot_y, 24, 28, 4, fill=0, stroke=1)
    pdf.setFillColor(black)
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawCentredString(spot_x + 12, spot_y + 8, 'A')
    positions = {'1': (spot_x + 2, spot_y + 2), '2': (spot_x + 10, spot_y + 2), '3': (spot_x + 19, spot_y + 2), '4': (spot_x + 19, spot_y + 23)}
    dot_x, dot_y = positions.get(str(product.spot_placement or ''), (spot_x + 2, spot_y + 2))
    pdf.rect(dot_x, dot_y, 4, 3, fill=1, stroke=0)

    # Tableau des huit couleurs.
    table_x, table_top = 28, 216
    column_widths = [28, 65, 70, 70, 75, 75, 75, 328]
    column_titles = ['', '', 'COULEURS', 'ANILOX', 'ADHÉSIF', 'VISCOSITÉ', 'TYPE ENCRE', 'FORMULE ENCRE']
    row_height, header_height = 19, 20
    x_positions = [table_x]
    for width in column_widths:
        x_positions.append(x_positions[-1] + width)
    table_bottom = table_top - header_height - row_height * 8

    pdf.setStrokeColor(black)
    pdf.setLineWidth(1.1)
    pdf.rect(table_x, table_bottom, sum(column_widths), header_height + row_height * 8, fill=0, stroke=1)
    for x in x_positions[1:-1]:
        pdf.line(x, table_bottom, x, table_top)
    pdf.line(table_x, table_top - header_height, x_positions[-1], table_top - header_height)
    for index in range(1, 9):
        y = table_top - header_height - row_height * index
        pdf.line(table_x, y, x_positions[-1], y)
    for index, title in enumerate(column_titles):
        if title:
            centered_text(title, x_positions[index], table_top - header_height, column_widths[index], header_height, color=black, size=7.2)

    rows = context.get('color_rows', [])[:8]
    for index in range(8):
        color = rows[index] if index < len(rows) else {'ordre': index + 1, 'is_empty': True}
        y = table_top - header_height - row_height * (index + 1)
        centered_text(color.get('ordre', index + 1), x_positions[0], y, column_widths[0], row_height, color=black, size=8.5, font='Helvetica-Bold')
        if not color.get('is_empty'):
            try:
                pdf.setFillColor(colors.HexColor(color.get('couleur_hex') or '#FFFFFF'))
            except ValueError:
                pdf.setFillColor(colors.white)
            pdf.rect(x_positions[1] + 2, y + 2, column_widths[1] - 4, row_height - 4, fill=1, stroke=0)
            values = [
                color.get('nom_couleur', ''), color.get('anilox', ''), color.get('adhesif', ''),
                color.get('viscosite', ''), color.get('type_encre', ''), color.get('formule_encre', ''),
            ]
            for value_index, value in enumerate(values, start=2):
                centered_text(value, x_positions[value_index], y, column_widths[value_index], row_height, color=blue, size=7.5)

    if product.technical_notes:
        label('Observations :', 30, 36, size=6.8)
        pdf.setFillColor(black)
        pdf.setFont('Helvetica', 6.8)
        note = str(product.technical_notes).replace('\n', ' ')
        pdf.drawString(105, 36, note[:150])

    revision = context.get('latest_revision')
    generated_at = context.get('generated_at')
    generated = generated_at.strftime('%d/%m/%Y %H:%M') if generated_at else ''
    pdf.setFillColor(colors.HexColor('#777777'))
    pdf.setFont('Helvetica', 5.8)
    pdf.drawString(28, 14, f'{product.ref_internal} · {product.version}' + (f' · R{revision.revision_number}' if revision else ''))
    pdf.drawRightString(page_width - 28, 14, f'FB Pack ERP · {generated}')
    pdf.showPage()
    pdf.save()
    return output.getvalue()
