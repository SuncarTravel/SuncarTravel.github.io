import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from prune_expired_offers import expired, prune_expired_divs, refresh_sitemap_xml, CARD

TZ = ZoneInfo("America/Santo_Domingo")
NOW = datetime(2026, 10, 26, 12, 0, tzinfo=TZ)


class OfferExpiryTests(unittest.TestCase):
    def test_october_hotel_expired(self):
        sample = '<article class="offer-card limited-offer" data-expire="2026-10-23T00:00:00-04:00">'
        self.assertTrue(expired(sample, NOW))

    def test_november_hotel_still_active(self):
        sample = '<article class="offer-card limited-offer" data-expire="2026-11-06T00:00:00-04:00">'
        self.assertFalse(expired(sample, NOW))

    def test_expires_at_start_of_departure_day(self):
        card = '<article class="offer-card limited-offer" data-expire="2026-11-06">'
        self.assertFalse(expired(card, datetime(2026, 11, 5, 23, 59, tzinfo=TZ)))
        self.assertTrue(expired(card, datetime(2026, 11, 6, 0, 0, tzinfo=TZ)))

    def test_valid_through_inclusive(self):
        card = '<div class="limited-offer" data-valid-through="2026-10-11">'
        self.assertFalse(expired(card, datetime(2026, 10, 11, 23, 59, tzinfo=TZ)))
        self.assertTrue(expired(card, datetime(2026, 10, 12, 0, 0, tzinfo=TZ)))

    def test_cancelled_offer_is_removed(self):
        self.assertTrue(expired('<article class="limited-offer" data-status="retirada">', NOW))

    def test_nested_msc_block_is_removed_without_affecting_neighbor(self):
        html = ('<section><div class="limited-offer" data-valid-through="2026-10-11">'
                '<div class="price-list"><div>Precio</div></div></div>'
                '<div class="promo-tag">BLOQUEO DE GRUPO</div></section>')
        changed, names = prune_expired_divs(html, NOW)
        self.assertEqual(len(names), 1)
        self.assertNotIn("Precio", changed)
        self.assertIn("BLOQUEO DE GRUPO", changed)
        self.assertTrue(changed.startswith("<section>"))

    def test_expired_hotel_card_removed(self):
        html = ('<div class="card" data-expire="2026-10-23T00:00:00-04:00">'
                '<div class="tag">Hotel</div><h3>Grand Palladium</h3></div>'
                '<div class="card" data-expire="2026-11-06T00:00:00-04:00">'
                '<h3>BlueBay</h3></div>')
        changed, removed = prune_expired_divs(html, NOW)
        self.assertEqual(len(removed), 1)
        self.assertNotIn("Grand Palladium", changed)
        self.assertIn("BlueBay", changed)

    def test_sitemap_lastmod_updates_only_changed_page(self):
        xml = ('<url><loc>https://www.suncartravel.com/hoteles.html</loc>'
               '<lastmod>2026-10-08</lastmod></url>'
               '<url><loc>https://www.suncartravel.com/ofertas.html</loc>'
               '<lastmod>2026-10-08</lastmod></url>')
        changed = refresh_sitemap_xml(xml, ["hoteles.html"], "2026-11-02")
        self.assertIn("hoteles.html</loc><lastmod>2026-11-02", changed)
        self.assertIn("ofertas.html</loc><lastmod>2026-10-08", changed)

    def test_article_selector_matches_cards(self):
        html = '<article class="offer-card limited-offer" data-expire="2026-10-23"><div>x</div></article>'
        self.assertEqual(len(CARD.findall(html)), 1)


if __name__ == "__main__":
    unittest.main()
