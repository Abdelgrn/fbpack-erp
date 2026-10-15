from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404,redirect,render
from django.urls import NoReverseMatch
from django.views.decorators.http import require_POST
from ..models import AniloxRoll,Client,InkCalculationColor,InkCalculationJob,OrdreFabrication,TechnicalProduct
from ..models.permissions import user_has_module_access
from ..services.ink_calculator import density_default,validate_coverage
from ..services.cliche_suppliers import SUPPLIER_CHOICES,summarize,supplier_or_blank
from ..services.bat_extractor import MAX_BAT_BYTES,analyze_bat

def allowed(u): return u.is_superuser or user_has_module_access(u,'prepress')

BAT_EXTENSIONS=('.pdf','.png','.jpg','.jpeg','.webp')

@login_required
def ink_calculator(request):
    if not allowed(request.user): return redirect('dashboard')
    bat=None
    if request.method=='POST':
      # --- LOT BAT AUTOFILL V1 : analyse de la fiche BAT (aucun enregistrement) ---
      if 'analyze_bat' in request.POST:
        upload=request.FILES.get('bat_file')
        if not upload:
          messages.error(request,'Choisissez un fichier BAT (PDF ou image) avant de lancer l’analyse.')
        elif upload.size>MAX_BAT_BYTES:
          messages.error(request,'Fiche BAT trop lourde : 10 Mo maximum.')
        elif not upload.name.lower().endswith(BAT_EXTENSIONS):
          messages.error(request,'Format non pris en charge : PDF, PNG, JPG ou WEBP.')
        else:
          bat=analyze_bat(upload.read(),upload.name)
          if bat.get('error'):
            messages.error(request,bat['error']); bat=None
          else:
            n=len(bat.get('rows',[]))
            if n:
              messages.success(request,f'Analyse {bat["mode"]} : {n} couleur(s) détectée(s). Vérifiez/completez les lignes puis « Calculer et enregistrer ».')
            else:
              messages.warning(request,'Analyse terminée mais aucune pastille reconnue : saisissez les couleurs manuellement.')
        context=_base_context(request)
        context['bat']=bat
        context['bat_rows_json']=_json_rows(bat)
        context['bat_hints_json']=_json_hints(bat)
        context['keep_post']=_keep_post(request)
        return render(request,'ink_calculator.html',context)
      # --- moteur historique inchangé ---
      try:
       with transaction.atomic():
        job=InkCalculationJob.objects.create(name=request.POST['name'],process=request.POST.get('process','FLEXO'),client_id=request.POST.get('client') or None,product_id=request.POST.get('product') or None,of_id=request.POST.get('of') or None,width_mm=float(request.POST['width_mm'].replace(',','.')),length_m=float(request.POST['length_m'].replace(',','.')),repeat_mm=float((request.POST.get('repeat_mm') or '0').replace(',','.')),poses_across=int(request.POST.get('poses_across') or 1),poses_repeat=int(request.POST.get('poses_repeat') or 1),transfer_percent=float(request.POST['transfer_percent'].replace(',','.')),loss_percent=float((request.POST.get('loss_percent') or '0').replace(',','.')),cliche_supplier=supplier_or_blank(request.POST.get('cliche_supplier','')),created_by=request.user)
        names=request.POST.getlist('color_name'); coverages=request.POST.getlist('coverage'); aniloxes=request.POST.getlist('anilox'); types=request.POST.getlist('ink_type'); densities=request.POST.getlist('density'); prices=request.POST.getlist('price'); areas=request.POST.getlist('area_cm2')
        for i,name in enumerate(names):
         if not name.strip(): continue
         coverage=float(coverages[i].replace(',','.')); area=float(areas[i].replace(',','.')) if i<len(areas) and areas[i] else None
         ok,calc=validate_coverage(area,coverage,job.repeat_mm,job.width_mm/max(job.poses_across or 1,1))  # V1.7 : laize d'UNE piste
         if not ok: raise ValueError(f'Couverture incohérente pour {name}: {calc:.2f}% calculés.')
         typ=types[i]; density=float(densities[i].replace(',','.')) if densities[i] else density_default(job.process,typ)
         InkCalculationColor.objects.create(job=job,name=name.strip(),ink_type=typ,coverage_percent=coverage,coverage_area_cm2=area,anilox_id=aniloxes[i],density=density,price_per_kg=float((prices[i] or '0').replace(',','.')))
       return _redirect_detail(request,job.id)
      except Exception as e: messages.error(request,str(e))
    return render(request,'ink_calculator.html',_base_context(request))

