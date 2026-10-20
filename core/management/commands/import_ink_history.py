"""Importe un export d'historique d'encre dans la base COURANTE (ex. Neon).

Règles de sécurité :
- AUCUNE suppression. Les calculs déjà en ligne sont conservés.
- Mode simulation par défaut : rien n'est écrit sans --apply.
- Doublon ignoré : même nom, même date de création, même laize, même métrage.
- Relancer la commande ne crée pas de doublons.
- Les ancrages (anilox) manquants sont créés (ajout seulement).
- Utilisateur : le créateur du fichier est retrouvé par son identifiant ; sinon --user.

Exemple (PowerShell, base Neon pointée par DATABASE_URL) :
    python manage.py import_ink_history --file ink_history_export.json
    python manage.py import_ink_history --file ink_history_export.json --apply
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils.dateparse import parse_datetime

from core.models import AniloxRoll, InkCalculationColor, InkCalculationJob


class Command(BaseCommand):
    help = "Importe un export d'historique d'encre (ajout seulement, aucune suppression)."

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Fichier JSON exporté')
        parser.add_argument('--apply', action='store_true',
                            help='Écrit réellement. Sans cette option : simulation.')
        parser.add_argument('--user', default=None,
                            help="Nom d'utilisateur de repli si le créateur n'existe pas en ligne")

    def handle(self, *args, **options):
        try:
            with open(options['file'], encoding='utf-8') as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f'Fichier illisible : {exc}')
        if payload.get('format') != 'fbpack-ink-history':
            raise CommandError("Ce fichier n'est pas un export d'historique d'encre.")

        db = connection.settings_dict
        self.stdout.write(f"Base cible : {connection.vendor} · {db.get('HOST') or '(local)'} · {db.get('NAME')}")
        if connection.vendor == 'sqlite':
            self.stdout.write(self.style.WARNING(
                "Attention : la base est SQLite (locale). Vérifie que DATABASE_URL pointe vers Neon."))

        try:
            InkCalculationJob.objects.count()
        except Exception as exc:
            raise CommandError(
                f"La table des calculs n'existe pas sur cette base ({exc}). "
                "Lance d'abord : python manage.py migrate")

        User = get_user_model()
        fallback = None
        if options['user']:
            fallback = User.objects.filter(username=options['user']).first()
            if fallback is None:
                raise CommandError(f"Utilisateur de repli introuvable : {options['user']}")

        stats = {'jobs_crees': 0, 'jobs_deja_presents': 0, 'couleurs': 0,
                 'ancrages_crees': 0, 'attribues_au_repli': 0}
        erreurs = []

        with transaction.atomic():
            for item in payload.get('jobs', []):
                try:
                    self._import_job(item, User, fallback, stats)
                except Exception as exc:
                    erreurs.append(f"« {item.get('name', '?')} » : {exc}")
            # tout-ou-rien : une seule erreur, ou pas de --apply -> annulation complète
            if erreurs or not options['apply']:
                transaction.set_rollback(True)

        for e in erreurs:
            self.stdout.write(self.style.ERROR(f"ERREUR {e}"))
        if erreurs:
            self.stdout.write(self.style.ERROR(
                "AUCUNE ÉCRITURE : corrige les erreurs ci-dessus puis relance."))
            raise CommandError(f"{len(erreurs)} erreur(s), import annulé.")

        if options['apply']:
            self.stdout.write(self.style.SUCCESS("== ÉCRIT =="))
        else:
            self.stdout.write(self.style.WARNING("== SIMULATION : rien n'a été écrit =="))
        for k, v in stats.items():
            self.stdout.write(f"{k}: {v}")
        if not options['apply']:
            self.stdout.write(self.style.WARNING("Relance avec --apply pour écrire."))

    def _import_job(self, item, User, fallback, stats):
        created_at = parse_datetime(item['created_at'])
        if created_at is None:
            raise ValueError('date de création invalide')

        exists = InkCalculationJob.objects.filter(
            name=item['name'], created_at=created_at,
            width_mm=item['width_mm'], length_m=item['length_m'],
            transfer_percent=item['transfer_percent']).exists()
        if exists:
            stats['jobs_deja_presents'] += 1
            return

        user = User.objects.filter(username=item['created_by']).first() or fallback
        if user is None:
            raise ValueError(f"créateur « {item['created_by']} » absent en ligne : utilise --user")
        if user.username != item['created_by']:
            stats['attribues_au_repli'] += 1

        job = InkCalculationJob.objects.create(
            name=item['name'], process=item['process'],
            width_mm=item['width_mm'], length_m=item['length_m'],
            repeat_mm=item['repeat_mm'], poses_across=item['poses_across'],
            poses_repeat=item['poses_repeat'],
            transfer_percent=item['transfer_percent'], loss_percent=item['loss_percent'],
            confidence=item['confidence'], created_by=user)
        # auto_now_add écrase la date : on restaure la date d'origine
        InkCalculationJob.objects.filter(pk=job.pk).update(created_at=created_at)

        for c in item['colors']:
            a = c['anilox']
            anilox, was_created = AniloxRoll.objects.get_or_create(
                lineature=a['lineature'], volume_cm3_m2=Decimal(a['volume_cm3_m2']),
                defaults={'quantity': 1, 'notes': 'créé par import historique'})
            if was_created:
                stats['ancrages_crees'] += 1
            InkCalculationColor.objects.create(
                job=job, name=c['name'], ink_type=c['ink_type'],
                coverage_percent=c['coverage_percent'], coverage_area_cm2=c['coverage_area_cm2'],
                anilox=anilox, density=c['density'],
                price_per_kg=Decimal(c['price_per_kg']),
                actual_consumed_kg=c['actual_consumed_kg'], recovered_kg=c['recovered_kg'])
            stats['couleurs'] += 1
        stats['jobs_crees'] += 1
