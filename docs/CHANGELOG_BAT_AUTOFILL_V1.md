## [BAT-AUTOFILL-V1.16] — 2026-10-15
### Corrigé après essai réel (V1.15)
- **Gabarit Poly Slim reconnu** (« Carré Décoré Caramel ») : format H = laize par piste, Laize Bobine = laize totale, Dev Cylindre = pas de coupe, N°Piste / N°Pose = poses, Couleurs Utilisées = nombre de couleurs. Le cartouche est lu ; les six encres sont pré-remplies.
- **Noms Poly Slim** : « P7565 », « P9224 », « P185 » deviennent PANTONE 7565, 9224, 185 ; « Opaque White » devient Blanc.
- **Surfaces Poly Slim** : calculées sur piste × développement (205 × 480 = 984 cm²). Un avertissement demande de vérifier la base de calcul.
- **Suffixe Pantone** : tout PANTONE sans suffixe C ou U est signalé « à vérifier » (ex. PANTONE 234, 485, 654).
- Image agrandie avant lecture si sa largeur est inférieure à 2000 px.
- Laize totale marquée « non lue » quand le gabarit ne la donne pas (ex. Yahiaoui 1 pose).
### Non-régression
- Fiches validées inchangées : RIFKUS spaghetti, HAMAMA moyen 1 kg, HAMAMA FIN 500 g, djari, CHOR KHALED, Bronzi 4717-26.
### Limites connues
- Gabarit Dulcesol / Poly Slim : une colonne (Black) n'est pas lue sur l'image 3 (capture de fiche plus petite) ; le total des couleurs annoncées permet de le repérer.
- « gold » non détecté sur HAMAMA moyen (à saisir).
- Chips mini RIFKUS ketchup (7 C) : non fourni dans les fichiers de ce tour ; résultat de l'essai utilisateur conservé dans la capture.
### Fichiers
- `core/services/bat_ocr.py` (remplacé), `core/services/bat_extractor.py` (remplacé), `core/tests/test_bat_ocr.py` (remplacé).
### Tests
- 23 tests hors Django OK ; 1 test réel ignoré sans BAT_SAMPLES_DIR (RIFKUS passe quand il est défini).