def _url_or_empty(name,*args):
    from django.urls import NoReverseMatch,reverse
    try: return reverse(name,args=args or None)
    except NoReverseMatch: return ''

def _redirect_detail(request,job_id):
    """Redirige vers le détail du job même si urls.py nomme la route autrement.

    Certaines installations ne déclarent pas « ink_calculation_detail » :
    on essaie les noms connus, puis toute route « ink…detail », sinon on
    revient au calculateur avec un message (le job est déjà enregistré).
    """
    from django.urls import get_resolver
    for n in ('ink_calculation_detail','ink_calculator_detail'):
        try: return redirect(n,job_id)
        except NoReverseMatch: pass
    for key in list(get_resolver().reverse_dict.keys()):
        if isinstance(key,str) and 'ink' in key and 'detail' in key:
            try: return redirect(key,job_id)
            except NoReverseMatch: pass
    messages.success(request,f'Job n°{job_id} enregistré. Route détail absente de urls.py : ajoutez en tête "from core.views.ink_calculator import ink_calculation_detail" puis path("ink/detail/<int:job_id>", ink_calculation_detail, name="ink_calculation_detail").')
    try: return redirect('ink_calculator')
    except NoReverseMatch: return redirect(request.META.get('HTTP_REFERER','/'))

def _base_context(request):
    return {'cliche_choices':SUPPLIER_CHOICES,'aniloxes':AniloxRoll.objects.filter(is_active=True),'clients':Client.objects.order_by('name'),'products':TechnicalProduct.objects.order_by('name'),'ofs':OrdreFabrication.objects.exclude(statut__in=['TERMINE','ANNULE']),'history_url':_url_or_empty('ink_calculation_list')}

def _json_rows(bat):
    import json
    if not bat: return '[]'
    return json.dumps([{'name':r.get('name',''),'ink_type':r.get('ink_type','COLOR'),'coverage_percent':r.get('coverage_percent'),'coverage_area_cm2':r.get('coverage_area_cm2'),'swatch_hex':r.get('swatch_hex','')} for r in bat.get('rows',[])],ensure_ascii=False).replace('</','<\\/')

def _json_hints(bat):
    import json
    if not bat: return '{}'
    hints=dict(bat.get('job_hints',{}) or {}); hints['cliche_supplier']=bat.get('cliche_supplier') or ''
    return json.dumps(hints,ensure_ascii=False).replace('</','<\\/')

def _keep_post(request):
    """Rejoue les champs job saisis après une analyse BAT (rien n’est perdu)."""
    import json
    keys=['name','process','width_mm','length_m','repeat_mm','transfer_percent','loss_percent','poses_across','poses_repeat']
    return json.dumps({k:request.POST.get(k,'') for k in keys},ensure_ascii=False).replace('</','<\\/')

@login_required
def ink_calculation_list(request):
    """LOT BAT AUTOFILL V1.5 : historique de tous les jobs enregistrés."""
    if not allowed(request.user): return redirect('dashboard')
    jobs=InkCalculationJob.objects.select_related('client','product','of','created_by').prefetch_related('colors').order_by('-created_at')
    rows=[{'job':j,'total_cost':sum((c.cost for c in j.colors.all()),0),'detail_url':_url_or_empty('ink_calculation_detail',j.id)} for j in jobs]
    suppliers=summarize([(j.cliche_supplier,j.total_prepare_kg,j.surface_m2) for j in jobs])
    return render(request,'ink_calculation_list.html',{'rows':rows,'suppliers':suppliers,'calc_url':_url_or_empty('ink_calculator')})

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
