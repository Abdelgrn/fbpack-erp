from django.db.models import Q, Sum
from django.utils import timezone

from ..models import Material, OFMaterialRequirement, OFPrelaunchCheck, StockLot, Tooling


def can_override_prelaunch(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        perms = user.module_permissions
        return bool(perms.can_access_planification or perms.can_access_admin)
    except Exception:
        return False


def _result(code, area, level, title, detail):
    return {'code': code, 'area': area, 'level': level, 'title': title, 'detail': detail}


def evaluate_prelaunch(of):
    results = []
    product = of.produit

    # PRÉPRESSE
    if product.is_obsolete:
        results.append(_result('PREPRESS_OBSOLETE', 'Prépresse', 'BLOCKED', 'Produit obsolète', 'La fiche produit est archivée ou obsolète.'))
    if product.bat_status != 'VALIDE':
        results.append(_result('PREPRESS_BAT', 'Prépresse', 'BLOCKED', 'BAT non validé', f'Statut actuel : {product.get_bat_status_display()}.'))
    else:
        results.append(_result('PREPRESS_BAT_OK', 'Prépresse', 'OK', 'BAT validé', 'Le BAT du produit est validé.'))
    if not (of.fiche_technique or product.tech_sheet_file):
        results.append(_result('PREPRESS_TECH_SHEET', 'Prépresse', 'WARNING', 'Fiche technique absente', 'Aucune fiche technique OF ou produit n’est jointe.'))
    tools = list(Tooling.objects.filter(product=product))
    if (product.num_colors or 0) > 0 and not tools:
        results.append(_result('PREPRESS_TOOLING', 'Prépresse', 'BLOCKED', 'Outillage absent', 'Aucun cliché ou cylindre n’est associé au produit.'))
    elif tools:
        max_wear = max(tool.wear_percent for tool in tools)
        level = 'BLOCKED' if max_wear >= 100 else ('WARNING' if max_wear >= 90 else 'OK')
        results.append(_result('PREPRESS_TOOLING_WEAR', 'Prépresse', level, 'État des outillages', f'Usure maximale détectée : {max_wear} %.'))

    # MATIÈRES — les besoins structurés remplacent le rapprochement indicatif
    requirements = list(OFMaterialRequirement.objects.filter(of=of).prefetch_related('reservations'))
    if not requirements:
        support = (of.support or product.support_impression or '').strip()
        if not support:
            results.append(_result('MATERIAL_SUPPORT', 'Matières', 'WARNING', 'Support non renseigné', 'Impossible de rapprocher automatiquement la matière nécessaire.'))
        else:
            tokens = [token for token in support.replace('/', ' ').replace('-', ' ').split() if len(token) >= 3][:5]
            query = Q()
            for token in tokens:
                query |= Q(name__icontains=token) | Q(code__icontains=token)
            materials = Material.objects.filter(query, is_archived=False).distinct()[:10] if tokens else Material.objects.none()
            if not materials:
                results.append(_result('MATERIAL_NOT_FOUND', 'Matières', 'WARNING', 'Matière non rapprochée', f'Aucune matière ne correspond automatiquement au support « {support} ».'))
            else:
                available = 0
                names = []
                for material in materials:
                    lot_qty = StockLot.objects.filter(material=material, statut='CONFORME', quantite_restante__gt=0).aggregate(total=Sum('quantite_restante'))['total'] or 0
                    available += float(lot_qty)
                    names.append(material.name)
                if available <= 0:
                    results.append(_result('MATERIAL_NO_VALID_LOT', 'Matières', 'BLOCKED', 'Aucun lot conforme disponible', 'Matières rapprochées : ' + ', '.join(names[:4])))
                elif available < float(of.quantite_prevue or 0):
                    results.append(_result('MATERIAL_SHORTAGE', 'Matières', 'BLOCKED', 'Quantité matière insuffisante', f'{available:g} kg conformes pour {of.quantite_prevue:g} kg prévus.'))
                else:
                    results.append(_result('MATERIAL_OK', 'Matières', 'OK', 'Lots conformes disponibles', f'{available:g} kg conformes détectés.'))
    

    # RÉSERVATIONS STRUCTURÉES PAR OF
    if not requirements:
        results.append(_result('RESERVATION_NO_REQUIREMENTS', 'Matières', 'WARNING', 'Besoins matière non définis', 'Ajoutez les besoins et réservations depuis la fiche OF CRM.'))
    else:
        for requirement in requirements:
            reserved = requirement.reserved_quantity
            required = float(requirement.quantity_required)
            if reserved + 0.000001 < required:
                results.append(_result(f'RESERVATION_MISSING_{requirement.pk}', 'Matières', 'BLOCKED', f'Réservation insuffisante — {requirement.material.name}', f'{reserved:g} kg réservés sur {required:g} kg requis.'))
            else:
                results.append(_result(f'RESERVATION_OK_{requirement.pk}', 'Matières', 'OK', f'Réservation complète — {requirement.material.name}', f'{reserved:g} kg réservés.'))

    # PRODUCTION
    steps = list(of.etapes.select_related('machine', 'process_type').order_by('numero_etape'))
    if not steps:
        results.append(_result('PRODUCTION_NO_STEPS', 'Production', 'BLOCKED', 'Aucune étape de production', 'Ajoutez au moins une étape avant le lancement.'))
    for step in steps:
        label = step.nom_etape or (step.process_type.nom if step.process_type else f'Étape {step.numero_etape}')
        if not step.process_type:
            results.append(_result(f'PRODUCTION_PROCESS_{step.pk}', 'Production', 'BLOCKED', f'Processus absent — {label}', 'Le type de processus est obligatoire.'))
        if not step.machine:
            results.append(_result(f'PRODUCTION_MACHINE_{step.pk}', 'Production', 'BLOCKED', f'Machine absente — {label}', 'Aucune machine n’est affectée.'))
        elif not step.machine.est_active or step.machine.status == 'PANNE':
            results.append(_result(f'PRODUCTION_MACHINE_STATE_{step.pk}', 'Production', 'BLOCKED', f'Machine indisponible — {step.machine.name}', f'État : {step.machine.get_status_display()}.'))
        elif step.machine.status == 'MAINT':
            results.append(_result(f'PRODUCTION_MACHINE_MAINT_{step.pk}', 'Production', 'WARNING', f'Machine en maintenance — {step.machine.name}', 'Confirmez sa disponibilité réelle.'))

    # PLANIFICATION
    for step in steps:
        if not step.date_planifiee:
            results.append(_result(f'PLANNING_DATE_{step.pk}', 'Planification', 'WARNING', f'Date absente — étape {step.numero_etape}', 'La date planifiée n’est pas renseignée.'))
        if step.machine and step.date_planifiee:
            conflicts = step.machine.etapeproduction_set.filter(date_planifiee=step.date_planifiee).exclude(of=of).exclude(statut__in=['TERMINE', 'ANNULE'])
            if step.heure_debut_planifiee and step.heure_fin_planifiee:
                conflicts = conflicts.filter(heure_debut_planifiee__lt=step.heure_fin_planifiee, heure_fin_planifiee__gt=step.heure_debut_planifiee)
            if conflicts.exists():
                results.append(_result(f'PLANNING_CONFLICT_{step.pk}', 'Planification', 'BLOCKED', f'Conflit machine — {step.machine.name}', f'Un autre OF occupe cette machine le {step.date_planifiee:%d/%m/%Y}.'))
    if of.date_prevue_fin and of.date_lancement and of.date_prevue_fin < of.date_lancement:
        results.append(_result('PLANNING_DATES', 'Planification', 'BLOCKED', 'Dates incohérentes', 'La fin prévue précède la date de lancement.'))

    if any(item['level'] == 'BLOCKED' for item in results):
        status = 'BLOCKED'
    elif any(item['level'] == 'WARNING' for item in results):
        status = 'WARNING'
    else:
        status = 'READY'
    return status, results


def run_prelaunch_check(of, user):
    status, results = evaluate_prelaunch(of)
    return OFPrelaunchCheck.objects.create(of=of, status=status, results=results, checked_by=user)
