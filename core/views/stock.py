import json
import openpyxl
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.db.models import Sum, Q, F
from django.utils import timezone

from ..models import (
    Material, Supplier, ConsommationEncre, StockLocation, StockLot, StockMovement,
    DemandeAchat, BonCommande, LigneBonCommande, StockSeuil, Client, Machine, ProductionOrder
)
from ..forms import MaterialForm, SupplierForm, ConsommationEncreForm
from .helpers import highlight_search

# ===========================================================================
# --- STOCKS ---
# ===========================================================================

@login_required
def stock_view(request):
    materials = Material.objects.all()
    suppliers = Supplier.objects.all()
    consos = ConsommationEncre.objects.all().order_by('-date')
    return render(request, 'stock_list.html', {
        'materials': materials,
        'suppliers': suppliers,
        'consos': consos
    })


@login_required
def add_material(request):
    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Matière ajoutée avec succès !')
            return redirect('stock_advanced')
    else:
        form = MaterialForm()
    suppliers = Supplier.objects.all()
    return render(request, 'stock/material_form.html', {
        'form': form, 'suppliers': suppliers,
        'title': 'Nouvelle Matière Première', 'btn_label': 'Ajouter la Matière',
    })


@login_required
def edit_material(request, id):
    material = get_object_or_404(Material, id=id)
    if request.method == 'POST':
        form = MaterialForm(request.POST, instance=material)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ Matière "{material.name}" modifiée !')
            return redirect('stock_advanced')
    else:
        form = MaterialForm(instance=material)
    suppliers = Supplier.objects.all()
    return render(request, 'stock/material_form.html', {
        'form': form, 'material': material, 'suppliers': suppliers,
        'title': f'Modifier : {material.name}', 'btn_label': 'Enregistrer les modifications',
    })


@login_required
def delete_material(request, id):
    material = get_object_or_404(Material, id=id)
    if request.method == 'POST':
        nom = material.name
        material.delete()
        messages.success(request, f'🗑️ Matière "{nom}" supprimée.')
    return redirect('stock_advanced')


@login_required
def clear_all_stock(request):
    if request.method == 'POST':
        StockMovement.objects.all().delete()
        StockLot.objects.all().delete()
        count, _ = Material.objects.all().delete()
        messages.success(request, f"⚠️ Tout le stock a été vidé ({count} matières supprimées).")
    return redirect('stock_advanced')


@login_required
def add_supplier(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Fournisseur ajouté avec succès !')
            return redirect('stock_advanced')
    else:
        form = SupplierForm()
    return render(request, 'stock/supplier_form.html', {
        'form': form, 'title': 'Nouveau Fournisseur', 'btn_label': 'Ajouter le Fournisseur',
    })


@login_required
def edit_supplier(request, id):
    supplier = get_object_or_404(Supplier, id=id)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ Fournisseur "{supplier.name}" modifié !')
            return redirect('stock_advanced')
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'stock/supplier_form.html', {
        'form': form, 'supplier': supplier,
        'title': f'Modifier : {supplier.name}', 'btn_label': 'Enregistrer les modifications',
    })


@login_required
def delete_supplier(request, id):
    supplier = get_object_or_404(Supplier, id=id)
    if request.method == 'POST':
        nom = supplier.name
        supplier.delete()
        messages.success(request, f'🗑️ Fournisseur "{nom}" supprimé.')
    return redirect('stock_advanced')


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
# --- STOCK AVANCÉ AVEC RECHERCHE INTELLIGENTE ---
# ===========================================================================

