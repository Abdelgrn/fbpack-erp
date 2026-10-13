#!/usr/bin/env python3
"""Vérification statique ciblée de l’intégration Assistant Fiches V3."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str, errors: list[str]) -> None:
    print(f"[ERREUR] {message}")
    errors.append(message)


def require_markers(text: str, markers: tuple[str, ...], label: str, errors: list[str]) -> None:
    missing = [marker for marker in markers if marker not in text]
    if missing:
        fail(f"{label} : marqueurs absents : {', '.join(missing)}", errors)
    else:
        ok(label)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Racine du projet Django mis à jour (défaut : dossier courant).",
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    errors: list[str] = []

    relative_files = (
        "core/views/erp_assistant.py",
        "core/test_erp_assistant_technical_sheet.py",
        "core/urls.py",
        "templates/assistant/assistant_home.html",
        "templates/assistant/_widget.html",
    )
    missing = [name for name in relative_files if not (root / name).is_file()]
    if missing:
        for name in missing:
            fail(f"Fichier absent : {name}", errors)
        return 1
    ok("Fichiers Assistant, tests et routes présents")

    for relative in ("core/views/erp_assistant.py", "core/test_erp_assistant_technical_sheet.py"):
        try:
            ast.parse((root / relative).read_text(encoding="utf-8"), filename=relative)
        except (OSError, SyntaxError, UnicodeError) as exc:
            fail(f"Syntaxe Python invalide dans {relative} : {exc}", errors)
    if not errors:
        ok("Syntaxe Python valide")

    view = (root / "core/views/erp_assistant.py").read_text(encoding="utf-8")
    require_markers(
        view,
        (
            "def _technical_sheet_intent",
            "def _technical_sheet_answer",
            "_allowed(user, 'prepress')",
            "Q(ref_internal__icontains=token)",
            "Q(name__icontains=token)",
            "Q(client__name__icontains=token)",
            "Q(ref_graveur__icontains=token)",
            "reverse('prepress_technical_sheet'",
            "reverse('prepress_technical_sheet_print'",
            "reverse('prepress_technical_sheet_pdf'",
            "reverse('prepress_technical_sheet_list'",
            "'target': '_blank'",
        ),
        "Recherche, permission Prépresse et actions directes détectées",
        errors,
    )
    require_markers(
        view,
        (
            "def _stock_answer",
            "def _calculator_answer",
            "def _of_answer",
            "def _tool_answer",
            "def _time_answer",
            "def _context_answer",
            "def assistant_home",
            "def assistant_ask",
            "def assistant_clear",
        ),
        "Fonctions Assistant cumulatives conservées",
        errors,
    )

    answer_start = view.find("def answer_question")
    sheet_branch = view.find("if _technical_sheet_intent(normalized):", answer_start)
    calculator_branch = view.find("if any(word in normalized for word in ('calcul'", answer_start)
    if answer_start < 0 or sheet_branch < 0 or calculator_branch < 0 or sheet_branch > calculator_branch:
        fail("La branche fiche technique n’est pas placée avant les intentions génériques", errors)
    else:
        ok("Priorité de l’intention fiche technique confirmée")

    urls = (root / "core/urls.py").read_text(encoding="utf-8")
    require_markers(
        urls,
        (
            "name='assistant_home'",
            "name='assistant_ask'",
            "name='assistant_clear'",
            "name='prepress_technical_sheet'",
            "name='prepress_technical_sheet_print'",
            "name='prepress_technical_sheet_pdf'",
            "name='prepress_technical_sheet_list'",
        ),
        "Routes Assistant et Prépresse requises présentes",
        errors,
    )

    for relative in ("templates/assistant/assistant_home.html", "templates/assistant/_widget.html"):
        text = (root / relative).read_text(encoding="utf-8")
        tag_pairs = len(re.findall(r"{%.*?%}", text, flags=re.S))
        variable_pairs = len(re.findall(r"{{.*?}}", text, flags=re.S))
        if text.count("{%") != tag_pairs or text.count("{{") != variable_pairs:
            fail(f"Délimiteurs Django déséquilibrés : {relative}", errors)
        if "anchor.target = link.target" not in text:
            fail(f"Gestion de target absente : {relative}", errors)
        if "fiche technique" not in text.lower():
            fail(f"Capacité fiche technique non annoncée : {relative}", errors)
    if not any("templates/assistant" in error for error in errors):
        ok("Templates Assistant équilibrés, enrichis et compatibles avec target")

    tests = (root / "core/test_erp_assistant_technical_sheet.py").read_text(encoding="utf-8")
    test_count = len(re.findall(r"^\s+def test_", tests, flags=re.M))
    if test_count != 5:
        fail(f"Nombre de tests Assistant inattendu : {test_count} au lieu de 5", errors)
    else:
        ok("Cinq tests Assistant ciblés présents")

    if errors:
        print(f"\nÉCHEC : {len(errors)} anomalie(s).")
        return 1
    print("\nSUCCÈS : intégration Assistant Fiches V3 statiquement conforme.")
    print("Contrôles dynamiques : python manage.py check && python manage.py test core.test_prepress_technical_sheet core.test_erp_assistant_technical_sheet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
