import json
import calendar
from collections import defaultdict
from datetime import timedelta, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User, Group
from django.contrib.admin.models import LogEntry
from django.db.models import Count, Sum, Q, F
from django.utils import timezone
from django.http import JsonResponse
from django.contrib import messages

from ..models import (
    Client, Opportunite, Quote, OrdreFabrication, ProductionEntry, Material,
    Machine, Atelier, OrdreMaintenance, AlerteMaintenance, PlanMaintenancePreventive, PieceRechange, CategoriePiece
)
from ..forms import (
    AtelierForm, MachineMaintenanceForm, CompteurMachineForm, OrdreMaintenanceForm,
    ClotureOrdreMaintenanceForm, ConsommationPieceForm, PlanMaintenancePreventiveForm, PieceRechangeForm, MouvementPieceForm, CategoriePieceForm
)


# ===========================================================================
# --- ADMINISTRATION PERSONNALISÉE ---
# ===========================================================================

@login_required
@staff_member_required
def admin_view(request):
    users = User.objects.all().order_by('-date_joined')
    stats_modules = [
        {
            'nom': 'CRM & Clients', 'icone': '🤝',
            'items': [
                {'label': 'Clients', 'count': Client.objects.count(), 'url': 'crm_view'},
                {'label': 'Opportunités', 'count': Opportunite.objects.count(), 'url': 'opportunites_view'},
                {'label': 'Devis', 'count': Quote.objects.count(), 'url': 'quotes_view'}
            ]
        },
        {
            'nom': 'Production', 'icone': '🏭',
            'items': [
                {'label': 'OF Multi', 'count': OrdreFabrication.objects.count(), 'url': 'of_list'},
                {'label': 'Saisies', 'count': ProductionEntry.objects.count(), 'url': 'prod_dashboard'}
            ]
        },
        {
            'nom': 'Stock', 'icone': '📦',
            'items': [
                {'label': 'Matières', 'count': Material.objects.count(), 'url': 'stock_advanced'},
                {'label': 'Machines', 'count': Machine.objects.count(), 'url': 'machine_view'}
            ]
        },
    ]
    return render(request, 'admin_custom.html', {
        'users': users,
        'total_users': users.count(),
        'active_users': users.filter(is_active=True).count(),
        'staff_users': users.filter(is_staff=True).count(),
        'groups': Group.objects.annotate(user_count=Count('user')).all(),
        'stats_modules': stats_modules,
        'recent_actions': LogEntry.objects.select_related('user', 'content_type').order_by('-action_time')[:20],
        'page_title': 'Administration',
    })


@login_required
@staff_member_required
def admin_add_user(request):
    if request.method == 'POST':
        uname = request.POST.get('username', '').strip()
        em = request.POST.get('email', '').strip()
        pw = request.POST.get('password', '')
        if uname and pw and not User.objects.filter(username=uname).exists():
            u = User.objects.create_user(username=uname, email=em, password=pw)
            u.is_staff = (request.POST.get('is_staff') == 'on')
            u.is_active = (request.POST.get('is_active') == 'on')
            u.save()
            messages.success(request, f"✅ Utilisateur '{uname}' créé avec succès !")
        else:
            messages.error(request, "❌ Données invalides ou utilisateur déjà existant.")
    return redirect('admin_view')


