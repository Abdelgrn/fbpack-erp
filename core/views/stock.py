import openpyxl
import json
import traceback
import os
import re
import unicodedata
import base64
import urllib.request
import urllib.error
from datetime import datetime, date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.db import models, transaction
from django.db.models import Sum, Q, F, Count
from django.db.models.functions import TruncDate, Coalesce
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.core.paginator import Paginator

from core.models import (
    Material, Supplier, SupplierContact, StockLocation, StockLot, StockMovement,
    DemandeAchat, BonCommande, LigneBonCommande, StockSeuil, Machine
)
try:
    from core.models import ConsommationEncre, ProductionOrder
except ImportError:
    pass
from core.forms import MaterialForm, SupplierForm
from core.forms.stock import MaterialCreateForm, MaterialEditForm
from core.models.stock import StockCatalogOption, StockPrintDocument, StockPrintDocumentLine
from core.services.stock_reservation import (
    lot_available_quantity_for_of, material_available_quantity,
    lot_reserved_quantity, consume_of_reservations, restore_of_reservation_consumption,
    release_reservations_for_manual_issue, restore_manual_issue_reservations,
)
from .helpers import highlight_search

import logging
import math
from urllib.parse import quote

from core.decorators import module_required
from .security_utils import (
    parse_date, parse_float, parse_int, rate_limited, safe_json,
    self_approval_blocked, validate_upload, xl_safe,
)

logger = logging.getLogger('security')

LOT_STATUTS = ('EN_ATTENTE', 'CONFORME', 'BLOQUE', 'QUARANTAINE')
CERTIFICATE_EXTENSIONS = frozenset({'pdf', 'png', 'jpg', 'jpeg'})
CERTIFICATE_MAX_BYTES = 10 * 1024 * 1024
IMPORT_EXTENSIONS = frozenset({'xlsx', 'xlsm'})
IMPORT_MAX_BYTES = 10 * 1024 * 1024
IMPORT_MAX_ROWS = 20000
LABEL_IMAGE_TYPES = frozenset({'image/jpeg', 'image/png', 'image/webp'})
LABEL_MAX_BYTES = 6 * 1024 * 1024
_ISO_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# ===========================================================================
# --- DROITS ET LOGIQUE DE SÉCURITÉ ---
# ===========================================================================

def can_manage_stock(user):
    return user.is_staff or user.groups.filter(name__in=['RESPONSABLE_STOCK', 'ADMIN']).exists()

def can_validate_purchase(user):
    return user.is_staff or user.groups.filter(name__in=['DIRECTION', 'ADMIN']).exists()


def _refuse_manage(request):
    messages.error(request, "Accès refusé.")
    return redirect('stock_advanced')


def _positive_float(value, label):
    number = parse_float(value)
    if number is None or number <= 0:
        raise ValueError(f"{label} invalide : une valeur positive est requise.")
    return number


def _non_negative_float(value, label):
    number = parse_float(value)
    if number is None or not math.isfinite(float(number)) or number < 0:
        raise ValueError(f"{label} invalide.")
    return number


def _signed_nonzero_float(value, label):
    number = parse_float(value)
    if number is None or not math.isfinite(float(number)) or number == 0:
        raise ValueError(f"{label} doit être un nombre positif ou négatif, différent de zéro.")
    return float(number)


def _document_characteristics(post_data, category):
    """Valide les mesures saisies pour une ligne de retour ou d’avarie."""
    weight = _non_negative_float(post_data.get('poids_kg'), 'Poids (kg)')
    units_value = None
    if category == 'FILM':
        units_raw = post_data.get('nombre_unites')
        parsed_units = parse_float(units_raw)
        try:
            units_value = float(parsed_units) if parsed_units is not None else float('nan')
        except (TypeError, ValueError, OverflowError):
            units_value = float('nan')
        if not math.isfinite(units_value) or units_value < 0 or not units_value.is_integer():
            raise ValueError('Le nombre d’unités doit être un entier positif ou nul pour Film/Papier.')
        units_value = int(units_value)
    laize = None
    micronage = None
    if category == 'FILM':
        raw_laize = (post_data.get('laize_mm') or '').strip()
        raw_micronage = (post_data.get('micronage') or '').strip()
        parsed_laize = _non_negative_float(raw_laize, 'Laize (mm)')
        parsed_micronage = _non_negative_float(raw_micronage, 'Micronage (µm)')
        if not parsed_laize.is_integer():
            raise ValueError('La laize doit être un nombre entier de millimètres.')
        if not parsed_micronage.is_integer():
            raise ValueError('Le micronage doit être un nombre entier de microns.')
        laize = int(parsed_laize)
        micronage = int(parsed_micronage)
    metrage = _non_negative_float(post_data.get('metrage'), 'Métrage (m)') if category == 'FILM' else None
    return {
        'laize_mm_snapshot': laize, 'micronage_snapshot': micronage,
        'metrage': metrage, 'poids_kg': weight, 'nombre_unites': units_value,
    }


def _clean_iso_date(value):
    """Date AAAA-MM-JJ valide, sinon '' (None et '' sont conservés tels quels)."""
    if not value:
        return value
    return value if _ISO_DATE.match(value) and parse_date(value) else ''


def _clean_int_str(value):
    if not value:
        return value
    return value if str(value).isdecimal() else ''


def _clean_ids(data):
    raw = data.getlist('ids') if hasattr(data, 'getlist') else data.get('ids', [])
    if not isinstance(raw, (list, tuple)):
        return []
    ids = []
    for value in raw[:1000]:
        number = parse_int(value, minimum=1)
        if number is not None:
            ids.append(number)
    return ids

# ===========================================================================
# --- VUE COMPATIBILITÉ HISTORIQUE STOCK_VIEW ---
# ===========================================================================

@login_required
def stock_view(request):
    """Redirection transparente ou affichage du module stock unifié."""
    return redirect('stock_advanced')

@login_required
@module_required('stock')
def clear_all_stock(request):
    if not request.user.is_superuser:
        messages.error(request, "Action réservée aux super-administrateurs.")
        return redirect('stock_advanced')
    if request.method == 'POST':
        try:
            with transaction.atomic():
                StockMovement.objects.all().delete()
                StockLot.objects.all().delete()
                count, _ = Material.objects.all().delete()
            logger.warning('stock_cleared user_id=%s deleted_rows=%s', request.user.id, count)
            messages.success(request, f"⚠️ Tout le stock a été vidé ({count} matières supprimées).")
        except Exception:
            logger.exception('stock_clear_failed')
            messages.error(request, "Erreur lors de la vidange. Détails dans les journaux du serveur.")
    return redirect('stock_advanced')

# ===========================================================================
# --- LOGIQUE TRANSACTIONNELLE SÉCURISÉE (SERVICES) ---
# ===========================================================================

class StockService:
    @staticmethod
    @transaction.atomic
    def enregistrer_mouvement(type_mvt, material, quantite, lot=None, src=None, dst=None, of=None, machine=None, user=None, motif="", laize_mm=None, micronage=None, metrage=None, poids_kg=None, nombre_unites=None):
        try:
            quantity_value = float(quantite)
            quantite_valide = math.isfinite(quantity_value) and (
                quantity_value != 0 if type_mvt == 'AJUSTEMENT' else quantity_value > 0
            )
        except (TypeError, ValueError):
            quantite_valide = False
        if not quantite_valide:
            if type_mvt == 'AJUSTEMENT':
                raise ValueError("La variation d’inventaire doit être différente de zéro.")
            raise ValueError("La quantité doit être strictement positive.")
        if type_mvt not in {code for code, _label in StockMovement.TYPE_CHOICES}:
            raise ValueError("Type de mouvement inconnu.")
        if type_mvt == 'SORTIE' and of is not None and of.statut in {'TERMINE', 'ANNULE'}:
            raise ValueError('Une sortie ne peut pas être liée à un OF terminé ou annulé.')

        # Verrou des lignes concernées : deux mouvements simultanés ne s'écrasent plus.
        Material.objects.select_for_update().filter(pk=material.pk).first()
        material.refresh_from_db(fields=['quantity'])
        if lot:
            StockLot.objects.select_for_update().filter(pk=lot.pk).first()
            lot.refresh_from_db(fields=['quantite_restante'])

        adjustment_lot_breakdown = []
        manual_sortie_lot_breakdown = []
        manual_unlinked_sortie = type_mvt == 'SORTIE' and of is None
        if type_mvt == 'AJUSTEMENT':
            if float(material.quantity or 0) + quantity_value < -0.0005:
                raise ValueError(
                    f"Cette correction ferait passer le stock de « {material.name} » sous zéro. "
                    f"Stock actuel : {float(material.quantity or 0):.3f} {material.unit}; variation demandée : {quantity_value:+.3f}."
                )
            if quantity_value < 0:
                remaining = abs(quantity_value)
                if lot:
                    candidates = [lot]
                else:
                    candidates = list(material.get_fefo_lots().select_for_update())
                for candidate_lot in candidates:
                    available = max(0.0, float(candidate_lot.quantite_restante or 0) - lot_reserved_quantity(candidate_lot.pk))
                    deduction = min(available, remaining)
                    if deduction > 0:
                        candidate_lot.quantite_restante = round(available - deduction, 3)
                        candidate_lot.save(update_fields=['quantite_restante'])
                        adjustment_lot_breakdown.append([candidate_lot.pk, deduction])
                        remaining = round(remaining - deduction, 3)
                    if remaining <= 0.0005:
                        break
                if remaining > 0.0005:
                    raise ValueError(
                        f"L’ajustement dépasserait le stock libre de {remaining:.3f} {material.unit}; "
                        "libérez d’abord les réservations OF concernées ou corrigez un autre lot."
                    )
                lot = None  # La ventilation complète est conservée dans notes pour permettre l’annulation.
            if quantity_value > 0 and lot is None:
                lot = StockLot.objects.create(
                    material=material,
                    numero_lot=f"AJUST-{material.code or material.pk}-{timezone.now():%Y%m%d-%H%M%S-%f}",
                    date_reception=timezone.localdate(), fournisseur=material.supplier,
                    emplacement=dst, quantite_initiale=quantity_value, quantite_restante=0,
                    prix_unitaire=material.price_per_unit, statut='CONFORME',
                    created_by=user, notes='Lot créé pour une correction positive d’inventaire.',
                )
        if type_mvt in ['SORTIE', 'PERTE', 'RETOUR']:
            if type_mvt == 'SORTIE' and float(material.quantity or 0) < float(quantite):
                raise ValueError(
                    f"Stock réel insuffisant pour « {material.name} » : "
                    f"{float(material.quantity or 0):.3f} {material.unit} disponible(s), "
                    f"{float(quantite):.3f} {material.unit} demandé(s)."
                )
            if lot and lot.quantite_restante < quantite:
                raise ValueError(
                    f"Le lot {lot.numero_lot} ne peut pas couvrir ce mouvement sortant : "
                    f"{float(lot.quantite_restante or 0):.3f} {material.unit} restant(s), "
                    f"{float(quantite):.3f} {material.unit} demandé(s)."
                )
            has_lotted_stock = StockLot.objects.filter(material=material, quantite_restante__gt=0).exists()
            if type_mvt != 'SORTIE' or lot or (manual_unlinked_sortie and has_lotted_stock):
                if material.usable_quantity < quantite:
                    raise ValueError(f"La matière n'a pas assez de stock utilisable et conforme (Disponible: {material.usable_quantity:.3f} {material.unit}).")
            # Les mouvements sans OF ne doivent pas consommer le stock réservé à d'autres OF.
            if type_mvt in {'SORTIE', 'PERTE', 'RETOUR'}:
                of_id = getattr(of, 'pk', None) if type_mvt == 'SORTIE' else None
                if lot:
                    available = lot_available_quantity_for_of(lot, of_id)
                else:
                    available = material_available_quantity(material, of_id)
                    # Compatibilité des stocks historiques sans lots : aucune réservation par lot n'y est possible.
                    if not StockLot.objects.filter(material=material, quantite_restante__gt=0).exists():
                        available = float(material.usable_quantity or 0)
                if not manual_unlinked_sortie and float(quantite) > available + 1e-6:
                    raise ValueError(
                        f"Stock libre insuffisant pour « {material.name} » : {available:.3f} {material.unit} "
                        "disponible(s) après protection des réservations OF."
                    )

        if manual_unlinked_sortie and lot is None:
            remaining = float(quantite)
            candidates = list(material.get_fefo_lots().select_for_update())
            for candidate in candidates:
                take = min(max(0.0, float(candidate.quantite_restante or 0)), remaining)
                if take > 1e-9:
                    candidate.quantite_restante = round(float(candidate.quantite_restante or 0) - take, 3)
                    candidate.save(update_fields=['quantite_restante'])
                    manual_sortie_lot_breakdown.append([candidate.pk, round(take, 3)])
                    remaining = round(remaining - take, 3)
                if remaining <= 1e-6:
                    break

        mvt = StockMovement.objects.create(
            type=type_mvt, material=material, lot=lot, quantite=quantite,
            emplacement_source=src, emplacement_destination=dst,
            of=of, machine=machine, utilisateur=user, motif=motif,
            laize_mm=laize_mm, micronage=micronage, metrage=metrage,
            poids_kg=poids_kg, nombre_unites=nombre_unites,
        )
        if adjustment_lot_breakdown:
            mvt.notes = 'AJUSTEMENT_LOTS:' + json.dumps(adjustment_lot_breakdown)
            mvt.save(update_fields=['notes'])
        if manual_sortie_lot_breakdown:
            mvt.notes = 'SORTIE_MANUELLE_LOTS:' + json.dumps(manual_sortie_lot_breakdown)
            mvt.save(update_fields=['notes'])
        if manual_unlinked_sortie:
            if lot is not None:
                release_reservations_for_manual_issue(lot, quantite, mvt.pk, user)
            else:
                for lot_id, amount in manual_sortie_lot_breakdown:
                    affected_lot = StockLot.objects.select_for_update().get(pk=lot_id)
                    release_reservations_for_manual_issue(affected_lot, amount, mvt.pk, user)

        if type_mvt in {'ENTREE', 'RETOUR_INTERNE'}:
            material.quantity = round(material.quantity + quantite, 3)
            if lot:
                lot.quantite_restante = round(lot.quantite_restante + quantite, 3)
        elif type_mvt in ['SORTIE', 'PERTE', 'RETOUR']:
            material.quantity = round(material.quantity - quantite, 3)
            if lot:
                lot.quantite_restante = round(lot.quantite_restante - quantite, 3)
        elif type_mvt == 'AJUSTEMENT':
            material.quantity = round(material.quantity + quantity_value, 3)
            if lot:
                lot.quantite_restante = round(lot.quantite_restante + quantity_value, 3)

        material.save()
        if lot:
            lot.save()
        if type_mvt == 'SORTIE' and of is not None:
            consume_of_reservations(of, material, quantite, user, lot=lot)
        return mvt

    @staticmethod
    @transaction.atomic
    def annuler_mouvement(mouvement, motif_annulation, user):
        # Verrou puis relecture : une annulation en double ne contre-passe plus deux fois.
        StockMovement.objects.select_for_update().filter(pk=mouvement.pk).first()
        Material.objects.select_for_update().filter(pk=mouvement.material_id).first()
        if mouvement.lot_id:
            StockLot.objects.select_for_update().filter(pk=mouvement.lot_id).first()
        mouvement.refresh_from_db()

        if mouvement.annule:
            raise ValueError("Ce mouvement est déjà annulé.")

        mouvement.annule = True
        mouvement.motif_annulation = motif_annulation
        mouvement.save()

        mat = mouvement.material
        lot = mouvement.lot
        qte = mouvement.quantite

        if mouvement.type in {'ENTREE', 'RETOUR_INTERNE'}:
            mat.quantity = round(mat.quantity - qte, 3)
            if lot:
                lot.quantite_restante = round(lot.quantite_restante - qte, 3)
        elif mouvement.type in ['SORTIE', 'PERTE', 'RETOUR']:
            mat.quantity = round(mat.quantity + qte, 3)
            if lot:
                lot.quantite_restante = round(lot.quantite_restante + qte, 3)
            elif mouvement.type == 'SORTIE' and mouvement.notes.startswith('SORTIE_MANUELLE_LOTS:'):
                try:
                    breakdown = json.loads(mouvement.notes.split(':', 1)[1])
                    for lot_id, amount in breakdown:
                        restored_lot = StockLot.objects.select_for_update().filter(pk=lot_id, material=mat).first()
                        if restored_lot:
                            restored_lot.quantite_restante = round(restored_lot.quantite_restante + float(amount), 3)
                            restored_lot.save(update_fields=['quantite_restante'])
                except (TypeError, ValueError, json.JSONDecodeError):
                    logger.exception('manual_sortie_lot_breakdown_restore_failed movement_id=%s', mouvement.pk)
        elif mouvement.type == 'AJUSTEMENT':
            mat.quantity = round(mat.quantity - qte, 3)
            if lot and qte > 0:
                lot.quantite_restante = round(lot.quantite_restante - qte, 3)
            elif qte < 0 and mouvement.notes.startswith('AJUSTEMENT_LOTS:'):
                try:
                    breakdown = json.loads(mouvement.notes.split(':', 1)[1])
                    for lot_id, amount in breakdown:
                        restored_lot = StockLot.objects.select_for_update().filter(pk=lot_id, material=mat).first()
                        if restored_lot:
                            restored_lot.quantite_restante = round(restored_lot.quantite_restante + float(amount), 3)
                            restored_lot.save(update_fields=['quantite_restante'])
                except (ValueError, TypeError, json.JSONDecodeError):
                    raise ValueError('Impossible de contre-passer la ventilation des lots de cet ajustement.')

        mat.save()
        if lot:
            lot.save()
        if mouvement.type == 'SORTIE' and mouvement.of_id is None:
            restore_manual_issue_reservations(mouvement.pk, user)
        if mouvement.type == 'SORTIE' and mouvement.of_id:
            restore_of_reservation_consumption(mouvement.of, mat, qte, user, lot=lot)


