#!/usr/bin/env python3
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL="https://www.msccruisesusa.com/deals/cruise-from-199-plus-onboard-credit/all-itineraries?sort=relevance"
out={"search_requests":[],"search_responses":[]}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(
        viewport={"width":1440,"height":1200},
        locale="en-US",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    )

    def on_request(req):
        if "/api-search/1/indexes/*/queries" in req.url:
            out["search_requests"].append({
                "method":req.method,
                "url":req.url,
                "headers":dict(req.headers),
                "post_data":req.post_data,
            })

    def on_response(resp):
        if "/api-search/1/indexes/*/queries" in resp.url:
            item={"status":resp.status,"url":resp.url,"headers":dict(resp.headers)}
            try:
                item["json"]=resp.json()
            except Exception as e:
                try: item["text"]=resp.text()[:200000]
                except Exception as e2: item["error"]=str(e2)
            out["search_responses"].append(item)

    page.on("request",on_request)
    page.on("response",on_response)

    resp=page.goto(URL,wait_until="domcontentloaded",timeout=90000)
    out["status"]=resp.status if resp else None
    page.wait_for_timeout(12000)
    out["title"]=page.title()
    out["url"]=page.url
    text=page.locator("body").inner_text(timeout=20000)
    out["text_sample"]=text[:30000]
    out["reported_results"]=None
    import re
    m=re.search(r"([0-9][0-9,]*)\s+results found",text,re.I)
    if m: out["reported_results"]=m.group(1)

    browser.close()

Path("msc-browser-probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print("STATUS",out.get("status"),"TITLE",out.get("title"),"REPORTED",out.get("reported_results"))
print("SEARCH_REQUEST_COUNT",len(out["search_requests"]))
for i,r in enumerate(out["search_requests"]):
    print("REQUEST",i,r["method"],r["url"])
    print((r.get("post_data") or "")[:12000])
print("SEARCH_RESPONSE_COUNT",len(out["search_responses"]))
for i,r in enumerate(out["search_responses"]):
    print("RESPONSE",i,"STATUS",r.get("status"))
    j=r.get("json")
    if isinstance(j,dict):
        print("TOP_KEYS",list(j.keys()))
        res=j.get("results")
        if isinstance(res,list):
            print("RESULTS",len(res))
            for ri,item in enumerate(res[:4]):
                if isinstance(item,dict):
                    print("RESULT_ITEM",ri,"KEYS",list(item.keys()))
                    print(json.dumps(item,ensure_ascii=False)[:16000])
    elif r.get("text"):
        print(r["text"][:16000])

if out.get("status") not in (200,304): sys.exit(2)
if not out["search_responses"]: sys.exit(3)