@login_required
@staff_member_required
def admin_edit_user(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        u.username = request.POST.get('username', '').strip() or u.username
        u.email = request.POST.get('email', '').strip()
        u.is_staff = (request.POST.get('is_staff') == 'on')
        u.is_active = (request.POST.get('is_active') == 'on')
        if request.POST.get('password'):
            u.set_password(request.POST['password'])
        u.save()
        messages.success(request, f"✅ Utilisateur '{u.username}' mis à jour !")
    return redirect('admin_view')


@login_required
@staff_member_required
def admin_toggle_user(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if not u.is_superuser:
        u.is_active = not u.is_active
        u.save()
        messages.success(request, f"✅ Utilisateur '{u.username}' {'activé' if u.is_active else 'désactivé'}.")
    return redirect('admin_view')


# ===========================================================================
# --- TABLEAU DE BORD MAINTENANCE ---
# ===========================================================================

@login_required
def maintenance_dashboard(request):
    today = timezone.now().date()
    start_m = today.replace(day=1)
    machines_en_panne = Machine.objects.filter(status='PANNE', est_active=True)
    oms_m = OrdreMaintenance.objects.filter(date_creation__date__gte=start_m)
    
    repartition_type = [
        {'label': lbl, 'count': OrdreMaintenance.objects.filter(type_maintenance=code, date_creation__date__gte=start_m).count()}
        for code, lbl in OrdreMaintenance.TYPE_CHOICES
    ]
    top_pannes = Machine.objects.annotate(
        nb_pannes=Count('ordres_maintenance', filter=Q(ordres_maintenance__type_maintenance='CORRECTIVE'))
    ).filter(nb_pannes__gt=0).order_by('-nb_pannes')[:5]
    
    evolution = []
    for i in range(5, -1, -1):
        ref = today - timedelta(days=30 * i)
        tot = OrdreMaintenance.objects.filter(date_creation__month=ref.month, date_creation__year=ref.year).aggregate(t=Sum('temps_arret_minutes'))['t'] or 0
        evolution.append({'mois': ref.strftime('%b %Y'), 'heures': round(tot / 60, 1)})

    return render(request, 'maintenance/dashboard.html', {
        'total_machines': Machine.objects.filter(est_active=True).count(),
        'machines_en_panne': machines_en_panne.count(),
        'machines_en_maintenance': Machine.objects.filter(status='MAINT', est_active=True).count(),
        'machines_en_prod': Machine.objects.filter(status='RUN', est_active=True).count(),
        'om_ouverts': OrdreMaintenance.objects.filter(statut__in=['OUVERT', 'EN_COURS', 'EN_ATTENTE_PIECE']).count(),
        'om_corrective_mois': OrdreMaintenance.objects.filter(type_maintenance='CORRECTIVE', date_creation__date__gte=start_m).count(),
        'om_preventive_mois': OrdreMaintenance.objects.filter(type_maintenance='PREVENTIVE', date_creation__date__gte=start_m).count(),
        'om_termines_mois': OrdreMaintenance.objects.filter(statut='TERMINE', date_cloture__date__gte=start_m).count(),
        'om_en_retard': OrdreMaintenance.objects.filter(statut__in=['OUVERT', 'EN_COURS'], date_planifiee__lt=timezone.now()).count(),
        'temps_arret_heures': round((OrdreMaintenance.objects.filter(date_creation__date__gte=start_m).aggregate(t=Sum('temps_arret_minutes'))['t'] or 0) / 60, 1),
        'cout_total_mois': sum(om.cout_total for om in oms_m),
        'plans_actifs': PlanMaintenancePreventive.objects.filter(statut='ACTIF').count(),
        'plans_a_faire': sum(1 for p in PlanMaintenancePreventive.objects.filter(statut='ACTIF') if p.est_a_faire),
        'plans_en_retard': sum(1 for p in PlanMaintenancePreventive.objects.filter(statut='ACTIF') if p.est_en_retard),
        'pieces_total': PieceRechange.objects.filter(est_active=True).count(),
        'pieces_stock_bas': PieceRechange.objects.filter(est_active=True, quantite_stock__lte=F('stock_minimum')).count(),
        'pieces_rupture': PieceRechange.objects.filter(est_active=True, quantite_stock__lte=0).count(),
        'valeur_stock_pieces': sum(p.valeur_stock for p in PieceRechange.objects.filter(est_active=True)),
        'alertes_non_lues': AlerteMaintenance.objects.filter(est_lue=False).count(),
        'alertes_critiques': AlerteMaintenance.objects.filter(est_traitee=False, niveau='CRITICAL').count(),
        'alertes_recentes': AlerteMaintenance.objects.filter(est_traitee=False).order_by('-date_creation')[:10],
        'ateliers': Atelier.objects.filter(est_actif=True).prefetch_related('machines_atelier').order_by('ordre_affichage'),
        'om_recents': OrdreMaintenance.objects.select_related('machine', 'technicien_principal').order_by('-date_creation')[:10],
        'repartition_type_labels': json.dumps([r['label'] for r in repartition_type]),
        'repartition_type_data': json.dumps([r['count'] for r in repartition_type]),
        'top_pannes_labels': json.dumps([m.name for m in top_pannes]),
        'top_pannes_data': json.dumps([m.nb_pannes for m in top_pannes]),
        'evolution_arret_mois': json.dumps([e['mois'] for e in evolution]),
        'evolution_arret_data': json.dumps([e['heures'] for e in evolution]),
    })


# ===========================================================================
# --- ATELIERS & MACHINES ---
# ===========================================================================

@login_required
def atelier_list(request):
    form = AtelierForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Atelier créé !")
        return redirect('atelier_list')
    return render(request, 'maintenance/atelier_list.html', {
        'ateliers': Atelier.objects.prefetch_related('machines_atelier').order_by('ordre_affichage'),
        'form': form
    })


@login_required
def atelier_create(request):
    form = AtelierForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Atelier créé !")
        return redirect('atelier_list')
    return render(request, 'maintenance/atelier_form.html', {'form': form, 'titre': 'Nouvel Atelier'})


@login_required
def maintenance_machine_list(request):
    at_f = request.GET.get('atelier', '')
    type_f = request.GET.get('type', '')
    stat_f = request.GET.get('status', '')
    q = request.GET.get('q', '')

    machines = Machine.objects.select_related('atelier').filter(est_active=True)
    if at_f:
        machines = machines.filter(atelier_id=at_f)
    if type_f:
        machines = machines.filter(type=type_f)
    if stat_f:
        machines = machines.filter(status=stat_f)
    if q:
        machines = machines.filter(
            Q(name__icontains=q) | Q(code_machine__icontains=q) | Q(marque__icontains=q) | Q(modele__icontains=q)
        )
    
    return render(request, 'maintenance/machine_list.html', {
        'machines': machines.order_by('atelier', 'name'),
        'stats': {
            'total': machines.count(),
            'run': machines.filter(status='RUN').count(),
            'stop': machines.filter(status='STOP').count(),
            'maint': machines.filter(status='MAINT').count(),
            'panne': machines.filter(status='PANNE').count()
        },
        'ateliers': Atelier.objects.filter(est_actif=True),
        'type_choices': Machine.TYPE_CHOICES,
        'status_choices': Machine.STATUS_CHOICES,
        'selected_atelier': at_f,
        'selected_type': type_f,
        'selected_status': stat_f,
        'search': q,
    })


@login_required
def maintenance_machine_create(request):
    form = MachineMaintenanceForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        m = form.save()
        messages.success(request, f"Machine {m.name} créée !")
        return redirect('maintenance_machine_detail', machine_id=m.id)
    return render(request, 'maintenance/machine_form.html', {'form': form, 'titre': 'Nouvelle Machine'})


@login_required
def maintenance_machine_detail(request, machine_id):
    m = get_object_or_404(Machine.objects.select_related('atelier', 'fournisseur_machine'), id=machine_id)
    pannes = m.ordres_maintenance.filter(type_maintenance='CORRECTIVE').order_by('-date_creation')[:50]
    p_par_mois = defaultdict(int)
    for p in pannes:
        p_par_mois[p.date_creation.strftime('%Y-%m')] += 1
    mois_sorted = sorted(p_par_mois.keys())

    return render(request, 'maintenance/machine_detail.html', {
        'machine': m,
        'oms': m.ordres_maintenance.select_related('technicien_principal').order_by('-date_creation')[:20],
        'plans': m.plans_preventifs.filter(statut='ACTIF').order_by('titre'),
        'pieces': m.pieces_compatibles.filter(est_active=True),
        'compteurs': m.releves_compteur.order_by('-date_releve')[:20],
        'operateurs': m.operateurs_autorises.filter(statut='VALIDE').select_related('employee'),
        'mtbf': m.mtbf,
        'mttr': m.mttr,
        'taux_disponibilite': m.taux_disponibilite,
        'nb_pannes_total': m.nb_pannes_total,
        'temps_arret_total': m.temps_arret_total_heures,
        'pannes_mois_labels': json.dumps(mois_sorted),
        'pannes_mois_data': json.dumps([p_par_mois[mois] for mois in mois_sorted]),
    })


@login_required
def maintenance_machine_edit(request, machine_id):
    m = get_object_or_404(Machine, id=machine_id)
    form = MachineMaintenanceForm(request.POST or None, request.FILES or None, instance=m)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"Machine {m.name} mise à jour !")
        return redirect('maintenance_machine_detail', machine_id=m.id)
    return render(request, 'maintenance/machine_form.html', {'form': form, 'machine': m, 'titre': f'Modifier {m.name}'})


@login_required
def maintenance_machine_delete(request, machine_id):
    m = get_object_or_404(Machine, id=machine_id)
    if request.method == 'POST':
        if m.ordres_maintenance.filter(statut__in=['OUVERT', 'EN_COURS', 'EN_ATTENTE_PIECE']).count() > 0:
            messages.error(request, "Impossible de supprimer la machine avec des ordres actifs.")
        else:
            m.delete()
            messages.success(request, "Machine supprimée.")
            return redirect('maintenance_machine_list')
    return render(request, 'maintenance/machine_confirm_delete.html', {'machine': m})


@login_required
def machine_compteur_add(request, machine_id):
    m = get_object_or_404(Machine, id=machine_id)
    form = CompteurMachineForm(request.POST or None, initial={'machine': m})
    if request.method == 'POST' and form.is_valid():
        c = form.save(commit=False)
        c.machine = m
        c.releve_par = request.user
        c.save()
        messages.success(request, "Compteur mis à jour !")
        return redirect('maintenance_machine_detail', machine_id=m.id)
    return render(request, 'maintenance/compteur_form.html', {'form': form, 'machine': m, 'titre': f'Relevé compteur — {m.name}'})


# ===========================================================================
# --- ORDRES DE MAINTENANCE (OM) ---
# ===========================================================================

@login_required
def om_list(request):
    t_f = request.GET.get('type', '')
    s_f = request.GET.get('statut', '')
    m_f = request.GET.get('machine', '')
    p_f = request.GET.get('priorite', '')
    q = request.GET.get('q', '')

    oms = OrdreMaintenance.objects.select_related('machine', 'technicien_principal', 'demandeur').order_by('-date_creation')
    if t_f:
        oms = oms.filter(type_maintenance=t_f)
    if s_f:
        oms = oms.filter(statut=s_f)
    if m_f:
        oms = oms.filter(machine_id=m_f)
    if p_f:
        oms = oms.filter(priorite=p_f)
    if q:
        oms = oms.filter(Q(numero_om__icontains=q) | Q(titre__icontains=q) | Q(machine__name__icontains=q))

    return render(request, 'maintenance/om_list.html', {
        'oms': oms[:100],
        'machines': Machine.objects.filter(est_active=True),
        'stats': {
            'total': oms.count(),
            'ouverts': oms.filter(statut='OUVERT').count(),
            'en_cours': oms.filter(statut='EN_COURS').count(),
            'termines': oms.filter(statut='TERMINE').count(),
            'en_retard': sum(1 for om in oms if om.est_en_retard)
        },
        'type_choices': OrdreMaintenance.TYPE_CHOICES,
        'statut_choices': OrdreMaintenance.STATUT_CHOICES,
        'priorite_choices': OrdreMaintenance.PRIORITE_CHOICES,
        'selected_type': t_f,
        'selected_statut': s_f,
        'selected_machine': m_f,
        'selected_priorite': p_f,
        'search': q,
    })


@login_required
def om_create(request):
    initial = {}
    if request.GET.get('machine'):
        initial['machine'] = request.GET['machine']
    form = OrdreMaintenanceForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        om = form.save(commit=False)
        om.demandeur = request.user
        om.save()
        om.machine.status = 'PANNE' if om.type_maintenance == 'CORRECTIVE' else 'MAINT'
        om.machine.save(update_fields=['status'])
        AlerteMaintenance.objects.create(
            type_alerte='PANNE' if om.type_maintenance == 'CORRECTIVE' else 'PREVENTIVE_DUE',
            niveau='CRITICAL' if om.type_maintenance == 'CORRECTIVE' else 'WARNING',
            titre=f"{'🚨 PANNE' if om.type_maintenance == 'CORRECTIVE' else '🔧 Maintenance'} — {om.machine.name}",
            message=f"OM-{om.numero_om} créé : {om.titre}",
            machine=om.machine
        )
        messages.success(request, f"OM-{om.numero_om} créé !")
        return redirect('om_detail', om_id=om.id)
    return render(request, 'maintenance/om_form.html', {'form': form, 'titre': 'Nouvel Ordre de Maintenance'})


@login_required
def om_create_panne(request, machine_id):
    m = get_object_or_404(Machine, id=machine_id)
    form = OrdreMaintenanceForm(request.POST or None, initial={'machine': m, 'type_maintenance': 'CORRECTIVE', 'priorite': 'URGENTE'})
    if request.method == 'POST' and form.is_valid():
        om = form.save(commit=False)
        om.demandeur = request.user
        om.type_maintenance = 'CORRECTIVE'
        om.machine = m
        om.save()
        m.status = 'PANNE'
        m.save(update_fields=['status'])
        AlerteMaintenance.objects.create(
            type_alerte='PANNE',
            niveau='CRITICAL',
            titre=f"🚨 PANNE — {m.name}",
            message=f"Machine {m.name} en panne.",
            machine=m
        )
        messages.success(request, f"🚨 Panne déclarée ! OM-{om.numero_om} créé.")
        return redirect('om_detail', om_id=om.id)
    return render(request, 'maintenance/om_form.html', {'form': form, 'machine': m, 'titre': f'🚨 Déclarer une Panne — {m.name}'})


@login_required
def om_detail(request, om_id):
    om = get_object_or_404(
        OrdreMaintenance.objects.select_related('machine', 'machine__atelier', 'technicien_principal', 'demandeur', 'plan_preventif'),
        id=om_id
    )
    return render(request, 'maintenance/om_detail.html', {
        'om': om,
        'consommations': om.consommations_pieces.select_related('piece').all()
    })


@login_required
def om_demarrer(request, om_id):
    if request.method == 'POST':
        om = get_object_or_404(OrdreMaintenance, id=om_id)
        om.statut = 'EN_COURS'
        om.date_debut_intervention = timezone.now()
        om.machine.status = 'MAINT'
        om.machine.save(update_fields=['status'])
        om.save()
        messages.success(request, f"Intervention OM-{om.numero_om} démarrée !")
    return redirect('om_detail', om_id=om_id)


@login_required
def om_cloturer(request, om_id):
    om = get_object_or_404(OrdreMaintenance, id=om_id)
    form = ClotureOrdreMaintenanceForm(request.POST or None, request.FILES or None, instance=om)
    if request.method == 'POST' and form.is_valid():
        om = form.save(commit=False)
        om.cloturer()
        if om.plan_preventif:
            om.plan_preventif.marquer_executee()
        messages.success(request, f"OM-{om.numero_om} clôturé !")
        return redirect('om_detail', om_id=om.id)
    return render(request, 'maintenance/om_cloturer.html', {'form': form, 'om': om, 'titre': f'Clôturer OM-{om.numero_om}'})


@login_required
def om_ajouter_piece(request, om_id):
    om = get_object_or_404(OrdreMaintenance, id=om_id)
    form = ConsommationPieceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cp = form.save(commit=False)
        cp.ordre_maintenance = om
        cp.save()
        messages.success(request, f"Pièce ajoutée à OM-{om.numero_om}")
        return redirect('om_detail', om_id=om.id)
    return render(request, 'maintenance/om_piece_form.html', {'form': form, 'om': om, 'titre': f'Ajouter pièce — OM-{om.numero_om}'})


# ===========================================================================
# --- PLANS PRÉVENTIFS ---
# ===========================================================================

@login_required
def plan_preventif_list(request):
    m_f = request.GET.get('machine', '')
    s_f = request.GET.get('statut', 'ACTIF')
    plans = PlanMaintenancePreventive.objects.select_related('machine', 'technicien_defaut').order_by('machine', 'titre')
    if m_f:
        plans = plans.filter(machine_id=m_f)
    if s_f:
        plans = plans.filter(statut=s_f)
    
    return render(request, 'maintenance/plan_preventif_list.html', {
        'plans': plans,
        'plans_a_faire': [p for p in plans if p.est_a_faire],
        'plans_en_retard': [p for p in plans if p.est_en_retard],
        'machines': Machine.objects.filter(est_active=True),
        'selected_machine': m_f,
        'selected_statut': s_f,
    })


@login_required
def plan_preventif_create(request):
    form = PlanMaintenancePreventiveForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        plan = form.save()
        if plan.type_frequence == 'TEMPS' and plan.frequence_jours:
            plan.prochaine_execution = timezone.now() + timedelta(days=plan.frequence_jours)
            plan.save()
        messages.success(request, f"Plan préventif créé : {plan.titre}")
        return redirect('plan_preventif_list')
    return render(request, 'maintenance/plan_preventif_form.html', {'form': form, 'titre': 'Nouveau Plan Préventif'})


@login_required
def plan_preventif_detail(request, plan_id):
    plan = get_object_or_404(PlanMaintenancePreventive.objects.select_related('machine', 'technicien_defaut'), id=plan_id)
    return render(request, 'maintenance/plan_preventif_detail.html', {
        'plan': plan,
        'ordres': plan.ordres_generes.order_by('-date_creation')[:10]
    })


@login_required
def plan_preventif_generer_om(request, plan_id):
    if request.method == 'POST':
        om = get_object_or_404(PlanMaintenancePreventive, id=plan_id).generer_ordre(user=request.user)
        messages.success(request, f"OM-{om.numero_om} généré !")
        return redirect('om_detail', om_id=om.id)
    return redirect('plan_preventif_detail', plan_id=plan_id)


@login_required
def generer_om_preventifs_auto(request):
    if request.method == 'POST':
        plans = PlanMaintenancePreventive.objects.filter(statut='ACTIF')
        generes = 0
        for p in plans:
            if p.est_a_faire and not OrdreMaintenance.objects.filter(plan_preventif=p, statut__in=['OUVERT', 'EN_COURS']).exists():
                p.generer_ordre(user=request.user)
                generes += 1
        messages.success(request, f"✅ {generes} OM générés !" if generes else "Aucune action requise.")
    return redirect('plan_preventif_list')


# ===========================================================================
# --- PIÈCES DE RECHANGE ---
# ===========================================================================

@login_required
def piece_list(request):
    cat = request.GET.get('categorie', '')
    stock = request.GET.get('stock', '')
    q = request.GET.get('q', '')

    pieces = PieceRechange.objects.select_related('categorie', 'fournisseur').filter(est_active=True)
    if cat:
        pieces = pieces.filter(categorie_id=cat)
    if stock == 'bas':
        pieces = pieces.filter(quantite_stock__lte=F('stock_minimum'))
    elif stock == 'rupture':
        pieces = pieces.filter(quantite_stock__lte=0)
    if q:
        pieces = pieces.filter(Q(reference__icontains=q) | Q(designation__icontains=q) | Q(marque_piece__icontains=q))

    return render(request, 'maintenance/piece_list.html', {
        'pieces': pieces.order_by('designation'),
        'categories': CategoriePiece.objects.all(),
        'stats': {
            'total': pieces.count(),
            'stock_bas': sum(1 for p in pieces if p.est_stock_bas),
            'rupture': sum(1 for p in pieces if p.est_rupture),
            'valeur_totale': sum(p.valeur_stock for p in pieces)
        },
        'selected_categorie': cat,
        'selected_stock': stock,
        'search': q,
    })


@login_required
def piece_create(request):
    form = PieceRechangeForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        p = form.save()
        messages.success(request, f"Pièce {p.reference} créée !")
        return redirect('piece_list')
    return render(request, 'maintenance/piece_form.html', {'form': form, 'titre': 'Nouvelle Pièce'})


@login_required
def piece_detail(request, piece_id):
    p = get_object_or_404(PieceRechange.objects.select_related('categorie', 'fournisseur'), id=piece_id)
    return render(request, 'maintenance/piece_detail.html', {
        'piece': p,
        'mouvements': p.mouvements_piece.order_by('-date_mouvement')[:30],
        'machines': p.machines_compatibles.all(),
        'consommations': p.consommations_piece.select_related('ordre_maintenance', 'ordre_maintenance__machine').order_by('-date_consommation')[:20],
    })


@login_required
def piece_edit(request, piece_id):
    p = get_object_or_404(PieceRechange, id=piece_id)
    form = PieceRechangeForm(request.POST or None, request.FILES or None, instance=p)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"Pièce {p.reference} mise à jour !")
        return redirect('piece_detail', piece_id=p.id)
    return render(request, 'maintenance/piece_form.html', {'form': form, 'piece': p, 'titre': f'Modifier {p.reference}'})


