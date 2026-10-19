"""INK_HISTORIQUE V1.0 — modifier et supprimer un calcul d'encre enregistré.

Routes à ajouter dans urls.py (voir LIRE_MOI) :
  ink/historique/<int:job_id>/modifier/   -> ink_calculation_edit   (name='ink_calculation_edit')
  ink/historique/<int:job_id>/supprimer/  -> ink_calculation_delete (name='ink_calculation_delete')
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..models import AniloxRoll, InkCalculationJob
from ..services.cliche_suppliers import SUPPLIER_CHOICES, supplier_or_blank
from ..services.ink_calculator import density_default, validate_coverage
from .ink_calculator import allowed

INK_TYPES = [('COLOR', 'Couleur solvant'), ('WHITE', 'Blanc TiO₂'), ('VARNISH', 'Vernis')]


def _num(value, default=None):
    value = (value or '').strip().replace(',', '.')
    if value == '':
        return default
    try:
        return float(value)
    except ValueError:
        raise ValueError(f'Valeur numérique invalide : « {value} ».')


def _posted(post, job):
    """Valeurs du formulaire (depuis la base en GET, depuis la saisie en erreur)."""
    jf = {'name': post.get('name', job.name), 'width_mm': post.get('width_mm', job.width_mm),
          'length_m': post.get('length_m', job.length_m), 'repeat_mm': post.get('repeat_mm', job.repeat_mm),
          'transfer_percent': post.get('transfer_percent', job.transfer_percent),
          'loss_percent': post.get('loss_percent', job.loss_percent),
          'cliche_supplier': post.get('cliche_supplier', job.cliche_supplier or '')}
    cf = []
    for c in job.colors.all():
        p = f'c{c.id}_'
        cf.append({'id': c.id, 'name': post.get(p + 'name', c.name), 'ink_type': post.get(p + 'ink_type', c.ink_type),
                   'coverage': post.get(p + 'coverage', c.coverage_percent),
                   'area': post.get(p + 'area', c.coverage_area_cm2 if c.coverage_area_cm2 is not None else ''),
                   'anilox_id': int(post.get(p + 'anilox', c.anilox_id) or c.anilox_id),
                   'density': post.get(p + 'density', c.density), 'price': post.get(p + 'price', c.price_per_kg)})
    return jf, cf


def _save(post, job):
    name = (post.get('name') or '').strip()
    if not name:
        raise ValueError('Le nom du job est obligatoire.')
    width = _num(post.get('width_mm'))
    length = _num(post.get('length_m'))
    if not width or not length or width <= 0 or length <= 0:
        raise ValueError('Laize et métrage doivent être supérieurs à 0.')
    repeat = _num(post.get('repeat_mm'), 0.0)
    transfer = _num(post.get('transfer_percent'))
    if transfer is None or not (0 < transfer <= 100):
        raise ValueError('Le transfert doit être entre 0 et 100 %.')
    loss = _num(post.get('loss_percent'), 0.0)
    if not (0 <= loss <= 100):
        raise ValueError('La perte doit être entre 0 et 100 %.')
    job.name = name
    job.width_mm = width
    job.length_m = length
    job.repeat_mm = repeat
    job.transfer_percent = transfer
    job.loss_percent = loss
    job.cliche_supplier = supplier_or_blank(post.get('cliche_supplier'))
    job.save()
    for c in job.colors.all():
        p = f'c{c.id}_'
        if p + 'name' not in post:
            continue
        cname = (post.get(p + 'name') or '').strip()
        if not cname:
            raise ValueError('Chaque couleur doit avoir un nom.')
        ink_type = post.get(p + 'ink_type') or c.ink_type
        if ink_type not in dict(INK_TYPES):
            raise ValueError(f'Type d\'encre inconnu pour {cname}.')
        cov = _num(post.get(p + 'coverage'))
        if cov is None or not (0 <= cov <= 100):
            raise ValueError(f'Couverture invalide pour {cname} (0 à 100 %).')
        area = _num(post.get(p + 'area'))
        ok, calc = validate_coverage(area, cov, job.repeat_mm, job.width_mm / max(job.poses_across or 1, 1))
        if not ok:
            raise ValueError(f'Couverture incohérente pour {cname} : {calc:.2f} % calculés.')
        anilox = AniloxRoll.objects.get(pk=int(post.get(p + 'anilox') or c.anilox_id))
        density = _num(post.get(p + 'density'))
        if density is None:
            density = density_default(job.process, ink_type)
        if density <= 0:
            raise ValueError(f'Densité invalide pour {cname}.')
        price = _num(post.get(p + 'price'), 0.0)
        c.name = cname
        c.ink_type = ink_type
        c.coverage_percent = cov
        c.coverage_area_cm2 = area
        c.anilox = anilox
        c.density = density
        c.price_per_kg = price
        c.save()


@login_required
def ink_calculation_edit(request, job_id):
    if not allowed(request.user):
        return redirect('dashboard')
    job = get_object_or_404(InkCalculationJob.objects.prefetch_related('colors__anilox'), pk=job_id)
    if request.method == 'POST':
        try:
            with transaction.atomic():
                _save(request.POST, job)
            messages.success(request, 'Calcul modifié. Les totaux sont recalculés.')
            return redirect('ink_calculation_detail', job_id=job.id)
        except Exception as e:
            messages.error(request, str(e) or 'Modification refusée.')
            jf, cf = _posted(request.POST, job)
    else:
        jf, cf = _posted({}, job)
    used = {c['anilox_id'] for c in cf}
    aniloxes = list(AniloxRoll.objects.filter(is_active=True))
    aniloxes += list(AniloxRoll.objects.filter(pk__in=used - {a.pk for a in aniloxes}))
    return render(request, 'ink_calculation_edit.html', {
        'job': job, 'jf': jf, 'cf': cf, 'aniloxes': aniloxes,
        'ink_types': INK_TYPES, 'suppliers': SUPPLIER_CHOICES,
        'back_url': request.META.get('HTTP_REFERER', ''),
    })


@login_required
@require_POST
def ink_calculation_delete(request, job_id):
    if not allowed(request.user):
        return redirect('dashboard')
    job = get_object_or_404(InkCalculationJob, pk=job_id)
    nom = job.name
    job.delete()
    messages.success(request, f'Calcul « {nom} » supprimé.')
    return redirect('ink_calculation_list')
