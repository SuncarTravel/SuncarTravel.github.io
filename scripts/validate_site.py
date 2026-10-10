#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = [
    "index.html",
    "servicios.html",
    "hoteles.html",
    "vuelos.html",
    "cruceros.html",
    "seguros-viaje.html",
    "paquetes.html",
    "ofertas.html",
    "msc-opera.html",
    "politica-privacidad.html",
    "terminos-condiciones.html",
    "cambios-cancelaciones-reembolsos.html",
]

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.h1 = 0
        self.title_depth = 0
        self.title = []
        self.meta = []
        self.refs = []
        self.blank_links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.append(a["id"])
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self.title_depth += 1
        if tag == "meta":
            self.meta.append(a)
        if tag in {"a", "link"} and a.get("href"):
            self.refs.append((tag, a["href"]))
        if tag in {"img", "script", "source"} and a.get("src"):
            self.refs.append((tag, a["src"]))
        if tag == "a" and a.get("target", "").lower() == "_blank":
            self.blank_links.append(a)

    def handle_endtag(self, tag):
        if tag == "title" and self.title_depth:
            self.title_depth -= 1

    def handle_data(self, data):
        if self.title_depth:
            self.title.append(data)

def local_target(page: Path, raw: str) -> Path | None:
    raw = raw.strip()
    if not raw or raw.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    u = urlsplit(raw)
    if u.scheme or u.netloc:
        return None
    path = u.path
    if not path:
        return None
    if path.startswith("/"):
        return ROOT / path.lstrip("/")
    return (page.parent / path).resolve()

def meta_value(meta, *, name=None, prop=None):
    for item in meta:
        if name and item.get("name", "").lower() == name.lower():
            return item.get("content", "")
        if prop and item.get("property", "").lower() == prop.lower():
            return item.get("content", "")
    return ""

def fail(errors, message):
    errors.append(message)

def main():
    errors = []
    for rel in OFFICIAL:
        page = ROOT / rel
        if not page.exists():
            fail(errors, f"{rel}: falta el archivo oficial")
            continue
        text = page.read_text(encoding="utf-8")
        if "\ufffd" in text:
            fail(errors, f"{rel}: contiene el carácter de reemplazo U+FFFD")
        if re.search(r"""(?:href|src)=["'][^"']*prueba/""", text, re.I):
            fail(errors, f"{rel}: enlaza a /prueba/ desde una página oficial")

        parser = PageParser()
        parser.feed(text)

        title = "".join(parser.title).strip()
        if not title:
            fail(errors, f"{rel}: falta <title>")
        if parser.h1 != 1:
            fail(errors, f"{rel}: debe tener exactamente un H1 (tiene {parser.h1})")
        if not meta_value(parser.meta, name="viewport"):
            fail(errors, f"{rel}: falta meta viewport")
        if not meta_value(parser.meta, name="description"):
            fail(errors, f"{rel}: falta meta description")
        robots = meta_value(parser.meta, name="robots").lower()
        if "noindex" in robots:
            fail(errors, f"{rel}: una página oficial quedó con noindex")

        ids = set()
        for ident in parser.ids:
            if ident in ids:
                fail(errors, f"{rel}: id duplicado: {ident}")
            ids.add(ident)

        for attrs in parser.blank_links:
            rels = set(attrs.get("rel", "").lower().split())
            if "noopener" not in rels:
                fail(errors, f"{rel}: enlace target=_blank sin rel=noopener")

        for tag, ref in parser.refs:
            target = local_target(page, ref)
            if target is None:
                continue
            try:
                target.relative_to(ROOT)
            except ValueError:
                fail(errors, f"{rel}: referencia sale del repositorio: {ref}")
                continue
            if not target.exists():
                fail(errors, f"{rel}: referencia local rota ({tag}): {ref}")

        if "assets/analytics-config.js" not in text or "assets/analytics.js" not in text:
            fail(errors, f"{rel}: falta la integración compartida de Analytics")

        if "limited-offer" in text:
            if "assets/offers-expiry.js" not in text:
                fail(errors, f"{rel}: contiene ofertas limitadas sin el motor automático de vencimiento")
            for tag in re.findall(r'<(?:article|div)\\b[^>]*class=["\\'][^"\\']*\\blimited-offer\\b[^"\\']*["\\'][^>]*>', text, re.I):
                if "data-expire=" not in tag and "data-valid-through=" not in tag:
                    fail(errors, f"{rel}: oferta limitada sin fecha de vencimiento")
                m_expire = re.search(r'data-expire=["\\']([^"\\']+)["\\']', tag, re.I)
                m_through = re.search(r'data-valid-through=["\\']([^"\\']+)["\\']', tag, re.I)
                if m_expire:
                    value = m_expire.group(1)
                    if not re.fullmatch(r'\\d{4}-\\d{2}-\\d{2}(?:T\\d{2}:\\d{2}:\\d{2}-\\d{2}:\\d{2})?', value):
                        fail(errors, f"{rel}: data-expire inválido: {value}")
                if m_through:
                    value = m_through.group(1)
                    if not re.fullmatch(r'\\d{4}-\\d{2}-\\d{2}', value):
                        fail(errors, f"{rel}: data-valid-through inválido: {value}")


    config = (ROOT / "assets/analytics-config.js").read_text(encoding="utf-8")
    match = re.search(r'SUNCAR_GA4_ID\s*=\s*["\']([^"\']*)', config)
    ga_id = match.group(1).strip() if match else ""
    if ga_id and not re.fullmatch(r"G-[A-Z0-9]+", ga_id, re.I):
        fail(errors, "assets/analytics-config.js: Measurement ID de GA4 inválido")
    if ga_id:
        privacy = (ROOT / "politica-privacidad.html").read_text(encoding="utf-8").lower()
        if "google analytics" not in privacy:
            fail(errors, "politica-privacidad.html: GA4 está activo pero no se menciona Google Analytics")
        for rel in OFFICIAL:
            text = (ROOT / rel).read_text(encoding="utf-8")
            if f"googletagmanager.com/gtag/js?id={ga_id}" not in text:
                fail(errors, f"{rel}: falta la etiqueta estándar de Google en el HTML")

    sitemap = ROOT / "sitemap.xml"
    if not sitemap.exists():
        fail(errors, "falta sitemap.xml")
    else:
        try:
            root = ET.parse(sitemap).getroot()
            ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            urls = [x.text.strip() for x in root.findall("s:url/s:loc", ns) if x.text]
            if any("/prueba/" in u for u in urls):
                fail(errors, "sitemap.xml: contiene una URL de prueba")
            expected = {"https://suncartravel.github.io/"}
            expected |= {f"https://suncartravel.github.io/{p}" for p in OFFICIAL if p != "index.html"}
            missing = expected - set(urls)
            if missing:
                fail(errors, "sitemap.xml: faltan URLs oficiales: " + ", ".join(sorted(missing)))
        except ET.ParseError as exc:
            fail(errors, f"sitemap.xml: XML inválido: {exc}")

    robots = (ROOT / "robots.txt").read_text(encoding="utf-8") if (ROOT / "robots.txt").exists() else ""
    if "https://suncartravel.github.io/sitemap.xml" not in robots:
        fail(errors, "robots.txt: falta la referencia al sitemap")

    if errors:
        print("VALIDACIÓN DEL SITIO: ERROR")
        for item in errors:
            print(" -", item)
        return 1

    print(f"VALIDACIÓN DEL SITIO: OK · {len(OFFICIAL)} páginas oficiales")
    return 0

if __name__ == "__main__":
    sys.exit(main())
