"""Outils de sécurité partagés par les vues de l'ERP (core/views/security_utils.py)."""
import json
import math
import os
from datetime import date, datetime

from django.conf import settings
from django.core.cache import cache

_FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def safe_json(value):
    """JSON utilisable dans un <script> avec le filtre |safe.

    json.dumps seul laisse passer « </script> » : un nom contenant cette séquence
    fermerait la balise et exécuterait du code. Ici <, > et & sont écrits en \\uXXXX :
    le résultat reste du JSON/JavaScript valide, sans aucun changement de gabarit.
    """
    text = json.dumps(value)
    return (
        text.replace('<', '\\u003c')
        .replace('>', '\\u003e')
        .replace('&', '\\u0026')
    )


def xl_safe(value):
    """Neutralise l'injection de formule dans Excel (=, +, -, @ en début de texte)."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def parse_int(value, default=None, minimum=None, maximum=None):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    if minimum is not None and number < minimum:
        return default
    if maximum is not None and number > maximum:
        return default
    return number


def parse_float(value, default=None, minimum=None, maximum=None):
    """Nombre décimal fini (refuse NaN et l'infini)."""
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    if minimum is not None and number < minimum:
        return default
    if maximum is not None and number > maximum:
        return default
    return number


def parse_date(value):
    """Date ISO (AAAA-MM-JJ) ou None."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError):
        return None


def parse_time(value):
    """Heure HH:MM ou HH:MM:SS, ou None."""
    text = str(value or '').strip()
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def validate_upload(uploaded, allowed_extensions, max_bytes):
    """Vérifie l'extension et la taille d'un fichier envoyé. Lève ValueError sinon."""
    name = os.path.basename(getattr(uploaded, 'name', '') or '')
    extension = os.path.splitext(name)[1].lower().lstrip('.')
    if extension not in allowed_extensions:
        raise ValueError(
            'Type de fichier refusé. Formats acceptés : ' + ', '.join(sorted(allowed_extensions)) + '.'
        )
    if uploaded.size > max_bytes:
        raise ValueError(f'Fichier trop volumineux (maximum {max_bytes // (1024 * 1024)} Mo).')
    return name


def rate_limited(key, limit, window_seconds):
    """True si la clé a dépassé `limit` appels dans la fenêtre (cache Django)."""
    cache_key = f'ratelimit:{key}'
    if cache.add(cache_key, 1, timeout=window_seconds):
        return False
    try:
        count = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=window_seconds)
        return False
    return count > limit


def self_approval_blocked(user, owner_user_id):
    """Auto-validation interdite si ERP_ALLOW_SELF_APPROVAL=False (hors superadmin).

    Par défaut (True) rien ne change : la règle est facultative.
    """
    if getattr(settings, 'ERP_ALLOW_SELF_APPROVAL', True):
        return False
    return bool(owner_user_id) and owner_user_id == user.id and not user.is_superuser