@login_required
def piece_mouvement(request, piece_id):
    p = get_object_or_404(PieceRechange, id=piece_id)
    form = MouvementPieceForm(request.POST or None, initial={'piece': p})
    if request.method == 'POST' and form.is_valid():
        m = form.save(commit=False)
        m.piece = p
        m.utilisateur = request.user
        m.save()
        messages.success(request, "Mouvement enregistré.")
        return redirect('piece_detail', piece_id=p.id)
    return render(request, 'maintenance/mouvement_piece_form.html', {'form': form, 'piece': p, 'titre': f'Mouvement — {p.designation}'})


@login_required
def categorie_piece_list(request):
    form = CategoriePieceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Catégorie créée !")
        return redirect('categorie_piece_list')
    return render(request, 'maintenance/categorie_piece_list.html', {'categories': CategoriePiece.objects.all(), 'form': form})


# ===========================================================================
# --- ALERTES & KPIs ---
# ===========================================================================

@login_required
def alerte_list(request):
    n_f = request.GET.get('niveau', '')
    t_f = request.GET.get('type', '')
    tr_f = request.GET.get('traitee', '')

    alertes = AlerteMaintenance.objects.select_related('machine', 'piece', 'plan_preventif').order_by('-date_creation')
    if n_f:
        alertes = alertes.filter(niveau=n_f)
    if t_f:
        alertes = alertes.filter(type_alerte=t_f)
    if tr_f == '0':
        alertes = alertes.filter(est_traitee=False)
    elif tr_f == '1':
        alertes = alertes.filter(est_traitee=True)

    return render(request, 'maintenance/alerte_list.html', {
        'alertes': alertes[:100],
        'non_traitees': alertes.filter(est_traitee=False).count(),
        'critiques': alertes.filter(niveau='CRITICAL', est_traitee=False).count(),
        'niveau_choices': AlerteMaintenance.NIVEAU_CHOICES,
        'type_choices': AlerteMaintenance.TYPE_CHOICES,
        'selected_niveau': n_f,
        'selected_type': t_f,
        'selected_traitee': tr_f,
    })