## [BAT-AUTOFILL-V1.15] — 2026-10-15
### Changement de règle (à valider) : OCR local, sans API
- L'analyse des fiches BAT n'appelle plus Gemini ni aucune API. Elle utilise **RapidOCR** (paquet pip, moteur ONNX) exécuté sur le serveur.
- **Aucun envoi de la fiche à un tiers** pour le calculateur. Le module stock (scan d'étiquette) garde son propre appel Gemini, inchangé.
- Variable `GEMINI_API_KEY` : plus nécessaire pour le calculateur (toujours utilisée par le stock).
### Ce qui est lu
- Cartouche technique recherché en haut puis en bas de page (gabarits Studio Flexo et Yahiaoui).
- Champs : laize piste, laize totale, pas de coupe, poses en laize et en coupe, dossier, nombre de couleurs, LPI, épaisseur de cliché, date, nom du job (sans « AMALGAME »).
- Encres : nom, cm², %. Colonnes ancrées sur les pourcentages ; cm² rattaché à sa colonne par position.
- **Contrôle croisé** : cm² = % × laize × pas. Un cm² manquant est calculé depuis le % (et inversement) ; une incohérence est signalée et recalculée, avec mention « vérifiez ».
- Noms ramenés à un vocabulaire fixe (Cyan, Magenta, Yellow, Black, Gold, Blanc, B.Ref, PANTONE xxx [C]). Un nom non reconnu devient « Encre n°k (nom à saisir) » : **aucun nom n'est deviné**.
- Confiance OCR < 70 % : la valeur est signalée « vérifiez ».
### Résultats mesurés (fiches réelles, bac à sable)
- RIFKUS spaghetti (6 C) : 6/6 encres, laize 385 / totale 1155 / pas 240, fournisseur Studio Flexo.
- Bronzi 4717-26 (6 encres, cartouche en haut) : 6/6 encres, laize 255 / pas 260, fournisseur Yahiaoui.
- HAMAMA FIN 500 g (6 C) : 6/6 encres, laize 256 / pas 270.
- HAMAMA couscous moyen 1 kg (6 C) : valeurs justes ; « gold » non détecté par l'OCR (à saisir).
- Djari couscous moyen 1 kg (4 C) : valeurs justes ; 1 nom à saisir.
- CHOR KHALED (8 C) : 8 colonnes ; plusieurs valeurs recalculées depuis le % (signalées) ; 1 nom à saisir.
- Limites connues : gabarit Poly Slim et Dulcesol (ex. « Carré Décoré Caramel ») non reconnu comme cartouche : lecture partielle signalée, à vérifier entièrement.
- Image non fiche (capture d'écran) : refus propre (« Aucun cartouche reconnu »).
- Durée : 2 à 7 s par fiche sur le bac à sable.
### Mémoire (point critique)
- RapidOCR charge ~125 Mo puis monte à ~420–600 Mo pendant la première lecture. Le plan gratuit Render (512 Mo) est insuffisant avec Django : prévoir un plan d'au moins 1 Go (voir GUIDE).
### Fichiers
- `core/services/bat_ocr.py` (nouveau moteur) ; `core/services/bat_extractor.py` (remplacé : même contrat `analyze_bat`) ; `core/tests/test_bat_ocr.py` (nouveau) ; `core/tests/test_bat_extractor.py` (remplacé) ; `requirements.txt` (rapidocr-onnxruntime, opencv-python-headless) ; `scripts/verify_bat_autofill.py`.
- `core/services/bat_vision.py` (Gemini) : conservé mais n'est plus appelé par le calculateur.
### Tests
- 21 tests hors Django OK (dont lecture réelle de la fiche RIFKUS quand BAT_SAMPLES_DIR est défini). Non exécuté ici : suite Django complète (projet non fourni dans le bac à sable).

## [BAT-AUTOFILL-V1.14] — 2026-10-15
### Corrigé (retour réel : plus de 4 minutes d'attente puis « erreur HTTP 503 après plusieurs essais »)
- **Durée maximale bornée à 100 s** (au lieu de plus de 4 min) : l'opérateur n'attend plus indéfiniment.
- **Chaîne de modèles** : `gemini-3.8-flash` (2 essais) -> `gemini-3.5-flash-lite` (2 essais, modèle rapide conçu pour le volume)
  -> `gemini-3.6-flash` (2 essais). Un 503 sur le modèle principal bascule vers le modèle suivant.
- Attente de 4 s entre deux essais sur le même modèle ; 2 échecs réseau au total maximum.
- **Point à vérifier** : le modèle « lite » peut lire un peu moins bien les petits caractères. Les valeurs lues restent à valider dans le formulaire.
### Fichiers
- `core/services/bat_vision.py` ; `core/tests/test_bat_vision.py` (18 tests) ; documentation.
### Tests
- 30 tests hors Django OK (`test_bat_vision`, `test_cliche_suppliers`, `AnalyseGeminiSeulTests`).

## [BAT-AUTOFILL-V1.13] — 2026-10-15
### Corrigé (retour réel : « erreur HTTP 503 de l’API » sur les fiches BAT, alors que le stock fonctionne)
- **Essais plus patients** sur le modèle principal : 4 essais pour 503/429/5xx, attentes de 4 s, 10 s puis 20 s.
  Le modèle de secours `gemini-3.6-flash` a 2 essais.
- **Délais réseau** : 2 échecs (délai ou réseau) au total maximum, pour ne pas faire attendre l'opérateur trop longtemps.
- **Budget total borné à 150 s**, sous le délai Gunicorn de 240 s.
- Si le message affiché ne contient pas « après plusieurs essais », c'est que la V1.12 ou la V1.13 n'est pas encore déployée.
### Fichiers
- `core/services/bat_vision.py` ; `core/tests/test_bat_vision.py` (4 tests de relance) ; documentation.
- Aucun changement de `bat_extractor.py`, de vue, de modèle ni de migration.
### Tests
- 29 tests hors Django OK.

## [BAT-AUTOFILL-V1.12] — 2026-10-15
### Corrigé (retours réels avec clé : « erreur HTTP 503 » sur Poly Slim, « délai dépassé » sur Yahiaoui et Studio Flexo)
- **Nouvel essai** : sur erreur passagère (429, 500, 502, 503, 504 ou délai), le modèle principal est réessayé une fois après 3 s.
- **Modèle de secours** `gemini-3.6-flash` si le principal reste indisponible. Les erreurs permanentes (400, 401, 403, 404) ne sont pas relancées.
- **Image envoyée réduite** : 2048 px de large, JPEG qualité 85 (au lieu de 2600 px, qualité 90) : moins de données à envoyer.
- Délai Gunicorn à régler à **240 s** (`--timeout 240`) : pire cas d'une analyse ≈ 183 s.
### Fichiers
- `core/services/bat_vision.py` (nouvelle logique d'appel) ; `core/tests/test_bat_vision.py` (4 tests de relance).
- Aucun changement de `bat_extractor.py`, de vue, de modèle, de migration ni de moteur.
### Tests
- 29 tests hors Django OK (`test_bat_vision`, `test_cliche_suppliers`, `AnalyseGeminiSeulTests`).

## [BAT-AUTOFILL-V1.11] — 2026-10-15
### Changement de règle (demandé par l'utilisateur)
- **OCR supprimé** (RapidOCR, lecture colorimétrique, appairage des valeurs, repli local) : **Gemini est le seul moteur**
  d'analyse des fiches BAT (PNG, JPEG, WEBP, PDF avec ou sans texte).
- Sans `GEMINI_API_KEY` : message « Analyse IA indisponible » ; aucune ligne n'est inventée.
- `rapidocr-onnxruntime` retiré de `requirements.txt` (build plus léger, mémoire réduite sur Render).
### Corrigé
- Les PDF avec texte (ex. Poly Slim) étaient lus sans IA : ils passent désormais par Gemini.
- Les scans envoient la page entière à Gemini (la légende peut être en haut de la fiche, ex. Yahiaoui).
- Crash Render sur fiche Yahiaoui : pic mémoire de l'OCR local (environ 530 Mo) et délai Gunicorn de 30 s.
  Réglage requis : `gunicorn fbpack.wsgi --workers 1 --timeout 180` (voir le guide).
### Fichiers
- `core/services/bat_extractor.py` : réécrit en Gemini seul (fonctions OCR retirées).
- `core/tests/test_bat_extractor.py` : tests Gemini seul ; `InkHistoryViewTests` conservé à l'identique.
- `core/tests/test_bat_vision.py` : tests PDF Gemini et erreurs sans repli.
- `scripts/verify_bat_autofill.py`, `requirements.txt`, docs.
- Aucun changement de vue, de modèle, de migration ni de moteur de calcul.
### Tests
- 27 tests hors Django OK (`test_bat_vision`, `test_cliche_suppliers`, `AnalyseGeminiSeulTests`, `DensityDefaultTests`).
- `InkHistoryViewTests` : base Django, à lancer sur votre poste.

## [BAT-AUTOFILL-V1.10] — 2026-10-15
### Ajouté
- **Fournisseur de clichés** sur le calculateur : liste Studio Flexo, Poly Slim, Yahiaoui Photogravure, Autre
  (vide = non renseigné). Choix enregistré sur chaque calcul (`InkCalculationJob.cliche_supplier`).
- Pré-remplissage : le fournisseur lu sur la fiche BAT (API Gemini) est proposé dans ce champ ; validation humaine.
- Liste des calculs : tableau de consommation **par fournisseur** (nombre de jobs, total kg, moyenne kg/job,
  g/m² = total kg × 1000 ÷ total m², tri décroissant). Permet de comparer les fournisseurs.
### Modifié
- `core/services/cliche_suppliers.py` (nouveau, pur Python) : liste des fournisseurs, filtre de la valeur postée, synthèse.
- `core/views/ink_calculator.py`, `templates/ink_calculator.html`, `templates/ink_calculation_list.html` : champ et tableau ci-dessus.
- `core/services/bat_extractor.py` : fournisseur extrait de la réponse IA (valeur hors liste = saisie libre conservée, non filtrée).
- **Modèle** `InkCalculationJob` : nouveau champ `cliche_supplier` (CharField 40, blank, défaut vide, choix ci-dessus).
  Fichier de remplacement fourni séparément (`FICHIERS_A_REMPLACER_MODELE_INK_V1.10/`). **Migration à générer
  sur le poste** : `python manage.py makemigrations core` puis `python manage.py migrate` (aucune migration écrite ici).
- Formules du moteur de calcul (`core/services/ink_calculator.py`) : inchangées.
### Changement de règle (rappel V1.9, à connaître)
- Lecture des fiches BAT par l'API Gemini (clé dans `GEMINI_API_KEY`) : la fiche est envoyée à Google pour lecture.
  Sans clé, ou en cas d'échec : repli OCR local avec avertissement.
### Tests
- `core/tests/test_cliche_suppliers.py` : liste, valeur hors liste rejetée, regroupement par fournisseur, g/m².
- `core/tests/test_bat_vision.py`, `core/tests/test_bat_extractor.py` : inchangés, OK.
- `scripts/verify_bat_autofill.py` : marqueurs V1.10 OK.

## [BAT-AUTOFILL-V1.9] — 2026-10-15
### Ajouté
- **Lecture IA Gemini** (même API que « Scan Étiquette (IA) » du stock) : `core/services/bat_vision.py`.
  Clé lue dans la variable d'environnement `GEMINI_API_KEY` (jamais dans le code ni dans l'URL : en-tête
  `x-goog-api-key`). Modèle `gemini-3.8-flash` (variable `GEMINI_MODEL` facultative).
- L'analyse BAT essaie l'IA en premier (PDF : bande basse de chaque page, 2 pages au plus ; image : entière).
  Sans clé, ou si l'appel échoue, la lecture locale (OCR) reprend, avec un avertissement explicite.
- Les réponses IA sont des propositions : valeurs à vérifier avant « Calculer et enregistrer ».
- **Fournisseur de clichés** détecté sur la fiche (IA, ou mots-clés sur l'OCR) : Studio Flexo, Poly Slim,
  Yahiaoui Photogravure. Affiché comme avertissement ; l'enregistrement sur chaque calcul reste à faire
  (champ de modèle + migration à générer sur le poste).
### Changement de règle (annoncé)
- Votre consigne V1.2 « pas d'API » est révisée sur demande : l'API Gemini est utilisée pour le calculateur,
  en plus de l'OCR de repli. Le moteur de calcul n'est pas modifié.
### Tests
- `core/tests/test_bat_vision.py` : clé absente, en-tête sans clé dans l'URL, erreur HTTP sans fuite,
  mapping des encres (pas de nom par position), repli OCR. Aucun appel réseau réel.

## [BAT-AUTOFILL-V1.8.1] — 2026-10-15
### Corrigé (retour terrain : formulaire inchangé, laize fausse, analyse lente)
- **Formulaire** : après une analyse, nom / laize / pas / poses prennent la valeur lue, ou restent VIDES si non lue
  (plus de « Chips RIFKUS » resté dans le champ job d'une autre fiche).
- **Laize** : plus de laize totale inventée à partir d'une seule piste ; saisie demandée (avertissement).
  Garde-fou : laize totale lue = laize d'une piste -> rejetée.
- **Vitesse** : pleine image lue d'abord ; bande basse relue seulement si la légende n'est pas nette (≥ 4 lignes).
- **Limite** : une capture d'écran de fiche (petit texte, ~600 px) n'est pas lisible fiablement par OCR.
  Utiliser le PDF d'origine ou un PNG/JPEG ≥ 2000 px de large.
### Tests
- 22 tests hors Django OK (test_hints_texte : une piste seule n'est plus la laize totale).

## [BAT-AUTOFILL-V1.8] — 2026-10-15
### Corrigé (retours PDF réels : 4 BAT couscous + capture RIFKUS)
- **Aperçu** : un PDF affiche la page rendue (pypdfium2), plus la première image embarquée (QR code).
- **Légende** : OCR sur la bande basse de la page qui porte la légende ; capture (image) lue en entier
  et en bande basse, fusionnées sans doublon.
- **Noms** : plus aucun nom déduit de la position. Nom illisible = « Encre n°k (nom à saisir) » + avertissement.
- **Motif (surface de référence)** : Σ cm² ÷ Σ % sur les lignes cohérentes (une valeur % fausse est écartée).
- **Job / laize / pas** : lus sur la fiche (y compris capture) ; avertissement « Job lu par OCR, à vérifier ».
- **Formulaire** : l'analyse écrase nom, laize, pas et poses de l'analyse précédente (plus de valeurs périmées).
- **Pantone** : « PANTONE 7731C » -> « PANTONE 7731 C », « PANTONE234 » -> « PANTONE 234 » (+ suffixe lu sous le nom).
- **Job** : « COUSCOUSMOYEN 1KGCHORKHALED » -> « COUSCOUS MOYEN 1KG CHOR KHALED ».
### Limites connues
- Poses en laize non lues par OCR (avertissement : saisir les poses).
- Fiche Chor Khaled 1 Kg : 6 couleurs lues sur 8 annoncées ; vérifier les lignes.
- Capture RIFKUS : job lu « Chips Ri FKUS spaghettibolonaise » (erreur OCR, à corriger à la main).
### Tests
- 22 tests hors Django OK (dont V18NomsEtJobTests) ; InkHistoryViewTests exige la base Django (poste local).

## [BAT-AUTOFILL-V1.7] — 2026-10-14
### Corrigé (retours terrain : fiches « La Dorée couscous » 8 C et « Chips mini RIFKUS » 7 C)
- **Légende lue par colonnes** : une colonne par valeur cm² / % (8 colonnes pour 8 C). Plus de
  manque de couleurs quand un nom est mal lu (ex. « Biack », « blane », « MO)IPA »).
- **Noms partiels** : « PANTONE » + ligne suivante recollés (« PANTONE Black C », « PANTONE Reflex Blue C »).
  Un nom illisible est remplacé par l'ordre standard (Cyan, Magenta, Jaune, Noir) **avec avertissement**,
  ou par « Ton n » à saisir.
- **Surface de référence déduite des couleurs** (médiane cm² ÷ %) : fonctionne sur les deux fiches,
  quelle que soit la laize ou le pas. Les % OCR incohérents sont corrigés et signalés.
- **PDF sans image décodable** : rendu de la page avec pypdfium2 (pip seul) au lieu de « PDF sans image ».
- **Grandes images** : OCR sur la bande basse (légende et job) pour ne pas perdre les petits caractères.
- **Poses** : non lues quand l'OCR ne les voit pas ; avertissement si laize totale ≠ poses × piste
  (ex. 975 mm = 3 × 325, mais « NBR POSES EN LAIZE » = 2 sur cette fiche : à confirmer).
- **Repli** : sans légende lisible, seules les encres process du bandeau bas sont proposées.
### Tests
- 20 tests dont « LegendeFicheDoreeTests » (fiche 8 C réelle).

# CHANGELOG — LOT BAT AUTOFILL V1 (Calculateur de consommation d'encre)

## [BAT-AUTOFILL-V1.6] — 2026-10-14
### Corrigé (retour terrain « Chips mini RIFKUS ketchup », fiche 7 C)
- **Couleurs** : 16 lignes parasites (ORANGE, PANTONE ORANGE 021 C, « Couleur BAT #… ») venaient
  des pixels de la maquette. Quand la légende est lue par OCR, seules les couleurs de la rangée
  sous « Nbr de couleurs » sont retenues (7 C → 7 lignes).
- **Blanc** : la pastille blanche était écartée ; le « blanc » de la légende est désormais retenu (100 %).
- **Pourcentages** : la surface de référence = laize d'une piste × pas de coupe (345 × 190 = 655,5 cm²).
  Un % OCR incohérent avec la surface est corrigé et signalé (ex. PANTONE 485 : 20,0 → 28,2 %).
- **Surface cm²** : le point parasite OCR « 303.977.cm² » est accepté (ne plus recalculer depuis le %).
- **Nom du job** : « AMALGAME: » n'est plus pris comme valeur de « JOB: » ; les mots fusionnés
  sont séparés (Chipsmini -> Chips mini, RIFKUSketchup -> RIFKUS ketchup).
- **Laize** : lue par étiquette (« LAIZE: 345 mm », « LAIZE Totale: 1035 mm »), avec relecture
  agrandie de la zone si la valeur n'est pas dans la même zone OCR (ex. poses « 3 »).
### Changement de règle (à connaître)
- **Laize du job = LAIZE TOTALE (toutes pistes)** : c'est elle qui sert à la surface et au métrage
  (ex. 345 × 3 poses = 1035 mm). La laize d'une piste sert au contrôle couleur × surface.
- Dans le formulaire, le champ « Laize imprimée mm » devient « Laize totale film mm (toutes pistes) ».
- Dans la vue, la vérification couleur × surface utilise `laize totale / poses en laize`.
- **Les anciens calculs saisis avec la laize d'une piste sous-estiment la surface** (× nombre de
  pistes) : à corriger si nécessaire.
### Repli sans légende lisible
- Aucun ton de maquette proposé. Seules les encres process (Cyan, Magenta, Jaune, Noir, Blanc)
  du bandeau bas sont gardées, avec avertissement.
### Tests
- 17 tests (dont 4 nouveaux « LegendeOcrTests » sur la vraie mise en page OCR de la fiche).

## [BAT-AUTOFILL-V1.5.2] — 2026-10-14
### Ajouté
- Historique : la colonne Couleurs affiche désormais les **noms des couleurs** sous le
  nombre (le test historique les exigeait ; c'était un vrai manque produit).

## [BAT-AUTOFILL-V1.5.1] — 2026-10-14
### Corrigé
- Test historique : `IntegrityError UNIQUE constraint failed: core_aniloxroll…`
  chez les projets dont une migration **seede** un anilox 420/5,0. Le test réutilise
  désormais l'enregistrement existant (user et anilox) au lieu de le recréer.

## [BAT-AUTOFILL-V1.5] — 2026-10-14
### Ajouté
- **Historique des calculs** : vue `ink_calculation_list` + template
  `ink_calculation_list.html` (route conseillée `ink/history/`) : tous les jobs
  enregistrés (id, nom, procédé, client/produit/OF, laize, métrage, nb couleurs,
  total à préparer kg, coût, auteur, date) + ouverture du détail.
  Bouton « 📚 Historique des calculs » sur le calculateur (affiché seulement si la
  route existe : `_url_or_empty`, aucun crash si urls.py non mis à jour).
- Bloc PowerShell lot : déclaration des routes `ink_calculation_actual` (POST du
  réel, utilisée par le template détail) et `ink_calculation_list`.
### Tests
- 14 tests : + rendu de la vue historique (RequestFactory, job + couleur créés).

## [BAT-AUTOFILL-V1.4.1] — 2026-10-14
### Corrigé
- Message d'aide et LIRE_MOI : la ligne urls.py proposée utilisait une **vue en chaîne
  pointonnée**, interdite par `path()` depuis Django 1.10 (`TypeError: view must be a
  callable…`). Proposition remplacée par l'import du callable + `path(..., ink_calculation_detail, ...)`.

## [BAT-AUTOFILL-V1.4] — 2026-10-14
### Corrigé
- **`Reverse for 'ink_calculation_detail' not found`** à l'enregistrement : certaines
  installations ne déclarent pas cette route dans urls.py. Nouveau `_redirect_detail` :
  essaie `ink_calculation_detail`, `ink_calculator_detail`, puis toute route
  « ink…detail » du resolver ; à défaut, message succès explicite (avec la ligne
  urls.py à ajouter) et retour au calculateur. **Le job était déjà enregistré avant
  l'erreur : aucun données perdues.**
- **Nom du job erroné (« FLEXOSOLUTIONS »)** et **poses 4/7 absentes** sur scan :
  `ocr_job_hints` réécrit **zone par zone** (étiquette cherchée dans chaque zone OCR,
  valeur dans la zone ou dans la zone voisine de droite sur la même ligne) au lieu
  d'un blob global ; garde-fous anti-logo (KODAK/FLEXCEL exclus du nom).
- **Poses non pré-remplies** : les champs portaient `value="1"`, le JS croyait un champ
  déjà saisi et n'appliquait pas le hint. Défaut retiré (le moteur mettait déjà 1 si vide).
### Tests
- 13 tests : + cas zones découpées (« JoB: » seul + nom à droite, « PASDECOUPE: » +
  valeur à droite, « NBR.POSES ENLAIZE: » + 4).

## [BAT-AUTOFILL-V1.3] — 2026-10-14
### Ajouté
- **Hints job sur SCAN par OCR** (`ocr_job_hints`) : nom du job (« JOB: … » nettoyé :
  TwinGAUFRETTE20gr → « Twin GAUFRETTE 20gr »), LAIZE (hors LAIZE Totale),
  PAS DE COUPE, POSES EN LAIZE/COUPE, LINIATURE — pré-remplis dans les champs vides.
- **Densité pré-remplie et modifiable** : 1,3 (Couleur / Vernis), 1,5 (Blanc TiO₂) —
  JS `DENSITY_DEFAULT` + `wireDensity` (recalée si changement de type tant que non
  saisie manuellement ; toute saisie manuelle désactive l'auto).
### Modifié (demande utilisateur + bug bloquant levant)
- `core/services/ink_calculator.py` (moteur historique) :
  - `density_default` : WHITE 1,35→**1,5** ; autres 1,00→**1,3** (valeurs FB PACK) ;
  - `validate_coverage` : rendait un **ratio 0-1** comparé à une couverture en % →
    avec le pré-remplissage BAT (cm² + %), tout enregistrement échouait
    (« Couverture incohérente »). Formule désormais en pourcent
    (`100*area/((repeat*width)/100)`), tolérance ±1 point conservée.
- Template : hint `name` appliqué au champ Nom du job si vide.
### Tests
- 12 tests : + hints OCR scannées (zones réalistes), + densités 1,3/1,5,
  + validate_coverage en pourcent (40.402 cm² / 140×137 mm → 21.06 %).

## [BAT-AUTOFILL-V1.2] — 2026-10-14
### Ajouté
- Lecture **Couv. % et Surface cm² sur BAT scannée/image** par OCR optionnelle
  `rapidocr-onnxruntime` (pip uniquement, modèles embarqués, offline — ni Tesseract,
  ni binaire système, ni API) :
  - `pair_ocr_values` : appairage colonne par colonne (fenêtre étroite 0,35×largeur
    de pastille, zones strictement sous la pastille, choix au centre-x le plus
    proche) + repli global par ordre de lecture ;
  - `apply_ocr_names` : nomme par OCR uniquement les pastilles non nommées par la
    colorimétrie (synonymes blanc : blane/bianc/white…) ;
  - avertissement systématique « valeurs lues par OCR : vérifiez avant calcul ».
- `requirements.txt` : ajout `rapidocr-onnxruntime==1.2.3`.
- Tests : 2 cas déterministes d'appairage/renommage OCR (9 tests au total).
### Comportement sans l'option
- Si `rapidocr-onnxruntime` absent : comportement V1 (couleurs seules sur scan,
  valeurs « à saisir ») + avertissement indiquant la commande d'activation.

## [BAT-AUTOFILL-V1.1] — 2026-10-14
### Corrigé
- `templates/ink_calculator.html` : attribut `formnovalidate` ajouté au bouton
  « 🔍 Analyser la BAT ». Sans lui, la validation HTML5 du navigateur (champs
  `required` du formulaire, ex. Couverture % d'une ligne vide) bloquait le POST :
  le clic sur « Analyser la BAT » n'atteignait jamais le serveur (« Veuillez
  remplir ce champ. »). Le bouton « Calculer et enregistrer » conserve la
  validation normale (validation humaine obligatoire avant enregistrement).

## [BAT-AUTOFILL-V1] — 2026-10-14
### Ajouté
- `core/services/bat_extractor.py` : service pur Python d'analyse de fiche BAT.
  - PDF texte (pypdf) : noms de couleurs, surfaces cm², couvertures %, appairage
    contrôlé ; indices job (LAIZE, PAS DE COUPE, POSES LAIZE/COUPE, LINIATURE).
  - PDF scanné / image : extraction colorimétrique des pastilles (Pillow + numpy) :
    blocs purs 3 paliers, composantes connexes, filtres taille/forme/rangée/maquette,
    nommage référentiel process + Pantone usuels, blanc/vernis par mot-clé.
  - Aperçu data-URI JPEG (1300 px max) pour affichage côte à côte.
  - `validate_bat_size`, `ink_type_for`, jamais d'exception remontée (`error` dict).
- `core/views/ink_calculator.py` : submit distinct `analyze_bat` (aucun enregistrement),
  contrôles taille/extension, messages utilisateur, contexte `bat` + JSON échappés,
  champs job rejoués après analyse (`keep_post`).
- `templates/ink_calculator.html` : bloc upload + bouton « 🔍 Analyser la BAT »,
  aperçu BAT / tableau détecté côte à côte, avertissements, lignes pré-remplies via
  JSON (`bat-rows`, `bat-hints`, `bat-keep`), pastille colorée par ligne, champ
  « Poses coupe » ajouté au bloc job.
- `core/tests/test_bat_extractor.py` : 7 tests (image synthétique 4 pastilles nommées,
  PDF texte lignes+hints, texte non appairé, hints, corrompu, vide, taille max).
- `scripts/verify_bat_autofill.py` : contrôle post-installation par marqueurs.
- `requirements.txt` : ajout `pypdf==6.20.1` (pur Python, aucune installation système).

### Inchangé (vérifié)
- Moteur de calcul : `density_default`, `validate_coverage`, création job + couleurs,
  écran détail, saisie des consommations réelles.
- Modèles `AniloxRoll`, `InkCalculationJob`, `InkCalculationColor` : **zéro migration**.
- Permissions : même garde `allowed()` (superuser ou module `prepress`).
- `core/forms/encre.py` (ConsommationEncre legacy) non touché.

### Limites documentées
- Scan/image : valeurs chiffrées non lues (pas d'OCR, choix « zéro installation »).
- Noms Pantone approchés sur photo ; noirs voisins possibles doublons `NOIR` ;
  ligne parasite logo possible ; blanc sur blanc non détectable → validation humaine.
