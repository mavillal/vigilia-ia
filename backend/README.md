# VIGIL-IA — Backend

API local (FastAPI + SQLite) para el Panel de Detecciones. Corre 100% en el nodo NVIDIA Jetson Orin, sin dependencia de internet, junto al motor de inferencia (`../scripts/04_deploy_inference.py`).

## Instalación

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuración

Variables de entorno (opcionales, con default apto solo para desarrollo):

| Variable | Descripción | Default |
|---|---|---|
| `VIGILIA_DB_PATH` | Ruta a la base de datos SQLite | `./data/vigilia_events.db` |
| `VIGILIA_JWT_SECRET` | Secreto para firmar tokens JWT | `dev-secret-change-me` (**cambiar en producción**) |
| `VIGILIA_JWT_EXPIRE_MIN` | Expiración del token en minutos | `480` (un turno de 8h) |

## Primer uso: crear usuario de gerencia

```bash
python seed_admin.py --username admin --password "clave-segura-de-produccion" --rol gerencia
```

## Ejecutar

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Endpoints

| Endpoint | Método | Rol mínimo | Descripción |
|---|---|---|---|
| `/health` | GET | — | Estado del servicio |
| `/auth/login` | POST | — | Autenticación, retorna JWT |
| `/detecciones` | GET | operador | Listado de eventos de detección |
| `/alertas` | GET | operador | Eventos con acción='alerta' |
| `/resumen` | GET | supervisor | Indicadores agregados diarios |

Los roles siguen un orden ascendente de privilegio: `gerencia` > `supervisor` > `operador`.

## Notas de consistencia

- Las clases, umbrales de confianza y matriz de riesgo/acción (`constants.py`) deben mantenerse en sincronía con `../scripts/04_deploy_inference.py` y los Anexos B y C del proyecto.
- La tabla `eventos` es poblada por el motor de inferencia; este backend la consume en modo lectura.
- Ver `../docs/VIGIL-IA_Documentacion_Backend.md` para el detalle funcional completo (hito 3.2).
