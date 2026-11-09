"""Cherche des secrets ecrits en dur : fichiers suivis par Git ET historique complet.

Usage (a la racine du projet) :   python verifier_secrets.py
Les valeurs trouvees sont MASQUEES dans l'affichage.
"""
import re
import subprocess
import sys
from collections import OrderedDict

MOTIFS = OrderedDict([
    ('affectation de secret',
     re.compile(r"""(?i)\b([A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASSWD|API_?KEY)[A-Z0-9_]*)\s*[=:]\s*['"]([^'"\s]{8,})['"]""")),
    ('cle Google (AIza...)', re.compile(r'AIza[0-9A-Za-z_\-]{30,}')),
    ('URL de base de donnees avec mot de passe',
     re.compile(r'(?i)(?:postgres(?:ql)?|mysql)://[^\s:@/]+:[^\s@/]+@\S+')),
    ('cle privee', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----')),
    ('jeton Bearer en dur', re.compile(r'(?i)bearer\s+[A-Za-z0-9_\-\.]{24,}')),
])
FAUX_POSITIFS = ('dev-only', 'changeme', 'change-me', 'exemple', 'example', 'votre_', 'your_',
                 'xxxx', '****', 'placeholder', '<', '{{', '${', 'os.environ', 'getattr(', 'request.')
IGNORER_CHEMIN = ('node_modules/', 'static/vendor/', 'package-lock.json', '.min.js', '.min.css',
                  'staticfiles/')
IGNORER_EXT = ('.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.sqlite3', '.woff', '.woff2',
               '.ttf', '.lock', '.pyc')


def git(*args):
    return subprocess.run(['git', *args], capture_output=True, check=True).stdout


def masquer(valeur):
    return f"{valeur[:3]}***({len(valeur)} car.)"


def analyser_ligne(ligne):
    bas = ligne.lower()
    if any(f in bas for f in FAUX_POSITIFS):
        return
    for nom, motif in MOTIFS.items():
        for m in motif.finditer(ligne):
            if nom == 'affectation de secret':
                yield nom, f"{m.group(1)} = {masquer(m.group(2))}"
            else:
                yield nom, masquer(m.group(0))


def ignorer(chemin):
    c = chemin.replace('\\', '/').lower()
    return any(p in c for p in IGNORER_CHEMIN) or c.endswith(IGNORER_EXT)


def scanner_fichiers():
    trouves = {}
    for chemin in git('ls-files', '-z').decode('utf-8', 'replace').split('\0'):
        if not chemin or ignorer(chemin):
            continue
        try:
            with open(chemin, 'rb') as f:
                contenu = f.read(2_000_000).decode('utf-8', 'ignore')
        except OSError:
            continue
        for i, ligne in enumerate(contenu.splitlines(), 1):
            for nom, valeur in analyser_ligne(ligne):
                trouves.setdefault((nom, valeur), []).append(f"{chemin}:{i}")
    return trouves


def scanner_historique():
    trouves, chemin, commit = {}, '?', '?'
    proc = subprocess.Popen(['git', 'log', '--all', '-p', '-U0', '--no-color', '--no-ext-diff'],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    for brut in proc.stdout:
        ligne = brut.decode('utf-8', 'replace').rstrip('\r\n')
        if ligne.startswith('commit '):
            commit = ligne[7:15]
        elif ligne.startswith('diff --git'):
            chemin = ligne.split(' b/', 1)[-1]
        elif ligne.startswith('+') and not ligne.startswith('+++') and not ignorer(chemin):
            for nom, valeur in analyser_ligne(ligne[1:]):
                trouves.setdefault((nom, valeur), set()).add(f"{chemin} (commit {commit})")
    proc.wait()
    return trouves


def main():
    try:
        git('rev-parse', '--git-dir')
    except Exception:
        print("Lancez ce script a la racine du depot Git.")
        return 2

    actuels = scanner_fichiers()
    historique = scanner_historique()

    print('=== 1. Dans les fichiers actuels ===')
    if not actuels:
        print('Rien de suspect.')
    for (nom, valeur), lieux in sorted(actuels.items()):
        print(f"  [{nom}] {valeur}\n      {', '.join(lieux[:3])}")

    anciens = {k: v for k, v in historique.items() if k not in actuels}
    print('\n=== 2. Uniquement dans l\'historique (retirees du code mais toujours recuperables) ===')
    if not anciens:
        print('Rien de suspect.')
    for (nom, valeur), lieux in sorted(anciens.items()):
        lieux = sorted(lieux)
        print(f"  [{nom}] {valeur}\n      {lieux[0]}" + (f" (+{len(lieux) - 1} autre(s))" if len(lieux) > 1 else ''))

    total = len(actuels) + len(anciens)
    print(f"\n{total} valeur(s) a verifier. Toute valeur reelle (mot de passe, jeton, cle) doit etre CHANGEE,"
          " meme si elle a ete retiree du code.")
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main())