"""
main.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Punto de entrada del backend. API local (sin salida a internet) que corre
en el mismo nodo Jetson Orin que el motor de inferencia
(scripts/04_deploy_inference.py), y alimenta al Panel de Detecciones.

Uso:
  uvicorn main:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import API_TITLE, API_VERSION
from database import init_db
from routers import alertas, auth, detecciones, resumen

app = FastAPI(title=API_TITLE, version=API_VERSION)

# CORS restringido a la red local del nodo edge (ajustar según despliegue en terreno)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "proyecto": "VIGIL-IA", "modo": "100% local"}


app.include_router(auth.router)
app.include_router(detecciones.router)
app.include_router(alertas.router)
app.include_router(resumen.router)
