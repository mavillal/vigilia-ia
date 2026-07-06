#!/usr/bin/env python3
"""
05_run_pipeline.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Paso ORQUESTADOR del pipeline (Anexo D, Figura D.1).
Ejecuta el pipeline completo end-to-end: data -> train -> eval -> export -> deploy,
encadenando 00_prepare_dataset.py, 01_train.py, 02_evaluate.py, 03_export.py y
04_deploy_inference.py.

Input : todos los parámetros (csv, imágenes, hiperparámetros, fuente RTSP)
Output: reporte final JSON + artefactos de cada etapa

Comando de referencia (Anexo D.2):
  python 05_run_pipeline.py \
    --csv ./data/vigilia_dataset_entrenamiento_completo.csv \
    --images ./data/raw_images \
    --model_size s \
    --epochs 150 \
    --source rtsp://192.168.1.100/stream1 \
    --skip_deploy
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("run_pipeline")

SCRIPT_DIR = Path(__file__).resolve().parent


def parse_args():
    p = argparse.ArgumentParser(description="Pipeline completo VIGIL-IA: data -> train -> eval -> export -> deploy")
    # Dataset
    p.add_argument("--csv", required=True, help="CSV maestro con anotaciones")
    p.add_argument("--images", required=True, help="Directorio con imágenes 4K crudas")
    p.add_argument("--data_output", default="./data", help="Directorio de salida de datos preparados")
    p.add_argument("--split", type=float, default=0.8)
    # Train
    p.add_argument("--model_size", default="s", choices=["n", "s", "m", "l", "x"])
    p.add_argument("--epochs", type=int, default=150)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--device", default="0")
    p.add_argument("--train_project", default="./runs/train")
    p.add_argument("--train_name", default="vigilia_yolov8s")
    # Eval
    p.add_argument("--strict_eval", action="store_true", help="Aplicar gate --strict en la evaluación")
    # Export
    p.add_argument("--export_dir", default="./runs/export")
    # Deploy
    p.add_argument("--source", default=None, help="Fuente RTSP para el deploy (cámara Axis P1448-LE)")
    p.add_argument("--gpio", action="store_true")
    p.add_argument("--skip_deploy", action="store_true", help="Omitir la etapa DEPLOY (recomendado fuera de Jetson Orin)")
    p.add_argument("--report_output", default="./runs/pipeline_report.json")
    return p.parse_args()


def run_step(name, cmd, allow_fail=False):
    log.info(f"=== Etapa {name} ===")
    log.info("Comando: " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    status = "ok" if result.returncode == 0 else "fallo"
    if result.returncode != 0 and not allow_fail:
        log.error(f"Etapa {name} falló (código {result.returncode}). Abortando pipeline.")
        sys.exit(result.returncode)
    elif result.returncode != 0:
        log.warning(f"Etapa {name} falló (código {result.returncode}), pero se continúa (allow_fail=True).")
    return {"etapa": name, "estado": status, "codigo_salida": result.returncode, "comando": cmd}


def main():
    args = parse_args()

    if not args.skip_deploy and not args.source:
        log.error("--source es requerido cuando no se usa --skip_deploy.")
        sys.exit(1)

    report = {
        "proyecto": "VIGIL-IA",
        "codigo_corfo": "25INI-282394",
        "inicio": datetime.now(timezone.utc).isoformat(),
        "etapas": [],
    }

    # 00 · DATA
    report["etapas"].append(run_step(
        "DATA",
        [sys.executable, str(SCRIPT_DIR / "00_prepare_dataset.py"),
         "--csv", args.csv, "--images", args.images,
         "--output", args.data_output, "--split", str(args.split)],
    ))

    dataset_yaml = str(Path(args.data_output) / "vigilia_dataset.yaml")

    # 01 · TRAIN
    report["etapas"].append(run_step(
        "TRAIN",
        [sys.executable, str(SCRIPT_DIR / "01_train.py"),
         "--data", dataset_yaml, "--model_size", args.model_size,
         "--epochs", str(args.epochs), "--imgsz", str(args.imgsz),
         "--batch", str(args.batch), "--device", args.device,
         "--project", args.train_project, "--name", args.train_name],
    ))

    best_pt = str(Path(args.train_project) / args.train_name / "weights" / "best.pt")

    # 02 · EVAL
    eval_cmd = [sys.executable, str(SCRIPT_DIR / "02_evaluate.py"),
                "--model", best_pt, "--imgsz", str(args.imgsz), "--device", args.device,
                "--output", str(Path(args.export_dir).parent / "eval")]
    if args.strict_eval:
        eval_cmd.append("--strict")
    report["etapas"].append(run_step("EVAL", eval_cmd))

    eval_report_path = str(Path(args.export_dir).parent / "eval" / "eval_report.json")

    # 03 · EXPORT
    report["etapas"].append(run_step(
        "EXPORT",
        [sys.executable, str(SCRIPT_DIR / "03_export.py"),
         "--model", best_pt, "--output_dir", args.export_dir,
         "--imgsz", str(args.imgsz), "--device", args.device,
         "--eval_report", eval_report_path],
    ))

    best_engine = str(Path(args.export_dir) / "best.engine")

    # 04 · DEPLOY
    if args.skip_deploy:
        log.info("=== Etapa DEPLOY === omitida (--skip_deploy)")
        report["etapas"].append({"etapa": "DEPLOY", "estado": "omitida", "codigo_salida": None, "comando": None})
    else:
        deploy_cmd = [sys.executable, str(SCRIPT_DIR / "04_deploy_inference.py"),
                      "--model", best_engine, "--source", args.source]
        if args.gpio:
            deploy_cmd.append("--gpio")
        report["etapas"].append(run_step("DEPLOY", deploy_cmd, allow_fail=True))

    report["fin"] = datetime.now(timezone.utc).isoformat()
    report["exitoso"] = all(e["estado"] in ("ok", "omitida") for e in report["etapas"])

    report_path = Path(args.report_output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    log.info(f"Reporte final del pipeline guardado en {report_path}")

    if not report["exitoso"]:
        log.error("El pipeline finalizó con al menos una etapa fallida.")
        sys.exit(1)

    log.info("Pipeline VIGIL-IA completo ejecutado exitosamente: data -> train -> eval -> export -> deploy.")


if __name__ == "__main__":
    main()
