# VIGIL-IA — Descriptores Técnicos del Pipeline de Entrenamiento
### CORFO Semilla Inicia · Código 25INI-282394 · Anexo D — Scripts de Entrenamiento

---

## 00_prepare_dataset.py — Preparación y Validación del Dataset

```python
EXPECTED_COLUMNS = {"image_filename", "class_id", "origin", "cx", "cy", "width", "height"}

def load_master_csv(csv_path: Path):
    """Lee el CSV maestro y agrupa anotaciones por imagen. No inventa filas faltantes."""
    ...
    for row in reader:
        class_id = int(row["class_id"])
        if class_id not in CLASS_MAP:
            log.warning(f"class_id desconocido ({class_id}) en {fname}, se omite fila")
            continue
```

Este script constituye la puerta de entrada del pipeline y su función es transformar el activo crudo del proyecto —un CSV maestro de anotaciones más un repositorio de imágenes 4K capturadas en Copper Phoenix I— en una estructura de datos íntegra, verificada y lista para ser consumida por el framework de entrenamiento. Desde una perspectiva de arquitectura, lo tratamos como la capa de "data contract": ningún archivo avanza a la etapa de entrenamiento sin haber pasado por una validación explícita de existencia física, de formato de clase y de integridad de las coordenadas normalizadas.

```python
def validate_images(annotations, origins, images_dir: Path):
    """Verifica que cada imagen referenciada exista físicamente. Reporta faltantes sin inventar datos."""
    valid, missing = [], []
    for fname in annotations:
        if (images_dir / fname).exists():
            valid.append(fname)
        else:
            missing.append(fname)
    log.info(f"Imágenes válidas: {len(valid)} / {len(annotations)}")
    return valid
```

El funcionamiento se apoya en tres operaciones secuenciales. Primero, se parsea el CSV maestro y se agrupan las anotaciones por imagen, validando que cada fila declare una de las tres clases operacionales del proyecto (mineral_normal, roca_oversize, metal_grande) y descartando de forma explícita —nunca silenciosa— cualquier fila con una clase no reconocida. Segundo, se realiza un cruce contra el sistema de archivos para confirmar que cada imagen referenciada exista realmente en el directorio de origen, reportando cualquier discrepancia en vez de asumir que el dato está completo. Tercero, se ejecuta un split estratificado 80/20 por clase dominante, de modo que la proporción de mineral_normal, roca_oversize y metal_grande se mantenga equilibrada tanto en el subconjunto de entrenamiento como en el de validación, evitando el sesgo que introduciría un split puramente aleatorio sobre un dataset con distribución de clases desigual (44,2% / 32,6% / 23,3%).

```python
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

En términos de implementación, el script no depende de librerías de terceros para el procesamiento central —usa `csv`, `pathlib` y `random` de la librería estándar—, lo que lo hace portable entre el entorno de desarrollo y el entorno de despliegue en Jetson Orin sin fricciones de dependencias. La escritura de archivos de imagen se resuelve mediante symlinks por defecto (con fallback automático a copia física si el sistema de archivos no soporta enlaces simbólicos), lo que minimiza el uso de disco al no duplicar los datos de origen. Las etiquetas se emiten en el formato YOLOv8 TXT estándar (`class_id cx cy width height`, normalizado 0–1), idéntico al documentado en el Anexo C.

```python
try:
    dst_img.symlink_to(src_img.resolve())
except OSError:
    shutil.copy2(src_img, dst_img)   # fallback si el filesystem no soporta symlinks

label_path = out_labels_dir / (Path(fname).stem + ".txt")
with open(label_path, "w") as lf:
    for class_id, cx, cy, w, h in annotations[fname]:
        lf.write(f"{class_id} {cx:.4f} {cy:.4f} {w:.4f} {h:.4f}\n")