# ===========================================================================
# --- CONTROLE DE COHÉRENCE ---
# ===========================================================================

@login_required
@module_required('stock')
def controle_stock_view(request):
    materials = Material.objects.filter(is_archived=False)
    ecarts = []
    
    for m in materials:
        entrees = StockMovement.objects.filter(material=m, type__in=['ENTREE', 'RETOUR_INTERNE'], annule=False).aggregate(total=Sum('quantite'))['total'] or 0.0
        sorties = StockMovement.objects.filter(material=m, type__in=['SORTIE', 'PERTE', 'RETOUR'], annule=False).aggregate(total=Sum('quantite'))['total'] or 0.0
        ajustements = StockMovement.objects.filter(material=m, type='AJUSTEMENT', annule=False).aggregate(total=Sum('quantite'))['total'] or 0.0
        
        theorique_ledger = m.initial_quantity + entrees - sorties + ajustements
        somme_lots = m.lots.aggregate(total=Sum('quantite_restante'))['total'] or 0.0

        if abs(m.quantity - theorique_ledger) > 0.01 or abs(m.quantity - somme_lots) > 0.01:
            ecarts.append({
                'material': m,
                'stock_physique': m.quantity,
                'theorique_ledger': theorique_ledger,
                'somme_lots': somme_lots,
                'ecart': abs(m.quantity - somme_lots)
            })

    return render(request, 'stock/controle_stock.html', {'ecarts': ecarts})


@login_required
@module_required('stock')
def seuils_recalculer(request):
    if not can_manage_stock(request.user):
        messages.error(request, "Accès refusé.")
        return redirect('stock_advanced')

    materials = Material.objects.filter(is_archived=False)
    date_limite = timezone.now() - timezone.timedelta(days=30)
    recalculs = 0

    for m in materials:
        conso_totale = StockMovement.objects.filter(
            material=m, type='SORTIE', annule=False, date__gte=date_limite
        ).aggregate(total=Sum('quantite'))['total'] or 0.0
        
        conso_journaliere = round(conso_totale / 30.0, 2)
        
        seuil, _ = StockSeuil.objects.get_or_create(material=m)
        seuil.consommation_journaliere_moy = conso_journaliere
        seuil.save()
        recalculs += 1

    messages.success(request, f"🔮 Recalcul automatique terminé pour {recalculs} matière(s) sur les 30 derniers jours de production.")
    return redirect('stock_advanced')


# ===========================================================================
# --- VUES DES MATIÈRES PREMIÈRES (CRUD & ARCHIVE) ---
# ===========================================================================

@login_required
@module_required('stock')
def stock_advanced_view(request):
    try:
        tab = request.GET.get('tab', 'matieres')
        sub = request.GET.get('sub', 'da')
        search_query = request.GET.get('q', '').strip()
        category_filter = request.GET.get('category', '')
        low_stock_only = request.GET.get('low_stock', '') == 'on'
        supplier_filter = request.GET.get('supplier', '')
        depot_filter = _clean_int_str(request.GET.get('depot', ''))
        family_filter = _clean_int_str(request.GET.get('family', ''))
        subfamily_filter = _clean_int_str(request.GET.get('subfamily', ''))
        micronage_filter = _clean_int_str(request.GET.get('micronage', ''))
        laize_filter = _clean_int_str(request.GET.get('laize', ''))
        origin_filter = request.GET.get('origin', '') if request.GET.get('origin', '') in {'IMPORTATION', 'LOCAL'} else ''
        grammage_raw = request.GET.get('grammage', '').strip()
        try:
            grammage_filter = float(grammage_raw.replace(',', '.')) if grammage_raw else ''
        except (TypeError, ValueError):
            grammage_filter = ''
        sort_by = request.GET.get('sort', 'alert')
        archives = request.GET.get('archives', '') == '1'

        peut_gerer = can_manage_stock(request.user)
        peut_valider = can_validate_purchase(request.user)

        materials_list = Material.objects.select_related('supplier', 'depot', 'famille', 'sous_famille').filter(is_archived=archives).annotate(usable_quantity_cached=Coalesce(Sum('lots__quantite_restante', filter=Q(lots__statut='CONFORME')), 0.0))

        if search_query:
            # Tous les mots doivent être présents, mais peuvent se trouver n’importe où
            # dans le code, la désignation ou le fournisseur (ex. « BOPP 1070 »).
            for search_term in search_query.split():
                materials_list = materials_list.filter(
                    Q(name__icontains=search_term) |
                    Q(code__icontains=search_term) |
                    Q(supplier__name__icontains=search_term)
                )
        if category_filter:
            materials_list = materials_list.filter(category=category_filter)
        if supplier_filter:
            materials_list = materials_list.filter(supplier_id=supplier_filter)
        if depot_filter:
            materials_list = materials_list.filter(depot_id=depot_filter)
        if family_filter:
            materials_list = materials_list.filter(famille_id=family_filter)
        if subfamily_filter:
            materials_list = materials_list.filter(sous_famille_id=subfamily_filter)
        if micronage_filter:
            materials_list = materials_list.filter(micronage_standard=micronage_filter)
        if grammage_filter != '':
            materials_list = materials_list.filter(grammage=grammage_filter)
        if laize_filter:
            materials_list = materials_list.filter(laize_mm=laize_filter)
        if origin_filter:
            materials_list = materials_list.filter(origine=origin_filter)
        if low_stock_only:
            materials_list = materials_list.filter(quantity__lte=F('min_threshold'))

        if sort_by in {'name', 'name_asc'}:
            materials_list = materials_list.order_by('name', 'id')
        elif sort_by == 'name_desc':
            materials_list = materials_list.order_by('-name', 'id')
        elif sort_by == 'stock_asc':
            materials_list = materials_list.order_by('quantity', 'name')
        elif sort_by == 'stock_desc':
            materials_list = materials_list.order_by('-quantity', 'name')
        elif sort_by == 'price_asc':
            materials_list = materials_list.order_by('price_per_unit', 'name')
        elif sort_by == 'price_desc':
            materials_list = materials_list.order_by('-price_per_unit', 'name')
        elif sort_by == 'date_asc':
            materials_list = materials_list.order_by('created_at', 'id')
        elif sort_by == 'date_desc':
            materials_list = materials_list.order_by('-created_at', '-id')
        else:
            # Le tri « alertes en premier » reste en SQL au lieu de charger toute la liste en Python.
            materials_list = materials_list.order_by(
                models.Case(
                    models.When(quantity__lte=F('min_threshold'), then=models.Value(0)),
                    default=models.Value(1), output_field=models.IntegerField(),
                ),
                'quantity', 'name',
            )

        paginator_mat = Paginator(materials_list, 20)
        page_mat_num = request.GET.get('page_mat', 1)
        materials_page = paginator_mat.get_page(page_mat_num)

        all_active_materials = Material.objects.filter(is_archived=False).select_related('supplier', 'seuil_intelligent').annotate(usable_quantity_cached=Coalesce(Sum('lots__quantite_restante', filter=Q(lots__statut='CONFORME')), 0.0))
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

        for m in all_active_materials:
            if float(m.quantity or 0) <= float(m.min_threshold or 0):
                qty = float(m.quantity or 0)
                thresh = m.min_threshold
                pct = round((qty / thresh) * 100, 1) if thresh > 0 else 0

                if qty <= 0:
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
                    'cat_label': m.get_category_display(), 'quantity': qty, 'unit': m.unit,
                    'min_threshold': thresh, 'supplier': m.supplier.name if m.supplier else '—',
                    'pct': min(pct, 100), 'niveau': niveau, 'icone': icone,
                    'suggestion': max(0.0, (thresh * 2) - qty)
                })

        alertes_stock.sort(key=lambda x: (0 if x['niveau'] == 'RUPTURE' else (1 if x['niveau'] == 'CRITIQUE' else 2), -x['pct']))

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

        lots_peremption = StockLot.objects.filter(
            quantite_restante__gt=0, date_expiration__isnull=False,
            date_expiration__lte=timezone.localdate() + timedelta(days=30),
        ).select_related('material').order_by('date_expiration')

        # Les réceptions initiales/achats restent enregistrées en base et dans l'historique,
        # mais ne figurent pas dans le journal courant affiché.
        mouvements_list = StockMovement.objects.select_related('material', 'lot', 'emplacement_source', 'emplacement_destination', 'utilisateur').exclude(type='ENTREE')
        mvt_from = request.GET.get('mvt_from')
        mvt_to = request.GET.get('mvt_to')
        mvt_type = request.GET.get('mvt_type')
        mvt_cat = request.GET.get('mvt_cat')
        mvt_loc = request.GET.get('mvt_loc')
        mvt_from, mvt_to, mvt_loc = _clean_iso_date(mvt_from), _clean_iso_date(mvt_to), _clean_int_str(mvt_loc)
        mvt_q = request.GET.get('mvt_q')
        mvt_annules = request.GET.get('mvt_annules') == '1'

        if not mvt_annules:
            mouvements_list = mouvements_list.filter(annule=False)
        if mvt_from:
            mouvements_list = mouvements_list.filter(date__date__gte=mvt_from)
        if mvt_to:
            mouvements_list = mouvements_list.filter(date__date__lte=mvt_to)
        if mvt_type:
            mouvements_list = mouvements_list.filter(type=mvt_type)
        if mvt_cat:
            mouvements_list = mouvements_list.filter(material__category=mvt_cat)
        if mvt_loc:
            mouvements_list = mouvements_list.filter(Q(emplacement_source_id=mvt_loc) | Q(emplacement_destination_id=mvt_loc))
        if mvt_q:
            mouvements_list = mouvements_list.filter(Q(material__name__icontains=mvt_q) | Q(lot__numero_lot__icontains=mvt_q))

        paginator_mvt = Paginator(mouvements_list, 30)
        page_mvt_num = request.GET.get('page_mvt', 1)
        mouvements_page = paginator_mvt.get_page(page_mvt_num)

        previsions = []
        for m in all_active_materials:
            try:
                seuil = m.seuil_intelligent
                if seuil and seuil.consommation_journaliere_moy > 0:
                    jours = seuil.jours_de_stock
                    if jours <= 15:
                        previsions.append({
                            'material_id': m.id,
                            'material': m.name,
                            'stock_actuel': m.usable_quantity,
                            'conso_jour': seuil.consommation_journaliere_moy,
                            'jours_restants': jours,
                            'date_rupture': seuil.date_rupture_prevue,
                            'critique': jours <= 7
                        })
            except Exception:
                pass
        previsions.sort(key=lambda x: x['jours_restants'])

        suppliers_list = Supplier.objects.filter(is_archived=False).order_by('name')
        locations = StockLocation.objects.filter(is_active=True)
        lots_a_traiter = StockLot.objects.filter(statut__in=['EN_ATTENTE', 'BLOQUE', 'QUARANTAINE']).order_by('-date_reception')
        lots_tous = StockLot.objects.all().order_by('-id')[:100]
        
        da_statut = request.GET.get('da_statut', '')
        demandes = DemandeAchat.objects.all()
        if da_statut:
            demandes = demandes.filter(statut=da_statut)
            
        da_en_attente = DemandeAchat.objects.filter(statut='SOUMISE').count()
        bons_commande = BonCommande.objects.all().order_by('-date_commande')

        valeur_stock_total = sum(float(m.usable_quantity) * float(m.price_per_unit) for m in all_active_materials)

        context = {
            'tab': tab, 'sub': sub, 'search_query': search_query,
            'category_filter': category_filter, 'low_stock_only': low_stock_only,
            'supplier_filter': supplier_filter, 'depot_filter': depot_filter,
            'family_filter': family_filter, 'subfamily_filter': subfamily_filter,
            'micronage_filter': micronage_filter, 'grammage_filter': grammage_filter,
            'laize_filter': laize_filter, 'origin_filter': origin_filter,
            'micronage_options': Material.objects.filter(is_archived=False, micronage_standard__isnull=False).order_by('micronage_standard').values_list('micronage_standard', flat=True).distinct(),
            'grammage_options': Material.objects.filter(is_archived=False, grammage__isnull=False).order_by('grammage').values_list('grammage', flat=True).distinct(),
            'laize_options': Material.objects.filter(is_archived=False, laize_mm__isnull=False).order_by('laize_mm').values_list('laize_mm', flat=True).distinct(),
            'origine_options': Material.ORIGINE_CHOICES,
            'depot_options': StockCatalogOption.objects.filter(kind='DEPOT', active=True).order_by('position', 'name'),
            'family_options': StockCatalogOption.objects.filter(kind='FAMILY', active=True).order_by('position', 'name'),
            'subfamily_options': StockCatalogOption.objects.filter(kind='SUBFAMILY', active=True).order_by('position', 'name'),
            'sort': sort_by, 'archives': archives,
            
            'materials': materials_page, 
            'all_materials': all_active_materials,
            'materials_film': [m for m in all_active_materials if m.category == 'FILM'],
            'materials_ink': [m for m in all_active_materials if m.category == 'INK'],
            'materials_glue': [m for m in all_active_materials if m.category == 'GLUE'],
            'materials_solv': [m for m in all_active_materials if m.category == 'SOLV'],
            
            'total_matieres': all_active_materials.count(),
            'alertes_stock': alertes_stock, 'nb_alertes': len(alertes_stock),
            'nb_ruptures': nb_ruptures, 'nb_critiques': nb_critiques,
            'nb_alertes_simples': nb_alertes_simples, 'top_alertes': alertes_stock[:5],
            'top_alertes_noms': safe_json(top_alertes_noms),
            'top_alertes_stock': safe_json(top_alertes_stock),
            'top_alertes_seuil': safe_json(top_alertes_seuil),
            'top_alertes_couleurs': safe_json(top_alertes_couleurs),
            'cat_labels_json': safe_json(cat_labels),
            'cat_rupture_json': safe_json(cat_rupture),
            'cat_critique_json': safe_json(cat_critique),
            'cat_alerte_json': safe_json(cat_alerte),
            'previsions': previsions, 'lots_peremption': lots_peremption,
            'lots_a_traiter': lots_a_traiter, 'lots': lots_tous,
            'lots_bloques': StockLot.objects.filter(statut='BLOQUE').count(),
            'lots_attente': StockLot.objects.filter(statut='EN_ATTENTE').count(),
            'mouvements': mouvements_page, 'locations': locations, 'machines': Machine.objects.all().order_by('name'), 'suppliers_list': suppliers_list,
            'suppliers': suppliers_list, 'demandes': demandes, 'da_en_attente': da_en_attente,
            'da_statut': da_statut, 'bons_commande': bons_commande,
            'valeur_stock_total': valeur_stock_total, 'categories': Material.CAT_CHOICES,
            'types_mouvement': StockMovement.TYPE_CHOICES,
            'peut_gerer': peut_gerer, 'peut_valider': peut_valider,
            'qs_mat': f"tab=matieres&q={quote(str(search_query))}&category={quote(str(category_filter))}&supplier={quote(str(supplier_filter))}&depot={quote(str(depot_filter or ''))}&family={quote(str(family_filter or ''))}&subfamily={quote(str(subfamily_filter or ''))}&micronage={quote(str(micronage_filter or ''))}&grammage={quote(str(grammage_filter or ''))}&laize={quote(str(laize_filter or ''))}&origin={quote(str(origin_filter or ''))}&sort={quote(str(sort_by))}",
            'qs_mvt': f"tab=mouvements&mvt_from={quote(str(mvt_from or ''))}&mvt_to={quote(str(mvt_to or ''))}&mvt_type={quote(str(mvt_type or ''))}&mvt_cat={quote(str(mvt_cat or ''))}&mvt_loc={quote(str(mvt_loc or ''))}&mvt_q={quote(str(mvt_q or ''))}&mvt_annules={quote(request.GET.get('mvt_annules', ''))}"
        }
        return render(request, 'stock/stock_advanced.html', context)
    except Exception:
        logger.exception('stock_advanced_failed')
        messages.error(request, "❌ Erreur critique. Détails dans les journaux du serveur.")
        return redirect('dashboard')


