#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
WIDGET = ROOT / "assets" / "msc-assistant-widget.js"

SECONDARY_PAGES = [
    "servicios.html",
    "hoteles.html",
    "vuelos.html",
    "cruceros.html",
    "seguros-viaje.html",
    "paquetes.html",
    "ofertas.html",
    "msc-opera.html",
    "politica-privacidad.html",
    "terminos-condiciones.html",
    "cambios-cancelaciones-reembolsos.html",
]

REQUIRED_FLOW_MARKERS = [
    "const addMainMenu=",
    "const returnToMainMenu=",
    "const addFlowChoices=",
    "const addSearchExit=",
    "b.dataset.action='main-menu'",
    "addMainMenu();",
    "addSearchExit();",
    "← Menú principal",
]

def assert_contains(text: str, marker: str, source: str) -> None:
    if marker not in text:
        raise AssertionError(f"{source}: falta marcador de flujo: {marker}")

def node_check(path: Path) -> None:
    result = subprocess.run(
        ["node", "--check", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"JavaScript inválido en {path.name}:\n{result.stdout}\n{result.stderr}"
        )

def check_inline_scripts(html: str) -> None:
    scripts = re.findall(r"<script([^>]*)>([\s\S]*?)</script>", html, flags=re.I)
    checked = 0
    for attrs, code in scripts:
        if re.search(r"\bsrc\s*=", attrs, flags=re.I):
            continue
        if re.search(r"application/ld\+json", attrs, flags=re.I):
            continue
        if not code.strip():
            continue
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", encoding="utf-8", delete=False
        ) as tmp:
            tmp.write(code)
            tmp_path = Path(tmp.name)
        try:
            node_check(tmp_path)
            checked += 1
        finally:
            tmp_path.unlink(missing_ok=True)
    if checked == 0:
        raise AssertionError("index.html: no se encontró JavaScript inline para validar")

def main() -> int:
    index = INDEX.read_text(encoding="utf-8")
    widget = WIDGET.read_text(encoding="utf-8")

    for marker in REQUIRED_FLOW_MARKERS:
        assert_contains(index, marker, "index.html")
        assert_contains(widget, marker, "assets/msc-assistant-widget.js")

    for source, text in [
        ("index.html", index),
        ("assets/msc-assistant-widget.js", widget),
    ]:
        if text.count("const addMainMenu=") != 1:
            raise AssertionError(f"{source}: addMainMenu debe existir exactamente una vez")
        if "if(r.kind==='departures')" not in text or "addSearchExit();return;" not in text:
            raise AssertionError(f"{source}: las búsquedas deben ofrecer volver al menú")
        if "add(r.text);" not in text or "addMainMenu();" not in text:
            raise AssertionError(f"{source}: las respuestas informativas deben volver a mostrar opciones")
        if "addFlowChoices(regions" not in text:
            raise AssertionError(f"{source}: el flujo por zonas debe permitir salir al menú")

    node_check(WIDGET)
    check_inline_scripts(index)

    expected = "assets/msc-assistant-widget.js?v=20261008d"
    for rel in SECONDARY_PAGES:
        page = (ROOT / rel).read_text(encoding="utf-8")
        if expected not in page:
            raise AssertionError(f"{rel}: no usa la versión actual del widget MSC")

    print("FLUJO UI MSC: OK · información con menú recurrente · búsquedas con continuidad")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
