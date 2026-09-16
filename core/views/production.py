import json
from collections import defaultdict
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q, Avg, F
from django.utils import timezone
from django.http import JsonResponse
from django.contrib import messages

from ..models import (
    Client, TechnicalProduct, Tooling, Quote, Opportunite,
    ProductionOrder, Machine, ConsumptionLog, Material,
    OrdreFabrication, EtapeProduction, SemiProduit, SuiviProduction, ProcessType,
    ProductionEntry, CalculTempsProduction, OrdreMaintenance, AlerteMaintenance
)
from ..forms import (
    ProductForm, ToolForm, ProductionOrderForm, OrdreFabricationForm, EtapeProductionFormSet,
    SuiviProductionForm, ProcessTypeForm, OFLancementRapideForm, ProductionEntryForm, CalculTempsProductionForm
)


# ===========================================================================
# --- DASHBOARD & GENERAL REPORTING ---
# ===========================================================================

@login_required
def dashboard(request):
    machines_en_panne = Machine.objects.filter(status='PANNE', est_active=True)
    machines_en_maintenance = Machine.objects.filter(status='MAINT', est_active=True)

    om_urgents = OrdreMaintenance.objects.filter(
        statut__in=['OUVERT', 'EN_COURS'],
        priorite__in=['URGENTE', 'HAUTE']
    ).select_related('machine').order_by('-date_creation')[:5]

    alertes_critiques_maint = AlerteMaintenance.objects.filter(
        est_traitee=False,
        niveau='CRITICAL'
    ).count()

    context = {
        'count_clients': Client.objects.count(),
        'count_of_running': ProductionOrder.objects.filter(status='IN_PROGRESS').count(),
        'low_stock_count': sum(1 for m in Material.objects.all() if m.is_low_stock()),
        'machines': Machine.objects.all(),
        'orders_per_machine': ProductionOrder.objects.values('machine__name').annotate(count=Count('id')),
        'count_opportunites': Opportunite.objects.filter(status__in=['PROSPECT', 'QUALIFICATION', 'PROPOSITION', 'NEGOCIATION']).count(),
        'count_devis_envoyes': Quote.objects.filter(status='SENT').count(),
        'pipeline_total': Opportunite.objects.exclude(status__in=['GAGNE', 'PERDU']).aggregate(total=Sum('valeur_estimee'))['total'] or 0,
        'of_total': OrdreFabrication.objects.count(),
        'of_en_cours': OrdreFabrication.objects.filter(statut='EN_COURS').count(),
        'of_en_retard': sum(1 for of in OrdreFabrication.objects.filter(statut__in=['LANCE', 'EN_COURS']) if of.est_en_retard),
        'of_termine_mois': OrdreFabrication.objects.filter(statut='TERMINE', date_fin_reelle__month=timezone.now().month).count(),
        'semi_produits_dispo': SemiProduit.objects.filter(statut='DISPONIBLE').count(),
        'of_recents': OrdreFabrication.objects.select_related('client', 'produit').order_by('-date_creation')[:5],
        'machines_en_panne': machines_en_panne,
        'machines_en_maintenance': machines_en_maintenance,
        'om_urgents': om_urgents,
        'alertes_critiques_maint': alertes_critiques_maint,
        'nb_pannes_actives': machines_en_panne.count(),
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


# ===========================================================================
# --- PRODUCTION SIMPLE ---
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
    return render(request, 'production_form.html', {
        'form': form,
        'titre': 'Créer un Ordre de Fabrication'
    })


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
    return render(request, 'production_form.html', {
        'form': form,
        'titre': f'Modifier OF {of.of_number}'
    })


# ===========================================================================
# --- OF MULTI-PROCESSUS ---
# ===========================================================================

@login_required
def of_list_view(request):
    statut = request.GET.get('statut', '')
    priorite = request.GET.get('priorite', '')
    client_id = request.GET.get('client', '')
    search = request.GET.get('q', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    ofs = OrdreFabrication.objects.select_related(
        'client', 'produit', 'cree_par'
    ).prefetch_related('etapes').order_by('-date_creation')

    if statut:
        ofs = ofs.filter(statut=statut)
    if priorite:
        ofs = ofs.filter(priorite=priorite)
    if client_id:
        ofs = ofs.filter(client_id=client_id)
    if search:
        ofs = ofs.filter(
            Q(numero_of__icontains=search) |
            Q(numero_lot__icontains=search) |
            Q(produit__name__icontains=search) |
            Q(client__name__icontains=search)
        )
    if date_from:
        ofs = ofs.filter(date_lancement__gte=date_from)
    if date_to:
        ofs = ofs.filter(date_lancement__lte=date_to)

    stats = {
        'total': ofs.count(),
        'brouillon': ofs.filter(statut='BROUILLON').count(),
        'en_cours': ofs.filter(statut='EN_COURS').count(),
        'termine': ofs.filter(statut='TERMINE').count(),
        'en_retard': sum(1 for of in ofs if of.est_en_retard),
    }

    context = {
        'ofs': ofs[:100],
        'stats': stats,
        'statut_choices': OrdreFabrication.STATUT_CHOICES,
        'priorite_choices': OrdreFabrication.PRIORITE_CHOICES,
        'clients': Client.objects.filter(status='ACTIVE'),
        'selected_statut': statut,
        'selected_priorite': priorite,
        'selected_client': client_id,
        'search': search,
        'selected_date_from': date_from,
        'selected_date_to': date_to,
    }
    return render(request, 'of/of_list.html', context)


@login_required
def of_create_view(request):
    machine_warning = None
    machine_blocked = None
    machine_id = request.GET.get('machine')

    if machine_id:
        try:
            machine_check = Machine.objects.get(id=machine_id)
            peut_creer, msg = machine_check.peut_creer_of
            if not peut_creer:
                machine_blocked = msg
            elif msg:
                machine_warning = msg
        except Machine.DoesNotExist:
            pass

    if request.method == 'POST':
        form = OrdreFabricationForm(request.POST, request.FILES)
        formset = EtapeProductionFormSet(request.POST, prefix='etapes')

        blocked_messages = []
        warning_messages = []

        if form.is_valid():
            for etape_form in formset.forms:
                machine_val = etape_form.data.get(f"{etape_form.prefix}-machine")
                if machine_val:
                    try:
                        m = Machine.objects.get(id=machine_val)
                        peut, msg = m.peut_creer_of
                        if not peut:
                            blocked_messages.append(f"Étape {etape_form.data.get(f'{etape_form.prefix}-numero_etape', '?')} — {m.name}: {msg}")
                        elif msg:
                            warning_messages.append(f"{m.name}: {msg}")
                    except Machine.DoesNotExist:
                        pass

            if blocked_messages:
                for msg in blocked_messages:
                    messages.error(request, msg)
            else:
                of = form.save(commit=False)
                of.cree_par = request.user
                of.save()

                if formset.is_valid():
                    etapes = formset.save(commit=False)
                    for etape in etapes:
                        etape.of = of
                        etape.save()
                    for obj in formset.deleted_objects:
                        obj.delete()

                for msg in warning_messages:
                    messages.warning(request, msg)

                messages.success(request, f"OF {of.numero_of} créé avec succès !")
                return redirect('of_detail', of_id=of.id)
        else:
            messages.error(request, "Erreur dans le formulaire. Vérifiez les champs.")
    else:
        form = OrdreFabricationForm()
        formset = EtapeProductionFormSet(prefix='etapes', queryset=EtapeProduction.objects.none())

    context = {
        'form': form,
        'formset': formset,
        'process_types': ProcessType.objects.filter(est_actif=True),
        'machines': Machine.objects.filter(est_active=True).order_by('name'),
        'titre': 'Nouvel Ordre de Fabrication',
        'machine_warning': machine_warning,
        'machine_blocked': machine_blocked,
        'machines_statuts': {
            str(m.id): {
                'status': m.status,
                'peut_creer': m.peut_creer_of[0],
                'message': m.peut_creer_of[1],
                'om_actif': str(m.om_actif) if m.om_actif else None,
            }
            for m in Machine.objects.filter(est_active=True)
        },
    }
    return render(request, 'of/of_form.html', context)


@login_required
def of_detail_view(request, of_id):
    of = get_object_or_404(
        OrdreFabrication.objects.select_related('client', 'produit', 'cree_par'),
        id=of_id
    )

    etapes = of.etapes.select_related(
        'process_type', 'machine', 'operateur'
    ).prefetch_related('suivis', 'consommations').order_by('numero_etape')

    semi_produits = SemiProduit.objects.filter(of_origine=of).order_by('-date_creation')

    suivis = SuiviProduction.objects.filter(
        etape__of=of
    ).select_related('etape', 'operateur').order_by('-date_heure')[:50]

    etapes_data = []
    for etape in etapes:
        etapes_data.append({
            'nom': etape.get_nom_display(),
            'progression': etape.progression,
            'statut': etape.statut,
            'couleur': etape.get_statut_color(),
        })

    context = {
        'of': of,
        'etapes': etapes,
        'semi_produits': semi_produits,
        'suivis': suivis,
        'etapes_data_json': json.dumps(etapes_data),
    }
    return render(request, 'of/of_detail.html', context)


@login_required
def of_edit_view(request, of_id):
    of = get_object_or_404(OrdreFabrication, id=of_id)

    if request.method == 'POST':
        form = OrdreFabricationForm(request.POST, request.FILES, instance=of)
        formset = EtapeProductionFormSet(request.POST, instance=of, prefix='etapes')

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f"OF {of.numero_of} mis à jour !")
            return redirect('of_detail', of_id=of.id)
        else:
            messages.error(request, "Erreur dans le formulaire.")
    else:
        form = OrdreFabricationForm(instance=of)
        formset = EtapeProductionFormSet(instance=of, prefix='etapes')

    context = {
        'form': form,
        'formset': formset,
        'of': of,
        'process_types': ProcessType.objects.filter(est_actif=True),
        'machines': Machine.objects.all(),
        'titre': f'Modifier OF {of.numero_of}',
    }
    return render(request, 'of/of_form.html', context)


@login_required
def of_delete_view(request, of_id):
    of = get_object_or_404(OrdreFabrication, id=of_id)
    if request.method == 'POST':
        numero = of.numero_of
        of.delete()
        messages.success(request, f"OF {numero} supprimé.")
        return redirect('of_list')
    return render(request, 'of/of_confirm_delete.html', {'of': of})


@login_required
def of_changer_statut(request, of_id, nouveau_statut):
    of = get_object_or_404(OrdreFabrication, id=of_id)
    ancien_statut = of.statut

    if nouveau_statut in dict(OrdreFabrication.STATUT_CHOICES):
        of.statut = nouveau_statut
        if nouveau_statut == 'LANCE' and not of.date_lancement:
            of.date_lancement = timezone.now().date()
        elif nouveau_statut == 'TERMINE':
            of.date_fin_reelle = timezone.now().date()

        of.save()
        messages.success(request, f"OF {of.numero_of} : {ancien_statut} → {nouveau_statut}")
    else:
        messages.error(request, "Statut invalide.")
    return redirect('of_detail', of_id=of_id)


@login_required
def of_lancement_rapide(request):
    if request.method == 'POST':
        form = OFLancementRapideForm(request.POST)

        if form.is_valid():
            of = OrdreFabrication.objects.create(
                client=form.cleaned_data['client'],
                produit=form.cleaned_data['produit'],
                quantite_prevue=form.cleaned_data['quantite'],
                priorite=form.cleaned_data['priorite'],
                date_lancement=form.cleaned_data['date_lancement'],
                statut='LANCE',
                cree_par=request.user,
            )

            numero = 1

            if form.cleaned_data.get('etape_extrusion'):
                process = ProcessType.objects.filter(code='EXTRUSION').first()
                EtapeProduction.objects.create(
                    of=of, numero_etape=numero, process_type=process,
                    machine=form.cleaned_data.get('machine_extrusion'),
                    quantite_entree=form.cleaned_data.get('qte_extrusion') or form.cleaned_data['quantite'],
                    statut='PRET',
                )
                numero += 1

            if form.cleaned_data.get('etape_impression'):
                process = ProcessType.objects.filter(code='IMPRESSION').first()
                EtapeProduction.objects.create(
                    of=of, numero_etape=numero, process_type=process,
                    machine=form.cleaned_data.get('machine_impression'),
                    quantite_entree=form.cleaned_data.get('qte_impression') or form.cleaned_data['quantite'],
                    statut='EN_ATTENTE',
                )
                numero += 1

            if form.cleaned_data.get('etape_decoupe'):
                process = ProcessType.objects.filter(code='DECOUPE').first()
                EtapeProduction.objects.create(
                    of=of, numero_etape=numero, process_type=process,
                    machine=form.cleaned_data.get('machine_decoupe'),
                    quantite_entree=form.cleaned_data.get('qte_decoupe') or form.cleaned_data['quantite'],
                    statut='EN_ATTENTE',
                )

            messages.success(request, f"OF {of.numero_of} lancé avec {of.nb_etapes} étapes !")
            return redirect('of_detail', of_id=of.id)
    else:
        form = OFLancementRapideForm()

    context = {'form': form, 'titre': 'Lancement Rapide OF'}
    return render(request, 'of/of_lancement_rapide.html', context)


# ===========================================================================
# --- ÉTAPES & SUIVIS ---
# ===========================================================================

@login_required
def etape_detail_view(request, etape_id):
    etape = get_object_or_404(
        EtapeProduction.objects.select_related('of', 'process_type', 'machine', 'operateur'),
        id=etape_id
    )

    suivis = etape.suivis.select_related('operateur').order_by('-date_heure')
    consommations = etape.consommations.select_related('material', 'lot')
    semi_produits = SemiProduit.objects.filter(etape_origine=etape)

    if request.method == 'POST':
        form = SuiviProductionForm(request.POST)
        if form.is_valid():
            suivi = form.save(commit=False)
            suivi.etape = etape
            suivi.operateur = request.user
            suivi.save()

            etape.quantite_sortie += suivi.quantite_produite
            etape.quantite_rebut += suivi.quantite_rebut

            if suivi.type_evenement == 'DEMARRAGE':
                etape.statut = 'EN_COURS'
                if not etape.date_debut_reel:
                    etape.date_debut_reel = timezone.now()
            elif suivi.type_evenement == 'FIN':
                etape.statut = 'TERMINE'
                etape.date_fin_reel = timezone.now()
            elif suivi.type_evenement == 'ARRET':
                etape.statut = 'PAUSE'

            etape.save()

            of = etape.of
            of.quantite_produite = sum(e.quantite_sortie for e in of.etapes.filter(statut='TERMINE'))
            of.quantite_rebut = sum(e.quantite_rebut for e in of.etapes.all())
            of.save()

            messages.success(request, "Suivi enregistré !")
            return redirect('etape_detail', etape_id=etape_id)
    else:
        form = SuiviProductionForm()

    context = {
        'etape': etape, 'of': etape.of, 'suivis': suivis,
        'consommations': consommations, 'semi_produits': semi_produits,
        'form': form,
    }
    return render(request, 'of/etape_detail.html', context)


@login_required
def etape_demarrer(request, etape_id):
    etape = get_object_or_404(EtapeProduction, id=etape_id)
    if etape.statut in ['EN_ATTENTE', 'PRET', 'PAUSE']:
        etape.statut = 'EN_COURS'
        if not etape.date_debut_reel:
            etape.date_debut_reel = timezone.now()
        etape.save()

        SuiviProduction.objects.create(
            etape=etape, operateur=request.user,
            type_evenement='DEMARRAGE', commentaire="Étape démarrée"
        )

        if etape.of.statut == 'LANCE':
            etape.of.statut = 'EN_COURS'
            etape.of.save()

        messages.success(request, f"Étape {etape.numero_etape} démarrée !")

    return redirect('etape_detail', etape_id=etape_id)


@login_required
def etape_terminer(request, etape_id):
    etape = get_object_or_404(EtapeProduction, id=etape_id)

    if request.method == 'POST':
        quantite_sortie = float(request.POST.get('quantite_sortie', 0))
        quantite_rebut = float(request.POST.get('quantite_rebut', 0))

        etape.quantite_sortie = quantite_sortie
        etape.quantite_rebut = quantite_rebut
        etape.statut = 'TERMINE'
        etape.date_fin_reel = timezone.now()
        etape.save()

        if etape.genere_semi_produit and quantite_sortie > 0:
            type_sp = 'FILM_EXTRUDE'
            if etape.process_type:
                if 'IMP' in etape.process_type.code.upper():
                    type_sp = 'FILM_IMPRIME'
                elif 'COMP' in etape.process_type.code.upper():
                    type_sp = 'FILM_COMPLEXE'

            SemiProduit.objects.create(
                designation=f"SP - {etape.of.produit.name} - Étape {etape.numero_etape}",
                type_semi_produit=type_sp,
                of_origine=etape.of, etape_origine=etape,
                quantite=quantite_sortie, laize=etape.of.laize, conforme=True,
            )

        SuiviProduction.objects.create(
            etape=etape, operateur=request.user, type_evenement='FIN',
            quantite_produite=quantite_sortie, quantite_rebut=quantite_rebut,
            commentaire="Étape terminée"
        )

        of = etape.of
        if all(e.statut == 'TERMINE' for e in of.etapes.all()):
            of.statut = 'TERMINE'
            of.date_fin_reelle = timezone.now().date()
            of.quantite_produite = quantite_sortie

        of.quantite_rebut = sum(e.quantite_rebut for e in of.etapes.all())
        of.save()

        etape_suivante = EtapeProduction.objects.filter(
            of=of, numero_etape=etape.numero_etape + 1
        ).first()

        if etape_suivante:
            etape_suivante.statut = 'PRET'
            etape_suivante.quantite_entree = quantite_sortie
            etape_suivante.save()

        messages.success(request, f"Étape {etape.numero_etape} terminée !")
        return redirect('of_detail', of_id=etape.of.id)

    return render(request, 'of/etape_terminer.html', {'etape': etape})


# ===========================================================================
# --- SEMI-PRODUITS & PROCESS TYPES ---
# ===========================================================================

@login_required
def semi_produit_list(request):
    statut = request.GET.get('statut', '')
    type_sp = request.GET.get('type', '')

    semi_produits = SemiProduit.objects.select_related(
        'of_origine', 'etape_origine', 'emplacement'
    ).order_by('-date_creation')

    if statut:
        semi_produits = semi_produits.filter(statut=statut)
    if type_sp:
        semi_produits = semi_produits.filter(type_semi_produit=type_sp)

    stats = {
        'total': semi_produits.count(),
        'disponible': semi_produits.filter(statut='DISPONIBLE').count(),
        'reserve': semi_produits.filter(statut='RESERVE').count(),
        'total_kg': semi_produits.filter(statut='DISPONIBLE').aggregate(t=Sum('quantite'))['t'] or 0,
    }

    context = {
        'semi_produits': semi_produits[:100], 'stats': stats,
        'statut_choices': SemiProduit.STATUT_CHOICES,
        'type_choices': SemiProduit.TYPE_CHOICES,
        'selected_statut': statut, 'selected_type': type_sp,
    }
    return render(request, 'of/semi_produit_list.html', context)


@login_required
def semi_produit_detail(request, sp_id):
    sp = get_object_or_404(
        SemiProduit.objects.select_related(
            'of_origine', 'etape_origine', 'etape_destination', 'emplacement'
        ), id=sp_id
    )
    return render(request, 'of/semi_produit_detail.html', {'semi_produit': sp})


@login_required
def process_type_list(request):
    process_types = ProcessType.objects.all().order_by('ordre_defaut')
    if request.method == 'POST':
        form = ProcessTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Type de processus créé !")
            return redirect('process_type_list')
    else:
        form = ProcessTypeForm()

    return render(request, 'of/process_type_list.html', {'process_types': process_types, 'form': form})


@login_required
def process_type_delete(request, pt_id):
    pt = get_object_or_404(ProcessType, id=pt_id)
    if request.method == 'POST':
        pt.delete()
        messages.success(request, "Type de processus supprimé.")
    return redirect('process_type_list')


@login_required
def of_stats_api(request):
    statuts = {code: OrdreFabrication.objects.filter(statut=code).count() for code, _ in OrdreFabrication.STATUT_CHOICES}
    date_30j = timezone.now().date() - timedelta(days=30)
    ofs_recents = OrdreFabrication.objects.filter(
        date_lancement__gte=date_30j
    ).values('date_lancement').annotate(
        qte=Sum('quantite_produite')
    ).order_by('date_lancement')

    prod_par_jour = {str(of['date_lancement']): of['qte'] or 0 for of in ofs_recents}
    top_clients = OrdreFabrication.objects.values(
        'client__name'
    ).annotate(
        total=Sum('quantite_prevue')
    ).order_by('-total')[:5]

    return JsonResponse({
        'statuts': statuts,
        'production_par_jour': prod_par_jour,
        'top_clients': list(top_clients),
    })


# ===========================================================================
# --- PRODUCTION SPÉCIALE & QUALITÉ ---
# ===========================================================================

def _get_filtered_entries(request):
    entries = ProductionEntry.objects.exclude(
        machine__name__icontains="Nettoyage"
    ).order_by('-date', '-heure_debut')
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    machine_id = request.GET.get('machine', '')
    support = request.GET.get('support', '')
    equipe = request.GET.get('equipe', '')
    produit = request.GET.get('produit', '')
    unite = request.GET.get('unite_commande', '')

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
    if produit:
        entries = entries.filter(produit=produit)
    if unite:
        entries = entries.filter(unite_commande=unite)
    return entries


def _get_filter_context(request):
    all_produits = ProductionEntry.objects.values_list('produit', flat=True).distinct().order_by('produit')
    machines_sans_nettoyage = Machine.objects.exclude(name__icontains="Nettoyage").order_by('name')
    return {
        'all_machines': machines_sans_nettoyage,
        'all_supports': ProductionEntry.objects.values_list('support', flat=True).distinct().order_by('support'),
        'all_produits': all_produits,
        'all_unites': [('PCS', 'Pièces (Étiquettes/Sacs)'), ('KG', 'Tonnage (KG)'), ('ML', 'Mètres Linéaires (ML)')],
        'selected_date_from': request.GET.get('date_from', ''),
        'selected_date_to': request.GET.get('date_to', ''),
        'selected_machine': request.GET.get('machine', ''),
        'selected_support': request.GET.get('support', ''),
        'selected_equipe': request.GET.get('equipe', ''),
        'selected_produit': request.GET.get('produit', ''),
        'selected_unite': request.GET.get('unite_commande', ''),
    }


@login_required
def prod_dashboard(request):
    entries = _get_filtered_entries(request)
    total_prod_ml = entries.aggregate(t=Sum('prod_ml'))['t'] or 0
    total_prod_kg = entries.aggregate(t=Sum('prod_kg'))['t'] or 0
    total_dechets_kg = round(sum(e.total_dechets_kg for e in entries), 2)
    taux_dechets = round((total_dechets_kg / float(total_prod_kg) * 100), 2) if total_prod_kg else 0

    stats_modes = {
        'PCS': {'count': 0, 'volume': 0},
        'KG': {'count': 0, 'volume': 0},
        'ML': {'count': 0, 'volume': 0}
    }
    for e in entries:
        mode = getattr(e, 'unite_commande', 'PCS') or 'PCS'
        if mode in stats_modes:
            stats_modes[mode]['count'] += 1
            stats_modes[mode]['volume'] += float(e.quantite_lancee or 0)

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
        'stats_modes': stats_modes,
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
    if request.method == 'POST':
        form = ProductionEntryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Saisie de production enregistrée avec succès.")
            return redirect('prod_dashboard')
        else:
            messages.error(request, "Erreur dans le formulaire. Vérifiez les données saisies.")
    else:
        form = ProductionEntryForm()
    
    form.fields['machine'].queryset = Machine.objects.exclude(name__icontains="Nettoyage")
    recent = ProductionEntry.objects.all().order_by('-date', '-heure_debut')[:10]
    return render(request, 'production_special/saisie.html', {
        'form': form, 'titre': 'Nouvelle Saisie Production',
        'recent': recent, 'edit_mode': False,
    })


@login_required
def prod_edit_entry(request, id):
    entry = get_object_or_404(ProductionEntry, id=id)
    if request.method == 'POST':
        form = ProductionEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, "Saisie mise à jour avec succès.")
            return redirect('prod_base')
        else:
            messages.error(request, "Erreur dans le formulaire lors de la modification.")
    else:
        form = ProductionEntryForm(instance=entry)
    
    form.fields['machine'].queryset = Machine.objects.exclude(name__icontains="Nettoyage")
    recent = ProductionEntry.objects.all().order_by('-date', '-heure_debut')[:10]
    return render(request, 'production_special/saisie.html', {
        'form': form, 'titre': f'Modifier Saisie — {entry.produit} ({entry.date})',
        'recent': recent, 'edit_mode': True, 'entry': entry,
    })


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
    entries = _get_filtered_entries(request)
    context = {'entries': entries}
    context.update(_get_filter_context(request))
    return render(request, 'production_special/base.html', context)


