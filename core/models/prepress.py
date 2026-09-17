from django.db import models

class TechnicalProduct(models.Model):
    client = models.ForeignKey('core.Client', on_delete=models.CASCADE)
    ref_internal = models.CharField("Ref Interne", max_length=50, unique=True)
    name = models.CharField("Désignation", max_length=200)
    structure_type = models.CharField(
        max_length=20,
        choices=[('MONO', 'Mono'), ('DUPLEX', 'Duplex'), ('TRIPLEX', 'Triplex')],
        default='MONO'
    )
    width_mm = models.FloatField("Laize (mm)", default=0)
    cut_length_mm = models.FloatField("Pas de coupe (mm)", default=0, null=True, blank=True)
    num_colors = models.IntegerField("Nb Couleurs", default=0, null=True, blank=True)
    artwork_file = models.FileField("Fichier Graphique (AI/PDF)", upload_to='artwork/', blank=True)
    artwork_version = models.IntegerField(default=1)

    class Meta:
        app_label = 'core'
        verbose_name = "Produit technique"
        verbose_name_plural = "Produits techniques"

    def __str__(self):
        return f"{self.ref_internal} - {self.name}"


class Tooling(models.Model):
    TYPE_CHOICES = [('CYL', 'Cylindre Hélio'), ('CLICHE', 'Cliché Flexo')]
    product = models.ForeignKey(TechnicalProduct, on_delete=models.CASCADE)
    tool_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    serial_number = models.CharField("N° Série", max_length=100)
    max_impressions = models.IntegerField("Durée de vie (tours)", default=1000000)
    current_impressions = models.IntegerField("Tours actuels", default=0)

    class Meta:
        app_label = 'core'
        verbose_name = "Outillage cliché, cylindre"
        verbose_name_plural = "Outillages cliché, cylindre"