#!/usr/bin/env python3
"""
03_export.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Paso EXPORT del pipeline (Anexo D, Figura D.1).
Exporta el modelo entrenado a TensorRT FP16 (para inferencia en Jetson Orin)
y a ONNX (portabilidad/depuración), generando además un model_card.json con
la trazabilidad completa del modelo.

Input : best.pt
Output: best.engine + best.onnx + model_card.json

Uso:
  python 03_export.py --model ./runs/train/best.pt --output_dir ./runs/export
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("export")

CLASS_MAP = {0: "mineral_normal", 1: "roca_oversize", 2: "metal_grande"}

# Umbrales de confianza en producción por clase (Anexo C, Figura C.3)
DEPLOY_CONF_THRESHOLDS = {
    "mineral_normal": 0.50,
    "roca_oversize": 0.40,
    "metal_grande": 0.30,
}


def parse_args():
    p = argparse.ArgumentParser(description="Export de modelo VIGIL-IA a TensorRT FP16 + ONNX")
    p.add_argument("--model", required=True, help="Ruta a best.pt")
    p.add_argument("--output_dir", default="./runs/export", help="Directorio de salida")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--half", action="store_true", default=True, help="Exportar en FP16 (default: activado)")
    p.add_argument("--device", default="0", help="Dispositivo CUDA para export TensorRT")
    p.add_argument("--skip_onnx", action="store_true", help="Omitir export a ONNX")
    p.add_argument("--skip_engine", action="store_true", help="Omitir export a TensorRT (.engine)")
    p.add_argument("--eval_report", default=None,
                   help="Ruta a eval_report.json (de 02_evaluate.py) para incluir métricas reales en el model_card")
    return p.parse_args()


def main():
    args = parse_args()
    model_path = Path(args.model)
    if not model_path.exists():
        log.error(f"No se encontró el modelo: {model_path}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from ultralytics import YOLO
    except ImportError:
        log.error("Falta la dependencia 'ultralytics'. Instalar con: pip install ultralytics")
        sys.exit(1)

    log.info(f"Cargando modelo: {model_path}")
    model = YOLO(str(model_path))

    exported_paths = {}

    if not args.skip_onnx:
        log.info("Exportando a ONNX...")
        onnx_path = model.export(format="onnx", imgsz=args.imgsz, half=args.half)
        exported_paths["onnx"] = str(onnx_path)
        log.info(f"  -> {onnx_path}")

    if not args.skip_engine:
        log.info(f"Exportando a TensorRT (FP16={args.half}) — requiere entorno Jetson/CUDA con TensorRT...")
        try:
            engine_path = model.export(format="engine", imgsz=args.imgsz, half=args.half, device=args.device)
            exported_paths["engine"] = str(engine_path)
            log.info(f"  -> {engine_path}")
        except Exception as e:
            log.error(f"Fallo el export a TensorRT: {e}")
            log.error("Verificar que el export se ejecute en el hardware destino (Jetson Orin) con TensorRT instalado.")
            if args.skip_onnx:
                sys.exit(1)
            log.warning("Continuando solo con el artefacto ONNX generado.")

    # Métricas reales, solo si fueron provistas por 02_evaluate.py. No se inventan valores.
    metrics_section = None
    if args.eval_report and Path(args.eval_report).exists():
        eval_data = json.loads(Path(args.eval_report).read_text())
        metrics_section = {
            "global_map50": eval_data.get("global_map50"),
            "por_clase": eval_data.get("por_clase"),
            "fps_medido": eval_data.get("fps_medido"),
        }
    else:
        log.warning("No se proporcionó --eval_report: el model_card.json no incluirá métricas de validación.")

    model_card = {
        "proyecto": "VIGIL-IA",
        "codigo_corfo": "25INI-282394",
        "empresa": "VIGIL SpA",
        "modelo_base": "YOLOv8s",
        "fecha_export": datetime.now(timezone.utc).isoformat(),
        "clases": CLASS_MAP,
        "umbrales_confianza_produccion": DEPLOY_CONF_THRESHOLDS,
        "imgsz": args.imgsz,
        "precision": "FP16" if args.half else "FP32",
        "hardware_objetivo": "NVIDIA Jetson Orin",
        "camara": "Axis P1448-LE (3840x2160 px, RTSP)",
        "artefactos": exported_paths,
        "metricas_validacion": metrics_section,
        "sitio_piloto": "Copper Phoenix I — Barreal Seco, Taltal, Región de Antofagasta (1.030 m.s.n.m.)",
    }

    card_path = output_dir / "model_card.json"
    card_path.write_text(json.dumps(model_card, indent=2, ensure_ascii=False))
    log.info(f"model_card.json generado en {card_path}")
    log.info("Export finalizado.")


if __name__ == "__main__":
    main()
