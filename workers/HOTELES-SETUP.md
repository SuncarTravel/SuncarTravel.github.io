# Suncar Hotels API — configuración gratuita

Este Worker está preparado para el cotizador mundial de hoteles de Suncar.

## Orden de búsqueda interno

1. Caché de Cloudflare (6 horas)
2. SerpApi Google Hotels
3. HasData Google Hotels
4. StayingAPI opcional como último respaldo de evaluación

Las fuentes nunca se muestran al cliente. La web solo recibe hoteles, tarifas y detalles normalizados.

## Secretos del Worker

Agregar en Cloudflare > Worker > Settings > Variables and Secrets:

- `SERPAPI_KEY`
- `HASDATA_API_KEY`

Opcionales:
- `STAYINGAPI_KEY`
- `STAYINGAPI_ENABLED=true`

No guardar claves en GitHub.

## Cuota gratuita verificada al 7 octubre 2026

- SerpApi: 250 búsquedas/mes en plan Free.
- HasData Google Hotels: 100 búsquedas/mes, renovadas mensualmente, sin tarjeta.
- StayingAPI: créditos gratuitos de evaluación; no se considera parte de la capacidad mensual permanente.

## Protección de cuota

- Las búsquedas idénticas se cachean 6 horas en Cloudflare.
- El detalle de habitación solo se consulta cuando el cliente pulsa “Ver tarifas”.
- SerpApi conserva una pequeña reserva de búsquedas.
- Si una fuente no responde o se acerca a su límite, el Worker pasa a la siguiente.
- Las tarifas propias de Suncar se cargan desde `assets/hotels-suncar-rates.json` y no consumen API.

## URL esperada

https://suncar-hotels-api.suncartravel.workers.dev

La web de prueba usa esa URL desde `assets/hotels-config.js`.
