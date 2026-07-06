"""
constants.py
VIGIL-IA · CORFO Semilla Inicia 25INI-282394

Constantes de negocio del backend. Deben mantenerse en sincronía con:
  - scripts/04_deploy_inference.py (motor de inferencia que puebla `eventos`)
  - Anexo B, Figura B.2 (matriz clase -> riesgo -> acción)
  - Anexo C, Figura C.3 (umbrales de confianza en producción)
"""

# Clases operacionales VIGIL-IA
CLASS_MAP = {0: "mineral_normal", 1: "roca_oversize", 2: "metal_grande"}

# Matriz de riesgo y acción por clase (Anexo B, Figura B.2)
RISK_LEVEL = {"mineral_normal": "sin_riesgo", "roca_oversize": "riesgo", "metal_grande": "daño"}
ALERT_ACTION = {"mineral_normal": "log", "roca_oversize": "alerta", "metal_grande": "alerta"}

# Umbrales de confianza en producción por clase (Anexo C, Figura C.3)
DEPLOY_CONF_THRESHOLDS = {
    "mineral_normal": 0.50,
    "roca_oversize": 0.40,
    "metal_grande": 0.30,
}

# Roles de usuario y alcance funcional (hito 3.2, Anexo A - Fig. A.4)
ROLES = ("operador", "supervisor", "gerencia")
