#!/usr/bin/env python3
"""
integration/run_integration_check.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Verifica que los tres componentes (motor de inferencia, backend, frontend)
estén correctamente integrados:

  1. Consistencia de constantes de negocio (clases, umbrales, matriz de
     riesgo/acción) entre scripts/04_deploy_inference.py y
     backend/constants.py — deben ser idénticas, o el sistema podría
     aplicar umbrales distintos al detectar (edge) y al mostrar (dashboard).
  2. Esquema de la base de datos SQLite compartida.
  3. Disponibilidad del backend (endpoint /health).
  4. Presencia de los archivos estáticos del frontend.

No requiere que el motor de inferencia esté corriendo: se ejecuta como
chequeo previo/posterior al despliegue en terreno.

Uso:
  python integration/run_integration_check.py --db ../data/vigilia_events.db
"""

import argparse
import ast
import logging
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("integration_check")

REPO_ROOT = Path(__file__).resolve().parent.parent
INFERENCE_SCRIPT = REPO_ROOT / "scripts" / "04_deploy_inference.py"
BACKEND_CONSTANTS = REPO_ROOT / "backend" / "constants.py"
FRONTEND_DIR = REPO_ROOT / "frontend"

CONSTANTS_TO_COMPARE = [
    "CLASS_MAP",
    "RISK_LEVEL",
    "ALERT_ACTION",
]

EXPECTED_EVENTOS_COLUMNS = {
    "id", "frame_id", "clase", "confianza", "nivel_riesgo",
    "accion", "timestamp", "bbox_cx", "bbox_cy", "bbox_w", "bbox_h",
}


def parse_args():
    p = argparse.ArgumentParser(description="Verificación de integración VIGIL-IA")
    p.add_argument("--db", default=str(REPO_ROOT / "data" / "vigilia_events.db"))
    p.add_argument("--backend_url", default="http://localhost:8000")
    p.add_argument("--skip_backend", action="store_true", help="Omitir el chequeo de disponibilidad del backend")
    return p.parse_args()


def extract_top_level_dicts(path: Path) -> dict:
    """Extrae los diccionarios de nivel superior de un archivo .py vía AST,
    sin ejecutar el código (seguro para constantes de configuración)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        result[target.id] = ast.literal_eval(node.value)
                    except (ValueError, SyntaxError):
                        continue
    return result


def check_constants_consistency() -> bool:
    log.info("=== 1. Consistencia de constantes de negocio ===")
    ok = True

    if not INFERENCE_SCRIPT.exists() or not BACKEND_CONSTANTS.exists():
        log.error("No se encontraron scripts/04_deploy_inference.py y/o backend/constants.py")
        return False

    inference_consts = extract_top_level_dicts(INFERENCE_SCRIPT)
    backend_consts = extract_top_level_dicts(BACKEND_CONSTANTS)

    # DEPLOY_CONF_THRESHOLDS (backend) vs DEFAULT_CONF_THRESHOLDS (inference):
    # nombres distintos por contexto (uno son defaults de CLI, el otro
    # metadatos de export/documentación), pero el valor debe coincidir.
    threshold_pairs = [
        ("DEFAULT_CONF_THRESHOLDS", "DEPLOY_CONF_THRESHOLDS"),
    ]

    for name in CONSTANTS_TO_COMPARE:
        a = inference_consts.get(name)
        b = backend_consts.get(name)
        if a is None or b is None:
            log.error(f"  {name}: no encontrado en uno de los dos archivos")
            ok = False
        elif a != b:
            log.error(f"  {name}: DIFIERE entre inferencia y backend -> {a} vs {b}")
            ok = False
        else:
            log.info(f"  {name}: OK (idéntico en ambos archivos)")

    for inf_name, bk_name in threshold_pairs:
        a = inference_consts.get(inf_name)
        b = backend_consts.get(bk_name)
        if a is None or b is None:
            log.error(f"  {inf_name}/{bk_name}: no encontrado en uno de los dos archivos")
            ok = False
        elif a != b:
            log.error(f"  {inf_name} (inferencia) != {bk_name} (backend) -> {a} vs {b}")
            ok = False
        else:
            log.info(f"  {inf_name} == {bk_name}: OK (umbrales de confianza idénticos)")

    return ok


def check_database_schema(db_path: Path) -> bool:
    log.info("=== 2. Esquema de la base de datos compartida ===")
    if not db_path.exists():
        log.warning(f"  BD no encontrada en {db_path} (normal si el motor de inferencia aún no ha corrido)")
        return True

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute("PRAGMA table_info(eventos)")
        columns = {row[1] for row in cur.fetchall()}
    finally:
        conn.close()

    if not columns:
        log.error("  La tabla 'eventos' no existe en la BD")
        return False

    missing = EXPECTED_EVENTOS_COLUMNS - columns
    if missing:
        log.error(f"  Faltan columnas en 'eventos': {missing}")
        return False

    log.info(f"  Tabla 'eventos' OK ({len(columns)} columnas)")
    return True


def check_backend_health(url: str) -> bool:
    log.info("=== 3. Disponibilidad del backend ===")
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=3) as resp:
            if resp.status == 200:
                log.info(f"  Backend respondiendo en {url}/health")
                return True
            log.error(f"  Backend respondió con status {resp.status}")
            return False
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        log.warning(f"  Backend no disponible en {url} ({e}). ¿Está corriendo? (uvicorn / docker compose up)")
        return False


def check_frontend_files() -> bool:
    log.info("=== 4. Archivos del frontend ===")
    required = ["index.html", "dashboard.html", "js/api.js", "css/tokens.css"]
    ok = True
    for rel in required:
        path = FRONTEND_DIR / rel
        if path.exists():
            log.info(f"  {rel}: OK")
        else:
            log.error(f"  {rel}: FALTANTE")
            ok = False
    return ok


def main():
    args = parse_args()
    results = {
        "constantes": check_constants_consistency(),
        "esquema_bd": check_database_schema(Path(args.db)),
        "frontend": check_frontend_files(),
    }
    if not args.skip_backend:
        results["backend"] = check_backend_health(args.backend_url)

    log.info("=== Resumen ===")
    for name, ok in results.items():
        log.info(f"  {name}: {'OK' if ok else 'FALLÓ'}")

    if not all(results.values()):
        log.error("Integración incompleta: revisar los ítems marcados como FALLÓ arriba.")
        sys.exit(1)

    log.info("Integración de componentes verificada correctamente.")


if __name__ == "__main__":
    main()
