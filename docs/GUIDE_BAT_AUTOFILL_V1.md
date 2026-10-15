# Guide d'utilisation — Remplissage automatique depuis la fiche BAT (LOT BAT AUTOFILL V1)

## Écran concerné
Calculateur de consommation d'encre (menu prépresse, permission module `prepress`).

## Mode opératoire quotidien

1. Ouvrir le calculateur : un bloc « 📄 Remplissage automatique depuis la fiche BAT »
   surmonte le formulaire.
2. Cliquer sur le champ fichier et choisir la BAT du fournisseur :
   - **PDF** (avec ou sans texte) → lu par Gemini, page par page ;
   - **PNG, JPG, WEBP** → lu par Gemini ;
   - la fiche est envoyée à Gemini : aucun autre moteur n'est utilisé (V1.11, OCR supprimé).
3. Cliquer **« 🔍 Analyser la BAT »** (le formulaire n'est PAS enregistré à ce stade).
4. L'écran affiche :
   - à gauche l'**aperçu** de la fiche (zoom possible via clic droit → ouvrir l'image) ;
   - à droite le **récapitulatif détecté** (pastille / nom / type / couv. % / surface cm²) ;
   - dessous, la **Séparation des couleurs pré-remplie** : chaque ligne porte sa pastille
     colorée, son nom, son type (Couleur / Blanc TiO₂ / Vernis), sa couverture et sa surface
     si lues. Les champs job (laize, pas de coupe, poses) sont complétés **s'ils étaient vides**.
5. Les champs **Nom du job, Laize, Pas de coupe, Poses** sont complétés depuis la BAT
   (lus par Gemini) s'ils étaient vides ; la **densité** de chaque ligne arrive
   pré-remplie (1,3 / blanc 1,5) et reste modifiable.
6. **Corriger** : renommer une couleur, supprimer une ligne parasite (logo), ajouter une
   ligne manquante (« + Couleur »), saisir cm² / % manquants, choisir l'Anilox et le prix
   de chaque ligne (non fournis par la BAT).
7. Compléter métrage, transfert, perte puis **« Calculer et enregistrer »** :
   le calcul (couverture × volume Anilox × transfert × densité, + perte) est inchangé.

## Lecture des avertissements
- « Lecture IA Gemini : n couleur(s) » → vérifiez chaque valeur avant « Calculer et enregistrer ».
- « erreur HTTP 503 » ou « délai dépassé » après plusieurs essais → l'API Gemini est surchargée ou lente : réessayez dans quelques minutes.
- « Analyse IA impossible » ou « GEMINI_API_KEY n'est pas définie » → aucune ligne n'est remplie :
  saisissez les lignes à la main, et prévenez l'administrateur si le message persiste.
- « Nombre de couleurs différent de la mention » → comparez la fiche et les lignes.
- « Analyse terminée mais aucune pastille reconnue » → fichier trop dégradé : saisie manuelle.

## Règles de nommage appliquées
- Process : `CYAN`, `MAGENTA`, `JAUNE`, `NOIR` (tolérance serrée, prioritaires).
- Pantone usuels flexo : `PANTONE 485 C`, `186 C`, `032 C`, `WARM RED C`, `RUBINE RED C`,
  `RHODAMINE RED C`, `REFLEX BLUE C`, `072 C`, `VIOLET C`, `2685 C`, `355 C`, `347 C`,
  `GREEN C`, `3272 C`, `ORANGE 021 C`, `151 C`, `1235 C`, `BROWN C`, `4695 C`, `BLACK C`…
- Mots-clés : `blanc`/`white` → Blanc TiO₂ ; `vernis`/`varnish` → Vernis.
- Couleur hors référentiel : `Couleur BAT #RRGGBB` (renommer librement).

## Retrouver ses calculs enregistrés
- Bouton « 📚 Historique des calculs » en haut du calculateur, ou route `ink/history/`.
- Chaque ligne s'ouvre sur la fiche détail : graphique net / à préparer / réel,
  tableau par couleur et saisie des consommations réelles (« Enregistrer le réel »).

## Fournisseur de clichés (V1.10)
- Champ « Fournisseur clichés… » à côté du nom du job : Studio Flexo, Poly Slim, Yahiaoui Photogravure, Autre.
- Pré-rempli si la fiche le montre ; à vérifier puis enregistré avec le calcul.
- Tableau « consommation par fournisseur » sur la liste des calculs : kg totaux, moyenne par job, g/m².

## Ce qui n'est jamais fait automatiquement
- aucun enregistrement de job ni fichier BAT stocké par l'application ;
- **envoi externe** : la fiche BAT (PDF ou image) est envoyée à l'API Gemini de Google pour lecture ; sans `GEMINI_API_KEY`, aucune analyse n'est faite ;
- aucun choix d'Anilox, de densité, de prix : décision opérateur ;
- le calcul lui-même : uniquement via « Calculer et enregistrer ».

## Réglages Render (V1.11)
- Start Command : `gunicorn fbpack.wsgi --workers 1 --timeout 240` (une analyse IA peut durer jusqu'à environ 3 min en cas d'erreur passagère).
- Environment : `GEMINI_API_KEY` doit être défini, sinon l'analyse BAT est indisponible (message affiché).

## Moteur OCR local (V1.15)
- Aucune clé API nécessaire pour le calculateur. La fiche est lue sur le serveur par RapidOCR.
- Le formulaire est pré-rempli ; vérifiez chaque ligne (surtout celles marquées « vérifiez » ou « à saisir ») avant « Calculer et enregistrer ».
- Un nom « Encre n°k (nom à saisir) » signifie que l'OCR ne l'a pas lu : saisissez-le. Aucun nom n'est deviné.
- Un avertissement « Cartouche non reconnu » signifie que le gabarit n'est pas géré : laize et pas à saisir, lecture partielle.

### Déploiement Render (à faire une fois)
1. Plan : au moins 1 Go de mémoire (le plan gratuit de 512 Mo est insuffisant : la lecture atteint 420–600 Mo).
2. Commande de build : `pip install -r requirements.txt && pip uninstall -y opencv-python && pip install --force-reinstall --no-deps opencv-python-headless==4.11.0.86`
   (RapidOCR installe `opencv-python`, qui exige libGL absente des serveurs : la variante headless la remplace.)
3. Commande de démarrage inchangée : `gunicorn fbpack.wsgi --workers 1 --timeout 240`.
4. Contrôle après déploiement : `python -c "import cv2, rapidocr_onnxruntime"` doit s'exécuter sans erreur.
