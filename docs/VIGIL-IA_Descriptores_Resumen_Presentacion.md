# VIGIL-IA — Pipeline de Entrenamiento (versión resumida para presentación)
### CORFO Semilla Inicia · 25INI-282394

---

**00_prepare_dataset.py — Preparación de Datos**
Valida y estructura el dataset de Copper Phoenix I (1.720 imágenes) a partir del CSV maestro: verifica que cada imagen exista, aplica un split 80/20 estratificado por clase y genera el archivo de configuración que alimenta el entrenamiento. Es el control de calidad que evita entrenar sobre datos incompletos o mal etiquetados.

```python
# Clases operacionales VIGIL-IA (Anexo C, Figura C.3)
CLASS_MAP = {0: "mineral_normal", 1: "roca_oversize", 2: "metal_grande"}

def stratified_split(valid_files, annotations, split_ratio, seed):
    """Split 80/20 estratificado por clase dominante de cada imagen."""
    random.seed(seed)
    by_class = defaultdict(list)
    for fname in valid_files:
        classes_in_img = [a[0] for a in annotations[fname]]
        dominant_class = max(set(classes_in_img), key=classes_in_img.count)
        by_class[dominant_class].append(fname)

    train_set, val_set = [], []
    for class_id, files in by_class.items():
        random.shuffle(files)
        cut = int(len(files) * split_ratio)
        train_set.extend(files[:cut])
        val_set.extend(files[cut:])
    return train_set, val_set
```

**01_train.py — Entrenamiento YOLOv8s**
Entrena el modelo YOLOv8s sobre las 3 clases operacionales (mineral_normal, roca_oversize, metal_grande) durante 150 épocas, usando el framework Ultralytics. Genera el checkpoint `best.pt` y las curvas de entrenamiento, sin fijar de antemano ninguna métrica: todo resultado se extrae directamente de la corrida real.

```python
weights = args.pretrained or f"yolov8{args.model_size}.pt"  # default: yolov8s.pt
model = YOLO(weights)

results = model.train(
    data=str(data_path),
    epochs=args.epochs,      # default: 150
    imgsz=args.imgsz,
    batch=args.batch,
    patience=args.patience,  # early stopping
    device=args.device,
    project=args.project,
    name=args.name,
    exist_ok=True,
)

run_dir = Path(model.trainer.save_dir)
best_pt = run_dir / "weights" / "best.pt"  # métricas se extraen de la corrida real, no se fijan a priori
```

**02_evaluate.py — Evaluación por Clase**
Mide precisión, recall y mAP@0.5 por clase, más un benchmark real de FPS sobre el hardware de destino. Incluye un modo `--strict` que actúa como gate de calidad: bloquea el avance del pipeline si el modelo no cumple los umbrales mínimos (incluyendo el piso de ≥25 FPS validado en terreno).

```python
# Umbrales mínimos de gate para --strict, calibrados como piso de
# no-regresión sobre lo efectivamente logrado en Copper Phoenix I
DEFAULT_GATES = {
    "mineral_normal_map50": 0.70,
    "roca_oversize_map50": 0.60,
    "metal_grande_map50": 0.45,
    "global_map50": 0.60,
    "min_fps": 25.0,
}

if args.strict:
    failures = []
    if fps < gates["min_fps"]:
        failures.append(f"FPS {fps:.1f} < mínimo requerido {gates['min_fps']}")
    if failures:
        log.error("GATE --strict FALLIDO:")
        sys.exit(1)
```

**03_export.py — Exportación a Producción**
Convierte el modelo entrenado a TensorRT FP16 (formato optimizado para Jetson Orin) y a ONNX. Genera además un `model_card.json` con la trazabilidad completa: versión del modelo, umbrales de confianza por clase y métricas de validación reales.

```python
# Umbrales de confianza en producción por clase (Anexo C, Figura C.3)
DEPLOY_CONF_THRESHOLDS = {
    "mineral_normal": 0.50,
    "roca_oversize": 0.40,
    "metal_grande": 0.30,
}

engine_path = model.export(format="engine", imgsz=args.imgsz,
                            half=args.half, device=args.device)  # TensorRT FP16

model_card = {
    "modelo_base": "YOLOv8s",
    "clases": CLASS_MAP,
    "umbrales_confianza_produccion": DEPLOY_CONF_THRESHOLDS,
    "hardware_objetivo": "NVIDIA Jetson Orin",
    "metricas_validacion": metrics_section,  # tomadas de 02_evaluate.py, no inventadas
}
```

**04_deploy_inference.py — Motor de Inferencia en Producción**
Corre en el Jetson Orin instalado en terreno: procesa el stream RTSP de la cámara, aplica umbrales de confianza diferenciados por clase (0,50 / 0,40 / 0,30) y registra cada evento en SQLite. El umbral reducido en metal_grande prioriza deliberadamente el recall, dado el 23,8% de falsos negativos detectado en validación. Incluye alertas GPIO y una API local para el dashboard.

```python
# Lógica de alertas (Anexo B, Figura B.2)
RISK_LEVEL = {"mineral_normal": "sin_riesgo", "roca_oversize": "riesgo", "metal_grande": "daño"}
ALERT_ACTION = {"mineral_normal": "log", "roca_oversize": "alerta", "metal_grande": "alerta"}

for box in boxes:
    class_id = int(box.cls[0])
    confidence = float(box.conf[0])
    class_name = CLASS_MAP[class_id]
    if confidence < conf_threshold_for(class_name, thresholds):  # 0.50 / 0.40 / 0.30
        continue
    process_detection(conn, frame_id, class_id, confidence, xywhn, gpio_ctx, gpio_enabled)

if action == "alerta" and gpio_enabled:
    trigger_gpio_alert(gpio_ctx)  # salida física en Jetson Orin
```

**05_run_pipeline.py — Orquestador End-to-End**
Encadena las 5 etapas anteriores en una sola ejecución, propagando automáticamente los artefactos entre pasos (dataset → modelo → métricas → export → deploy). Incluye la opción `--skip_deploy` para correr todo el ciclo de entrenamiento fuera del hardware Jetson Orin. Cierra con un reporte JSON auditable del pipeline completo.

```python
# 00 · DATA -> genera vigilia_dataset.yaml, usado directo por TRAIN
report["etapas"].append(run_step("DATA", [
    sys.executable, "00_prepare_dataset.py",
    "--csv", args.csv, "--images", args.images, "--split", str(args.split),
]))

# 01 · TRAIN -> usa la salida de DATA
report["etapas"].append(run_step("TRAIN", [
    sys.executable, "01_train.py",
    "--data", dataset_yaml, "--model_size", args.model_size, "--epochs", str(args.epochs),
]))

if args.skip_deploy:
    report["etapas"].append({"etapa": "DEPLOY", "estado": "omitida"})  # útil fuera de Jetson Orin
```
