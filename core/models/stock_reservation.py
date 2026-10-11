from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class OFMaterialRequirement(models.Model):
    of = models.ForeignKey('core.OrdreFabrication', on_delete=models.CASCADE, related_name='material_requirements')
    material = models.ForeignKey('core.Material', on_delete=models.PROTECT, related_name='of_requirements')
    quantity_required = models.FloatField(validators=[MinValueValidator(0.000001)])
    notes = models.CharField(max_length=250, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_material_requirements')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['material__name']
        constraints = [models.UniqueConstraint(fields=['of', 'material'], name='unique_of_material_requirement')]

    @property
    def reserved_quantity(self):
        return sum(row.active_quantity for row in self.reservations.all())

    @property
    def missing_quantity(self):
        return max(0, float(self.quantity_required) - self.reserved_quantity)


class StockReservation(models.Model):
    STATUS_CHOICES = [('ACTIVE', 'Active'), ('CONSUMED', 'Consommée'), ('RELEASED', 'Libérée'), ('CANCELLED', 'Annulée')]
    requirement = models.ForeignKey(OFMaterialRequirement, on_delete=models.CASCADE, related_name='reservations')
    lot = models.ForeignKey('core.StockLot', on_delete=models.PROTECT, related_name='of_reservations')
    quantity_reserved = models.FloatField(validators=[MinValueValidator(0.000001)])
    quantity_consumed = models.FloatField(default=0)
    quantity_released = models.FloatField(default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE', db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_stock_reservations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['lot__date_reception', 'id']
        constraints = [models.UniqueConstraint(fields=['requirement', 'lot'], name='unique_requirement_lot_reservation')]
        indexes = [models.Index(fields=['lot', 'status'], name='reservation_lot_status_idx')]

    @property
    def active_quantity(self):
        if self.status != 'ACTIVE':
            return 0
        return max(0, float(self.quantity_reserved) - float(self.quantity_consumed) - float(self.quantity_released))


class StockReservationEvent(models.Model):
    ACTION_CHOICES = [('RESERVE', 'Réservation'), ('RELEASE', 'Libération'), ('CONSUME', 'Consommation'), ('CANCEL', 'Annulation')]
    reservation = models.ForeignKey(StockReservation, on_delete=models.PROTECT, related_name='events')
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    quantity = models.FloatField(validators=[MinValueValidator(0.000001)])
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='stock_reservation_events')
    reason = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
