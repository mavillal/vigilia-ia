# Fuentes de marca — auto-alojadas

Este directorio debe contener, antes del despliegue en Jetson Orin, los archivos:

- `BarlowCondensed-SemiBold.woff2`
- `DMSans-Regular.woff2`
- `IBMPlexMono-Regular.woff2`

Se referencian vía `@font-face` en `css/tokens.css`. **No usar Google Fonts ni ningún CDN**: el nodo edge opera sin conectividad a internet en terreno (Copper Phoenix I), por lo que las fuentes deben empaquetarse localmente junto al resto de los archivos del dashboard.

Mientras estos archivos no estén presentes, la interfaz usa automáticamente las pilas de fallback definidas en `tokens.css` (Oswald/Arial Narrow, system-ui, Menlo/Consolas), por lo que el dashboard sigue siendo completamente funcional sin ellas.
