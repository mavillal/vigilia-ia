# VIGIL-IA — Panel de Detecciones (Frontend)

Dashboard web 100% local para operadores de pequeña minería, diseñado para interpretación en menos de 3 segundos (hito 3.4, Informe de Desarrollo de Producto). Sin frameworks ni build step: HTML + CSS + JS planos, servibles directamente desde el propio Jetson Orin o cualquier servidor estático local.

## Estructura

```
frontend/
├── index.html          # Login
├── dashboard.html       # Panel de Detecciones (3 columnas: nav / feed / alertas)
├── css/
│   ├── tokens.css       # Paleta de marca, tipografía, escala de espaciado
│   └── styles.css       # Layout y componentes
├── js/
│   ├── api.js           # Cliente del backend (fetch + sesión JWT en sessionStorage)
│   ├── login.js
│   └── dashboard.js
└── assets/fonts/        # Fuentes auto-alojadas (ver README.md de esa carpeta)
```

## Ejecutar localmente

El dashboard consume la API del backend (`../backend`). Con el backend corriendo en `http://localhost:8000`:

```bash
cd frontend
python3 -m http.server 8080
```

Abrir `http://localhost:8080` en el navegador.

Si el backend corre en otra IP del nodo edge, definir antes de cargar los scripts:

```html
<script>window.VIGILIA_API_BASE = "http://192.168.1.50:8000";</script>
```

## Control de acceso por rol

El token JWT recibido en `/auth/login` determina el rol (`operador` / `supervisor` / `gerencia`), guardado en `sessionStorage` (se limpia al cerrar la pestaña). El panel de indicadores agregados (`/resumen`) requiere rol `supervisor` o superior; si el backend responde 403, el dashboard lo indica sin bloquear el resto de la vista.

## Consistencia con el resto del proyecto

- Clases, umbrales y matriz de riesgo/acción replican `../backend/constants.py` y el Anexo B (Figura B.2).
- Paleta y tipografía replican la identidad visual usada en los mockups del hito 3.4 (Negro Vigil `#1A1A18` · Verde IA `#2E7D72` · Beige `#F5F3EE` · Gris `#8A8A82`; Barlow Condensed / DM Sans / IBM Plex Mono).
- **Sin dependencia de internet**: no se usan CDNs (ni de fuentes ni de librerías); ver `assets/fonts/README.md`.
