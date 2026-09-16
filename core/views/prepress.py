from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from ..models import TechnicalProduct, Tooling
from ..forms import ProductForm, ToolForm

@login_required
def prepress_view(request):
    products = TechnicalProduct.objects.all().order_by('-id')
    tools = Tooling.objects.all().order_by('-id')
    return render(request, 'prepress.html', {'products': products, 'tools': tools})


@login_required
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('prepress_view')
    else:
        form = ProductForm()
    return render(request, 'product_form.html', {'form': form, 'titre': 'Nouveau Produit Technique'})


@login_required
def edit_product(request, id):
    product = get_object_or_404(TechnicalProduct, id=id)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            return redirect('prepress_view')
    else:
        form = ProductForm(instance=product)
    return render(request, 'product_form.html', {
        'form': form,
        'titre': f'Modifier {product.ref_internal}'
    })


@login_required
def add_tool(request):
    if request.method == 'POST':
        form = ToolForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('prepress_view')
    else:
        form = ToolForm()
    return render(request, 'tool_form.html', {'form': form, 'titre': 'Nouvel Outillage'})


@login_required
def edit_tool(request, id):
    tool = get_object_or_404(Tooling, id=id)
    if request.method == 'POST':
        form = ToolForm(request.POST, instance=tool)
        if form.is_valid():
            form.save()
            return redirect('prepress_view')
    else:
        form = ToolForm(instance=tool)
    return render(request, 'tool_form.html', {
        'form': form,
        'titre': f'Modifier Outillage {tool.serial_number}'
    })