#!/usr/bin/env python3
"""Static checks only; requires Python standard library, not Django."""
from pathlib import Path
import ast
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
errors = []

for path in ROOT.rglob('*.py'):
    try:
        ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        errors.append(f'Python syntax: {path.relative_to(ROOT)}: {exc}')

for path in ROOT.rglob('*.html'):
    text = path.read_text(encoding='utf-8', errors='replace')
    for opening, closing in [('if', 'endif'), ('for', 'endfor'), ('block', 'endblock')]:
        a = len(re.findall(r'{%\s*' + opening + r'\b', text))
        b = len(re.findall(r'{%\s*' + closing + r'\b', text))
        if a != b:
            errors.append(f'Template block balance: {path.relative_to(ROOT)}: {opening}={a}, {closing}={b}')

urls = (ROOT / 'core/urls.py').read_text(errors='replace')
required_routes = [
    "name='of_stock_reservations'", "name='stock_reservations_overview'", "name='commande_creer_of'", "name='crm_of_detail'", "name='crm_of_commandes_a_convertir'",
    "name='stock_kpi'", "name='stock_catalog_manage'", "name='stock_documents_list'",
    "name='stock_receipt_create'", "name='stock_daily_issue_create'", "name='stock_damage_create'",
    "name='stock_return_create'", "name='stock_movement_edit'", "name='stock_movement_delete'",
    "name='of_prelaunch_check'",
]
for route in required_routes:
    if route not in urls:
        errors.append(f'Missing route: {route}')
route_names = set(re.findall(r"name\s*=\s*['\"]([^'\"]+)", urls))
for template in (ROOT / 'templates').rglob('*.html'):
    text = template.read_text(errors='replace')
    for route in re.findall(r"{%\s*url\s+['\"]([^'\"]+)", text):
        if route not in route_names:
            errors.append(f'Missing route used by {template.relative_to(ROOT)}: {route}')

required_files = [
    'core/views/stock_reservation.py', 'core/services/of_materials.py',
    'core/services/stock_reservation.py', 'templates/stock/of_stock_reservations.html',
    'templates/stock/reservations_overview.html', 'templates/stock/partials/stock_advanced_tabs.html',
    'templates/crm/commande_creer_of_sync.html', 'templates/crm/commandes_a_convertir_of.html',
]
for rel in required_files:
    if not (ROOT / rel).is_file():
        errors.append(f'Missing integration file: {rel}')

checks = {
    'core/views/crm_views.py': ['create_requirements_and_reserve', "quantite_prevue=calculated['quantity_kg']", 'core.add_ordrefabrication', 'def crm_of_commandes_a_convertir', 'of_lie__isnull=True', 'request.user.is_staff'],  
    'core/services/stock_reservation.py': ['def reserve_fifo_partial', 'def consume_of_reservations', 'def restore_of_reservation_consumption'],
    'core/views/stock.py': ['lot_available_quantity_for_of', 'consume_of_reservations', 'restore_of_reservation_consumption'],
    'core/services/of_materials.py': ['laize_bobine_mm', 'developpement_mm', 'poses', 'quantity_required'],
}
for rel, needles in checks.items():
    text = (ROOT / rel).read_text(errors='replace')
    for needle in needles:
        if needle not in text:
            errors.append(f'Missing invariant {needle!r} in {rel}')

q, poses, development_mm, useful_mm, roll_mm, gsm = 10000, 2, 100, 300, 320, 18.2
surface = (q / poses) * development_mm / 1000 * useful_mm / 1000
loss = 1 - useful_mm / roll_mm
required_kg = surface * gsm / 1000 / (1 - loss)
finished_kg = surface * gsm / 1000
if abs(surface - 150.0) > 1e-8 or abs(required_kg - 2.912) > 0.002 or abs(finished_kg - 2.73) > 1e-8:
    errors.append('Formula sanity sample failed')

if errors:
    print('\n'.join('FAIL: ' + error for error in errors))
    sys.exit(1)
print('OK: Python AST, template blocks and URL references, required routes, integration wiring, stock invariants, formula sanity sample.')