```

El artefacto de salida principal es la estructura `images/{train,val}` y `labels/{train,val}`, acompañada de un archivo `vigilia_dataset.yaml` autogenerado que declara las rutas y el mapeo de las tres clases, y que es consumido directamente por Ultralytics en la etapa siguiente. Adicionalmente se emite un `dataset_summary.json` con el conteo real de imágenes procesadas, faltantes y la proporción de split efectivamente aplicada, lo que da trazabilidad auditable a cada corrida.

```python
summary = {
    "total_imagenes": len(valid_files),
    "imagenes_faltantes": len(annotations) - len(valid_files),
    "train": len(train_files),
    "val": len(val_files),
    "split_ratio": args.split,
    "clases": CLASS_MAP,
}
summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
```

Desde la mirada de gobernanza técnica, este script es el punto de control que impide que un problema de datos —una imagen faltante, un class_id corrupto, un archivo mal referenciado— se propague silenciosamente hasta contaminar un entrenamiento de varias horas. Preferimos fallar rápido y con contexto (logging explícito de cada imagen faltante) antes que entrenar sobre un dataset parcialmente inconsistente; esta es una decisión de diseño deliberada dado el costo de cómputo de reentrenar un YOLOv8s sobre 150 épocas.

---

## 01_train.py — Entrenamiento de YOLOv8s

```python
p.add_argument("--model_size", default="s", choices=["n", "s", "m", "l", "x"],
               help="Tamaño del modelo YOLOv8 (default: s, usado en producción)")
p.add_argument("--epochs", type=int, default=150, help="Épocas de entrenamiento (default: 150)")
```

Este script encapsula la etapa de aprendizaje del sistema: toma el dataset ya validado y estructurado por `00_prepare_dataset.py` y entrena un modelo YOLOv8s especializado en la detección de las tres clases operacionales sobre imágenes de cinta transportadora. La elección del tamaño "s" (small) de la familia YOLOv8 no es arbitraria: responde al balance entre precisión y latencia requerido para correr inferencia en tiempo real sobre el hardware edge del proyecto (Jetson Orin), descartando variantes más pesadas (m/l/x) que comprometerían el umbral de ≥25 FPS validado en terreno.

```python
weights = args.pretrained or f"yolov8{args.model_size}.pt"
model = YOLO(weights)

results = model.train(
    data=str(data_path),
    epochs=args.epochs,
    imgsz=args.imgsz,
    batch=args.batch,
    patience=args.patience,
    device=args.device,
    project=args.project,
    name=args.name,
    exist_ok=True,
)
```

El flujo de entrenamiento delega el ciclo de optimización al framework Ultralytics, que internamente gestiona el forward/backward pass, el scheduler de learning rate, el data augmentation (mosaic, flip, HSV jitter) y el checkpointing automático del mejor modelo según la métrica de validación. Nuestro script se limita a orquestar esta llamada con los hiperparámetros del proyecto —150 épocas, tamaño de imagen configurable, batch size y early-stopping patience— y a exponerlos como argumentos de línea de comando para que cualquier reentrenamiento futuro (por ejemplo, para calibración específica por yacimiento) sea reproducible sin tocar código.

```python
run_dir = Path(model.trainer.save_dir)
best_pt = run_dir / "weights" / "best.pt"

if not best_pt.exists():
    log.error("No se generó best.pt. Revisar logs de entrenamiento de Ultralytics.")
    sys.exit(1)
```

Un aspecto relevante de la implementación es que el script no hardcodea ninguna métrica de resultado esperado: toda cifra de rendimiento (mAP por clase, época del mejor checkpoint) se extrae dinámicamente del objeto `results` que retorna Ultralytics al finalizar el entrenamiento, y no de valores fijados de antemano. Esto es deliberado — el entrenamiento sobre un dataset híbrido (1.200 imágenes sintéticas + 520 nativas) puede variar levemente entre corridas por la naturaleza estocástica del proceso, y el reporte debe reflejar siempre lo efectivamente logrado, no una expectativa.

```python
metadata = {
    "modelo_base": weights,
    "clases": CLASS_MAP,
    "epochs_solicitadas": args.epochs,
    "run_dir": str(run_dir),
    "best_pt": str(best_pt),
    "results_csv": str(run_dir / "results.csv"),
    "results_png": str(run_dir / "results.png"),
}
meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
```

Las salidas del script son los artefactos estándar de un run de Ultralytics: `best.pt` (checkpoint con mejor desempeño en validación), `last.pt` (último checkpoint, útil para reanudar entrenamientos interrumpidos), y las curvas de entrenamiento (`results.csv`, `results.png`) que documentan la evolución de las funciones de pérdida y las métricas por época — el mismo tipo de evidencia visual referenciado como Figura 3 y Figura 4 en el Informe de Desarrollo de Producto. Se agrega también un `train_metadata.json` con la configuración exacta usada, dando trazabilidad completa entre el modelo entregado y los parámetros que lo generaron.

```python
p.add_argument("--resume", action="store_true", help="Reanudar desde el último checkpoint")
p.add_argument("--pretrained", default=None,
               help="Pesos preentrenados custom (default: yolov8{size}.pt de Ultralytics)")
