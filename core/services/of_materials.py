import json
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.apps import apps

from ..models import Material, EtapeProduction, ProcessType
from .stock_reservation import reserve_fifo_partial


def _positive(value, label):
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f'Paramètre technique invalide : {label}.')
    if value <= 0:
        raise ValidationError(f'Paramètre technique requis : {label}.')
    return value


def _material_grammage(material):
    density = float(material.densite_iso or 0)
    if density <= 0:
        raise ValidationError(f'Densité technique manquante pour {material.name}. Complétez la fiche matière.')
    if material.micronage_standard:
        return float(material.micronage_standard) * density
    if material.grammage:
        return float(material.grammage)
    raise ValidationError(f'Micronnage ou grammage manquant pour {material.name}. Complétez la fiche matière.')


def calculate_order(commande):
    """Recalcule côté serveur les besoins à partir des données CRM validées."""
    lines = list(commande.lignes.select_related('material', 'produit').all())
    if not lines:
        raise ValidationError('La commande ne contient aucune ligne de matière ou de produit.')

    calcul_lines = [line for line in lines if line.type_calcul in ('PIECES', 'POIDS') and line.structure_json]
    if calcul_lines:
        raw_structures = {line.structure_json for line in calcul_lines}
        if len(raw_structures) != 1:
            raise ValidationError('Les lignes de commande contiennent plusieurs calculs techniques incompatibles.')
        try:
            data = json.loads(next(iter(raw_structures)))
        except (TypeError, ValueError):
            raise ValidationError('La structure technique enregistrée est illisible. Recalculez la commande.')
        if not isinstance(data, dict) or data.get('type_calcul') not in ('PIECES', 'POIDS'):
            raise ValidationError('Type de calcul technique manquant ou non reconnu.')

        calc_type = data['type_calcul']
        qte = _positive(data.get('quantity_input'), 'quantité commandée')
        expected_unit = 'pieces' if calc_type == 'PIECES' else 'kg'
        if str(data.get('quantity_unit', '')).lower() != expected_unit:
            raise ValidationError('Unité de la quantité commandée incohérente avec le type de calcul.')
        if calc_type == 'PIECES' and abs(qte - round(qte)) > 1e-6:
            raise ValidationError('La quantité commandée en pièces doit être un nombre entier.')
        bobine = _positive(data.get('laize_bobine_mm'), 'laize bobine')
        utile = _positive(data.get('laize_utile_mm'), 'laize utile')
        dev = _positive(data.get('developpement_mm'), 'développement')
        poses = _positive(data.get('poses'), 'nombre de poses')
        if abs(poses - round(poses)) > 1e-6:
            raise ValidationError('Le nombre de poses doit être entier.')
        poses = int(round(poses))
        if utile > bobine:
            raise ValidationError('La laize utile ne peut pas dépasser la laize bobine.')
        layers = data.get('layers')
        if not isinstance(layers, list) or not layers:
            raise ValidationError('La structure doit comporter au moins une couche matière.')
        if len(layers) != len(calcul_lines):
            raise ValidationError('Les matières calculées ne correspondent pas aux lignes de commande. Relancez le calculateur.')

        surface = ((qte / poses) * (dev / 1000.0) * (utile / 1000.0)) if calc_type == 'PIECES' else None
        grams = []
        layer_mats = []
        line_materials = [line.material_id for line in calcul_lines]
        for index, layer in enumerate(layers):
            if not isinstance(layer, dict):
                raise ValidationError('Détail de couche invalide.')
            try:
                material_id = int(layer.get('mat_id'))
            except (TypeError, ValueError):
                raise ValidationError('Une couche ne possède pas de matière liée.')
            if material_id != line_materials[index]:
                raise ValidationError('La matière d’une couche ne correspond pas à la ligne de commande.')
            try:
                material = Material.objects.get(pk=material_id, category='FILM', is_archived=False)
            except Material.DoesNotExist:
                raise ValidationError('Une matière de la structure est indisponible ou ne peut pas être utilisée.')
            grams_per_m2 = _material_grammage(material)
            # Refuser une valeur de calcul client divergente des caractéristiques techniques conservées en base.
            try:
                supplied = float(layer.get('grm2') or 0)
            except (TypeError, ValueError):
                supplied = 0
            if supplied <= 0 or abs(supplied - grams_per_m2) > max(0.5, grams_per_m2 * 0.03):
                raise ValidationError(f'Grammage calculé incohérent pour {material.name}. Corrigez ses caractéristiques puis relancez le calcul.')
            layer_mats.append(material)
            grams.append(grams_per_m2)

        if calc_type == 'POIDS':
            total_grammage = sum(grams) + max(0, len(grams) - 1) * 3.0
            if total_grammage <= 0:
                raise ValidationError('Grammage total nul : vérifiez la structure.')
            surface = (qte * 1000.0) / total_grammage
        if not surface or surface <= 0:
            raise ValidationError('La surface calculée est nulle. Vérifiez quantité, laizes, développement et poses.')

        # La perte est recalculée côté serveur depuis les laizes, elle n'est pas reprise du navigateur.
        perte = max(0.0, 1.0 - utile / bobine)
        ml_utile = surface / (utile / 1000.0)
        requirements = defaultdict(float)
        stage_rows = []
        for index, material in enumerate(layer_mats):
            theoretical_kg = surface * grams[index] / 1000.0
            required_kg = theoretical_kg / (1.0 - perte)
            unit = (material.unit or '').strip().lower()
            if unit in ('kg', 'kgs'):
                stock_required = required_kg
            elif unit in ('m', 'ml', 'metre', 'metres'):
                stock_required = ml_utile
            elif unit in ('m2', 'm²', 'sqm'):
                stock_required = surface / (1.0 - perte)
            else:
                raise ValidationError(f'Unité de stock « {material.unit} » non convertible automatiquement pour {material.name}. Complétez sa fiche technique ou utilisez une unité kg, m ou m².')
            if (calcul_lines[index].unite or '').strip().lower() != unit:
                raise ValidationError(f'L’unité de la ligne CRM ne correspond pas à l’unité de stock de {material.name}. Relancez le calculateur.')
            requirements[material.pk] += stock_required
            stage_rows.append({
                'material': material,
                'quantity': required_kg, 
                'ml': ml_utile,
                'order': index + 1,
                'name': 'Impression' if index == 0 else 'Complexage / Façonnage',
                'development': dev, 'laize_bobine': bobine, 'laize_utile': utile,
            })
        finished_weight = surface * (sum(grams) + max(0, len(grams) - 1) * 3.0) / 1000.0
        if calc_type == 'POIDS':
            finished_weight = qte
        # Preserve additional standard material lines on the same CRM order.
        calculated_line_ids = {line.pk for line in calcul_lines}
        for line in lines:
            if line.pk in calculated_line_ids or not line.material_id:
                continue
            unit = (line.material.unit or '').strip().lower()
            if float(line.quantite or 0) <= 0 or (line.unite or '').strip().lower() != unit:
                raise ValidationError(f'La ligne complémentaire « {line.designation} » doit avoir une quantité positive dans l’unité de stock de {line.material.name} ({line.material.unit}).')
            requirements[line.material_id] += float(line.quantite)
        return {
            'requirements': requirements, 'steps': stage_rows,
            'quantity_kg': finished_weight, 'calculation': data,
            'shortage_note': f"Commande saisie en {qte:g} pièces" if calc_type == 'PIECES' else f"Commande saisie pour {qte:g} kg",
        }

    # Voie historique : les lignes standard exprimées en kg restent compatibles.
    requirements = defaultdict(float)
    quantity_kg = 0.0
    for line in lines:
        if not line.material_id or float(line.quantite or 0) <= 0:
            raise ValidationError(f'La ligne « {line.designation} » doit préciser une matière et une quantité avant la création de l’OF.')
        unit = (line.material.unit or '').strip().lower()
        if (line.unite or '').strip().lower() != unit:
            raise ValidationError(f'L’unité de « {line.designation} » ne correspond pas à l’unité de stock de {line.material.name}.')
        if unit not in ('kg', 'kgs'):
            raise ValidationError(f'La quantité de « {line.designation} » doit être en kg, ou être calculée avec le calculateur technique.')
        requirements[line.material_id] += float(line.quantite)
        quantity_kg += float(line.quantite)
    if quantity_kg <= 0:
        raise ValidationError('La quantité prévue en kg est requise pour l’OF.')
    return {
        'requirements': requirements, 'steps': [],
        'quantity_kg': quantity_kg, 'calculation': None,
        'shortage_note': 'Besoins matières repris des lignes de commande en kg',
    }


