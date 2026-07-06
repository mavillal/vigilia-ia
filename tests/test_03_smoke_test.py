#!/usr/bin/env python3
"""
tests/test_03_smoke_test.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Chequeo técnico complementario a la Prueba 3 (Interfaz de Operador).

IMPORTANTE: este script NO mide interpretabilidad humana ni reemplaza el
protocolo manual de tests/test_03_interfaz_operador_checklist.md. Solo
verifica que las condiciones técnicas necesarias para ejecutar esa prueba
estén dadas: que los elementos críticos del dashboard existan en el HTML
(tarjetas KPI, banner de alerta crítica, tabla de eventos, badges de riesgo)
y que los archivos estáticos carguen sin error.

Uso:
  python tests/test_03_smoke_test.py
"""

import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("test_smoke")

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"

REQUIRED_ELEMENT_IDS = [
    "kpi-row",           # tarjetas KPI (indicadores superiores)
    "critical-banner",   # banner de alerta crítica
    "events-tbody",       # tabla de eventos
    "alerts-list",         # listado de alertas
]

REQUIRED_CSS_CLASSES = ["badge-sin", "badge-medio", "badge-alto"]


def check_dashboard_html() -> list:
    failures = []
    dashboard_html = FRONTEND_DIR / "dashboard.html"
    if not dashboard_html.exists():
        return ["frontend/dashboard.html no existe"]

    html = dashboard_html.read_text(encoding="utf-8")
    for element_id in REQUIRED_ELEMENT_IDS:
        if f'id="{element_id}"' not in html:
            failures.append(f"Falta el elemento id=\"{element_id}\" en dashboard.html")
    return failures


def check_badge_css_classes() -> list:
    failures = []
    styles_css = FRONTEND_DIR / "css" / "styles.css"
    if not styles_css.exists():
        return ["frontend/css/styles.css no existe"]

    css = styles_css.read_text(encoding="utf-8")
    for css_class in REQUIRED_CSS_CLASSES:
        if f".{css_class}" not in css:
            failures.append(f"Falta la clase CSS .{css_class} en styles.css")
    return failures


def check_scripts_referenced() -> list:
    failures = []
    dashboard_html = FRONTEND_DIR / "dashboard.html"
    if not dashboard_html.exists():
        return ["frontend/dashboard.html no existe"]

    html = dashboard_html.read_text(encoding="utf-8")
    for script in ["js/api.js", "js/dashboard.js"]:
        if script not in html:
            failures.append(f"dashboard.html no referencia {script}")
        if not (FRONTEND_DIR / script).exists():
            failures.append(f"{script} referenciado pero no existe en disco")
    return failures


def main():
    log.info("=== Chequeo técnico complementario — Prueba 3 (Interfaz de Operador) ===")
    log.info("Nota: esto NO evalúa interpretabilidad humana. Ver test_03_interfaz_operador_checklist.md")

    all_failures = []
    all_failures += check_dashboard_html()
    all_failures += check_badge_css_classes()
    all_failures += check_scripts_referenced()

    if all_failures:
        log.error("Condiciones técnicas incompletas para ejecutar la Prueba 3:")
        for f in all_failures:
            log.error(f"  - {f}")
        sys.exit(1)

    log.info("Condiciones técnicas OK: el dashboard está listo para la evaluación humana del checklist.")


if __name__ == "__main__":
    main()
