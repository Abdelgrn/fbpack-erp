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