@login_required
def stock_advanced_view(request):
    search_query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '')
    low_stock_only = request.GET.get('low_stock', '') == 'on'
    supplier_filter = request.GET.get('supplier', '')

    materials = Material.objects.select_related('supplier').all()

    if search_query:
        materials = materials.filter(
            Q(name__icontains=search_query) |
            Q(supplier__name__icontains=search_query)
        )
    if category_filter:
        materials = materials.filter(category=category_filter)
    if supplier_filter:
        materials = materials.filter(supplier_id=supplier_filter)

    materials = materials.order_by('name')

    if low_stock_only:
        materials = [m for m in materials if m.is_low_stock()]

    all_materials = Material.objects.select_related('supplier').all()
    alertes_stock = []
    nb_ruptures = 0
    nb_critiques = 0
    nb_alertes_simples = 0

    cat_stats = {
        'FILM': {'rupture': 0, 'critique': 0, 'alerte': 0},
        'INK': {'rupture': 0, 'critique': 0, 'alerte': 0},
        'GLUE': {'rupture': 0, 'critique': 0, 'alerte': 0},
        'SOLV': {'rupture': 0, 'critique': 0, 'alerte': 0},
    }

    for m in all_materials:
        if m.is_low_stock():
            pct = round((m.quantity / m.min_threshold) * 100, 1) if m.min_threshold > 0 else 0
            if m.quantity <= 0:
                niveau = 'RUPTURE'
                icone = '🔴'
                nb_ruptures += 1
                if m.category in cat_stats:
                    cat_stats[m.category]['rupture'] += 1
            elif pct < 50:
                niveau = 'CRITIQUE'
                icone = '🟠'
                nb_critiques += 1
                if m.category in cat_stats:
                    cat_stats[m.category]['critique'] += 1
            else:
                niveau = 'ALERTE'
                icone = '🟡'
                nb_alertes_simples += 1
                if m.category in cat_stats:
                    cat_stats[m.category]['alerte'] += 1

            alertes_stock.append({
                'id': m.id, 'name': m.name, 'category': m.category,
                'cat_label': m.get_category_display(), 'quantity': m.quantity,
                'unit': m.unit, 'min_threshold': m.min_threshold,
                'supplier': m.supplier.name if m.supplier else '—',
                'pct': min(pct, 100), 'niveau': niveau, 'icone': icone,
            })

    ordre_priorite = {'RUPTURE': 0, 'CRITIQUE': 1, 'ALERTE': 2}
    alertes_stock.sort(key=lambda x: (ordre_priorite.get(x['niveau'], 3), -x['pct']))

    top_alertes = alertes_stock[:10]
    top_alertes_noms = [a['name'][:25] + '...' if len(a['name']) > 25 else a['name'] for a in top_alertes]
    top_alertes_stock = [a['quantity'] for a in top_alertes]
    top_alertes_seuil = [a['min_threshold'] for a in top_alertes]
    top_alertes_couleurs = []
    for a in top_alertes:
        if a['niveau'] == 'RUPTURE':
            top_alertes_couleurs.append('#dc2626')
        elif a['niveau'] == 'CRITIQUE':
            top_alertes_couleurs.append('#ea580c')
        else:
            top_alertes_couleurs.append('#ca8a04')

    cat_labels = ['Film/Papier', 'Encre', 'Colle', 'Solvant']
    cat_rupture = [cat_stats['FILM']['rupture'], cat_stats['INK']['rupture'], cat_stats['GLUE']['rupture'], cat_stats['SOLV']['rupture']]
    cat_critique = [cat_stats['FILM']['critique'], cat_stats['INK']['critique'], cat_stats['GLUE']['critique'], cat_stats['SOLV']['critique']]
    cat_alerte = [cat_stats['FILM']['alerte'], cat_stats['INK']['alerte'], cat_stats['GLUE']['alerte'], cat_stats['SOLV']['alerte']]

    previsions = []
    for m in all_materials:
        try:
            seuil = m.seuil_intelligent
            if seuil and seuil.consommation_journaliere_moy > 0:
                jours = seuil.jours_de_stock
                if jours <= 15:
                    previsions.append({
                        'material': m.name,
                        'stock_actuel': m.quantity,
                        'conso_jour': seuil.consommation_journaliere_moy,
                        'jours_restants': jours,
                        'date_rupture': seuil.date_rupture_prevue.strftime('%d/%m/%Y') if seuil.date_rupture_prevue else '—',
                        'critique': jours <= 7,
                    })
        except Exception:
            pass
    previsions.sort(key=lambda x: x['jours_restants'])

    lots = StockLot.objects.select_related('material', 'fournisseur', 'emplacement').order_by('-date_reception')[:100]
    lots_bloques = StockLot.objects.filter(statut='BLOQUE').count()
    lots_attente = StockLot.objects.filter(statut='EN_ATTENTE').count()

    mouvements = StockMovement.objects.select_related(
        'material', 'lot', 'emplacement_source', 'emplacement_destination', 'utilisateur', 'machine', 'of'
    ).order_by('-date')[:100]

    locations = StockLocation.objects.filter(is_active=True).order_by('type', 'name')
    suppliers = Supplier.objects.all().order_by('name')

    demandes = DemandeAchat.objects.select_related('material', 'demandeur', 'valideur').order_by('-date_creation')[:50]
    da_en_attente = DemandeAchat.objects.filter(statut='SOUMISE').count()

    bons_commande = BonCommande.objects.select_related('fournisseur', 'cree_par').order_by('-date_commande')[:50]
    consos = ConsommationEncre.objects.all().order_by('-date')[:50]
    valeur_stock_total = sum(float(m.quantity) * float(m.price_per_unit) for m in all_materials if m.price_per_unit)

    context = {
        'search_query': search_query, 'category_filter': category_filter,
        'low_stock_only': low_stock_only, 'supplier_filter': supplier_filter,
        'categories': Material.CAT_CHOICES, 'materials': materials,
        'total_matieres': Material.objects.count(), 'suppliers': suppliers,
        'alertes_stock': alertes_stock, 'nb_alertes': len(alertes_stock),
        'nb_ruptures': nb_ruptures, 'nb_critiques': nb_critiques,
        'nb_alertes_simples': nb_alertes_simples,
        'top_alertes_noms': json.dumps(top_alertes_noms),
        'top_alertes_stock': json.dumps(top_alertes_stock),
        'top_alertes_seuil': json.dumps(top_alertes_seuil),
        'top_alertes_couleurs': json.dumps(top_alertes_couleurs),
        'cat_labels_json': json.dumps(cat_labels),
        'cat_rupture_json': json.dumps(cat_rupture),
        'cat_critique_json': json.dumps(cat_critique),
        'cat_alerte_json': json.dumps(cat_alerte),
        'previsions': previsions[:6],
        'lots': lots, 'lots_bloques': lots_bloques, 'lots_attente': lots_attente,
        'mouvements': mouvements, 'locations': locations,
        'demandes': demandes, 'da_en_attente': da_en_attente,
        'bons_commande': bons_commande, 'consos': consos,
        'valeur_stock_total': valeur_stock_total,
    }
    return render(request, 'stock/stock_advanced.html', context)