@login_required
def prod_detail_qualite(request):
    entries = _get_filtered_entries(request)
    total_dechets_kg = round(sum(e.total_dechets_kg for e in entries), 2)
    total_dechets_demarrage = round(sum(e.dechets_demarrage for e in entries), 2)
    total_dechets_lisiere = round(sum(e.dechets_lisiere for e in entries), 2)
    total_dechets_jonction = round(sum(e.dechets_jonction for e in entries), 2)
    total_dechets_transport = round(sum(e.dechets_transport for e in entries), 2)

    dechets_par_machine = defaultdict(lambda: {'total': 0, 'prod': 0, 'dem': 0, 'lis': 0, 'jon': 0, 'tra': 0})
    dechets_par_equipe = defaultdict(lambda: {'total': 0, 'prod': 0, 'dem': 0, 'lis': 0, 'jon': 0, 'tra': 0})

    for e in entries:
        m_name = e.machine.name if e.machine else "Inconnue"
        eq = e.equipe or 'Inconnue'
        
        dechets_par_machine[m_name]['total'] += e.total_dechets_kg
        dechets_par_machine[m_name]['prod'] += e.prod_kg
        dechets_par_machine[m_name]['dem'] += e.dechets_demarrage
        dechets_par_machine[m_name]['lis'] += e.dechets_lisiere
        dechets_par_machine[m_name]['jon'] += e.dechets_jonction
        dechets_par_machine[m_name]['tra'] += e.dechets_transport

        dechets_par_equipe[eq]['total'] += e.total_dechets_kg
        dechets_par_equipe[eq]['prod'] += e.prod_kg
        dechets_par_equipe[eq]['dem'] += e.dechets_demarrage
        dechets_par_equipe[eq]['lis'] += e.dechets_lisiere
        dechets_par_equipe[eq]['jon'] += e.dechets_jonction
        dechets_par_equipe[eq]['tra'] += e.dechets_transport

    for val in list(dechets_par_machine.values()) + list(dechets_par_equipe.values()):
        val['taux'] = round((val['total'] / val['prod'] * 100), 2) if val['prod'] > 0 else 0
        val['total'] = round(val['total'], 2)

    data_dates = defaultdict(lambda: {
        'dem_a': 0, 'dem_b': 0, 'dem_c': 0,
        'lis_a': 0, 'lis_b': 0, 'lis_c': 0,
        'jon_a': 0, 'jon_b': 0, 'jon_c': 0,
        'tra_a': 0, 'tra_b': 0, 'tra_c': 0, 'total': 0
    })
    for e in entries:
        d = str(e.date)
        eq_key = (e.equipe or 'A').lower()
        data_dates[d]['dem_' + eq_key] += e.dechets_demarrage
        data_dates[d]['lis_' + eq_key] += e.dechets_lisiere
        data_dates[d]['jon_' + eq_key] += e.dechets_jonction
        data_dates[d]['tra_' + eq_key] += e.dechets_transport
        data_dates[d]['total'] += e.total_dechets_kg

    dates_sorted = sorted(data_dates.keys())
    context = {
        'entries': entries,
        'total_dechets_kg': total_dechets_kg,
        'total_dechets_demarrage': total_dechets_demarrage,
        'total_dechets_lisiere': total_dechets_lisiere,
        'total_dechets_jonction': total_dechets_jonction,
        'total_dechets_transport': total_dechets_transport,
        'dechets_par_machine': dict(dechets_par_machine),
        'dechets_par_equipe': dict(dechets_par_equipe),
        'dates_labels': json.dumps(dates_sorted),
        'dem_a': json.dumps([round(data_dates[d]['dem_a'], 2) for d in dates_sorted]),
        'dem_b': json.dumps([round(data_dates[d]['dem_b'], 2) for d in dates_sorted]),
        'dem_c': json.dumps([round(data_dates[d]['dem_c'], 2) for d in dates_sorted]),
        'lis_a': json.dumps([round(data_dates[d]['lis_a'], 2) for d in dates_sorted]),
        'lis_b': json.dumps([round(data_dates[d]['lis_b'], 2) for d in dates_sorted]),
        'lis_c': json.dumps([round(data_dates[d]['lis_c'], 2) for d in dates_sorted]),
        'jon_a': json.dumps([round(data_dates[d]['jon_a'], 2) for d in dates_sorted]),
        'jon_b': json.dumps([round(data_dates[d]['jon_b'], 2) for d in dates_sorted]),
        'jon_c': json.dumps([round(data_dates[d]['jon_c'], 2) for d in dates_sorted]),
        'tra_a': json.dumps([round(data_dates[d]['tra_a'], 2) for d in dates_sorted]),
        'tra_b': json.dumps([round(data_dates[d]['tra_b'], 2) for d in dates_sorted]),
        'tra_c': json.dumps([round(data_dates[d]['tra_c'], 2) for d in dates_sorted]),
        'h_dates': json.dumps(dates_sorted),
        'h_dem': json.dumps([round(data_dates[d]['dem_a'] + data_dates[d]['dem_b'] + data_dates[d]['dem_c'], 2) for d in dates_sorted]),
        'h_lis': json.dumps([round(data_dates[d]['lis_a'] + data_dates[d]['lis_b'] + data_dates[d]['lis_c'], 2) for d in dates_sorted]),
        'h_jon': json.dumps([round(data_dates[d]['jon_a'] + data_dates[d]['jon_b'] + data_dates[d]['jon_c'], 2) for d in dates_sorted]),
        'h_tra': json.dumps([round(data_dates[d]['tra_a'] + data_dates[d]['tra_b'] + data_dates[d]['tra_c'], 2) for d in dates_sorted]),
    }
    context.update(_get_filter_context(request))
    return render(request, 'production_special/detail_qualite.html', context)


