#!/usr/bin/env python3
"""
04_deploy_inference.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Paso DEPLOY del pipeline (Anexo D, Figura D.1).
Motor de inferencia en producción: consume el stream RTSP de la cámara Axis
P1448-LE, ejecuta inferencia local con el motor TensorRT (best.engine) sobre
NVIDIA Jetson Orin, aplica la lógica de alertas por clase y registra los
eventos en SQLite. 100% local, sin dependencia de internet/nube.

Input : best.engine + fuente RTSP
Output: BD SQLite + alertas (log / alerta según clase)

Integración de componentes:
  Este script tiene una única responsabilidad — inferencia y persistencia —
  y NO expone ninguna API HTTP. La exposición de los eventos vía REST
  (/detecciones, /alertas, /resumen) corre en un proceso independiente:
  backend/main.py, que lee la misma base SQLite en modo solo-lectura. Ambos
  procesos se orquestan juntos mediante integration/ (docker-compose o
  unidades systemd), lo que evita acoplar el ciclo de vida del motor de
  inferencia al de la API y elimina cualquier duplicación de endpoints.

Lógica de alertas (Anexo B, Figura B.2):
  mineral_normal -> log        (sin riesgo)
  roca_oversize  -> alerta     (riesgo)
  metal_grande   -> alerta     (daño / inchancable)

Umbrales de confianza en producción (Anexo C, Figura C.3):
  mineral_normal = 0.50 · roca_oversize = 0.40 · metal_grande = 0.30
  (umbral reducido en metal_grande para priorizar recall sobre precisión,
  dado el 23.8% de falsos negativos observado en validación)

Uso:
  python 04_deploy_inference.py --model ./runs/export/best.engine \
      --source rtsp://192.168.1.100/stream1 --gpio
"""

import argparse
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("deploy_inference")

CLASS_MAP = {0: "mineral_normal", 1: "roca_oversize", 2: "metal_grande"}
RISK_LEVEL = {"mineral_normal": "sin_riesgo", "roca_oversize": "riesgo", "metal_grande": "daño"}
ALERT_ACTION = {"mineral_normal": "log", "roca_oversize": "alerta", "metal_grande": "alerta"}

