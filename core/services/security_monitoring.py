"""Services du centre de surveillance des connexions.

Principes de sécurité :
- aucune clé de session, aucun cookie et aucun secret ne sont persistés ici ;
- les identifiants techniques sont transformés par HMAC-SHA-256 avec SECRET_KEY ;
- les métadonnées passent par une liste de nettoyage stricte ;
- une panne du journal de surveillance ne doit jamais empêcher une connexion légitime.
"""

import hashlib
import hmac
import ipaddress
import logging
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.urls import Resolver404, resolve
from django.utils import timezone

from ..models.security_audit import (
    AccountSecurityState,
    KnownAccessSignature,
    SecurityEvent,
    SecurityEventType,
    SecurityRiskLevel,
    SecuritySession,
)

logger = logging.getLogger("security")

SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "pwd",
    "cookie",
    "csrf",
    "token",
    "authorization",
    "secret",
    "session_key",
    "body",
    "post_data",
    "backup_agent",
)

RISK_ORDER = {
    SecurityRiskLevel.NORMAL: 0,
    SecurityRiskLevel.WARNING: 1,
    SecurityRiskLevel.SUSPICIOUS: 2,
    SecurityRiskLevel.CRITICAL: 3,
}


def _bounded_text(value, maximum):
    if value is None:
        return ""
    value = str(value).replace("\x00", "").replace("\r", " ").replace("\n", " ")
    return value[:maximum]


def irreversible_fingerprint(namespace, value):
    """Retourne une empreinte HMAC stable sans révéler la valeur d'origine."""
    if not value:
        return ""
    payload = f"fbpack-security:{namespace}:{value}".encode("utf-8", "replace")
    key = settings.SECRET_KEY.encode("utf-8", "replace")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def hash_submitted_identity(username):
    normalized = _bounded_text(username, 150).strip().casefold()
    return irreversible_fingerprint("submitted-identity", normalized) if normalized else ""


def fingerprint_session_key(session_key):
    return irreversible_fingerprint("django-session", session_key)


def fingerprint_ip(ip_value):
    return irreversible_fingerprint("client-ip", _canonical_ip(ip_value))


def _canonical_ip(value):
    value = _bounded_text(value, 64).strip()
    if not value:
        return ""
    if value.startswith("[") and "]" in value:
        value = value[1:value.index("]")]
    elif value.count(":") == 1 and "." in value:
        possible_ip, possible_port = value.rsplit(":", 1)
        if possible_port.isdigit():
            value = possible_ip
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return ""


def get_request_network(request):
    """Retourne (IP client, IP technique/proxy) sans faire confiance au proxy local."""
    remote_ip = _canonical_ip(request.META.get("REMOTE_ADDR", ""))
    client_ip = remote_ip

    trust_proxy = bool(getattr(settings, "SECURITY_TRUST_PROXY_HEADERS", False))
    if trust_proxy:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        for candidate in forwarded.split(","):
            normalized = _canonical_ip(candidate.strip())
            if normalized:
                client_ip = normalized
                break

    return client_ip or None, remote_ip or None


def _version_label(name, match):
    if not match:
        return name
    version = _bounded_text(match.group(1), 24).replace("_", ".")
    return f"{name} {version}" if version else name


