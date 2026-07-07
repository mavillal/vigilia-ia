# VIGIL-IA — Especificación del Dataset (fuente única de verdad)
### Copper Phoenix I · CORFO Semilla Inicia 25INI-282394 · Anexo C

Este documento es la referencia canónica de la composición del dataset de entrenamiento. Los valores aquí descritos son los mismos que aparecen en el Anexo C del proyecto (Figuras C.1, C.2, C.3) y en el docstring de `scripts/00_prepare_dataset.py`. Cualquier cambio en la composición real del dataset debe actualizarse primero aquí, y `data/dataset_manifest.json` (versión machine-readable de este mismo documento) debe editarse en el mismo commit — `scripts/validate_dataset_manifest.py` falla si ambos divergen.

## Composición por origen y subconjunto (Figura C.1)

| Categoría | Subconjunto | Imágenes | % Total | Condiciones de captura |
|---|---|---|---|---|
| Sintético | Mineral Normal simulado | 480 | 27,9% | Iluminación, ángulo cámara, granulometría |
| Sintético | Roca Oversize simulada | 420 | 24,4% | Texturas variables, tamaño, sombras duras |
| Sintético | Metal Grande simulado | 300 | 17,4% | Reflexión metálica, oclusión parcial |
| Nativo | Mineral Normal real | 280 | 16,3% | Radiación, polvo, vibración operativa |
| Nativo | Roca Oversize real | 140 | 8,1% | Variación de iluminación entre capturas |
| Nativo | Metal Grande real | 100 | 5,8% | Vibración operativa, polvo, velocidad de cinta |
| **TOTAL** | **Dataset híbrido completo** | **1.720** | **100%** | Split 80/20 train/val · Formato YOLOv8 TXT · Resolución 3840×2160 px |

## Distribución por clase operacional (Figura C.2)

| Clase | Nivel de riesgo | Total imgs | Sintéticas | Nativas | % Dataset |
|---|---|---|---|---|---|
| `mineral_normal` | Sin riesgo | 760 | 480 | 280 | 44,2% |
| `roca_oversize` | Riesgo | 560 | 420 | 140 | 32,6% |
| `metal_grande` | Daño | 400 | 300 | 100 | 23,3% |
| **TOTAL** | — | **1.720** | **1.200** | **520** | 100% |

## Formato de anotación (Figura C.3)

```
# Formato: class_id cx cy width height (normalizados 0–1)
# Ejemplo — Metal Grande detectado en frame FRM-00841
2 0.4821 0.5634 0.2341 0.1892
# Ejemplo — Roca Oversize detectada en frame FRM-00829
1 0.6234 0.4123 0.3412 0.2156
# Clases: 0=mineral_normal 1=roca_oversize 2=metal_grande
```

- **Umbral de confianza en entrenamiento:** 0,001 (NMS posterior — default de Ultralytics en `val()`, no se sobreescribe)
- **Umbral de confianza en producción (deploy):** `mineral_normal`=0,50 · `roca_oversize`=0,40 · `metal_grande`=0,30 (Anexo C.3 · `backend/constants.py::DEPLOY_CONF_THRESHOLDS`)

## Dónde se referencia esta especificación en el proyecto

| Parte del proyecto | Qué debe coincidir con esta especificación |
|---|---|
| `scripts/00_prepare_dataset.py` (docstring) | Composición total y por clase, split 80/20, formato YOLOv8 TXT |
| `backend/constants.py` | `CLASS_MAP`, `DEPLOY_CONF_THRESHOLDS` (umbrales de producción) |
| `scripts/04_deploy_inference.py` | `CLASS_MAP`, `DEFAULT_CONF_THRESHOLDS` (deben ser idénticos a `backend/constants.py`, verificado por `integration/run_integration_check.py`) |
| `docs/VIGIL-IA_Documentacion_Backend.md` | Umbrales de confianza citados en la tabla de endpoints |
| Informe de Validación Técnica (CORFO) | mAP@0.5 por clase, dataset composition, FPS |
| Anexo C del proyecto | Fuente original de estas cifras (Figuras C.1, C.2, C.3) |

## Métricas de validación asociadas (referencia, no forman parte del dataset en sí)

mAP@0.5 verificado (Anexo D.3): `mineral_normal`=0,743 · `roca_oversize`=0,672 · `metal_grande`=0,490 · global=0,67. Nota de consistencia ya documentada en el proyecto: el cuerpo de algunos informes etiqueta erróneamente la Precisión (91% / 74% / 61%, Figura C.2) como si fuera mAP — el valor de mAP@0.5 correcto para `mineral_normal` es 0,743, no 0,91. Esta especificación usa los valores de Precisión/Recall tal como aparecen en Figura C.2 (que sí son correctos como tales) y remite a Anexo D.3 para el mAP real.