@login_required
def alerte_traiter(request, alerte_id):
    if request.method == 'POST':
        a = get_object_or_404(AlerteMaintenance, id=alerte_id)
        a.est_traitee = True
        a.est_lue = True
        a.date_traitement = timezone.now()
        a.traite_par = request.user
        a.save()
        messages.success(request, "Alerte traitée !")
    return redirect('alerte_list')


@login_required
def generer_alertes(request):
    if request.method == 'POST':
        nb = 0
        for p in PieceRechange.objects.filter(est_active=True):
            if p.est_rupture and not AlerteMaintenance.objects.filter(type_alerte='STOCK_PIECE_RUPTURE', piece=p, est_traitee=False).exists():
                AlerteMaintenance.objects.create(
                    type_alerte='STOCK_PIECE_RUPTURE',
                    niveau='CRITICAL',
                    titre=f"🔴 Rupture stock — {p.designation}",
                    message=f"Pièce {p.reference} en rupture.",
                    piece=p
                )
                nb += 1
            elif p.est_stock_bas and not AlerteMaintenance.objects.filter(type_alerte='STOCK_PIECE_BAS', piece=p, est_traitee=False).exists():
                AlerteMaintenance.objects.create(
                    type_alerte='STOCK_PIECE_BAS',
                    niveau='WARNING',
                    titre=f"⚠️ Stock bas — {p.designation}",
                    message=f"Pièce {p.reference} sous le seuil.",
                    piece=p
                )
                nb += 1

        for plan in PlanMaintenancePreventive.objects.filter(statut='ACTIF'):
            if plan.est_a_faire and not AlerteMaintenance.objects.filter(type_alerte='PREVENTIVE_DUE', plan_preventif=plan, est_traitee=False).exists():
                AlerteMaintenance.objects.create(
                    type_alerte='PREVENTIVE_DUE',
                    niveau='WARNING' if not plan.est_en_retard else 'CRITICAL',
                    titre=f"🔧 Maintenance à faire — {plan.machine.name}",
                    message=f"Plan : {plan.titre}",
                    machine=plan.machine,
                    plan_preventif=plan
                )
                nb += 1

        for om in OrdreMaintenance.objects.filter(statut__in=['OUVERT', 'EN_COURS']):
            if om.est_en_retard and not AlerteMaintenance.objects.filter(type_alerte='OM_EN_RETARD', machine=om.machine, est_traitee=False).exists():
                AlerteMaintenance.objects.create(
                    type_alerte='OM_EN_RETARD',
                    niveau='CRITICAL',
                    titre=f"⏰ OM en retard — {om.numero_om}",
                    message=f"OM-{om.numero_om} est en retard.",
                    machine=om.machine
                )
                nb += 1
        messages.success(request, f"✅ {nb} alertes générées !")
    return redirect('alerte_list')


