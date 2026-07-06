"""
database.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Inicialización y acceso a la base de datos SQLite local. Corresponde al
Diagrama ER documentado en el Informe de Desarrollo de Producto (Figura 1):
tablas `eventos`, `usuarios` y `sesiones`.

La tabla `eventos` es poblada por el motor de inferencia
(scripts/04_deploy_inference.py); este backend la consume en modo lectura
para los endpoints de detecciones/alertas/resumen, y gestiona en escritura
las tablas `usuarios` y `sesiones` para el control de acceso por roles.
"""

import sqlite3
from pathlib import Path

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    frame_id INTEGER NOT NULL,
    clase TEXT NOT NULL,
    confianza REAL NOT NULL,
    nivel_riesgo TEXT NOT NULL,
    accion TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    bbox_cx REAL,
    bbox_cy REAL,
    bbox_w REAL,
    bbox_h REAL
);

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    rol TEXT NOT NULL CHECK (rol IN ('operador', 'supervisor', 'gerencia')),
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sesiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    timestamp_login TEXT NOT NULL,
    timestamp_logout TEXT,
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
);

CREATE INDEX IF NOT EXISTS idx_eventos_timestamp ON eventos (timestamp);
CREATE INDEX IF NOT EXISTS idx_eventos_clase ON eventos (clase);
CREATE INDEX IF NOT EXISTS idx_eventos_accion ON eventos (accion);
"""


def init_db(db_path: str = DB_PATH) -> None:
    """Crea el archivo de base de datos y el esquema si no existen. Idempotente."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Retorna una conexión con row_factory configurado para acceso tipo dict."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """Dependencia FastAPI: entrega una conexión por request y la cierra al final."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
