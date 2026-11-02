#!/usr/bin/env python3
"""Retira de las páginas públicas promociones que ya no están vigentes.

Se ejecuta a diario por GitHub Actions, sin necesidad de que un visitante
abra la página. data-valid-through=YYYY-MM-DD es inclusivo.
data-expire admite ISO 8601 con zona horaria o YYYY-MM-DD, ambos exclusivos.
"""
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo
import re

TZ = ZoneInfo("America/Santo_Domingo")
PAGES = ("index.html", "ofertas.html", "msc-opera.html", "hoteles.html", "paquetes.html")
CARD = re.compile(r'<article\b[^>]*\bclass=["\'][^"\']*\blimited-offer\b[^"\']*["\'][^>]*>[\s\S]*?</article>\s*', re.I)
ATTRIBUTE = re.compile(r'\b(data-expire|data-valid-through|data-status)=["\']([^"\']+)["\']', re.I)
DIV_OPEN = re.compile(r'<div\b(?=[^>]*\b(?:data-expire|data-valid-through)=)[^>]*>', re.I)
DIV_TAG = re.compile(r"</?div\b[^>]*>", re.I)



def expired(card: str, now: datetime) -> bool:
    opening_tag = card.split(">", 1)[0]
    attrs = dict((key.lower(), value.strip()) for key, value in ATTRIBUTE.findall(opening_tag))
    if attrs.get("data-status", "").lower() in ("retirada", "inactiva", "cancelada"):
        return True

    end_date = attrs.get("data-valid-through")
    if end_date:
        try:
            return now.date() > date.fromisoformat(end_date)
        except ValueError:
            print(f"AVISO: data-valid-through inválido: {end_date}")
            return False

    deadline = attrs.get("data-expire")
    if not deadline:
        return False
    try:
        if len(deadline) == 10:
            expiry = datetime.combine(date.fromisoformat(deadline), time.min, TZ)
        else:
            expiry = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=TZ)
        return now >= expiry.astimezone(TZ)
    except ValueError:
        print(f"AVISO: data-expire inválido: {deadline}")
        return False



def prune_expired_divs(source: str, now: datetime) -> tuple[str, list[str]]:
    """Quita tarjetas y bloques promocionales div con caducidad, incluyendo anidados."""
    chunks = []
    names = []
    cursor = 0
    for opening in DIV_OPEN.finditer(source):
        if opening.start() < cursor or not expired(opening.group(0), now):
            continue
        depth = 1
        closing_end = None
        for tag in DIV_TAG.finditer(source, opening.end()):
            depth += -1 if tag.group(0).startswith("</") else 1
            if depth == 0:
                closing_end = tag.end()
                break
        if closing_end is None:
            raise ValueError("Bloque div.limited-offer sin cierre, no se elimina nada")
        chunks.append(source[cursor:opening.start()])
        cursor = closing_end
        names.append("Bloque promocional caducado")
    chunks.append(source[cursor:])
    return "".join(chunks), names


def refresh_sitemap_xml(xml: str, changed: list[str], updated: str) -> str:
    """Actualiza lastmod solo para las páginas cuyo HTML realmente cambió."""
    for filename in changed:
        url = "https://www.suncartravel.com/" if filename == "index.html" else "https://www.suncartravel.com/" + filename
        pattern = re.compile(r"(<loc>" + re.escape(url) + r"</loc>\s*<lastmod>)([^<]+)(</lastmod>)")
        xml, count = pattern.subn(lambda m: m.group(1) + updated + m.group(3), xml)
        if count != 1:
            raise ValueError(f"Falta entrada única en sitemap.xml para {filename}")
    return xml


def run() -> None:
    now = datetime.now(TZ)
    removed_total = 0
    changed = []
    for filename in PAGES:
        path = Path(__file__).resolve().parents[1] / filename
        original = path.read_text(encoding="utf-8")
        removed = []

        def prune(match: re.Match[str]) -> str:
            if not expired(match.group(0), now):
                return match.group(0)
            title = re.search(r"<h3[^>]*>(.*?)</h3>", match.group(0), re.S | re.I)
            removed.append(re.sub("<[^>]+>", "", title.group(1)).strip() if title else "Oferta sin título")
            return ""

        modified = CARD.sub(prune, original)
        modified, div_removed = prune_expired_divs(modified, now)
        removed.extend(div_removed)
        if modified != original:
            path.write_text(modified, encoding="utf-8")
            changed.append(filename)
        removed_total += len(removed)
        print(f"{filename}: {len(removed)} ofertas retiradas", *[f"  - {n}" for n in removed], sep="\n")
    if changed:
        sitemap = Path(__file__).resolve().parents[1] / "sitemap.xml"
        original_xml = sitemap.read_text(encoding="utf-8")
        new_xml = refresh_sitemap_xml(original_xml, changed, now.date().isoformat())
        if new_xml != original_xml:
            sitemap.write_text(new_xml, encoding="utf-8")
    print(f"TOTAL: {removed_total} retiradas a las {now.isoformat()}")


if __name__ == "__main__":
    run()
