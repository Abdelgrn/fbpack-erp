# Créez un fichier: core/management/commands/fix_duplicate_machines.py

from django.core.management.base import BaseCommand
from core.models import Machine

class Command(BaseCommand):
    help = 'Corrige les doublons de code_machine'

    def handle(self, *args, **options):
        machines = Machine.objects.all()
        codes_vus = set()
        
        for machine in machines:
            if machine.code_machine in codes_vus:
                # Générer un nouveau code unique
                nouveau_code = f"{machine.code_machine}_{machine.id}"
                self.stdout.write(f"Doublon trouvé: {machine.code_machine} -> {nouveau_code}")
                machine.code_machine = nouveau_code
                machine.save()
            else:
                codes_vus.add(machine.code_machine)
        
        self.stdout.write(self.style.SUCCESS('Doublons corrigés!'))