```

Desde la perspectiva de ingeniería de producto, este script es el corazón del ciclo de mejora continua del sistema: cualquier ampliación futura del dataset nativo (la meta declarada de escalar de 520 a más de 2.000 imágenes reales) o cualquier ajuste de hiperparámetros de rotación para compensar la vibración estructural detectada en campo, se ejecuta reinvocando este mismo script con nuevos datos de entrada, sin requerir cambios estructurales en el pipeline.

---

## 02_evaluate.py — Evaluación por Clase y Benchmark de Latencia

```python
DEFAULT_GATES = {
    "mineral_normal_map50": 0.70,
    "roca_oversize_map50": 0.60,
    "metal_grande_map50": 0.45,
    "global_map50": 0.60,
    "min_fps": 25.0,
}
```

Este script responde a una pregunta que en un proyecto de visión artificial para minería no es opcional: ¿el modelo entrenado es efectivamente apto para producción, o solo se ve bien en una métrica agregada? Por eso el script está diseñado para reportar dos dimensiones independientes y complementarias: la calidad de detección desagregada por clase (precisión, recall, mAP@0.5) y el desempeño de latencia/FPS medido empíricamente sobre el hardware de destino, en vez de asumir ambos a partir de un único número global.

```python
metrics = model.val(**val_kwargs)
maps = metrics.box.maps
map50_per_class = metrics.box.ap50
for idx, class_name in CLASS_MAP.items():
    per_class[class_name] = {
        "map50": float(map50_per_class[idx]),
        "map50_95": float(maps[idx]),
    }
```

Técnicamente, la evaluación de calidad delega en la rutina `model.val()` de Ultralytics sobre el subconjunto de validación generado en la etapa DATA, y extrae de ahí las métricas por clase (`box.ap50`, `box.maps`) y globales (`box.map50`, `box.map`). El benchmark de latencia, en cambio, es una rutina propia: ejecuta un warmup de cinco inferencias para estabilizar el uso de GPU y luego mide el tiempo real de `model.predict()` sobre N iteraciones configurables, reportando FPS y latencia media en milisegundos — la misma métrica que en el Informe de Validación Técnica se documenta como el umbral crítico de ≥25 FPS sobre Jetson Orin con flujo RTSP.

```python
if args.strict:
    gates = load_gates(args.gates)
    failures = []
    if fps < gates["min_fps"]:
        failures.append(f"FPS {fps:.1f} < mínimo requerido {gates['min_fps']}")
    if global_map50 < gates["global_map50"]:
        failures.append(f"mAP@0.5 global {global_map50:.3f} < mínimo requerido {gates['global_map50']}")
    if failures:
        sys.exit(1)
```

El elemento más relevante desde el punto de vista de calidad de software es la bandera `--strict`, pensada explícitamente para integrarse en un pipeline de CI/CD: convierte el script de una herramienta de reporte pasivo a un gate de aceptación activo, que retorna un código de salida distinto de cero si el modelo no alcanza umbrales mínimos configurables de mAP por clase y de FPS. Estos umbrales por defecto están calibrados como un piso de no regresión respecto a lo efectivamente alcanzado en la validación de Copper Phoenix I, no como metas aspiracionales, y son sobreescribibles vía un JSON externo para adaptarse a futuras iteraciones del modelo.

```python
report = {
    "global_map50": global_map50,
    "por_clase": per_class,
    "fps_medido": fps,
    "latencia_ms": latency_s * 1000,
}
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
```

La salida se materializa en un `eval_report.json` estructurado —con métricas por clase, métricas globales, FPS y latencia— que queda disponible tanto para consumo humano (como evidencia formal ante CORFO) como para consumo programático por la siguiente etapa del pipeline, ya que `03_export.py` puede incorporar este mismo reporte dentro del model card final, evitando la duplicación o transcripción manual de cifras entre documentos.

```python
for cname in CLASS_MAP.values():
    gate_key = f"{cname}_map50"
    achieved = per_class.get(cname, {}).get("map50")
    if achieved is not None and achieved < gates[gate_key]:
        failures.append(f"{cname} mAP@0.5 {achieved:.3f} < mínimo requerido {gates[gate_key]}")
