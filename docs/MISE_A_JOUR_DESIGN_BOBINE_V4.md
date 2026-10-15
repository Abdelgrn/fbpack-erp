# MISE À JOUR DESIGN BOBINE V4 — Fiches techniques Prépresse

Date : 13/10/2026 · Base : archive cumulative `FBPACK_Fiches_Techniques_Prepress_0048_ASSISTANT_V3`
Périmètre : module Prépresse → fiches techniques (consultation, impression, PDF WeasyPrint, secours ReportLab).

## 1. Demande utilisateur traitée

1. « Dans le côté VISUEL / MAQUETTE PRODUIT, je ne veux pas que ce soit juste un visuel :
   je donne juste le visuel de la maquette et l'ERP me fait le visuel en bobine d'impression
   suivant le sens. »
2. « En haut où il y a mon logo, je ne veux pas avoir cet arrière-plan bleu : juste mon logo
   sur du blanc. »

## 2. Ce qui a changé

### 2.1 Visuel bobine d'impression (serveur, Pillow uniquement)

- Nouveau moteur `compose_roll_image()` dans `core/services/prepress_technical_sheet.py` :
  - rouleau enroulé en haut (mandrin, tranches, ombrage cylindrique, maquette enroulée) ;
  - web en S descendant portant 3 à 4 répétitions **jointives** de la maquette :
    une homographie (coefficients perspective résolus en interne, élimination de Gauss 8×8)
    par segment → aucune échancrure, quelle que soit la courbure ;
  - masque ruban par polygone offset supersamplé (anti-crénelé, sans artefact) ;
  - orientation des étiquettes dictée par `sens_bobine` (1 à 8) via `SENS_ROTATION`,
    cohérente avec le pictogramme « sens » historique ; sens 5 à 8 = web miroir ;
  - rognage tolérant des marges claires d'une maquette scannée (`_trim_light_borders`) ;
  - aucune dépendance nouvelle : Pillow est déjà dans `requirements.txt`.
- `build_roll_visual_data_uri(product)` : data-URI PNG du visuel bobine ; **retourne une
  chaîne vide en cas d'absence de maquette, de Pillow ou d'image illisible** — la fiche
  retombe alors sur le visuel plat, puis sur le placeholder « VISUEL / MAQUETTE PRODUIT ».
  Aucune exception ne remonte jamais vers la vue.
- Contexte `build_print_context()` enrichi de :
  `roll_visual_data_uri`, `sens_rotation_deg` (rotation CSS de la flèche du pictogramme),
  `spot_css` (position du point du pictogramme spot). Les pictogrammes restent pilotés
  serveur, aucune logique dans le template.
- Canevas : `{% if roll_visual_data_uri %}` → bobine ; `{% elif product_visual_data_uri %}` →
  visuel plat (repli) ; `{% else %}` → placeholder historique.
- Secours ReportLab : dessine désormais la bobine (`roll_visual_data_uri`) avec repli visuel
  plat puis placeholder — parité totale avec WeasyPrint.

### 2.2 Logo sur fond blanc

- Nouvel asset `core/static/logo_blanc.png` : glyphe FB Pack doré sur **fond transparent**
  (donc sur blanc à l'impression), extrait du logo existant par alpha-matting « goldness »,
  upscales ×3 (639×216) pour l'impression.
- `_logo_data_uri()` sert `logo_blanc.png` en priorité, repli historique `logo.png`.
- Canevas : classe `.ft-logo-plain`, aucun rectangle coloré derrière le logo.
- Secours ReportLab : le rectangle navy `roundRect(28, 522, 132, 40)` est **supprimé** ;
  repli texte « FB PACK » en navy sur fond blanc si aucun logo n'est trouvé.

### 2.3 Canevas `_technical_sheet_canvas.html`

- Reconstruit à l'identique du Design Métier V2 validé (fond clair, titre encadré rouge,
  cartouche FLEXO/HELIO, valeurs bleues italiques, métriques sur fond rose, tableau 8 couleurs,
  pictogrammes sens/spot, observations, pied de page) avec les deux évolutions ci-dessus.
- Mise en page **table / inline-block** (pas de flexbox imbriquée) : c'est la seule combinaison
  rendue correctement par les trois moteurs (navigateur, WeasyPrint, et cohérence ReportLab).
