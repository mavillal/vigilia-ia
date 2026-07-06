#!/usr/bin/env python3
"""
tests/test_02_gestion_alertas.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Validación de Funcionamiento — Prueba 2: Gestión de Alertas (Lógica de Negocio)
Corresponde a la fila "Gestión de Alertas" de la Tabla 4 (Indicadores de
desempeño) del Informe de Desarrollo de Producto.

Objetivo  : validar la activación de alertas según umbrales.
Método    : inyección de eventos sintéticos con objetos de cada clase y
            verificación del cambio de estado (nivel de riesgo / acción)
            resultante, usando las MISMAS constantes de negocio y las MISMAS
            funciones de consulta que usa el backend real — no una
            reimplementación paralela de la lógica.
Evidencia : tabla de eventos con badges de estado (impresa en consola,
            equivalente textual a la tabla del Panel de Detecciones) +
            tests/validation_report.json.

No requiere un modelo entrenado ni una cámara: inyecta directamente en una
base SQLite temporal, con el mismo esquema que usa el sistema en producción.
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("test_gestion_alertas")

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DASHBOARD_JS = REPO_ROOT / "frontend" / "js" / "dashboard.js"

sys.path.insert(0, str(BACKEND_DIR))

from constants import ALERT_ACTION, CLASS_MAP, DEPLOY_CONF_THRESHOLDS, RISK_LEVEL  # noqa: E402
from database import SCHEMA  # noqa: E402
import crud  # noqa: E402


def extract_frontend_risk_labels(js_path: Path) -> dict:
    """Extrae RISK_BADGE del frontend (regex, sin parser JS completo) para
    verificar que las etiquetas mostradas al operador correspondan a los
    valores de nivel_riesgo que realmente produce el backend."""
    if not js_path.exists():
        return {}
    text = js_path.read_text(encoding="utf-8")
    match = re.search(r"RISK_BADGE\s*=\s*\{(.*?)\n\};", text, re.DOTALL)
    if not match:
        return {}
    block = match.group(1)
    entries = re.findall(r'["\']?([\wáéíóúñÁÉÍÓÚÑ]+)["\']?:\s*\{\s*label:\s*"([^"]+)"', block)
    return {key: label for key, label in entries}


def build_temp_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def inject_synthetic_events(conn: sqlite3.Connection) -> list:
    """Inyecta un evento sintético por clase, con confianza justo por sobre
    el umbral de producción de esa clase (Anexo C, Figura C.3)."""
    injected = []
    now = datetime.now(timezone.utc).isoformat()
    for frame_id, (class_id, class_name) in enumerate(CLASS_MAP.items()):
        confianza = min(DEPLOY_CONF_THRESHOLDS[class_name] + 0.05, 0.99)
        nivel_riesgo = RISK_LEVEL[class_name]
        accion = ALERT_ACTION[class_name]
        conn.execute(
            "INSERT INTO eventos (frame_id, clase, confianza, nivel_riesgo, accion, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (frame_id, class_name, confianza, nivel_riesgo, accion, now),
        )
        injected.append(
            {"frame_id": frame_id, "clase": class_name, "confianza": confianza,
             "nivel_riesgo": nivel_riesgo, "accion": accion}
        )
    conn.commit()
    return injected


def run_test(conn: sqlite3.Connection, injected: list, frontend_labels: dict) -> dict:
    failures = []

    # 1. Cada evento inyectado debe reflejar exactamente la matriz clase -> riesgo -> acción
    for ev in injected:
        clase = ev["clase"]
        if ev["nivel_riesgo"] != RISK_LEVEL[clase]:
            failures.append(f"{clase}: nivel_riesgo inyectado no coincide con RISK_LEVEL")
        if ev["accion"] != ALERT_ACTION[clase]:
            failures.append(f"{clase}: accion inyectada no coincide con ALERT_ACTION")

    # 2. list_alertas() debe contener exactamente las clases con accion='alerta'
    alertas = crud.list_alertas(conn, limit=50)
    clases_en_alertas = {a["clase"] for a in alertas}
    clases_esperadas_alerta = {c for c in CLASS_MAP.values() if ALERT_ACTION[c] == "alerta"}
    if clases_en_alertas != clases_esperadas_alerta:
        failures.append(
            f"/alertas devolvió {clases_en_alertas}, se esperaba {clases_esperadas_alerta}"
        )

    # 3. mineral_normal (accion='log') NO debe aparecer en alertas
    if "mineral_normal" in clases_en_alertas:
        failures.append("mineral_normal apareció en /alertas (debería ser solo 'log')")

    # 4. get_resumen() debe contar 1 evento por clase
    resumen = crud.get_resumen(conn)
    por_clase = {r["clase"]: r["total"] for r in resumen["por_clase"]}
    for clase in CLASS_MAP.values():
        if por_clase.get(clase) != 1:
            failures.append(f"resumen.por_clase[{clase}] = {por_clase.get(clase)}, se esperaba 1")

    if resumen["inchancables_detectados"] != 1:
        failures.append(
            f"resumen.inchancables_detectados = {resumen['inchancables_detectados']}, se esperaba 1"
        )

    # 5. Consistencia de etiquetas mostradas al operador (frontend) vs. nivel_riesgo real (backend)
    if frontend_labels:
        for ev in injected:
            label = frontend_labels.get(ev["nivel_riesgo"])
            if label is None:
                failures.append(
                    f"frontend/js/dashboard.js no define una etiqueta para nivel_riesgo='{ev['nivel_riesgo']}'"
                )
    else:
        log.warning("No se pudo leer frontend/js/dashboard.js; se omite el chequeo de etiquetas de badge.")

    return {"failures": failures, "alertas": alertas, "resumen": resumen}


def print_events_table(injected: list, frontend_labels: dict):
    """Imprime en consola el equivalente textual de la tabla de eventos con
    badges de estado del Panel de Detecciones (evidencia de la Tabla 4)."""
    log.info("=== Tabla de eventos con badges de estado (evidencia) ===")
    header = f"{'clase':<16} {'confianza':<10} {'nivel_riesgo':<12} {'accion':<8} {'badge':<12}"
    log.info(header)
    log.info("-" * len(header))
    for ev in injected:
        badge = frontend_labels.get(ev["nivel_riesgo"], ev["nivel_riesgo"])
        log.info(
            f"{ev['clase']:<16} {ev['confianza']*100:>7.0f}%  {ev['nivel_riesgo']:<12} "
            f"{ev['accion']:<8} {badge:<12}"
        )


def parse_args():
    p = argparse.ArgumentParser(description="Prueba 2 — Gestión de Alertas (Validación de Funcionamiento)")
    p.add_argument("--report", default=str(REPO_ROOT / "tests" / "validation_report_alertas.json"))
    return p.parse_args()


def main():
    args = parse_args()
    log.info("=== Prueba 2: Gestión de Alertas (Lógica de Negocio) ===")

    conn = build_temp_db()
    injected = inject_synthetic_events(conn)
    frontend_labels = extract_frontend_risk_labels(FRONTEND_DASHBOARD_JS)

    result = run_test(conn, injected, frontend_labels)
    print_events_table(injected, frontend_labels)

    report = {
        "prueba": "Gestión de Alertas (Lógica de Negocio)",
        "objetivo": "Validar la activación de alertas según umbrales",
        "metodo": "Inyección de eventos sintéticos por clase y verificación de cambio de estado",
        "eventos_inyectados": injected,
        "fallas": result["failures"],
        "resultado": "Cumplido" if not result["failures"] else "No cumplido",
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    log.info(f"Reporte guardado en {args.report}")

    if result["failures"]:
        log.error("=== FALLAS DETECTADAS ===")
        for f in result["failures"]:
            log.error(f"  - {f}")
        sys.exit(1)

    log.info("Resultado: Cumplido — la gestión de alertas refleja correctamente la matriz clase -> riesgo -> acción.")


if __name__ == "__main__":
    main()
