"""Tests for PriceCache's open-price capture (PLAN §13.A1), added
alongside the existing PriceCache test suite in test_cache.py rather than
editing it.
"""

from app.market.cache import PriceCache


class TestOpenPriceCapture:
    def test_open_price_captured_on_first_tick(self):
        cache = PriceCache()
        update = cache.update("AAPL", 100.0)
        assert update.open_price == 100.0

    def test_open_price_not_overwritten_by_later_ticks(self):
        cache = PriceCache()
        cache.update("AAPL", 100.0)
        cache.update("AAPL", 150.0)
        third = cache.update("AAPL", 90.0)

        assert third.open_price == 100.0
        assert cache.get("AAPL").open_price == 100.0

    def test_day_change_percent_computes_against_open_price(self):
        cache = PriceCache()
        cache.update("AAPL", 100.0)
        update = cache.update("AAPL", 110.0)

        assert update.day_change == 10.0
        assert update.day_change_percent == 10.0

    def test_open_price_is_per_ticker(self):
        cache = PriceCache()
        cache.update("AAPL", 100.0)
        cache.update("GOOGL", 175.0)
        cache.update("AAPL", 120.0)

        assert cache.get("AAPL").open_price == 100.0
        assert cache.get("GOOGL").open_price == 175.0

    def test_removed_then_readded_ticker_gets_fresh_open_price(self):
        cache = PriceCache()
        cache.update("AAPL", 100.0)
        cache.remove("AAPL")

        update = cache.update("AAPL", 50.0)

        assert update.open_price == 50.0
        assert update.day_change == 0.0

    def test_first_tick_has_no_bogus_day_change(self):
        cache = PriceCache()
        update = cache.update("AAPL", 190.50)

        # First tick: open_price == price, so day_change is exactly 0, not
        # some artifact of previous_price defaulting to price too.
        assert update.day_change == 0.0
        assert update.day_change_percent == 0.0

    def test_to_dict_from_cache_includes_day_change(self):
        cache = PriceCache()
        cache.update("AAPL", 100.0)
        update = cache.update("AAPL", 105.0)

        d = update.to_dict()
        assert d["day_change"] == 5.0
        assert d["day_change_percent"] == 5.0
