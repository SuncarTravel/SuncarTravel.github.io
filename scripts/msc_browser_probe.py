#!/usr/bin/env python3
import json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL="https://www.msccruisesusa.com/msc-voyagers-club/exclusives-offer?departureDateFrom=06-10-2026&departureDateTo=31-12-2028&page=1&sort=date-soon"
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
    page.wait_for_timeout(8000)
    out["title"]=page.title()
    out["url"]=page.url
    text=page.locator("body").inner_text(timeout=20000)
    out["text_sample"]=text[:20000]
    links=page.locator("a[href*='/itinerary-details/']").evaluate_all("(els)=>els.map(e=>e.href)")
    seen=[]
    for x in links:
        if x not in seen: seen.append(x)
    out["itinerary_links"]=len(seen)
    out["sample_links"]=seen[:50]
    m=re.search(r"([0-9][0-9,]*)\s+Itineraries",text,re.I)
    out["reported_itineraries"]=m.group(1) if m else None
    browser.close()
Path("msc-browser-probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in out.items() if k!="text_sample"},ensure_ascii=False,indent=2))
if out.get("status") not in (200,304): sys.exit(2)
if out.get("itinerary_links",0)<1: sys.exit(3)