def parse_user_agent(raw_user_agent):
    """Analyse locale et déterministe ; aucune donnée n'est envoyée à un tiers."""
    ua = _bounded_text(raw_user_agent, 512)
    ua_lower = ua.lower()

    if "edg/" in ua_lower:
        browser = _version_label("Microsoft Edge", re.search(r"Edg/([\d.]+)", ua, re.I))
    elif "opr/" in ua_lower or "opera" in ua_lower:
        browser = _version_label("Opera", re.search(r"(?:OPR|Opera)/([\d.]+)", ua, re.I))
    elif "firefox/" in ua_lower:
        browser = _version_label("Firefox", re.search(r"Firefox/([\d.]+)", ua, re.I))
    elif "chrome/" in ua_lower and "chromium" not in ua_lower:
        browser = _version_label("Chrome", re.search(r"Chrome/([\d.]+)", ua, re.I))
    elif "chromium/" in ua_lower:
        browser = _version_label("Chromium", re.search(r"Chromium/([\d.]+)", ua, re.I))
    elif "safari/" in ua_lower and "version/" in ua_lower:
        browser = _version_label("Safari", re.search(r"Version/([\d.]+)", ua, re.I))
    elif "msie " in ua_lower or "trident/" in ua_lower:
        browser = "Internet Explorer"
    elif "curl/" in ua_lower:
        browser = _version_label("cURL", re.search(r"curl/([\d.]+)", ua, re.I))
    elif ua:
        browser = "Navigateur non identifié"
    else:
        browser = "Non renseigné"

    if "windows nt 10.0" in ua_lower:
        operating_system = "Windows 10/11"
    elif "windows nt 6.3" in ua_lower:
        operating_system = "Windows 8.1"
    elif "windows" in ua_lower:
        operating_system = "Windows"
    elif "android" in ua_lower:
        operating_system = _version_label("Android", re.search(r"Android\s+([\d.]+)", ua, re.I))
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        operating_system = _version_label("iOS/iPadOS", re.search(r"OS\s+([\d_]+)", ua, re.I))
    elif "mac os x" in ua_lower:
        operating_system = _version_label("macOS", re.search(r"Mac OS X\s+([\d_]+)", ua, re.I))
    elif "cros" in ua_lower:
        operating_system = "ChromeOS"
    elif "linux" in ua_lower:
        operating_system = "Linux"
    else:
        operating_system = "Non identifié"

    if any(marker in ua_lower for marker in ("bot", "crawler", "spider", "curl/", "wget/")):
        device = "Robot / client automatisé"
    elif "ipad" in ua_lower or "tablet" in ua_lower:
        device = "Tablette"
    elif any(marker in ua_lower for marker in ("mobile", "iphone", "android")):
        device = "Téléphone"
    else:
        device = "Ordinateur"

    return {
        "user_agent": ua,
        "device": _bounded_text(device, 80),
        "browser": _bounded_text(browser, 80),
        "operating_system": _bounded_text(operating_system, 80),
    }


def request_device_snapshot(request):
    parsed = parse_user_agent(request.META.get("HTTP_USER_AGENT", ""))
    language = _bounded_text(request.META.get("HTTP_ACCEPT_LANGUAGE", ""), 80).casefold()
    platform = _bounded_text(request.META.get("HTTP_SEC_CH_UA_PLATFORM", ""), 80).casefold()
    normalized_ua = re.sub(r"\s+", " ", parsed["user_agent"].strip()).casefold()
    source = "|".join((normalized_ua, language, platform))
    parsed["device_fingerprint"] = irreversible_fingerprint("device", source)
    return parsed


def safe_route(request):
    """Stocke le motif de route, pas les paramètres d'URL potentiellement sensibles."""
    match = getattr(request, "resolver_match", None)
    try:
        if match is None:
            match = resolve(getattr(request, "path_info", request.path))
        route = getattr(match, "route", "") or ""
        name = getattr(match, "url_name", "") or ""
        if route:
            label = f"/{route}"
            if name:
                label += f" [{name}]"
            return _bounded_text(label, 255)
    except (Resolver404, ImproperlyConfigured, AttributeError, TypeError):
        pass

    # Pour une route non résolue, ne conserver que le premier segment générique.
    raw_path = _bounded_text(getattr(request, "path", ""), 255)
    first_segment = raw_path.strip("/").split("/", 1)[0]
    return f"/{first_segment}/<route-non-resolue>" if first_segment else "/"


def _sanitize_metadata(value, depth=0):
    if depth > 3:
        return "[profondeur limitée]"
    if isinstance(value, dict):
        cleaned = {}
        for key, item in list(value.items())[:30]:
            key_text = _bounded_text(key, 80)
            if any(part in key_text.casefold() for part in SENSITIVE_KEY_PARTS):
                continue
            cleaned[key_text] = _sanitize_metadata(item, depth + 1)
        return cleaned
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_metadata(item, depth + 1) for item in list(value)[:30]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _bounded_text(value, 300)


def _highest_risk(*levels):
    valid = [level for level in levels if level in RISK_ORDER]
    return max(valid, key=lambda item: RISK_ORDER[item]) if valid else SecurityRiskLevel.NORMAL


def is_outside_business_hours(moment=None):
    moment = timezone.localtime(moment or timezone.now())
    start = int(getattr(settings, "SECURITY_BUSINESS_HOUR_START", 6))
    end = int(getattr(settings, "SECURITY_BUSINESS_HOUR_END", 22))
    start = max(0, min(23, start))
    end = max(0, min(24, end))
    if start < end:
        return not (start <= moment.hour < end)
    # Plage traversant minuit, par exemple 22h -> 6h.
    return not (moment.hour >= start or moment.hour < end)