```

Operacionalmente, este script es el que permite distinguir con evidencia objetiva por qué metal_grande —la clase de mayor criticidad y menor representación nativa— exhibe un desempeño más conservador que mineral_normal, y por qué esa brecha se compensa en producción con un umbral de confianza reducido (0,30) en vez de exigir una paridad de mAP entre clases que el tamaño actual del dataset nativo (100 imágenes) no permite sostener de forma realista.

---

## 03_export.py — Exportación a TensorRT FP16 y ONNX

```python
DEPLOY_CONF_THRESHOLDS = {
    "mineral_normal": 0.50,
    "roca_oversize": 0.40,
    "metal_grande": 0.30,
}
```

Este script marca la transición de "modelo de investigación" a "artefacto de producción". Un checkpoint `best.pt` de PyTorch no está optimizado para correr con baja latencia sobre el hardware embebido de Jetson Orin; este script lo convierte en dos formatos con propósitos distintos: TensorRT (`best.engine`), el formato de ejecución optimizado para GPU NVIDIA que efectivamente corre en producción, y ONNX (`best.onnx`), un formato intermedio portable útil para depuración, validación cruzada o despliegue en hardware no-NVIDIA si el proyecto lo requiriera a futuro.

```python
onnx_path = model.export(format="onnx", imgsz=args.imgsz, half=args.half)
engine_path = model.export(format="engine", imgsz=args.imgsz, half=args.half, device=args.device)
```

La decisión de exportar en precisión FP16 (half precision) en vez de FP32 es una decisión de ingeniería directamente ligada al requisito de negocio de operar en el borde sin conexión a internet: FP16 reduce a la mitad el uso de memoria y aumenta significativamente el throughput de inferencia en las Tensor Cores de Jetson Orin, a un costo de precisión numérica que en la práctica es despreciable para un problema de detección de objetos con las tres clases del proyecto. Esta es precisamente la configuración validada en el protocolo de pruebas de campo documentado en el Informe de Validación Técnica.

```python
try:
    engine_path = model.export(format="engine", imgsz=args.imgsz, half=args.half, device=args.device)
except Exception as e:
    log.error(f"Fallo el export a TensorRT: {e}")
    if args.skip_onnx:
        sys.exit(1)
    log.warning("Continuando solo con el artefacto ONNX generado.")
```

El script delega el trabajo pesado de conversión en la función `export()` de Ultralytics, que internamente gestiona la traza del grafo computacional, la fusión de capas y la generación del engine específico para la arquitectura de GPU presente en el dispositivo de export — por eso el export a TensorRT debe ejecutarse en el hardware de destino real (Jetson Orin) y no es portable entre arquitecturas de GPU distintas, a diferencia del artefacto ONNX que sí lo es. El script maneja explícitamente el escenario de fallo de este paso (por ejemplo, ausencia de TensorRT en el entorno de export) sin abortar el pipeline completo si al menos el artefacto ONNX se generó correctamente.

```python
model_card = {
    "modelo_base": "YOLOv8s",
    "clases": CLASS_MAP,
    "umbrales_confianza_produccion": DEPLOY_CONF_THRESHOLDS,
    "hardware_objetivo": "NVIDIA Jetson Orin",
    "camara": "Axis P1448-LE (3840x2160 px, RTSP)",
    "metricas_validacion": metrics_section,
}
card_path.write_text(json.dumps(model_card, indent=2, ensure_ascii=False))
```

El artefacto distintivo de este script es el `model_card.json`: un documento de trazabilidad que consolida en un único punto la versión del modelo, los umbrales de confianza de producción por clase, la resolución y formato de cámara, el hardware objetivo, y —cuando está disponible— las métricas de validación reales obtenidas en `02_evaluate.py`. Esto responde a una necesidad concreta de gobernanza de modelos: cualquier auditoría posterior (CORFO, un cliente, un ajuste de fine-tuning) puede reconstruir exactamente qué modelo está corriendo y bajo qué condiciones fue validado, sin depender de la memoria del equipo o de documentación desactualizada.

```python
if args.eval_report and Path(args.eval_report).exists():
    eval_data = json.loads(Path(args.eval_report).read_text())
    metrics_section = {
        "global_map50": eval_data.get("global_map50"),
        "por_clase": eval_data.get("por_clase"),
        "fps_medido": eval_data.get("fps_medido"),
    }
