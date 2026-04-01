import os
import datetime
import json
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Count, Q, Avg
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib import messages

from .models import (
    Client, ClientContact, InteractionLog, Opportunite,
    TechnicalProduct, Tooling, Quote,
    ProductionOrder, Machine, ConsumptionLog,
    Material, Supplier, ConsommationEncre, ProductionEntry,
    PurchaseOrder,
    # Nouveaux modèles stock avancé
    StockLocation, StockLot, StockMovement,
    DemandeAchat, BonCommande, LigneBonCommande, StockSeuil,
)
from .forms import (
    ClientForm, ClientContactForm, InteractionLogForm, OpportuniteForm,
    ProductForm, ToolForm, QuoteForm,
    ProductionOrderForm, SupplierForm, MaterialForm, ConsommationEncreForm,
    MachineForm, ProductionEntryForm,
)


# ===========================================================================
# --- DASHBOARD ---
# ===========================================================================

@login_required
def dashboard(request):
    context = {
        'count_clients': Client.objects.count(),
        'count_of_running': ProductionOrder.objects.filter(status='IN_PROGRESS').count(),
        'low_stock_count': len([m for m in Material.objects.all() if m.is_low_stock()]),
        'machines': Machine.objects.all(),
        'orders_per_machine': ProductionOrder.objects.values('machine__name').annotate(count=Count('id')),
        'count_opportunites': Opportunite.objects.filter(status__in=['PROSPECT', 'QUALIFICATION', 'PROPOSITION', 'NEGOCIATION']).count(),
        'count_devis_envoyes': Quote.objects.filter(status='SENT').count(),
        'pipeline_total': Opportunite.objects.exclude(status__in=['GAGNE', 'PERDU']).aggregate(total=Sum('valeur_estimee'))['total'] or 0,
    }
    return render(request, 'dashboard.html', context)


@login_required
def production_gantt(request):
    orders = ProductionOrder.objects.exclude(status='DONE').order_by('machine', 'start_time')
    return render(request, 'production/gantt.html', {'orders': orders})


@login_required
def reporting(request):
    delayed_ofs = ProductionOrder.objects.filter(status='LATE')
    top_clients = ProductionOrder.objects.values('client__name').annotate(total_kg=Sum('produced_qty')).order_by('-total_kg')[:5]
    top_consumptions = ConsumptionLog.objects.values('material__name').annotate(total_used=Sum('quantity_used')).order_by('-total_used')[:5]
    total_devis = Quote.objects.count()
    devis_acceptes = Quote.objects.filter(status__in=['ACCEPTED', 'SIGNED']).count()
    taux_conversion = round((devis_acceptes / total_devis * 100), 1) if total_devis > 0 else 0
    context = {
        'delayed_ofs': delayed_ofs,
        'top_clients_labels': [c['client__name'] for c in top_clients],
        'top_clients_data': [c['total_kg'] for c in top_clients],
        'top_consumptions_labels': [c['material__name'] for c in top_consumptions],
        'top_consumptions_data': [c['total_used'] for c in top_consumptions],
        'taux_conversion': taux_conversion,
        'total_devis': total_devis,
        'devis_acceptes': devis_acceptes,
    }
    return render(request, 'reporting.html', context)


# ===========================================================================
# --- CRM ---
# ===========================================================================

@login_required
def crm_view(request):
    status_filter = request.GET.get('status', '')
    segment_filter = request.GET.get('segment', '')
    region_filter = request.GET.get('region', '')
    search = request.GET.get('q', '')
    clients = Client.objects.all().order_by('name')
    if status_filter: clients = clients.filter(status=status_filter)
    if segment_filter: clients = clients.filter(segment=segment_filter)
    if region_filter: clients = clients.filter(region=region_filter)
    if search:
        clients = clients.filter(Q(name__icontains=search) | Q(city__icontains=search) | Q(code_client__icontains=search))
    quotes = Quote.objects.all().order_by('-date')
    opportunites = Opportunite.objects.all().order_by('-date_ouverture')
    pipeline_stages = []
    for stage_code, stage_label in Opportunite.STAGE_CHOICES:
        count = Opportunite.objects.filter(status=stage_code).count()
        montant = Opportunite.objects.filter(status=stage_code).aggregate(t=Sum('valeur_estimee'))['t'] or 0
        pipeline_stages.append({'code': stage_code, 'label': stage_label, 'count': count, 'montant': montant})
    context = {
        'clients': clients, 'quotes': quotes, 'opportunites': opportunites,
        'pipeline_stages': pipeline_stages, 'status_filter': status_filter,
        'segment_filter': segment_filter, 'region_filter': region_filter, 'search': search,
        'status_choices': Client.STATUS_CHOICES, 'segment_choices': Client.SEGMENT_CHOICES,
        'region_choices': Client.REGION_CHOICES,
    }
    return render(request, 'crm.html', context)


@login_required
def client_detail(request, id):
    client = get_object_or_404(Client, id=id)
    contacts = ClientContact.objects.filter(client=client)
    interactions = InteractionLog.objects.filter(client=client).order_by('-date')[:20]
    opportunites = Opportunite.objects.filter(client=client).order_by('-date_ouverture')
    quotes = Quote.objects.filter(client=client).order_by('-date')
    orders = ProductionOrder.objects.filter(client=client).order_by('-start_time')[:5]
    context = {'client': client, 'contacts': contacts, 'interactions': interactions,
               'opportunites': opportunites, 'quotes': quotes, 'orders': orders}
    return render(request, 'crm/client_detail.html', context)


@login_required
def add_client(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f"Client « {client.name} » créé.")
            return redirect('client_detail', id=client.id)
    else:
        form = ClientForm()
    return render(request, 'crm/client_form.html', {'form': form, 'titre': 'Nouveau Client'})


@login_required
def edit_client(request, id):
    client = get_object_or_404(Client, id=id)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, "Client mis à jour.")
            return redirect('client_detail', id=client.id)
    else:
        form = ClientForm(instance=client)
    return render(request, 'crm/client_form.html', {'form': form, 'titre': f'Modifier {client.name}', 'client': client})


