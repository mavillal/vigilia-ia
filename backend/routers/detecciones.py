"""
routers/detecciones.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Endpoint de detecciones: alimenta la tabla de eventos con badges de estado
del Panel de Detecciones (Anexo A, Figura A.3). Acceso mínimo: operador.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from database import get_db
from models import Evento
from security import require_role
import crud

router = APIRouter(prefix="/detecciones", tags=["detecciones"])


@router.get("", response_model=list[Evento])
def get_detecciones(
    limit: int = Query(50, ge=1, le=500),
    clase: Optional[str] = Query(None, description="Filtrar por clase: mineral_normal | roca_oversize | metal_grande"),
    conn=Depends(get_db),
    user: dict = Depends(require_role("operador")),
):
    return crud.list_detecciones(conn, limit=limit, clase=clase)
