# 3.5 Integración de Componentes
### Versión actualizada — Julio 2026 · VIGIL-IA Informe de Desarrollo de Producto · 25INI-282394

**HITO:** Integración funcional end-to-end — flujo cámara → inferencia → alerta → dashboard, con orquestación reproducible entre procesos

Se validó y consolidó el flujo completo de integración: Cámara Axis P1448-LE → Servidor Local (Jetson Orin) → motor de inferencia YOLOv8s → base de datos SQLite → Panel de Detecciones (dashboard web). A diferencia de una integración implícita entre módulos desarrollados de forma independiente, esta etapa incorporó una capa explícita de orquestación (directorio `integration/` del repositorio del proyecto) que define cómo los tres componentes —motor de inferencia, backend y frontend— se despliegan y comunican entre sí como un sistema único.

Como parte de esta integración se identificó y corrigió una inconsistencia entre el motor de inferencia y el backend: el primero exponía una API HTTP propia con nomenclatura de endpoints distinta a la del backend oficial. Se eliminó esa duplicación, dejando al motor de inferencia con una única responsabilidad —inferencia y persistencia en SQLite— y al backend como única fuente de la API REST consumida por el dashboard.

Se implementaron dos rutas de despliegue equivalentes: (a) mediante contenedores Docker (`docker-compose`) para backend y frontend, con un proxy nginx que expone ambos bajo el mismo origen para operar sin necesidad de configuración de CORS; y (b) mediante unidades `systemd` nativas para los tres procesos, pensada para el nodo Jetson Orin cuando se requiere acceso directo a la GPU/TensorRT sin la capa adicional de contenedores.

**Pipeline de integración end-to-end (100% local · sin internet):**

- 01 · Cámara Axis P1448-LE
- 02 · Servidor local: motor de inferencia (YOLOv8s + TensorRT) + BD SQLite
- 03 · Backend: API REST (autenticación por roles, endpoints de detecciones / alertas / resumen)
- 04 · Panel de Detecciones — dashboard para operadores y supervisores

**Resultados obtenidos:**

- Comunicación entre módulos habilitada: cámara → Jetson Orin → YOLOv8s → SQLite → backend → frontend
- Eliminación de la duplicación de API entre el motor de inferencia y el backend
- Dos rutas de despliegue documentadas y disponibles (Docker / systemd nativo)
- Script de verificación automática que compara, sin ejecutar código, las constantes de negocio (clases, umbrales de confianza, matriz de riesgo) entre el motor de inferencia y el backend, para prevenir divergencias futuras

**Evidencias:**

- Diagrama de integración end-to-end — 3 zonas funcionales (Anexo B)
- Repositorio del proyecto, directorio `integration/` (`docker-compose.yml`, `nginx.conf`, `systemd/`, `run_integration_check.py`)
- Salida de ejecución de `integration/run_integration_check.py` confirmando consistencia entre componentes