def _request_fields(request):
    client_ip, proxy_ip = get_request_network(request)
    device = request_device_snapshot(request)
    return {
        "client_ip": client_ip,
        "proxy_ip": proxy_ip,
        "user_agent": device["user_agent"],
        "device": device["device"],
        "browser": device["browser"],
        "operating_system": device["operating_system"],
        "device_fingerprint": device["device_fingerprint"],
        "route": safe_route(request),
    }


def record_security_event(
    event_type,
    *,
    request=None,
    user=None,
    security_session=None,
    submitted_identity_hash="",
    risk_level=SecurityRiskLevel.NORMAL,
    reason="",
    metadata=None,
    snapshot=None,
):
    """Enregistre un événement sans jamais faire échouer la requête métier."""
    try:
        fields = dict(snapshot or {})
        if request is not None:
            fields = {**_request_fields(request), **fields}
        if user is None and request is not None:
            candidate = getattr(request, "user", None)
            if getattr(candidate, "is_authenticated", False):
                user = candidate

        return SecurityEvent.objects.create(
            event_type=event_type,
            user=user,
            submitted_identity_hash=_bounded_text(submitted_identity_hash, 64),
            session=security_session,
            client_ip=fields.get("client_ip") or None,
            proxy_ip=fields.get("proxy_ip") or None,
            user_agent=_bounded_text(fields.get("user_agent", ""), 512),
            device=_bounded_text(fields.get("device", ""), 80),
            browser=_bounded_text(fields.get("browser", ""), 80),
            operating_system=_bounded_text(fields.get("operating_system", ""), 80),
            route=_bounded_text(fields.get("route", ""), 255),
            risk_level=risk_level,
            reason=_bounded_text(reason, 500),
            metadata=_sanitize_metadata(metadata or {}),
        )
    except Exception as exc:  # La surveillance ne doit pas bloquer l'ERP avant/après migration.
        logger.error("security_event_write_failed type=%s error=%s", event_type, type(exc).__name__)
        return None


def _observe_signature(user, kind, fingerprint, display_value):
    if not user or not fingerprint:
        return None, False
    now = timezone.now()
    defaults = {
        "display_value": _bounded_text(display_value, 255),
        "first_seen_at": now,
        "last_seen_at": now,
    }
    try:
        signature, created = KnownAccessSignature.objects.get_or_create(
            user=user,
            kind=kind,
            fingerprint=fingerprint,
            defaults=defaults,
        )
    except IntegrityError:
        signature = KnownAccessSignature.objects.get(
            user=user,
            kind=kind,
            fingerprint=fingerprint,
        )
        created = False

    if not created:
        updates = {"last_seen_at": now}
        clean_display = _bounded_text(display_value, 255)
        if clean_display and clean_display != signature.display_value:
            updates["display_value"] = clean_display
        KnownAccessSignature.objects.filter(pk=signature.pk).update(**updates)
        for field, value in updates.items():
            setattr(signature, field, value)
    return signature, created


def current_session_fingerprint(request):
    session_key = getattr(getattr(request, "session", None), "session_key", None)
    return fingerprint_session_key(session_key) if session_key else ""


