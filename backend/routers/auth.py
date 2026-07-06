"""
routers/auth.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Endpoint de autenticación. Corresponde a la pantalla de login con control
de acceso documentada como evidencia del hito 3.2 (Anexo A, Figura A.4).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from database import get_db
from models import LoginRequest, Token
from security import create_access_token, register_login, verify_password
import crud

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, conn=Depends(get_db)):
    usuario = crud.get_usuario_by_username(conn, payload.username)
    if usuario is None or not verify_password(payload.password, usuario["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    crud.register_login(conn, usuario["id"])
    token = create_access_token(username=usuario["username"], rol=usuario["rol"])
    return Token(access_token=token, rol=usuario["rol"])
