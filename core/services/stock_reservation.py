from django.core.exceptions import ValidationError
from django.db import transaction
from django.apps import apps
from django.db.models import Sum

from ..models import StockLot

def _reservation_models():
    return (apps.get_model('core', 'OFMaterialRequirement'), apps.get_model('core', 'StockReservation'), apps.get_model('core', 'StockReservationEvent'))


def lot_reserved_quantity(lot_id, exclude_reservation_id=None, exclude_of_id=None):
    OFMaterialRequirement, StockReservation, StockReservationEvent = _reservation_models()
    qs = StockReservation.objects.filter(lot_id=lot_id, status='ACTIVE')
    if exclude_reservation_id:
        qs = qs.exclude(pk=exclude_reservation_id)
    if exclude_of_id:
        qs = qs.exclude(requirement__of_id=exclude_of_id)
    rows = qs.aggregate(r=Sum('quantity_reserved'), c=Sum('quantity_consumed'), l=Sum('quantity_released'))
    return max(0.0, float(rows['r'] or 0) - float(rows['c'] or 0) - float(rows['l'] or 0))


def lot_available_quantity(lot):
    """Stock physically available for a new OF (after all active reservations)."""
    if lot.statut != 'CONFORME':
        return 0.0
    return max(0.0, float(lot.quantite_restante) - lot_reserved_quantity(lot.pk))


def lot_available_quantity_for_of(lot, of_id=None):
    """Quantity an OF can issue: unreserved stock plus its own reservation."""
    if lot.statut != 'CONFORME':
        return 0.0
    return max(0.0, float(lot.quantite_restante) - lot_reserved_quantity(lot.pk, exclude_of_id=of_id))


def material_available_quantity(material, of_id=None):
    lots = StockLot.objects.filter(material=material, statut='CONFORME', quantite_restante__gt=0)
    return sum(lot_available_quantity_for_of(lot, of_id) for lot in lots)


def _validate_of(requirement):
    if requirement.of.statut in ['TERMINE', 'ANNULE']:
        raise ValidationError('Un OF terminé ou annulé ne peut pas réserver de stock.')


@transaction.atomic
def reserve_on_lot(requirement, lot_id, quantity, user):
    OFMaterialRequirement, StockReservation, StockReservationEvent = _reservation_models()
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
    current = StockReservation.objects.select_for_update().filter(requirement=requirement, lot=lot).first()
    available = lot_available_quantity(lot)
    if current and current.status == 'ACTIVE':
        available += current.active_quantity
    target = min(quantity, requirement.missing_quantity)
    if target <= 0:
        raise ValidationError('Le besoin matière est déjà entièrement couvert.')
    if target > available + 1e-9:
        raise ValidationError(f'Stock disponible insuffisant sur ce lot : {available:g}.')
    if current:
        current.quantity_reserved += target
        current.status = 'ACTIVE'
        current.created_by = user
        current.save(update_fields=['quantity_reserved', 'status', 'created_by', 'updated_at'])
        reservation = current
    else:
        reservation = StockReservation.objects.create(requirement=requirement, lot=lot, quantity_reserved=target, created_by=user)
    StockReservationEvent.objects.create(reservation=reservation, action='RESERVE', quantity=target, user=user)
    return reservation


@transaction.atomic
def reserve_fifo_partial(requirement, user):
    """Réserve autant que possible sans annuler la réservation partielle."""
    OFMaterialRequirement, StockReservation, StockReservationEvent = _reservation_models()
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
        if take > 1e-9:
            created.append(reserve_on_lot(requirement, lot.pk, take, user))
            missing -= take
        if missing <= 1e-9:
            break
    return created


@transaction.atomic
def reserve_fifo(requirement, user):
    """Mode historique tout-ou-rien, maintenu pour les appels existants."""
    OFMaterialRequirement, StockReservation, StockReservationEvent = _reservation_models()
    requirement = OFMaterialRequirement.objects.select_for_update().select_related('of', 'material').get(pk=requirement.pk)
    missing = requirement.missing_quantity
    rows = reserve_fifo_partial(requirement, user)
    remaining = max(0.0, requirement.missing_quantity)
    # Si un ancien appel exige le mode atomique, lever l'exception annule les réservations de cet appel.
    if remaining > 1e-9:
        raise ValidationError(f'Stock conforme insuffisant : manque {remaining:g}.')
    return rows


@transaction.atomic
def release_reservation(reservation, user, reason='Libération manuelle', action='RELEASE'):
    OFMaterialRequirement, StockReservation, StockReservationEvent = _reservation_models()
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
    OFMaterialRequirement, StockReservation, StockReservationEvent = _reservation_models()
    rows = list(StockReservation.objects.select_for_update().filter(requirement__of=of, status='ACTIVE'))
    for row in rows:
        release_reservation(row, user, reason=reason, action='CANCEL')
    return len(rows)