@login_required
@module_required('stock')
@transaction.atomic
def add_material(request):
    if not can_manage_stock(request.user):
        messages.error(request, "Accès refusé.")
        return redirect(reverse('stock_advanced') + '?tab=matieres')

    if request.method == 'POST':
        form = MaterialCreateForm(request.POST)
        if form.is_valid():
            opening_quantity = float(form.cleaned_data.get('initial_quantity') or 0)
            reception_location = form.cleaned_data['emplacement_reception']
            mat = form.save(commit=False)
            mat.initial_quantity = opening_quantity
            # Le stock courant part à zéro; le mouvement d'entrée ci-dessous le crédite
            # une seule fois et le rend visible dans le journal.
            mat.quantity = 0
            mat.save()
            StockSeuil.objects.create(material=mat)
            if opening_quantity > 0:
                StockService.enregistrer_mouvement(
                    type_mvt='ENTREE', material=mat, quantite=opening_quantity,
                    dst=reception_location, user=request.user,
                    motif='Réception initiale lors de la création de la matière première.'
                )
            messages.success(request, f'✅ Matière ajoutée et réception initiale enregistrée au journal ({opening_quantity:g} {mat.unit}).')
            return redirect(reverse('stock_advanced') + '?tab=matieres')
    else:
        form = MaterialCreateForm()
    return render(request, 'stock/material_form.html', {
        'form': form, 'is_new_material': True,
        'title': 'Nouvelle Matière Première', 'btn_label': 'Ajouter la Matière'
    })


@login_required
@module_required('stock')
def edit_material(request, id):
    if not can_manage_stock(request.user):
        messages.error(request, "Accès refusé.")
        return redirect(reverse('stock_advanced') + '?tab=matieres')

    material = get_object_or_404(Material, id=id)
    if request.method == 'POST':
        form = MaterialEditForm(request.POST, instance=material)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ Matière "{material.name}" modifiée !')
            return redirect(reverse('stock_advanced') + '?tab=matieres')
    else:
        form = MaterialEditForm(instance=material)
    return render(request, 'stock/material_form.html', {
        'form': form, 'material': material, 'title': f'Modifier : {material.name}', 'btn_label': 'Enregistrer'
    })


@login_required
@module_required('stock')
def delete_material(request, id):
    if not can_manage_stock(request.user):
        messages.error(request, "Accès refusé.")
        return redirect(reverse('stock_advanced') + '?tab=matieres')

    material = get_object_or_404(Material, id=id)
    if request.method == 'POST':
        material.is_archived = True
        material.save()
        messages.success(request, f'📁 Matière « {material.name} » archivée avec succès.')
    return redirect(reverse('stock_advanced') + '?tab=matieres')


@login_required
@module_required('stock')
def material_restore(request, id):
    if not can_manage_stock(request.user):
        messages.error(request, "Accès refusé.")
        return redirect(reverse('stock_advanced') + '?tab=matieres')

    material = get_object_or_404(Material, id=id)
    if request.method == 'POST':
        material.is_archived = False
        material.save()
        messages.success(request, f'♻️ Matière « {material.name} » restaurée parmi les matières actives.')
    return redirect(reverse('stock_advanced') + '?tab=matieres')


# ===========================================================================
# --- ACTIONS GROUPÉES SÉCURISÉES ---
# ===========================================================================

