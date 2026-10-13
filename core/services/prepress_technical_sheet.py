"""Services de sauvegarde et d'impression des fiches techniques prépresse."""

import base64
import mimetypes
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

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
    logo_path = finders.find('logo.png')
    if not logo_path:
        return ''
    try:
        path = Path(logo_path)
        return _bytes_to_data_uri(path.read_bytes(), path.name)
    except Exception:
        return ''


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

    # En-tête métier.
    pdf.setFillColor(navy)
    pdf.roundRect(28, 522, 132, 40, 6, fill=1, stroke=0)
    logo = image_reader(context.get('logo_data_uri'))
    if not draw_image(logo, 38, 528, 112, 28):
        centered_text('FB PACK', 28, 522, 132, 40, color=colors.HexColor('#FFBF32'), size=16)

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
    product_visual = image_reader(context.get('product_visual_data_uri'))
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
