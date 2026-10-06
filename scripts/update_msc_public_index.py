#!/usr/bin/env python3
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "msc-public-index.json"

SOURCE_PAGE = "https://www.msccruisesusa.com/deals/cruise-from-199-plus-onboard-credit/all-itineraries?sort=relevance"
SEARCH_PATH = "/api-search/1/indexes/*/queries"
BASE_FILTER = "(noofAdults=2) AND (noofMinors=0) AND (noofJuniors=0) AND (prices.availability: true)"

AREA_MAP = {
    "CAR": "Caribe",
    "SOC": "Caribe",
    "MED": "Mediterráneo",
    "NOR": "Norte de Europa",
    "SOA": "Sudamérica",
    "POS": "MSC Grand Voyages",
    "WEE": "Canarias y Madeira",
    "FAE": "Asia",
    "ALA": "Alaska",
    "INW": "Sudáfrica",
    "PAN": "Canal de Panamá",
    "WOR": "Vuelta al Mundo",
}

def iso_end(start, nights):
    try:
        d = datetime.strptime(start, "%Y-%m-%d").date() + timedelta(days=int(nights or 0))
        return d.isoformat()
    except Exception:
        return None

def region_for(hit):
    keys = [x.get("key") for x in (hit.get("commArea") or []) if x.get("key")]
    itinerary = (hit.get("itineraryName") or "").lower()
    for key in keys:
        if key in ("CAR", "SOC"):
            if "bahamas" in itinerary and "caribbean" not in itinerary:
                return "Bahamas"
            return "Caribe"
        if key in AREA_MAP:
            return AREA_MAP[key]
    canvas = hit.get("canvasMap") or {}
    if "CAR-SOC-NCA-BHM" in canvas:
        if "bahamas" in itinerary and "caribbean" not in itinerary:
            return "Bahamas"
        return "Caribe"
    for key, value in AREA_MAP.items():
        if key in canvas:
            return value
    return "Otros MSC"

def clean_stop(value):
    if not value:
        return None
    if value == "Day at Sea":
        return "Navegación"
    if value == "Cruising Panama Canal":
        return "Tránsito Canal de Panamá"
    return value

def transform(hit, refreshed):
    ship = (hit.get("shipCd") or {}).get("value")
    start = hit.get("departureStartDate")
    embark = (hit.get("embkPort") or {}).get("value")
    disembark = (hit.get("disembkPort") or {}).get("value")
    nights = hit.get("numberOfNights")
    visiting = [clean_stop(x.get("value")) for x in (hit.get("visitingPorts") or [])]
    visiting = [x for x in visiting if x]
    route_parts = [embark] if embark else []
    route_parts.extend(visiting)
    if disembark:
        route_parts.append(disembark)

    prices = hit.get("prices") or {}
    price_after = hit.get("pricesAfterDiscount") or {}
    adult_price = prices.get("adultPrice")
    cabin_price = prices.get("cabinPrice")
    if adult_price is None:
        adult_price = price_after.get("adultPrice")
    if cabin_price is None:
        cabin_price = price_after.get("cabinPrice")

    price_note = "Precio a confirmar con Suncar"
    if isinstance(adult_price, (int, float)) and adult_price > 0:
        amount = f"{adult_price:,.0f}" if float(adult_price).is_integer() else f"{adult_price:,.2f}"
        price_note = (
            "Desde US$" + amount + " por persona como referencia pública; "
            "tasas e impuestos incluidos en el precio mostrado. "
            "Suncar confirma tarifa y disponibilidad."
        )

    updated_on = hit.get("updatedOn")
    source_updated = None
    if isinstance(updated_on, (int, float)):
        try:
            source_updated = datetime.fromtimestamp(updated_on / 1000, tz=timezone.utc).isoformat()
        except Exception:
            pass

    return {
        "id": hit.get("cruiseID"),
        "cruiseID": hit.get("cruiseID"),
        "sourceType": "OfficialPublicIndex",
        "sourceMarket": "USA",
        "region": region_for(hit),
        "ship": ship,
        "shipCode": (hit.get("shipCd") or {}).get("key"),
        "port": embark,
        "disembark": disembark,
        "start": start,
        "end": iso_end(start, nights),
        "nights": nights,
        "itineraryName": hit.get("itineraryName"),
        "itineraryCode": hit.get("itinCd"),
        "route": " → ".join(route_parts),
        "stops": visiting,
        "priceFrom": adult_price,
        "cabinPriceFrom": cabin_price,
        "currency": "USD",
        "priceCategory": (hit.get("category") or {}).get("value"),
        "publicPriceNote": price_note,
        "priceIncludesFeesTaxes": True,
        "sourceUpdatedAt": source_updated,
        "refreshedAt": refreshed,
    }

