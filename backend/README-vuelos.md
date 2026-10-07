# Buscador de vuelos Suncar — configuración gratuita

## Arquitectura
- Página: `/prueba/vuelos.html`
- Backend seguro: Cloudflare Worker `backend/flights-worker.js`
- Fuente inicial: SerpApi Google Flights
- Configuración pública del endpoint: `assets/flights-config.js`

## Por qué esta combinación
- Cloudflare Workers Free: 100,000 solicitudes/día.
- SerpApi Free: 250 búsquedas/mes.
- La clave de SerpApi queda como secreto del Worker; nunca se expone en GitHub ni en el navegador.
- El Worker cachea búsquedas iguales durante 30 minutos para cuidar el cupo gratuito.

## Activación
1. Crear cuenta gratuita de SerpApi y copiar la API key.
2. Crear cuenta gratuita de Cloudflare.
3. Crear un Worker llamado `suncar-flights`.
4. Pegar el contenido de `backend/flights-worker.js`.
5. En Settings > Variables and Secrets del Worker, crear un secreto llamado `SERPAPI_KEY`.
6. Desplegar.
7. Copiar la URL del Worker, por ejemplo `https://suncar-flights.<cuenta>.workers.dev`.
8. Colocar esa URL en `assets/flights-config.js`:
   `window.SUNCAR_FLIGHTS_API = "https://...workers.dev";`

## Comportamiento
- El cliente busca dentro de Suncar.
- Se muestran hasta 12 opciones, aerolíneas, vuelos, horarios, escalas, duración y precio estimado.
- No se envía al cliente a Google Flights ni a SerpApi.
- El botón final genera un WhatsApp organizado a Suncar para confirmar y cerrar la venta.
- Si el cupo gratuito se termina o no hay resultados, sigue disponible la solicitud manual por WhatsApp.

## Segundo motor
La estructura del backend permite añadir otro proveedor más adelante. Se deja desactivado de inicio para mantener costo $0.