@login_required
@module_required('stock')
@transaction.atomic
def bulk_delete_materials(request):
    if not can_manage_stock(request.user):
        return JsonResponse({'status': 'error', 'message': 'Accès interdit.'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
            ids = _clean_ids(data)
            if ids:
                materials = Material.objects.filter(id__in=ids)
                count = materials.count()
                materials.update(is_archived=True)
                return JsonResponse({'status': 'success', 'message': f'📁 {count} matière(s) archivée(s) avec succès.'})
            return JsonResponse({'status': 'error', 'message': 'Sélection vide.'})
        except ValueError as exc:
            transaction.set_rollback(True)
            return JsonResponse({'status': 'error', 'message': str(exc)})
        except Exception:
            transaction.set_rollback(True)
            logger.exception('stock_bulk_action_failed')
            return JsonResponse({'status': 'error', 'message': "Opération impossible. Détails dans les journaux du serveur."}, status=500)
    return redirect('stock_advanced')


@login_required
@module_required('stock')
@transaction.atomic
def bulk_delete_movements(request):
    if not can_manage_stock(request.user):
        return JsonResponse({'status': 'error', 'message': 'Accès interdit.'}, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            ids = _clean_ids(data)
            motif = str(data.get('motif', 'Annulation groupée')).strip()[:500]
            
            if ids:
                mouvements = StockMovement.objects.filter(id__in=ids, annule=False)
                count = mouvements.count()
                for m in mouvements:
                    _ensure_movement_reversible(m)
                    StockService.annuler_mouvement(m, motif, request.user)
                return JsonResponse({'status': 'success', 'message': f'↩ {count} mouvement(s) annulé(s) (contre-passation effectuée).'})
            return JsonResponse({'status': 'error', 'message': 'Sélection vide.'})
        except ValueError as exc:
            transaction.set_rollback(True)
            return JsonResponse({'status': 'error', 'message': str(exc)})
        except Exception:
            transaction.set_rollback(True)
            logger.exception('stock_bulk_action_failed')
            return JsonResponse({'status': 'error', 'message': "Opération impossible. Détails dans les journaux du serveur."}, status=500)
    return redirect('stock_advanced')


# ===========================================================================
# --- ENREGISTREMENTS DE LOTS ET CONTROLE QUALITÉ (FEFO) ---
# ===========================================================================

@login_required
@module_required('stock')
@transaction.atomic
def lot_add(request):
    if not can_manage_stock(request.user):
        messages.error(request, "Accès refusé.")
        return redirect('stock_advanced')

    if request.method == 'POST':
        try:
            material_id = request.POST.get('material')
            material_name_free = request.POST.get('material_name_free', '').strip()
            category = request.POST.get('category')
            numero_lot = request.POST.get('numero_lot', '').strip()
            date_reception = request.POST.get('date_reception')
            fournisseur_id = request.POST.get('fournisseur') or None
            emplacement_id = request.POST.get('emplacement') or None
            quantite = _positive_float(request.POST.get('quantite_initiale'), 'Quantité')
            prix = _non_negative_float(request.POST.get('prix_unitaire', 0), 'Prix unitaire')
            statut = request.POST.get('statut', 'EN_ATTENTE')
            if statut not in LOT_STATUTS:
                raise ValueError("Statut de lot invalide.")
            notes = request.POST.get('notes', '')
            laize_raw = request.POST.get('laize') or ''
            micronage_raw = request.POST.get('micronage') or ''
            grammage_raw = request.POST.get('grammage') or ''
            metrage_raw = request.POST.get('metrage') or request.POST.get('longueur') or ''
            unites_raw = request.POST.get('nombre_unites') or ''
            origine = request.POST.get('origine', '').strip()
            laize = int(laize_raw) if laize_raw else None
            micronage = int(micronage_raw) if micronage_raw else None
            grammage = _non_negative_float(grammage_raw, 'Grammage') if grammage_raw else None
            metrage = _non_negative_float(metrage_raw, 'Métrage') if metrage_raw else None
            longueur = int(round(metrage)) if metrage is not None else None
            nombre_unites = int(unites_raw) if unites_raw else None
            if laize is not None and laize < 0:
                raise ValueError('La laize ne peut pas être négative.')
            if micronage is not None and micronage < 0:
                raise ValueError('Le micronage ne peut pas être négatif.')
            if nombre_unites is None or nombre_unites < 1:
                raise ValueError('Saisissez un nombre d’unités supérieur à zéro.')
            if origine not in dict(Material.ORIGINE_CHOICES):
                raise ValueError('Choisissez une origine valide (Importation ou Local).')

            if not _clean_iso_date(date_reception):
                raise ValueError("Date de réception invalide.")
            certificat = request.FILES.get('certificat_qualite')
            if certificat:
                validate_upload(certificat, CERTIFICATE_EXTENSIONS, CERTIFICATE_MAX_BYTES)

            if category not in dict(Material.CAT_CHOICES):
                raise ValueError('Choisissez une catégorie de matière valide.')
            if material_id:
                material = get_object_or_404(Material, id=material_id)
            elif material_name_free:
                material, _ = Material.objects.get_or_create(
                    name=material_name_free,
                    defaults={'category': category or 'INK', 'quantity': 0, 'min_threshold': 100}
                )
            else:
                messages.error(request, "Veuillez désigner la matière première.")
                return redirect('stock_advanced')

            category = material.category
            material.poids_kg = quantite
            material.nombre_unites = nombre_unites
            material.origine = origine
            material_fields = ['poids_kg', 'nombre_unites', 'origine']
            if category == 'FILM':
                if laize is not None:
                    material.laize_mm = laize
                    material_fields.append('laize_mm')
                if micronage is not None:
                    material.micronage_standard = micronage
                    material_fields.append('micronage_standard')
                if grammage is not None:
                    material.grammage = grammage
                    material_fields.append('grammage')
                if metrage is not None:
                    material.metrage_standard = metrage
                    material_fields.append('metrage_standard')
            material.save(update_fields=material_fields)

            fournisseur = Supplier.objects.filter(id=fournisseur_id).first() if fournisseur_id else None
            emplacement = StockLocation.objects.filter(id=emplacement_id).first() if emplacement_id else None
            
            lot = StockLot.objects.create(
                material=material, numero_lot=numero_lot,
                date_reception=date_reception, fournisseur=fournisseur,
                emplacement=emplacement, quantite_initiale=quantite,
                quantite_restante=0, prix_unitaire=prix,
                statut=statut, notes=notes, laize=laize, longueur=longueur,
                micronage=micronage, grammage=grammage, metrage=metrage,
                poids_kg=quantite, nombre_unites=nombre_unites, origine=origine,
                created_by=request.user
            )

            if request.FILES.get('certificat_qualite'):
                lot.certificat_qualite = request.FILES['certificat_qualite']
                lot.save()

            # Toute réception augmente le stock physique. Le statut qualité filtre
            # séparément l'usage en production via usable_quantity.
            StockService.enregistrer_mouvement(
                type_mvt='ENTREE', material=material, quantite=quantite, lot=lot,
                dst=emplacement, user=request.user, motif=f"Réception lot {numero_lot}"
            )

            messages.success(request, f"✅ Lot {numero_lot} créé avec succès en Magasin Général.")
        except ValueError as exc:
            transaction.set_rollback(True)
            messages.error(request, f"❌ Erreur lors de la création du lot : {exc}")
        except Exception:
            transaction.set_rollback(True)
            logger.exception('stock_lot_add_failed')
            messages.error(request, "❌ Erreur lors de la création du lot. Détails dans les journaux du serveur.")
    return redirect('stock_advanced')


@login_required
@module_required('stock')
@transaction.atomic
def lot_valider(request, id):
    if not can_validate_purchase(request.user):
        messages.error(request, "Accès refusé (Droits de validation requis).")
        return redirect('stock_advanced')

    lot = get_object_or_404(StockLot, id=id)
    if request.method == 'POST':
        ancien_statut = lot.statut
        lot.statut = 'CONFORME'
        lot.save()

        deja_entre_en_stock = lot.mouvements.filter(type='ENTREE', annule=False).exists()
        if ancien_statut != 'CONFORME' and not deja_entre_en_stock and lot.quantite_restante > 0:
            StockService.enregistrer_mouvement(
                type_mvt='ENTREE', material=lot.material, quantite=lot.quantite_restante,
                lot=lot, dst=lot.emplacement, user=request.user, motif=f"Validation Qualité Lot {lot.numero_lot}"
            )
        messages.success(request, f"✅ Le lot {lot.numero_lot} est validé et utilisable en production.")
    return redirect('stock_advanced')


@login_required
@module_required('stock')
@transaction.atomic
def lot_bloquer(request, id):
    if not can_validate_purchase(request.user):
        messages.error(request, "Accès refusé.")
        return redirect('stock_advanced')

    lot = get_object_or_404(StockLot, id=id)
    if request.method == 'POST':
        lot.statut = 'BLOQUE'
        lot.save()
        messages.warning(request, f"🔴 Le lot {lot.numero_lot} a été bloqué et écarté du stock utilisable.")
    return redirect('stock_advanced')


@login_required
@module_required('stock')
def lot_detail(request, id):
    lot = get_object_or_404(StockLot, id=id)
    mouvements = lot.mouvements.all().order_by('-date')
    return render(request, 'stock/lot_detail.html', {'lot': lot, 'mouvements': mouvements})


# ===========================================================================
# --- MOUVEMENTS UNITAIRES ---
# ===========================================================================

@login_required
@module_required('stock')
@transaction.atomic
def mouvement_add(request):
    if not can_manage_stock(request.user):
        messages.error(request, "Accès refusé.")
        return redirect(reverse('stock_advanced') + '?tab=mouvements')

    if request.method == 'POST':
        try:
            form_type = request.POST.get('type')
            valid_types = {'SORTIE', 'RETOUR_INTERNE', 'AVARIE', 'AJUSTEMENT'}
            if form_type not in valid_types:
                raise ValueError('Type de mouvement inconnu. Choisissez Sortie, Retour, Avarie ou Ajustement.')
            # L’avarie est journalisée comme une perte physique avec son bon dédié.
            type_mvt = 'PERTE' if form_type == 'AVARIE' else form_type

            material_ids = request.POST.getlist('materials')
            quantities = request.POST.getlist('quantites')
            # Compatibilité avec les formulaires simples déjà en circulation.
            legacy_single = not material_ids and bool(request.POST.get('material'))
            if legacy_single:
                material_ids = [request.POST.get('material')]
                quantities = [request.POST.get('quantite', '')]
            if len(material_ids) != len(quantities):
                raise ValueError('Le nombre de matières et de quantités ne correspond pas.')

            lines = []
            for index, (material_id, raw_quantity) in enumerate(zip(material_ids, quantities), start=1):
                if not material_id and not raw_quantity:
                    continue
                if not material_id:
                    raise ValueError(f'Sélectionnez la matière de la ligne {index}.')
                if not raw_quantity:
                    raise ValueError(f'Saisissez la quantité de la ligne {index}.')
                material = get_object_or_404(Material, id=material_id, is_archived=False)
                quantity = (
                    _signed_nonzero_float(raw_quantity, f'Variation ligne {index}')
                    if form_type == 'AJUSTEMENT'
                    else _positive_float(raw_quantity, f'Nombre d’articles ligne {index}')
                )
                if form_type != 'AJUSTEMENT' and not legacy_single and not quantity.is_integer():
                    raise ValueError(f'Le nombre d’articles de la ligne {index} doit être un entier.')
                lines.append((material, quantity, legacy_single, index - 1))
            if not lines:
                raise ValueError('Ajoutez au moins une matière et une quantité.')
            selected_category = request.POST.get('category', '')
            if selected_category not in {code for code, _label in Material.CAT_CHOICES}:
                raise ValueError('Choisissez un univers valide.')
            mismatched = [material.name for material, _quantity, _legacy, _form_index in lines if material.category != selected_category]
            if mismatched:
                raise ValueError('Toutes les matières doivent appartenir à l’univers choisi.')

            laizes = request.POST.getlist('laizes')
            micronages = request.POST.getlist('micronages')
            metragess = request.POST.getlist('metrages')
            weights = request.POST.getlist('poids_kg')
            unit_counts = request.POST.getlist('nombre_unites')
            lines_with_specs = []
            for material, quantity, is_legacy, form_index in lines:
                index = form_index
                display_index = form_index + 1
                laize = micronage = metrage = weight = None
                number_of_items = None
                if form_type == 'AJUSTEMENT':
                    # La variation signée est la seule quantité qui modifie le stock; les champs ci-dessous sont descriptifs.
                    stock_quantity = quantity
                    raw_units = unit_counts[index].strip() if index < len(unit_counts) else ''
                    if raw_units:
                        units_value = _positive_float(raw_units, f'Nombre d’unités ligne {display_index}')
                        if not units_value.is_integer():
                            raise ValueError(f'Le nombre d’unités de la ligne {display_index} doit être un entier.')
                        number_of_items = int(units_value)
                    if selected_category == 'FILM':
                        try:
                            laize_value = _positive_float(laizes[index], f'Laize ligne {display_index}')
                            micronage_value = _positive_float(micronages[index], f'Micronage ligne {display_index}')
                            metrage = _positive_float(metragess[index], f'Métrage par article ligne {display_index}')
                        except IndexError:
                            raise ValueError(f'Renseignez la laize, le micronage et le métrage de la ligne {display_index}.')
                        if not laize_value.is_integer() or not micronage_value.is_integer():
                            raise ValueError('La laize et le micronage doivent être des nombres entiers.')
                        laize, micronage = int(laize_value), int(micronage_value)
                else:
                    try:
                        weight = _positive_float(weights[index], f'Poids par article ligne {index + 1}')
                    except IndexError:
                        raise ValueError(f'Saisissez le poids par article de la ligne {display_index}.')
                    if selected_category == 'FILM':
                        try:
                            laize_value = _positive_float(laizes[index], f'Laize ligne {display_index}')
                            micronage_value = _positive_float(micronages[index], f'Micronage ligne {display_index}')
                            metrage = _positive_float(metragess[index], f'Métrage ligne {display_index}')
                        except IndexError:
                            raise ValueError(f'Renseignez la laize, le micronage et le métrage de la ligne {display_index}.')
                        if not laize_value.is_integer() or not micronage_value.is_integer():
                            raise ValueError('La laize et le micronage doivent être des nombres entiers.')
                        laize, micronage = int(laize_value), int(micronage_value)
                    if is_legacy:
                        # Compatibilité des anciens formulaires simples qui transmettaient déjà des kg.
                        stock_quantity = quantity
                    else:
                        number_of_items = int(quantity)
                        stock_quantity = round(number_of_items * weight, 3)
                        if stock_quantity <= 0:
                            raise ValueError(f'Le poids total de la ligne {index + 1} doit être supérieur à zéro.')
                lines_with_specs.append((material, stock_quantity, {
                    'laize_mm': laize, 'micronage': micronage,
                    'metrage': metrage, 'poids_kg': weight,
                    'nombre_unites': number_of_items,
                }))
            lines = lines_with_specs

            src_id = request.POST.get('emplacement_source') or None
            dst_id = request.POST.get('emplacement_destination') or None
            of_id = request.POST.get('of') or None
            machine_id = request.POST.get('machine') or None
            motif = request.POST.get('motif', '')
            src = StockLocation.objects.filter(id=src_id).first() if src_id else None
            dst = StockLocation.objects.filter(id=dst_id).first() if dst_id else None
            machine_obj = Machine.objects.filter(id=machine_id).first() if machine_id else None
            of_model = StockMovement._meta.get_field('of').remote_field.model
            of_obj = of_model.objects.filter(pk=of_id).first() if of_id else None
            if machine_id and not machine_obj:
                raise ValueError('Machine sélectionnée introuvable.')
            if of_id and not of_obj:
                raise ValueError('Ordre de Fabrication sélectionné introuvable.')
            if type_mvt == 'SORTIE' and not machine_obj:
                raise ValueError('Toute sortie de production doit être liée à une Machine.')

            if form_type in {'RETOUR_INTERNE', 'AVARIE'} and not (motif or '').strip():
                raise ValueError('Saisissez le motif obligatoire du retour ou de l’avarie.')

            # Une seule transaction : mouvements multi-matières et bon de suivi atomiques.
            with transaction.atomic():
                doc = None
                if form_type in {'RETOUR_INTERNE', 'AVARIE'}:
                    doc = StockPrintDocument.objects.create(
                        kind='RETOUR_INTERNE' if form_type == 'RETOUR_INTERNE' else 'AVARIE',
                        document_date=timezone.localdate(), created_by=request.user,
                        notes=(motif or '').strip(),
                    )
                for material, quantity, characteristics in lines:
                    lot = None
                    if type_mvt == 'SORTIE' and of_obj is not None:
                        lot = next((candidate for candidate in material.get_fefo_lots() if lot_available_quantity_for_of(candidate, of_obj.pk) + 1e-6 >= float(quantity)), None)
                    elif type_mvt == 'PERTE':
                        lot = next((candidate for candidate in material.get_fefo_lots() if lot_available_quantity_for_of(candidate, None) + 1e-6 >= float(quantity)), None)
                        if not lot and material.get_fefo_lots().exists():
                            raise ValueError(f'Aucun lot conforme ne couvre la quantité d’avarie de « {material.name} ».')
                    elif type_mvt == 'RETOUR_INTERNE':
                        lot = StockLot.objects.create(
                            material=material,
                            numero_lot=f"RETOUR-{material.code or material.pk}-{timezone.now():%Y%m%d-%H%M%S-%f}",
                            date_reception=timezone.localdate(), fournisseur=material.supplier,
                            emplacement=dst, quantite_initiale=float(quantity), quantite_restante=0,
                            prix_unitaire=material.price_per_unit, statut='CONFORME',
                            created_by=request.user, notes=f'Retour interne — {motif or ""}',
                        )
                    movement = StockService.enregistrer_mouvement(
                        type_mvt=type_mvt, material=material, quantite=quantity, lot=lot,
                        src=src, dst=dst, of=of_obj, machine=machine_obj,
                        user=request.user,
                        motif=(f"Avarie — {(motif or '').strip()}" if form_type == 'AVARIE' else (motif or '').strip()),
                        **characteristics,
                    )
                    if doc:
                        doc.movements.add(movement)
                        StockPrintDocumentLine.objects.create(
                            document=doc, material=material, movement=movement, lot=lot,
                            emplacement=src if form_type == 'AVARIE' else (dst or src),
                            quantity=quantity, unit_snapshot=material.unit,
                            notes=(motif or '').strip(),
                        )

            labels = ', '.join(material.name for material, _quantity, _characteristics in lines)
            if doc:
                messages.success(request, f"Bon {doc.reference} créé : {len(lines)} ligne(s) pour {labels}.")
                return redirect('stock_document_print', id=doc.id)
            messages.success(request, f"🔄 {len(lines)} mouvement(s) enregistré(s) : {labels}.")
        except ValueError as exc:
            transaction.set_rollback(True)
            messages.error(request, f"❌ Erreur : {exc}")
        except Exception:
            transaction.set_rollback(True)
            logger.exception('stock_movement_failed')
            messages.error(request, "❌ Erreur inattendue. Détails dans les journaux du serveur.")
    return redirect(reverse('stock_advanced') + '?tab=mouvements')


@login_required
@module_required('stock')
@transaction.atomic
def mouvement_annuler(request, id):
    if not can_manage_stock(request.user):
        messages.error(request, "Accès refusé.")
        return redirect('stock_advanced')

    mvt = get_object_or_404(StockMovement, id=id)
    if request.method == 'POST':
        motif = request.POST.get('motif', '').strip()
        if not motif:
            messages.error(request, "Un motif est obligatoire pour annuler un mouvement.")
            return redirect('stock_advanced')
        try:
            StockService.annuler_mouvement(mvt, motif, request.user)
            messages.success(request, "✅ Mouvement annulé et contre-passé avec succès.")
        except ValueError as exc:
            transaction.set_rollback(True)
            messages.error(request, f"❌ Erreur : {exc}")
        except Exception:
            transaction.set_rollback(True)
            logger.exception('stock_movement_failed')
            messages.error(request, "❌ Erreur inattendue. Détails dans les journaux du serveur.")
    return redirect('stock_advanced')


# ===========================================================================
# --- CHAINE D'ACHATS SÉQUENTIELLE (DA -> BC -> RÉCEPTION) ---
# ===========================================================================

@login_required
@module_required('stock')
@transaction.atomic
def da_add(request):
    if request.method == 'POST':
        try:
            annee = timezone.now().year
            dernier = DemandeAchat.objects.filter(reference__startswith=f"DA-{annee}-").order_by('-reference').first()
            seq = 1
            if dernier:
                try:
                    seq = int(dernier.reference.split('-')[-1]) + 1
                except Exception:
                    pass
            ref = f"DA-{annee}-{seq:04d}"

            material = get_object_or_404(Material, id=request.POST.get('material'))
            DemandeAchat.objects.create(
                reference=ref, material=material,
                quantite_demandee=_positive_float(request.POST.get('quantite_demandee'), 'Quantité'),
                motif=request.POST.get('motif', ''),
                urgence=request.POST.get('urgence', 'NORMALE'),
                statut='SOUMISE', demandeur=request.user,
                date_besoin=_clean_iso_date(request.POST.get('date_besoin')) or None,
            )
            messages.success(request, f"📋 Demande d'achat {ref} soumise à la direction.")
        except ValueError as exc:
            transaction.set_rollback(True)
            messages.error(request, f"Erreur : {exc}")
        except Exception:
            transaction.set_rollback(True)
            logger.exception('stock_purchase_failed')
            messages.error(request, "Erreur inattendue. Détails dans les journaux du serveur.")
    return redirect('stock_advanced')


@login_required
@module_required('stock')
def da_valider(request, id):
    if not can_validate_purchase(request.user):
        messages.error(request, "Accès refusé.")
        return redirect('stock_advanced')

    da = get_object_or_404(DemandeAchat, id=id)
    if request.method == 'POST':
        if da.statut != 'SOUMISE':
            messages.warning(request, f"DA {da.reference} : déjà traitée.")
            return redirect('stock_advanced')
        if self_approval_blocked(request.user, da.demandeur_id):
            messages.error(request, "Vous ne pouvez pas valider votre propre demande d'achat.")
            return redirect('stock_advanced')
        da.statut = 'VALIDEE'
        da.valideur = request.user
        da.date_validation = timezone.now().date()
        da.save()
        messages.success(request, f"DA {da.reference} validée par la direction.")
    return redirect('stock_advanced')


@login_required
@module_required('stock')
def da_refuser(request, id):
    if not can_validate_purchase(request.user):
        messages.error(request, "Accès refusé.")
        return redirect('stock_advanced')

    da = get_object_or_404(DemandeAchat, id=id)
    if request.method == 'POST':
        if da.statut not in ('SOUMISE', 'VALIDEE'):
            messages.warning(request, f"DA {da.reference} : déjà traitée.")
            return redirect('stock_advanced')
        da.statut = 'REFUSEE'
        da.save()
        messages.warning(request, f"DA {da.reference} refusée.")
    return redirect('stock_advanced')


@login_required
@module_required('stock')
@transaction.atomic
def bc_add(request):
    if not can_manage_stock(request.user):
        messages.error(request, "Accès refusé.")
        return redirect('stock_advanced')

    if request.method == 'POST':
        try:
            annee = timezone.now().year
            dernier = BonCommande.objects.filter(reference__startswith=f"BC-{annee}-").order_by('-reference').first()
            seq = 1
            if dernier:
                try:
                    seq = int(dernier.reference.split('-')[-1]) + 1
                except Exception:
                    pass
            ref = f"BC-{annee}-{seq:04d}"

            fournisseur = get_object_or_404(Supplier, id=request.POST.get('fournisseur'))
            bc = BonCommande.objects.create(
                reference=ref, fournisseur=fournisseur, statut='BROUILLON',
                date_livraison_prevue=_clean_iso_date(request.POST.get('date_livraison_prevue')) or None,
                notes=request.POST.get('notes', ''), cree_par=request.user,
            )
            idx = 1
            total = 0
            while idx <= 200 and request.POST.get(f'material_{idx}'):
                mat = Material.objects.filter(id=request.POST.get(f'material_{idx}')).first()
                if mat:
                    qte = _positive_float(request.POST.get(f'quantite_{idx}'), 'Quantité')
                    prix = _non_negative_float(request.POST.get(f'prix_{idx}', 0), 'Prix')
                    LigneBonCommande.objects.create(
                        bon_commande=bc, material=mat,
                        quantite_commandee=qte, prix_unitaire=prix
                    )
                    total += qte * prix
                idx += 1
            
            da_id = parse_int(request.GET.get('da'))
            if da_id:
                da = DemandeAchat.objects.filter(id=da_id).first()
                # Seule une demande déjà validée par la direction peut devenir un bon de commande.
                if da and da.statut == 'VALIDEE':
                    da.statut = 'COMMANDEE'
                    da.bon_commande = bc
                    da.save()

            bc.montant_total = total
            bc.save()
            messages.success(request, f"📄 BC {bc.reference} généré avec succès.")
        except ValueError as exc:
            transaction.set_rollback(True)
            messages.error(request, f"Erreur : {exc}")
        except Exception:
            transaction.set_rollback(True)
            logger.exception('stock_purchase_failed')
            messages.error(request, "Erreur inattendue. Détails dans les journaux du serveur.")
    return redirect('stock_advanced')


@login_required
@module_required('stock')
def bc_envoyer(request, id):
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    bc = get_object_or_404(BonCommande, id=id)
    if request.method == 'POST':
        if bc.statut != 'BROUILLON':
            messages.warning(request, f"BC {bc.reference} : déjà envoyé ou clôturé.")
            return redirect('stock_advanced')
        bc.statut = 'ENVOYE'
        bc.save()
        messages.success(request, f"BC {bc.reference} marqué comme envoyé au fournisseur.")
    return redirect('stock_advanced')


def _ensure_movement_reversible(movement):
    """Refuse to reverse a receipt if its quantity has already left the lot."""
    reversibility_check = movement.type == 'ENTREE' or (
        movement.type == 'AJUSTEMENT' and float(movement.quantite or 0) > 0
    )
    if not reversibility_check:
        return
    material = Material.objects.select_for_update().get(pk=movement.material_id)
    material.refresh_from_db(fields=['quantity'])
    if movement.lot_id:
        lot = StockLot.objects.select_for_update().get(pk=movement.lot_id)
        lot.refresh_from_db(fields=['quantite_restante'])
        available = float(lot.quantite_restante or 0)
    else:
        available = float(material.quantity or 0)
    if available + 0.0001 < float(movement.quantite):
        raise ValueError('Modification/annulation refusée : une partie du stock ajouté par ce mouvement a déjà été consommée.')


@login_required
@module_required('stock')
@transaction.atomic
def stock_movement_delete(request, id):
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    if not can_manage_stock(request.user):
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'Accès refusé.'}, status=403)
        return _refuse_manage(request)
    if request.method != 'POST':
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'Méthode non autorisée.'}, status=405)
        return redirect(reverse('stock_advanced') + '?tab=mouvements')
    try:
        movement = get_object_or_404(StockMovement.objects.select_for_update(), pk=id)
        if movement.annule:
            raise ValueError('Ce mouvement est déjà annulé.')
        _ensure_movement_reversible(movement)
        StockService.annuler_mouvement(movement, 'Annulation demandée depuis le journal des mouvements.', request.user)
        message = f'Mouvement #{movement.id} annulé avec contre-passation; il reste dans l’historique.'
        if is_ajax:
            return JsonResponse({'success': True, 'message': message, 'id': movement.id})
        messages.success(request, message)
    except ValueError as exc:
        transaction.set_rollback(True)
        if is_ajax:
            return JsonResponse({'success': False, 'message': str(exc)}, status=400)
        messages.error(request, str(exc))
    except Exception:
        transaction.set_rollback(True)
        logger.exception('stock_movement_cancel_failed')
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'Impossible d’annuler le mouvement. Consultez les journaux du serveur.'}, status=500)
        messages.error(request, 'Impossible d’annuler ce mouvement. Consultez les journaux du serveur.')
    return redirect(reverse('stock_advanced') + '?tab=mouvements')


