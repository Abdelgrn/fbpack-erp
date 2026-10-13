from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models.security_audit import (
    KnownAccessSignature,
    SecurityEvent,
    SecuritySession,
)


class Command(BaseCommand):
    help = (
        "Supprime les événements détaillés et sessions closes au-delà de la "
        "rétention de sécurité (90 jours par défaut)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=int(getattr(settings, "SECURITY_EVENT_RETENTION_DAYS", 90)),
            help="Nombre de jours à conserver (défaut : paramètre SECURITY_EVENT_RETENTION_DAYS).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compte les lignes sans les supprimer.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days < 1 or days > 3650:
            raise CommandError("--days doit être compris entre 1 et 3650.")

        cutoff = timezone.now() - timedelta(days=days)
        event_query = SecurityEvent.objects.filter(occurred_at__lt=cutoff)
        closed_session_query = SecuritySession.objects.exclude(
            status=SecuritySession.Status.ACTIVE
        ).filter(ended_at__lt=cutoff)
        unknown_signature_query = KnownAccessSignature.objects.filter(
            is_recognized=False,
            last_seen_at__lt=cutoff,
        )

        counts = {
            "events": event_query.count(),
            "sessions": closed_session_query.count(),
            "signatures": unknown_signature_query.count(),
        }
        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    "Simulation — "
                    f"{counts['events']} événement(s), "
                    f"{counts['sessions']} session(s) close(s), "
                    f"{counts['signatures']} signature(s) non reconnue(s) seraient supprimés."
                )
            )
            return

        with transaction.atomic():
            # Les événements référencent les sessions en SET_NULL, donc l'ordre est sûr.
            event_query.delete()
            closed_session_query.delete()
            unknown_signature_query.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Purge terminée (antérieur au {cutoff:%Y-%m-%d %H:%M:%S}) — "
                f"{counts['events']} événement(s), "
                f"{counts['sessions']} session(s), "
                f"{counts['signatures']} signature(s) non reconnue(s) supprimés."
            )
        )
