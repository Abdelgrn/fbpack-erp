from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

class AniloxRoll(models.Model):
    lineature = models.PositiveIntegerField()
    volume_cm3_m2 = models.DecimalField(max_digits=6, decimal_places=2, validators=[MinValueValidator(0.01)])
    quantity = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=200, blank=True)
    class Meta:
        app_label='core'; ordering=['-lineature','volume_cm3_m2']; constraints=[models.UniqueConstraint(fields=['lineature','volume_cm3_m2'],name='unique_anilox_spec')]
    def __str__(self): return f'{self.lineature} l/cm — {self.volume_cm3_m2} cm³/m²'

class InkCalculationJob(models.Model):
    PROCESS_CHOICES=[('FLEXO','Flexographie'),('HELIO','Héliogravure')]
    CONFIDENCE_CHOICES=[('ESTIMATED','Estimé'),('TECHNICAL','Technique'),('CALIBRATED','Calibré FB PACK')]
    name=models.CharField(max_length=200); process=models.CharField(max_length=10,choices=PROCESS_CHOICES,default='FLEXO')
    client=models.ForeignKey('core.Client',on_delete=models.SET_NULL,null=True,blank=True,related_name='ink_calculations')
    product=models.ForeignKey('core.TechnicalProduct',on_delete=models.SET_NULL,null=True,blank=True,related_name='ink_calculations')
    of=models.ForeignKey('core.OrdreFabrication',on_delete=models.SET_NULL,null=True,blank=True,related_name='ink_calculations')
    width_mm=models.FloatField(validators=[MinValueValidator(0.01)]); length_m=models.FloatField(validators=[MinValueValidator(0.01)])
    repeat_mm=models.FloatField(default=0); poses_across=models.PositiveIntegerField(default=1); poses_repeat=models.PositiveIntegerField(default=1)
    transfer_percent=models.FloatField(validators=[MinValueValidator(0.01),MaxValueValidator(100)]); loss_percent=models.FloatField(default=0,validators=[MinValueValidator(0),MaxValueValidator(100)])
    confidence=models.CharField(max_length=12,choices=CONFIDENCE_CHOICES,default='TECHNICAL')
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='ink_calculations'); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: app_label='core'; ordering=['-created_at']
    @property
    def surface_m2(self): return self.length_m*(self.width_mm/1000)
    @property
    def total_net_kg(self): return sum(x.net_kg for x in self.colors.all())
    @property
    def total_prepare_kg(self): return sum(x.prepare_kg for x in self.colors.all())

class InkCalculationColor(models.Model):
    INK_CHOICES=[('COLOR','Couleur solvant'),('WHITE','Blanc TiO₂'),('VARNISH','Vernis')]
    job=models.ForeignKey(InkCalculationJob,on_delete=models.CASCADE,related_name='colors'); name=models.CharField(max_length=100)
    ink_type=models.CharField(max_length=10,choices=INK_CHOICES,default='COLOR'); coverage_percent=models.FloatField(validators=[MinValueValidator(0),MaxValueValidator(100)])
    coverage_area_cm2=models.FloatField(null=True,blank=True); anilox=models.ForeignKey(AniloxRoll,on_delete=models.PROTECT,related_name='calculation_colors')
    density=models.FloatField(validators=[MinValueValidator(0.01)]); price_per_kg=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    actual_consumed_kg=models.FloatField(null=True,blank=True); recovered_kg=models.FloatField(default=0)
    class Meta: app_label='core'; ordering=['id']
    @property
    def grams_m2(self): return (self.coverage_percent/100)*float(self.anilox.volume_cm3_m2)*(self.job.transfer_percent/100)*self.density
    @property
    def net_kg(self): return self.grams_m2*self.job.surface_m2/1000
    @property
    def prepare_kg(self): return self.net_kg*(1+self.job.loss_percent/100)
    @property
    def cost(self): return self.prepare_kg*float(self.price_per_kg)
