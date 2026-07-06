"""
crud.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Consultas a SQLite para eventos (lectura, poblados por el motor de
inferencia) y usuarios (gestión de acceso). Sin ORM: consultas SQL directas,
consistente con el resto del pipeline (ver 04_deploy_inference.py).
"""

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from constants import CLASS_MAP


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row) if row is not None else None


def list_detecciones(conn: sqlite3.Connection, limit: int = 50, clase: Optional[str] = None) -> list[dict]:
    if clase:
        cur = conn.execute(
            "SELECT * FROM eventos WHERE clase = ? ORDER BY id DESC LIMIT ?",
            (clase, limit),
        )
    else:
        cur = conn.execute("SELECT * FROM eventos ORDER BY id DESC LIMIT ?", (limit,))
    return [row_to_dict(r) for r in cur.fetchall()]


def list_alertas(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    """Eventos cuya acción es 'alerta' (roca_oversize, metal_grande) — Anexo B."""
    cur = conn.execute(
        "SELECT * FROM eventos WHERE accion = 'alerta' ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return [row_to_dict(r) for r in cur.fetchall()]


def get_resumen(conn: sqlite3.Connection) -> dict:
    """Indicadores de resumen diario: detecciones de hoy, inchancables, última alerta, por clase."""
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    cur = conn.execute("SELECT COUNT(*) AS n FROM eventos WHERE timestamp LIKE ?", (f"{hoy}%",))
    detecciones_hoy = cur.fetchone()["n"]

    cur = conn.execute(
        "SELECT COUNT(*) AS n FROM eventos WHERE clase = 'metal_grande' AND timestamp LIKE ?",
        (f"{hoy}%",),
    )
    inchancables_detectados = cur.fetchone()["n"]

    cur = conn.execute("SELECT * FROM eventos WHERE accion = 'alerta' ORDER BY id DESC LIMIT 1")
    ultima_alerta = row_to_dict(cur.fetchone())

    por_clase = []
    for class_name in CLASS_MAP.values():
        cur = conn.execute("SELECT COUNT(*) AS n FROM eventos WHERE clase = ?", (class_name,))
        por_clase.append({"clase": class_name, "total": cur.fetchone()["n"]})

    return {
        "detecciones_hoy": detecciones_hoy,
        "inchancables_detectados": inchancables_detectados,
        "ultima_alerta": ultima_alerta,
        "por_clase": por_clase,
    }


def get_usuario_by_username(conn: sqlite3.Connection, username: str) -> Optional[dict]:
    cur = conn.execute("SELECT * FROM usuarios WHERE username = ? AND activo = 1", (username,))
    return row_to_dict(cur.fetchone())


def create_usuario(conn: sqlite3.Connection, username: str, password_hash: str, rol: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO usuarios (username, password_hash, rol, activo, creado_en) VALUES (?, ?, ?, 1, ?)",
        (username, password_hash, rol, now),
    )
    conn.commit()
    return {"id": cur.lastrowid, "username": username, "rol": rol, "activo": True}


def register_login(conn: sqlite3.Connection, usuario_id: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO sesiones (usuario_id, timestamp_login) VALUES (?, ?)",
        (usuario_id, now),
    )
    conn.commit()
