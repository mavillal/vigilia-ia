"""
security.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Hashing de contraseñas, emisión/verificación de JWT y dependencias de
FastAPI para exigir un rol mínimo por endpoint. Implementa el control de
acceso por roles (operador / supervisor / gerencia) documentado en el
hito 3.2 del Informe de Desarrollo de Producto.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET
from constants import ROLES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# Orden de privilegio ascendente: gerencia ve todo lo que ve supervisor,
# supervisor ve todo lo que ve operador.
ROLE_RANK = {"operador": 0, "supervisor": 1, "gerencia": 2}


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(username: str, rol: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": username, "rol": rol, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decode_access_token(token)
    username: Optional[str] = payload.get("sub")
    rol: Optional[str] = payload.get("rol")
    if username is None or rol not in ROLES:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    return {"username": username, "rol": rol}


def require_role(minimo: str):
    """Dependencia parametrizable: exige un rol igual o superior al mínimo indicado."""

    def dependency(user: dict = Depends(get_current_user)) -> dict:
        if ROLE_RANK[user["rol"]] < ROLE_RANK[minimo]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Se requiere rol '{minimo}' o superior",
            )
        return user

    return dependency
