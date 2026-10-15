#!/usr/bin/env python3
"""Contrôle post-installation du LOT BAT AUTOFILL V1.15 (OCR local RapidOCR, sans API).

Usage : python scripts/verify_bat_autofill.py <racine_projet>
Vérifie par marqueurs que les 5 fichiers métier sont en place et cohérents.
"""
import sys
from pathlib import Path

MARKERS = [
    ('core/services/bat_extractor.py', [
        'def analyze_bat(', 'def _render_pdf_pages(', 'def _rows_from_ocr(', 'def _hints(',
        'MAX_BAT_BYTES', 'def validate_bat_size(', 'from . import bat_ocr', 'def _clean_job_name(']),
    ('core/services/bat_ocr.py', [
        'def analyze_pages(', 'def find_cartouche(', 'def parse_fields(', 'def ink_table(',
        'def build_rows(', 'def canon_ink_name(', 'def _engine(', 'from rapidocr_onnxruntime']),
    ('core/services/cliche_suppliers.py', [
        'def summarize(', 'def supplier_or_blank(', 'SUPPLIER_CHOICES']),
    ('core/services/ink_calculator.py', [
        'def density_default', 'return 1.5', 'return 1.3', 'calculated=100.0*']),
    ('core/views/ink_calculator.py', [
        "'analyze_bat' in request.POST", 'from ..services.bat_extractor import',
        'validate_coverage', 'density_default', 'def ink_calculation_actual(', 'width_mm/max(job.poses_across',
        'MAX_BAT_BYTES', '_redirect_detail', 'NoReverseMatch',
        'def ink_calculation_list(', '_url_or_empty']),
    ('templates/ink_calculator.html', [
        'enctype="multipart/form-data"', 'name="analyze_bat"', 'id="bat-rows"',
        'id="bat-hints"', 'id="bat-keep"', 'Calculer et enregistrer',
        'name="poses_repeat"', 'formnovalidate', 'DENSITY_DEFAULT', 'wireDensity',
        'id="f_poses_across" type="number" min="1" placeholder', 'history_url']),
    ('templates/ink_calculation_list.html', [
        'Historique des calculs', 'total_prepare_kg', 'detail_url',
        '{% for c in r.job.colors.all %}']),
    ('core/tests/test_bat_extractor.py', [
        'class AnalyzeContractTests', 'test_resultat_mocke_mappe_les_lignes']),
    ('core/tests/test_bat_ocr.py', [
        'class ParseFieldsTests', 'class InkTableTests', 'class BuildRowsTests']),
    ('requirements.txt', ['pypdfium2==']),
]


def main(root):
    ok = True
    for rel, markers in MARKERS:
        path = Path(root) / rel
        if not path.exists():
            # le template peut vivre dans un autre dossier templates
            alt = list(Path(root).rglob(Path(rel).name))
            if not alt:
                print(f'[ABSENT] {rel}')
                ok = False
                continue
            path = alt[0]
        txt = path.read_text(encoding='utf-8', errors='replace')
        missing = [m for m in markers if m not in txt]
        if missing:
            print(f'[MARQUEURS MANQUANTS] {path}: {missing}')
            ok = False
        else:
            print(f'[OK] {path} ({len(markers)} marqueurs)')
    print('VERIFICATION BAT AUTOFILL V1 :', 'OK' if ok else 'ECHEC')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else '.'))
