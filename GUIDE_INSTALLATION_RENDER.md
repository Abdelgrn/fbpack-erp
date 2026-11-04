# Kit de préparation des assets locaux — Django / Render

## Pourquoi les commandes précédentes échouaient

Le projet local n’avait ni `package.json`, ni `package-lock.json`, ni script npm `build:assets`. `npm ci` ne peut pas créer ces fichiers : il installe à partir d’un lockfile déjà présent. De même, `npm run build:assets` ne peut fonctionner qu’après l’ajout du script au `package.json`.

Cette archive fournit les fichiers de configuration manquants. Elle ne contient volontairement ni `node_modules`, ni CSS Tailwind compilé : le CSS doit être généré à la racine du véritable projet pour que Tailwind puisse analyser ses templates.

## Contenu

- `package.json` et `package-lock.json` — versions exactes des dépendances et commande de build.
- `tailwind.config.cjs` — configuration Tailwind v3, avec les couleurs personnalisées déjà présentes dans la base fournie.
- `static/src/tailwind.css` — fichier source du CSS compilé.
- `scripts/copy-chart.js` — copie le build UMD local de Chart.js dans `static/vendor/`.

Versions verrouillées dans ce kit : Tailwind CSS `3.4.19` et Chart.js `4.6.1`. Tailwind reste en version 3 pour conserver la syntaxe de configuration utilisée par la base actuelle ; ne pas passer à Tailwind 4 dans le même changement.

## Installation locale sous Windows / PowerShell

1. Décompressez le contenu de l’archive à la racine du projet — le dossier qui contient `manage.py`. Fusionnez `static/src/` et `scripts/` avec les dossiers existants. Ne remplacez pas un éventuel fichier de configuration déjà présent sans l’avoir comparé.
2. À cette racine, exécutez :

   ```powershell
   npm ci --include=dev
   npm run build:assets
   ```

   La première commande doit maintenant fonctionner : le kit inclut un `package-lock.json` compatible. La seconde génère `static/css/tailwind.min.css` et `static/vendor/chart.umd.min.js`.
3. Vérifiez que le CSS généré contient les classes utilisées dans les pages de l’ERP. La configuration parcourt les templates Django (`templates/**/*.html` et répertoires d’applications), le JavaScript statique et les fichiers Python. Si une classe est construite par concaténation à l’exécution, il faudra l’ajouter à une safelist ou écrire ses noms complets dans le code source.
4. Dans le `base.html` réellement utilisé, remplacez l’import CDN Tailwind par :

   ```django
   <link rel="stylesheet" href="{% static 'css/tailwind.min.css' %}">
   ```

   Remplacez l’import CDN Chart.js, en gardant son emplacement relatif par rapport aux scripts qui s’en servent, par :

   ```django
   <script src="{% static 'vendor/chart.umd.min.js' %}"></script>
   ```

   Déplacez les options de `tailwind.config` (notamment `darkMode` et les couleurs `neon`, `darkbg`, `panel`, `lightbg`, `lightcard`) dans `tailwind.config.cjs`. Retirez ensuite uniquement ce bloc de configuration runtime ; conservez les autres fonctions JavaScript de la base.
5. Lancez la collecte Django :

   ```powershell
   python manage.py collectstatic --no-input
   ```

## Build Render

Conservez le `build.sh` et le Build Command actuels. Dans le script existant, ajoutez ces deux commandes **après l’installation des dépendances Python et avant `collectstatic`** :

```bash
npm ci --include=dev
npm run build:assets
```

La suite doit conserver l’appel actuel à `python manage.py collectstatic --no-input`. Ne remplacez pas le script de déploiement complet par cet extrait et ne changez pas la commande Gunicorn. Commitez `package.json`, `package-lock.json`, `tailwind.config.cjs`, le fichier source CSS et le script de copie — jamais `node_modules/`.

## Contrôle à faire après installation

- Vérifier l’apparence des pages, les thèmes clair et sombre, et les pages qui utilisent des graphiques.
- Vérifier dans l’onglet Réseau du navigateur qu’aucune requête ne part vers `cdn.tailwindcss.com` ou `cdn.jsdelivr.net`.
- Exécuter `python manage.py collectstatic --no-input` après chaque build local et lors des déploiements Render.

## Avertissement `logo.png` de collectstatic

Ce message est distinct de npm. Django a trouvé au moins deux sources portant le même chemin de destination `logo.png` ; il en collecte une et ignore l’autre. Pour trouver les sources, exécutez :

```powershell
python manage.py findstatic logo.png --verbosity 2
```

Vérifiez laquelle est utilisée et donnez aux fichiers des chemins statiques uniques (par exemple `core/images/logo.png` et `of/images/logo.png`), puis ajustez leurs références. Ne supprimez pas un logo avant d’avoir confirmé ses usages.
