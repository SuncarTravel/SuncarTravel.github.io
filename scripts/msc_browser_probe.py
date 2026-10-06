#!/usr/bin/env python3
import json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL="https://www.msccruisesusa.com/msc-voyagers-club/exclusives-offer?departureDateFrom=06-10-2026&departureDateTo=31-12-2028&page=1&sort=date-soon"
out={"responses":[]}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(
        viewport={"width":1440,"height":1200},
        locale="en-US",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    )
    def on_response(resp):
        try:
            ct=(resp.headers.get("content-type") or "").lower()
            u=resp.url
            if "json" in ct or any(k in u.lower() for k in ("api","search","cruise","itiner","voyager","booking")):
                out["responses"].append({"status":resp.status,"url":u,"content_type":ct})
        except Exception:
            pass
    page.on("response",on_response)
    resp=page.goto(URL,wait_until="domcontentloaded",timeout=90000)
    out["status"]=resp.status if resp else None
    page.wait_for_timeout(12000)
    out["title"]=page.title()
    out["url"]=page.url
    text=page.locator("body").inner_text(timeout=20000)
    out["text_sample"]=text[:25000]
    links=page.locator("a").evaluate_all("(els)=>els.map(e=>e.href).filter(Boolean)")
    itins=[]
    for x in links:
        if "/itinerary-details/" in x and x not in itins: itins.append(x)
    out["itinerary_links"]=len(itins)
    out["sample_links"]=itins[:50]
    out["all_link_count"]=len(links)
    m=re.search(r"([0-9][0-9,]*)\s+Itineraries",text,re.I)
    out["reported_itineraries"]=m.group(1) if m else None
    browser.close()

Path("msc-browser-probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print("STATUS",out["status"],"TITLE",out["title"],"URL",out["url"])
print("ITIN_LINKS",out["itinerary_links"],"ALL_LINKS",out["all_link_count"],"REPORTED",out["reported_itineraries"])
print("BODY_SAMPLE_START")
print(out["text_sample"][:8000])
print("BODY_SAMPLE_END")
print("NETWORK_CANDIDATES")
for item in out["responses"][-120:]:
    print(item["status"], item["content_type"], item["url"])
if out.get("status") not in (200,304): sys.exit(2)
