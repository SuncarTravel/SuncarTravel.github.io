#!/usr/bin/env python3
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL="https://www.msccruisesusa.com/deals/cruise-from-199-plus-onboard-credit/all-itineraries?sort=relevance"
SEARCH="/api-search/1/indexes/*/queries"
out={"captured":None}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(
        viewport={"width":1440,"height":1200},
        locale="en-US",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    )
    page=context.new_page()
    captured=[]

    def on_request(req):
        if SEARCH in req.url and not captured:
            captured.append({
                "url":req.url,
                "headers":dict(req.headers),
                "post_data":req.post_data,
            })

    page.on("request",on_request)
    resp=page.goto(URL,wait_until="domcontentloaded",timeout=90000)
    out["status"]=resp.status if resp else None
    page.wait_for_timeout(8000)

    if not captured:
        out["error"]="no captured search request"
    else:
        cap=captured[0]
        out["captured"]={
            "url":cap["url"],
            "headers":cap["headers"],
            "post_data":cap["post_data"],
        }
        safe_headers={k:v for k,v in cap["headers"].items() if k.lower() not in ("content-length","host","cookie")}
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
        rr=context.request.post(cap["url"],headers=safe_headers,data=json.dumps(payload),timeout=60000)
        out["query_status"]=rr.status
        out["query_text"]=rr.text()[:2000] if rr.status!=200 else None
        if rr.status==200:
            data=rr.json()
            res=(data.get("results") or [{}])[0]
            hits=res.get("hits") or []
            out.update({
                "nbHits":res.get("nbHits"),
                "nbPages":res.get("nbPages"),
                "hitsPerPage":res.get("hitsPerPage"),
                "returnedHits":len(hits),
                "uniqueCruiseIDs":len({h.get("cruiseID") for h in hits if h.get("cruiseID")}),
                "ships":sorted({(h.get("shipCd") or {}).get("value") for h in hits if (h.get("shipCd") or {}).get("value")}),
                "sample":[{
                  "cruiseID":h.get("cruiseID"),
                  "date":h.get("departureStartDate"),
                  "ship":(h.get("shipCd") or {}).get("value"),
                  "embark":(h.get("embkPort") or {}).get("value"),
                  "nights":h.get("numberOfNights"),
                  "itinerary":h.get("itineraryName"),
                  "adultPrice":(h.get("prices") or {}).get("adultPrice"),
                  "category":(h.get("category") or {}).get("value"),
                  "visiting":h.get("visitingPorts"),
                  "canvasMap":h.get("canvasMap"),
                  "commArea":h.get("commArea")
                } for h in hits[:10]]
            })
    browser.close()

Path("msc-browser-probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print("STATUS",out.get("status"),"QUERY_STATUS",out.get("query_status"))
if out.get("captured"):
    print("CAPTURED_HEADERS")
    for k,v in out["captured"]["headers"].items():
        print(k,":",v)
    print("CAPTURED_POST",out["captured"]["post_data"])
print("SUMMARY",json.dumps({k:v for k,v in out.items() if k not in ("captured","query_text")},ensure_ascii=False,indent=2))
if out.get("query_text"): print("QUERY_TEXT",out["query_text"])
if out.get("query_status")!=200: sys.exit(3)
