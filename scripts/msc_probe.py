#!/usr/bin/env python3
import json, re, sys, time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

URL = "https://www.msccruisesusa.com/msc-voyagers-club/exclusives-offer?departureDateFrom=06-10-2026&departureDateTo=31-12-2028&page=1&sort=date-soon"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SuncarTravelMSCIndexer/1.0; +https://suncartravel.github.io/)",
    "Accept-Language": "en-US,en;q=0.9",
}
r = requests.get(URL, headers=HEADERS, timeout=40)
out = {
    "status": r.status_code,
    "url": r.url,
    "length": len(r.text),
    "content_type": r.headers.get("content-type"),
}
soup = BeautifulSoup(r.text, "html.parser")
links = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    if "/itinerary-details/" in href:
        full = urljoin(URL, href)
        if full not in links:
            links.append(full)
out["itinerary_links"] = len(links)
out["sample_links"] = links[:20]

text = " ".join(soup.stripped_strings)
m = re.search(r"(\d[\d,]*)\s+Itineraries", text, re.I)
out["reported_itineraries"] = m.group(1) if m else None
out["text_sample"] = text[:12000]

# Inspect the first itinerary page if available.
if links:
    rr = requests.get(links[0], headers=HEADERS, timeout=40)
    ss = BeautifulSoup(rr.text, "html.parser")
    out["first_detail"] = {
        "status": rr.status_code,
        "url": rr.url,
        "length": len(rr.text),
        "title": ss.title.get_text(" ", strip=True) if ss.title else None,
        "text_sample": " ".join(ss.stripped_strings)[:10000],
    }

with open("msc-probe.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(json.dumps({k:v for k,v in out.items() if k not in ("text_sample","first_detail")}, ensure_ascii=False, indent=2))
if r.status_code != 200:
    sys.exit(2)
if len(links) < 1:
    sys.exit(3)
