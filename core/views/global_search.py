from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from ..models import (
    BonCommande, Client, CommandeClient, Material, Machine, OrdreFabrication,
    OrdreMaintenance, Quote, StockLot, Supplier, TechnicalProduct, Tooling,
)
from ..models.permissions import user_has_module_access

MAX_PER_GROUP = 6


def _allowed(user, *modules):
    return user.is_superuser or any(user_has_module_access(user, module) for module in modules)


def _item(title, subtitle, url, kind, identifier):
    return {'title': str(title), 'subtitle': str(subtitle or ''), 'url': url, 'kind': kind, 'id': identifier}


@login_required
@require_GET
def global_search_api(request):
    query = ' '.join(request.GET.get('q', '').strip().split())[:100]
    if len(query) < 2:
        return JsonResponse({'ok': True, 'query': query, 'groups': [], 'total': 0})

    groups = []

    def add_group(key, label, icon, items):
        if items:
            groups.append({'key': key, 'label': label, 'icon': icon, 'items': items})

    if _allowed(request.user, 'crm'):
        clients = Client.objects.filter(
            Q(name__icontains=query) | Q(code_client__icontains=query) |
            Q(city__icontains=query) | Q(phone__icontains=query) | Q(email__icontains=query)
        ).order_by('name')[:MAX_PER_GROUP]
        add_group('clients', 'Clients', '👥', [
            _item(x.name, ' · '.join(filter(None, [x.code_client, x.city, x.phone])), reverse('client_detail', args=[x.pk]), 'Client', x.pk)
            for x in clients
        ])

        quotes = Quote.objects.filter(
            Q(reference__icontains=query) | Q(client__name__icontains=query) | Q(notes__icontains=query)
        ).select_related('client').order_by('-date')[:MAX_PER_GROUP]
        add_group('quotes', 'Devis', '🧾', [
            _item(x.reference, f'{x.client.name} · {x.get_status_display()}', reverse('edit_quote', args=[x.pk]), 'Devis', x.pk)
            for x in quotes
        ])

        orders = CommandeClient.objects.filter(
            Q(reference__icontains=query) | Q(client__name__icontains=query) | Q(notes__icontains=query)
        ).select_related('client').order_by('-date_commande')[:MAX_PER_GROUP]
        add_group('orders', 'Commandes clients', '📦', [
            _item(x.reference, f'{x.client.name} · {x.get_statut_display()}', reverse('commande_detail', args=[x.pk]), 'Commande', x.pk)
            for x in orders
        ])

    if _allowed(request.user, 'planning', 'planification', 'production'):
        production_orders = OrdreFabrication.objects.filter(
            Q(numero_of__icontains=query) | Q(numero_lot__icontains=query) |
            Q(client__name__icontains=query) | Q(produit__name__icontains=query)
        ).select_related('client', 'produit').order_by('-date_creation')[:MAX_PER_GROUP]
        add_group('production-orders', 'Ordres de fabrication', '🏭', [
            _item(x.numero_of, f'{x.client.name} · {x.produit.name} · {x.get_statut_display()}', reverse('of_detail', args=[x.pk]), 'OF', x.pk)
            for x in production_orders
        ])

    if _allowed(request.user, 'prepress'):
        products = TechnicalProduct.objects.filter(
            Q(ref_internal__icontains=query) | Q(name__icontains=query) |
            Q(client__name__icontains=query) | Q(ref_graveur__icontains=query)
        ).select_related('client').order_by('name')[:MAX_PER_GROUP]
        add_group('products', 'Produits', '🎨', [
            _item(x.name, f'{x.ref_internal} · {x.client.name}', reverse('edit_product', args=[x.pk]), 'Produit', x.pk)
            for x in products
        ])

        tools = Tooling.objects.filter(
            Q(serial_number__icontains=query) | Q(supplier_name__icontains=query) |
            Q(product__name__icontains=query) | Q(product__client__name__icontains=query)
        ).select_related('product__client').order_by('serial_number')[:MAX_PER_GROUP]
        tooling_url = reverse('prepress_tooling_park')
        add_group('toolings', 'Outillages', '🧰', [
            _item(x.serial_number, f'{x.product.name} · {x.get_tool_type_display()} · usure {x.wear_percent}%', f'{tooling_url}?q={x.serial_number}', 'Outillage', x.pk)
            for x in tools
        ])

    if _allowed(request.user, 'stock'):
        materials = Material.objects.filter(is_archived=False).filter(
            Q(name__icontains=query) | Q(code__icontains=query) | Q(supplier__name__icontains=query)
        ).select_related('supplier').order_by('name')[:MAX_PER_GROUP]
        add_group('materials', 'Matières', '🧪', [
            _item(x.name, f'{x.code or "Sans code"} · stock {x.quantity:g} {x.unit}', reverse('edit_material', args=[x.pk]), 'Matière', x.pk)
            for x in materials
        ])

        lots = StockLot.objects.filter(
            Q(numero_lot__icontains=query) | Q(material__name__icontains=query) |
            Q(fournisseur__name__icontains=query)
        ).select_related('material', 'fournisseur').order_by('-date_reception')[:MAX_PER_GROUP]
        add_group('lots', 'Lots', '🏷️', [
            _item(x.numero_lot, f'{x.material.name} · {x.get_statut_display()} · {x.quantite_restante:g} kg', reverse('lot_detail', args=[x.pk]), 'Lot', x.pk)
            for x in lots
        ])

        suppliers = Supplier.objects.filter(is_archived=False).filter(
            Q(name__icontains=query) | Q(email__icontains=query) | Q(contacts__nom__icontains=query)
        ).distinct().order_by('name')[:MAX_PER_GROUP]
        add_group('suppliers', 'Fournisseurs', '🚚', [
            _item(x.name, x.email or 'Fournisseur', reverse('edit_supplier', args=[x.pk]), 'Fournisseur', x.pk)
            for x in suppliers
        ])

        purchase_orders = BonCommande.objects.filter(
            Q(reference__icontains=query) | Q(fournisseur__name__icontains=query)
        ).select_related('fournisseur').order_by('-date_commande')[:MAX_PER_GROUP]
        add_group('purchase-orders', 'Commandes fournisseurs', '🛒', [
            _item(x.reference, f'{x.fournisseur.name} · {x.get_statut_display()}', reverse('stock_advanced') + '?tab=achats', 'Bon de commande', x.pk)
            for x in purchase_orders
        ])

    if _allowed(request.user, 'maintenance'):
        machines = Machine.objects.filter(est_active=True).filter(
            Q(name__icontains=query) | Q(code_machine__icontains=query) |
            Q(marque__icontains=query) | Q(modele__icontains=query) | Q(numero_serie__icontains=query)
        ).order_by('name')[:MAX_PER_GROUP]
        add_group('machines', 'Machines', '⚙️', [
            _item(x.name, f'{x.code_machine} · {x.get_status_display()}', reverse('maintenance_machine_detail', args=[x.pk]), 'Machine', x.pk)
            for x in machines
        ])

        maintenance_orders = OrdreMaintenance.objects.filter(
            Q(numero_om__icontains=query) | Q(titre__icontains=query) |
            Q(description_probleme__icontains=query) | Q(machine__name__icontains=query) |
            Q(machine__code_machine__icontains=query)
        ).select_related('machine').order_by('-date_creation')[:MAX_PER_GROUP]
        add_group('maintenance', 'Maintenance', '🔧', [
            _item(x.numero_om, f'{x.machine.name} · {x.titre} · {x.get_statut_display()}', reverse('om_detail', args=[x.pk]), 'OM', x.pk)
            for x in maintenance_orders
        ])

    total = sum(len(group['items']) for group in groups)
    return JsonResponse({'ok': True, 'query': query, 'groups': groups, 'total': total})