@login_required
def prod_synthese_temps(request):
    entries = _get_filtered_entries(request)
    decalage_total = round(sum(e.decalage for e in entries), 2)
    temps_ouverture_total_min = sum(e.temps_ouverture_minutes for e in entries)
    heures = int(temps_ouverture_total_min // 60)
    minutes = int(temps_ouverture_total_min % 60)
    temps_ouverture_total = f"{heures}:{minutes:02d}"
    total_rebobinage = round(sum(e.rebobinage_kg for e in entries), 2)

    total_calage_min = sum(getattr(e, 'temps_calage_min', 30) or 30 for e in entries)
    total_roulage_min = max(0, temps_ouverture_total_min - total_calage_min)
    
    calage_heures = round(total_calage_min / 60, 1)
    roulage_heures = round(total_roulage_min / 60, 1)

    machine_vitesses = defaultdict(list)
    for e in entries:
        if e.machine and getattr(e, 'vitesse_machine_trmin', None):
            machine_vitesses[e.machine.name].append(e.vitesse_machine_trmin)
    
    avg_machine_vitesses = {
        m_name: round(sum(vits) / len(vits), 1) if vits else 0
        for m_name, vits in machine_vitesses.items()
    }

    unite_stats = defaultdict(lambda: {'count': 0, 'total': 0})
    for e in entries:
        mode = getattr(e, 'unite_commande', 'PCS') or 'PCS'
        unite_stats[mode]['count'] += 1
        unite_stats[mode]['total'] += float(e.quantite_lancee or 0)

    data_dec = defaultdict(float)
    data_temps_a = defaultdict(float)
    data_temps_b = defaultdict(float)
    data_temps_c = defaultdict(float)
    produits_set = set()

    for e in entries:
        d = str(e.date)
        data_dec[d] += e.decalage
        produits_set.add(e.produit[:20])
        eq = e.equipe or 'A'
        if eq == 'A':
            data_temps_a[e.produit[:20]] += e.temps_ouverture_minutes / 60
        elif eq == 'B':
            data_temps_b[e.produit[:20]] += e.temps_ouverture_minutes / 60
        elif eq == 'C':
            data_temps_c[e.produit[:20]] += e.temps_ouverture_minutes / 60

    dates_sorted = sorted(data_dec.keys())
    produits_sorted = sorted(produits_set)

    calculs_recents = CalculTempsProduction.objects.all().select_related(
        'client', 'machine_impression', 'machine_decoupe', 'cree_par'
    ).order_by('-date_calcul')[:30]

    form_calcul = CalculTempsProductionForm()

    context = {
        'entries': entries,
        'decalage_total': decalage_total,
        'temps_ouverture_total': temps_ouverture_total,
        'total_rebobinage': total_rebobinage,
        'calage_heures': calage_heures,
        'roulage_heures': roulage_heures,
        'avg_machine_vitesses': avg_machine_vitesses,
        'unite_stats': dict(unite_stats),
        'decalage_dates': json.dumps(dates_sorted),
        'decalage_values': json.dumps([round(data_dec[d], 2) for d in dates_sorted]),
        'temps_produit_labels': json.dumps(produits_sorted),
        'temps_produit_a': json.dumps([round(data_temps_a.get(p, 0), 2) for p in produits_sorted]),
        'temps_produit_b': json.dumps([round(data_temps_b.get(p, 0), 2) for p in produits_sorted]),
        'temps_produit_c': json.dumps([round(data_temps_c.get(p, 0), 2) for p in produits_sorted]),
        'calculs_recents': calculs_recents,
        'form_calcul': form_calcul,
    }
    context.update(_get_filter_context(request))
    return render(request, 'production_special/synthese_temps.html', context)


# ===========================================================================
# --- CALCULATEUR PRÉVISIONNEL DE TEMPS ---
# ===========================================================================

@login_required
def prod_calculer_temps(request):
    if request.method == 'POST':
        form = CalculTempsProductionForm(request.POST)
        if form.is_valid():
            calcul = form.save(commit=False)
            calcul.cree_par = request.user
            calcul.save()
            messages.success(request, f"✅ Calcul prévisionnel pour '{calcul.nom_job}' enregistré avec succès !")
            return redirect('prod_synthese_temps')
        else:
            messages.error(request, "❌ Erreur dans le formulaire de calcul. Vérifiez les champs.")
    return redirect('prod_synthese_temps')


@login_required
def prod_calculer_temps_save(request):
    return redirect('prod_synthese_temps')


@login_required
def prod_calculer_temps_delete(request, id):
    calcul = get_object_or_404(CalculTempsProduction, id=id)
    if request.method == 'POST':
        calcul.delete()
        messages.success(request, "🗑️ Calcul prévisionnel supprimé.")
    return redirect('prod_synthese_temps')