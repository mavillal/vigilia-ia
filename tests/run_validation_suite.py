#!/usr/bin/env python3
"""
tests/run_validation_suite.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Orquesta las 3 pruebas de la Validación de Funcionamiento (Tabla 4,
Informe de Desarrollo de Producto) y consolida un único
validation_report.json con el resultado de cada una.

  Prueba 1 · Inferencia de Modelos (YOLOv8s)   -> requiere --model
  Prueba 2 · Gestión de Alertas                -> automática, sin dependencias
  Prueba 3 · Interfaz de Operador              -> smoke test automático +
                                                    checklist manual (fuera
                                                    del alcance de este script)

Uso:
  python tests/run_validation_suite.py --model ./runs/train/vigilia_yolov8s/weights/best.pt
  python tests/run_validation_suite.py --skip_inferencia   # solo pruebas 2 y 3
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("run_validation_suite")

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"


def parse_args():
    p = argparse.ArgumentParser(description="Suite de Validación de Funcionamiento VIGIL-IA")
    p.add_argument("--model", default=None, help="Checkpoint para la Prueba 1 (best.pt/best.engine)")
    p.add_argument("--skip_inferencia", action="store_true", help="Omitir la Prueba 1 (requiere modelo entrenado)")
    p.add_argument("--report", default=str(TESTS_DIR / "validation_report.json"))
    return p.parse_args()


def run_script(name: str, cmd: list) -> tuple:
    log.info(f"--- {name} ---")
    result = subprocess.run(cmd)
    return name, result.returncode == 0


def main():
    args = parse_args()
    resultados = []

    if args.skip_inferencia or not args.model:
        log.info("Prueba 1 (Inferencia de Modelos) omitida: requiere --model con un checkpoint real.")
        resultados.append(("Inferencia de Modelos (YOLOv8s)", None))
    else:
        _, ok = run_script(
            "Prueba 1: Inferencia de Modelos",
            [sys.executable, str(TESTS_DIR / "test_01_inferencia_modelos.py"), "--model", args.model],
        )
        resultados.append(("Inferencia de Modelos (YOLOv8s)", ok))

    _, ok = run_script(
        "Prueba 2: Gestión de Alertas",
        [sys.executable, str(TESTS_DIR / "test_02_gestion_alertas.py")],
    )
    resultados.append(("Gestión de Alertas (Lógica de Negocio)", ok))

    _, ok = run_script(
        "Prueba 3: Interfaz de Operador (chequeo técnico)",
        [sys.executable, str(TESTS_DIR / "test_03_smoke_test.py")],
    )
    resultados.append(("Interfaz de Operador — condiciones técnicas", ok))
    log.info("Recordatorio: completar además tests/test_03_interfaz_operador_checklist.md (evaluación humana).")

    report = {
        "suite": "Validación de Funcionamiento — VIGIL-IA 25INI-282394",
        "resultados": [
            {"prueba": nombre, "resultado": ("Cumplido" if ok else "No cumplido") if ok is not None else "Omitido"}
            for nombre, ok in resultados
        ],
    }
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False))

    log.info("=== Resumen — Validación de Funcionamiento ===")
    for nombre, ok in resultados:
        estado = "Omitido" if ok is None else ("Cumplido" if ok else "NO CUMPLIDO")
        log.info(f"  {nombre}: {estado}")

    if any(ok is False for _, ok in resultados):
        log.error("Al menos una prueba automatizada no se cumplió.")
        sys.exit(1)

    log.info(f"Reporte consolidado en {args.report}")


if __name__ == "__main__":
    main()
