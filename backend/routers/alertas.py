"""
routers/alertas.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Endpoint de alertas: subconjunto de eventos con accion='alerta'
(roca_oversize, metal_grande), usado por el banner crítico del dashboard.
Acceso mínimo: operador.
"""

from fastapi import APIRouter, Depends, Query

from database import get_db
from models import Evento
from security import require_role
import crud

router = APIRouter(prefix="/alertas", tags=["alertas"])


@router.get("", response_model=list[Evento])
def get_alertas(
    limit: int = Query(50, ge=1, le=500),
    conn=Depends(get_db),
    user: dict = Depends(require_role("operador")),
):
    return crud.list_alertas(conn, limit=limit)
