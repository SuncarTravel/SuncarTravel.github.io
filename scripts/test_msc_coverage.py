#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "assets" / "msc-assistant-data.json").read_text(encoding="utf-8"))

def expanded():
    by_key = {}
    for d in DATA.get("departures", []):
        by_key[(d["ship"], d["start"])] = dict(d)
    for s in DATA.get("series", []):
        for start in s.get("dates", []):
            key = (s["ship"], start)
            if key not in by_key:
                by_key[key] = {
                    "id": f"{s['id']}-{start}",
                    "ship": s["ship"],
                    "start": start,
                    "region": s["region"],
                    "port": s["port"],
                    "route": s.get("route", ""),
                    "nights": s.get("nights"),
                }
    return list(by_key.values())

DEPS = expanded()

def find(region=None, year=None, month=None, ship=None, port_contains=None, route_contains=None):
    out = DEPS
    if region:
        out = [d for d in out if d.get("region") == region]
    if year:
        out = [d for d in out if d.get("start", "").startswith(str(year) + "-")]
    if month:
        out = [d for d in out if d.get("start", "")[5:7] == f"{month:02d}"]
    if ship:
        out = [d for d in out if d.get("ship") == ship]
    if port_contains:
        out = [d for d in out if port_contains.lower() in d.get("port", "").lower()]
    if route_contains:
        out = [d for d in out if route_contains.lower() in d.get("route", "").lower()]
    return out

checks = [
    ("World America Miami dic-2026", find(year=2026, month=12, ship="MSC World America", port_contains="Miami")),
    ("Noruega dic-2026", find(region="Norte de Europa", year=2026, month=12)),
    ("Opera La Romana sep-2027", find(year=2027, month=9, ship="MSC Opera", port_contains="La Romana")),
    ("Alaska may-2027", find(region="Alaska", year=2027, month=5)),
    ("Asia sep-2027", find(region="Asia", year=2027, month=9)),
    ("Canarias dic-2026", find(region="Canarias y Madeira", year=2026, month=12)),
    ("Sudáfrica dic-2026", find(region="Sudáfrica", year=2026, month=12)),
    ("Mediterráneo jun-2027", find(region="Mediterráneo", year=2027, month=6)),
    ("Cozumel nov-2026", find(year=2026, month=11, route_contains="Cozumel")),
]

failed = False
for label, results in checks:
    if not results:
        print(f"FAIL: {label}: sin resultados")
        failed = True
    else:
        print(f"OK: {label}: {len(results)} resultado(s)")

fleet = DATA.get("fleet", [])
if len(fleet) < 25:
    print(f"FAIL: fleet incompleta ({len(fleet)})")
    failed = True
else:
    print(f"OK: fleet {len(fleet)} barcos")

if len(DATA.get("knowledge", [])) < 25:
    print("FAIL: base de conocimiento demasiado corta")
    failed = True
else:
    print(f"OK: knowledge {len(DATA.get('knowledge', []))} bloques")

if failed:
    raise SystemExit(1)

print(f"TOTAL salidas únicas cargadas/derivadas: {len(DEPS)}")
print("Cobertura MSC crítica: OK")