def record_login_success(request, user):
    try:
        if not request.session.session_key:
            request.session.save()
        fingerprint = current_session_fingerprint(request)
        if not fingerprint:
            return None

        now = timezone.now()
        fields = _request_fields(request)
        online_minutes = int(getattr(settings, "SECURITY_MONITOR_ONLINE_MINUTES", 5))
        cutoff = now - timedelta(minutes=max(1, online_minutes))

        concurrent = SecuritySession.objects.filter(
            user=user,
            status=SecuritySession.Status.ACTIVE,
            last_activity_at__gte=cutoff,
        ).exclude(session_fingerprint=fingerprint)
        if fields["client_ip"]:
            concurrent = concurrent.exclude(client_ip=fields["client_ip"])
        multiple_ip = concurrent.exists()

        security_session, _ = SecuritySession.objects.update_or_create(
            session_fingerprint=fingerprint,
            defaults={
                "user": user,
                "status": SecuritySession.Status.ACTIVE,
                "initial_client_ip": fields["client_ip"],
                "client_ip": fields["client_ip"],
                "proxy_ip": fields["proxy_ip"],
                "user_agent": fields["user_agent"],
                "device": fields["device"],
                "browser": fields["browser"],
                "operating_system": fields["operating_system"],
                "device_fingerprint": fields["device_fingerprint"],
                "first_login_at": now,
                "last_activity_at": now,
                "recent_path": fields["route"],
                "ended_at": None,
                "revoked_by": None,
                "revoked_reason": "",
            },
        )

        ip_signature, new_ip = _observe_signature(
            user,
            KnownAccessSignature.Kind.IP,
            fingerprint_ip(fields["client_ip"]),
            fields["client_ip"] or "IP non disponible",
        )
        device_signature, new_device = _observe_signature(
            user,
            KnownAccessSignature.Kind.DEVICE,
            fields["device_fingerprint"],
            f'{fields["device"]} — {fields["browser"]} — {fields["operating_system"]}',
        )

        outside_hours = is_outside_business_hours(now)
        risk = _highest_risk(
            SecurityRiskLevel.SUSPICIOUS if multiple_ip else SecurityRiskLevel.NORMAL,
            SecurityRiskLevel.WARNING if outside_hours else SecurityRiskLevel.NORMAL,
        )
        reasons = []
        if multiple_ip:
            reasons.append("même compte actif sur plusieurs IP")
        if outside_hours:
            reasons.append("connexion hors horaires configurés")
        reason = "; ".join(reasons) or "Authentification réussie"

        record_security_event(
            SecurityEventType.LOGIN_SUCCESS,
            request=request,
            user=user,
            security_session=security_session,
            risk_level=risk,
            reason=reason,
            metadata={
                "multiple_ip": multiple_ip,
                "outside_business_hours": outside_hours,
                "ip_recognized": bool(ip_signature and ip_signature.is_recognized),
                "device_recognized": bool(device_signature and device_signature.is_recognized),
            },
        )
        if new_ip:
            record_security_event(
                SecurityEventType.NEW_IP,
                request=request,
                user=user,
                security_session=security_session,
                risk_level=SecurityRiskLevel.SUSPICIOUS if multiple_ip else SecurityRiskLevel.WARNING,
                reason="Première observation de cette adresse IP pour ce compte",
            )
        if new_device:
            record_security_event(
                SecurityEventType.NEW_DEVICE,
                request=request,
                user=user,
                security_session=security_session,
                risk_level=SecurityRiskLevel.WARNING,
                reason="Première observation de cet appareil pour ce compte",
            )
        return security_session
    except Exception as exc:
        logger.error("login_monitoring_failed user_id=%s error=%s", getattr(user, "pk", None), type(exc).__name__)
        return None