@login_required
@module_required('stock')
@transaction.atomic
def stock_movement_edit(request, id):
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    movement = get_object_or_404(StockMovement.objects.select_for_update().select_related('material', 'lot', 'machine', 'of'), pk=id)
    if movement.annule:
        messages.error(request, 'Un mouvement annulé ne peut pas être modifié.')
        return redirect(reverse('stock_advanced') + '?tab=mouvements')
    if request.method == 'POST':
        try:
            movement_type = request.POST.get('type', '')
            valid_types = {value for value, _label in StockMovement.TYPE_CHOICES if value != 'ENTREE'}
            if movement_type not in valid_types:
                raise ValueError('Les entrées de stock se corrigent via le flux de réception dédié.')
            material = get_object_or_404(Material, pk=request.POST.get('material'), is_archived=False)
            unit_mode = request.POST.get('unit_mode', 'kg')
            number_of_items = None
            weight_per_item = None
            if movement_type == 'AJUSTEMENT':
                quantity = _signed_nonzero_float(request.POST.get('quantity'), 'Variation (kg)')
                # Le formulaire de correction conserve les unités descriptives existantes pour un ajustement.
                number_of_items = movement.nombre_unites
            elif unit_mode == 'articles':
                raw_count = _positive_float(request.POST.get('quantity'), 'Nombre d’articles')
                if not raw_count.is_integer():
                    raise ValueError('Le nombre d’articles doit être un entier.')
                number_of_items = int(raw_count)
                weight_per_item = _positive_float(request.POST.get('poids_kg'), 'Poids par article (kg)')
                quantity = round(number_of_items * weight_per_item, 3)
            else:
                quantity = _positive_float(request.POST.get('quantity'), 'Quantité (kg)')
                raw_weight = request.POST.get('poids_kg')
                weight_per_item = _positive_float(raw_weight, 'Poids (kg)') if raw_weight else movement.poids_kg
            lot = StockLot.objects.filter(pk=request.POST.get('lot'), material=material).first() if request.POST.get('lot') else None
            if request.POST.get('lot') and not lot:
                raise ValueError('Le lot ne correspond pas à l’article sélectionné.')
            if lot and movement_type in {'SORTIE', 'PERTE'} and lot.statut != 'CONFORME':
                raise ValueError('Ce lot n’est pas validé conforme; choisissez un lot conforme ou demandez le contrôle qualité.')
            src = StockLocation.objects.filter(pk=request.POST.get('src'), is_active=True).first() if request.POST.get('src') else None
            dst = StockLocation.objects.filter(pk=request.POST.get('dst'), is_active=True).first() if request.POST.get('dst') else None
            machine_id = request.POST.get('machine') or None
            machine_obj = Machine.objects.filter(pk=machine_id).first() if machine_id else None
            if machine_id and not machine_obj:
                raise ValueError('Machine sélectionnée introuvable.')
            # Ce formulaire ne modifie pas l’OF éventuel déjà attaché au mouvement.
            of_obj = movement.of
            motif = (request.POST.get('motif') or '').strip()[:200]
            if movement_type == 'SORTIE' and not machine_obj:
                raise ValueError('Pour une sortie de production, sélectionnez la Machine dans ce formulaire.')

            linked_docs = list(movement.print_documents.all())
            _ensure_movement_reversible(movement)
            old_id = movement.id
            old_date = movement.date
            old_type = movement.type
            StockService.annuler_mouvement(movement, 'Mouvement remplacé par une correction depuis le journal.', request.user)
            # La sortie prend automatiquement un lot FEFO s'il peut couvrir la quantité,
            # sans bloquer la correction si aucun lot n'existe; les pertes restent FEFO.
            if not lot and movement_type == 'SORTIE' and of_obj is not None:
                lot = next((candidate for candidate in material.get_fefo_lots() if lot_available_quantity_for_of(candidate, of_obj.pk) + 1e-6 >= float(quantity)), None)
            if not lot and movement_type == 'PERTE':
                lot = material.get_fefo_lots().first()
                if not lot:
                    raise ValueError(
                        f'Aucun lot conforme avec du stock utilisable n’est disponible pour « {material.name} ». '
                        'Vérifiez la réception et le statut qualité du lot.'
                    )
            if movement_type == 'ENTREE' and not lot:
                lot = StockLot.objects.create(
                    material=material,
                    numero_lot=f"RECEPTION-{material.code or material.pk}-{timezone.now():%Y%m%d-%H%M%S-%f}",
                    date_reception=timezone.localdate(), fournisseur=material.supplier,
                    emplacement=dst, quantite_initiale=float(quantity), quantite_restante=0,
                    prix_unitaire=material.price_per_unit, statut='CONFORME', created_by=request.user,
                    notes=f'Lot généré pour corriger le mouvement #{old_id}.',
                )
            corrected = StockService.enregistrer_mouvement(
                type_mvt=movement_type, material=material, quantite=quantity, lot=lot,
                src=src, dst=dst, of=of_obj, machine=machine_obj,
                user=request.user, motif=motif or f'Correction du mouvement #{old_id}',
                laize_mm=movement.laize_mm, micronage=movement.micronage,
                metrage=movement.metrage, poids_kg=weight_per_item,
                nombre_unites=number_of_items,
            )
            corrected.date = old_date
            corrected.save(update_fields=['date'])

            compatible_types = {
                'SORTIE_JOURNALIERE': 'SORTIE', 'RECEPTION': 'ENTREE',
                'RETOUR_INTERNE': 'RETOUR_INTERNE', 'RETOUR_FOURNISSEUR': 'RETOUR',
            }
            for doc in linked_docs:
                if compatible_types.get(doc.kind) != movement_type:
                    continue
                doc.movements.add(corrected)
                StockPrintDocumentLine.objects.create(
                    document=doc, material=material, movement=corrected, lot=lot,
                    emplacement=src if movement_type in {'SORTIE', 'PERTE', 'RETOUR'} else dst,
                    quantity=quantity, unit_snapshot=material.unit,
                    poids_kg=weight_per_item, nombre_unites=number_of_items,
                    notes=f'Correction du mouvement annulé #{old_id}' + (f' — {motif}' if motif else ''),
                )
            if old_type != movement_type:
                messages.success(request, f'Mouvement #{old_id} annulé et remplacé par le mouvement corrigé #{corrected.id}. Les bons antérieurs signalent la ligne annulée.')
            else:
                messages.success(request, f'Mouvement #{old_id} corrigé (nouvelle ligne #{corrected.id}); l’historique reste traçable.')
            return redirect(reverse('stock_advanced') + '?tab=mouvements')
        except ValueError as exc:
            transaction.set_rollback(True)
            messages.error(request, str(exc))
            return redirect(reverse('stock_movement_edit', args=[id]))
        except Exception:
            transaction.set_rollback(True)
            logger.exception('stock_movement_edit_failed')
            messages.error(request, 'Impossible de corriger ce mouvement. Consultez les journaux du serveur.')
            return redirect(reverse('stock_movement_edit', args=[id]))

    values = request.POST if request.method == 'POST' else {
        'type': movement.type, 'material': str(movement.material_id),
        'quantity': str(movement.nombre_unites if movement.nombre_unites is not None else movement.quantite),
        'unit_mode': 'articles' if movement.nombre_unites is not None else 'kg',
        'poids_kg': str(movement.poids_kg or ''), 'src': str(movement.emplacement_source_id or ''),
        'dst': str(movement.emplacement_destination_id or ''), 'motif': movement.motif,
        'machine': str(movement.machine_id or ''),
    }
    materials = Material.objects.filter(is_archived=False).annotate(
        usable_quantity_cached=Coalesce(Sum('lots__quantite_restante', filter=Q(lots__statut='CONFORME')), 0.0)
    ).order_by('name')
    if movement.material.is_archived:
        archived_current = Material.objects.filter(pk=movement.material_id).annotate(
            usable_quantity_cached=Coalesce(Sum('lots__quantite_restante', filter=Q(lots__statut='CONFORME')), 0.0)
        )
        materials = (archived_current | materials).distinct().order_by('name')
    return render(request, 'stock/movement_edit.html', {
        'movement': movement, 'values': values, 'materials': materials,
        'locations': StockLocation.objects.filter(is_active=True).order_by('name'),
        'machines': Machine.objects.all().order_by('name'),
        'type_choices': [(value, label) for value, label in StockMovement.TYPE_CHOICES if value != 'ENTREE'],
    })


@login_required
@module_required('stock')
@transaction.atomic
def bc_reception(request, id):
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    bc = get_object_or_404(BonCommande.objects.select_for_update(), id=id)
    if request.method == 'POST':
        # Une réception répétée (double clic, rechargement) ne recrée plus les lots.
        if bc.statut == 'RECU_TOTAL':
            messages.warning(request, f"BC {bc.reference} : déjà réceptionné.")
            return redirect('stock_advanced')
        bc.statut = 'RECU_TOTAL'
        bc.date_livraison_reelle = timezone.now().date()
        bc.save()
        
        reception_doc = StockPrintDocument.objects.create(
            kind='RECEPTION', document_date=timezone.localdate(), created_by=request.user,
            supplier=bc.fournisseur, bon_commande=bc,
            notes=f"Réception du bon de commande {bc.reference}; lots placés en attente de contrôle qualité.",
        )
        for ligne in bc.lignes.select_related('material').all():
            num_lot = f"LOT-{bc.reference}-{ligne.material.id}"
            lot = StockLot.objects.create(
                material=ligne.material, numero_lot=num_lot,
                date_reception=timezone.localdate(), fournisseur=bc.fournisseur,
                quantite_initiale=ligne.quantite_commandee, quantite_restante=0,
                prix_unitaire=ligne.prix_unitaire, statut='EN_ATTENTE', created_by=request.user,
            )
            movement = StockService.enregistrer_mouvement(
                type_mvt='ENTREE', material=ligne.material, quantite=ligne.quantite_commandee,
                lot=lot, user=request.user, motif=f"Réception BC {bc.reference}",
            )
            reception_doc.movements.add(movement)
            StockPrintDocumentLine.objects.create(
                document=reception_doc, material=ligne.material, movement=movement, lot=lot,
                quantity=ligne.quantite_commandee, unit_snapshot=ligne.material.unit,
                notes=f"Réception fournisseur — lot {num_lot}",
            )
            ligne.quantite_recue = ligne.quantite_commandee
            ligne.save(update_fields=['quantite_recue'])
        messages.success(request, f"📦 BC {bc.reference} réceptionné : mouvement enregistré et bon {reception_doc.reference} généré.")
        return redirect('stock_document_print', id=reception_doc.id)
    return redirect('stock_advanced')


@login_required
@module_required('stock')
def stock_daily_issue_create(request):
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    selected_date = _clean_iso_date(request.GET.get('date', '')) or timezone.localdate().isoformat()
    if request.method == 'POST':
        selected_date = _clean_iso_date(request.POST.get('date', ''))
        if not selected_date:
            messages.error(request, 'Date invalide.')
            return redirect('stock_daily_issue_create')
        document_date = parse_date(selected_date)
        with transaction.atomic():
            existing_doc = StockPrintDocument.objects.select_for_update().filter(
                kind='SORTIE_JOURNALIERE', document_date=document_date,
            ).order_by('id').first()
            movements = list(StockMovement.objects.select_for_update().filter(
                type='SORTIE', annule=False, date__date=document_date,
            ).exclude(print_documents__kind='SORTIE_JOURNALIERE')
             .select_related('material', 'lot', 'emplacement_source').distinct().order_by('date', 'id'))
            if not movements and existing_doc:
                messages.info(request, f"Le bon de sortie de cette journée existe déjà : {existing_doc.display_reference}.")
                return redirect('stock_document_print', id=existing_doc.id)
            if not movements:
                messages.warning(request, 'Aucun mouvement de type Sortie à consolider à cette date. Les entrées et retours ne sont pas des sorties.')
                return render(request, 'stock/document_form.html', {'mode': 'daily', 'selected_date': selected_date, 'pending_count': 0})
            doc = existing_doc or StockPrintDocument.objects.create(
                kind='SORTIE_JOURNALIERE', document_date=document_date,
                created_by=request.user, notes=(request.POST.get('notes') or '').strip(),
            )
            if existing_doc and request.POST.get('notes'):
                doc.notes = request.POST.get('notes').strip()
                doc.save(update_fields=['notes'])
            doc.movements.add(*movements)
            for movement in movements:
                StockPrintDocumentLine.objects.create(
                    document=doc, material=movement.material, movement=movement,
                    lot=movement.lot, emplacement=movement.emplacement_source,
                    quantity=movement.quantite, unit_snapshot=movement.material.unit,
                    notes=movement.motif or '',
                )
        messages.success(request, f"Bon de sortie {doc.display_reference} consolidé : {doc.movements.count()} mouvement(s) au total.")
        return redirect('stock_document_print', id=doc.id)
    selected_day = parse_date(selected_date)
    pending_count = StockMovement.objects.filter(type='SORTIE', annule=False, date__date=selected_day).exclude(print_documents__kind='SORTIE_JOURNALIERE').distinct().count()
    return render(request, 'stock/document_form.html', {'mode': 'daily', 'selected_date': selected_date, 'pending_count': pending_count})


@login_required
@module_required('stock')
def stock_receipt_create(request):
    """Consolide les entrées manuelles d’une journée en un seul bon de réception."""
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    locations = StockLocation.objects.filter(is_active=True).order_by('name')
    selected_date = _clean_iso_date(request.GET.get('date', '')) or timezone.localdate().isoformat()
    if request.method == 'POST':
        selected_date = _clean_iso_date(request.POST.get('date', ''))
        if not selected_date:
            messages.error(request, 'Date invalide.')
            return redirect('stock_receipt_create')
        fallback_location = None
        if request.POST.get('emplacement_reception'):
            fallback_location = StockLocation.objects.filter(pk=request.POST.get('emplacement_reception'), is_active=True).first()
            if not fallback_location:
                messages.error(request, 'Emplacement de réception invalide.')
                return redirect('stock_receipt_create')
        document_date = parse_date(selected_date)
        with transaction.atomic():
            existing_doc = StockPrintDocument.objects.select_for_update().filter(
                kind='RECEPTION', document_date=document_date, bon_commande__isnull=True,
                notes__startswith='Réceptions manuelles consolidées',
            ).order_by('id').first()
            movements = list(StockMovement.objects.select_for_update().filter(
                type='ENTREE', annule=False, date__date=document_date,
            ).exclude(print_documents__kind='RECEPTION')
             .select_related('material', 'material__supplier', 'lot', 'emplacement_destination').distinct().order_by('date', 'id'))
            if existing_doc and fallback_location:
                updated = existing_doc.lines.filter(emplacement__isnull=True).update(emplacement=fallback_location)
                if updated:
                    messages.success(request, f"{updated} ligne(s) sans emplacement mises à jour avec {fallback_location.name}.")
            if not movements and existing_doc:
                messages.info(request, f"Le bon de réception de cette journée existe déjà : {existing_doc.reference}.")
                return redirect('stock_document_print', id=existing_doc.id)
            if not movements:
                messages.warning(request, 'Aucune entrée manuelle à consolider à cette date. Une réception de BC possède déjà son propre bon.')
                return render(request, 'stock/document_form.html', {'mode': 'receipt', 'selected_date': selected_date, 'pending_count': 0, 'locations': locations})
            doc = existing_doc or StockPrintDocument.objects.create(
                kind='RECEPTION', document_date=document_date, created_by=request.user,
                notes='Réceptions manuelles consolidées' + (f" — {request.POST.get('notes').strip()}" if request.POST.get('notes') else ' pour la journée.'),
            )
            if existing_doc and request.POST.get('notes'):
                doc.notes = 'Réceptions manuelles consolidées — ' + request.POST.get('notes').strip()
                doc.save(update_fields=['notes'])
            doc.movements.add(*movements)
            suppliers = set()
            for movement in movements:
                supplier_id_for_line = movement.lot.fournisseur_id if movement.lot_id and movement.lot.fournisseur_id else movement.material.supplier_id
                if supplier_id_for_line:
                    suppliers.add(supplier_id_for_line)
            if existing_doc:
                suppliers.update(doc.lines.filter(lot__fournisseur__isnull=False).values_list('lot__fournisseur_id', flat=True))
                suppliers.update(doc.lines.filter(material__supplier__isnull=False).values_list('material__supplier_id', flat=True))
            supplier_id = next(iter(suppliers)) if len(suppliers) == 1 else None
            if doc.supplier_id != supplier_id:
                doc.supplier_id = supplier_id
                doc.save(update_fields=['supplier'])
            for movement in movements:
                StockPrintDocumentLine.objects.create(
                    document=doc, material=movement.material, movement=movement,
                    lot=movement.lot, emplacement=movement.emplacement_destination or fallback_location,
                    quantity=movement.quantite, unit_snapshot=movement.material.unit,
                    notes=movement.motif or '',
                )
        messages.success(request, f"Bon de réception {doc.reference} consolidé : {doc.movements.count()} entrée(s) au total.")
        return redirect('stock_document_print', id=doc.id)
    selected_day = parse_date(selected_date)
    pending_count = StockMovement.objects.filter(type='ENTREE', annule=False, date__date=selected_day).exclude(print_documents__kind='RECEPTION').distinct().count()
    return render(request, 'stock/document_form.html', {'mode': 'receipt', 'selected_date': selected_date, 'pending_count': pending_count, 'locations': locations})


@login_required
@module_required('stock')
def stock_return_create(request):
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    materials = Material.objects.filter(is_archived=False).order_by('name')
    lots = StockLot.objects.select_related('material').filter(quantite_restante__gt=0).order_by('material__name', '-date_reception')
    locations = StockLocation.objects.filter(is_active=True).order_by('name')
    suppliers = Supplier.objects.filter(is_archived=False).order_by('name')
    if request.method == 'POST':
        try:
            kind = request.POST.get('kind')
            if kind not in {'RETOUR_INTERNE', 'RETOUR_FOURNISSEUR'}:
                raise ValueError('Type de retour invalide.')
            universe = request.POST.get('universe', '')
            if universe not in {'FILM', 'INK', 'GLUE', 'SOLV'}:
                raise ValueError('Choisissez un univers valide.')
            material = get_object_or_404(Material, pk=request.POST.get('material'), is_archived=False)
            if material.category != universe:
                raise ValueError('L’article sélectionné ne correspond pas à l’univers choisi.')
            characteristics = _document_characteristics(request.POST, material.category)
            quantity = _positive_float(request.POST.get('quantity'), 'Quantité')
            lot = StockLot.objects.filter(pk=request.POST.get('lot'), material=material).first() if request.POST.get('lot') else None
            src = StockLocation.objects.filter(pk=request.POST.get('src'), is_active=True).first() if request.POST.get('src') else None
            dst = StockLocation.objects.filter(pk=request.POST.get('dst'), is_active=True).first() if request.POST.get('dst') else None
            if kind == 'RETOUR_FOURNISSEUR' and not lot:
                raise ValueError('Pour un retour fournisseur, sélectionnez le lot concerné.')
            if kind == 'RETOUR_INTERNE' and not dst:
                raise ValueError('Sélectionnez l’emplacement magasin de destination du retour interne.')
            reason = (request.POST.get('notes') or '').strip()
            if not reason:
                raise ValueError('Le motif du retour est obligatoire.')
            with transaction.atomic():
                if kind == 'RETOUR_INTERNE' and not lot:
                    lot = StockLot.objects.create(
                        material=material,
                        numero_lot=f"RETOUR-{material.code or material.pk}-{timezone.now():%Y%m%d-%H%M%S-%f}",
                        date_reception=timezone.localdate(), fournisseur=material.supplier,
                        emplacement=dst, quantite_initiale=quantity, quantite_restante=0,
                        prix_unitaire=material.price_per_unit, statut='CONFORME',
                        created_by=request.user, notes='Lot créé lors du retour interne depuis l’atelier.',
                    )
                doc = StockPrintDocument.objects.create(
                    kind=kind, document_date=timezone.localdate(), created_by=request.user,
                    supplier=(Supplier.objects.filter(pk=request.POST.get('supplier')).first() if kind == 'RETOUR_FOURNISSEUR' and request.POST.get('supplier') else material.supplier),
                    notes=reason,
                )
                movement = StockService.enregistrer_mouvement(
                    type_mvt='RETOUR_INTERNE' if kind == 'RETOUR_INTERNE' else 'RETOUR',
                    material=material, quantite=quantity, lot=lot,
                    src=src, dst=dst, user=request.user,
                    motif=f"{doc.get_kind_display()} {doc.reference}: {reason}",
                    laize_mm=characteristics['laize_mm_snapshot'],
                    micronage=characteristics['micronage_snapshot'],
                    metrage=characteristics['metrage'], poids_kg=characteristics['poids_kg'],
                )
                doc.movements.add(movement)
                StockPrintDocumentLine.objects.create(
                    document=doc, material=material, movement=movement, lot=lot,
                    emplacement=dst if kind == 'RETOUR_INTERNE' else src,
                    quantity=quantity, unit_snapshot=material.unit, notes=reason,
                    **characteristics,
                )
            return redirect('stock_document_print', id=doc.id)
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, 'stock/document_form.html', {
        'mode': 'return', 'materials': materials, 'lots': lots,
        'locations': locations, 'suppliers': suppliers,
        'selected_universe': request.POST.get('universe', '') if request.method == 'POST' else '',
    })