DEFAULT_CONF_THRESHOLDS = {
    "mineral_normal": 0.50,
    "roca_oversize": 0.40,
    "metal_grande": 0.30,
}

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    frame_id INTEGER NOT NULL,
    clase TEXT NOT NULL,
    confianza REAL NOT NULL,
    nivel_riesgo TEXT NOT NULL,
    accion TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    bbox_cx REAL,
    bbox_cy REAL,
    bbox_w REAL,
    bbox_h REAL
);
"""


def parse_args():
    p = argparse.ArgumentParser(description="Motor de inferencia en producción VIGIL-IA (Jetson Orin)")
    p.add_argument("--model", required=True, help="Ruta a best.engine (TensorRT) o best.pt")
    p.add_argument("--source", required=True, help="Fuente de video RTSP (cámara Axis P1448-LE) o índice de webcam/archivo")
    p.add_argument("--db", default="./data/vigilia_events.db", help="Ruta a la base de datos SQLite")
    p.add_argument("--conf_mineral", type=float, default=DEFAULT_CONF_THRESHOLDS["mineral_normal"])
    p.add_argument("--conf_oversize", type=float, default=DEFAULT_CONF_THRESHOLDS["roca_oversize"])
    p.add_argument("--conf_metal", type=float, default=DEFAULT_CONF_THRESHOLDS["metal_grande"])
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--device", default="0")
    p.add_argument("--gpio", action="store_true", help="Habilitar salida GPIO en Jetson Orin para alertas sonoras/lumínicas")
    p.add_argument("--max_frames", type=int, default=None, help="Límite de frames a procesar (default: sin límite, corre continuo)")
    return p.parse_args()


def init_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute(DB_SCHEMA)
    conn.commit()
    return conn


def setup_gpio():
    """Inicializa GPIO en Jetson Orin para alertas sonoras/lumínicas. Falla de forma segura si no está disponible."""
    try:
        import Jetson.GPIO as GPIO  # noqa: N814
        ALERT_PIN = 7
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(ALERT_PIN, GPIO.OUT, initial=GPIO.LOW)
        log.info(f"GPIO inicializado en pin {ALERT_PIN} (Jetson.GPIO)")
        return GPIO, ALERT_PIN
    except ImportError:
        log.warning("Jetson.GPIO no disponible en este entorno. La bandera --gpio no tendrá efecto físico.")
        return None, None


def trigger_gpio_alert(gpio_ctx, duration_s=0.5):
    GPIO, pin = gpio_ctx
    if GPIO is None:
        return
    GPIO.output(pin, GPIO.HIGH)
    time.sleep(duration_s)
    GPIO.output(pin, GPIO.LOW)


def conf_threshold_for(class_name, thresholds):
    return thresholds[class_name]


def process_detection(conn, frame_id, class_id, confidence, bbox, gpio_ctx, gpio_enabled):
    class_name = CLASS_MAP[class_id]
    risk = RISK_LEVEL[class_name]
    action = ALERT_ACTION[class_name]
    ts = datetime.now(timezone.utc).isoformat()
    cx, cy, w, h = bbox

    conn.execute(
        "INSERT INTO eventos (frame_id, clase, confianza, nivel_riesgo, accion, timestamp, bbox_cx, bbox_cy, bbox_w, bbox_h) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (frame_id, class_name, confidence, risk, action, ts, cx, cy, w, h),
    )
    conn.commit()

    if action == "alerta":
        log.warning(f"[ALERTA] frame={frame_id} clase={class_name} conf={confidence:.2f} riesgo={risk}")
        if gpio_enabled:
            gpio_ctx_local = gpio_ctx
            if gpio_ctx_local[0] is not None:
                trigger_gpio_alert(gpio_ctx_local)
    else:
        log.info(f"[LOG] frame={frame_id} clase={class_name} conf={confidence:.2f}")


def run_inference_loop(model, source, conn, thresholds, gpio_ctx, gpio_enabled, imgsz, device, max_frames):
    try:
        import cv2
    except ImportError:
        log.error("Falta la dependencia 'opencv-python'. Instalar con: pip install opencv-python")
        sys.exit(1)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        log.error(f"No se pudo abrir la fuente de video: {source}")
        sys.exit(1)

    log.info(f"Stream abierto: {source}. Iniciando loop de inferencia (100% local, sin internet)...")
    frame_id = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                log.warning("No se pudo leer el frame. Reintentando conexión al stream RTSP...")
                time.sleep(1.0)
                cap.release()
                cap = cv2.VideoCapture(source)
                continue

            results = model.predict(frame, imgsz=imgsz, device=device, verbose=False)
            for r in results:
                boxes = getattr(r, "boxes", None)
                if boxes is None:
                    continue
                for box in boxes:
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])
                    if class_id not in CLASS_MAP:
                        continue
                    class_name = CLASS_MAP[class_id]
                    if confidence < conf_threshold_for(class_name, thresholds):
                        continue
                    xywhn = box.xywhn[0].tolist()  # cx, cy, w, h normalizados
                    process_detection(conn, frame_id, class_id, confidence, xywhn, gpio_ctx, gpio_enabled)

            frame_id += 1
            if max_frames is not None and frame_id >= max_frames:
                log.info(f"Límite de {max_frames} frames alcanzado. Deteniendo.")
                break
    except KeyboardInterrupt:
        log.info("Interrumpido por el usuario. Cerrando stream...")
    finally:
        cap.release()


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

    log.info(f"Cargando motor de inferencia: {model_path}")
    model = YOLO(str(model_path))

    thresholds = {
        "mineral_normal": args.conf_mineral,
        "roca_oversize": args.conf_oversize,
        "metal_grande": args.conf_metal,
    }
    log.info(f"Umbrales de confianza activos: {json.dumps(thresholds, ensure_ascii=False)}")

    conn = init_db(Path(args.db))
    log.info(f"Base de datos SQLite lista en {args.db}")

    gpio_ctx = (None, None)
    if args.gpio:
        gpio_ctx = setup_gpio()

    run_inference_loop(
        model=model,
        source=args.source,
        conn=conn,
        thresholds=thresholds,
        gpio_ctx=gpio_ctx,
        gpio_enabled=args.gpio,
        imgsz=args.imgsz,
        device=args.device,
        max_frames=args.max_frames,
    )

    conn.close()
    log.info("Motor de inferencia detenido.")


if __name__ == "__main__":
    main()