def track_authenticated_request(request):
    """Met à jour l'activité et détecte IP/appareil/multi-IP en cours de session."""
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return None
    fingerprint = current_session_fingerprint(request)
    if not fingerprint:
        return None

    try:
        now = timezone.now()
        fields = _request_fields(request)
        security_session = SecuritySession.objects.filter(
            session_fingerprint=fingerprint
        ).select_related("user").first()

        if security_session and security_session.status != SecuritySession.Status.ACTIVE:
            # Ne jamais ressusciter une session explicitement close ou révoquée.
            return security_session

        is_discovery = security_session is None
        previous_device = security_session.device_fingerprint if security_session else ""
        if is_discovery:
            security_session = SecuritySession.objects.create(
                user=user,
                session_fingerprint=fingerprint,
                status=SecuritySession.Status.ACTIVE,
                initial_client_ip=fields["client_ip"],
                client_ip=fields["client_ip"],
                proxy_ip=fields["proxy_ip"],
                user_agent=fields["user_agent"],
                device=fields["device"],
                browser=fields["browser"],
                operating_system=fields["operating_system"],
                device_fingerprint=fields["device_fingerprint"],
                first_login_at=now,
                last_activity_at=now,
                recent_path=fields["route"],
            )
        else:
            previous_ip = security_session.client_ip
            SecuritySession.objects.filter(pk=security_session.pk).update(
                user=user,
                client_ip=fields["client_ip"],
                proxy_ip=fields["proxy_ip"],
                user_agent=fields["user_agent"],
                device=fields["device"],
                browser=fields["browser"],
                operating_system=fields["operating_system"],
                device_fingerprint=fields["device_fingerprint"],
                last_activity_at=now,
                recent_path=fields["route"],
            )
            security_session.user = user
            security_session.client_ip = fields["client_ip"]
            security_session.proxy_ip = fields["proxy_ip"]
            security_session.user_agent = fields["user_agent"]
            security_session.device = fields["device"]
            security_session.browser = fields["browser"]
            security_session.operating_system = fields["operating_system"]
            security_session.device_fingerprint = fields["device_fingerprint"]
            security_session.last_activity_at = now
            security_session.recent_path = fields["route"]

            if previous_ip and fields["client_ip"] and previous_ip != fields["client_ip"]:
                record_security_event(
                    SecurityEventType.IP_CHANGED,
                    request=request,
                    user=user,
                    security_session=security_session,
                    risk_level=SecurityRiskLevel.SUSPICIOUS,
                    reason="Adresse IP modifiée pendant une session ouverte",
                )
            if previous_device and fields["device_fingerprint"] and previous_device != fields["device_fingerprint"]:
                record_security_event(
                    SecurityEventType.NEW_DEVICE,
                    request=request,
                    user=user,
                    security_session=security_session,
                    risk_level=SecurityRiskLevel.SUSPICIOUS,
                    reason="Signature d'appareil modifiée pendant une session ouverte",
                )

        _, new_ip = _observe_signature(
            user,
            KnownAccessSignature.Kind.IP,
            fingerprint_ip(fields["client_ip"]),
            fields["client_ip"] or "IP non disponible",
        )
        _, new_device = _observe_signature(
            user,
            KnownAccessSignature.Kind.DEVICE,
            fields["device_fingerprint"],
            f'{fields["device"]} — {fields["browser"]} — {fields["operating_system"]}',
        )
        if new_ip:
            record_security_event(
                SecurityEventType.NEW_IP,
                request=request,
                user=user,
                security_session=security_session,
                risk_level=(
                    SecurityRiskLevel.SUSPICIOUS
                    if not is_discovery
                    else SecurityRiskLevel.WARNING
                ),
                reason=(
                    "Nouvelle IP observée pendant une session ouverte"
                    if not is_discovery
                    else "Nouvelle IP découverte sur une session déjà ouverte"
                ),
            )
        if new_device and (is_discovery or not previous_device):
            record_security_event(
                SecurityEventType.NEW_DEVICE,
                request=request,
                user=user,
                security_session=security_session,
                risk_level=SecurityRiskLevel.WARNING,
                reason="Nouvel appareil découvert sur une session déjà ouverte",
            )

        if is_outside_business_hours(now):
            day_key = timezone.localdate(now).isoformat()
            once_key = f"security:outside:{fingerprint}:{day_key}"
            if cache.add(once_key, 1, timeout=24 * 60 * 60):
                record_security_event(
                    SecurityEventType.SUSPICIOUS_ACTIVITY,
                    request=request,
                    user=user,
                    security_session=security_session,
                    risk_level=SecurityRiskLevel.WARNING,
                    reason="Activité hors horaires configurés",
                )

        online_minutes = max(1, int(getattr(settings, "SECURITY_MONITOR_ONLINE_MINUTES", 5)))
        other = SecuritySession.objects.filter(
            user=user,
            status=SecuritySession.Status.ACTIVE,
            last_activity_at__gte=now - timedelta(minutes=online_minutes),
        ).exclude(pk=security_session.pk)
        if fields["client_ip"]:
            other = other.exclude(client_ip=fields["client_ip"])
        other_session = other.only("pk", "client_ip").first()
        if other_session:
            pair = ":".join(str(item) for item in sorted((security_session.pk, other_session.pk)))
            once_key = f"security:multi-ip:{irreversible_fingerprint('pair', pair)}"
            if cache.add(once_key, 1, timeout=online_minutes * 60):
                record_security_event(
                    SecurityEventType.SUSPICIOUS_ACTIVITY,
                    request=request,
                    user=user,
                    security_session=security_session,
                    risk_level=SecurityRiskLevel.SUSPICIOUS,
                    reason="Même compte actif simultanément sur plusieurs IP",
                )
        return security_session
    except Exception as exc:
        logger.error("session_activity_monitoring_failed error=%s", type(exc).__name__)
        return None


def _failed_attempt_risk(attempt_count, outside_hours=False):
    if attempt_count >= 10:
        base = SecurityRiskLevel.CRITICAL
    elif attempt_count >= 5:
        base = SecurityRiskLevel.SUSPICIOUS
    elif attempt_count >= 3:
        base = SecurityRiskLevel.WARNING
    else:
        base = SecurityRiskLevel.NORMAL
    return _highest_risk(base, SecurityRiskLevel.WARNING if outside_hours else SecurityRiskLevel.NORMAL)


