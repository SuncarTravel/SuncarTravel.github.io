#!/usr/bin/env python3
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL="https://www.msccruisesusa.com/deals/cruise-from-199-plus-onboard-credit/all-itineraries?sort=relevance"
SEARCH="/api-search/1/indexes/*/queries"
areas=["CAR","SOC","MED","NOR","SOA","POS","WEE","FAE","ALA","INW","PAN","WOR"]
out={}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport={"width":1440,"height":1200},locale="en-US",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")
    page=context.new_page(); captured=[]
    page.on("request",lambda req: captured.append({"url":req.url,"headers":dict(req.headers)}) if SEARCH in req.url and not captured else None)
    page.goto(URL,wait_until="domcontentloaded",timeout=90000); page.wait_for_timeout(7000)
    if not captured: raise RuntimeError("No search request")
    cap=captured[0]; headers={k:v for k,v in cap["headers"].items() if k.lower() not in ("content-length","host","cookie")}
    base="(noofAdults=2) AND (noofMinors=0) AND (noofJuniors=0) AND (prices.availability: true)"
    for area in areas:
        payload={"requests":[{"indexName":"prod-en-us-cruises","filters":base+f" AND (commArea.key:{area})","hitsPerPage":3,"page":0,"distinct":1,"attributesToHighlight":[""],"facets":[],"getRankingInfo":False,"clickAnalytics":False,"query":""}]}
        rr=context.request.post(cap["url"],headers=headers,data=json.dumps(payload),timeout=60000)
        item={"status":rr.status}
        if rr.status==200:
            res=rr.json()["results"][0]; item["nbHits"]=res.get("nbHits"); item["hits"]=[]
            for h in res.get("hits",[]):
                item["hits"].append({
                    "ship":(h.get("shipCd") or {}).get("value"),
                    "date":h.get("departureStartDate"),
                    "itinerary":h.get("itineraryName"),
                    "embark":(h.get("embkPort") or {}).get("value"),
                    "canvasMap":h.get("canvasMap"),
                    "commArea":h.get("commArea"),
                    "visiting":[x.get("value") for x in h.get("visitingPorts",[])]
                })
        out[area]=item
    browser.close()
Path("msc-browser-probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
