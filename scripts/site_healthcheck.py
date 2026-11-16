#!/usr/bin/env python3
"""Auditoría pública, de solo lectura, para GitHub Actions de Suncar Travel.

Comprueba HTTPS y certificado mediante TLS verificado, redirecciones,
DNS-over-HTTPS en dos resolutores, páginas, archivos JS, Analytics,
WhatsApp, formularios presentes y promociones vencidas en HTML.
No efectúa reservas, compras ni envíos de formularios.
"""
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import unquote
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE = "https://www.suncartravel.com/"
TZ = ZoneInfo("America/Santo_Domingo")
PHONE = "18093161070"
PAGES = [
    "", "ofertas.html", "msc-opera.html", "hoteles.html",
    "paquetes.html", "vuelos.html", "cruceros.html",
    "seguros-viaje.html", "servicios.html",
    "politica-privacidad.html", "terminos-condiciones.html",
    "cambios-cancelaciones-reembolsos.html",
]
ASSETS = [
    "assets/offers-expiry.js", "assets/analytics.js",
    "assets/msc-assistant-widget.js", "assets/msc-assistant-data.json",
    "assets/msc-public-index.json", "assets/airports-iata.json",
]
REPORT = []


def request(url, accept=None, limit=200000, timeout=14):
    headers = {"User-Agent": "SuncarHealthCheck/1.0 (+public-site-monitor)"}
    if accept:
        headers["Accept"] = accept
    error = None
    for attempt in range(2):
        try:
            with urlopen(Request(url, headers=headers), timeout=timeout) as response:
                status = response.status
                final = response.url
                content = response.read(limit)
            return status, final, content
        except Exception as exc:
            error = exc
            if attempt == 0:
                time.sleep(1.0)
    raise RuntimeError(f"Fallo de consulta a {url}: {error}")


def record(label, fn):
    try:
        detail = fn()
        REPORT.append(("OK", label, detail or ""))
    except Exception as exc:
        REPORT.append(("ERROR", label, str(exc)[:320]))


def check_redirect(url):
    status, final, _ = request(url, limit=2000)
    actual = urlsplit(final)
    if status != 200 or actual.scheme != "https" or actual.netloc.lower() != "www.suncartravel.com" or actual.path not in ("", "/"):
        raise AssertionError(f"Esperado HTTPS en www.suncartravel.com/; recibido HTTP {status}: {final}")
    return f"HTTP {status} → {final}"