def record_login_failure(request, username):
    identity_hash = hash_submitted_identity(username)
    fields = _request_fields(request)
    now = timezone.now()
    cutoff = now - timedelta(minutes=15)
    try:
        attempts = SecurityEvent.objects.filter(
            event_type__in=[SecurityEventType.LOGIN_FAILED, SecurityEventType.LOGIN_LOCKED],
            occurred_at__gte=cutoff,
        )
        if identity_hash:
            attempts = attempts.filter(
                Q(submitted_identity_hash=identity_hash) | Q(client_ip=fields["client_ip"])
            )
        elif fields["client_ip"]:
            attempts = attempts.filter(client_ip=fields["client_ip"])
        attempt_count = attempts.count() + 1
    except Exception:
        attempt_count = 1

    outside_hours = is_outside_business_hours(now)
    risk = _failed_attempt_risk(attempt_count, outside_hours)
    user = None
    disabled = False
    try:
        normalized = _bounded_text(username, 150).strip()
        if normalized:
            user = get_user_model().objects.filter(username__iexact=normalized).first()
            disabled = bool(user and not user.is_active)
    except Exception:
        user = None

    record_security_event(
        SecurityEventType.LOGIN_FAILED,
        request=request,
        user=user,
        submitted_identity_hash=identity_hash,
        risk_level=_highest_risk(risk, SecurityRiskLevel.SUSPICIOUS if disabled else SecurityRiskLevel.NORMAL),
        reason="Authentification refusée",
        metadata={
            "attempts_last_15_minutes": attempt_count,
            "outside_business_hours": outside_hours,
            "account_disabled": disabled,
        },
    )
    if disabled:
        record_security_event(
            SecurityEventType.ACCOUNT_DISABLED_ATTEMPT,
            request=request,
            user=user,
            submitted_identity_hash=identity_hash,
            risk_level=SecurityRiskLevel.SUSPICIOUS,
            reason="Tentative de connexion avec un compte désactivé",
            metadata={"attempts_last_15_minutes": attempt_count},
        )
    return attempt_count


def record_login_locked(request, username):
    identity_hash = hash_submitted_identity(username)
    user = None
    try:
        normalized = _bounded_text(username, 150).strip()
        if normalized:
            user = get_user_model().objects.filter(username__iexact=normalized).first()
    except Exception:
        user = None
    record_security_event(
        SecurityEventType.LOGIN_LOCKED,
        request=request,
        user=user,
        submitted_identity_hash=identity_hash,
        risk_level=SecurityRiskLevel.CRITICAL,
        reason="Seuil anti-bruteforce atteint ; connexion temporairement verrouillée",
        metadata={"account_disabled": bool(user and not user.is_active)},
    )
    if user and not user.is_active:
        record_security_event(
            SecurityEventType.ACCOUNT_DISABLED_ATTEMPT,
            request=request,
            user=user,
            submitted_identity_hash=identity_hash,
            risk_level=SecurityRiskLevel.CRITICAL,
            reason="Tentative verrouillée avec un compte désactivé",
        )


def record_access_denied(request, reason="Accès serveur refusé"):
    try:
        fields = _request_fields(request)
        user = request.user if getattr(request.user, "is_authenticated", False) else None
        cutoff = timezone.now() - timedelta(minutes=15)
        repeated = SecurityEvent.objects.filter(
            event_type=SecurityEventType.ACCESS_DENIED,
            occurred_at__gte=cutoff,
            route=fields["route"],
        )
        if user:
            repeated = repeated.filter(user=user)
        elif fields["client_ip"]:
            repeated = repeated.filter(client_ip=fields["client_ip"])
        count = repeated.count() + 1
        if count >= 10:
            risk = SecurityRiskLevel.CRITICAL
        elif count >= 4:
            risk = SecurityRiskLevel.SUSPICIOUS
        else:
            risk = SecurityRiskLevel.WARNING
        module = fields["route"].strip("/").split("/", 1)[0] if fields["route"] else ""
        record_security_event(
            SecurityEventType.ACCESS_DENIED,
            request=request,
            user=user,
            risk_level=risk,
            reason=reason,
            metadata={"denials_last_15_minutes": count, "route_group": module},
        )
    except Exception as exc:
        logger.error("access_denied_monitoring_failed error=%s", type(exc).__name__)


def record_logout(request, fingerprint=None):
    fingerprint = fingerprint or current_session_fingerprint(request)
    if not fingerprint:
        return
    try:
        security_session = SecuritySession.objects.filter(
            session_fingerprint=fingerprint
        ).select_related("user").first()
        if not security_session or security_session.status != SecuritySession.Status.ACTIVE:
            return
        now = timezone.now()
        record_security_event(
            SecurityEventType.LOGOUT,
            request=request,
            user=security_session.user,
            security_session=security_session,
            risk_level=SecurityRiskLevel.NORMAL,
            reason="Déconnexion de la session",
        )
        SecuritySession.objects.filter(pk=security_session.pk).update(
            status=SecuritySession.Status.LOGGED_OUT,
            ended_at=now,
            last_activity_at=now,
        )
    except Exception as exc:
        logger.error("logout_monitoring_failed error=%s", type(exc).__name__)


