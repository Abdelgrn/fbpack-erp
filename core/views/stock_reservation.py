from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from ..models import Material, OFMaterialRequirement, OrdreFabrication, StockLot, StockReservation
from ..models.permissions import user_has_module_access
from ..services.stock_reservation import lot_available_quantity, release_reservation, reserve_fifo, reserve_on_lot


def _allowed(user):
    return user.is_superuser or user_has_module_access(user, 'stock') or user_has_module_access(user, 'planification') or user_has_module_access(user, 'admin')


def _deny(request, of):
    messages.error(request, "Vous n’avez pas l’autorisation de gérer les réservations de stock.")
    return redirect('crm_of_detail', of_id=of.pk)


@login_required
@require_http_methods(['GET', 'POST'])
def of_stock_reservations(request, of_id):
    of = get_object_or_404(OrdreFabrication.objects.select_related('client', 'produit'), pk=of_id)
    if not _allowed(request.user):
        return _deny(request, of)
    if request.method == 'POST':
        material = get_object_or_404(Material, pk=request.POST.get('material_id'), is_archived=False)
        try:
            quantity = float((request.POST.get('quantity_required') or '').replace(',', '.'))
            if quantity <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Quantité requise invalide.')
            return redirect('of_stock_reservations', of_id=of.pk)
        requirement, created = OFMaterialRequirement.objects.get_or_create(of=of, material=material, defaults={'quantity_required': quantity, 'created_by': request.user})
        if not created:
            if quantity + 0.000001 < requirement.reserved_quantity:
                messages.error(request, 'Libérez d’abord l’excédent réservé avant de diminuer le besoin.')
                return redirect('of_stock_reservations', of_id=of.pk)
            requirement.quantity_required = quantity
            requirement.notes = (request.POST.get('notes') or '')[:250]
            requirement.save(update_fields=['quantity_required', 'notes', 'updated_at'])
        messages.success(request, f'Besoin {material.name} enregistré : {quantity:g} kg.')
        return redirect('of_stock_reservations', of_id=of.pk)
    requirements = of.material_requirements.select_related('material').prefetch_related('reservations__lot')
    lots_by_requirement = {}
    for requirement in requirements:
        lots = StockLot.objects.filter(material=requirement.material, statut='CONFORME', quantite_restante__gt=0).order_by('date_reception')
        lots_by_requirement[requirement.pk] = [{'lot': lot, 'available': lot_available_quantity(lot)} for lot in lots]
    return render(request, 'crm/of_stock_reservations.html', {'of': of, 'requirements': requirements, 'materials': Material.objects.filter(is_archived=False).order_by('name'), 'lots_by_requirement': lots_by_requirement})


@login_required
@require_POST
def requirement_reserve_fifo(request, requirement_id):
    requirement = get_object_or_404(OFMaterialRequirement.objects.select_related('of'), pk=requirement_id)
    if not _allowed(request.user):
        return _deny(request, requirement.of)
    try:
        reserve_fifo(requirement, request.user)
        messages.success(request, 'Réservation FIFO effectuée sans dépassement de stock.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('of_stock_reservations', of_id=requirement.of_id)


@login_required
@require_POST
def requirement_reserve_manual(request, requirement_id):
    requirement = get_object_or_404(OFMaterialRequirement.objects.select_related('of'), pk=requirement_id)
    if not _allowed(request.user):
        return _deny(request, requirement.of)
    try:
        quantity = float((request.POST.get('quantity') or '').replace(',', '.'))
        reserve_on_lot(requirement, int(request.POST.get('lot_id')), quantity, request.user)
        messages.success(request, 'Réservation manuelle enregistrée.')
    except (ValidationError, ValueError, TypeError) as exc:
        messages.error(request, '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'Lot ou quantité invalide.')
    return redirect('of_stock_reservations', of_id=requirement.of_id)


@login_required
@require_POST
def reservation_release(request, reservation_id):
    reservation = get_object_or_404(StockReservation.objects.select_related('requirement__of'), pk=reservation_id)
    if not _allowed(request.user):
        return _deny(request, reservation.requirement.of)
    release_reservation(reservation, request.user, reason=(request.POST.get('reason') or 'Libération manuelle'))
    messages.success(request, 'Réservation libérée.')
    return redirect('of_stock_reservations', of_id=reservation.requirement.of_id)
