"""Modèles du centre de surveillance des connexions FB PACK.

Ce module ne conserve jamais de cookie, de clé de session brute, de mot de passe,
de jeton CSRF ni de contenu de formulaire. Les identifiants techniques sont des
empreintes HMAC-SHA-256 irréversibles produites par le service de sécurité.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class SecurityRiskLevel(models.TextChoices):
    NORMAL = "NORMAL", "Normal"
    WARNING = "WARNING", "Avertissement"
    SUSPICIOUS = "SUSPICIOUS", "Suspect"
    CRITICAL = "CRITICAL", "Critique"


class SecurityEventType(models.TextChoices):
    LOGIN_SUCCESS = "LOGIN_SUCCESS", "Connexion réussie"
    LOGIN_FAILED = "LOGIN_FAILED", "Échec de connexion"
    LOGIN_LOCKED = "LOGIN_LOCKED", "Connexion verrouillée"
    LOGOUT = "LOGOUT", "Déconnexion"
    SESSION_EXPIRED = "SESSION_EXPIRED", "Session expirée"
    SESSION_REVOKED = "SESSION_REVOKED", "Session révoquée"
    ACCESS_DENIED = "ACCESS_DENIED", "Accès refusé"
    IP_CHANGED = "IP_CHANGED", "IP changée en session"
    NEW_IP = "NEW_IP", "Nouvelle IP"
    NEW_DEVICE = "NEW_DEVICE", "Nouvel appareil"
    ACCOUNT_DISABLED_ATTEMPT = (
        "ACCOUNT_DISABLED_ATTEMPT",
        "Tentative sur compte désactivé",
    )
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY", "Activité suspecte"
    SECURITY_ACTION = "SECURITY_ACTION", "Action de sécurité"


class SecuritySession(models.Model):
    """Projection surveillée d'une session Django sans sa clé brute."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Ouverte"
        LOGGED_OUT = "LOGGED_OUT", "Déconnectée"
        EXPIRED = "EXPIRED", "Expirée"
        REVOKED = "REVOKED", "Révoquée"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_sessions",
    )
    session_fingerprint = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="HMAC-SHA-256 de la clé de session, jamais la clé brute.",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    initial_client_ip = models.GenericIPAddressField(null=True, blank=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    proxy_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    device = models.CharField(max_length=80, blank=True)
    browser = models.CharField(max_length=80, blank=True)
    operating_system = models.CharField(max_length=80, blank=True)
    device_fingerprint = models.CharField(max_length=64, blank=True, db_index=True)
    first_login_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_activity_at = models.DateTimeField(default=timezone.now, db_index=True)
    recent_path = models.CharField(max_length=255, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_security_sessions",
    )
    revoked_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "core"
        ordering = ["-last_activity_at"]
        indexes = [
            models.Index(
                fields=["user", "status", "last_activity_at"],
                name="sec_sess_user_status_idx",
            ),
            models.Index(
                fields=["status", "last_activity_at"],
                name="sec_sess_status_seen_idx",
            ),
        ]
        verbose_name = "Session de sécurité"
        verbose_name_plural = "Sessions de sécurité"

    def __str__(self):
        account = self.user.get_username() if self.user_id else "Compte inconnu"
        return f"{account} — {self.session_fingerprint[:12]}"

    @property
    def short_fingerprint(self):
        return self.session_fingerprint[:16]


class SecurityEvent(models.Model):
    """Événement de sécurité détaillé soumis à une rétention limitée."""

    event_type = models.CharField(
        max_length=32,
        choices=SecurityEventType.choices,
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_events",
    )
    submitted_identity_hash = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Empreinte HMAC du nom saisi lors d'un échec.",
    )
    session = models.ForeignKey(
        SecuritySession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    proxy_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    device = models.CharField(max_length=80, blank=True)
    browser = models.CharField(max_length=80, blank=True)
    operating_system = models.CharField(max_length=80, blank=True)
    route = models.CharField(max_length=255, blank=True, db_index=True)
    risk_level = models.CharField(
        max_length=16,
        choices=SecurityRiskLevel.choices,
        default=SecurityRiskLevel.NORMAL,
        db_index=True,
    )
    reason = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "core"
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(
                fields=["event_type", "occurred_at"],
                name="sec_evt_type_date_idx",
            ),
            models.Index(
                fields=["risk_level", "occurred_at"],
                name="sec_evt_risk_date_idx",
            ),
            models.Index(
                fields=["user", "occurred_at"],
                name="sec_evt_user_date_idx",
            ),
        ]
        verbose_name = "Événement de sécurité"
        verbose_name_plural = "Événements de sécurité"

    def __str__(self):
        return f"{self.event_type} — {self.occurred_at:%Y-%m-%d %H:%M:%S}"


class KnownAccessSignature(models.Model):
    """IP ou appareil observé et éventuellement reconnu par un superadmin."""

    class Kind(models.TextChoices):
        IP = "IP", "Adresse IP"
        DEVICE = "DEVICE", "Appareil"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="known_access_signatures",
    )
    kind = models.CharField(max_length=12, choices=Kind.choices)
    fingerprint = models.CharField(max_length=64)
    display_value = models.CharField(max_length=255, blank=True)
    is_recognized = models.BooleanField(default=False, db_index=True)
    first_seen_at = models.DateTimeField(default=timezone.now)
    last_seen_at = models.DateTimeField(default=timezone.now)
    recognized_at = models.DateTimeField(null=True, blank=True)
    recognized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recognized_access_signatures",
    )

    class Meta:
        app_label = "core"
        ordering = ["user__username", "kind", "-last_seen_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "kind", "fingerprint"],
                name="unique_user_security_signature",
            )
        ]
        indexes = [
            models.Index(
                fields=["user", "kind", "last_seen_at"],
                name="sec_sig_user_kind_idx",
            )
        ]
        verbose_name = "Signature d'accès connue"
        verbose_name_plural = "Signatures d'accès connues"

    def __str__(self):
        return f"{self.user.get_username()} — {self.kind} — {self.display_value}"


class AccountSecurityState(models.Model):
    """État temporaire de désactivation, séparé du profil métier."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_state",
    )
    temporarily_disabled_until = models.DateTimeField(null=True, blank=True, db_index=True)
    disabled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="temporary_account_disables",
    )
    disabled_reason = models.CharField(max_length=255, blank=True)
    was_active_before_disable = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "core"
        verbose_name = "État de sécurité du compte"
        verbose_name_plural = "États de sécurité des comptes"

    def __str__(self):
        return f"Sécurité de {self.user.get_username()}"