def reconcile_expired_sessions():
    """Marque expirées les sessions suivies absentes de django_session."""
    session_engine = getattr(settings, "SESSION_ENGINE", "django.contrib.sessions.backends.db")
    if session_engine != "django.contrib.sessions.backends.db":
        logger.warning("security_session_reconcile_skipped unsupported_engine=%s", session_engine)
        return 0
    try:
        now = timezone.now()
        active_hashes = {
            fingerprint_session_key(key)
            for key in Session.objects.filter(expire_date__gt=now).values_list("session_key", flat=True).iterator()
        }
        expired = list(
            SecuritySession.objects.filter(status=SecuritySession.Status.ACTIVE)
            .exclude(session_fingerprint__in=active_hashes)
            .select_related("user")
        )
        expired_count = 0
        for monitored in expired:
            snapshot = {
                "client_ip": monitored.client_ip,
                "proxy_ip": monitored.proxy_ip,
                "user_agent": monitored.user_agent,
                "device": monitored.device,
                "browser": monitored.browser,
                "operating_system": monitored.operating_system,
                "route": monitored.recent_path,
            }
            changed = SecuritySession.objects.filter(
                pk=monitored.pk,
                status=SecuritySession.Status.ACTIVE,
            ).update(
                status=SecuritySession.Status.EXPIRED,
                ended_at=now,
            )
            if not changed:
                continue
            expired_count += 1
            record_security_event(
                SecurityEventType.SESSION_EXPIRED,
                user=monitored.user,
                security_session=monitored,
                risk_level=SecurityRiskLevel.NORMAL,
                reason="Session Django expirée ou supprimée",
                snapshot=snapshot,
            )
        return expired_count
    except Exception as exc:
        logger.error("session_reconcile_failed error=%s", type(exc).__name__)
        return 0


def _delete_session_matching_fingerprint(fingerprint):
    deleted = 0
    for django_session in Session.objects.all().only("session_key").iterator():
        candidate = fingerprint_session_key(django_session.session_key)
        if secrets.compare_digest(candidate, fingerprint):
            django_session.delete()
            deleted += 1
    return deleted


def revoke_security_session(monitored, actor, reason=""):
    now = timezone.now()
    deleted = _delete_session_matching_fingerprint(monitored.session_fingerprint)
    SecuritySession.objects.filter(pk=monitored.pk).update(
        status=SecuritySession.Status.REVOKED,
        ended_at=now,
        revoked_by=actor,
        revoked_reason=_bounded_text(reason, 255),
    )
    monitored.status = SecuritySession.Status.REVOKED
    monitored.ended_at = now
    monitored.revoked_by = actor
    monitored.revoked_reason = _bounded_text(reason, 255)
    record_security_event(
        SecurityEventType.SESSION_REVOKED,
        user=monitored.user,
        security_session=monitored,
        risk_level=SecurityRiskLevel.WARNING,
        reason=_bounded_text(reason, 500) or "Session révoquée par un superadministrateur",
        metadata={"actor_user_id": getattr(actor, "pk", None), "django_session_deleted": bool(deleted)},
        snapshot={
            "client_ip": monitored.client_ip,
            "proxy_ip": monitored.proxy_ip,
            "user_agent": monitored.user_agent,
            "device": monitored.device,
            "browser": monitored.browser,
            "operating_system": monitored.operating_system,
            "route": monitored.recent_path,
        },
    )
    return deleted


