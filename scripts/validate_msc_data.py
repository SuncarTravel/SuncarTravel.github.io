#!/usr/bin/env python3
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets" / "msc-assistant-data.json"
INDEX = ROOT / "index.html"

errors = []

try:
    data = json.loads(DATA.read_text(encoding="utf-8"))
except Exception as exc:
    print(f"ERROR: no se pudo leer JSON: {exc}")
    sys.exit(1)

def need(cond, msg):
    if not cond:
        errors.append(msg)

need(data.get("salesOwner") == "Suncar Tours & Travel", "salesOwner debe ser Suncar Tours & Travel")
need(data.get("whatsapp") == "18093161070", "WhatsApp debe apuntar a Suncar")
need(data.get("policy", {}).get("externalBooking") is False, "externalBooking debe permanecer en false")

def unique(items, key, label):
    seen = set()
    for item in items:
        value = item.get(key)
        need(bool(value), f"{label}: falta {key}")
        if value:
            need(value not in seen, f"{label}: duplicado {key}={value}")
            seen.add(value)

knowledge = data.get("knowledge", [])
departures = data.get("departures", [])
series = data.get("series", [])
fleet = data.get("fleet", [])
regions = set(data.get("regions", []))

unique(knowledge, "id", "knowledge")
unique(departures, "id", "departures")
unique(series, "id", "series")
unique(fleet, "name", "fleet")

fleet_names = {s.get("name") for s in fleet if s.get("name")}
iso = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def check_common(item, label, require_start=False):
    for field in ("ship", "region", "port"):
        need(bool(item.get(field)), f"{label}: falta {field}")
    need(item.get("ship") in fleet_names, f"{label}: barco no existe en fleet: {item.get('ship')}")
    need(item.get("region") in regions, f"{label}: región no declarada: {item.get('region')}")
    if require_start:
        need(bool(item.get("start")), f"{label}: falta start")
    internal = item.get("internalUrl")
    if internal:
        need(not internal.startswith(("http://", "https://", "//")), f"{label}: internalUrl no puede salir de Suncar")
    for forbidden in ("bookingUrl", "externalUrl", "bookNowUrl", "sourceUrl"):
        need(forbidden not in item, f"{label}: campo externo prohibido {forbidden}")

for d in departures:
    label = d.get("id", "?")
    check_common(d, label, require_start=True)
    start = d.get("start")
    if start:
        need(bool(iso.match(start)), f"{label}: start no es YYYY-MM-DD")
    end = d.get("end")
    if end:
        need(bool(iso.match(end)), f"{label}: end no es YYYY-MM-DD")
        if iso.match(start or "") and iso.match(end):
            try:
                need(date.fromisoformat(end) >= date.fromisoformat(start), f"{label}: end anterior a start")
            except ValueError:
                errors.append(f"{label}: fecha inválida")

for s in series:
    label = s.get("id", "?")
    check_common(s, label)
    need(isinstance(s.get("dates"), list) and len(s.get("dates")) > 0, f"{label}: dates vacío")
    need(isinstance(s.get("nights"), int) and s.get("nights") > 0, f"{label}: nights inválido")
    need(bool(s.get("route")), f"{label}: falta route")
    seen_dates = set()
    for start in s.get("dates", []):
        need(isinstance(start, str) and bool(iso.match(start)), f"{label}: fecha inválida {start}")
        need(start not in seen_dates, f"{label}: fecha duplicada {start}")
        seen_dates.add(start)
        if isinstance(start, str) and iso.match(start):
            try:
                date.fromisoformat(start)
            except ValueError:
                errors.append(f"{label}: fecha imposible {start}")

for k in knowledge:
    need(bool(k.get("answer")), f"{k.get('id','?')}: falta answer")
    need(isinstance(k.get("keywords"), list) and len(k.get("keywords")) > 0, f"{k.get('id','?')}: keywords vacíos")

for s in fleet:
    need(bool(s.get("class")), f"{s.get('name','?')}: falta class")

# Validación del front-end del Asistente MSC
try:
    index_html = INDEX.read_text(encoding="utf-8")
    need("returnavailableDepartures" not in index_html, "index: typo returnavailableDepartures detectado")
    start = index_html.find("const allDepartures=()=>")
    end = index_html.find("const availableDepartures=()=>")
    if start >= 0 and end > start:
        all_departures_src = index_html[start:end]
        need("availableDepartures()" not in all_departures_src, "index: recursión allDepartures -> availableDepartures")
    else:
        errors.append("index: funciones de expansión de salidas no encontradas")
    for match in re.findall(r"https://wa\.me/(\d+)", index_html):
        need(match == "18093161070", f"index: WhatsApp externo/no autorizado {match}")
    need("msccruisesusa.com" not in index_html.lower(), "index: contiene enlace directo a MSC USA")
    need("msccruceros.com" not in index_html.lower(), "index: contiene enlace directo a MSC LATAM/México")
    need("bookingUrl" not in index_html, "index: contiene bookingUrl externo")
except Exception as exc:
    errors.append(f"index: no se pudo validar: {exc}")

# Evita dos registros exactos del mismo barco y fecha entre departures explícitas.
seen_ship_dates = set()
for d in departures:
    key = (d.get("ship"), d.get("start"))
    need(key not in seen_ship_dates, f"departures: duplicado barco/fecha {key}")
    seen_ship_dates.add(key)

if errors:
    print("Validación MSC: FALLÓ")
    for e in errors:
        print("-", e)
    sys.exit(1)

series_dates = sum(len(s.get("dates", [])) for s in series)
print("Validación MSC: OK")
print(f"Version: {data.get('version')}")
print(f"Barcos: {len(fleet)}")
print(f"Salidas explícitas: {len(departures)}")
print(f"Series: {len(series)}")
print(f"Fechas en series: {series_dates}")
print(f"Conocimiento: {len(knowledge)}")