@login_required
def material_search_api(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 1:
        return JsonResponse([], safe=False)

    materials = Material.objects.filter(
        Q(name__icontains=query) | Q(category__icontains=query) | Q(supplier__name__icontains=query)
    ).select_related('supplier').order_by('name')[:30]

    results = []
    for m in materials:
        results.append({
            'id': m.id, 'name': m.name,
            'name_html': highlight_search(m.name, query),
            'category': m.get_category_display(),
            'quantity': m.quantity, 'unit': m.unit,
            'min_threshold': m.min_threshold,
            'supplier': m.supplier.name if m.supplier else '—',
            'is_low_stock': m.is_low_stock(),
            'price': float(m.price_per_unit) if m.price_per_unit else 0,
        })
    return JsonResponse({'query': query, 'count': len(results), 'results': results})


@login_required
def export_search_results(request):
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '')
    materials = Material.objects.select_related('supplier').all()

    if query:
        materials = materials.filter(Q(name__icontains=query) | Q(supplier__name__icontains=query))
    if category:
        materials = materials.filter(category=category)
    materials = materials.order_by('name')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Stock Matières"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1e3a5f", end_color="1e3a5f", fill_type="solid")
    alert_fill = PatternFill(start_color="fee2e2", end_color="fee2e2", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    headers = ['Désignation', 'Catégorie', 'Stock Actuel', 'Unité', 'Seuil Min', 'Fournisseur', 'Prix/Unité', 'Valeur Stock', 'État']
    ws.append(headers)

    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = thin_border

    for row_num, m in enumerate(materials, 2):
        valeur = float(m.quantity) * float(m.price_per_unit) if m.price_per_unit else 0
        etat = "⚠️ ALERTE" if m.is_low_stock() else "✓ OK"
        row_data = [
            m.name, m.get_category_display(), m.quantity, m.unit,
            m.min_threshold, m.supplier.name if m.supplier else '',
            float(m.price_per_unit) if m.price_per_unit else 0,
            round(valeur, 2), etat
        ]
        ws.append(row_data)
        for col_num in range(1, len(row_data) + 1):
            cell = ws.cell(row=row_num, column=col_num)
            cell.border = thin_border
            if m.is_low_stock():
                cell.fill = alert_fill

    column_widths = [40, 15, 15, 10, 12, 25, 12, 15, 12]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width

    filename = f"stock_matieres_{query if query else 'all'}.xlsx"
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


# ===========================================================================
# --- STOCK AVANCÉ (SUITE) ---
# ===========================================================================

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
                    type='ENTREE', material=material, lot=lot,
                    quantite=quantite, emplacement_destination=emplacement,
                    utilisateur=request.user, motif=f"Réception lot {numero_lot}"
                )
            messages.success(request, f"Lot {numero_lot} créé.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
    return redirect('stock_advanced')


@login_required
def lot_valider(request, id):
    author_lot = get_object_or_404(StockLot, id=id)
    if request.method == 'POST':
        ancien_statut = author_lot.statut
        author_lot.statut = 'CONFORME'
        author_lot.save()
        if ancien_statut != 'CONFORME':
            StockMovement.objects.create(
                type='ENTREE', material=author_lot.material, lot=author_lot,
                quantite=author_lot.quantite_restante,
                emplacement_destination=author_lot.emplacement,
                utilisateur=request.user, motif=f"Validation lot {author_lot.numero_lot}"
            )
        messages.success(request, f"Lot {author_lot.numero_lot} validé.")
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
                type=type_mvt, material=material, lot=lot,
                quantite=quantite, emplacement_source=src,
                emplacement_destination=dst, of=of_obj,
                machine=machine_obj, utilisateur=request.user, motif=motif,
            )
            messages.success(request, "Mouvement enregistré.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
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
            messages.success(request, "Demande d'achat créée.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
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
                    LigneBonCommande.objects.create(
                        bon_commande=bc, material=mat,
                        quantite_commandee=qte, prix_unitaire=prix
                    )
                    total += qte * prix
                idx += 1
            bc.montant_total = total
            bc.save()
            messages.success(request, f"Bon de commande {bc.reference} créé.")
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")
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
                date_reception=timezone.now().date(),
                fournisseur=bc.fournisseur,
                quantite_initiale=ligne.quantite_commandee,
                quantite_restante=ligne.quantite_commandee,
                prix_unitaire=ligne.prix_unitaire,
                statut='EN_ATTENTE', created_by=request.user,
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
    critiques = []
    for m in Material.objects.all():
        if m.is_low_stock():
            critiques.append({'name': m.name, 'stock': m.quantity, 'seuil': m.min_threshold})
    return JsonResponse({'critiques': critiques})