def main():
    refreshed = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1200},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        captured = []

        def on_request(req):
            if SEARCH_PATH in req.url and not captured:
                captured.append({"url": req.url, "headers": dict(req.headers)})

        page.on("request", on_request)
        response = page.goto(SOURCE_PAGE, wait_until="domcontentloaded", timeout=90000)
        if not response or response.status != 200:
            raise RuntimeError(f"No se pudo abrir el índice público MSC: {getattr(response, 'status', None)}")
        page.wait_for_timeout(7000)
        if not captured:
            raise RuntimeError("No se detectó la consulta pública de itinerarios MSC")

        search_url = captured[0]["url"]
        headers = {
            k: v
            for k, v in captured[0]["headers"].items()
            if k.lower() not in ("content-length", "host", "cookie")
        }

        def query(filters, page_no=0, hits=1000, facets=None):
            payload = {
                "requests": [
                    {
                        "indexName": "prod-en-us-cruises",
                        "filters": filters,
                        "hitsPerPage": hits,
                        "page": page_no,
                        "distinct": 1,
                        "attributesToHighlight": [""],
                        "facets": facets or [],
                        "getRankingInfo": False,
                        "clickAnalytics": False,
                        "query": "",
                    }
                ]
            }
            rr = context.request.post(
                search_url,
                headers=headers,
                data=json.dumps(payload),
                timeout=90000,
            )
            if rr.status != 200:
                raise RuntimeError(f"Consulta MSC falló ({rr.status}): {rr.text()[:500]}")
            return rr.json()["results"][0]

        discovery = query(BASE_FILTER, page_no=0, hits=1, facets=["shipCd.key"])
        ship_codes = sorted((discovery.get("facets") or {}).get("shipCd.key", {}).keys())
        if not ship_codes:
            raise RuntimeError("El índice MSC no devolvió barcos")

        hits_by_cruise = {}
        ship_stats = {}
        for code in ship_codes:
            filters = BASE_FILTER + f' AND (shipCd.key:"{code}")'
            first = query(filters, page_no=0, hits=1000)
            nb_hits = int(first.get("nbHits") or 0)
            nb_pages = int(first.get("nbPages") or 1)
            pages = [first]
            for page_no in range(1, nb_pages):
                pages.append(query(filters, page_no=page_no, hits=1000))
            count = 0
            ship_name = None
            for result in pages:
                for hit in result.get("hits") or []:
                    cruise_id = hit.get("cruiseID")
                    if not cruise_id:
                        continue
                    start = hit.get("departureStartDate")
                    if not start or start < today:
                        continue
                    ship_name = ship_name or (hit.get("shipCd") or {}).get("value")
                    if cruise_id not in hits_by_cruise:
                        hits_by_cruise[cruise_id] = hit
                        count += 1
            ship_stats[ship_name or code] = {
                "shipCode": code,
                "reportedHits": nb_hits,
                "indexedFutureDepartures": count,
            }
            print(f"{code}: {ship_name or '?'} -> {count} salidas")

        browser.close()

    departures = [transform(hit, refreshed) for hit in hits_by_cruise.values()]
    departures = [
        d
        for d in departures
        if d.get("ship") and d.get("start") and d.get("region")
    ]
    departures.sort(key=lambda d: (d.get("start") or "", d.get("ship") or "", d.get("port") or ""))

    region_counts = Counter(d["region"] for d in departures)
    ship_counts = Counter(d["ship"] for d in departures)
    price_count = sum(1 for d in departures if isinstance(d.get("priceFrom"), (int, float)) and d["priceFrom"] > 0)

    payload = {
        "version": 1,
        "refreshedAt": refreshed,
        "market": "USA",
        "currency": "USD",
        "salesOwner": "Suncar Tours & Travel",
        "disclaimer": (
            "Índice informativo construido con datos públicos de MSC. "
            "Los precios son referencias y pueden cambiar. "
            "Disponibilidad, tarifa final, condiciones, reserva y pago "
            "se confirman exclusivamente con Suncar Tours & Travel."
        ),
        "stats": {
            "departures": len(departures),
            "withPublicPrice": price_count,
            "ships": len(ship_counts),
            "regions": dict(sorted(region_counts.items())),
            "byShip": dict(sorted(ship_counts.items())),
            "firstDeparture": departures[0]["start"] if departures else None,
            "lastDeparture": departures[-1]["start"] if departures else None,
        },
        "departures": departures,
    }

    if len(departures) < 1000:
        raise RuntimeError(f"Índice sospechosamente pequeño: {len(departures)} salidas")
    if len(ship_counts) < 20:
        raise RuntimeError(f"Índice sospechosamente incompleto: {len(ship_counts)} barcos")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["stats"], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
