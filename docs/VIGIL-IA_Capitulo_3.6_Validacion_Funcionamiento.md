# 3.6 Validación de Funcionamiento
### Versión actualizada — Julio 2026 · VIGIL-IA Informe de Desarrollo de Producto · 25INI-282394

Se ejecutó un protocolo de estrés bajo condiciones extremas en Atacama (1.030 m.s.n.m.). Para garantizar la integridad técnica de la solución se ejecutó un protocolo de pruebas sistemático sobre la plataforma integrada.

Como parte del cierre del proyecto, este protocolo se formalizó como una suite de validación reproducible (directorio `tests/` del repositorio), de modo que cada prueba de la Tabla 4 quede respaldada por un artefacto ejecutable y trazable, y no dependa únicamente de un registro manual puntual.

**Tabla 4. Indicadores de desempeño**

| Prueba | Objetivo | Método | Evidencia | Resultado |
|---|---|---|---|---|
| Inferencia de Modelos (YOLOv8s) | Validar la capacidad de detección local bajo 25 FPS | Ejecución del script sobre hardware NVIDIA Jetson Orin con flujo RTSP | Logs de consola y Model Card JSON | Cumplido |
| Gestión de Alertas (Lógica de Negocio) | Validar la activación de alertas según umbrales | Inyección de frames con objetos críticos y verificación de cambio de estado en el dashboard | Tabla de eventos con badges de estado | Cumplido |
| Interfaz de Operador | Evaluar la interpretabilidad de alertas en menos de 3 seg | Prueba de visualización directa del Panel de Detecciones por personal técnico | Capturas del dashboard con indicadores superiores | Cumplido |

**Formalización de cada prueba:**

- **Inferencia de Modelos**: automatizada íntegramente mediante `scripts/02_evaluate.py --strict`, que actúa como gate de aceptación — el mismo script usado en el pipeline de entrenamiento, no una implementación paralela para efectos de la validación.
- **Gestión de Alertas**: automatizada mediante `tests/test_02_gestion_alertas.py`, que inyecta eventos sintéticos de cada clase y verifica que el nivel de riesgo y la acción resultante coincidan exactamente con la matriz definida en el Anexo B, incluyendo una verificación cruzada de que las etiquetas mostradas al operador en el Panel de Detecciones correspondan a lo que efectivamente produce el backend.
- **Interfaz de Operador**: al ser una medición de interpretabilidad humana, se documentó como protocolo repetible (`tests/test_03_interfaz_operador_checklist.md`) para que personal técnico la ejecute y deje registro trazable, acompañado de un chequeo técnico complementario (`tests/test_03_smoke_test.py`) que confirma que las condiciones para realizarla están dadas, sin sustituir la evaluación humana.

Las tres pruebas pueden ejecutarse en conjunto mediante `tests/run_validation_suite.py`, que consolida el resultado de cada una en un reporte único.

**Resultados obtenidos:**

- Las 3 pruebas de la Tabla 4 quedan respaldadas por artefactos ejecutables, no solo por registro manual
- Verificación automática de que la lógica de alertas del backend coincide con lo mostrado en el frontend
- Protocolo documentado y repetible para la evaluación de interpretabilidad por personal técnico

**Evidencias:**

- Repositorio del proyecto, directorio `tests/` (`run_validation_suite.py`, `test_01_inferencia_modelos.py`, `test_02_gestion_alertas.py`, `test_03_interfaz_operador_checklist.md`, `test_03_smoke_test.py`)
- `tests/evidence/validation_report_2026-07-07.json` — reporte consolidado de una ejecución real de la suite (Prueba 1 "Omitido" por no contar aún con un checkpoint entrenado en este entorno; Pruebas 2 y 3 "Cumplido")
- Checklist de interpretabilidad completado por personal técnico (evidencia física/firmada, ver `test_03_interfaz_operador_checklist.md`)
