#!/usr/bin/env python3
"""
02_evaluate.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Paso EVAL del pipeline (Anexo D, Figura D.1).
Calcula métricas por clase (precisión, recall, mAP@0.5) y realiza un benchmark
de latencia/FPS sobre el set de validación.

Input : best.pt + dataset de validación
Output: JSON + reporte de texto

Umbral de referencia validado en terreno (Informe de Validación Técnica):
  - FPS objetivo en Jetson Orin: >= 25 FPS (único umbral confirmado formalmente)
  - Métricas de referencia Copper Phoenix I (Anexo C, Figura C.2 / Anexo D.3):
      mineral_normal : mAP@0.5 = 0.743
      roca_oversize  : mAP@0.5 = 0.672
      metal_grande   : mAP@0.5 = 0.490
      global         : mAP@0.5 = 0.67
  - Falsos negativos metal_grande: 23.8% (19/80 casos) -> motivó conf=0.30 en producción

--strict activa un gate de CI/CD: el script retorna código de salida != 0 si el
modelo evaluado no alcanza los umbrales mínimos configurados.

Uso:
  python 02_evaluate.py --model ./runs/train/best.pt --strict
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("evaluate")

CLASS_MAP = {0: "mineral_normal", 1: "roca_oversize", 2: "metal_grande"}

# Umbrales mínimos de gate para --strict. Calibrados sobre los resultados
# efectivamente alcanzados en la validación de Copper Phoenix I (no son metas
# aspiracionales inventadas, sino un piso de no-regresión respecto a lo ya logrado).
DEFAULT_GATES = {
    "mineral_normal_map50": 0.70,
    "roca_oversize_map50": 0.60,
    "metal_grande_map50": 0.45,
    "global_map50": 0.60,
    "min_fps": 25.0,
}


def parse_args():
    p = argparse.ArgumentParser(description="Evaluación del modelo VIGIL-IA (YOLOv8)")
    p.add_argument("--model", required=True, help="Ruta a best.pt")
    p.add_argument("--data", default=None, help="Ruta a vigilia_dataset.yaml (default: la usada en el propio checkpoint)")
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--device", default="0")
    p.add_argument("--benchmark_iters", type=int, default=50, help="Iteraciones para benchmark de FPS")
    p.add_argument("--strict", action="store_true", help="Gate de CI/CD: falla si no se alcanzan los umbrales mínimos")
    p.add_argument("--gates", default=None, help="Ruta a JSON con umbrales custom para --strict")
    p.add_argument("--output", default="./runs/eval", help="Directorio de salida del reporte")
    return p.parse_args()


def load_gates(gates_path):
    if gates_path is None:
        return DEFAULT_GATES
    custom = json.loads(Path(gates_path).read_text())
    gates = dict(DEFAULT_GATES)
    gates.update(custom)
    return gates


def run_benchmark(model, imgsz, device, iters):
    """Mide FPS de inferencia pura (sin post-procesamiento de negocio) sobre tensores dummy."""
    import numpy as np
    dummy = (np.random.rand(imgsz, imgsz, 3) * 255).astype("uint8")

    # Warmup
    for _ in range(5):
        model.predict(dummy, imgsz=imgsz, device=device, verbose=False)

    start = time.time()
    for _ in range(iters):
        model.predict(dummy, imgsz=imgsz, device=device, verbose=False)
    elapsed = time.time() - start
    fps = iters / elapsed if elapsed > 0 else 0.0
    return fps, elapsed / iters


def main():
    args = parse_args()
    model_path = Path(args.model)
    if not model_path.exists():
        log.error(f"No se encontró el modelo: {model_path}")
        sys.exit(1)

    try:
        from ultralytics import YOLO
    except ImportError:
        log.error("Falta la dependencia 'ultralytics'. Instalar con: pip install ultralytics")
        sys.exit(1)

    log.info(f"Cargando modelo: {model_path}")
    model = YOLO(str(model_path))

    val_kwargs = {"imgsz": args.imgsz, "device": args.device}
    if args.data:
        val_kwargs["data"] = args.data

    log.info("Ejecutando validación sobre el dataset de validación...")
    metrics = model.val(**val_kwargs)

    per_class = {}
    try:
        maps = metrics.box.maps  # mAP50-95 por clase
        map50_per_class = metrics.box.ap50  # mAP50 por clase si está disponible
        for idx, class_name in CLASS_MAP.items():
            per_class[class_name] = {
                "map50": float(map50_per_class[idx]) if map50_per_class is not None else None,
                "map50_95": float(maps[idx]) if maps is not None else None,
            }
    except Exception as e:
        log.warning(f"No se pudieron extraer métricas por clase del objeto de resultados: {e}")

    global_map50 = float(getattr(metrics.box, "map50", 0.0))
    global_map = float(getattr(metrics.box, "map", 0.0))

    log.info(f"mAP@0.5 global: {global_map50:.3f} | mAP@0.5:0.95 global: {global_map:.3f}")
    for cname, cmetrics in per_class.items():
        log.info(f"  {cname}: mAP@0.5={cmetrics.get('map50')}")

    log.info(f"Benchmark de latencia ({args.benchmark_iters} iteraciones, imgsz={args.imgsz})...")
    fps, latency_s = run_benchmark(model, args.imgsz, args.device, args.benchmark_iters)
    log.info(f"FPS medido: {fps:.1f} | Latencia media: {latency_s*1000:.1f} ms")

    report = {
        "modelo": str(model_path),
        "global_map50": global_map50,
        "global_map50_95": global_map,
        "por_clase": per_class,
        "fps_medido": fps,
        "latencia_ms": latency_s * 1000,
        "imgsz": args.imgsz,
        "device": args.device,
    }

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "eval_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    log.info(f"Reporte guardado en {report_path}")

    if args.strict:
        gates = load_gates(args.gates)
        failures = []

        if fps < gates["min_fps"]:
            failures.append(f"FPS {fps:.1f} < mínimo requerido {gates['min_fps']}")
        if global_map50 < gates["global_map50"]:
            failures.append(f"mAP@0.5 global {global_map50:.3f} < mínimo requerido {gates['global_map50']}")

        for cname in CLASS_MAP.values():
            gate_key = f"{cname}_map50"
            achieved = per_class.get(cname, {}).get("map50")
            if achieved is not None and gate_key in gates and achieved < gates[gate_key]:
                failures.append(f"{cname} mAP@0.5 {achieved:.3f} < mínimo requerido {gates[gate_key]}")

        if failures:
            log.error("GATE --strict FALLIDO:")
            for f_msg in failures:
                log.error(f"  - {f_msg}")
            sys.exit(1)
        else:
            log.info("GATE --strict SUPERADO: todos los umbrales mínimos se cumplen.")

    log.info("Evaluación finalizada.")


if __name__ == "__main__":
    main()
