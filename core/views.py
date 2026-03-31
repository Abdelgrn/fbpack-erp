import os
import datetime
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Count, Q, Avg
from django.core.files.storage import FileSystemStorage
from django.utils.dateparse import parse_datetime
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib import messages

from .models import (
    Client, ClientContact, InteractionLog, Opportunite,
    TechnicalProduct, Tooling, Quote,
    ProductionOrder, Machine, ConsumptionLog,
    Material, Supplier, ConsommationEncre, ProductionEntry,
    PurchaseOrder
)
from .forms import (
    ClientForm, ClientContactForm, InteractionLogForm, OpportuniteForm,
    ProductForm, ToolForm, QuoteForm,
    ProductionOrderForm, SupplierForm, MaterialForm, ConsommationEncreForm,
    MachineForm, ProductionEntryForm
)


# ===========================================================================
# --- DASHBOARD & REPORTING ---
# ===========================================================================

@login_required
def dashboard(request):
    context = {
        'count_clients': Client.objects.count(),
        'count_of_running': ProductionOrder.objects.filter(status='IN_PROGRESS').count(),
        'low_stock_count': len([m for m in Material.objects.all() if m.is_low_stock()]),
        'machines': Machine.objects.all(),
        'orders_per_machine': ProductionOrder.objects.values('machine__name').annotate(count=Count('id')),
        # CRM KPIs
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

    # Taux de conversion devis
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
# --- MODULE CRM — LISTE PRINCIPALE ---
# ===========================================================================

@login_required
def crm_view(request):
    # Filtres
    status_filter = request.GET.get('status', '')
    segment_filter = request.GET.get('segment', '')
    region_filter = request.GET.get('region', '')
    search = request.GET.get('q', '')

    clients = Client.objects.all().order_by('name')

    if status_filter:
        clients = clients.filter(status=status_filter)
    if segment_filter:
        clients = clients.filter(segment=segment_filter)
    if region_filter:
        clients = clients.filter(region=region_filter)
    if search:
        clients = clients.filter(
            Q(name__icontains=search) |
            Q(city__icontains=search) |
            Q(code_client__icontains=search)
        )

    quotes = Quote.objects.all().order_by('-date')
    opportunites = Opportunite.objects.all().order_by('-date_ouverture')

    # Stats pipeline
    pipeline_stages = []
    for stage_code, stage_label in Opportunite.STAGE_CHOICES:
        count = Opportunite.objects.filter(status=stage_code).count()
        montant = Opportunite.objects.filter(status=stage_code).aggregate(t=Sum('valeur_estimee'))['t'] or 0
        pipeline_stages.append({
            'code': stage_code,
            'label': stage_label,
            'count': count,
            'montant': montant,
        })

    context = {
        'clients': clients,
        'quotes': quotes,
        'opportunites': opportunites,
        'pipeline_stages': pipeline_stages,
        # Filtres actifs
        'status_filter': status_filter,
        'segment_filter': segment_filter,
        'region_filter': region_filter,
        'search': search,
        # Choix pour les filtres
        'status_choices': Client.STATUS_CHOICES,
        'segment_choices': Client.SEGMENT_CHOICES,
        'region_choices': Client.REGION_CHOICES,
    }
    return render(request, 'crm.html', context)


# ===========================================================================
# --- FICHE CLIENT DÉTAILLÉE ---
# ===========================================================================

@login_required
def client_detail(request, id):
    client = get_object_or_404(Client, id=id)
    contacts = ClientContact.objects.filter(client=client)
    interactions = InteractionLog.objects.filter(client=client).order_by('-date')[:20]
    opportunites = Opportunite.objects.filter(client=client).order_by('-date_ouverture')
    quotes = Quote.objects.filter(client=client).order_by('-date')
    orders = ProductionOrder.objects.filter(client=client).order_by('-start_time')[:5]

    context = {
        'client': client,
        'contacts': contacts,
        'interactions': interactions,
        'opportunites': opportunites,
        'quotes': quotes,
        'orders': orders,
    }
    return render(request, 'crm/client_detail.html', context)


# ===========================================================================
# --- CLIENTS : AJOUTER / MODIFIER ---
# ===========================================================================

@login_required
def add_client(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f"Client « {client.name} » créé avec succès.")
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


# ===========================================================================
# --- CONTACTS ---
# ===========================================================================

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
    return render(request, 'crm/contact_form.html', {
        'form': form, 'client': contact.client, 'titre': f'Modifier {contact.name}'
    })


@login_required
def delete_contact(request, id):
    contact = get_object_or_404(ClientContact, id=id)
    client_id = contact.client.id
    if request.method == 'POST':
        contact.delete()
        messages.success(request, "Contact supprimé.")
    return redirect('client_detail', id=client_id)


# ===========================================================================
# --- INTERACTIONS / JOURNAL ---
# ===========================================================================

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


# ===========================================================================
# --- OPPORTUNITÉS & PIPELINE ---
# ===========================================================================

@login_required
def opportunites_view(request):
    opportunites = Opportunite.objects.all().order_by('-date_ouverture')
    # Grouper par étape pour le kanban
    pipeline = {}
    for stage_code, stage_label in Opportunite.STAGE_CHOICES:
        pipeline[stage_code] = {
            'label': stage_label,
            'items': Opportunite.objects.filter(status=stage_code),
            'total': Opportunite.objects.filter(status=stage_code).aggregate(t=Sum('valeur_estimee'))['t'] or 0,
        }
    return render(request, 'crm/opportunites.html', {
        'opportunites': opportunites,
        'pipeline': pipeline,
    })


@login_required
def add_opportunite(request):
    if request.method == 'POST':
        form = OpportuniteForm(request.POST)
        if form.is_valid():
            opp = form.save()
            messages.success(request, f"Opportunité « {opp.titre} » créée.")
            return redirect('crm_view')
    else:
        # Pré-remplir le client si passé en GET
        initial = {}
        client_id = request.GET.get('client_id')
        if client_id:
            initial['client'] = client_id
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


# ===========================================================================
# --- DEVIS ---
# ===========================================================================

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
        if client_id:
            initial['client'] = client_id
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
    """Convertit un devis accepté en commande de production."""
    quote = get_object_or_404(Quote, id=id)
    if quote.status in ['ACCEPTED', 'SIGNED'] and not quote.commande_creee:
        quote.commande_creee = True
        quote.save()
        messages.success(request, f"Devis {quote.reference} marqué comme converti en commande.")
    return redirect('crm_view')


# ===========================================================================
# --- MODULE PRÉPRESSE ---
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
# --- MODULE PRODUCTION (OF) ---
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
# --- MODULE STOCKS, FOURNISSEURS & CONSO ---
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
# --- MODULE PARC MACHINE ---
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
# --- MODULE PRODUCTION SPÉCIALE ---
# ===========================================================================

@login_required
def prod_dashboard(request):
    entries = ProductionEntry.objects.all().order_by('-date')[:20]
    total_kg = ProductionEntry.objects.aggregate(total=Sum('prod_kg'))['total'] or 0
    total_ml = ProductionEntry.objects.aggregate(total=Sum('prod_ml'))['total'] or 0
    context = {
        'entries': entries,
        'total_kg': total_kg,
        'total_ml': total_ml,
        'count': ProductionEntry.objects.count(),
    }
    return render(request, 'production_special/dashboard.html', context)


@login_required
def prod_saisie(request):
    if request.method == 'POST':
        form = ProductionEntryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('prod_dashboard')
    else:
        form = ProductionEntryForm()
    return render(request, 'production_special/saisie.html', {'form': form, 'titre': 'Nouvelle Saisie Production'})


@login_required
def prod_edit_entry(request, id):
    entry = get_object_or_404(ProductionEntry, id=id)
    if request.method == 'POST':
        form = ProductionEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            return redirect('prod_dashboard')
    else:
        form = ProductionEntryForm(instance=entry)
    return render(request, 'production_special/saisie.html', {'form': form, 'titre': 'Modifier Saisie'})


@login_required
def prod_delete_entry(request, id):
    entry = get_object_or_404(ProductionEntry, id=id)
    if request.method == 'POST':
        entry.delete()
        return redirect('prod_dashboard')
    return render(request, 'production_special/confirm_delete.html', {'entry': entry})


@login_required
def prod_base(request):
    entries = ProductionEntry.objects.all().order_by('-date')
    return render(request, 'production_special/dashboard.html', {'entries': entries})


@login_required
def prod_detail_qualite(request):
    entries = ProductionEntry.objects.all().order_by('-date')
    return render(request, 'production_special/detail_qualite.html', {'entries': entries})


@login_required
def prod_synthese_temps(request):
    entries = ProductionEntry.objects.all().order_by('-date')
    return render(request, 'production_special/synthese_temps.html', {'entries': entries})


# ===========================================================================
# --- IMPORT EXCEL ---
# ===========================================================================

def parse_time_safe(val):
    if val is None or val == 0 or val == '' or str(val).strip() == '':
        return None
    try:
        if hasattr(val, 'hour'):
            return val
        if hasattr(val, 'time'):
            return val.time()
        if isinstance(val, float):
            total_seconds = int(val * 24 * 3600)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return datetime.time(hours, minutes)
        s = str(val).strip()
        parts = s.replace('h', ':').replace('H', ':').split(':')
        if len(parts) >= 2:
            h = int(parts[0])
            m = int(parts[1])
            return datetime.time(h, m)
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
                        details.append(f"Ligne {idx+2}: ❌ ERREUR - {str(e)}")

            elif import_type == 'CRM':
                for idx, row in df.iterrows():
                    try:
                        status_map = {'Active': 'ACTIVE', 'Prospect': 'PROSPECT', 'VIP': 'VIP'}
                        nom = row.get('Nom')
                        if nom and nom != 0:
                            Client.objects.update_or_create(
                                name=nom,
                                defaults={
                                    'city': row.get('Ville', ''),
                                    'phone': row.get('Telephone', ''),
                                    'email': row.get('Email', ''),
                                    'sector': row.get('Secteur', ''),
                                    'status': status_map.get(row.get('Statut'), 'PROSPECT')
                                }
                            )
                            count += 1
                            details.append(f"Ligne {idx+2}: ✅ Client {nom} importé")
                        else:
                            details.append(f"Ligne {idx+2}: ⚠️ IGNORÉE - Nom vide")
                    except Exception as e:
                        errors += 1
                        details.append(f"Ligne {idx+2}: ❌ ERREUR - {str(e)}")

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
                        details.append(f"Ligne {idx+2}: ❌ ERREUR - {str(e)}")

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
                            end_d = start_d + datetime.timedelta(hours=4)
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
                        details.append(f"Ligne {idx+2}: ❌ ERREUR - {str(e)}")

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
                        details.append(f"Ligne {idx+2}: ❌ ERREUR - {str(e)}")

            elif import_type == 'SPECIAL_PROD':
                for idx, row in df.iterrows():
                    try:
                        try:
                            d_val = pd.to_datetime(row.get('Date')).date()
                        except:
                            d_val = datetime.date.today()
                        produit_val = str(row.get('Produit', '')).strip()
                        if not produit_val or produit_val == '0':
                            details.append(f"Ligne {idx+2}: ⚠️ IGNORÉE - Produit vide")
                            continue
                        client_obj = None
                        cli_name = str(row.get('Client', '')).strip()
                        if cli_name and cli_name != '0' and cli_name != '':
                            client_obj, _ = Client.objects.get_or_create(
                                name=cli_name,
                                defaults={'city': 'Non renseigné', 'phone': '000'}
                            )
                        machine_obj = None
                        mac_name = str(row.get('Machine', '')).strip()
                        if mac_name and mac_name != '0' and mac_name != '':
                            machine_obj = Machine.objects.filter(name__icontains=mac_name).first()
                            if not machine_obj:
                                machine_obj = Machine.objects.create(name=mac_name, type='IMP', status='STOP')
                        equipe_val = str(row.get('Equipe', 'A')).strip().upper()
                        if equipe_val not in ['A', 'B', 'C']:
                            equipe_val = 'A'
                        h_debut = parse_time_safe(row.get('H_Debut'))
                        h_fin = parse_time_safe(row.get('H_Fin'))

                        def safe_float(val, default=0):
                            try:
                                v = float(val)
                                return v if v == v else default
                            except:
                                return default

                        ProductionEntry.objects.create(
                            date=d_val, produit=produit_val,
                            support=str(row.get('Support', '')),
                            quantite_lancee=safe_float(row.get('Qte_Lancee')),
                            lot=str(row.get('Lot', '')),
                            laize=safe_float(row.get('Laize')),
                            client=client_obj, equipe=equipe_val, machine=machine_obj,
                            heure_debut=h_debut, heure_fin=h_fin,
                            prod_ml=safe_float(row.get('Prod_ML')),
                            dechets_demarrage=safe_float(row.get('Dec_Demarrage')),
                            dechets_lisiere=safe_float(row.get('Dec_Lisiere')),
                            dechets_jonction=safe_float(row.get('Dec_Jonction')),
                            dechets_transport=safe_float(row.get('Dec_Transport')),
                            prod_kg=safe_float(row.get('Prod_KG')),
                            rebobinage_kg=safe_float(row.get('Rebobinage_KG'))
                        )
                        count += 1
                        details.append(f"Ligne {idx+2}: ✅ {produit_val} ({d_val}) importé")
                    except Exception as e:
                        errors += 1
                        details.append(f"Ligne {idx+2}: ❌ ERREUR - {str(e)}")

            if errors > 0:
                context = {
                    'message': f'⚠️ Import terminé : {count} lignes OK, {errors} erreurs.',
                    'success': count > 0,
                    'details': details
                }
            else:
                context = {
                    'message': f'✅ Succès ! {count} lignes importées.',
                    'success': True,
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
    header_font = Font(name='Arial', bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='0D47A1', end_color='0D47A1', fill_type='solid')
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = thin_border

    for col in ws.columns:
        max_len = max((len(str(c.value)) for c in col if c.value), default=0)
        ws.column_dimensions[col[0].column_letter].width = max_len + 4

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="Template_Production_Speciale.xlsx"'
    wb.save(response)
    return response
