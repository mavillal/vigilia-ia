"""
config.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Configuración central del backend. Todo el servicio corre 100% local en el
nodo Jetson Orin, sin dependencia de internet ni de un proveedor de secretos
en la nube: el secreto JWT se lee de una variable de entorno con un default
solo apto para desarrollo local.
"""

import os

# Base de datos SQLite local (misma BD que puebla 04_deploy_inference.py)
DB_PATH = os.environ.get("VIGILIA_DB_PATH", "./data/vigilia_events.db")

# JWT — en producción, definir VIGILIA_JWT_SECRET como variable de entorno
# en el propio Jetson Orin (no se transmite ni se almacena en la nube).
JWT_SECRET = os.environ.get("VIGILIA_JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.environ.get("VIGILIA_JWT_EXPIRE_MIN", "480"))  # turno de 8h

API_TITLE = "VIGIL-IA Backend API"
API_VERSION = "25INI-282394"
