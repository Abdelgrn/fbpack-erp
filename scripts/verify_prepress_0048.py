#!/usr/bin/env python3
"""Vérification statique non destructive du lot Prépresse 0048."""

import argparse
import ast
import sys
from pathlib import Path


REQUIRED_FILES = [
    'core/models/prepress.py',
    'core/models/__init__.py',
    'core/forms/prepress.py',
    'core/views/prepress.py',
    'core/services/prepress_technical_sheet.py',
    'core/migrations/0048_prepress_technical_sheet_erp.py',
    'core/urls.py',
    'core/static/logo.png',
    'core/test_prepress_technical_sheet.py',
    'templates/prepress.html',
    'templates/prepress/_technical_sheet_canvas.html',
    'templates/prepress/technical_sheet_form.html',
    'templates/prepress/technical_sheet_list.html',
    'templates/prepress/technical_sheet_detail.html',
    'templates/prepress/technical_sheet_print.html',
    'templates/prepress/technical_sheet_revisions.html',
    'requirements.txt',
]

CRITICAL_URL_TOKENS = [
    "name='global_search_api'",
    "name='of_stock_reservations'",
    "name='notification_center'",
    "name='assistant_home'",
    "name='of_prelaunch_verification'",
    "name='ink_calculator'",
    "name='maintenance_dashboard'",
    "name='kpi_dashboard'",
    "name='crm_view'",
    "name='admin_promote_superuser'",
    "name='security_monitoring'",
    "name='prepress_technical_sheet_list'",
    "name='prepress_technical_sheet'",
    "name='prepress_technical_sheet_print'",
    "name='prepress_technical_sheet_pdf'",
    "name='prepress_technical_sheet_revisions'",
]


def fail(message, errors):
    errors.append(message)
    print(f'[ERREUR] {message}')


def ok(message):
    print(f'[OK] {message}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--project-root',
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help='Racine du projet Django ou du lot extrait.',
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    errors = []

    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            fail(f'Fichier manquant : {relative}', errors)
    if errors:
        return 1
    ok(f'{len(REQUIRED_FILES)} fichiers obligatoires présents')

    python_files = [root / relative for relative in REQUIRED_FILES if relative.endswith('.py')]
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            fail(f'Syntaxe Python invalide dans {path.relative_to(root)} : {exc}', errors)
    if not errors:
        ok('Syntaxe Python valide')

    urls = (root / 'core/urls.py').read_text(encoding='utf-8')
    missing_routes = [token for token in CRITICAL_URL_TOKENS if token not in urls]
    if missing_routes:
        fail('Routes cumulatives absentes : ' + ', '.join(missing_routes), errors)
    else:
        ok('Routes cumulatives historiques et nouvelles présentes')

    migration = (root / 'core/migrations/0048_prepress_technical_sheet_erp.py').read_text(encoding='utf-8')
    if "('core', '0047_security_connection_monitoring')" not in migration:
        fail('La migration 0048 ne dépend pas exactement de 0047_security_connection_monitoring', errors)
    else:
        ok('Dépendance de migration 0048 → 0047 correcte')

    models = (root / 'core/models/prepress.py').read_text(encoding='utf-8')
    for token in ('class TechnicalProductRevision', 'product_visual', 'couleur_hex', 'last_modified_by'):
        if token not in models:
            fail(f'Élément modèle absent : {token}', errors)

    views = (root / 'core/views/prepress.py').read_text(encoding='utf-8')
    for token in ("@module_required('prepress')", 'transaction.atomic()', 'create_product_revision', 'generate_reportlab_pdf'):
        if token not in views:
            fail(f'Contrôle requis absent des vues : {token}', errors)
    if not any(message.startswith('Contrôle requis') for message in errors):
        ok('Permissions serveur, transactions et double moteur PDF détectés')

    form_template = (root / 'templates/prepress/technical_sheet_form.html').read_text(encoding='utf-8')
    canvas_template = (root / 'templates/prepress/_technical_sheet_canvas.html').read_text(encoding='utf-8')
    for token in ('roll-picto', 'spot-picto', 'Sens de défilement'):
        if token not in form_template:
            fail(f'Sélecteur graphique absent : {token}', errors)
    for token in ('ft-title', 'ft-product-image', 'ft-colors', 'ft-metric'):
        if token not in canvas_template:
            fail(f'Élément de fiche métier absent : {token}', errors)
    if not any(message.startswith(('Sélecteur graphique', 'Élément de fiche métier')) for message in errors):
        ok('Sélecteurs graphiques et fiche métier visuelle détectés')

    logo = (root / 'core/static/logo.png').read_bytes()
    if not logo.startswith(b'\x89PNG\r\n\x1a\n'):
        fail('core/static/logo.png n’est pas un PNG valide', errors)
    else:
        ok('Logo PNG valide')

    requirements = (root / 'requirements.txt').read_text(encoding='utf-8').lower()
    for dependency in ('django==4.2.29', 'pillow==', 'weasyprint==', 'reportlab=='):
        if dependency not in requirements:
            fail(f'Dépendance absente de requirements.txt : {dependency}', errors)
    if not any(message.startswith('Dépendance absente') for message in errors):
        ok('Dépendances Django, image et PDF présentes')

    for relative in REQUIRED_FILES:
        if relative.endswith('.html'):
            text = (root / relative).read_text(encoding='utf-8')
            if text.count('{%') != text.count('%}') or text.count('{{') != text.count('}}'):
                fail(f'Balises Django déséquilibrées : {relative}', errors)
    if not any(message.startswith('Balises Django') for message in errors):
        ok('Délimiteurs des templates Django équilibrés')

    if errors:
        print(f'\nÉCHEC : {len(errors)} anomalie(s).')
        return 1
    print('\nSUCCÈS : contrôle statique du lot 0048 terminé sans anomalie.')
    print('Contrôles dynamiques conseillés : python manage.py check && python manage.py test core.test_prepress_technical_sheet')
    return 0


if __name__ == '__main__':
    sys.exit(main())
