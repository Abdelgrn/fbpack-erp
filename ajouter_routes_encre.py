"""Ajoute à core/urls.py les routes Modifier / Supprimer de l'historique encre.

Usage (dans le dossier du projet, environnement .venv actif) :
    python ajouter_routes_encre.py core/urls.py
"""
import pathlib
import shutil
import sys

IMPORT = 'from core.views.ink_history import ink_calculation_edit, ink_calculation_delete'
ROUTES = [
    "    path('ink/historique/<int:job_id>/modifier/', ink_calculation_edit, name='ink_calculation_edit'),",
    "    path('ink/historique/<int:job_id>/supprimer/', ink_calculation_delete, name='ink_calculation_delete'),",
]
REPERE = "name='ink_calculation_actual'"


def main(chemin):
    p = pathlib.Path(chemin)
    if not p.is_file():
        sys.exit(f'ERREUR : fichier introuvable : {chemin}. Lancez la commande depuis le dossier du projet.')
    raw = p.read_bytes()
    fin = '\r\n' if b'\r\n' in raw else '\n'
    lignes = raw.decode('utf-8').splitlines()

    if any(IMPORT in l for l in lignes):
        print('Import déjà présent.')
    else:
        fin_imports = next((i for i, l in enumerate(lignes) if l.startswith('urlpatterns')), len(lignes))
        idx = max((i for i, l in enumerate(lignes[:fin_imports]) if l.startswith(('from ', 'import '))), default=-1)
        lignes.insert(idx + 1, IMPORT)
        print('Import ajouté.')

    if any("name='ink_calculation_edit'" in l for l in lignes):
        print('Routes déjà présentes : rien à ajouter.')
    else:
        pos = next((i for i, l in enumerate(lignes) if REPERE in l), None)
        if pos is None:
            sys.exit("ERREUR : ligne de repère introuvable (name='ink_calculation_actual'). Fichier NON modifié.")
        lignes[pos + 1:pos + 1] = ROUTES
        print('Routes ajoutées après la ligne', pos + 1, '.')

    shutil.copy2(p, str(p) + '.bak_avant_encre')
    p.write_bytes((fin.join(lignes) + fin).encode('utf-8'))
    print('OK. Sauvegarde : ' + str(p) + '.bak_avant_encre')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Usage : python ajouter_routes_encre.py core/urls.py')
    main(sys.argv[1])
