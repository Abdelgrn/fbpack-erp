import re
import unicodedata
from math import ceil

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from ..models import Material, Tooling, OrdreFabrication, CalculTempsProduction


def _normalize(text):
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'\s+', ' ', text.lower()).strip()


def _number(patterns, text):
    for pattern in patterns:
        found = re.search(pattern, text, re.I)
        if found:
            try:
                return float(found.group(1).replace(' ', '').replace(',', '.'))
            except (TypeError, ValueError):
                pass
    return None


def _history(request):
    return request.session.get('erp_assistant_history', [])


def _save_exchange(request, question, answer, kind='INFO', links=None):
    history = _history(request)
    history.extend([
        {'role': 'user', 'text': question},
        {'role': 'assistant', 'text': answer, 'kind': kind, 'links': links or []},
    ])
    request.session['erp_assistant_history'] = history[-30:]
    request.session.modified = True


def _stock_answer(question, normalized):
    alerts_words = ('alerte', 'seuil', 'rupture', 'faible', 'critique')
    if any(word in normalized for word in alerts_words) and not any(word in normalized for word in ('combien', 'reste', 'stock de')):
        materials = [m for m in Material.objects.filter(is_archived=False).order_by('quantity') if m.quantity <= m.min_threshold][:10]
        if not materials:
            return "Bonne nouvelle : aucune matière n’est actuellement sous son seuil d’alerte.", 'SUCCESS', [{'label': 'Ouvrir le stock', 'url': '/stock/'}]
        lines = [f"• {m.name} : {m.quantity:g} {m.unit} (seuil {m.min_threshold:g})" for m in materials]
        return "Matières prioritaires :\n" + "\n".join(lines), 'WARNING', [{'label': 'Voir les alertes stock', 'url': '/stock/?tab=matieres&low_stock=on'}]

    cleaned = normalized
    for phrase in ('combien me reste t il de', 'combien reste t il de', 'combien reste', 'stock disponible de', 'stock de', 'reste de', 'quantite de'):
        cleaned = cleaned.replace(phrase, ' ')
    cleaned = re.sub(r'\b(stock|matiere|produit|dans|mon|le|la|les|du|des|en|actuel|disponible|svp)\b', ' ', cleaned)
    tokens = [token for token in cleaned.split() if len(token) >= 2]
    query = Q()
    for token in tokens:
        query |= Q(name__icontains=token) | Q(code__icontains=token)
    matches = Material.objects.filter(query, is_archived=False).select_related('supplier')[:8] if tokens else Material.objects.none()
    scored = []
    for material in matches:
        name = _normalize(material.name + ' ' + material.code)
        score = sum(1 for token in tokens if token in name)
        scored.append((score, material))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return "Je n’ai pas trouvé la matière demandée. Essayez avec une partie exacte du nom ou son code, par exemple « Soliprop Cyan ».", 'INFO', [{'label': 'Rechercher dans le stock', 'url': '/stock/'}]
    material = scored[0][1]
    margin = material.quantity - material.min_threshold
    status = 'RUPTURE' if material.quantity <= 0 else ('SOUS LE SEUIL' if margin <= 0 else 'DISPONIBLE')
    supplier = material.supplier.name if material.supplier else 'non renseigné'
    answer = (f"{material.name}\n"
              f"• Stock réel : {material.quantity:g} {material.unit}\n"
              f"• Seuil d’alerte : {material.min_threshold:g} {material.unit}\n"
              f"• Écart au seuil : {margin:+g} {material.unit}\n"
              f"• Fournisseur : {supplier}\n"
              f"• État : {status}")
    return answer, ('WARNING' if margin <= 0 else 'SUCCESS'), [{'label': 'Ouvrir le stock', 'url': '/stock/?tab=matieres'}]


def _calculator_answer(question, normalized):
    kg = _number([r'(\d[\d\s.,]*)\s*kg'], normalized)
    widths = re.findall(r'(\d[\d\s.,]*)\s*mm', normalized)
    micron = _number([r'(\d+(?:[.,]\d+)?)\s*(?:micron|µm|um)'], normalized)
    density = _number([r'densit[eé]\s*(?:de|=|:)?\s*(\d+(?:[.,]\d+)?)'], normalized)
    mother = float(widths[0].replace(' ', '').replace(',', '.')) if len(widths) >= 1 else None
    printed = float(widths[1].replace(' ', '').replace(',', '.')) if len(widths) >= 2 else None
    if density is None:
        density = 0.91 if 'opp' in normalized or 'bopp' in normalized else None
    missing = []
    if kg is None: missing.append('quantité cible en kg')
    if mother is None: missing.append('laize bobine mère en mm')
    if printed is None: missing.append('laize imprimée en mm')
    if micron is None: missing.append('micronage')
    if density is None: missing.append('densité du support')
    if missing:
        return "Pour calculer précisément, indiquez : " + ', '.join(missing) + ". Exemple : « 10 000 kg, bobine 1 200 mm, imprimée 1 100 mm, OPP 20 microns, densité 0,91 ».", 'QUESTION', []
    if mother <= 0 or printed <= 0 or printed > mother or micron <= 0:
        return "Les dimensions ne sont pas cohérentes : la laize imprimée doit être positive et inférieure ou égale à la bobine mère.", 'ERROR', []
    grammage = micron * density
    loss_pct = ((mother - printed) / mother) * 100
    surface = (kg * 1000) / grammage
    useful_length = surface / (printed / 1000)
    mother_length = surface / (mother / 1000)
    gross_kg = kg / (1 - loss_pct / 100) if loss_pct < 100 else 0
    loss_kg = gross_kg - kg
    answer = ("Simulation matière — couche unique\n"
              f"• Poids cible : {kg:,.0f} kg\n"
              f"• Grammage automatique : {grammage:.2f} g/m²\n"
              f"• Perte de laize : {loss_pct:.2f} %\n"
              f"• Surface utile : {surface:,.0f} m²\n"
              f"• Métrage utile : {useful_length:,.0f} m\n"
              f"• Métrage bobine mère : {mother_length:,.0f} m\n"
              f"• Besoin brut estimé : {gross_kg:,.0f} kg\n"
              f"• Lisières estimées : {loss_kg:,.0f} kg\n"
              "Estimation indicative à confirmer dans le calculateur complet.")
    return answer, 'CALC', [{'label': 'Ouvrir le calculateur', 'url': '/crm/commande/add/'}]


