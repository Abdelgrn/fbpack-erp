from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import OFPrelaunchCheck, OrdreFabrication
from ..models.permissions import user_has_module_access
from ..services.prelaunch import can_override_prelaunch, run_prelaunch_check


def _can_access(user):
    return user.is_superuser or user_has_module_access(user, 'planification') or user_has_module_access(user, 'admin')


@login_required
@require_http_methods(['GET', 'POST'])
def of_prelaunch_check(request, of_id):
    of = get_object_or_404(OrdreFabrication.objects.select_related('client', 'produit'), pk=of_id)
    if not _can_access(request.user):
        messages.error(request, "Vous n’avez pas l’autorisation de vérifier ou lancer cet OF.")
        return redirect('crm_of_detail', of_id=of.pk)

    if request.method == 'GET':
        check = run_prelaunch_check(of, request.user)
    else:
        action = request.POST.get('action', '')
        reason = (request.POST.get('override_reason') or '').strip()
        with transaction.atomic():
            of = OrdreFabrication.objects.select_for_update().select_related('client', 'produit').get(pk=of.pk)
            check = run_prelaunch_check(of, request.user)
            allowed = False
            if check.status == 'READY':
                allowed = action == 'launch'
            elif check.status == 'WARNING':
                allowed = action == 'confirm_warning' and request.POST.get('confirm_warnings') == 'yes'
            elif check.status == 'BLOCKED' and action == 'override':
                if not can_override_prelaunch(request.user):
                    messages.error(request, "Vous n’avez pas le droit de forcer un lancement bloqué.")
                elif len(reason) < 10:
                    messages.error(request, "Le motif de forçage doit contenir au moins 10 caractères.")
                else:
                    allowed = True
                    check.override_used = True
                    check.override_reason = reason
                    check.override_by = request.user
                    check.override_at = timezone.now()
            if allowed:
                if of.statut in ['TERMINE', 'ANNULE']:
                    messages.error(request, "Cet OF terminé ou annulé ne peut pas être lancé.")
                else:
                    of.statut = 'LANCE'
                    of.date_lancement = of.date_lancement or timezone.localdate()
                    of.save(update_fields=['statut', 'date_lancement'])
                    check.launched = True
                    check.launched_at = timezone.now()
                    check.save(update_fields=['launched', 'launched_at', 'override_used', 'override_reason', 'override_by', 'override_at'])
                    if check.override_used:
                        messages.warning(request, f"OF {of.numero_of} lancé par dérogation. Le motif a été audité.")
                    else:
                        messages.success(request, f"OF {of.numero_of} lancé après vérification automatique.")
                    return redirect('crm_of_detail', of_id=of.pk)

    grouped = {}
    for item in check.results:
        grouped.setdefault(item['area'], []).append(item)
    return render(request, 'of/of_prelaunch_check.html', {
        'of': of,
        'check': check,
        'grouped_results': grouped,
        'can_override': can_override_prelaunch(request.user),
    })