@login_required
@module_required('stock')
def stock_damage_create(request):
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    materials = Material.objects.filter(is_archived=False).order_by('name')
    lots = StockLot.objects.select_related('material').filter(quantite_restante__gt=0).order_by('material__name', '-date_reception')
    locations = StockLocation.objects.filter(is_active=True).order_by('name')
    if request.method == 'POST':
        try:
            universe = request.POST.get('universe', '')
            if universe not in {'FILM', 'INK', 'GLUE', 'SOLV'}:
                raise ValueError('Choisissez un univers valide.')
            material = get_object_or_404(Material, pk=request.POST.get('material'), is_archived=False)
            if material.category != universe:
                raise ValueError('L’article sélectionné ne correspond pas à l’univers choisi.')
            characteristics = _document_characteristics(request.POST, material.category)
            quantity = _positive_float(request.POST.get('quantity'), 'Quantité')
            lot = StockLot.objects.filter(pk=request.POST.get('lot'), material=material).first() if request.POST.get('lot') else None
            location = StockLocation.objects.filter(pk=request.POST.get('location'), is_active=True).first() if request.POST.get('location') else None
            reason = (request.POST.get('notes') or '').strip()
            if not reason:
                raise ValueError('La description de l’avarie est obligatoire.')
            with transaction.atomic():
                if not lot:
                    lot = next((candidate for candidate in material.get_fefo_lots() if lot_available_quantity_for_of(candidate, None) + 1e-6 >= float(quantity)), None)
                doc = StockPrintDocument.objects.create(kind='AVARIE', document_date=timezone.localdate(), created_by=request.user, notes=reason)
                movement = StockService.enregistrer_mouvement(
                    type_mvt='PERTE', material=material, quantite=quantity, lot=lot,
                    src=location, user=request.user,
                    motif=f"Avarie {doc.reference}: {reason}",
                    laize_mm=characteristics['laize_mm_snapshot'],
                    micronage=characteristics['micronage_snapshot'],
                    metrage=characteristics['metrage'], poids_kg=characteristics['poids_kg'],
                )
                doc.movements.add(movement)
                StockPrintDocumentLine.objects.create(
                    document=doc, material=material, movement=movement, lot=lot, emplacement=location,
                    quantity=quantity, unit_snapshot=material.unit, notes=reason,
                    **characteristics,
                )
            return redirect('stock_document_print', id=doc.id)
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, 'stock/document_form.html', {'mode': 'damage', 'materials': materials, 'lots': lots, 'locations': locations, 'selected_universe': request.POST.get('universe', '') if request.method == 'POST' else ''})


@login_required
@module_required('stock')
def stock_document_print(request, id):
    document = get_object_or_404(
        StockPrintDocument.objects.select_related('created_by', 'supplier', 'bon_commande')
        .prefetch_related('lines__material', 'lines__lot', 'lines__emplacement', 'lines__movement', 'movements'),
        pk=id,
    )
    lines = list(document.lines.select_related(
        'material', 'material__depot', 'lot', 'emplacement', 'movement',
        'movement__machine', 'movement__emplacement_destination',
    ).order_by('id'))
    if document.kind == 'RECEPTION':
        unique_lines = []
        seen_movements = set()
        for line in lines:
            if line.movement_id and line.movement_id in seen_movements:
                continue
            if line.movement_id:
                seen_movements.add(line.movement_id)
            unique_lines.append(line)
        lines = unique_lines
    return render(request, 'stock/document_print.html', {'document': document, 'lines': lines})


@login_required
@module_required('stock')
def stock_documents_list(request):
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    kind = request.GET.get('kind', '')
    valid_kinds = {value for value, _label in StockPrintDocument.KIND_CHOICES}
    date_from = _clean_iso_date(request.GET.get('date_from'))
    date_to = _clean_iso_date(request.GET.get('date_to'))
    query = (request.GET.get('q') or '').strip()[:100]
    documents = StockPrintDocument.objects.select_related('created_by', 'supplier', 'bon_commande').prefetch_related('lines').order_by('-document_date', '-id')
    if kind in valid_kinds:
        documents = documents.filter(kind=kind)
    else:
        kind = ''
    if date_from:
        documents = documents.filter(document_date__gte=date_from)
    if date_to:
        documents = documents.filter(document_date__lte=date_to)
    if query:
        documents = documents.filter(
            Q(reference__icontains=query) | Q(supplier__name__icontains=query)
            | Q(bon_commande__reference__icontains=query)
            | Q(lines__material__name__icontains=query)
            | Q(lines__material__code__icontains=query)
        ).distinct()
    page = Paginator(documents, 30).get_page(request.GET.get('page'))
    return render(request, 'stock/documents_list.html', {
        'documents': page, 'page_obj': page, 'kind_filter': kind,
        'date_from': date_from or '', 'date_to': date_to or '', 'query': query,
        'kind_choices': StockPrintDocument.KIND_CHOICES,
    })


# ===========================================================================
# --- AUTRES CONFIGURATIONS, EXPORTS ET GRAPHES ---
# ===========================================================================

@login_required
@module_required('stock')
def seuil_update(request, material_id):
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    material = get_object_or_404(Material, id=material_id)
    if request.method == 'POST':
        seuil, _ = StockSeuil.objects.get_or_create(
            material=material,
            defaults={'consommation_journaliere_moy': 0, 'delai_fournisseur_jours': 7}
        )
        conso = parse_float(request.POST.get('conso_jour', 0), minimum=0)
        delai = parse_int(request.POST.get('delai_jours', 7), minimum=0, maximum=3650)
        securite = parse_int(request.POST.get('securite_jours', 3), minimum=0, maximum=3650)
        if conso is None or delai is None or securite is None:
            messages.error(request, "❌ Valeurs invalides.")
            return redirect('stock_advanced')
        seuil.consommation_journaliere_moy = conso
        seuil.delai_fournisseur_jours = delai
        seuil.stock_securite_jours = securite
        seuil.save()
        messages.success(request, f"🔮 Paramètres prévisionnels mis à jour pour {material.name}.")
    return redirect('stock_advanced')


@login_required
@module_required('stock')
def location_add(request):
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        type_loc = request.POST.get('type', 'GENERAL')
        desc = request.POST.get('description', '')
        if name:
            StockLocation.objects.create(name=name, type=type_loc, description=desc)
            messages.success(request, f"Emplacement « {name} » créé.")
    return redirect('stock_advanced')


@login_required
@module_required('stock')
def location_delete(request, id):
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    loc = get_object_or_404(StockLocation, id=id)
    if request.method == 'POST':
        loc.delete()
        messages.success(request, "Emplacement supprimé.")
    return redirect('stock_advanced')


@login_required
@module_required('stock')
def add_supplier(request):
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        if name:
            supplier = Supplier.objects.create(name=name, email=email)
            contact_noms = request.POST.getlist('contact_nom[]')
            contact_postes = request.POST.getlist('contact_poste[]')
            contact_telephones = request.POST.getlist('contact_telephone[]')
            contact_emails = request.POST.getlist('contact_email[]')
            for i in range(len(contact_noms)):
                nom = contact_noms[i].strip() if i < len(contact_noms) else ''
                if nom:
                    SupplierContact.objects.create(
                        supplier=supplier,
                        nom=nom,
                        poste=contact_postes[i].strip() if i < len(contact_postes) else '',
                        telephone=contact_telephones[i].strip() if i < len(contact_telephones) else '',
                        email=contact_emails[i].strip() if i < len(contact_emails) else ''
                    )
            messages.success(request, '✅ Fournisseur ajouté avec succès !')
            return redirect('stock_advanced')
    return redirect('stock_advanced')


@login_required
@module_required('stock')
def edit_supplier(request, id):
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    supplier = get_object_or_404(Supplier, id=id)
    if request.method == 'POST':
        supplier.name = request.POST.get('name', supplier.name)
        supplier.email = request.POST.get('email', supplier.email)
        supplier.save()
        messages.success(request, f'✅ Fournisseur "{supplier.name}" modifié !')
        return redirect('stock_advanced')
    return redirect('stock_advanced')


@login_required
@module_required('stock')
def delete_supplier(request, id):
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    supplier = get_object_or_404(Supplier, id=id)
    if request.method == 'POST':
        supplier.is_archived = True
        supplier.save()
        messages.success(request, f'🗑️ Fournisseur "{supplier.name}" archivé.')
    return redirect('stock_advanced')


@login_required
@module_required('stock', 'dashboard')
def stock_dashboard_data(request):
    critiques = []
    for m in Material.objects.filter(is_archived=False):
        if float(m.quantity or 0) <= float(m.min_threshold or 0):
            critiques.append({
                'name': m.name, 
                'stock': float(m.quantity or 0), 
                'seuil': m.min_threshold
            })
    return JsonResponse({'critiques': critiques})


@login_required
@module_required('stock', 'crm', 'prepress', 'production', 'planification')
def material_search_api(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 1:
        return JsonResponse([], safe=False)

    materials = Material.objects.filter(is_archived=False).filter(
        Q(name__icontains=query) | Q(code__icontains=query)
    )[:10]

    results = []
    for m in materials:
        results.append({
            'id': m.id,
            'name': m.name,
            'code': m.code,
            'stock': m.usable_quantity,
            'unit': m.unit,
            'thickness': m.thickness_or_grammage_display,
            'metrage': m.metrage_display
        })
    return JsonResponse(results, safe=False)


def _stock_header_key(value):
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]', '', text)


def _find_six_column_stock_header(ws):
    """Repère les en-têtes du classeur utilisateur, même sous un titre fusionné."""
    for row_idx in range(1, min(ws.max_row, 15) + 1):
        found = {}
        for col_idx in range(1, ws.max_column + 1):
            h = _stock_header_key(ws.cell(row=row_idx, column=col_idx).value)
            if ('produit' in h and (h.startswith('n') or h.startswith('numero') or h.startswith('code'))) and 'designation' not in h:
                found['code'] = col_idx
            elif 'designation' in h or h in {'libelle', 'nomarticle'}:
                found['name'] = col_idx
            elif h in {'unite', 'unit'}:
                found['unit'] = col_idx
            elif h in {'depot', 'magasin'}:
                found['depot'] = col_idx
            elif h in {'famille', 'family'}:
                found['family'] = col_idx
            elif h in {'sousfamille', 'subfamily'}:
                found['subfamily'] = col_idx
            elif 'fournisseur' in h or h == 'supplier':
                found['supplier'] = col_idx
            elif 'categorie' in h or h == 'category':
                found['category'] = col_idx
            elif 'micronage' in h or 'grammage' in h:
                found['mic_gram'] = col_idx
            elif 'metrage' in h:
                found['metrage'] = col_idx
            elif 'laize' in h:
                found['laize'] = col_idx
            elif h.startswith('origine') or h == 'origin':
                found['origin'] = col_idx
            elif 'poids' in h or h == 'weight':
                found['weight'] = col_idx
            elif 'nombreunite' in h or h in {'nbunites', 'unites'}:
                found['units_count'] = col_idx
            elif h.startswith('stockinitial') or h == 'initialquantity':
                found['initial_quantity'] = col_idx
            elif h.startswith('stockreel') or h in {'quantity', 'stockactuel'}:
                found['quantity'] = col_idx
            elif h.startswith('seuilmin') or h in {'seuilminimum', 'minthreshold'}:
                found['threshold'] = col_idx
            elif h.startswith('prixunitaire') or h in {'prixu', 'priceperunit'}:
                found['price'] = col_idx
        if all(k in found for k in ('code', 'name', 'unit', 'depot', 'family', 'subfamily')):
            return row_idx, found
    return None, None


def _catalog_option_from_import(kind, raw_value):
    name = str(raw_value or '').strip()
    if not name:
        return None
    key = _stock_header_key(name)
    for option in StockCatalogOption.objects.filter(kind=kind):
        if _stock_header_key(option.name) == key:
            if not option.active:
                option.active = True
                option.save(update_fields=['active'])
            return option
    # L'import Stock est déjà réservé aux responsables (can_manage_stock).
    # Une valeur du classeur absente du catalogue est ajoutée pour garder les deux synchronisés.
    position = StockCatalogOption.objects.filter(kind=kind).count()
    return StockCatalogOption.objects.create(kind=kind, name=name, position=position, active=True)


# ===========================================================================
# --- STATION D'IMPORTATION EXCEL ET FORMATS ---
# ===========================================================================