```

Este script es, en definitiva, el punto donde la responsabilidad técnica se vuelve explícita: es la última oportunidad de dejar registro verificable de qué se está desplegando antes de que el artefacto llegue al motor de inferencia en el yacimiento, y por diseño no permite avanzar sin dejar ese registro.

---

## 04_deploy_inference.py — Motor de Inferencia en Producción

```python
RISK_LEVEL = {"mineral_normal": "sin_riesgo", "roca_oversize": "riesgo", "metal_grande": "daño"}
ALERT_ACTION = {"mineral_normal": "log", "roca_oversize": "alerta", "metal_grande": "alerta"}
```

Este es el script que efectivamente corre en el Jetson Orin instalado junto a la cinta transportadora en Copper Phoenix I, y representa el cierre del ciclo completo de la propuesta de valor de VIGIL-IA: captura de video, inferencia local y generación de alertas operacionales, sin ninguna dependencia de conectividad a internet o servicios en la nube. Consume el stream RTSP entregado por la cámara Axis P1448-LE, aplica el motor TensorRT exportado en la etapa anterior, y traduce cada detección en una acción de negocio concreta según la clase identificada.

```python
DEFAULT_CONF_THRESHOLDS = {
    "mineral_normal": 0.50,
    "roca_oversize": 0.40,
    "metal_grande": 0.30,
}

if confidence < conf_threshold_for(class_name, thresholds):
    continue
```

El núcleo de la lógica de negocio está en la aplicación diferenciada de umbrales de confianza por clase antes de registrar cualquier detección: 0,50 para mineral_normal, 0,40 para roca_oversize y 0,30 para metal_grande. Este umbral reducido en la clase crítica no es un descuido sino una decisión deliberada de diseño: dado que la validación técnica documentó una tasa de falsos negativos de 23,8% en metal_grande (19 de 80 casos), se prioriza explícitamente el recall sobre la precisión en esa clase, bajo la premisa operacional de que una alerta por exceso es más tolerable que un inchancable no detectado que dañe un chancador aguas abajo.

```python
conn.execute(
    "INSERT INTO eventos (frame_id, clase, confianza, nivel_riesgo, accion, timestamp, "
    "bbox_cx, bbox_cy, bbox_w, bbox_h) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    (frame_id, class_name, confidence, risk, action, ts, cx, cy, w, h),
)
conn.commit()
```

Cada detección que supera su umbral correspondiente se persiste en una base SQLite local mediante una tabla `eventos` con timestamp, clase, confianza, nivel de riesgo, acción tomada y coordenadas de la caja detectada — la misma fuente de datos que alimenta la tabla de eventos con badges de estado del Panel de Detecciones. La elección de SQLite en vez de un motor de base de datos cliente-servidor es intencional: es embebido, no requiere proceso servidor separado, y es resiliente a los micro-cortes de energía documentados como riesgo operacional en el desierto de Atacama, siempre que se resguarde con la protección UPS contemplada en las próximas etapas del proyecto.

```python
def setup_gpio():
    try:
        import Jetson.GPIO as GPIO
        GPIO.setup(ALERT_PIN, GPIO.OUT, initial=GPIO.LOW)
        return GPIO, ALERT_PIN
    except ImportError:
        log.warning("Jetson.GPIO no disponible. --gpio no tendrá efecto físico.")
        return None, None
```

El script contempla dos mecanismos de acción física además del registro en base de datos: una capa opcional de salida GPIO (activable con `--gpio`) que permite disparar alertas sonoras o lumínicas directamente desde los pines del Jetson Orin cuando se detecta metal_grande o roca_oversize, y una capa de API vía FastAPI que expone los eventos recientes y un resumen agregado por clase, pensada para ser consumida por el Panel de Detecciones sin que el frontend necesite acceso directo a la base de datos. Ambas capas están diseñadas para degradarse de forma segura: si `Jetson.GPIO` no está disponible en el entorno de ejecución, o si FastAPI no está instalado, el motor de inferencia continúa operando sin interrumpirse.

```python
while True:
    ret, frame = cap.read()
    if not ret:
        log.warning("No se pudo leer el frame. Reintentando conexión al stream RTSP...")
        time.sleep(1.0)
        cap.release()
        cap = cv2.VideoCapture(source)
        continue