@login_required
def maintenance_kpi(request):
    kpis = [{
        'machine': m,
        'mtbf': m.mtbf,
        'mttr': m.mttr,
        'disponibilite': m.taux_disponibilite,
        'pannes_total': m.nb_pannes_total,
        'pannes_mois': m.nb_pannes_mois,
        'temps_arret': m.temps_arret_total_heures,
    } for m in Machine.objects.filter(est_active=True).select_related('atelier')]
    
    kpis.sort(key=lambda x: x['disponibilite'])
    return render(request, 'maintenance/kpi.html', {
        'kpis': kpis,
        'total_pannes': sum(k['pannes_total'] for k in kpis),
        'dispo_moyenne': round(sum(k['disponibilite'] for k in kpis) / max(len(kpis), 1), 1),
        'machines_labels': json.dumps([k['machine'].name for k in kpis[:10]]),
        'machines_dispo': json.dumps([k['disponibilite'] for k in kpis[:10]]),
        'machines_pannes': json.dumps([k['pannes_total'] for k in kpis[:10]]),
    })


@login_required
def maintenance_stats_api(request):
    return JsonResponse({
        'machines_panne': Machine.objects.filter(status='PANNE', est_active=True).count(),
        'om_ouverts': OrdreMaintenance.objects.filter(statut__in=['OUVERT', 'EN_COURS']).count(),
        'alertes_non_lues': AlerteMaintenance.objects.filter(est_traitee=False).count(),
        'pieces_stock_bas': PieceRechange.objects.filter(est_active=True, quantite_stock__lte=F('stock_minimum')).count(),
    })