def revoke_all_user_sessions(user, actor, reason=""):
    """Révoque les sessions suivies et les éventuelles sessions Django historiques."""
    monitored_sessions = list(
        SecuritySession.objects.filter(user=user, status=SecuritySession.Status.ACTIVE)
    )
    deleted_keys = set()
    for django_session in Session.objects.all().iterator():
        try:
            decoded = django_session.get_decoded()
            if str(decoded.get("_auth_user_id", "")) == str(user.pk):
                deleted_keys.add(django_session.session_key)
                django_session.delete()
        except Exception:
            continue

    # Une session suivie peut ne plus être décodable : recherche par empreinte.
    for monitored in monitored_sessions:
        if not any(
            secrets.compare_digest(
                fingerprint_session_key(raw_key),
                monitored.session_fingerprint,
            )
            for raw_key in deleted_keys
        ):
            _delete_session_matching_fingerprint(monitored.session_fingerprint)
        now = timezone.now()
        SecuritySession.objects.filter(pk=monitored.pk).update(
            status=SecuritySession.Status.REVOKED,
            ended_at=now,
            revoked_by=actor,
            revoked_reason=_bounded_text(reason, 255),
        )
        monitored.status = SecuritySession.Status.REVOKED
        monitored.ended_at = now
        record_security_event(
            SecurityEventType.SESSION_REVOKED,
            user=user,
            security_session=monitored,
            risk_level=SecurityRiskLevel.WARNING,
            reason=_bounded_text(reason, 500) or "Toutes les sessions du compte ont été révoquées",
            metadata={"actor_user_id": getattr(actor, "pk", None), "bulk_action": True},
            snapshot={
                "client_ip": monitored.client_ip,
                "proxy_ip": monitored.proxy_ip,
                "user_agent": monitored.user_agent,
                "device": monitored.device,
                "browser": monitored.browser,
                "operating_system": monitored.operating_system,
                "route": monitored.recent_path,
            },
        )
    return len(monitored_sessions), len(deleted_keys)


@transaction.atomic
def disable_user_temporarily(user, actor, minutes, reason):
    minutes = max(5, min(7 * 24 * 60, int(minutes)))
    now = timezone.now()
    state, _ = AccountSecurityState.objects.select_for_update().get_or_create(user=user)
    state.was_active_before_disable = bool(user.is_active)
    state.temporarily_disabled_until = now + timedelta(minutes=minutes)
    state.disabled_by = actor
    state.disabled_reason = _bounded_text(reason, 255)
    state.save()
    if user.is_active:
        user.is_active = False
        user.save(update_fields=["is_active"])
    revoke_all_user_sessions(
        user,
        actor,
        reason=f"Compte désactivé temporairement : {_bounded_text(reason, 180)}",
    )
    record_security_event(
        SecurityEventType.SECURITY_ACTION,
        user=user,
        risk_level=SecurityRiskLevel.WARNING,
        reason="Compte désactivé temporairement par un superadministrateur",
        metadata={"actor_user_id": actor.pk, "duration_minutes": minutes},
    )
    return state


def release_expired_temporary_disables(username=None):
    """Réactive uniquement les comptes qui étaient actifs avant la mesure temporaire."""
    try:
        now = timezone.now()
        states = AccountSecurityState.objects.filter(
            temporarily_disabled_until__isnull=False,
            temporarily_disabled_until__lte=now,
        ).select_related("user")
        if username:
            states = states.filter(user__username__iexact=_bounded_text(username, 150).strip())
        released = 0
        for state in states:
            user = state.user
            if state.was_active_before_disable and not user.is_active:
                user.is_active = True
                user.save(update_fields=["is_active"])
            state.temporarily_disabled_until = None
            state.disabled_by = None
            state.disabled_reason = ""
            state.was_active_before_disable = bool(user.is_active)
            state.save(
                update_fields=[
                    "temporarily_disabled_until",
                    "disabled_by",
                    "disabled_reason",
                    "was_active_before_disable",
                    "updated_at",
                ]
            )
            record_security_event(
                SecurityEventType.SECURITY_ACTION,
                user=user,
                risk_level=SecurityRiskLevel.NORMAL,
                reason="Désactivation temporaire arrivée à expiration",
            )
            released += 1
        return released
    except Exception as exc:
        logger.error("temporary_disable_release_failed error=%s", type(exc).__name__)
        return 0


def clear_temporary_disable_state(user):
    """Empêche une réactivation automatique après une désactivation permanente manuelle."""
    try:
        AccountSecurityState.objects.filter(user=user).update(
            temporarily_disabled_until=None,
            disabled_by=None,
            disabled_reason="",
            was_active_before_disable=False,
        )
    except Exception as exc:
        logger.error("temporary_disable_clear_failed error=%s", type(exc).__name__)


def mark_signature_recognized(signature, actor):
    now = timezone.now()
    signature.is_recognized = True
    signature.recognized_at = now
    signature.recognized_by = actor
    signature.save(update_fields=["is_recognized", "recognized_at", "recognized_by"])
    record_security_event(
        SecurityEventType.SECURITY_ACTION,
        user=signature.user,
        risk_level=SecurityRiskLevel.NORMAL,
        reason=f"{signature.get_kind_display()} marquée comme reconnue",
        metadata={"actor_user_id": actor.pk, "signature_kind": signature.kind},
    )
    return signature