@login_required
def add_contact(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if request.method == 'POST':
        form = ClientContactForm(request.POST)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.client = client
            contact.save()
            messages.success(request, f"Contact « {contact.name} » ajouté.")
            return redirect('client_detail', id=client_id)
    else:
        form = ClientContactForm()
    return render(request, 'crm/contact_form.html', {'form': form, 'client': client, 'titre': 'Nouveau Contact'})


@login_required
def edit_contact(request, id):
    contact = get_object_or_404(ClientContact, id=id)
    if request.method == 'POST':
        form = ClientContactForm(request.POST, instance=contact)
        if form.is_valid():
            form.save()
            messages.success(request, "Contact mis à jour.")
            return redirect('client_detail', id=contact.client.id)
    else:
        form = ClientContactForm(instance=contact)
    return render(request, 'crm/contact_form.html', {'form': form, 'client': contact.client, 'titre': f'Modifier {contact.name}'})


@login_required
def delete_contact(request, id):
    contact = get_object_or_404(ClientContact, id=id)
    client_id = contact.client.id
    if request.method == 'POST':
        contact.delete()
        messages.success(request, "Contact supprimé.")
    return redirect('client_detail', id=client_id)


@login_required
def add_interaction(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if request.method == 'POST':
        form = InteractionLogForm(request.POST, client=client)
        if form.is_valid():
            interaction = form.save(commit=False)
            interaction.client = client
            interaction.save()
            messages.success(request, "Interaction enregistrée.")
            return redirect('client_detail', id=client_id)
    else:
        form = InteractionLogForm(client=client)
    return render(request, 'crm/interaction_form.html', {'form': form, 'client': client, 'titre': 'Nouvelle Interaction'})


@login_required
def opportunites_view(request):
    opportunites = Opportunite.objects.all().order_by('-date_ouverture')
    pipeline = {}
    for stage_code, stage_label in Opportunite.STAGE_CHOICES:
        pipeline[stage_code] = {
            'label': stage_label,
            'items': Opportunite.objects.filter(status=stage_code),
            'total': Opportunite.objects.filter(status=stage_code).aggregate(t=Sum('valeur_estimee'))['t'] or 0,
        }
    return render(request, 'crm/opportunites.html', {'opportunites': opportunites, 'pipeline': pipeline})


@login_required
def add_opportunite(request):
    if request.method == 'POST':
        form = OpportuniteForm(request.POST)
        if form.is_valid():
            opp = form.save()
            messages.success(request, f"Opportunité « {opp.titre} » créée.")
            return redirect('crm_view')
    else:
        initial = {}
        client_id = request.GET.get('client_id')
        if client_id: initial['client'] = client_id
        form = OpportuniteForm(initial=initial)
    return render(request, 'crm/opportunite_form.html', {'form': form, 'titre': 'Nouvelle Opportunité'})


@login_required
def edit_opportunite(request, id):
    opp = get_object_or_404(Opportunite, id=id)
    if request.method == 'POST':
        form = OpportuniteForm(request.POST, instance=opp)
        if form.is_valid():
            form.save()
            messages.success(request, "Opportunité mise à jour.")
            return redirect('crm_view')
    else:
        form = OpportuniteForm(instance=opp)
    return render(request, 'crm/opportunite_form.html', {'form': form, 'opp': opp, 'titre': f'Modifier : {opp.titre}'})


@login_required
def delete_opportunite(request, id):
    opp = get_object_or_404(Opportunite, id=id)
    if request.method == 'POST':
        opp.delete()
        messages.success(request, "Opportunité supprimée.")
    return redirect('crm_view')


@login_required
def quotes_view(request):
    quotes = Quote.objects.all().order_by('-date')
    return render(request, 'crm/quotes_list.html', {'quotes': quotes})


@login_required
def add_quote(request):
    if request.method == 'POST':
        form = QuoteForm(request.POST, request.FILES)
        if form.is_valid():
            quote = form.save()
            messages.success(request, f"Devis {quote.reference} créé.")
            return redirect('crm_view')
    else:
        initial = {}
        client_id = request.GET.get('client_id')
        if client_id: initial['client'] = client_id
        form = QuoteForm(initial=initial)
    return render(request, 'crm/quote_form.html', {'form': form, 'titre': 'Nouveau Devis'})


@login_required
def edit_quote(request, id):
    quote = get_object_or_404(Quote, id=id)
    if request.method == 'POST':
        form = QuoteForm(request.POST, request.FILES, instance=quote)
        if form.is_valid():
            form.save()
            messages.success(request, "Devis mis à jour.")
            return redirect('crm_view')
    else:
        form = QuoteForm(instance=quote)
    return render(request, 'crm/quote_form.html', {'form': form, 'titre': f'Modifier Devis {quote.reference}'})


@login_required
def convert_quote_to_order(request, id):
    quote = get_object_or_404(Quote, id=id)
    if quote.status in ['ACCEPTED', 'SIGNED'] and not quote.commande_creee:
        quote.commande_creee = True
        quote.save()
        messages.success(request, f"Devis {quote.reference} converti en commande.")
    return redirect('crm_view')


# ===========================================================================
# --- PRÉPRESSE ---
# ===========================================================================

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
    return render(request, 'product_form.html', {'form': form, 'titre': f'Modifier {product.ref_internal}'})


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
    return render(request, 'tool_form.html', {'form': form, 'titre': f'Modifier Outillage {tool.serial_number}'})


# ===========================================================================
# --- PRODUCTION (OF) ---
# ===========================================================================

@login_required
def production_view(request):
    ofs = ProductionOrder.objects.all().order_by('-start_time')
    return render(request, 'production_list.html', {'ofs': ofs})


@login_required
def add_production(request):
    if request.method == 'POST':
        form = ProductionOrderForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('production_view')
    else:
        form = ProductionOrderForm()
    return render(request, 'production_form.html', {'form': form, 'titre': 'Créer un Ordre de Fabrication'})


@login_required
def edit_production(request, id):
    of = get_object_or_404(ProductionOrder, id=id)
    if request.method == 'POST':
        form = ProductionOrderForm(request.POST, request.FILES, instance=of)
        if form.is_valid():
            form.save()
            return redirect('production_view')
    else:
        form = ProductionOrderForm(instance=of)
    return render(request, 'production_form.html', {'form': form, 'titre': f'Modifier OF {of.of_number}'})


# ===========================================================================
# --- STOCKS ---
# ===========================================================================

@login_required
def stock_view(request):
    materials = Material.objects.all()
    suppliers = Supplier.objects.all()
    consos = ConsommationEncre.objects.all().order_by('-date')
    return render(request, 'stock_list.html', {'materials': materials, 'suppliers': suppliers, 'consos': consos})


@login_required
def add_material(request):
    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('stock_view')
    else:
        form = MaterialForm()
    return render(request, 'stock_list.html', {'form': form, 'titre': 'Nouveau Matériau'})


@login_required
def add_supplier(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('stock_view')
    else:
        form = SupplierForm()
    return render(request, 'stock_list.html', {'form': form, 'titre': 'Nouveau Fournisseur'})


@login_required
def add_consommation(request):
    if request.method == 'POST':
        form = ConsommationEncreForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('conso_list')
    else:
        form = ConsommationEncreForm()
    return render(request, 'stock_list.html', {'form': form, 'titre': 'Nouvelle Consommation'})


@login_required
def conso_list_view(request):
    consos = ConsommationEncre.objects.all().order_by('-date')
    return render(request, 'stock_list.html', {'consos': consos})


# ===========================================================================
# --- STOCK AVANCÉ ---
# ===========================================================================

@login_required
def stock_advanced_view(request):
    materials = Material.objects.all()
    suppliers = Supplier.objects.all()
    consos = ConsommationEncre.objects.all().order_by('-date')
    locations = StockLocation.objects.filter(is_active=True)
    lots = StockLot.objects.select_related('material', 'fournisseur', 'emplacement').order_by('-date_reception')[:50]
    mouvements = StockMovement.objects.select_related('material', 'lot', 'utilisateur', 'machine').order_by('-date')[:100]
    demandes = DemandeAchat.objects.select_related('material', 'demandeur').order_by('-date_creation')[:20]
    bons_commande = BonCommande.objects.select_related('fournisseur').order_by('-date_commande')[:20]

    total_matieres = materials.count()
    alertes_stock = [m for m in materials if m.is_low_stock()]
    lots_bloques = StockLot.objects.filter(statut='BLOQUE').count()
    lots_attente = StockLot.objects.filter(statut='EN_ATTENTE').count()
    da_en_attente = DemandeAchat.objects.filter(statut__in=['SOUMISE', 'VALIDEE']).count()
    bc_en_cours = BonCommande.objects.filter(statut__in=['ENVOYE', 'CONFIRME', 'RECU_PARTIEL']).count()
    valeur_stock_total = sum(
        float(lot.quantite_restante) * float(lot.prix_unitaire)
        for lot in StockLot.objects.filter(statut='CONFORME')
    )

    from datetime import date
    date_7j = date.today() - timedelta(days=7)
    top_consos = ConsommationEncre.objects.filter(date__gte=date_7j).values(
        'support'
    ).annotate(
        total=Sum('encre_noir') + Sum('encre_magenta') + Sum('encre_jaune') + Sum('encre_cyan')
    ).order_by('-total')[:5]

    previsions = []
    for seuil in StockSeuil.objects.select_related('material').all():
        if seuil.consommation_journaliere_moy > 0:
            jours = seuil.jours_de_stock
            if jours < 30:
                previsions.append({
                    'material': seuil.material.name,
                    'stock_actuel': seuil.material.quantity,
                    'jours_restants': jours,
                    'date_rupture': seuil.date_rupture_prevue,
                    'conso_jour': seuil.consommation_journaliere_moy,
                    'critique': jours < 7,
                })
    previsions.sort(key=lambda x: x['jours_restants'])

    context = {
        'materials': materials, 'suppliers': suppliers, 'consos': consos,
        'locations': locations, 'lots': lots, 'mouvements': mouvements,
        'demandes': demandes, 'bons_commande': bons_commande,
        'total_matieres': total_matieres, 'alertes_stock': alertes_stock,
        'nb_alertes': len(alertes_stock), 'lots_bloques': lots_bloques,
        'lots_attente': lots_attente, 'da_en_attente': da_en_attente,
        'bc_en_cours': bc_en_cours, 'valeur_stock_total': round(valeur_stock_total, 2),
        'previsions': previsions, 'top_consos': list(top_consos),
    }
    return render(request, 'stock/stock_advanced.html', context)


@login_required
def location_list(request):
    locations = StockLocation.objects.all()
    return render(request, 'stock/stock_advanced.html', {'locations': locations})


@login_required
def location_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        type_loc = request.POST.get('type', 'GENERAL')
        desc = request.POST.get('description', '')
        if name:
            StockLocation.objects.create(name=name, type=type_loc, description=desc)
            messages.success(request, f"Emplacement « {name} » créé.")
        return redirect('stock_advanced')
    return redirect('stock_advanced')


@login_required
def location_delete(request, id):
    loc = get_object_or_404(StockLocation, id=id)
    if request.method == 'POST':
        loc.delete()
        messages.success(request, "Emplacement supprimé.")
    return redirect('stock_advanced')


@login_required
def lot_list(request):
    lots = StockLot.objects.select_related('material', 'fournisseur', 'emplacement').order_by('-date_reception')
    return render(request, 'stock/stock_advanced.html', {'lots': lots})


@login_required
def lot_add(request):
    if request.method == 'POST':
        try:
            material_id = request.POST.get('material')
            numero_lot = request.POST.get('numero_lot', '').strip()
            date_reception = request.POST.get('date_reception')
            fournisseur_id = request.POST.get('fournisseur') or None
            emplacement_id = request.POST.get('emplacement') or None
            quantite = float(request.POST.get('quantite_initiale', 0))
            prix = float(request.POST.get('prix_unitaire', 0))
            statut = request.POST.get('statut', 'EN_ATTENTE')
            notes = request.POST.get('notes', '')
            material = get_object_or_404(Material, id=material_id)
            fournisseur = Supplier.objects.filter(id=fournisseur_id).first() if fournisseur_id else None
            emplacement = StockLocation.objects.filter(id=emplacement_id).first() if emplacement_id else None
            lot = StockLot.objects.create(
                material=material, numero_lot=numero_lot,
                date_reception=date_reception, fournisseur=fournisseur,
                emplacement=emplacement, quantite_initiale=quantite,
                quantite_restante=quantite, prix_unitaire=prix,
                statut=statut, notes=notes, created_by=request.user
            )
            if request.FILES.get('certificat_qualite'):
                lot.certificat_qualite = request.FILES['certificat_qualite']
                lot.save()
            if statut == 'CONFORME':
                StockMovement.objects.create(
                    type='ENTREE', material=material, lot=lot, quantite=quantite,
                    emplacement_destination=emplacement, utilisateur=request.user,
                    motif=f"Réception lot {numero_lot}",
                )
            messages.success(request, f"Lot {numero_lot} créé.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
        return redirect('stock_advanced')
    return redirect('stock_advanced')


@login_required
def lot_valider(request, id):
    lot = get_object_or_404(StockLot, id=id)
    if request.method == 'POST':
        ancien_statut = lot.statut
        lot.statut = 'CONFORME'
        lot.save()
        if ancien_statut != 'CONFORME':
            StockMovement.objects.create(
                type='ENTREE', material=lot.material, lot=lot,
                quantite=lot.quantite_restante,
                emplacement_destination=lot.emplacement,
                utilisateur=request.user,
                motif=f"Validation lot {lot.numero_lot}",
            )
        messages.success(request, f"Lot {lot.numero_lot} validé.")
    return redirect('stock_advanced')


@login_required
def lot_bloquer(request, id):
    lot = get_object_or_404(StockLot, id=id)
    if request.method == 'POST':
        lot.statut = 'BLOQUE'
        lot.save()
        messages.warning(request, f"Lot {lot.numero_lot} bloqué.")
    return redirect('stock_advanced')


@login_required
def lot_detail(request, id):
    lot = get_object_or_404(StockLot, id=id)
    mouvements = lot.mouvements.select_related('utilisateur', 'machine', 'of').order_by('-date')
    return render(request, 'stock/lot_detail.html', {'lot': lot, 'mouvements': mouvements})


@login_required
def mouvement_add(request):
    if request.method == 'POST':
        try:
            material = get_object_or_404(Material, id=request.POST.get('material'))
            type_mvt = request.POST.get('type')
            quantite = float(request.POST.get('quantite', 0))
            lot_id = request.POST.get('lot') or None
            src_id = request.POST.get('emplacement_source') or None
            dst_id = request.POST.get('emplacement_destination') or None
            of_id = request.POST.get('of') or None
            machine_id = request.POST.get('machine') or None
            motif = request.POST.get('motif', '')
            lot = StockLot.objects.filter(id=lot_id).first() if lot_id else None
            src = StockLocation.objects.filter(id=src_id).first() if src_id else None
            dst = StockLocation.objects.filter(id=dst_id).first() if dst_id else None
            of_obj = ProductionOrder.objects.filter(id=of_id).first() if of_id else None
            machine_obj = Machine.objects.filter(id=machine_id).first() if machine_id else None
            StockMovement.objects.create(
                type=type_mvt, material=material, lot=lot, quantite=quantite,
                emplacement_source=src, emplacement_destination=dst,
                of=of_obj, machine=machine_obj,
                utilisateur=request.user, motif=motif,
            )
            messages.success(request, f"Mouvement enregistré.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
        return redirect('stock_advanced')
    return redirect('stock_advanced')


@login_required
def da_add(request):
    if request.method == 'POST':
        try:
            import random, string
            ref = 'DA-' + ''.join(random.choices(string.digits, k=6))
            material = get_object_or_404(Material, id=request.POST.get('material'))
            DemandeAchat.objects.create(
                reference=ref, material=material,
                quantite_demandee=float(request.POST.get('quantite_demandee', 0)),
                motif=request.POST.get('motif', ''),
                urgence=request.POST.get('urgence', 'NORMALE'),
                statut='SOUMISE', demandeur=request.user,
                date_besoin=request.POST.get('date_besoin') or None,
            )
            messages.success(request, f"Demande d'achat créée.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
        return redirect('stock_advanced')
    return redirect('stock_advanced')


@login_required
def da_valider(request, id):
    da = get_object_or_404(DemandeAchat, id=id)
    if request.method == 'POST':
        da.statut = 'VALIDEE'
        da.valideur = request.user
        da.date_validation = timezone.now().date()
        da.save()
        messages.success(request, f"DA {da.reference} validée.")
    return redirect('stock_advanced')


@login_required
def da_refuser(request, id):
    da = get_object_or_404(DemandeAchat, id=id)
    if request.method == 'POST':
        da.statut = 'REFUSEE'
        da.save()
        messages.warning(request, f"DA {da.reference} refusée.")
    return redirect('stock_advanced')


@login_required
def bc_add(request):
    if request.method == 'POST':
        try:
            import random, string
            ref = 'BC-' + ''.join(random.choices(string.digits, k=6))
            fournisseur = get_object_or_404(Supplier, id=request.POST.get('fournisseur'))
            bc = BonCommande.objects.create(
                reference=ref, fournisseur=fournisseur, statut='BROUILLON',
                date_livraison_prevue=request.POST.get('date_livraison_prevue') or None,
                notes=request.POST.get('notes', ''), cree_par=request.user,
            )
            idx = 1
            total = 0
            while request.POST.get(f'material_{idx}'):
                mat = Material.objects.filter(id=request.POST.get(f'material_{idx}')).first()
                if mat:
                    qte = float(request.POST.get(f'quantite_{idx}', 0))
                    prix = float(request.POST.get(f'prix_{idx}', 0))
                    LigneBonCommande.objects.create(bon_commande=bc, material=mat, quantite_commandee=qte, prix_unitaire=prix)
                    total += qte * prix
                idx += 1
            bc.montant_total = total
            bc.save()
            messages.success(request, f"Bon de commande {bc.reference} créé.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
        return redirect('stock_advanced')
    return redirect('stock_advanced')


@login_required
def bc_envoyer(request, id):
    bc = get_object_or_404(BonCommande, id=id)
    if request.method == 'POST':
        bc.statut = 'ENVOYE'
        bc.save()
        messages.success(request, f"BC {bc.reference} marqué comme envoyé.")
    return redirect('stock_advanced')


@login_required
def bc_reception(request, id):
    bc = get_object_or_404(BonCommande, id=id)
    if request.method == 'POST':
        bc.statut = 'RECU_TOTAL'
        bc.date_livraison_reelle = timezone.now().date()
        bc.save()
        for ligne in bc.lignes.all():
            import random, string
            num_lot = f"LOT-{bc.reference}-{''.join(random.choices(string.digits, k=4))}"
            StockLot.objects.create(
                material=ligne.material, numero_lot=num_lot,
                date_reception=timezone.now().date(), fournisseur=bc.fournisseur,
                quantite_initiale=ligne.quantite_commandee,
                quantite_restante=ligne.quantite_commandee,
                prix_unitaire=ligne.prix_unitaire, statut='EN_ATTENTE',
                created_by=request.user,
            )
            ligne.quantite_recue = ligne.quantite_commandee
            ligne.save()
        messages.success(request, f"BC {bc.reference} réceptionné.")
    return redirect('stock_advanced')


@login_required
def seuil_update(request, material_id):
    material = get_object_or_404(Material, id=material_id)
    if request.method == 'POST':
        seuil, _ = StockSeuil.objects.get_or_create(
            material=material,
            defaults={'consommation_journaliere_moy': 0, 'delai_fournisseur_jours': 7}
        )
        seuil.consommation_journaliere_moy = float(request.POST.get('conso_jour', 0))
        seuil.delai_fournisseur_jours = int(request.POST.get('delai_jours', 7))
        seuil.stock_securite_jours = int(request.POST.get('securite_jours', 3))
        seuil.save()
        messages.success(request, f"Seuil mis à jour pour {material.name}.")
    return redirect('stock_advanced')


@login_required
def stock_dashboard_data(request):
    from datetime import date
    date_30j = date.today() - timedelta(days=30)
    critiques = []
    for m in Material.objects.all():
        if m.is_low_stock():
            critiques.append({'name': m.name, 'stock': m.quantity, 'seuil': m.min_threshold})
    return JsonResponse({'critiques': critiques})


# ===========================================================================
# --- PARC MACHINE ---
# ===========================================================================

@login_required
def machine_view(request):
    machines = Machine.objects.all().order_by('-id')
    return render(request, 'machines.html', {'machines': machines})


@login_required
def add_machine(request):
    if request.method == 'POST':
        form = MachineForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('machine_view')
    else:
        form = MachineForm()
    return render(request, 'machines.html', {'form': form, 'titre': 'Nouvelle Machine'})


# ===========================================================================
# --- MODULE PRODUCTION SPÉCIALE — CORRIGÉ ---
# ===========================================================================

def _get_filtered_entries(request):
    """Fonction utilitaire : récupère les entrées avec filtres appliqués."""
    entries = ProductionEntry.objects.all().order_by('-date', '-heure_debut')

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    machine_id = request.GET.get('machine', '')
    support = request.GET.get('support', '')
    equipe = request.GET.get('equipe', '')

    if date_from:
        entries = entries.filter(date__gte=date_from)
    if date_to:
        entries = entries.filter(date__lte=date_to)
    if machine_id:
        entries = entries.filter(machine_id=machine_id)
    if support:
        entries = entries.filter(support=support)
    if equipe:
        entries = entries.filter(equipe=equipe)

    return entries


def _get_filter_context(request):
    """Contexte commun pour les filtres dans tous les templates production."""
    return {
        'all_machines': Machine.objects.all().order_by('name'),
        'all_supports': ProductionEntry.objects.values_list('support', flat=True).distinct().order_by('support'),
        'selected_date_from': request.GET.get('date_from', ''),
        'selected_date_to': request.GET.get('date_to', ''),
        'selected_machine': request.GET.get('machine', ''),
        'selected_support': request.GET.get('support', ''),
        'selected_equipe': request.GET.get('equipe', ''),
    }


@login_required
def prod_dashboard(request):
    """Dashboard avec KPIs et graphiques."""
    entries = _get_filtered_entries(request)

    # KPIs
    total_prod_ml = entries.aggregate(t=Sum('prod_ml'))['t'] or 0
    total_prod_kg = entries.aggregate(t=Sum('prod_kg'))['t'] or 0
    total_dechets_kg = round(sum(e.total_dechets_kg for e in entries), 2)
    taux_dechets = round((total_dechets_kg / float(total_prod_kg) * 100), 2) if total_prod_kg else 0

    # Données graphiques par date
    from collections import defaultdict
    data_par_date = defaultdict(lambda: {'ml': 0, 'kg': 0, 'dem': 0, 'lis': 0, 'jon': 0, 'tra': 0, 'taux': []})
    for e in entries:
        d = str(e.date)
        data_par_date[d]['ml'] += e.prod_ml
        data_par_date[d]['kg'] += e.prod_kg
        data_par_date[d]['dem'] += e.dechets_demarrage
        data_par_date[d]['lis'] += e.dechets_lisiere
        data_par_date[d]['jon'] += e.dechets_jonction
        data_par_date[d]['tra'] += e.dechets_transport
        if e.prod_kg > 0:
            data_par_date[d]['taux'].append(e.taux_dechets)

    dates_sorted = sorted(data_par_date.keys())

    # Graphique Prod KG par support (Pie)
    support_data = defaultdict(float)
    for e in entries:
        support_data[e.support] += e.prod_kg

    context = {
        'entries': entries[:20],
        'total_prod_ml': round(float(total_prod_ml), 2),
        'total_prod_kg': round(float(total_prod_kg), 2),
        'total_dechets_kg': total_dechets_kg,
        'taux_dechets': taux_dechets,
        'count': entries.count(),
        # Graphiques
        'prod_ml_dates': json.dumps(dates_sorted),
        'prod_ml_values': json.dumps([round(data_par_date[d]['ml'], 1) for d in dates_sorted]),
        'prod_kg_dates': json.dumps(dates_sorted),
        'prod_kg_values': json.dumps([round(data_par_date[d]['kg'], 2) for d in dates_sorted]),
        'prod_kg_support_labels': json.dumps(list(support_data.keys())),
        'prod_kg_support_values': json.dumps([round(v, 2) for v in support_data.values()]),
        'taux_dechets_dates': json.dumps(dates_sorted),
        'taux_dechets_values': json.dumps([
            round(sum(data_par_date[d]['taux']) / len(data_par_date[d]['taux']), 2) if data_par_date[d]['taux'] else 0
            for d in dates_sorted
        ]),
        'dechets_dates': json.dumps(dates_sorted),
        'dechets_dem_values': json.dumps([round(data_par_date[d]['dem'], 2) for d in dates_sorted]),
        'dechets_lis_values': json.dumps([round(data_par_date[d]['lis'], 2) for d in dates_sorted]),
        'dechets_jon_values': json.dumps([round(data_par_date[d]['jon'], 2) for d in dates_sorted]),
        'dechets_tra_values': json.dumps([round(data_par_date[d]['tra'], 2) for d in dates_sorted]),
    }
    context.update(_get_filter_context(request))
    return render(request, 'production_special/dashboard.html', context)


@login_required
def prod_saisie(request):
    """Formulaire de saisie — avec les machines bien chargées."""
    if request.method == 'POST':
        form = ProductionEntryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Saisie enregistrée avec succès.")
            return redirect('prod_dashboard')
        else:
            messages.error(request, "Erreur dans le formulaire. Vérifiez les champs.")
    else:
        form = ProductionEntryForm()

    # Les 10 dernières saisies pour l'aperçu à droite
    recent = ProductionEntry.objects.all().order_by('-date', '-heure_debut')[:10]

    context = {
        'form': form,
        'titre': 'Nouvelle Saisie Production',
        'recent': recent,
        'edit_mode': False,
    }
    return render(request, 'production_special/saisie.html', context)


@login_required
def prod_edit_entry(request, id):
    """Modifier une saisie existante."""
    entry = get_object_or_404(ProductionEntry, id=id)
    if request.method == 'POST':
        form = ProductionEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, "Saisie mise à jour.")
            return redirect('prod_base')
        else:
            messages.error(request, "Erreur dans le formulaire.")
    else:
        form = ProductionEntryForm(instance=entry)

    recent = ProductionEntry.objects.all().order_by('-date', '-heure_debut')[:10]
    context = {
        'form': form,
        'titre': f'Modifier — {entry.produit} ({entry.date})',
        'recent': recent,
        'edit_mode': True,
        'entry': entry,
    }
    return render(request, 'production_special/saisie.html', context)


@login_required
def prod_delete_entry(request, id):
    entry = get_object_or_404(ProductionEntry, id=id)
    if request.method == 'POST':
        entry.delete()
        messages.success(request, "Saisie supprimée.")
        return redirect('prod_base')
    return render(request, 'production_special/confirm_delete.html', {'entry': entry})


@login_required
def prod_base(request):
    """Vue base de données complète avec filtres."""
    entries = _get_filtered_entries(request)
    context = {'entries': entries}
    context.update(_get_filter_context(request))
    return render(request, 'production_special/base.html', context)


@login_required
def prod_detail_qualite(request):
    """Analyse détaillée qualité et déchets."""
    entries = _get_filtered_entries(request)

    total_dechets_kg = round(sum(e.total_dechets_kg for e in entries), 2)
    total_dechets_demarrage = round(sum(e.dechets_demarrage for e in entries), 2)
    total_dechets_lisiere = round(sum(e.dechets_lisiere for e in entries), 2)
    total_dechets_jonction = round(sum(e.dechets_jonction for e in entries), 2)
    total_dechets_transport = round(sum(e.dechets_transport for e in entries), 2)

    from collections import defaultdict
    data_dates = defaultdict(lambda: {'dem_a': 0, 'dem_b': 0, 'lis_a': 0, 'lis_b': 0,
                                       'jon_a': 0, 'jon_b': 0, 'tra_a': 0, 'tra_b': 0,
                                       'total': 0})
    for e in entries:
        d = str(e.date)
        eq = e.equipe
        data_dates[d]['dem_' + eq.lower()] += e.dechets_demarrage
        data_dates[d]['lis_' + eq.lower()] += e.dechets_lisiere
        data_dates[d]['jon_' + eq.lower()] += e.dechets_jonction
        data_dates[d]['tra_' + eq.lower()] += e.dechets_transport
        data_dates[d]['total'] += e.total_dechets_kg

    dates_sorted = sorted(data_dates.keys())

    context = {
        'entries': entries,
        'total_dechets_kg': total_dechets_kg,
        'total_dechets_demarrage': total_dechets_demarrage,
        'total_dechets_lisiere': total_dechets_lisiere,
        'total_dechets_jonction': total_dechets_jonction,
        'total_dechets_transport': total_dechets_transport,
        'dates_labels': json.dumps(dates_sorted),
        'dem_a': json.dumps([round(data_dates[d]['dem_a'], 2) for d in dates_sorted]),
        'dem_b': json.dumps([round(data_dates[d]['dem_b'], 2) for d in dates_sorted]),
        'lis_a': json.dumps([round(data_dates[d]['lis_a'], 2) for d in dates_sorted]),
        'lis_b': json.dumps([round(data_dates[d]['lis_b'], 2) for d in dates_sorted]),
        'jon_a': json.dumps([round(data_dates[d]['jon_a'], 2) for d in dates_sorted]),
        'jon_b': json.dumps([round(data_dates[d]['jon_b'], 2) for d in dates_sorted]),
        'tra_a': json.dumps([round(data_dates[d]['tra_a'], 2) for d in dates_sorted]),
        'tra_b': json.dumps([round(data_dates[d]['tra_b'], 2) for d in dates_sorted]),
        'h_dates': json.dumps(dates_sorted),
        'h_dem': json.dumps([round(data_dates[d]['dem_a'] + data_dates[d]['dem_b'], 2) for d in dates_sorted]),
        'h_lis': json.dumps([round(data_dates[d]['lis_a'] + data_dates[d]['lis_b'], 2) for d in dates_sorted]),
        'h_jon': json.dumps([round(data_dates[d]['jon_a'] + data_dates[d]['jon_b'], 2) for d in dates_sorted]),
        'h_tra': json.dumps([round(data_dates[d]['tra_a'] + data_dates[d]['tra_b'], 2) for d in dates_sorted]),
    }
    context.update(_get_filter_context(request))
    return render(request, 'production_special/detail_qualite.html', context)


@login_required
def prod_synthese_temps(request):
    """Synthèse des temps, décalage et rebobinage."""
    entries = _get_filtered_entries(request)

    decalage_total = round(sum(e.decalage for e in entries), 2)
    temps_ouverture_total_min = sum(e.temps_ouverture_minutes for e in entries)
    heures = int(temps_ouverture_total_min // 60)
    minutes = int(temps_ouverture_total_min % 60)
    temps_ouverture_total = f"{heures}:{minutes:02d}"
    total_rebobinage = round(sum(e.rebobinage_kg for e in entries), 2)

    from collections import defaultdict
    data_dec = defaultdict(float)
    data_temps_a = defaultdict(float)
    data_temps_b = defaultdict(float)
    produits_set = set()

    for e in entries:
        d = str(e.date)
        data_dec[d] += e.decalage
        produits_set.add(e.produit[:20])
        if e.equipe == 'A':
            data_temps_a[e.produit[:20]] += e.temps_ouverture_minutes / 60
        elif e.equipe == 'B':
            data_temps_b[e.produit[:20]] += e.temps_ouverture_minutes / 60

    dates_sorted = sorted(data_dec.keys())
    produits_sorted = sorted(produits_set)

    context = {
        'entries': entries,
        'decalage_total': decalage_total,
        'temps_ouverture_total': temps_ouverture_total,
        'total_rebobinage': total_rebobinage,
        'decalage_dates': json.dumps(dates_sorted),
        'decalage_values': json.dumps([round(data_dec[d], 2) for d in dates_sorted]),
        'temps_produit_labels': json.dumps(produits_sorted),
        'temps_produit_a': json.dumps([round(data_temps_a.get(p, 0), 2) for p in produits_sorted]),
        'temps_produit_b': json.dumps([round(data_temps_b.get(p, 0), 2) for p in produits_sorted]),
    }
    context.update(_get_filter_context(request))
    return render(request, 'production_special/synthese_temps.html', context)


# ===========================================================================
# --- IMPORT EXCEL ---
# ===========================================================================

def parse_time_safe(val):
    if val is None or val == 0 or val == '' or str(val).strip() == '':
        return None
    try:
        if hasattr(val, 'hour'): return val
        if hasattr(val, 'time'): return val.time()
        if isinstance(val, float):
            total_seconds = int(val * 24 * 3600)
            return datetime.time(total_seconds // 3600, (total_seconds % 3600) // 60)
        s = str(val).strip()
        parts = s.replace('h', ':').replace('H', ':').split(':')
        if len(parts) >= 2:
            return datetime.time(int(parts[0]), int(parts[1]))
        return None
    except:
        return None


@login_required
def import_stock_view(request):
    context = {}
    if request.method == 'POST' and request.FILES.get('excel_file'):
        try:
            import_type = request.POST.get('import_type')
            excel_file = request.FILES['excel_file']
            fs = FileSystemStorage()
            filename = fs.save(excel_file.name, excel_file)
            file_path = fs.path(filename)
            df = pd.read_excel(file_path).fillna(0)
            count = 0
            errors = 0
            details = []

            if import_type == 'STOCK':
                for idx, row in df.iterrows():
                    try:
                        cat_map = {'Film': 'FILM', 'Encre': 'INK', 'Colle': 'GLUE', 'Solvant': 'SOLV'}
                        cat_val = row.get('Categorie', 'FILM')
                        if cat_val == 0: cat_val = 'FILM'
                        Material.objects.update_or_create(
                            name=row.get('Designation', 'Inconnu'),
                            defaults={
                                'category': cat_map.get(cat_val, 'FILM'),
                                'quantity': row.get('Quantite', 0),
                                'unit': row.get('Unite', 'kg'),
                                'min_threshold': row.get('Seuil_Min', 0),
                                'price_per_unit': row.get('Prix', 0)
                            }
                        )
                        count += 1
                        details.append(f"Ligne {idx+2}: ✅ {row.get('Designation')} importé")
                    except Exception as e:
                        errors += 1
                        details.append(f"Ligne {idx+2}: ❌ {str(e)}")

            elif import_type == 'CRM':
                for idx, row in df.iterrows():
                    try:
                        nom = row.get('Nom')
                        if nom and nom != 0:
                            status_map = {'Active': 'ACTIVE', 'Prospect': 'PROSPECT', 'VIP': 'VIP'}
                            Client.objects.update_or_create(
                                name=nom,
                                defaults={'city': row.get('Ville', ''), 'phone': row.get('Telephone', ''),
                                          'email': row.get('Email', ''), 'sector': row.get('Secteur', ''),
                                          'status': status_map.get(row.get('Statut'), 'PROSPECT')}
                            )
                            count += 1
                            details.append(f"Ligne {idx+2}: ✅ Client {nom} importé")
                        else:
                            details.append(f"Ligne {idx+2}: ⚠️ Nom vide — ignorée")
                    except Exception as e:
                        errors += 1
                        details.append(f"Ligne {idx+2}: ❌ {str(e)}")

            elif import_type == 'SPECIAL_PROD':
                for idx, row in df.iterrows():
                    try:
                        try:
                            d_val = pd.to_datetime(row.get('Date')).date()
                        except:
                            d_val = datetime.date.today()

                        produit_val = str(row.get('Produit', '')).strip()
                        if not produit_val or produit_val == '0':
                            details.append(f"Ligne {idx+2}: ⚠️ Produit vide — ignorée")
                            continue

                        client_obj = None
                        cli_name = str(row.get('Client', '')).strip()
                        if cli_name and cli_name not in ('0', ''):
                            client_obj, _ = Client.objects.get_or_create(
                                name=cli_name,
                                defaults={'city': 'Non renseigné', 'phone': '000'}
                            )

                        machine_obj = None
                        mac_name = str(row.get('Machine', '')).strip()
                        if mac_name and mac_name not in ('0', ''):
                            machine_obj = Machine.objects.filter(name__icontains=mac_name).first()
                            if not machine_obj:
                                machine_obj = Machine.objects.create(name=mac_name, type='IMP', status='STOP')
                                details.append(f"  → Machine '{mac_name}' créée automatiquement")

                        equipe_val = str(row.get('Equipe', 'A')).strip().upper()
                        if equipe_val not in ['A', 'B', 'C']:
                            equipe_val = 'A'

                        h_debut = parse_time_safe(row.get('H_Debut'))
                        h_fin = parse_time_safe(row.get('H_Fin'))

                        def safe_float(v, d=0):
                            try:
                                x = float(v)
                                return x if x == x else d
                            except:
                                return d

                        # CRÉATION DE L'ENTRÉE
                        entry = ProductionEntry.objects.create(
                            date=d_val,
                            produit=produit_val,
                            support=str(row.get('Support', '')),
                            quantite_lancee=safe_float(row.get('Qte_Lancee')),
                            lot=str(row.get('Lot', '')),
                            laize=safe_float(row.get('Laize')),
                            client=client_obj,
                            equipe=equipe_val,
                            machine=machine_obj,
                            heure_debut=h_debut,
                            heure_fin=h_fin,
                            prod_ml=safe_float(row.get('Prod_ML')),
                            dechets_demarrage=safe_float(row.get('Dec_Demarrage')),
                            dechets_lisiere=safe_float(row.get('Dec_Lisiere')),
                            dechets_jonction=safe_float(row.get('Dec_Jonction')),
                            dechets_transport=safe_float(row.get('Dec_Transport')),
                            prod_kg=safe_float(row.get('Prod_KG')),
                            rebobinage_kg=safe_float(row.get('Rebobinage_KG'))
                        )
                        count += 1
                        details.append(f"Ligne {idx+2}: ✅ {produit_val} du {d_val} importé (ID={entry.id})")

                    except Exception as e:
                        errors += 1
                        details.append(f"Ligne {idx+2}: ❌ ERREUR — {str(e)}")

            elif import_type == 'CONSO':
                for idx, row in df.iterrows():
                    try:
                        try:
                            d_prod = pd.to_datetime(row.get('Date')).date()
                        except:
                            d_prod = datetime.date.today()
                        raw_type = str(row.get('Type', 'FLEXO')).upper()
                        final_type = 'HELIO' if 'HELIO' in raw_type else 'FLEXO'
                        ConsommationEncre.objects.create(
                            date=d_prod, process_type=final_type,
                            support=row.get('Support', 'Inconnu'),
                            laize=float(row.get('Laize', 0)),
                            bobine_in=float(row.get('Bobine_In', 0)),
                            bobine_out=float(row.get('Bobine_Out', 0)),
                            metrage=float(row.get('Metrage', 0)),
                            encre_noir=float(row.get('Noir', 0)),
                            encre_magenta=float(row.get('Magenta', 0)),
                            encre_jaune=float(row.get('Jaune', 0)),
                            encre_cyan=float(row.get('Cyan', 0)),
                            encre_dore=float(row.get('Dore', 0)),
                            encre_silver=float(row.get('Silver', 0)),
                            encre_orange=float(row.get('Orange', 0)),
                            encre_blanc=float(row.get('Blanc', 0)),
                            encre_vernis=float(row.get('Vernis', 0)),
                            solvant_metoxyn=float(row.get('Metoxyn', 0)),
                            solvant_2080=float(row.get('2080', 0))
                        )
                        count += 1
                        details.append(f"Ligne {idx+2}: ✅ Conso {d_prod} importée")
                    except Exception as e:
                        errors += 1
                        details.append(f"Ligne {idx+2}: ❌ {str(e)}")

            elif import_type == 'TOOLS':
                for idx, row in df.iterrows():
                    try:
                        prod_ref = row.get('Ref_Produit')
                        if prod_ref and prod_ref != 0:
                            cli, _ = Client.objects.get_or_create(name="Client Divers", defaults={'city': 'Interne', 'phone': '000'})
                            product, _ = TechnicalProduct.objects.get_or_create(
                                ref_internal=prod_ref,
                                defaults={'name': f"Produit {prod_ref}", 'client': cli, 'structure_type': 'MONO', 'width_mm': 100}
                            )
                            type_map = {'Cylindre': 'CYL', 'Cliche': 'CLICHE'}
                            type_val = row.get('Type', 'CYL')
                            if type_val == 0: type_val = 'CYL'
                            Tooling.objects.update_or_create(
                                serial_number=row.get('Serial'),
                                defaults={
                                    'product': product,
                                    'tool_type': type_map.get(type_val, 'CYL'),
                                    'max_impressions': row.get('Tours_Max', 1000000),
                                    'current_impressions': row.get('Tours_Actuels', 0)
                                }
                            )
                            count += 1
                            details.append(f"Ligne {idx+2}: ✅ Outil {row.get('Serial')} importé")
                    except Exception as e:
                        errors += 1
                        details.append(f"Ligne {idx+2}: ❌ {str(e)}")

            elif import_type == 'PLANNING':
                for idx, row in df.iterrows():
                    try:
                        cli_name = row.get('Client')
                        if cli_name and cli_name != 0:
                            client, _ = Client.objects.get_or_create(name=cli_name, defaults={'city': '?', 'phone': '?'})
                            prod_name = row.get('Produit')
                            product, _ = TechnicalProduct.objects.get_or_create(
                                ref_internal=f"REF-{str(prod_name)[:5]}",
                                defaults={'name': prod_name, 'client': client, 'structure_type': 'MONO', 'width_mm': 500}
                            )
                            mac_name = row.get('Machine')
                            machine = Machine.objects.filter(name__icontains=str(mac_name)).first()
                            try:
                                start_d = pd.to_datetime(row.get('Date_Debut'))
                            except:
                                start_d = datetime.datetime.now()
                            end_d = start_d + timedelta(hours=4)
                            ProductionOrder.objects.update_or_create(
                                of_number=str(row.get('OF_Numero')),
                                defaults={
                                    'client': client, 'product': product, 'machine': machine,
                                    'start_time': start_d, 'end_time': end_d,
                                    'quantity_planned': row.get('Qte_Prevue', 0), 'status': 'PLANNED'
                                }
                            )
                            count += 1
                            details.append(f"Ligne {idx+2}: ✅ OF {row.get('OF_Numero')} importé")
                    except Exception as e:
                        errors += 1
                        details.append(f"Ligne {idx+2}: ❌ {str(e)}")

            context = {
                'message': f'⚠️ {count} OK, {errors} erreurs.' if errors else f'✅ {count} lignes importées avec succès !',
                'success': count > 0,
                'details': details
            }
            try:
                os.remove(file_path)
            except:
                pass

        except Exception as e:
            context = {'message': f'❌ Erreur critique : {str(e)}', 'success': False}

    return render(request, 'stock/import_stock.html', context)


def download_template_special_prod(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Production Speciale"
    headers = [
        'Date', 'Produit', 'Support', 'Qte_Lancee', 'Lot', 'Laize',
        'Client', 'Equipe', 'Machine', 'H_Debut', 'H_Fin', 'Prod_ML',
        'Dec_Demarrage', 'Dec_Lisiere', 'Dec_Jonction', 'Dec_Transport',
        'Prod_KG', 'Rebobinage_KG'
    ]
    hf = Font(name='Arial', bold=True, color='FFFFFF', size=11)
    hfill = PatternFill(start_color='0D47A1', end_color='0D47A1', fill_type='solid')
    tb = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = hf
        cell.fill = hfill
        cell.alignment = Alignment(horizontal='center')
        cell.border = tb
    # Ligne exemple
    example = ['15/01/2025', 'Sac Lait 1L', 'PEBD 50μ', 500, 'LOT-001', 320,
               'Laiterie Atlas', 'A', 'IMP-01', '08:00', '16:30', 12000, 5.2, 3.1, 1.5, 2.0, 485, 10]
    ef = PatternFill(start_color='E8F5E9', end_color='E8F5E9', fill_type='solid')
    for col, val in enumerate(example, 1):
        cell = ws.cell(row=2, column=col, value=val)
        cell.fill = ef
        cell.border = tb
        cell.alignment = Alignment(horizontal='center')
    for col in ws.columns:
        ml = max((len(str(c.value)) for c in col if c.value), default=0)
        ws.column_dimensions[col[0].column_letter].width = ml + 4
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Template_Production_Speciale.xlsx"'
    wb.save(response)
    return response
