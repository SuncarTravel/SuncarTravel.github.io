#!/usr/bin/env python3
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL="https://www.msccruisesusa.com/deals/cruise-from-199-plus-onboard-credit/all-itineraries?sort=relevance"
SEARCH="/api-search/1/indexes/*/queries"
out={}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(
        viewport={"width":1440,"height":1200},locale="en-US",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    )
    page=context.new_page()
    captured=[]
    page.on("request",lambda req: captured.append({"url":req.url,"headers":dict(req.headers),"post_data":req.post_data}) if SEARCH in req.url and not captured else None)
    resp=page.goto(URL,wait_until="domcontentloaded",timeout=90000)
    out["status"]=resp.status if resp else None
    page.wait_for_timeout(7000)
    if not captured:
        raise RuntimeError("No search request captured")
    cap=captured[0]
    headers={k:v for k,v in cap["headers"].items() if k.lower() not in ("content-length","host","cookie")}

    def query(filters,hits=20,page_no=0,facets=True):
        payload={"requests":[{
          "indexName":"prod-en-us-cruises",
          "filters":filters,
          "hitsPerPage":hits,"page":page_no,"distinct":1,
          "attributesToHighlight":[""],"facets":["*"] if facets else [],
          "getRankingInfo":False,"clickAnalytics":False,"query":""
        }]}
        rr=context.request.post(cap["url"],headers=headers,data=json.dumps(payload),timeout=60000)
        if rr.status!=200:
            return {"status":rr.status,"text":rr.text()[:1000]}
        return {"status":200,"data":rr.json()}

    base="(noofAdults=2) AND (noofMinors=0) AND (noofJuniors=0) AND (prices.availability: true)"
    q0=query(base,20,0,True)
    out["base_status"]=q0["status"]
    if q0["status"]==200:
        res=q0["data"]["results"][0]
        out["base_nbHits"]=res.get("nbHits")
        out["facet_keys"]=sorted((res.get("facets") or {}).keys())
        out["ship_facets"]={k:v for k,v in (res.get("facets") or {}).items() if "ship" in k.lower()}
        out["area_facets"]={k:v for k,v in (res.get("facets") or {}).items() if "area" in k.lower()}
        out["season_facets"]={k:v for k,v in (res.get("facets") or {}).items() if "season" in k.lower()}

    test_filters=[
      base+' AND (shipCd.value:"MSC Seaside")',
      base+' AND (shipCd.key:SE)',
      base+' AND (departureStartDateTimestamp >= 1791244800000)'
    ]
    out["tests"]=[]
    for tf in test_filters:
        q=query(tf,10,0,False)
        item={"filter":tf,"status":q["status"]}
        if q["status"]==200:
            rr=q["data"]["results"][0]
            item["nbHits"]=rr.get("nbHits")
            item["ships"]=sorted({(h.get("shipCd") or {}).get("value") for h in rr.get("hits",[])})
            item["dates"]=[h.get("departureStartDate") for h in rr.get("hits",[])[:5]]
        else:item["text"]=q.get("text")
        out["tests"].append(item)

    browser.close()

Path("msc-browser-probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(out,ensure_ascii=False,indent=2))
if out.get("base_status")!=200: sys.exit(3)
