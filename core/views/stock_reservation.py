from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from ..models import OrdreFabrication, Machine
from ..services.stock_reservation import reserve_fifo_partial, material_available_quantity
from core.decorators import module_required
from core.views.stock import StockService, can_manage_stock


def _can_edit_of_reservations(user):
    return user.is_superuser or user.has_perm('core.change_ordrefabrication')


@login_required
@module_required('stock')
def stock_reservations_overview(request):
    """Vue magasinier transversale: réservations actives et besoins OF non couverts."""
    if not can_manage_stock(request.user):
        raise PermissionDenied("Accès réservé aux gestionnaires du stock.")

    Reservation = apps.get_model('core', 'StockReservation')
    Requirement = apps.get_model('core', 'OFMaterialRequirement')
    query = (request.GET.get('q') or '').strip()
    active_qs = Reservation.objects.filter(status='ACTIVE').select_related(
        'lot', 'lot__material', 'requirement', 'requirement__material',
        'requirement__of', 'requirement__of__client', 'requirement__of__produit',
    ).order_by('lot__material__name', 'lot__date_reception', 'requirement__of__numero_of')
    shortage_qs = Requirement.objects.exclude(of__statut__in=['TERMINE', 'ANNULE']).select_related(
        'material', 'of', 'of__client', 'of__produit'
    ).order_by('material__name', 'of__numero_of')
    if query:
        active_qs = active_qs.filter(
            Q(lot__material__name__icontains=query) |
            Q(lot__numero_lot__icontains=query) |
            Q(requirement__of__numero_of__icontains=query) |
            Q(requirement__of__client__name__icontains=query)
        )
        shortage_qs = shortage_qs.filter(
            Q(material__name__icontains=query) |
            Q(of__numero_of__icontains=query) |
            Q(of__client__name__icontains=query)
        )

    reservations = list(active_qs[:1000])
    summary_by_material = {}
    for reservation in reservations:
        active = reservation.active_quantity
        reservation.active_quantity_ui = active
        material = reservation.requirement.material
        entry = summary_by_material.setdefault(material.pk, {
            'material': material, 'reserved': 0.0,
        })
        entry['reserved'] += active
    material_summary = []
    for entry in summary_by_material.values():
        material = entry['material']
        entry['physical'] = float(material.usable_quantity or 0)
        entry['free'] = material_available_quantity(material)
        material_summary.append(entry)
    material_summary.sort(key=lambda item: item['material'].name.lower())

    shortages = []
    for requirement in shortage_qs[:1000]:
        missing = requirement.missing_quantity
        if missing > 1e-6:
            requirement.missing_quantity_ui = missing
            shortages.append(requirement)

    return render(request, 'stock/reservations_overview.html', {
        'reservations': reservations,
        'material_summary': material_summary,
        'shortages': shortages,
        'search': query,
        'reservation_count': len(reservations),
        'shortage_count': len(shortages),
    })


@login_required
def of_stock_reservations(request, of_id):
    if not (_can_edit_of_reservations(request.user) or can_manage_stock(request.user)):
        raise PermissionDenied("Vous n'avez pas le droit de consulter les réservations d'OF.")
    OFMaterialRequirement = apps.get_model('core', 'OFMaterialRequirement')
    StockReservation = apps.get_model('core', 'StockReservation')
    of = get_object_or_404(OrdreFabrication.objects.select_related('client', 'produit'), pk=of_id)
    if request.method == 'POST':
        action = request.POST.get('action', 'reserve')
        try:
            if action == 'issue':
                if not can_manage_stock(request.user):
                    raise PermissionDenied('Droit de gestion de stock requis pour enregistrer une sortie.')
                reservation = get_object_or_404(StockReservation.objects.select_related('requirement__material', 'lot'), pk=request.POST.get('reservation_id'), requirement__of=of)
                try:
                    quantity = float(request.POST.get('quantity', '0'))
                except (TypeError, ValueError):
                    quantity = 0
                if quantity <= 0 or quantity > reservation.active_quantity + 1e-6:
                    raise ValidationError(f'La quantité de sortie doit être positive et ne pas dépasser la réservation active ({reservation.active_quantity:.3f}).')
                machine = get_object_or_404(Machine, pk=request.POST.get('machine_id'))
                StockService.enregistrer_mouvement(
                    type_mvt='SORTIE', material=reservation.requirement.material,
                    quantite=quantity, lot=reservation.lot, of=of, machine=machine,
                    user=request.user, motif=(request.POST.get('motif') or f'Sortie pour OF {of.numero_of}')[:200],
                )
                messages.success(request, f'Sortie de {quantity:.3f} {reservation.requirement.material.unit} enregistrée sur {reservation.lot.numero_lot}; réservation consommée.')
            else:
                if not _can_edit_of_reservations(request.user):
                    raise PermissionDenied('Permission de modification d’OF requise pour créer une réservation manuelle.')
                requirement = get_object_or_404(OFMaterialRequirement, pk=request.POST.get('requirement_id'), of=of)
                reserve_fifo_partial(requirement, request.user)
                requirement.refresh_from_db()
                if requirement.missing_quantity > 1e-6:
                    messages.warning(request, f'Réservation partielle : solde non couvert de {requirement.missing_quantity:.3f} {requirement.material.unit}.')
                else:
                    messages.success(request, f'Besoin de {requirement.material.name} couvert par réservation.')
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect('of_stock_reservations', of_id=of.pk)
    requirements = list(
        OFMaterialRequirement.objects.filter(of=of).select_related('material')
        .prefetch_related('reservations__lot', 'reservations__events').order_by('material__name')
    )
    return render(request, 'stock/of_stock_reservations.html', {
        'of': of, 'requirements': requirements,
        'machines': Machine.objects.all().order_by('name'),
    })
