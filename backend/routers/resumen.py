"""
routers/resumen.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Endpoint de resumen: indicadores agregados diarios (detecciones del día,
inchancables detectados, última alerta crítica) — hito 3.2, resultados
obtenidos. Acceso mínimo: supervisor (indicadores agregados, no solo feed).
"""

from fastapi import APIRouter, Depends

from database import get_db
from models import ResumenDiario
from security import require_role
import crud

router = APIRouter(prefix="/resumen", tags=["resumen"])


@router.get("", response_model=ResumenDiario)
def get_resumen(conn=Depends(get_db), user: dict = Depends(require_role("supervisor"))):
    return crud.get_resumen(conn)
