#!/usr/bin/env python3
"""
01_train.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Paso TRAIN del pipeline (Anexo D, Figura D.1).
Entrena YOLOv8s con los hiperparámetros del proyecto sobre el dataset
Copper Phoenix I (1.720 imágenes, 3 clases operacionales).

Input : vigilia_dataset.yaml
Output: best.pt + curvas de entrenamiento (results.png, results.csv)

Referencia de validación técnica (Anexo D — Curvas de Entrenamiento):
  - 150 épocas · mejor checkpoint históricamente en época ~134 (brecha train/val mínima)
  - Dataset híbrido: 1.200 sintéticas + 520 nativas
  - Clase crítica: metal_grande (menor representación nativa, 100 imgs)

Uso:
  python 01_train.py --data ./vigilia_dataset.yaml --model_size s --epochs 150
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("train")

CLASS_MAP = {0: "mineral_normal", 1: "roca_oversize", 2: "metal_grande"}


def parse_args():
    p = argparse.ArgumentParser(description="Entrenamiento YOLOv8 para VIGIL-IA")
    p.add_argument("--data", required=True, help="Ruta a vigilia_dataset.yaml")
    p.add_argument("--model_size", default="s", choices=["n", "s", "m", "l", "x"],
                   help="Tamaño del modelo YOLOv8 (default: s, usado en producción)")
    p.add_argument("--epochs", type=int, default=150, help="Épocas de entrenamiento (default: 150)")
    p.add_argument("--imgsz", type=int, default=640, help="Tamaño de imagen de entrenamiento")
    p.add_argument("--batch", type=int, default=16, help="Batch size")
    p.add_argument("--patience", type=int, default=30, help="Early stopping patience")
    p.add_argument("--device", default="0", help="Dispositivo CUDA ('0', 'cpu', etc.)")
    p.add_argument("--project", default="./runs/train", help="Directorio de salida de runs")
    p.add_argument("--name", default="vigilia_yolov8s", help="Nombre del run")
    p.add_argument("--resume", action="store_true", help="Reanudar desde el último checkpoint")
    p.add_argument("--pretrained", default=None,
                   help="Pesos preentrenados custom (default: yolov8{size}.pt de Ultralytics)")
    return p.parse_args()


def main():
    args = parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        log.error(f"No se encontró el archivo de dataset: {data_path}")
        sys.exit(1)

    try:
        from ultralytics import YOLO
    except ImportError:
        log.error("Falta la dependencia 'ultralytics'. Instalar con: pip install ultralytics")
        sys.exit(1)

    weights = args.pretrained or f"yolov8{args.model_size}.pt"
    log.info(f"Cargando modelo base: {weights}")
    model = YOLO(weights)

    log.info(
        f"Iniciando entrenamiento — épocas={args.epochs}, imgsz={args.imgsz}, "
        f"batch={args.batch}, device={args.device}, patience={args.patience}"
    )
    results = model.train(
        data=str(data_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        patience=args.patience,
        device=args.device,
        project=args.project,
        name=args.name,
        resume=args.resume,
        exist_ok=True,
    )

    run_dir = Path(model.trainer.save_dir)
    best_pt = run_dir / "weights" / "best.pt"
    last_pt = run_dir / "weights" / "last.pt"

    if not best_pt.exists():
        log.error("No se generó best.pt. Revisar logs de entrenamiento de Ultralytics.")
        sys.exit(1)

    log.info(f"Entrenamiento finalizado. Checkpoints en: {run_dir / 'weights'}")
    log.info(f"  best.pt -> {best_pt}")
    log.info(f"  last.pt -> {last_pt}")

    # Metadatos del run (sin inventar métricas: se toman directo del objeto results de Ultralytics)
    metadata = {
        "modelo_base": weights,
        "clases": CLASS_MAP,
        "epochs_solicitadas": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "run_dir": str(run_dir),
        "best_pt": str(best_pt),
        "results_csv": str(run_dir / "results.csv"),
        "results_png": str(run_dir / "results.png"),
    }
    meta_path = run_dir / "train_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    log.info(f"Metadatos de entrenamiento guardados en {meta_path}")


if __name__ == "__main__":
    main()