@transaction.atomic
def consume_of_reservations(of, material, quantity, user, lot=None):
    """Convertit des réservations actives en consommation lors d'une sortie matière liée à l'OF."""
    OFMaterialRequirement, StockReservation, StockReservationEvent = _reservation_models()
    remaining = float(quantity)
    if remaining <= 0:
        return 0.0
    req = OFMaterialRequirement.objects.select_for_update().filter(of=of, material=material).first()
    if not req:
        return 0.0
    qs = StockReservation.objects.select_for_update().filter(requirement=req, status='ACTIVE').order_by('lot__date_reception', 'id')
    if lot is not None:
        qs = qs.filter(lot=lot)
    consumed_total = 0.0
    for reservation in qs:
        active_before = reservation.active_quantity
        take = min(remaining, active_before)
        if take <= 1e-9:
            continue
        reservation.quantity_consumed += take
        if active_before - take <= 1e-9:
            reservation.status = 'CONSUMED'
        reservation.save(update_fields=['quantity_consumed', 'status', 'updated_at'])
        StockReservationEvent.objects.create(reservation=reservation, action='CONSUME', quantity=take, user=user, reason='Sortie matière liée à l’OF')
        consumed_total += take
        remaining -= take
        if remaining <= 1e-9:
            break
    return consumed_total


@transaction.atomic
def restore_of_reservation_consumption(of, material, quantity, user, lot=None):
    """Restitue la couverture de réservation lors de l'annulation d'une sortie."""
    OFMaterialRequirement, StockReservation, StockReservationEvent = _reservation_models()
    remaining = float(quantity)
    req = OFMaterialRequirement.objects.select_for_update().filter(of=of, material=material).first()
    if not req or remaining <= 0:
        return 0.0
    qs = StockReservation.objects.select_for_update().filter(requirement=req, quantity_consumed__gt=0).order_by('-lot__date_reception', '-id')
    if lot is not None:
        qs = qs.filter(lot=lot)
    restored = 0.0
    for reservation in qs:
        take = min(remaining, reservation.quantity_consumed)
        reservation.quantity_consumed -= take
        if req.of.statut in ('TERMINE', 'ANNULE'):
            # La contre-passation rend le stock physique, mais ne réactive pas une réservation d'un OF clos.
            reservation.quantity_released = max(
                reservation.quantity_released,
                float(reservation.quantity_reserved) - float(reservation.quantity_consumed),
            )
            reservation.status = 'RELEASED'
            reason = 'Restitution physique après annulation; OF clos, réservation non réactivée'
        else:
            reservation.status = 'ACTIVE' if reservation.quantity_released < reservation.quantity_reserved else 'RELEASED'
            reason = 'Restitution après annulation de sortie'
        reservation.save(update_fields=['quantity_consumed', 'quantity_released', 'status', 'updated_at'])
        StockReservationEvent.objects.create(reservation=reservation, action='RESERVE', quantity=take, user=user, reason=reason)
        remaining -= take
        restored += take
        if remaining <= 1e-9:
            break
    return restored


@transaction.atomic
def release_reservations_for_manual_issue(lot, quantity, movement_id, user):
    """Libère, avec journal d'audit, les réservations affectées par une sortie manuelle sans OF."""
    OFMaterialRequirement, StockReservation, StockReservationEvent = _reservation_models()
    remaining = max(0.0, float(quantity))
    marker = f'[MVT#{movement_id}]'
    released_total = 0.0
    rows = StockReservation.objects.select_for_update().filter(
        lot=lot, status='ACTIVE'
    ).select_related('requirement').order_by('id')
    for reservation in rows:
        active = reservation.active_quantity
        take = min(active, remaining)
        if take <= 1e-9:
            continue
        reservation.quantity_released += take
        if active - take <= 1e-9:
            reservation.status = 'RELEASED'
        reservation.save(update_fields=['quantity_released', 'status', 'updated_at'])
        StockReservationEvent.objects.create(
            reservation=reservation, action='RELEASE', quantity=take, user=user,
            reason=f'{marker} Sortie manuelle sans OF; réservation libérée pour stock réellement consommé',
        )
        released_total += take
        remaining -= take
        if remaining <= 1e-9:
            break
    return released_total


@transaction.atomic
def restore_manual_issue_reservations(movement_id, user):
    """Réactive uniquement les quantités libérées par la contre-passation de cette sortie."""
    OFMaterialRequirement, StockReservation, StockReservationEvent = _reservation_models()
    marker = f'[MVT#{movement_id}]'
    events = list(StockReservationEvent.objects.select_for_update().filter(
        action='RELEASE', reason__contains=marker
    ).select_related('reservation').order_by('id'))
    restored = 0.0
    for event in events:
        reservation = StockReservation.objects.select_for_update().get(pk=event.reservation_id)
        amount = min(float(event.quantity), float(reservation.quantity_released or 0))
        if amount <= 1e-9:
            continue
        reservation.quantity_released = max(0.0, float(reservation.quantity_released) - amount)
        if reservation.quantity_consumed + reservation.quantity_released < reservation.quantity_reserved - 1e-9:
            reservation.status = 'ACTIVE'
        elif reservation.quantity_consumed >= reservation.quantity_reserved - 1e-9:
            reservation.status = 'CONSUMED'
        else:
            reservation.status = 'RELEASED'
        reservation.save(update_fields=['quantity_released', 'status', 'updated_at'])
        StockReservationEvent.objects.create(
            reservation=reservation, action='RESERVE', quantity=amount, user=user,
            reason=f'Annulation de la sortie manuelle #{movement_id}; réservation restaurée',
        )
        restored += amount
    return restored
