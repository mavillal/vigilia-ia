# VIGIL-IA

Plataforma de visión artificial en el borde (edge computing) para monitoreo de cintas transportadoras mineras — detección de material sobredimensionado (`roca_oversize`) y metal inchancable (`metal_grande`) en tiempo real, 100% local (sin dependencia de internet/nube).

**Proyecto:** VIGIL SpA · **CORFO Semilla Inicia** 25INI-282394
**Sitio piloto:** Copper Phoenix I — Barreal Seco, Taltal, Región de Antofagasta (Xplora Minerals)

## Contenido del repositorio

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — arquitectura completa del sistema, estructura de carpetas y diagrama de flujo end-to-end
- [`scripts/`](./scripts) — pipeline de entrenamiento y despliegue (data → train → eval → export → deploy → orquestador)
- [`backend/`](./backend) — API local (FastAPI + SQLite) para el Panel de Detecciones, con autenticación por roles
- [`frontend/`](./frontend) — Panel de Detecciones (dashboard web 100% local, HTML/CSS/JS sin build step)
- [`integration/`](./integration) — integración de componentes: docker-compose, systemd, nginx y verificación automática de consistencia
- [`docs/`](./docs) — documentación técnica del backend y descriptores de cada script

## Pipeline

| Script | Etapa | Descripción |
|---|---|---|
| `00_prepare_dataset.py` | DATA | Preparación y validación del dataset (split 80/20 estratificado) |
| `01_train.py` | TRAIN | Entrenamiento YOLOv8s (150 épocas) |
| `02_evaluate.py` | EVAL | Métricas por clase + benchmark de FPS + gate `--strict` |
| `03_export.py` | EXPORT | Exportación a TensorRT FP16 + ONNX + model card |
| `04_deploy_inference.py` | DEPLOY | Motor de inferencia en Jetson Orin (RTSP → SQLite → alertas) |
| `05_run_pipeline.py` | ORQUESTADOR | Pipeline completo end-to-end |

Ver [`ARCHITECTURE.md`](./ARCHITECTURE.md) para el diagrama de flujo completo y el detalle de cada módulo.
