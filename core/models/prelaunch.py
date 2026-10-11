from django.conf import settings
from django.db import models


class OFPrelaunchCheck(models.Model):
    STATUS_CHOICES = [('READY', 'Prêt'), ('WARNING', 'Avertissements'), ('BLOCKED', 'Bloqué')]

    of = models.ForeignKey('core.OrdreFabrication', on_delete=models.CASCADE, related_name='prelaunch_checks')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, db_index=True)
    results = models.JSONField(default=list)
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='of_prelaunch_checks')
    checked_at = models.DateTimeField(auto_now_add=True, db_index=True)
    launched = models.BooleanField(default=False)
    launched_at = models.DateTimeField(null=True, blank=True)
    override_used = models.BooleanField(default=False)
    override_reason = models.TextField(blank=True)
    override_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='of_prelaunch_overrides')
    override_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'core'
        ordering = ['-checked_at']
        indexes = [models.Index(fields=['of', '-checked_at'], name='prelaunch_of_date_idx')]

    def __str__(self):
        return f'{self.of.numero_of} — {self.get_status_display()} — {self.checked_at:%d/%m/%Y %H:%M}'