```

Finalmente, el loop de inferencia incluye manejo explícito de pérdida de señal RTSP —reintentando la conexión en vez de terminar el proceso— dado que la vibración operativa y las condiciones extremas de polvo y radiación en el yacimiento son factores de riesgo documentados para la estabilidad de la captura de video; este script está pensado para operar de forma continua y desatendida durante turnos de 8 a 24 horas, no como un proceso de corrida única.

---

## 05_run_pipeline.py — Orquestador End-to-End

```python
report["etapas"].append(run_step(
    "DATA",
    [sys.executable, "00_prepare_dataset.py", "--csv", args.csv, "--images", args.images],
))
```

Este script no introduce lógica de negocio nueva: su responsabilidad es encadenar de forma confiable y reproducible las cinco etapas anteriores —data, train, eval, export y deploy— en una única invocación, tal como se documenta en el comando de referencia del Anexo D.2. Desde la perspectiva de un CTO, este es el componente que transforma cinco scripts independientes en un pipeline de MLOps real: reduce el error humano de ejecutar pasos en el orden incorrecto u olvidar propagar una ruta de artefacto entre etapas.

```python
def run_step(name, cmd, allow_fail=False):
    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR))
    if result.returncode != 0 and not allow_fail:
        log.error(f"Etapa {name} falló (código {result.returncode}). Abortando pipeline.")
        sys.exit(result.returncode)
```

La implementación invoca cada script como un subproceso independiente (`subprocess.run`) en vez de importar sus funciones directamente en el mismo proceso Python. Esta decisión es deliberada: aísla el entorno de ejecución de cada etapa —relevante porque el entrenamiento y la evaluación requieren GPU/CUDA mientras que el deploy final corre específicamente en Jetson Orin con TensorRT—, y permite que un fallo en una etapa no deje al intérprete en un estado de memoria corrupto o con recursos de GPU sin liberar, algo especialmente relevante en corridas de entrenamiento de larga duración.

```python
dataset_yaml = str(Path(args.data_output) / "vigilia_dataset.yaml")
best_pt = str(Path(args.train_project) / args.train_name / "weights" / "best.pt")
eval_report_path = str(Path(args.export_dir).parent / "eval" / "eval_report.json")
```

El orquestador propaga automáticamente las rutas de artefactos entre etapas: el `vigilia_dataset.yaml` generado por DATA se pasa a TRAIN, el `best.pt` resultante de TRAIN se pasa tanto a EVAL como a EXPORT, y el `eval_report.json` de EVAL se inyecta en EXPORT para enriquecer el `model_card.json` final — eliminando la necesidad de que un operador copie rutas manualmente entre comandos, que es una fuente común de error en pipelines ejecutados a mano.

```python
if args.skip_deploy:
    log.info("=== Etapa DEPLOY === omitida (--skip_deploy)")
    report["etapas"].append({"etapa": "DEPLOY", "estado": "omitida", "codigo_salida": None})
else:
    deploy_cmd = [sys.executable, "04_deploy_inference.py", "--model", best_engine, "--source", args.source]
```

Un detalle de diseño relevante es la bandera `--skip_deploy`, incluida en el propio comando de referencia documentado en el Anexo D: permite ejecutar el pipeline completo de data-a-export en cualquier entorno de desarrollo con GPU (no necesariamente Jetson Orin), y reservar la etapa DEPLOY —que requiere el hardware físico instalado en terreno junto a la cinta transportadora— para una ejecución separada directamente en el dispositivo edge. Esto refleja una realidad operacional real del proyecto: el ciclo de entrenamiento y validación no ocurre en el mismo hardware que el ciclo de inferencia en producción.

```python
report["fin"] = datetime.now(timezone.utc).isoformat()
report["exitoso"] = all(e["estado"] in ("ok", "omitida") for e in report["etapas"])
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
```

El resultado final es un `pipeline_report.json` que documenta el estado de cada etapa (éxito, fallo u omitida), el código de salida y el comando exacto ejecutado, constituyendo en sí mismo una pieza de evidencia auditable de que el pipeline end-to-end fue ejecutado y validado de manera consistente — el mismo tipo de evidencia que respalda la afirmación, en el Informe de Desarrollo de Producto, de que el flujo cámara → inferencia → alerta fue integrado y validado de extremo a extremo.
