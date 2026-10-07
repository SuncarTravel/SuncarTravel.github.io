# Suncar Hotels API — configuración gratuita

Este Worker está preparado para el cotizador mundial de hoteles de Suncar.

## Orden de búsqueda interno

1. Caché de Cloudflare (1 hora)
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

- Las búsquedas idénticas se cachean 1 hora en Cloudflare para equilibrar frescura de precio y ahorro de cuota.
- El detalle de habitación solo se consulta cuando el cliente pulsa “Ver tarifas”.
- SerpApi conserva una pequeña reserva de búsquedas.
- Si una fuente no responde o se acerca a su límite, el Worker pasa a la siguiente.
- Las tarifas propias de Suncar se cargan desde `assets/hotels-suncar-rates.json` y no consumen API.

## URL esperada

https://suncar-hotels-api.suncartravel.workers.dev

La web de prueba usa esa URL desde `assets/hotels-config.js`.


## Reglas de seguridad y exactitud — versión 2026-10-07.2

- La búsqueda automática acepta **1 habitación**. Para 2 o más habitaciones la web deriva a confirmación con Suncar, porque Google Hotels no expone un parámetro de número de habitaciones en este motor.
- Si hay niños, se exige una edad por cada niño y se envía al motor de búsqueda.
- HasData no recibe ocupaciones recortadas: si la ocupación supera sus límites, se omite esa fuente en vez de cambiar silenciosamente el número de huéspedes.
- Los precios por noche y total de estadía se mantienen como campos separados. Si no son razonablemente coherentes entre sí, la interfaz evita mostrar un total dudoso.
- Los regímenes de comida no se deducen por ausencia de datos. Si una tarifa no confirma desayuno, media pensión, pensión completa, todo incluido o solo alojamiento, se marca como **régimen por confirmar**.
- Las fuentes externas nunca se muestran al cliente.
- El endpoint de búsqueda y detalle solo acepta solicitudes web desde los dominios autorizados de Suncar. `/health` permanece público para diagnóstico.
- La interfaz escapa texto externo y valida URLs de imágenes para reducir riesgo de inyección.
- Las tarifas siguen siendo referencias; Suncar confirma disponibilidad, impuestos, régimen, condiciones y precio final antes de reservar.
