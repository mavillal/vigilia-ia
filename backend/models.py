"""
models.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Esquemas Pydantic para request/response de la API. Reflejan directamente
las columnas de las tablas `eventos` y `usuarios` (ver database.py).
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

Rol = Literal["operador", "supervisor", "gerencia"]
Clase = Literal["mineral_normal", "roca_oversize", "metal_grande"]
Accion = Literal["log", "alerta"]


class Evento(BaseModel):
    id: int
    frame_id: int
    clase: Clase
    confianza: float
    nivel_riesgo: str
    accion: Accion
    timestamp: str
    bbox_cx: Optional[float] = None
    bbox_cy: Optional[float] = None
    bbox_w: Optional[float] = None
    bbox_h: Optional[float] = None


class ResumenClase(BaseModel):
    clase: Clase
    total: int


class ResumenDiario(BaseModel):
    detecciones_hoy: int
    inchancables_detectados: int
    ultima_alerta: Optional[Evento] = None
    por_clase: list[ResumenClase]


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: Rol


class UsuarioCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)
    rol: Rol


class UsuarioOut(BaseModel):
    id: int
    username: str
    rol: Rol
    activo: bool
