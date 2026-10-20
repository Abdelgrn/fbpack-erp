"""Exporte l'historique des calculs d'encre dans un fichier JSON.

Lecture seule : ne modifie ni ne supprime rien.
À lancer sur la base LOCALE (SQLite, Windows) :

    python manage.py export_ink_history --out ink_history_export.json

Non exportés : liens vers Client, Produit technique et OF (ils ne sont pas
identiques en ligne). Les calculs importés en ligne n'ont donc pas ces liens.
"""
import json

from django.core.management.base import BaseCommand

from core.models import InkCalculationJob


class Command(BaseCommand):
    help = "Exporte l'historique des calculs d'encre en JSON (lecture seule)."

    def add_arguments(self, parser):
        parser.add_argument('--out', default='ink_history_export.json',
                            help='Fichier de sortie (défaut : ink_history_export.json)')

    def handle(self, *args, **options):
        qs = (InkCalculationJob.objects
              .select_related('created_by')
              .prefetch_related('colors__anilox')
              .order_by('id'))
        jobs = []
        for j in qs:
            jobs.append({
                'name': j.name,
                'process': j.process,
                'width_mm': j.width_mm,
                'length_m': j.length_m,
                'repeat_mm': j.repeat_mm,
                'poses_across': j.poses_across,
                'poses_repeat': j.poses_repeat,
                'transfer_percent': j.transfer_percent,
                'loss_percent': j.loss_percent,
                'confidence': j.confidence,
                'created_by': j.created_by.get_username(),
                'created_at': j.created_at.isoformat(),
                'colors': [{
                    'name': c.name,
                    'ink_type': c.ink_type,
                    'coverage_percent': c.coverage_percent,
                    'coverage_area_cm2': c.coverage_area_cm2,
                    'anilox': {'lineature': c.anilox.lineature,
                               'volume_cm3_m2': str(c.anilox.volume_cm3_m2)},
                    'density': c.density,
                    'price_per_kg': str(c.price_per_kg),
                    'actual_consumed_kg': c.actual_consumed_kg,
                    'recovered_kg': c.recovered_kg,
                } for c in j.colors.all()],
            })
        payload = {'format': 'fbpack-ink-history', 'version': 1,
                   'count': len(jobs), 'jobs': jobs}
        with open(options['out'], 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(
            f"{len(jobs)} calcul(s) exporté(s) dans {options['out']}"))
