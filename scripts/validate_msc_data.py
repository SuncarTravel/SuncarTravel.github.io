#!/usr/bin/env python3
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "assets" / "msc-assistant-data.json"

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
fleet = data.get("fleet", [])

unique(knowledge, "id", "knowledge")
unique(departures, "id", "departures")
unique(fleet, "name", "fleet")

iso = re.compile(r"^\d{4}-\d{2}-\d{2}$")

for d in departures:
    for field in ("ship", "region", "port", "start"):
        need(bool(d.get(field)), f"{d.get('id','?')}: falta {field}")
    start = d.get("start")
    if start:
        need(bool(iso.match(start)), f"{d.get('id','?')}: start no es YYYY-MM-DD")
    end = d.get("end")
    if end:
        need(bool(iso.match(end)), f"{d.get('id','?')}: end no es YYYY-MM-DD")
        if iso.match(start or "") and iso.match(end):
            try:
                need(date.fromisoformat(end) >= date.fromisoformat(start), f"{d.get('id','?')}: end anterior a start")
            except ValueError:
                errors.append(f"{d.get('id','?')}: fecha inválida")
    internal = d.get("internalUrl")
    if internal:
        need(not internal.startswith(("http://","https://","//")), f"{d.get('id','?')}: internalUrl no puede salir de Suncar")
    for forbidden in ("bookingUrl","externalUrl","bookNowUrl"):
        need(forbidden not in d, f"{d.get('id','?')}: campo externo prohibido {forbidden}")

for k in knowledge:
    need(bool(k.get("answer")), f"{k.get('id','?')}: falta answer")
    need(isinstance(k.get("keywords"), list) and len(k.get("keywords")) > 0, f"{k.get('id','?')}: keywords vacíos")

for s in fleet:
    need(bool(s.get("class")), f"{s.get('name','?')}: falta class")

if errors:
    print("Validación MSC: FALLÓ")
    for e in errors:
        print("-", e)
    sys.exit(1)

print("Validación MSC: OK")
print(f"Version: {data.get('version')}")
print(f"Barcos: {len(fleet)}")
print(f"Salidas: {len(departures)}")
print(f"Conocimiento: {len(knowledge)}")