@login_required
@module_required('import', 'stock')
def import_stock_view(request):
    if not can_manage_stock(request.user):
        return _refuse_manage(request)
    crm_users = User.objects.filter(is_active=True).order_by('first_name', 'username')
    if request.method != 'POST':
        return render(request, 'stock/import_stock.html', {'crm_users': crm_users})

    import_type = request.POST.get('import_type', 'MOUVEMENTS')
    excel_file = request.FILES.get('excel_file')

    if not excel_file:
        messages.error(request, "❌ Veuillez sélectionner un fichier Excel.")
        return render(request, 'stock/import_stock.html', {'crm_users': crm_users})

    try:
        validate_upload(excel_file, IMPORT_EXTENSIONS, IMPORT_MAX_BYTES)
    except ValueError as exc:
        messages.error(request, f"❌ {exc}")
        return render(request, 'stock/import_stock.html', {'crm_users': crm_users})

    details = []
    success_count = 0
    error_count = 0

    try:
        wb = openpyxl.load_workbook(excel_file, data_only=True)
        ws = wb.worksheets[0]
        details.append(f"📄 Analyse : « {ws.title} » ({ws.max_row} lignes)")
        if ws.max_row > IMPORT_MAX_ROWS:
            raise ValueError(f"Fichier trop volumineux : {IMPORT_MAX_ROWS} lignes maximum.")

        if import_type == 'MOUVEMENTS':
            for row_idx in range(2, ws.max_row + 1):
                raw_date = ws.cell(row=row_idx, column=1).value
                raw_machine = ws.cell(row=row_idx, column=2).value
                raw_produit = ws.cell(row=row_idx, column=3).value
                raw_quantite = ws.cell(row=row_idx, column=4).value
                raw_code = ws.cell(row=row_idx, column=5).value
                raw_notes = ws.cell(row=row_idx, column=6).value

                if not raw_produit and not raw_code:
                    continue

                try:
                    qte_val = abs(float(raw_quantite or 0))
                    if qte_val == 0:
                        continue
                    
                    mat = Material.objects.filter(code=raw_code).first() or Material.objects.filter(name=raw_produit).first()
                    if not mat:
                        mat = Material.objects.create(
                            name=raw_produit or f"Import-{raw_code}", code=raw_code or '',
                            category='INK', quantity=0, min_threshold=50
                        )
                        details.append(f"Ligne {row_idx} : 🆕 Nouvelle matière créée « {mat.name} »")

                    StockService.enregistrer_mouvement(
                        type_mvt='SORTIE', material=mat, quantite=qte_val,
                        user=request.user, motif=f"Import Excel : {raw_notes or ''}"
                    )
                    success_count += 1
                except Exception as row_err:
                    error_count += 1
                    details.append(f"Ligne {row_idx} : ❌ Erreur ({str(row_err)})")

        elif import_type == 'STOCK':
            header_row, cols = _find_six_column_stock_header(ws)
            if header_row:
                details.append(f"✅ Format articles reconnu (en-têtes ligne {header_row}, 6 colonnes).")
                for row_idx in range(header_row + 1, ws.max_row + 1):
                    code_raw = ws.cell(row=row_idx, column=cols['code']).value
                    name_raw = ws.cell(row=row_idx, column=cols['name']).value
                    if not code_raw and not name_raw:
                        continue
                    try:
                        code = str(code_raw).strip() if code_raw is not None else ''
                        # Excel peut livrer un code numérique comme 123.0; éviter le suffixe .0.
                        if isinstance(code_raw, float) and code_raw.is_integer():
                            code = str(int(code_raw))
                        name = str(name_raw or '').strip()
                        if not code or not name:
                            raise ValueError('N°.Produit et Désignation sont obligatoires.')
                        unit_name = str(ws.cell(row=row_idx, column=cols['unit']).value or '').strip()
                        depot_name = str(ws.cell(row=row_idx, column=cols['depot']).value or '').strip()
                        family_name = str(ws.cell(row=row_idx, column=cols['family']).value or '').strip()
                        subfamily_name = str(ws.cell(row=row_idx, column=cols['subfamily']).value or '').strip()
                        if not all([unit_name, depot_name, family_name]):
                            raise ValueError('N°.Produit, Désignation, Unité, Dépôt et Famille sont obligatoires; Sous Famille peut rester vide.')
                        unit_opt = _catalog_option_from_import('UNIT', unit_name)
                        depot_opt = _catalog_option_from_import('DEPOT', depot_name)
                        family_opt = _catalog_option_from_import('FAMILY', family_name)
                        subfamily_opt = _catalog_option_from_import('SUBFAMILY', subfamily_name) if subfamily_name else None
                        def optional_number(key, default=None):
                            if key not in cols:
                                return default
                            raw = ws.cell(row=row_idx, column=cols[key]).value
                            if raw is None or str(raw).strip() == '':
                                return default
                            try:
                                return float(str(raw).replace(',', '.'))
                            except (TypeError, ValueError):
                                raise ValueError(f"Valeur numérique invalide dans la colonne {key}.")
                        mic_gram = optional_number('mic_gram', None)
                        metrage = optional_number('metrage', None)
                        laize_value = optional_number('laize', None)
                        weight_value = optional_number('weight', None)
                        units_value = optional_number('units_count', None)
                        origin_raw = str(ws.cell(row=row_idx, column=cols['origin']).value or '').strip() if 'origin' in cols else ''
                        origin_key = _stock_header_key(origin_raw)
                        if origin_raw and origin_key not in {'importation', 'importe', 'local', 'locale'}:
                            raise ValueError('Origine invalide : choisissez Importation ou Local.')
                        origin_value = 'IMPORTATION' if origin_key in {'importation', 'importe'} else ('LOCAL' if origin_key in {'local', 'locale'} else '')
                        designation_key = _stock_header_key(name)
                        family_key = _stock_header_key(family_opt.name)
                        category_raw = ws.cell(row=row_idx, column=cols['category']).value if 'category' in cols else None
                        category_key = _stock_header_key(category_raw)
                        is_paper = any(token in designation_key + family_key + category_key for token in ('papier', 'kraft', 'couche'))
                        if mic_gram is not None and is_paper:
                            grammage_value, micronage_value = mic_gram, None
                        else:
                            micronage_value = int(mic_gram) if mic_gram is not None else None
                            grammage_value = None
                        if laize_value is not None and not laize_value.is_integer():
                            raise ValueError('La laize doit être un nombre entier en millimètres.')
                        if units_value is not None and not units_value.is_integer():
                            raise ValueError('Le nombre d’unités doit être un entier.')
                        material = Material.objects.filter(code__iexact=code).first()
                        if material:
                            material.name = name
                            material.unit = unit_opt.name
                            material.depot = depot_opt
                            material.famille = family_opt
                            material.sous_famille = subfamily_opt
                            update_fields = ['name', 'unit', 'depot', 'famille', 'sous_famille']
                            for field_name, val in [('micronage_standard', micronage_value), ('grammage', grammage_value), ('metrage_standard', metrage), ('laize_mm', laize_value), ('origine', origin_value), ('poids_kg', weight_value), ('nombre_unites', units_value)]:
                                if field_name in {'micronage_standard', 'grammage'}:
                                    should_update = mic_gram is not None
                                else:
                                    key = {'metrage_standard': 'metrage', 'laize_mm': 'laize', 'origine': 'origin', 'poids_kg': 'weight', 'nombre_unites': 'units_count'}.get(field_name)
                                    should_update = bool(key and key in cols and ws.cell(row=row_idx, column=cols[key]).value not in (None, ''))
                                if should_update:
                                    setattr(material, field_name, val)
                                    update_fields.append(field_name)
                            material.save(update_fields=update_fields)
                            details.append(f"Ligne {row_idx} : ↻ article {code} mis à jour; les quantités, seuils et prix ERP sont conservés.")
                        else:
                            family_key = _stock_header_key(family_opt.name)
                            family_category = 'INK' if family_key == 'encres' else ('GLUE' if family_key == 'colle' else ('SOLV' if family_key == 'solvants' else 'FILM'))
                            raw_category = ws.cell(row=row_idx, column=cols['category']).value if 'category' in cols else None
                            category_key = _stock_header_key(raw_category)
                            if category_key in {'encre', 'encres', 'ink'}:
                                technical_category = 'INK'
                            elif category_key in {'colle', 'glue'}:
                                technical_category = 'GLUE'
                            elif category_key in {'solvant', 'solvants', 'solv'}:
                                technical_category = 'SOLV'
                            elif category_key in {'film', 'filmpapier', 'papier'}:
                                technical_category = 'FILM'
                            else:
                                technical_category = family_category
                            initial_qty = optional_number('initial_quantity', 0) or 0
                            current_qty = optional_number('quantity', initial_qty) or 0
                            threshold = optional_number('threshold', 0) or 0
                            price = optional_number('price', 0) or 0
                            if any(value < 0 for value in (initial_qty, current_qty, threshold, price)):
                                raise ValueError('Stock initial, stock réel, seuil et prix doivent être positifs ou nuls.')
                            if any(value is not None and value < 0 for value in (mic_gram, metrage, laize_value, weight_value, units_value)):
                                raise ValueError('Les caractéristiques numériques doivent être positives ou nulles.')
                            supplier_value = str(ws.cell(row=row_idx, column=cols['supplier']).value or '').strip() if 'supplier' in cols else ''
                            supplier_obj = Supplier.objects.get_or_create(name=supplier_value)[0] if supplier_value else None
                            with transaction.atomic():
                                Material.objects.create(
                                    code=code, name=name, category=technical_category,
                                    unit=unit_opt.name, depot=depot_opt, famille=family_opt,
                                    sous_famille=subfamily_opt, quantity=0,
                                    initial_quantity=initial_qty, min_threshold=threshold,
                                    price_per_unit=price, supplier=supplier_obj,
                                    micronage_standard=micronage_value, grammage=grammage_value,
                                    metrage_standard=metrage, laize_mm=int(laize_value) if laize_value is not None else None,
                                    origine=origin_value, poids_kg=weight_value, nombre_unites=int(units_value) if units_value is not None else None,
                                )
                                if current_qty > 0:
                                    imported_material = Material.objects.get(code=code)
                                    import_lot = StockLot.objects.create(
                                        material=imported_material,
                                        numero_lot=f"IMPORT-{code}-{timezone.localdate():%Y%m%d}",
                                        date_reception=timezone.localdate(), fournisseur=supplier_obj,
                                        quantite_initiale=current_qty, quantite_restante=0,
                                        prix_unitaire=price, statut='CONFORME', created_by=request.user,
                                    )
                                    StockService.enregistrer_mouvement(
                                        type_mvt='ENTREE', material=imported_material, quantite=current_qty,
                                        lot=import_lot, user=request.user,
                                        motif=f"Import Excel initial — {code}",
                                    )
                                details.append(f"Ligne {row_idx} : 🆕 article {code} créé avec les données optionnelles du fichier.")
                        success_count += 1
                    except Exception as row_err:
                        error_count += 1
                        details.append(f"Ligne {row_idx} : ❌ {str(row_err)}")
            else:
                details.append('ℹ️ En-têtes Excel à 6 colonnes non détectés : lecture du format historique 11 colonnes.')
                for row_idx in range(2, ws.max_row + 1):
                    designation = ws.cell(row=row_idx, column=1).value
                    code_val = ws.cell(row=row_idx, column=2).value
                    fournisseur_name = ws.cell(row=row_idx, column=3).value
                    category = str(ws.cell(row=row_idx, column=4).value or '')
                    
                    # --- LECTURE DES COLONNES "Micronage / Grammage" (col 5) ET "Metrage (m)" (col 6) ---
                    mic_grm_val = ws.cell(row=row_idx, column=5).value
                    metrage = ws.cell(row=row_idx, column=6).value
                    
                    stock_initial = float(ws.cell(row=row_idx, column=7).value or 0)
                    qty_val = float(ws.cell(row=row_idx, column=8).value or stock_initial)
                    unit = ws.cell(row=row_idx, column=9).value or 'kg'
                    seuil = float(ws.cell(row=row_idx, column=10).value or 50)
                    prix = float(ws.cell(row=row_idx, column=11).value or 0)

                    if not designation:
                        continue

                    try:
                        supplier_obj = None
                        if fournisseur_name:
                            supplier_obj, _ = Supplier.objects.get_or_create(name=fournisseur_name)

                        mic_val = None
                        gram_val = None
                        if mic_grm_val is not None:
                            desig_upper = str(designation).upper()
                            cat_upper = str(category).upper()
                            if 'PAPIER' in desig_upper or 'KRAFT' in desig_upper or 'COUCH' in desig_upper or 'PAPIER' in cat_upper:
                                gram_val = float(mic_grm_val)
                            else:
                                mic_val = int(float(mic_grm_val))

                        met_val = float(metrage) if metrage else None
                        cat_code = 'FILM' if 'FILM' in str(category).upper() or 'PAPIER' in str(category).upper() else 'INK'

                        mat, created = Material.objects.get_or_create(
                            code=code_val,
                            defaults={
                                'name': designation, 
                                'category': cat_code,
                                'micronage_standard': mic_val,
                                'grammage': gram_val,
                                'metrage_standard': met_val,
                                'quantity': qty_val, 
                                'initial_quantity': stock_initial, 
                                'unit': unit,
                                'min_threshold': seuil, 
                                'price_per_unit': prix, 
                                'supplier': supplier_obj
                            }
                        )
                        if not created:
                            mat.quantity = qty_val
                            if mic_val is not None: mat.micronage_standard = mic_val
                            if gram_val is not None: mat.grammage = gram_val
                            if met_val is not None: mat.metrage_standard = met_val
                            mat.save()

                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        details.append(f"Ligne {row_idx} : ❌ {str(e)}")

        messages.success(request, f"🎉 Importation réussie : {success_count} ligne(s) ajoutée(s). {error_count} erreur(s).")
        return render(request, 'stock/import_stock.html', {'success': True, 'details': details, 'crm_users': crm_users})
    except ValueError as exc:
        return render(request, 'stock/import_stock.html', {'success': False, 'message': str(exc), 'crm_users': crm_users})
    except Exception:
        logger.exception('stock_import_failed')
        return render(request, 'stock/import_stock.html', {
            'success': False,
            'message': "Fichier illisible ou invalide. Détails dans les journaux du serveur.",
            'crm_users': crm_users,
        })


@login_required
@module_required('import', 'stock')
def download_template_stock(request):
    """Génère le modèle Excel de la liste d'articles demandé par l'utilisateur."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Liste des articles"
    ws.merge_cells('A1:R1')
    ws['A1'] = 'LISTE DES ARTICLES'
    ws['A1'].font = openpyxl.styles.Font(bold=True, color='FF0000', size=14)
    ws['A1'].alignment = openpyxl.styles.Alignment(horizontal='left')
    headers = ['N°.Produit', 'Désignation', 'Unité', 'Dépôt', 'Famille', 'Sous Famille', 'Micronage / Grammage (optionnel)', 'Laize (mm) (optionnel)', 'Origine (optionnel)', 'Métrage (m) (optionnel)', 'Poids (kg) (optionnel)', 'Nombre d’unités (optionnel)', 'Fournisseur (optionnel)', 'Catégorie (optionnel)', 'Stock_Initial (optionnel)', 'Stock_Reel (optionnel)', 'Seuil_Min (optionnel)', 'Prix_Unitaire (optionnel)']
    ws.append(headers)
    header_fill = openpyxl.styles.PatternFill('solid', fgColor='D9EAF7')
    for cell in ws[2]:
        cell.font = openpyxl.styles.Font(bold=True)
        cell.fill = header_fill
        cell.auto_filter = True
    ws.freeze_panes = 'A3'
    ws.auto_filter.ref = 'A2:R2'
    widths = [20, 60, 14, 20, 28, 32, 30, 18, 20, 20, 18, 24, 24, 24, 18, 18, 18, 20]
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(idx)].width = width
    # Feuille de référence pour faciliter la saisie et montrer les listes autorisées.
    lists = wb.create_sheet('Listes')
    for col, (kind, title) in enumerate(StockCatalogOption.KIND_CHOICES, start=1):
        lists.cell(row=1, column=col, value=title)
        for row_idx, option in enumerate(StockCatalogOption.objects.filter(kind=kind, active=True).order_by('position', 'name'), start=2):
            lists.cell(row=row_idx, column=col, value=option.name)
        lists.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 28
    lists.sheet_state = 'hidden'
    instructions = wb.create_sheet('Instructions')
    instructions.append(['Importer le fichier dans le module Stock'])
    instructions.append(['Colonnes obligatoires : N°.Produit, Désignation, Unité, Dépôt, Famille. Sous Famille et les colonnes 7 à 18 sont optionnelles.'])
    instructions.append(['La ligne de titre « LISTE DES ARTICLES » est facultative; l’import repère les en-têtes dans les 15 premières lignes.'])
    instructions.append(['Si le code existe déjà, les champs descriptifs sont mis à jour; le stock, les seuils et les prix ne changent pas.'])
    instructions.append(['Pour un nouvel article, les colonnes optionnelles renseignées sont importées; les quantités, seuil et prix non fournis valent 0. Les listes de référence sont complétées automatiquement si une valeur est absente.'])
    instructions.column_dimensions['A'].width = 115
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="template_stock_matieres.xlsx"'
    wb.save(response)
    return response


@login_required
@module_required('import', 'stock', 'production', 'prepress')
def download_template_special_prod(request):
    """Génère le bon template Excel complet à jour pour la Production Spéciale"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Template Prod"
    
    # En-têtes complets (18 colonnes)
    ws.append([
        'Date', 'Produit', 'Support', 'Qte_Lancee', 'Lot', 'Laize', 'Client', 
        'Equipe (A/B/C)', 'Machine', 'H_Debut', 'H_Fin', 'Prod_ML', 
        'Dec_Demarrage', 'Dec_Lisiere', 'Dec_Jonction', 'Dec_Transport', 
        'Prod_KG', 'Rebobinage_KG'
    ])
    
    # Ligne d'exemple
    ws.append([
        '2025-01-15', 'Sachet Pâtes 1Kg', 'BOPP 20', 500, 'L2025-01', 820, 
        'Client X', 'A', 'Flexo 1', '08:00', '16:00', 4500, 
        2.5, 3.0, 0.5, 1.0, 480, 0
    ])
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="template_production.xlsx"'
    wb.save(response)
    return response


@login_required
@module_required('stock')
def export_search_results(request):
    materials = Material.objects.filter(is_archived=False)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Stock"
    ws.append(['N°.Produit', 'Désignation', 'Unité', 'Dépôt', 'Famille', 'Sous Famille', 'Micronage / Grammage', 'Laize (mm)', 'Origine', 'Métrage (m)', 'Poids (kg)', 'Nombre d’unités', 'Fournisseur', 'Catégorie', 'Stock_Initial', 'Stock_Reel', 'Seuil_Min', 'Prix_Unitaire'])
    for m in materials.select_related('depot', 'famille', 'sous_famille', 'supplier'):
        mic_gram = m.micronage_standard if m.micronage_standard is not None else m.grammage
        ws.append([
            xl_safe(m.code), xl_safe(m.name), xl_safe(m.unit),
            xl_safe(m.depot.name if m.depot else ''), xl_safe(m.famille.name if m.famille else ''),
            xl_safe(m.sous_famille.name if m.sous_famille else ''), mic_gram,
            m.laize_mm, m.get_origine_display() if m.origine else '', m.metrage_standard,
            m.poids_kg, m.nombre_unites, xl_safe(m.supplier.name if m.supplier else ''),
            m.get_category_display(), m.initial_quantity, m.usable_quantity,
            m.min_threshold, m.price_per_unit,
        ])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="stock_matiere.xlsx"'
    wb.save(response)
    return response


