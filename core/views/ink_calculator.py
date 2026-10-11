from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.http import require_POST
from ..models import AniloxRoll,Client,InkCalculationColor,InkCalculationJob,OrdreFabrication,TechnicalProduct
from ..models.permissions import user_has_module_access
from ..services.ink_calculator import density_default,validate_coverage

def allowed(u): return u.is_superuser or user_has_module_access(u,'prepress')
@login_required
def ink_calculator(request):
    if not allowed(request.user): return redirect('dashboard')
    if request.method=='POST':
      try:
       with transaction.atomic():
        job=InkCalculationJob.objects.create(name=request.POST['name'],process=request.POST.get('process','FLEXO'),client_id=request.POST.get('client') or None,product_id=request.POST.get('product') or None,of_id=request.POST.get('of') or None,width_mm=float(request.POST['width_mm'].replace(',','.')),length_m=float(request.POST['length_m'].replace(',','.')),repeat_mm=float((request.POST.get('repeat_mm') or '0').replace(',','.')),poses_across=int(request.POST.get('poses_across') or 1),poses_repeat=int(request.POST.get('poses_repeat') or 1),transfer_percent=float(request.POST['transfer_percent'].replace(',','.')),loss_percent=float((request.POST.get('loss_percent') or '0').replace(',','.')),created_by=request.user)
        names=request.POST.getlist('color_name'); coverages=request.POST.getlist('coverage'); aniloxes=request.POST.getlist('anilox'); types=request.POST.getlist('ink_type'); densities=request.POST.getlist('density'); prices=request.POST.getlist('price'); areas=request.POST.getlist('area_cm2')
        for i,name in enumerate(names):
         if not name.strip(): continue
         coverage=float(coverages[i].replace(',','.')); area=float(areas[i].replace(',','.')) if i<len(areas) and areas[i] else None
         ok,calc=validate_coverage(area,coverage,job.repeat_mm,job.width_mm)
         if not ok: raise ValueError(f'Couverture incohérente pour {name}: {calc:.2f}% calculés.')
         typ=types[i]; density=float(densities[i].replace(',','.')) if densities[i] else density_default(job.process,typ)
         InkCalculationColor.objects.create(job=job,name=name.strip(),ink_type=typ,coverage_percent=coverage,coverage_area_cm2=area,anilox_id=aniloxes[i],density=density,price_per_kg=float((prices[i] or '0').replace(',','.')))
       return redirect('ink_calculation_detail',job_id=job.id)
      except Exception as e: messages.error(request,str(e))
    return render(request,'ink_calculator.html',{'aniloxes':AniloxRoll.objects.filter(is_active=True),'clients':Client.objects.order_by('name'),'products':TechnicalProduct.objects.order_by('name'),'ofs':OrdreFabrication.objects.exclude(statut__in=['TERMINE','ANNULE'])})
@login_required
def ink_calculation_detail(request,job_id):
    job=get_object_or_404(InkCalculationJob.objects.prefetch_related('colors__anilox'),pk=job_id)
    return render(request,'ink_calculation_detail.html',{'job':job})
@login_required
@require_POST
def ink_calculation_actual(request,job_id):
    job=get_object_or_404(InkCalculationJob,pk=job_id)
    for c in job.colors.all():
      value=request.POST.get(f'actual_{c.id}'); recovered=request.POST.get(f'recovered_{c.id}')
      if value: c.actual_consumed_kg=float(value.replace(',','.')); c.recovered_kg=float((recovered or '0').replace(',','.')); c.save(update_fields=['actual_consumed_kg','recovered_kg'])
    messages.success(request,'Consommations réelles enregistrées.'); return redirect('ink_calculation_detail',job_id=job.id)
