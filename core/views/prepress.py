import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from ..decorators import module_required
from ..forms import PrepressColorFormSet, ProductForm, ToolForm
from ..models import Client, TechnicalProduct, Tooling
from ..services.prepress_technical_sheet import (
    build_print_context,
    create_product_revision,
    generate_reportlab_pdf,
)

logger = logging.getLogger(__name__)


@login_required
@module_required('prepress')
def prepress_view(request):
    clients = Client.objects.annotate(
        nb_produits=Count('technicalproduct')
    ).order_by('name')

    # KPI Usure Outillage
    all_tools = Tooling.objects.select_related('product__client').all()
    kpi_critic = []
    kpi_warning = []
    kpi_good_count = 0

    for t in all_tools:
        wp = t.wear_percent
        if wp >= 90:
            kpi_critic.append(t)
        elif wp >= 75:
            kpi_warning.append(t)
        else:
            kpi_good_count += 1

    total_tools = len(all_tools)
    kpi_health = int((kpi_good_count / total_tools * 100)) if total_tools > 0 else 100

    return render(request, 'prepress.html', {
        'clients': clients,
        'kpi_critic': kpi_critic,
        'kpi_warning': kpi_warning,
        'kpi_health': kpi_health,
        'total_tools': total_tools,
    })


@login_required
@module_required('prepress')
def prepress_client_products(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    products = TechnicalProduct.objects.filter(client=client).order_by('is_obsolete', '-id')

    tools = Tooling.objects.filter(product__client=client)
    cliches = tools.filter(tool_type='CLICHE').order_by('-id')
    cylindres = tools.filter(tool_type='CYL').order_by('-id')

    return render(request, 'prepress_client_products.html', {
        'client': client,
        'products': products,
        'cliches': cliches,
        'cylindres': cylindres,
    })


def _save_color_formset(formset, product):
    """Sauvegarde au maximum 8 lignes et les renumérote dans l'ordre visuel."""
    order = 1
    for color_form in formset.forms:
        cleaned = getattr(color_form, 'cleaned_data', {})
        if not cleaned:
            continue
        instance = color_form.instance
        if cleaned.get('DELETE') or not (cleaned.get('nom_couleur') or '').strip():
            if instance.pk:
                instance.delete()
            continue
        color = color_form.save(commit=False)
        color.product = product
        color.ordre = order
        color.save()
        order += 1

    product.num_colors = order - 1
    product.save(update_fields=['num_colors', 'updated_at'])


@login_required
@module_required('prepress')
def add_product(request):
    initial = {}
    client_id = request.GET.get('client')
    if client_id:
        initial['client'] = client_id

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        formset = PrepressColorFormSet(
            request.POST,
            instance=form.instance,
            prefix='colors',
        )
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                product = form.save(commit=False)
                product.last_modified_by = request.user
                product.save()
                formset.instance = product
                _save_color_formset(formset, product)
                create_product_revision(
                    product,
                    request.user,
                    request.POST.get('revision_reason') or 'Création de la fiche technique',
                )
            messages.success(request, 'Fiche technique créée et sauvegardée avec succès.')
            return redirect('prepress_technical_sheet', product_id=product.pk)
    else:
        form = ProductForm(initial=initial)
        formset = PrepressColorFormSet(prefix='colors')

    return render(request, 'prepress/technical_sheet_form.html', {
        'form': form,
        'formset': formset,
        'product': None,
        'titre': 'Nouvelle fiche technique prépresse',
    })


@login_required
@module_required('prepress')
def edit_product(request, id):
    product = get_object_or_404(
        TechnicalProduct.objects.select_related('client'),
        id=id,
    )
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        formset = PrepressColorFormSet(
            request.POST,
            instance=product,
            prefix='colors',
        )
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                product = form.save(commit=False)
                product.last_modified_by = request.user
                product.save()
                _save_color_formset(formset, product)
                create_product_revision(
                    product,
                    request.user,
                    request.POST.get('revision_reason') or 'Mise à jour de la fiche technique',
                )
            messages.success(request, 'Fiche technique mise à jour et nouvelle révision enregistrée.')
            return redirect('prepress_technical_sheet', product_id=product.pk)
    else:
        form = ProductForm(instance=product)
        formset = PrepressColorFormSet(instance=product, prefix='colors')

    return render(request, 'prepress/technical_sheet_form.html', {
        'form': form,
        'formset': formset,
        'product': product,
        'titre': f'Modifier la fiche : {product.ref_internal}',
    })


@login_required
@module_required('prepress')
def add_tool(request):
    client_id = request.GET.get('client')

    if request.method == 'POST':
        form = ToolForm(request.POST)
        if form.is_valid():
            tool = form.save()
            if tool.product and tool.product.client_id:
                return redirect('prepress_client_products', client_id=tool.product.client_id)
            return redirect('prepress_view')
    else:
        form = ToolForm()
        if client_id:
            form.fields['product'].queryset = TechnicalProduct.objects.filter(client_id=client_id)

    return render(request, 'tool_form.html', {
        'form': form,
        'titre': 'Nouvel Outillage (Cliché / Cylindre)',
    })


@login_required
@module_required('prepress')
def edit_tool(request, id):
    tool = get_object_or_404(Tooling, id=id)
    if request.method == 'POST':
        form = ToolForm(request.POST, instance=tool)
        if form.is_valid():
            tool = form.save()
            if tool.product and tool.product.client_id:
                return redirect('prepress_client_products', client_id=tool.product.client_id)
            return redirect('prepress_view')
    else:
        form = ToolForm(instance=tool)

    return render(request, 'tool_form.html', {
        'form': form,
        'titre': f'Modifier Outillage {tool.serial_number}',
    })

# ============================================================
# PARC OUTILLAGES GLOBAL — CLICHÉS FLEXO & CYLINDRES HÉLIO
# Vue ajoutée sans modifier les vues client existantes.
# ============================================================
@login_required
@module_required('prepress')
def prepress_tooling_park(request):
    tools = list(
        Tooling.objects
        .select_related('product', 'product__client')
        .prefetch_related('product__couleurs_flexo')
        .order_by('-date_creation', '-id')
    )

    status_counts = {
        'GOOD': 0,
        'WATCH': 0,
        'WARNING': 0,
        'CRITICAL': 0,
        'END': 0,
    }
    type_counts = {'CLICHE': 0, 'CYL': 0}
    total_wear = 0

    for tool in tools:
        wear = tool.wear_percent
        total_wear += wear
        type_counts[tool.tool_type] = type_counts.get(tool.tool_type, 0) + 1

        tool.remaining_impressions_display = max(
            int(tool.max_impressions or 0) - int(tool.current_impressions or 0),
            0,
        )

        if wear >= 100:
            tool.park_status = 'END'
            tool.park_status_label = 'Fin de vie'
        elif wear >= 90:
            tool.park_status = 'CRITICAL'
            tool.park_status_label = 'Critique'
        elif wear >= 75:
            tool.park_status = 'WARNING'
            tool.park_status_label = 'À remplacer'
        elif wear >= 50:
            tool.park_status = 'WATCH'
            tool.park_status_label = 'À surveiller'
        else:
            tool.park_status = 'GOOD'
            tool.park_status_label = 'Bon état'
        status_counts[tool.park_status] += 1

    total_tools = len(tools)
    average_wear = round(total_wear / total_tools) if total_tools else 0
    park_health = max(0, 100 - average_wear)
    client_ids = {tool.product.client_id for tool in tools}
    clients = Client.objects.filter(id__in=client_ids).order_by('name')

    most_worn = sorted(tools, key=lambda item: item.wear_percent, reverse=True)[:10]

    # Analyse fournisseur/graveur : longévité observée par nombre moyen de tours.
    supplier_stats = {}
    for tool in tools:
        supplier_name = (tool.supplier_name or tool.product.graveur or 'Non renseigné').strip()
        tool.tool_supplier_name = supplier_name
        tool.tool_color_count = tool.color_count or tool.product.num_colors or 0
        tool.tool_color_names = tool.color_names
        if not tool.tool_color_names:
            tool.tool_color_names = [color.nom_couleur for color in tool.product.couleurs_flexo.all()]
        stat = supplier_stats.setdefault(supplier_name, {
            'name': supplier_name, 'count': 0, 'total_tours': 0,
            'total_wear': 0, 'max_tours': 0,
        })
        stat['count'] += 1
        stat['total_tours'] += int(tool.current_impressions or 0)
        stat['total_wear'] += tool.wear_percent
        stat['max_tours'] = max(stat['max_tours'], int(tool.current_impressions or 0))

    supplier_rows = []
    for stat in supplier_stats.values():
        stat['avg_tours'] = round(stat['total_tours'] / stat['count']) if stat['count'] else 0
        stat['avg_wear'] = round(stat['total_wear'] / stat['count']) if stat['count'] else 0
        supplier_rows.append(stat)
    supplier_rows.sort(key=lambda row: row['avg_tours'], reverse=True)
    supplier_names = sorted(supplier_stats.keys(), key=str.lower)
    supplier_chart = [row for row in supplier_rows if row['name'] != 'Non renseigné'][:10]

    return render(request, 'prepress_tooling_park.html', {
        'tools': tools,
        'clients': clients,
        'total_tools': total_tools,
        'total_cliches': type_counts['CLICHE'],
        'total_cylindres': type_counts['CYL'],
        'average_wear': average_wear,
        'park_health': park_health,
        'status_counts': status_counts,
        'chart_status_labels': ['Bon état', 'À surveiller', 'À remplacer', 'Critique', 'Fin de vie'],
        'chart_status_values': [
            status_counts['GOOD'], status_counts['WATCH'], status_counts['WARNING'],
            status_counts['CRITICAL'], status_counts['END'],
        ],
        'chart_type_labels': ['Clichés Flexo', 'Cylindres Hélio'],
        'chart_type_values': [type_counts['CLICHE'], type_counts['CYL']],
        'chart_worn_labels': [item.serial_number for item in most_worn],
        'chart_worn_values': [item.wear_percent for item in most_worn],
        'supplier_names': supplier_names,
        'supplier_rows': supplier_rows,
        'chart_supplier_labels': [row['name'] for row in supplier_chart],
        'chart_supplier_values': [row['avg_tours'] for row in supplier_chart],
    })



# ============================================================
# FICHES TECHNIQUES PRÉPRESSE ERP — LISTE, APERÇU, PDF, HISTORIQUE
# ============================================================
@login_required
@module_required('prepress')
@require_GET
def prepress_technical_sheet_list(request):
    products = (
        TechnicalProduct.objects
        .select_related('client', 'last_modified_by')
        .annotate(revision_count=Count('revisions', distinct=True))
        .order_by('is_obsolete', 'client__name', 'name')
    )

    query = (request.GET.get('q') or '').strip()[:120]
    client_id = (request.GET.get('client') or '').strip()
    process = (request.GET.get('process') or '').strip()
    status = (request.GET.get('status') or '').strip()

    if query:
        products = products.filter(
            Q(ref_internal__icontains=query)
            | Q(name__icontains=query)
            | Q(client__name__icontains=query)
            | Q(graveur__icontains=query)
            | Q(ref_graveur__icontains=query)
        )
    if client_id.isdigit():
        products = products.filter(client_id=int(client_id))
    if process in dict(TechnicalProduct.PRINTING_PROCESS_CHOICES):
        products = products.filter(printing_process=process)
    if status in dict(TechnicalProduct.BAT_STATUS_CHOICES):
        products = products.filter(bat_status=status)

    paginator = Paginator(products, 40)
    product_page = paginator.get_page(request.GET.get('page'))
    preserved = request.GET.copy()
    preserved.pop('page', None)

    all_products = TechnicalProduct.objects.all()
    context = {
        'product_page': product_page,
        'clients': Client.objects.filter(technicalproduct__isnull=False).distinct().order_by('name'),
        'process_choices': TechnicalProduct.PRINTING_PROCESS_CHOICES,
        'status_choices': TechnicalProduct.BAT_STATUS_CHOICES,
        'query_without_page': preserved.urlencode(),
        'stats': {
            'total': all_products.count(),
            'validated': all_products.filter(bat_status='VALIDE', is_obsolete=False).count(),
            'waiting': all_products.filter(bat_status='ATTENTE', is_obsolete=False).count(),
            'obsolete': all_products.filter(is_obsolete=True).count(),
        },
    }
    return render(request, 'prepress/technical_sheet_list.html', context)


@login_required
@module_required('prepress')
@require_GET
def prepress_technical_sheet_detail(request, product_id):
    product = get_object_or_404(
        TechnicalProduct.objects
        .select_related('client', 'last_modified_by')
        .prefetch_related('couleurs_flexo', 'revisions__created_by'),
        pk=product_id,
    )
    context = build_print_context(product)
    context['colors'] = product.couleurs_flexo.all().order_by('ordre', 'pk')
    return render(request, 'prepress/technical_sheet_detail.html', context)


@login_required
@module_required('prepress')
@require_GET
def prepress_technical_sheet_print(request, product_id):
    product = get_object_or_404(
        TechnicalProduct.objects.select_related('client').prefetch_related(
            'couleurs_flexo', 'revisions'
        ),
        pk=product_id,
    )
    context = build_print_context(product)
    context['auto_print'] = request.GET.get('auto') == '1'
    return render(request, 'prepress/technical_sheet_print.html', context)


@login_required
@module_required('prepress')
@require_GET
def prepress_technical_sheet_pdf(request, product_id):
    product = get_object_or_404(
        TechnicalProduct.objects.select_related('client').prefetch_related(
            'couleurs_flexo', 'revisions'
        ),
        pk=product_id,
    )
    context = build_print_context(product)
    context['is_pdf'] = True
    html_string = render_to_string(
        'prepress/technical_sheet_print.html',
        context,
        request=request,
    )
    pdf_engine = 'weasyprint'
    try:
        from weasyprint import HTML

        pdf_bytes = HTML(
            string=html_string,
            base_url=str(settings.BASE_DIR),
        ).write_pdf()
    except Exception as weasy_exc:
        logger.warning(
            'prepress_pdf_weasyprint_fallback product_id=%s error=%s',
            product.pk,
            type(weasy_exc).__name__,
        )
        pdf_engine = 'reportlab'
        try:
            pdf_bytes = generate_reportlab_pdf(product, context)
        except Exception as reportlab_exc:
            logger.error(
                'prepress_pdf_generation_failed product_id=%s weasy_error=%s reportlab_error=%s',
                product.pk,
                type(weasy_exc).__name__,
                type(reportlab_exc).__name__,
            )
            messages.error(
                request,
                "La génération PDF serveur a échoué. Utilisez la page Imprimer puis « Enregistrer au format PDF ».",
            )
            return redirect('prepress_technical_sheet_print', product_id=product.pk)

    filename = slugify(f'{product.ref_internal}-{product.name}') or f'fiche-{product.pk}'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['X-PDF-Engine'] = pdf_engine
    response['Content-Disposition'] = f'attachment; filename="fiche-technique-{filename}.pdf"'
    response['Cache-Control'] = 'no-store, private'
    return response


@login_required
@module_required('prepress')
@require_GET
def prepress_technical_sheet_revisions(request, product_id):
    product = get_object_or_404(
        TechnicalProduct.objects.select_related('client'),
        pk=product_id,
    )
    revisions = product.revisions.select_related('created_by').order_by('-revision_number')
    revision_page = Paginator(revisions, 20).get_page(request.GET.get('page'))
    return render(request, 'prepress/technical_sheet_revisions.html', {
        'product': product,
        'revision_page': revision_page,
    })
