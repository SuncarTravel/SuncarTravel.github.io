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
PAGES = ("index.html", "ofertas.html")
CARD = re.compile(r'<article\b[^>]*\bclass=["\'][^"\']*\blimited-offer\b[^"\']*["\'][^>]*>[\s\S]*?</article>\s*', re.I)
ATTRIBUTE = re.compile(r'\b(data-expire|data-valid-through|data-status)=["\']([^"\']+)["\']', re.I)


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


def run() -> None:
    now = datetime.now(TZ)
    removed_total = 0
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
        if modified != original:
            path.write_text(modified, encoding="utf-8")
        removed_total += len(removed)
        print(f"{filename}: {len(removed)} ofertas retiradas", *[f"  - {n}" for n in removed], sep="\n")
    print(f"TOTAL: {removed_total} retiradas a las {now.isoformat()}")


if __name__ == "__main__":
    run()
