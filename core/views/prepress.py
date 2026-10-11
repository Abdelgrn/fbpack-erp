from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count

from ..models import TechnicalProduct, Tooling, Client
from ..forms import ProductForm, ToolForm, PrepressColorFormSet


@login_required
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


@login_required
def add_product(request):
    initial = {}
    client_id = request.GET.get('client')
    if client_id:
        initial['client'] = client_id

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            formset = PrepressColorFormSet(request.POST, instance=product)
            if formset.is_valid():
                formset.save()
            return redirect('prepress_client_products', client_id=product.client_id)
    else:
        form = ProductForm(initial=initial)
        formset = PrepressColorFormSet()

    return render(request, 'product_form.html', {
        'form': form,
        'formset': formset,
        'titre': 'Nouvelle Fiche Technique Flexo',
    })


@login_required
def edit_product(request, id):
    product = get_object_or_404(TechnicalProduct, id=id)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        formset = PrepressColorFormSet(request.POST, instance=product)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('prepress_client_products', client_id=product.client_id)
    else:
        form = ProductForm(instance=product)
        formset = PrepressColorFormSet(instance=product)

    return render(request, 'product_form.html', {
        'form': form,
        'formset': formset,
        'titre': f'Modifier Fiche Technique : {product.ref_internal}',
    })


@login_required
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

