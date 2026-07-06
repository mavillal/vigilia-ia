#!/usr/bin/env python3
"""
tests/test_01_inferencia_modelos.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Validación de Funcionamiento — Prueba 1: Inferencia de Modelos (YOLOv8s)
Corresponde a la fila "Inferencia de Modelos (YOLOv8s)" de la Tabla 4
(Indicadores de desempeño) del Informe de Desarrollo de Producto.

Objetivo  : validar la capacidad de detección local bajo el umbral de FPS
            requerido en producción.
Método    : ejecución del modelo entrenado sobre hardware NVIDIA Jetson Orin
            con flujo RTSP.
Evidencia : logs de consola y model_card.json (generados por
            scripts/02_evaluate.py y scripts/03_export.py).

Este script NO reimplementa el benchmark de FPS: lo reutiliza directamente
desde scripts/02_evaluate.py --strict, que ya es la fuente única de verdad
para el umbral de ≥25 FPS (ver Anexo D). Aquí solo se orquesta su ejecución
en el contexto del protocolo de Validación de Funcionamiento y se traduce
su resultado al formato de reporte de esta carpeta.
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("test_inferencia_modelos")

REPO_ROOT = Path(__file__).resolve().parent.parent
EVALUATE_SCRIPT = REPO_ROOT / "scripts" / "02_evaluate.py"


def parse_args():
    p = argparse.ArgumentParser(description="Prueba 1 — Inferencia de Modelos (Validación de Funcionamiento)")
    p.add_argument("--model", required=True, help="Ruta a best.pt o best.engine ya entrenado/exportado")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--device", default="0")
    p.add_argument("--report", default=str(REPO_ROOT / "tests" / "validation_report_inferencia.json"))
    return p.parse_args()


def main():
    args = parse_args()
    log.info("=== Prueba 1: Inferencia de Modelos (YOLOv8s) ===")

    if not Path(args.model).exists():
        log.error(f"No se encontró el modelo: {args.model}")
        log.error("Esta prueba requiere un checkpoint real (best.pt/best.engine); no se simula.")
        sys.exit(1)

    eval_dir = REPO_ROOT / "runs" / "eval"
    cmd = [
        sys.executable, str(EVALUATE_SCRIPT),
        "--model", args.model,
        "--imgsz", str(args.imgsz),
        "--device", args.device,
        "--output", str(eval_dir),
        "--strict",
    ]
    log.info("Delegando el benchmark de FPS a 02_evaluate.py --strict (fuente única de verdad):")
    log.info("  " + " ".join(cmd))

    result = subprocess.run(cmd)
    eval_report_path = eval_dir / "eval_report.json"

    eval_report = None
    if eval_report_path.exists():
        eval_report = json.loads(eval_report_path.read_text())

    report = {
        "prueba": "Inferencia de Modelos (YOLOv8s)",
        "objetivo": "Validar la capacidad de detección local bajo el umbral de FPS de producción",
        "metodo": "Ejecución de 02_evaluate.py --strict sobre el checkpoint provisto",
        "eval_report": eval_report,
        "codigo_salida_evaluate": result.returncode,
        "resultado": "Cumplido" if result.returncode == 0 else "No cumplido",
    }
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    log.info(f"Reporte guardado en {args.report}")

    if result.returncode != 0:
        log.error("Resultado: No cumplido — ver la salida de 02_evaluate.py arriba para el detalle del umbral que falló.")
        sys.exit(result.returncode)

    log.info("Resultado: Cumplido.")


if __name__ == "__main__":
    main()
