import datetime
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.utils import timezone

from ..models import (
    Client, Quote, Opportunite, ProductionOrder, Machine,
    OrdreFabrication, SemiProduit, OrdreMaintenance, AlerteMaintenance, Material,
    ProductionEntry, EtapeProduction, ConsumptionLog
)

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
        'low_stock_count': len([m for m in Material.objects.all() if m.is_low_stock()]),
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
    # 1. Récupération de toutes les machines d'usine (hors nettoyage)
    machines = Machine.objects.exclude(name__icontains="Nettoyage").order_by('atelier', 'name')
    
    # 2. Gestion du filtre par semaine (Format HTML5 "YYYY-Www" ex: "2024-W35")
    week_filter = request.GET.get('week', '')
    
    # Par défaut, on affiche la semaine en cours si aucun filtre n'est appliqué
    if not week_filter:
        now = datetime.date.today()
        year, week, _ = now.isocalendar()
        week_filter = f"{year}-W{week:02d}"
        
    try:
        year_str, week_str = week_filter.split('-W')
        iso_year = int(year_str)
        iso_week = int(week_str)
    except ValueError:
        now = datetime.date.today()
        iso_year, iso_week, _ = now.isocalendar()
        week_filter = f"{iso_year}-W{iso_week:02d}"

    # 3. Filtrage des Saisies de Production Spéciale par SEMAINE
    entries_qs = ProductionEntry.objects.filter(
        date__iso_year=iso_year, 
        date__week=iso_week
    ).select_related('machine', 'client')

    # 4. Filtrage des Étapes d'OFs par SEMAINE
    etapes_qs = EtapeProduction.objects.filter(
        Q(date_debut_reel__iso_year=iso_year, date_debut_reel__week=iso_week) |
        Q(date_prevue_debut__iso_year=iso_year, date_prevue_debut__week=iso_week) |
        Q(
            of__date_creation__iso_year=iso_year, 
            of__date_creation__week=iso_week, 
            date_debut_reel__isnull=True, 
            date_prevue_debut__isnull=True
        )
    ).select_related('machine', 'of', 'of__client')

    # 5. Construction de la structure de données Gantt unifiée par Machine
    machine_gantt = []
    total_jobs_count = 0
    total_en_cours_count = 0

    for m in machines:
        m_items = []
        
        # A. Injection des saisies de Production Spéciale
        m_entries = entries_qs.filter(machine=m).order_by('date', 'heure_debut')
        for e in m_entries:
            total_jobs_count += 1
            is_today = (e.date == datetime.date.today())
            if is_today:
                total_en_cours_count += 1

            m_items.append({
                'id': f"entry_{e.id}",
                'title': e.produit,
                'client_name': e.client.name if e.client else "Client non spécifié",
                'lot_or_of': f"Lot : {e.lot}" if e.lot else f"JOB-{e.id}",
                'type_process': e.get_type_process_display() if hasattr(e, 'get_type_process_display') else str(e.type_process),
                'date': e.date,
                'heure_debut': e.heure_debut,
                'heure_fin': e.heure_fin,
                'quantite_str': f"{e.prod_kg or e.quantite_lancee} kg / {e.prod_ml} ML",
                'source_type': 'SAISIE_DIRECTE',
                'status': 'IN_PROGRESS' if is_today else 'DONE',
                'status_label': 'Production Directe' if is_today else 'Terminé',
                'badge_color': 'emerald' if is_today else 'blue',
                'duree_str': e.temps_ouverture,
                'is_of': False,
            })
            
        # B. Injection des Étapes d'Ordres de Fabrication
        m_etapes = etapes_qs.filter(machine=m)
        m_etapes = sorted(m_etapes, key=lambda x: x.date_debut_reel or x.date_prevue_debut or x.of.date_creation)
        
        for et in m_etapes:
            total_jobs_count += 1
            if et.statut == 'EN_COURS':
                total_en_cours_count += 1

            dt_start = et.date_debut_reel or et.date_prevue_debut
            dt_end = et.date_fin_reel or et.date_prevue_fin

            m_items.append({
                'id': f"etape_{et.id}",
                'title': f"OF #{et.of.numero_of} - {et.nom_etape or (et.process_type.nom if et.process_type else 'Étape')}",
                'client_name': et.of.client.name if et.of.client else "",
                'lot_or_of': f"OF #{et.of.numero_of}",
                'type_process': et.process_type.nom if et.process_type else "Process",
                'date': dt_start.date() if dt_start else et.of.date_creation.date(),
                'heure_debut': dt_start.time() if dt_start else None,
                'heure_fin': dt_end.time() if dt_end else None,
                'quantite_str': f"{et.quantite_sortie or et.quantite_entree} kg",
                'source_type': 'OF_ETAPE',
                'status': et.statut,
                'status_label': et.get_statut_display(),
                'badge_color': 'amber' if et.statut == 'EN_COURS' else ('purple' if et.statut == 'TERMINE' else 'cyan'),
                'duree_str': f"{et.temps_arret_minutes} min",
                'is_of': True,
            })

        # Trier les items combinés par date et heure
        m_items = sorted(m_items, key=lambda x: (x['date'], x['heure_debut'] or datetime.time.min))

        machine_gantt.append({
            'machine': m,
            'items': m_items,
            'count': len(m_items)
        })

    context = {
        'machine_gantt': machine_gantt,
        'selected_week': week_filter,
        'week_display': f"Semaine {iso_week} ({iso_year})",
        'total_jobs_count': total_jobs_count,
        'total_en_cours_count': total_en_cours_count,
        'total_machines_count': len(machines),
    }
    return render(request, 'production/planning_gantt.html', context)


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