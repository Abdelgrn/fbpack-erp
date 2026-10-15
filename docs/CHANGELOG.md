# CHANGELOG cumulatif — FB Pack ERP / Prépresse

## V4.1 — Correctif géométrie bobine (13/10/2026, même lot)
- Rouleau centré, longueur du cylindre == largeur du web (laize cohérente avec le bandeau).
- Caps identiques aux deux extrémités ; ombre symétrique.
- Web en S symétrique à traverses horizontales partagées : étiquettes continues, non coupées.
- Poses en laize répétées selon `nb_poses_laize` (1 à 3) sur le web et le rouleau.
- Fin de web sur répétitions entières (3 à 6).

## V4 — Lot Design Bobine (13/10/2026)
- Ajout : moteur serveur de composition « bobine d'impression » (rouleau + web en S,
  homographies par segment, masque ruban supersamplé) dans
  `core/services/prepress_technical_sheet.py` (`compose_roll_image`,
  `build_roll_visual_data_uri`), orienté par `sens_bobine` 1→8 (5→8 = web miroir).
- Ajout : contexte `roll_visual_data_uri`, `sens_rotation_deg`, `spot_css`.
- Ajout : asset `core/static/logo_blanc.png` (glyphe doré sur fond transparent) ;
  `_logo_data_uri()` le sert en priorité avec repli `logo.png`.
- Modification : canevas `_technical_sheet_canvas.html` — bobine à la place du visuel plat
  (repli plat puis placeholder conservés), logo sans rectangle navy, mise en page table
  compatible WeasyPrint, pied de page absolu ancré page conservé.
- Modification : secours ReportLab — bobine prioritaire, logo sans rectangle navy.
- Tests : suite Prépresse 7 → 9 tests (`test_roll_visual_composed_from_product_visual`,
  `test_roll_visual_graceful_without_maquette`).
- Vérificateur `scripts/verify_prepress_0048.py` : marqueurs V4 ajoutés
  (`ft-roll-visual`, `ft-logo-plain`, `logo_blanc.png`, `compose_roll_image`, `SENS_ROTATION`).
- Sans nouvelle route, sans nouvelle migration, sans nouvelle dépendance.

## V3 — Intégration Assistant Fiches techniques
- Assistant FB PACK : demande directe de fiche technique (recherche ref/name/client/ref_graveur,
  présélection 40 candidats pondérés, ambiguïté ≤ 6 choix, contexte « ce produit »),
  contrôle `_allowed(user, 'prepress')` avant toute requête, liens via `reverse()`.
- Interfaces `assistant_home.html` et `_widget.html` enrichies (target=_blank PDF/impression).
- 5 tests Assistant.

## V2 — Design Métier de la fiche
- Canevas industriel partagé consultation/impression/PDF : fond clair, titre encadré rouge,
  cartouche FLEXO/HELIO, valeurs bleues italiques, métriques fond rose, tableau 8 couleurs,
  pictogrammes sens/spot, placeholder maquette, pied de page absolu, `.ft-box` flex.
- Exemples validés `docs/EXEMPLE_FICHE_TECHNIQUE_0048.pdf/.png`.

## V1 — Lot 0048 Fiches techniques Prépresse
- Modèles TechnicalProduct/PrepressColor étendus, TechnicalProductRevision créé ;
  migration `0048_prepress_technical_sheet_erp` (dépend de 0047_security_connection_monitoring).
- Formulaire ERP complet, calculs serveur autoritaires (développement, laize gravure),
  sauvegarde atomique + révision JSON, liste filtrable, consultation, impression A4 paysage,
  PDF WeasyPrint + secours ReportLab (`Cache-Control: no-store, private`),
  images ≤ 10 Mo PNG/JPEG/WEBP, permissions serveur `module_required('prepress')`.
- 7 tests Prépresse.
