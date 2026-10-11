from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from ..models import OFMaterialRequirement, StockLot, StockReservation, StockReservationEvent


def lot_reserved_quantity(lot_id, exclude_reservation_id=None):
    qs = StockReservation.objects.filter(lot_id=lot_id, status='ACTIVE')
    if exclude_reservation_id:
        qs = qs.exclude(pk=exclude_reservation_id)
    rows = qs.aggregate(r=Sum('quantity_reserved'), c=Sum('quantity_consumed'), l=Sum('quantity_released'))
    return max(0, float(rows['r'] or 0) - float(rows['c'] or 0) - float(rows['l'] or 0))


def lot_available_quantity(lot):
    if lot.statut != 'CONFORME':
        return 0
    return max(0, float(lot.quantite_restante) - lot_reserved_quantity(lot.pk))


def _validate_of(requirement):
    if requirement.of.statut in ['TERMINE', 'ANNULE']:
        raise ValidationError('Un OF terminé ou annulé ne peut pas réserver de stock.')


@transaction.atomic
def reserve_on_lot(requirement, lot_id, quantity, user):
    requirement = OFMaterialRequirement.objects.select_for_update().select_related('of', 'material').get(pk=requirement.pk)
    _validate_of(requirement)
    lot = StockLot.objects.select_for_update().get(pk=lot_id)
    quantity = float(quantity)
    if quantity <= 0:
        raise ValidationError('La quantité doit être strictement positive.')
    if lot.material_id != requirement.material_id:
        raise ValidationError('Le lot ne correspond pas à la matière demandée.')
    if lot.statut != 'CONFORME':
        raise ValidationError('Seuls les lots conformes peuvent être réservés.')
    current = StockReservation.objects.filter(requirement=requirement, lot=lot).first()
    available = lot_available_quantity(lot)
    if current and current.status == 'ACTIVE':
        available += current.active_quantity
    target = min(quantity, requirement.missing_quantity + (current.active_quantity if current else 0))
    if target <= 0:
        raise ValidationError('Le besoin matière est déjà entièrement réservé.')
    if target > available:
        raise ValidationError(f'Stock disponible insuffisant sur ce lot : {available:g} kg.')
    if current:
        current.quantity_reserved = target
        current.quantity_consumed = 0
        current.quantity_released = 0
        current.status = 'ACTIVE'
        current.created_by = user
        current.save()
        reservation = current
    else:
        reservation = StockReservation.objects.create(requirement=requirement, lot=lot, quantity_reserved=target, created_by=user)
    StockReservationEvent.objects.create(reservation=reservation, action='RESERVE', quantity=target, user=user)
    return reservation


@transaction.atomic
def reserve_fifo(requirement, user):
    requirement = OFMaterialRequirement.objects.select_for_update().select_related('of', 'material').get(pk=requirement.pk)
    _validate_of(requirement)
    missing = requirement.missing_quantity
    if missing <= 0:
        return []
    created = []
    lots = StockLot.objects.select_for_update().filter(material=requirement.material, statut='CONFORME', quantite_restante__gt=0).order_by('date_reception', 'id')
    for lot in lots:
        available = lot_available_quantity(lot)
        take = min(missing, available)
        if take > 0:
            created.append(reserve_on_lot(requirement, lot.pk, take, user))
            missing -= take
        if missing <= 0:
            break
    if missing > 0:
        raise ValidationError(f'Stock conforme insuffisant : manque {missing:g} kg.')
    return created


@transaction.atomic
def release_reservation(reservation, user, reason='Libération manuelle', action='RELEASE'):
    reservation = StockReservation.objects.select_for_update().get(pk=reservation.pk)
    active = reservation.active_quantity
    if active <= 0:
        return reservation
    reservation.quantity_released += active
    reservation.status = 'CANCELLED' if action == 'CANCEL' else 'RELEASED'
    reservation.save(update_fields=['quantity_released', 'status', 'updated_at'])
    StockReservationEvent.objects.create(reservation=reservation, action=action, quantity=active, user=user, reason=reason[:250])
    return reservation


@transaction.atomic
def release_of_reservations(of, user, reason='OF annulé'):
    rows = list(StockReservation.objects.select_for_update().filter(requirement__of=of, status='ACTIVE'))
    for row in rows:
        release_reservation(row, user, reason=reason, action='CANCEL')
    return len(rows)