def _of_answer(normalized):
    delayed = 'retard' in normalized
    qs = OrdreFabrication.objects.select_related('client', 'produit').exclude(statut__in=['TERMINE', 'ANNULE'])
    if delayed:
        from django.utils import timezone
        qs = qs.filter(date_prevue_fin__lt=timezone.localdate())
    qs = qs.order_by('date_prevue_fin', '-priorite')[:10]
    if not qs:
        return ("Aucun OF en retard n’a été trouvé." if delayed else "Aucun OF actif n’a été trouvé."), 'SUCCESS', [{'label': 'Ouvrir le planning', 'url': '/planification/'}]
    title = 'OF en retard' if delayed else 'OF actifs'
    lines = [f"• {o.numero_of} — {o.client.name} — {o.produit.name} — {o.statut}" for o in qs]
    return title + ' :\n' + '\n'.join(lines), ('WARNING' if delayed else 'INFO'), [{'label': 'Ouvrir le planning', 'url': '/planification/'}]


def _tool_answer():
    tools = list(Tooling.objects.select_related('product__client').all())
    critical = sorted([t for t in tools if t.wear_percent >= 75], key=lambda t: t.wear_percent, reverse=True)[:10]
    if not critical:
        return "Aucun cliché ou cylindre n’a dépassé 75 % de sa durée de vie.", 'SUCCESS', [{'label': 'Parc outillages', 'url': '/prepress/outillages/'}]
    lines = [f"• {t.serial_number} — {t.product.client.name} — {t.wear_percent}%" for t in critical]
    return "Outillages à surveiller :\n" + '\n'.join(lines), 'WARNING', [{'label': 'Parc outillages', 'url': '/prepress/outillages/'}]


def _time_answer(normalized):
    calculations = CalculTempsProduction.objects.select_related('client').order_by('-date_calcul')[:8]
    if not calculations:
        return "Aucun calcul historique n’est disponible dans la Synthèse du temps. Ajoutez d’abord quelques calculs pour permettre une estimation fiable.", 'INFO', [{'label': 'Synthèse du temps', 'url': '/prod/synthese/'}]
    lines = [f"• {c.nom_job} — {c.quantite_commandee:g} {c.unite_quantite} — {c.process_impression}" for c in calculations]
    return "Dernières simulations disponibles :\n" + '\n'.join(lines) + "\nPour une estimation précise, indiquez le job, la quantité, la machine et la vitesse prévue.", 'INFO', [{'label': 'Ouvrir la synthèse', 'url': '/prod/synthese/'}]


def answer_question(question, context=''):
    normalized = _normalize(question)
    if not normalized:
        return "Posez-moi une question sur le stock, le calculateur, les OF, les temps ou les outillages.", 'INFO', []
    if any(word in normalized for word in ('bonjour', 'salut', 'bonsoir')) and len(normalized.split()) <= 4:
        return "Bonjour ! Je suis l’assistant interne FB PACK. Je peux consulter le stock, calculer un besoin matière, vérifier les OF, les temps et le parc outillages.", 'SUCCESS', []
    if any(word in normalized for word in ('calcul', 'laize', 'micron', 'bobine mere', 'metrage')) and ('kg' in normalized or 'micron' in normalized):
        return _calculator_answer(question, normalized)
    if any(word in normalized for word in ('stock', 'reste', 'seuil', 'rupture', 'matiere', 'soliprop', 'encre', 'opp', 'bopp')):
        return _stock_answer(question, normalized)
    if any(word in normalized for word in ('of ', 'ordre de fabrication', 'planning', 'retard')):
        return _of_answer(normalized)
    if any(word in normalized for word in ('cliche', 'cylindre', 'outillage', 'gravure')):
        return _tool_answer()
    if any(word in normalized for word in ('temps', 'duree', 'combien de temps', 'synthese')):
        return _time_answer(normalized)
    return ("Je n’ai pas encore reconnu cette demande. Je peux répondre sur : stock, alertes, calcul matière, OF/planning, synthèse du temps et parc outillages. Reformulez avec le nom du module ou de la matière.", 'INFO', [])


@login_required
def assistant_home(request):
    return render(request, 'assistant/assistant_home.html', {'assistant_history': _history(request)})


@login_required
@require_POST
def assistant_ask(request):
    question = (request.POST.get('question') or '')[:1000].strip()
    context = (request.POST.get('context') or '')[:250]
    answer, kind, links = answer_question(question, context)
    _save_exchange(request, question, answer, kind, links)
    return JsonResponse({'ok': True, 'answer': answer, 'kind': kind, 'links': links})


@login_required
@require_POST
def assistant_clear(request):
    request.session.pop('erp_assistant_history', None)
    request.session.modified = True
    return JsonResponse({'ok': True})
