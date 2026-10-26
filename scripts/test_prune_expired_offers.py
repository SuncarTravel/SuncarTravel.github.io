import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from prune_expired_offers import expired, prune_expired_divs, CARD

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

    def test_article_selector_matches_cards(self):
        html = '<article class="offer-card limited-offer" data-expire="2026-10-23"><div>x</div></article>'
        self.assertEqual(len(CARD.findall(html)), 1)


if __name__ == "__main__":
    unittest.main()