@login_required
@module_required('stock')
def export_mouvements(request):
    mouvements = StockMovement.objects.select_related('material', 'lot', 'emplacement_source', 'emplacement_destination', 'utilisateur').all()
    mvt_from = request.GET.get('mvt_from')
    mvt_to = request.GET.get('mvt_to')
    mvt_type = request.GET.get('mvt_type')
    mvt_cat = request.GET.get('mvt_cat')
    mvt_loc = request.GET.get('mvt_loc')
    mvt_from, mvt_to, mvt_loc = _clean_iso_date(mvt_from), _clean_iso_date(mvt_to), _clean_int_str(mvt_loc)
    mvt_q = request.GET.get('mvt_q')
    mvt_annules = request.GET.get('mvt_annules') == '1'

    if not mvt_annules:
        mouvements = mouvements.filter(annule=False)
    if mvt_from:
        mouvements = mouvements.filter(date__date__gte=mvt_from)
    if mvt_to:
        mouvements = mouvements.filter(date__date__lte=mvt_to)
    if mvt_type:
        mouvements = mouvements.filter(type=mvt_type)
    if mvt_cat:
        mouvements = mouvements.filter(material__category=mvt_cat)
    if mvt_loc:
        mouvements = mouvements.filter(Q(emplacement_source_id=mvt_loc) | Q(emplacement_destination_id=mvt_loc))
    if mvt_q:
        mouvements = mouvements.filter(Q(material__name__icontains=mvt_q) | Q(lot__numero_lot__icontains=mvt_q))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Mouvements Stock"
    ws.append(['Date', 'Type', 'Matière', 'Code', 'Lot', 'Quantité (kg)', 'Source', 'Destination', 'Machine', 'OF', 'Utilisateur', 'Motif', 'Annulé'])
    for mv in mouvements:
        ws.append([
            mv.date.strftime('%d/%m/%Y %H:%M') if mv.date else '',
            mv.get_type_display(),
            xl_safe(mv.material.name) if mv.material else '',
            xl_safe(mv.material.code) if mv.material else '',
            xl_safe(mv.lot.numero_lot) if mv.lot else '',
            mv.quantite,
            xl_safe(mv.emplacement_source.name) if mv.emplacement_source else '',
            xl_safe(mv.emplacement_destination.name) if mv.emplacement_destination else '',
            xl_safe(mv.machine.name) if mv.machine else '',
            xl_safe(str(mv.of)) if mv.of else '',
            xl_safe(mv.utilisateur.username) if mv.utilisateur else '',
            xl_safe(mv.motif or ''),
            'OUI' if mv.annule else 'NON'
        ])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="journal_mouvements.xlsx"'
    wb.save(response)
    return response


# ===========================================================================
# --- API SCANNER IA (AVEC SÉCURISATION & JOURNALISATION) ---
# ===========================================================================

@login_required
@module_required('stock')
def scan_label_ai(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Requête POST requise.'}, status=400)

    if rate_limited(f'scan-label:{request.user.id}', 10, 60):
        return JsonResponse({'status': 'error', 'message': 'Trop de lectures, patientez une minute.'}, status=429)

    image_file = request.FILES.get('image')
    if not image_file:
        return JsonResponse({'status': 'error', 'message': 'Image manquante.'}, status=400)
    if image_file.size > LABEL_MAX_BYTES:
        return JsonResponse({'status': 'error', 'message': 'Image trop volumineuse (6 Mo maximum).'}, status=413)
    if (image_file.content_type or '') not in LABEL_IMAGE_TYPES:
        return JsonResponse({'status': 'error', 'message': 'Format refusé (JPEG, PNG ou WEBP).'}, status=400)

    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        return JsonResponse({'status': 'error', 'message': 'Module IA non configuré (Clé Gemini manquante).'}, status=400)

    try:
        image_bytes = image_file.read()
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        mime_type = image_file.content_type or 'image/jpeg'

        prompt = """
Analyse l'étiquette industrielle et renvoie UNIQUEMENT un JSON structuré :
{
  "fournisseur": "SunChemical" ou "GulfPack" ou "JPR" ou null,
  "material_name": "string complet",
  "category": "FILM" ou "INK" ou "GLUE" ou "SOLV",
  "numero_lot": "string ou null",
  "poids_net": number_kg ou null,
  "laize_width": number_mm ou null,
  "longueur_length": number_m ou null
}
Renvoie uniquement le format brut JSON, pas de balises markdown, pas de texte d'explication.
"""
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": image_b64}}
                ]
            }]
        }

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'x-goog-api-key': api_key}
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            res_body = json.loads(resp.read().decode('utf-8'))
            text_response = res_body['candidates'][0]['content']['parts'][0]['text'].strip()
            text_clean = re.sub(r'```json\s*|\s*```', '', text_response).strip().strip('`').strip()
            parsed_json = json.loads(text_clean)

            return JsonResponse({'status': 'success', 'data': parsed_json})
    except Exception:
        logger.exception('stock_scan_label_failed')
        return JsonResponse({'status': 'error', 'message': "Erreur IA. Détails dans les journaux du serveur."}, status=500)


# ===========================================================================
# --- STUBS COMPATIBILITÉ HISTORIQUE ---
# ===========================================================================

@login_required
def add_consommation(request):
    return redirect('stock_advanced')

@login_required
def conso_list_view(request):
    return redirect('stock_advanced')

@login_required
def location_list(request):
    return redirect('stock_advanced')

@login_required
def lot_list(request):
    return redirect('stock_advanced')

@login_required
@module_required('stock')
def stock_catalog_manage(request):
    """Administration sécurisée des listes déroulantes des articles stock."""
    if not can_manage_stock(request.user):
        messages.error(request, "Accès refusé : seuls les responsables stock peuvent gérer les listes.")
        return redirect('stock_advanced')
    if request.method == 'POST':
        action = request.POST.get('action', '')
        kind = request.POST.get('kind', '')
        if kind not in dict(StockCatalogOption.KIND_CHOICES):
            messages.error(request, 'Type de liste invalide.')
            return redirect('stock_catalog_manage')
        if action == 'add':
            name = (request.POST.get('name') or '').strip()
            if not name or len(name) > 120:
                messages.error(request, 'Saisissez un libellé valide (120 caractères maximum).')
            elif StockCatalogOption.objects.filter(kind=kind, name__iexact=name).exists():
                messages.error(request, 'Cette valeur existe déjà dans la liste.')
            else:
                StockCatalogOption.objects.create(kind=kind, name=name, position=(StockCatalogOption.objects.filter(kind=kind).count() + 1))
                messages.success(request, 'Valeur ajoutée.')
        elif action == 'toggle':
            option = get_object_or_404(StockCatalogOption, pk=request.POST.get('option_id'), kind=kind)
            option.active = not option.active
            option.save(update_fields=['active'])
            messages.success(request, 'Valeur réactivée.' if option.active else 'Valeur retirée des choix (historique conservé).')
        else:
            messages.error(request, 'Action invalide.')
        return redirect('stock_catalog_manage')
    sections = [{'key': kind, 'label': label, 'items': StockCatalogOption.objects.filter(kind=kind).order_by('position', 'name')} for kind, label in StockCatalogOption.KIND_CHOICES]
    return render(request, 'stock/catalog_manage.html', {'sections': sections})


@login_required
@module_required('stock')
def stock_kpi_view(request):
    """Vue de pilotage transversale du stock, achats, lots et mouvements."""
    today = timezone.localdate()
    start_raw = _clean_iso_date(request.GET.get('from', ''))
    end_raw = _clean_iso_date(request.GET.get('to', ''))
    date_from = parse_date(start_raw) if start_raw else today - timezone.timedelta(days=29)
    date_to = parse_date(end_raw) if end_raw else today
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    depot_filter = _clean_int_str(request.GET.get('depot', ''))
    family_filter = _clean_int_str(request.GET.get('family', ''))
    subfamily_filter = _clean_int_str(request.GET.get('subfamily', ''))
    micronage_filter = _clean_int_str(request.GET.get('micronage', ''))
    laize_filter = _clean_int_str(request.GET.get('laize', ''))
    origin_filter = request.GET.get('origin', '') if request.GET.get('origin', '') in {'IMPORTATION', 'LOCAL'} else ''
    grammage_raw = request.GET.get('grammage', '').strip()
    try:
        grammage_filter = float(grammage_raw.replace(',', '.')) if grammage_raw else ''
    except (TypeError, ValueError):
        grammage_filter = ''
    materials = Material.objects.filter(is_archived=False).select_related('supplier', 'depot', 'famille', 'sous_famille').annotate(usable_quantity_cached=Coalesce(Sum('lots__quantite_restante', filter=Q(lots__statut='CONFORME')), 0.0))
    if depot_filter:
        materials = materials.filter(depot_id=depot_filter)
    if family_filter:
        materials = materials.filter(famille_id=family_filter)
    if subfamily_filter:
        materials = materials.filter(sous_famille_id=subfamily_filter)
    if micronage_filter:
        materials = materials.filter(micronage_standard=micronage_filter)
    if grammage_filter != '':
        materials = materials.filter(grammage=grammage_filter)
    if laize_filter:
        materials = materials.filter(laize_mm=laize_filter)
    if origin_filter:
        materials = materials.filter(origine=origin_filter)

    material_rows = []
    rupture_count = critique_count = alerte_count = 0
    total_value = 0.0
    family_value = {}
    supplier_summary = {}
    for material in materials:
        usable = float(material.usable_quantity)
        threshold = float(material.min_threshold or 0)
        value = usable * float(material.price_per_unit or 0)
        total_value += value
        level = 'OK'
        if usable <= 0:
            level = 'RUPTURE'
            rupture_count += 1
        elif threshold > 0 and usable < threshold * 0.5:
            level = 'CRITIQUE'
            critique_count += 1
        elif threshold > 0 and usable <= threshold:
            level = 'ALERTE'
            alerte_count += 1
        material_rows.append((material, usable, value, level))
        family = material.famille.name if material.famille else 'Non classée'
        family_value[family] = family_value.get(family, 0.0) + value
        if material.supplier:
            entry = supplier_summary.setdefault(material.supplier_id, {'name': material.supplier.name, 'materials': 0, 'value': 0.0})
            entry['materials'] += 1
            entry['value'] += value

    materials_count = len(material_rows)
    alert_count = rupture_count + critique_count + alerte_count
    stock_value_rows = sorted(family_value.items(), key=lambda item: item[1], reverse=True)[:10]
    supplier_rows = sorted(supplier_summary.values(), key=lambda item: item['value'], reverse=True)[:10]

    movements = StockMovement.objects.filter(
        annule=False, date__date__gte=date_from, date__date__lte=date_to,
        material__in=materials,
    ).select_related('material', 'utilisateur', 'emplacement_source', 'emplacement_destination')
    movement_totals = {row['type']: int(row['total'] or 0) for row in movements.values('type').annotate(total=Count('id'))}
    movement_count = movements.count()
    unit_rows = movements.values('material__unit', 'type').annotate(total=Sum('quantite'), events=Count('id')).order_by('material__unit', 'type')
    movement_by_unit = {}
    for row in unit_rows:
        unit_name = row['material__unit'] or '—'
        movement_by_unit.setdefault(unit_name, {'unit': unit_name, 'entry': 0.0, 'exit': 0.0, 'events': 0})
        if row['type'] == 'ENTREE':
            movement_by_unit[unit_name]['entry'] += float(row['total'] or 0)
        elif row['type'] in ('SORTIE', 'PERTE', 'RETOUR'):
            movement_by_unit[unit_name]['exit'] += float(row['total'] or 0)
        movement_by_unit[unit_name]['events'] += int(row['events'] or 0)
    day_rows = movements.annotate(day=TruncDate('date')).values('day', 'type').annotate(total=Count('id')).order_by('day')
    daily = {}
    for row in day_rows:
        label = row['day'].strftime('%d/%m') if row['day'] else '—'
        daily.setdefault(label, {'ENTREE': 0, 'SORTIE': 0})
        if row['type'] == 'ENTREE':
            daily[label]['ENTREE'] += int(row['total'] or 0)
        elif row['type'] in ('SORTIE', 'PERTE', 'RETOUR'):
            daily[label]['SORTIE'] += int(row['total'] or 0)
    trend_labels = list(daily.keys())[-45:]
    entry_series = [daily[label]['ENTREE'] for label in trend_labels]
    exit_series = [daily[label]['SORTIE'] for label in trend_labels]
    recent_movements = movements.order_by('-date')[:12]

    location_rows = []
    for location in StockLocation.objects.filter(is_active=True).order_by('name'):
        lot_qs = StockLot.objects.filter(emplacement=location, material__in=materials, quantite_restante__gt=0)
        location_quantities = lot_qs.values('material__unit').annotate(total=Sum('quantite_restante')).order_by('material__unit')
        quantity_display = ', '.join(f"{float(row['total'] or 0):,.2f} {row['material__unit'] or '—'}" for row in location_quantities) or '0'
        location_rows.append({
            'name': location.name,
            'type': location.get_type_display(),
            'lots': lot_qs.count(),
            'quantity': quantity_display,
            'movements': movements.filter(Q(emplacement_source=location) | Q(emplacement_destination=location)).count(),
        })
    location_rows.sort(key=lambda item: (item['lots'], item['movements']), reverse=True)

    lot_status = StockLot.objects.filter(material__in=materials).values('statut').annotate(total=Count('id'))
    lots_by_status = {row['statut']: row['total'] for row in lot_status}
    da_qs = DemandeAchat.objects.filter(material__in=materials, date_creation__gte=date_from, date_creation__lte=date_to)
    bc_qs = BonCommande.objects.filter(date_commande__gte=date_from, date_commande__lte=date_to)
    if depot_filter or family_filter or subfamily_filter:
        bc_qs = bc_qs.filter(lignes__material__in=materials).distinct()
    purchase_amount = float(bc_qs.aggregate(total=Sum('montant_total'))['total'] or 0)
    open_orders = bc_qs.exclude(statut__in=['RECU_TOTAL', 'ANNULE']).count()
    purchase_status = list(bc_qs.values('statut').annotate(total=Count('id')).order_by('statut'))

    context = {
        'date_from': date_from.isoformat(), 'date_to': date_to.isoformat(),
        'depot_filter': depot_filter, 'family_filter': family_filter, 'subfamily_filter': subfamily_filter,
        'micronage_filter': micronage_filter, 'grammage_filter': grammage_filter, 'laize_filter': laize_filter, 'origin_filter': origin_filter,
        'micronage_options': Material.objects.filter(is_archived=False, micronage_standard__isnull=False).order_by('micronage_standard').values_list('micronage_standard', flat=True).distinct(),
        'grammage_options': Material.objects.filter(is_archived=False, grammage__isnull=False).order_by('grammage').values_list('grammage', flat=True).distinct(),
        'laize_options': Material.objects.filter(is_archived=False, laize_mm__isnull=False).order_by('laize_mm').values_list('laize_mm', flat=True).distinct(),
        'origine_options': Material.ORIGINE_CHOICES,
        'depot_options': StockCatalogOption.objects.filter(kind='DEPOT', active=True).order_by('position', 'name'),
        'family_options': StockCatalogOption.objects.filter(kind='FAMILY', active=True).order_by('position', 'name'),
        'subfamily_options': StockCatalogOption.objects.filter(kind='SUBFAMILY', active=True).order_by('position', 'name'),
        'materials_count': materials_count, 'alert_count': alert_count,
        'rupture_count': rupture_count, 'critique_count': critique_count, 'alerte_count': alerte_count,
        'stock_value': total_value, 'movement_count': movement_count,
        'entry_total': movement_totals.get('ENTREE', 0),
        'exit_total': sum(movement_totals.get(kind, 0) for kind in ('SORTIE', 'PERTE', 'RETOUR')),
        'transfer_total': movement_totals.get('TRANSFERT', 0), 'adjustment_total': movement_totals.get('AJUSTEMENT', 0),
        'movement_by_unit': sorted(movement_by_unit.values(), key=lambda item: item['unit']),
        'demand_count': da_qs.count(), 'demand_pending': da_qs.filter(statut='SOUMISE').count(),
        'open_orders': open_orders, 'purchase_amount': purchase_amount,
        'purchase_status': purchase_status, 'lots_by_status': lots_by_status,
        'family_labels': safe_json([row[0] for row in stock_value_rows]),
        'family_values': safe_json([round(row[1], 2) for row in stock_value_rows]),
        'supplier_rows': supplier_rows, 'location_rows': location_rows,
        'trend_labels': safe_json(trend_labels), 'entry_series': safe_json(entry_series),
        'exit_series': safe_json(exit_series), 'recent_movements': recent_movements,
        'top_alerts': sorted([{'material': m, 'quantity': q, 'value': v, 'level': level} for m, q, v, level in material_rows if level != 'OK'], key=lambda item: (item['quantity'], item['material'].name))[:10],
    }
    return render(request, 'stock/stock_kpi.html', context)
