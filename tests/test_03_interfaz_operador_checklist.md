# Prueba 3 — Interfaz de Operador
### Validación de Funcionamiento · VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Corresponde a la fila **"Interfaz de Operador"** de la Tabla 4 (Indicadores de desempeño) del Informe de Desarrollo de Producto.

| Campo | Detalle |
|---|---|
| **Objetivo** | Evaluar la interpretabilidad de alertas en menos de 3 segundos |
| **Método** | Prueba de visualización directa del Panel de Detecciones por personal técnico |
| **Evidencia** | Capturas del dashboard con indicadores superiores + este checklist firmado |

## Por qué este test es un protocolo manual, no un script automatizado

La interpretabilidad en menos de 3 segundos es una medida de **percepción humana**, no de rendimiento de software: no puede simularse con un timer de código sin perder validez como evidencia. Los scripts de `tests/` automatizan lo que es legítimamente automatizable (FPS, lógica de alertas); esta prueba en cambio se documenta como protocolo repetible para que personal técnico la ejecute y dejar registro trazable, igual que se hizo en la validación original.

`test_03_smoke_test.py` en esta misma carpeta corre un chequeo técnico complementario (que los elementos críticos del dashboard existan y carguen), pero **no reemplaza** esta evaluación humana — solo confirma que las condiciones técnicas para realizarla están dadas.

## Protocolo

**Preparación:**
1. Tener el Panel de Detecciones abierto y con datos recientes (`frontend/dashboard.html`, ver `integration/README.md` para levantarlo).
2. Preparar al menos un evento de cada clase visible en la tabla (`mineral_normal`, `roca_oversize`, `metal_grande`), idealmente inyectados con `tests/test_02_gestion_alertas.py` o generados por el motor de inferencia real.
3. Reclutar a una persona con el perfil real de uso (operador de planta, sin formación técnica en IA), sin explicación previa del sistema.

**Ejecución (por evaluador/a):**

| # | Instrucción al evaluador/a | Tiempo objetivo | Resultado (Cumple / No cumple) |
|---|---|---|---|
| 1 | Mostrar la pantalla del dashboard sin contexto previo. Preguntar: "¿hay alguna alerta activa ahora mismo?" | < 3 s | |
| 2 | Preguntar: "¿qué tipo de material fue detectado en la última alerta?" | < 3 s | |
| 3 | Preguntar: "¿esta situación requiere acción inmediata o solo quedó registrada?" | < 3 s | |
| 4 | Preguntar: "¿cuántas detecciones ha habido hoy?" (usar tarjetas KPI superiores) | < 3 s | |

**Registro:**

```
Fecha de evaluación:        ____________________
Evaluador/a (nombre/rol):   ____________________
Perfil del sujeto de prueba:____________________
Resultado ítem 1:            Cumple / No cumple
Resultado ítem 2:            Cumple / No cumple
Resultado ítem 3:            Cumple / No cumple
Resultado ítem 4:            Cumple / No cumple
Resultado global:            Cumplido / No cumplido
Observaciones:               ____________________
Captura de pantalla adjunta: Sí / No (archivo: ____________)
```

## Evidencia esperada

- Este archivo, con la sección de registro completada y firmada.
- Al menos una captura de pantalla del Panel de Detecciones durante la prueba, con las tarjetas KPI y la tabla de eventos visibles (mismo tipo de evidencia ya documentada en Anexo A).
