import json
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.utils import timezone
from django.http import JsonResponse
from django.contrib import messages

from ..models import (
    Client, ProductionOrder, OrdreFabrication, EtapeProduction, SemiProduit,
    SuiviProduction, ProcessType, Machine
)
from ..forms import (
    ProductionOrderForm, OrdreFabricationForm, EtapeProductionFormSet,
    SuiviProductionForm, ProcessTypeForm, OFLancementRapideForm
)


# ===========================================================================
# --- ANCIENS OF ---
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
# --- ÉTAPES DE PRODUCTION ---
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
# --- SEMI-PRODUITS ---
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
    context = {'semi_produit': sp}
    return render(request, 'of/semi_produit_detail.html', context)


# ===========================================================================
# --- PROCESS TYPES ---
# ===========================================================================

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

    context = {'process_types': process_types, 'form': form}
    return render(request, 'of/process_type_list.html', context)


@login_required
def process_type_delete(request, pt_id):
    pt = get_object_or_404(ProcessType, id=pt_id)
    if request.method == 'POST':
        pt.delete()
        messages.success(request, "Type de processus supprimé.")
    return redirect('process_type_list')


# ===========================================================================
# --- API JSON ---
# ===========================================================================

@login_required
def of_stats_api(request):
    statuts = {}
    for code, label in OrdreFabrication.STATUT_CHOICES:
        statuts[code] = OrdreFabrication.objects.filter(statut=code).count()

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

    data = {
        'statuts': statuts,
        'production_par_jour': prod_par_jour,
        'top_clients': list(top_clients),
    }

    return JsonResponse(data)