- Corrections PDF cumulatives **conservées** : `.ft-box { display:flex; }` et pied de page en
  `position:absolute` (déplacé hors du flux flex, ancré sur la page : WeasyPrint ignore un
  enfant absolu dans un conteneur flex).
- `html, body { height: 100% }` porté par le canevas lui-même : la boîte occupe exactement la
  page A4 paysage, le pied de page absolu se cale en bas de page.
- Toutes les variables Django historiques sont conservées (mêmes filtres, mêmes défauts « — »).

## 3. Ce qui n'a PAS changé

- Modèles, migration 0048, formulaire, vues, permissions `module_required('prepress')`,
  routes nommées, Assistant FB PACK, calculs serveur autoritaires, révisions JSON : intacts.
- Aucune nouvelle route, aucune nouvelle migration, aucune nouvelle dépendance.
- Sens historiques 5 à 8 conservés et désormais reflétés visuellement (web miroir).

## 4. Validations effectuées (environnement de reconstruction, 13/10/2026)

- `py_compile` : service, tests, vérificateur → OK.
- Rendu Django standalone du canevas (contexte simulé complet) → OK.
- **WeasyPrint 62.3 / pydyf 0.11** : PDF généré → **1 page, A4 paysage (841,89 × 595,28 pt)**,
  pied de page présent dans le texte PDF, observations complètes.
- Visuels bobine contrôlés visuellement pour les sens 1, 2, 3, 6 (rotations 180/0/90/0-miroir).
- Compositions : ~0,2 s par fiche (acceptable pour consultation/PDF).
- À exécuter chez toi après installation (le lot ne contient pas les 8 autres templates) :
  `python manage.py check`
  `python manage.py test core.test_prepress_technical_sheet core.test_erp_assistant_technical_sheet -v 2`
  `python scripts/verify_prepress_0048.py --project-root .`
  `python scripts/verify_assistant_fiches_v3.py --project-root .`

## 5. Installation (Windows / PowerShell)

Copier chaque fichier du lot par-dessus la version existante (sauvegarde préalable conseillée) :

```powershell
Copy-Item .\lot\core\services\prepress_technical_sheet.py .\core\services\ -Force
Copy-Item .\lot\core\static\logo_blanc.png .\core\static\ -Force
Copy-Item .\lot\core\test_prepress_technical_sheet.py .\core\ -Force
Copy-Item .\lot\templates\prepress\_technical_sheet_canvas.html .\templates\prepress\ -Force
Copy-Item .\lot\scripts\verify_prepress_0048.py .\scripts\ -Force
```

Aucun `collectstatic` nécessaire en DEBUG ; sur Render : `python manage.py collectstatic --noinput`.

## 6. Retour arrière

Replacer le canevas et le service de l'archive `..._ASSISTANT_V3` (V3) : le lot est strictement
additif/remplaçant fichier par fichier, sans touché aux modèles ni aux routes.

## 7. Correctif V4.1 (même lot, version corrigée du moteur bobine)

Suite retour utilisateur (« la bobine n'est pas symétrique et la laize de la bobine n'est pas
la même que le bandeau ») :

- **Longueur du rouleau == largeur du web** (300 px = 300 px) : la laize enroulée et le
  bandeau descendant sont désormais cohérents ; plus de rouleau plus large que le web.
- **Rouleau centré sur l'axe du canevas** avec **deux caps identiques** (tranches enroulées +
  mandrin) aux deux extrémités : composition symétrique.
- **Web en S symétrique** (une période complète, départ et retour au centre, amplitude 26 px)
  et **traverses horizontales exactement partagées** entre demi-segments : continuité parfaite,
  plus aucune étiquette coupée ni décalée, distorsion interne quasi nulle
  (deux homographies par répétition).
- **Poses en laize** : la maquette est répétée `nb_poses_laize` fois (plafonné à 3) côte à côte
  sur le web et sur le rouleau, comme sur une vraie bobine imprimée.
- **Fin de web propre** : nombre entier de répétitions (3 à 6), plus de ruban coupé net.
- Signature : `compose_roll_image(maquette_bytes, sens='1', poses_laize=1)` ;
  `build_roll_visual_data_uri(product)` transmet `product.nb_poses_laize`.
