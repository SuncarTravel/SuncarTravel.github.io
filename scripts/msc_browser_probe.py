#!/usr/bin/env python3
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL="https://www.msccruisesusa.com/deals/cruise-from-199-plus-onboard-credit/all-itineraries?sort=relevance"
out={}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(
        viewport={"width":1440,"height":1200},
        locale="en-US",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    )
    resp=page.goto(URL,wait_until="domcontentloaded",timeout=90000)
    out["status"]=resp.status if resp else None
    page.wait_for_timeout(7000)

    payload={
      "requests":[{
        "indexName":"prod-en-us-cruises",
        "filters":"(noofAdults=2) AND (noofMinors=0) AND (noofJuniors=0) AND (prices.availability: true)",
        "hitsPerPage":1000,
        "page":0,
        "distinct":1,
        "attributesToHighlight":[""],
        "facets":["*"],
        "getRankingInfo":False,
        "clickAnalytics":False,
        "query":""
      }]
    }
    result=page.evaluate("""async (payload)=>{
      const r=await fetch('/api-search/1/indexes/*/queries',{
        method:'POST',
        headers:{'content-type':'application/json'},
        body:JSON.stringify(payload)
      });
      const text=await r.text();
      return {status:r.status,text};
    }""",payload)
    out["query_status"]=result["status"]
    data=json.loads(result["text"]) if result["status"]==200 else {}
    res=(data.get("results") or [{}])[0]
    hits=res.get("hits") or []
    out["nbHits"]=res.get("nbHits")
    out["nbPages"]=res.get("nbPages")
    out["hitsPerPage"]=res.get("hitsPerPage")
    out["page"]=res.get("page")
    out["returnedHits"]=len(hits)
    out["uniqueCruiseIDs"]=len({h.get("cruiseID") for h in hits if h.get("cruiseID")})
    out["ships"]=sorted({(h.get("shipCd") or {}).get("value") for h in hits if (h.get("shipCd") or {}).get("value")})
    out["dates"]=[min([h.get("departureStartDate") for h in hits if h.get("departureStartDate")],default=None),max([h.get("departureStartDate") for h in hits if h.get("departureStartDate")],default=None)]
    out["facet_keys"]=sorted((res.get("facets") or {}).keys())
    out["sample"]=[{
      "cruiseID":h.get("cruiseID"),
      "date":h.get("departureStartDate"),
      "ship":(h.get("shipCd") or {}).get("value"),
      "embark":(h.get("embkPort") or {}).get("value"),
      "disembark":(h.get("disembkPort") or {}).get("value"),
      "nights":h.get("numberOfNights"),
      "itinerary":h.get("itineraryName"),
      "area":h.get("canvasMap"),
      "commArea":h.get("commArea"),
      "visiting":h.get("visitingPorts"),
      "adultPrice":(h.get("prices") or {}).get("adultPrice"),
      "cabinPrice":(h.get("prices") or {}).get("cabinPrice"),
      "category":(h.get("category") or {}).get("value"),
      "marketCd":h.get("marketCd"),
      "totalAvailable":h.get("totalAvailable"),
      "itinCd":h.get("itinCd")
    } for h in hits[:20]]

    Path("msc-browser-probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))
    browser.close()

if out.get("status") not in (200,304): sys.exit(2)
if out.get("query_status")!=200: sys.exit(3)
if not out.get("returnedHits"): sys.exit(4)