@login_required
def maintenance_calendrier(request):
    m = int(request.GET.get('mois', timezone.now().month))
    y = int(request.GET.get('annee', timezone.now().year))
    evts, seen = [], set()

    oms = OrdreMaintenance.objects.select_related('machine', 'technicien_principal').filter(
        Q(date_creation__month=m, date_creation__year=y) | Q(date_planifiee__month=m, date_planifiee__year=y)
    ).exclude(statut='ANNULE')

    for om in oms:
        if om.id in seen:
            continue
        d_ref = om.date_planifiee if om.date_planifiee else om.date_creation
        evts.append({
            'id': om.id,
            'date': d_ref.strftime('%Y-%m-%d') if d_ref else '',
            'titre': om.titre[:30],
            'type': om.type_maintenance,
            'machine': om.machine.name if om.machine else '—',
            'machine_id': om.machine.id if om.machine else 0,
            'technicien': om.technicien_principal.nom.split()[0] if om.technicien_principal else '',
            'priorite': om.priorite,
            'statut': om.get_statut_display(),
            'url': f'/maintenance/om/{om.id}/',
            'heure': d_ref.strftime('%H:%M') if d_ref else '',
            'couleur': {
                'CORRECTIVE': 'bg-red-200 text-red-900',
                'PREVENTIVE': 'bg-blue-200 text-blue-900',
                'PREDICTIVE': 'bg-purple-200 text-purple-900',
                'AMELIORATIVE': 'bg-green-200 text-green-900'
            }.get(om.type_maintenance, 'bg-gray-200 text-gray-900'),
            'is_plan': False,
        })
        seen.add(om.id)

    for p in PlanMaintenancePreventive.objects.select_related('machine', 'technicien_defaut').filter(statut='ACTIF'):
        d_prev = None
        if p.prochaine_execution and p.prochaine_execution.month == m and p.prochaine_execution.year == y:
            d_prev = p.prochaine_execution
        elif p.derniere_execution and p.frequence_jours:
            futur = p.derniere_execution + timedelta(days=p.frequence_jours)
            if futur.month == m and futur.year == y:
                d_prev = futur
            
        if d_prev:
            evts.append({
                'id': p.id,
                'date': d_prev.strftime('%Y-%m-%d'),
                'titre': p.titre[:30],
                'type': 'PLAN',
                'machine': p.machine.name if p.machine else '—',
                'machine_id': p.machine.id if p.machine else 0,
                'technicien': p.technicien_defaut.nom.split()[0] if p.technicien_defaut else '',
                'priorite': p.priorite,
                'statut': 'Planifié',
                'url': f'/maintenance/preventif/{p.id}/',
                'heure': '',
                'couleur': 'bg-yellow-200 text-yellow-900',
                'is_plan': True,
            })

    return render(request, 'maintenance/calendrier.html', {
        'evenements': evts,
        'jours_semaine': ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'],
        'mois_courant': m,
        'annee_courante': y
    })