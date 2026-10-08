# core/kpi/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg, Max, F, Q, FloatField
from django.db import connection

from core.models import (
    Client, CommandeClient, LigneCommandeClient, TechnicalProduct,
    FicheProductionJournaliere, ClientProductPrice, Material, Machine,
    OrdreFabrication, Opportunite, Tooling
)


@login_required
def kpi_dashboard(request):
    # --- 1. CLIENTS & VENTES ---
    clients_stats = Client.objects.aggregate(
        total=Count('id'),
        actifs=Count('id', filter=Q(status='ACTIVE')),
        vip=Count('id', filter=Q(status='VIP')),
        prospects=Count('id', filter=Q(status='PROSPECT'))
    )

    top_clients_commande = (
        CommandeClient.objects.filter(statut__in=['CONFIRMEE', 'EN_PRODUCTION', 'PRETE', 'LIVREE'])
        .exclude(statut='ANNULEE')
        .values('client__name', 'client__id', 'client__code_client')
        .annotate(
            nb_cmd=Count('id'),
            ca=Sum('montant_total')
        )
        .order_by('-ca')[:5]
    )

    # --- 2. PRODUITS TECHNIQUES (PRÉPRESSE / CRM) ---
    produits_tech = TechnicalProduct.objects.aggregate(
        total=Count('id')
    )

    top_produits_vendus = (
        LigneCommandeClient.objects
        .filter(commande__statut__in=['CONFIRMEE', 'EN_PRODUCTION', 'PRETE', 'LIVREE'])
        .exclude(commande__statut='ANNULEE')
        .values('produit__ref_internal', 'produit__name', 'produit__id')
        .annotate(
            qte_totale=Sum('quantite'),
            nb_lignes=Count('id'),
            ca_estime=Sum(
                F('quantite') * F('prix_unitaire'),
                output_field=FloatField()
            )
        )
        .order_by('-qte_totale')[:10]
    )

    # --- 3. STOCK & MATIÈRES ---
    stock_total = Material.objects.aggregate(
        total_items=Count('id'),
        total_qte=Sum('quantity')
    )

    # --- 4. PRODUCTION & DÉCHETS ---
    fiches_stats = FicheProductionJournaliere.objects.aggregate(
        total_fiches=Count('id'),
        dechet_moyen=Avg('total_dechets_kg')
    )

    produits_dechets = (
        FicheProductionJournaliere.objects
        .filter(type_fiche__in=['FLEXO', 'HELIO', 'EXTRUSION'])
        .values('designation_produit')
        .annotate(
            total_dechets=Sum('total_dechets_kg'),
            nb_fiches=Count('id'),
            duree_moyenne=Avg('t_fonctionnement_min')
        )
        .order_by('-total_dechets')[:8]
    )

    # --- 5. MACHINES & OUTILLAGE ---
    machines_stats = Machine.objects.aggregate(
        total=Count('id'),
        actives=Count('id', filter=Q(est_active=True))
    )

    # --- 6. OUTILLAGE PRÉPRESSE (Clichés & Cylindres) ---
    # Note : wear_percent est un @property, pas un champ SQL. On trie par current_impressions.
    tooling_stats = {
        'total': Tooling.objects.count(),
        'cylindres': Tooling.objects.filter(tool_type='CYL').count(),
        'cliches': Tooling.objects.filter(tool_type='CLICHE').count(),
    }

    top_tooling = (
        Tooling.objects.select_related('product')
        .order_by('-current_impressions')[:8]
    )

    # --- 7. OPPORTUNITÉS (PIPELINE) ---
    opportunites_stats = {
        'total': Opportunite.objects.count(),
        'gagnees': Opportunite.objects.filter(status='GAGNE').count(),
        'perdues': Opportunite.objects.filter(status='PERDU').count(),
    }

    # --- 8. KPI GÉNÉRAL (Chiffres rapides) ---
    ca_global = CommandeClient.objects.exclude(statut='ANNULEE').aggregate(s=Sum('montant_total'))['s'] or 0
    nb_commandes_global = CommandeClient.objects.exclude(statut='ANNULEE').count()

    context = {
        'clients_stats': clients_stats,
        'top_clients_commande': top_clients_commande,
        'produits_tech': produits_tech,
        'top_produits_vendus': top_produits_vendus,
        'stock_total': stock_total,
        'fiches_stats': fiches_stats,
        'produits_dechets': produits_dechets,
        'machines_stats': machines_stats,
        'opportunites_stats': opportunites_stats,
        'tooling_stats': tooling_stats,
        'top_tooling': top_tooling,
        'ca_global': ca_global,
        'nb_commandes_global': nb_commandes_global,
    }

    return render(request, 'kpi/dashboard.html', context)