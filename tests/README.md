# VIGIL-IA — Validación de Funcionamiento

Implementa las 3 pruebas de la **Tabla 4 (Indicadores de desempeño)** del Informe de Desarrollo de Producto — protocolo de estrés ejecutado bajo condiciones extremas en Atacama (1.030 m.s.n.m.) sobre la plataforma integrada.

| Prueba | Objetivo | Método | Evidencia | Archivo |
|---|---|---|---|---|
| Inferencia de Modelos (YOLOv8s) | Validar la capacidad de detección local bajo ≥25 FPS | Ejecución sobre Jetson Orin con flujo RTSP | Logs de consola y Model Card JSON | `test_01_inferencia_modelos.py` |
| Gestión de Alertas (Lógica de Negocio) | Validar la activación de alertas según umbrales | Inyección de eventos con objetos críticos y verificación de cambio de estado | Tabla de eventos con badges de estado | `test_02_gestion_alertas.py` |
| Interfaz de Operador | Evaluar la interpretabilidad de alertas en <3 seg | Visualización directa del Panel de Detecciones por personal técnico | Capturas del dashboard con indicadores superiores | `test_03_interfaz_operador_checklist.md` + `test_03_smoke_test.py` |

## Ejecutar la suite completa

```bash
# Con modelo entrenado disponible (corre las 3 pruebas automatizables)
python tests/run_validation_suite.py --model ./runs/train/vigilia_yolov8s/weights/best.pt

# Sin modelo entrenado a mano (omite la Prueba 1, corre 2 y 3)
python tests/run_validation_suite.py --skip_inferencia
```

Genera `tests/validation_report.json` con el resultado consolidado de cada prueba (`Cumplido` / `No cumplido` / `Omitido`).

## Evidencia de ejecuciones reales

`tests/evidence/` contiene las salidas reales (no simuladas) de correr esta suite contra el estado actual del repositorio, fechadas en el nombre del archivo:

- `validation_report_2026-01.json` — resultado consolidado de la suite completa. Corresponde a la validación de producto/desarrollo realizada originalmente en **enero de 2026**; regenerado como chequeo de regresión el 2026-07-07 (ver campo `fecha_regeneracion_artefacto` dentro del archivo).
- `validation_report_alertas_2026-02.json` — detalle de la Prueba 2 (eventos inyectados, matriz clase→riesgo→acción verificada, resultado `Cumplido`). Corresponde a la validación en terreno realizada del **25 al 27 de febrero de 2026** (Copper Phoenix I); regenerado como chequeo de regresión el 2026-07-07.

**La Prueba 1 (Inferencia de Modelos) figura como `Omitido`** en esta evidencia porque este entorno no cuenta con un checkpoint YOLOv8s entrenado (`best.pt`/`best.engine`) para ejecutar el benchmark de FPS real — no se fabricó un resultado. Para generar la evidencia de esa prueba en el nodo Jetson Orin con el modelo real:

```bash
python tests/run_validation_suite.py --model ./runs/train/vigilia_yolov8s/weights/best.pt
```

Y agregar el `validation_report.json` resultante a `tests/evidence/` con la fecha correspondiente.

## Por qué solo 2 de las 3 pruebas están 100% automatizadas

- **Prueba 1** reutiliza `scripts/02_evaluate.py --strict` como fuente única del benchmark de FPS — no se duplica esa lógica aquí.
- **Prueba 2** es completamente automática: inyecta eventos sintéticos en una base SQLite temporal y valida la matriz clase → riesgo → acción usando las mismas funciones (`backend/crud.py`) y constantes (`backend/constants.py`) que usa el sistema real, además de verificar que las etiquetas del frontend (`frontend/js/dashboard.js`) coincidan con los valores que produce el backend.
- **Prueba 3** mide interpretabilidad humana, que por definición no es automatizable sin perder validez como evidencia. Se documenta como protocolo manual repetible (`test_03_interfaz_operador_checklist.md`), acompañado de un chequeo técnico complementario (`test_03_smoke_test.py`) que solo verifica que las condiciones para ejecutarla estén dadas — nunca reemplaza la evaluación humana.

## Consistencia con el resto del proyecto

Estas pruebas no reimplementan reglas de negocio: importan `CLASS_MAP`, `RISK_LEVEL`, `ALERT_ACTION` y los umbrales de confianza directamente desde `backend/constants.py`, y extraen las etiquetas de riesgo directamente desde `frontend/js/dashboard.js`. Si alguno de esos archivos cambia y rompe la consistencia, `test_02_gestion_alertas.py` falla — de la misma forma en que `integration/run_integration_check.py` protege la consistencia entre el motor de inferencia y el backend.
