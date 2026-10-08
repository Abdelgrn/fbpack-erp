# core/kpi/models.py
from django.db import models


class KpiSnapshot(models.Model):
    """Snapshot quotidien des indicateurs pour historique."""
    date = models.DateField("Date du snapshot", auto_now_add=True)
    nb_commandes = models.IntegerField("Nombre de commandes", default=0)
    ca_total = models.DecimalField("CA Total (DA)", max_digits=16, decimal_places=2, default=0)
    produits_actifs = models.IntegerField("Produits techniques actifs", default=0)
    clients_actifs = models.IntegerField("Clients actifs", default=0)

    class Meta:
        app_label = 'core'
        verbose_name = "Snapshot KPI"
        verbose_name_plural = "Snapshots KPI"
        ordering = ['-date']

    def __str__(self):
        return f"Snapshot {self.date} | CA: {self.ca_total} DA"