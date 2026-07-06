# VIGIL-IA — Integración de Componentes

Esta carpeta contiene todo lo necesario para correr los tres componentes del sistema (motor de inferencia, backend, frontend) **integrados como un solo sistema**, en vez de como tres piezas independientes.

## Por qué existe esta capa

Antes de esta integración, el motor de inferencia (`scripts/04_deploy_inference.py`) exponía su propia API embebida con nombres de endpoint distintos (`/eventos`) a los del backend real (`/detecciones`). Esa duplicación se eliminó: **el motor de inferencia ahora solo escribe en SQLite**, y **el backend es la única fuente de la API**. Esta carpeta orquesta ambos procesos junto al frontend, y agrega un chequeo automático que impide que las constantes de negocio (clases, umbrales, matriz de riesgo) vuelvan a divergir entre componentes.

## Arquitectura de integración

```
Cámara Axis P1448-LE (RTSP)
        │
        ▼
scripts/04_deploy_inference.py   (proceso nativo, GPU/TensorRT — systemd)
        │  escribe
        ▼
   data/vigilia_events.db  (SQLite compartida)
        │  lee
        ▼
   backend/main.py   (API — Docker o systemd)
        │  proxy_pass (nginx, mismo origen)
        ▼
   frontend/  (Panel de Detecciones — nginx, mismo origen)
```

## Dos formas de desplegar

### Opción A — Docker (backend + frontend)

```bash
cd integration/
cp .env.example .env   # ajustar VIGILIA_JWT_SECRET antes de producción
docker compose up -d --build
```

Esto levanta `backend` (FastAPI) y `frontend` (nginx sirviendo `../frontend` y haciendo proxy al backend en el mismo origen, ver `nginx.conf`). El motor de inferencia **no** corre en Docker — requiere acceso directo a la GPU/TensorRT del Jetson Orin — y se despliega aparte con la unidad systemd `vigilia-inference.service`.

### Opción B — 100% nativo (sin Docker)

Instalar las tres unidades systemd:

```bash
sudo cp systemd/vigilia-inference.service /etc/systemd/system/
sudo cp systemd/vigilia-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vigilia-backend.service
sudo systemctl enable --now vigilia-inference.service
```

Para el frontend en modo nativo, servirlo con cualquier servidor estático local (ver `../frontend/README.md`) o reutilizar `nginx.conf` con un nginx instalado directamente en el Jetson Orin.

## Verificación de integración

Antes de dar por cerrada la integración (o como chequeo de salud periódico), correr:

```bash
python integration/run_integration_check.py
```

Valida:
1. Que `CLASS_MAP`, `RISK_LEVEL`, `ALERT_ACTION` y los umbrales de confianza sean **idénticos** entre `scripts/04_deploy_inference.py` y `backend/constants.py` (vía AST, sin ejecutar código).
2. Que la base SQLite compartida tenga el esquema esperado en `eventos`.
3. Que el backend responda en `/health`.
4. Que los archivos del frontend estén presentes.

Retorna código de salida distinto de cero si algo falla, por lo que puede integrarse a un pipeline de CI/CD o a un chequeo pre-despliegue.

## Archivos

| Archivo | Propósito |
|---|---|
| `docker-compose.yml` | Orquesta backend + frontend (nginx) |
| `backend.Dockerfile` | Imagen del backend usada por docker-compose |
| `nginx.conf` | Sirve el frontend y hace proxy del backend al mismo origen |
| `.env.example` | Variables compartidas por los tres componentes |
| `systemd/vigilia-inference.service` | Unidad nativa del motor de inferencia |
| `systemd/vigilia-backend.service` | Unidad nativa del backend (alternativa a Docker) |
| `run_integration_check.py` | Verificación automática de consistencia end-to-end |