def check_dns(provider, url, host):
    status, _, raw = request(url, accept="application/dns-json", limit=40000)
    if status != 200:
        raise AssertionError(f"HTTP {status}")
    data = json.loads(raw)
    if data.get("Status") != 0:
        raise AssertionError(f"DNS Status={data.get('Status')}")
    addrs = [a.get("data") for a in data.get("Answer", [])
             if a.get("type") == 1 and re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", str(a.get("data", "")))]
    if not addrs:
        raise AssertionError(f"Sin registros IPv4 de {host}; respuesta {str(data)[:160]}")
    return f"{provider}: {', '.join(addrs)}"


def current_expiry_problem(html):
    now = datetime.now(TZ)
    found = []
    for match in re.finditer(r"<(?:article|div)\b[^>]*\bdata-(expire|valid-through)=[\"']([^\"']+)[\"'][^>]*>", html, flags=re.I):
        kind, raw = match.group(1).lower(), match.group(2)
        try:
            if kind == "valid-through":
                past = now.date() > date.fromisoformat(raw)
            elif len(raw) == 10:
                past = now.date() >= date.fromisoformat(raw)
            else:
                d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if d.tzinfo is None:
                    d = d.replace(tzinfo=TZ)
                past = now >= d.astimezone(TZ)
        except ValueError:
            raise AssertionError(f"Fecha de oferta inválida: {raw}")
        if past:
            found.append(raw)
    return found


def site_page(path, ga_id):
    status, final, body = request(BASE + path)
    if status != 200 or urlsplit(final).netloc.lower() != "www.suncartravel.com":
        raise AssertionError(f"HTTP {status}, URL final {final}")
    html = body.decode("utf-8", errors="replace")
    if "<html" not in html.lower() or "Suncar" not in html:
        raise AssertionError("No parece contener la página de Suncar")
    ga = set(re.findall(r"gtag/js\?id=(G-[A-Z0-9]+)", html))
    if ga != {ga_id}:
        raise AssertionError(f"GA4 inesperado; configurado={ga_id}, encontrado={sorted(ga)}")
    numbers = set(re.findall(r"wa\.me/(\d{8,15})", html))
    if numbers and numbers != {PHONE}:
        raise AssertionError(f"WhatsApp inconsistente: {sorted(numbers)}")
    overdue = current_expiry_problem(html)
    if overdue:
        raise AssertionError(f"Promociones vencidas en HTML: {', '.join(overdue[:6])}")
    if "data-expire=" in html and "assets/offers-expiry.js" not in html:
        raise AssertionError("Ofertas con fecha, pero falta el script de caducidad")
    if path == "vuelos.html" and 'id="flightSearch"' not in html:
        raise AssertionError("No se encuentra el formulario de vuelos")
    if path == "" and 'id="cruiseQuoteForm"' not in html:
        raise AssertionError("No se encuentra el formulario de cruceros")
    return f"HTTP {status}, GA4 correcto, ofertas y enlaces WhatsApp revisados"


def site_asset(path):
    status, final, body = request(BASE + path, limit=2000)
    if status != 200 or urlsplit(final).netloc.lower() != "www.suncartravel.com" or not body:
        raise AssertionError(f"Recurso no disponible: HTTP {status}, {final}")
    return f"HTTP {status}, {len(body)} bytes leídos"



def check_local_links():
    """Revisa que los href/src relativos existentes apunten a archivos presentes."""
    root = Path(__file__).resolve().parents[1]
    bad = []
    checked = set()
    for file in PAGES:
        source = root / (file or "index.html")
        html = source.read_text(encoding="utf-8")
        for match in re.finditer(r"\b(?:href|src)=[\"']([^\"']+)[\"']", html, flags=re.I):
            raw = match.group(1).strip()
            if not raw or raw.startswith(("#", "//")):
                continue
            parsed = urlsplit(raw)
            if parsed.scheme or parsed.netloc:
                continue
            relative = unquote(parsed.path).lstrip("/")
            if not relative:
                relative = "index.html"
            if (file, relative) in checked:
                continue
            checked.add((file, relative))
            target = (root / relative).resolve()
            if not target.is_relative_to(root) or not target.is_file():
                bad.append(f"{file or 'index.html'} → {relative}")
    if bad:
        raise AssertionError("Enlaces internos que faltan: " + ", ".join(bad[:12]))
    return f"{len(checked)} referencias locales verificadas"


def check_flight_api_health():
    url = "https://suncar-flights-api.suncartravel.workers.dev/health"
    status, _, raw = request(url, accept="application/json", limit=4000)
    if status != 200:
        raise AssertionError(f"API vuelos: HTTP {status}")
    payload = json.loads(raw)
    if payload.get("ok") is not True or payload.get("service") != "Suncar Flights API":
        raise AssertionError(f"API vuelos: respuesta inesperada: {payload}")
    return f"HTTP {status}, servicio responde; no verifica búsquedas tarifarias"


def run():
    config = Path(__file__).resolve().parents[1] / "assets/analytics-config.js"
    text = config.read_text(encoding="utf-8")
    m = re.search(r"window\.SUNCAR_GA4_ID\s*=\s*[\"'](G-[A-Z0-9]+)[\"']", text)
    if not m:
        print("ERROR: falta ID GA4 en configuración local")
        return 1
    ga_id = m.group(1)

    record("Enlaces internos en el repositorio", check_local_links)
    record("Salud del API de vuelos", check_flight_api_health)

    for host in ("www.suncartravel.com", "suncartravel.com"):
        for provider, endpoint in (
            ("Google", "https://dns.google/resolve"),
            ("Cloudflare", "https://cloudflare-dns.com/dns-query"),
        ):
            dns_url = endpoint + "?" + urlencode({"name": host, "type": "A"})
            record(f"DNS {host} / {provider}", lambda p=provider, u=dns_url, h=host: check_dns(p, u, h))

    for url in (BASE, "https://suncartravel.com/", "https://suncartravel.github.io/"):
        record(f"Redirección y HTTPS {url}", lambda u=url: check_redirect(u))

    for path in PAGES:
        record("Página /" + path, lambda p=path: site_page(p, ga_id))

    for path in ASSETS:
        record("Recurso /" + path, lambda p=path: site_asset(p))

    print("# Auditoría pública Suncar Travel")
    print("Fecha (Santo Domingo):", datetime.now(TZ).isoformat(timespec="seconds"))
    print("Comprobación de HTML y recursos; NO equivale a prueba interactiva de cotizadores ni confirma visitas de GA4.")
    failures = 0
    for result, label, detail in REPORT:
        if result != "OK":
            failures += 1
        print(f"- {result}: {label} — {detail}")
    print(f"Resultado: {len(REPORT)-failures}/{len(REPORT)} comprobaciones correctas.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