@transaction.atomic
def create_requirements_and_reserve(of, calculated, user):
    OFMaterialRequirement = apps.get_model('core', 'OFMaterialRequirement')
    requirements = []
    for material_id, quantity in calculated['requirements'].items():
        material = Material.objects.select_for_update().get(pk=material_id)
        requirement, _ = OFMaterialRequirement.objects.get_or_create(
            of=of, material=material,
            defaults={'quantity_required': quantity, 'created_by': user,
                      'notes': calculated.get('shortage_note', '')[:250]},
        )
        if requirement.quantity_required != quantity:
            requirement.quantity_required = quantity
            requirement.notes = calculated.get('shortage_note', '')[:250]
            requirement.save(update_fields=['quantity_required', 'notes', 'updated_at'])
        reserve_fifo_partial(requirement, user)
        requirements.append(requirement)

    if calculated.get('steps'):
        process_types = list(ProcessType.objects.filter(est_actif=True))
        for spec in calculated['steps']:
            keyword = 'IMPRESSION' if spec['order'] == 1 else 'COMPLEX'
            process = next((p for p in process_types if keyword in p.nom.upper()), None)
            step_fields = {
                'of': of, 'process_type': process, 'numero_etape': spec['order'],
                'nom_etape': f"Étape {spec['order']} — {spec['name']}",
                'support': spec['material'].name, 'developpement': spec['development'],
                'quantite_ml': spec['ml'], 'unite_sortie': 'ML',
                'quantite_entree': spec['quantity'], 'quantite_sortie': spec['quantity'],
            }
            if spec['order'] == 1:
                step_fields.update({'imp_support': spec['material'].name[:100], 'imp_laize': spec['laize_bobine']})
            elif spec['order'] == 2:
                step_fields.update({'comp_mp1': spec['material'].name[:100], 'comp_laize1': spec['laize_bobine']})
            elif spec['order'] == 3:
                step_fields.update({'comp_mp2': spec['material'].name[:100], 'comp_laize2': spec['laize_bobine']})
            elif spec['order'] == 4:
                step_fields.update({'comp_mp3': spec['material'].name[:100], 'comp_laize3': spec['laize_bobine']})
            EtapeProduction.objects.create(**step_fields)
    return requirements
