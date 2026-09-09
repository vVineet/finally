"""Tests for PriceCache's bounded per-ticker history ring buffer
(PLAN §13.B13/C4), added alongside the existing PriceCache test suite in
test_cache.py rather than editing it.
"""

from app.market.cache import HISTORY_MAXLEN, PriceCache


class TestPriceCacheHistory:
    def test_get_history_empty_for_unknown_ticker(self):
        cache = PriceCache()
        assert cache.get_history("NOPE") == []

    def test_get_history_records_ticks_oldest_first(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00, timestamp=1.0)
        cache.update("AAPL", 191.00, timestamp=2.0)
        cache.update("AAPL", 192.00, timestamp=3.0)

        history = cache.get_history("AAPL")

        assert history == [(1.0, 190.00), (2.0, 191.00), (3.0, 192.00)]

    def test_history_is_per_ticker_isolated(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00, timestamp=1.0)
        cache.update("GOOGL", 175.00, timestamp=1.0)
        cache.update("AAPL", 191.00, timestamp=2.0)

        assert cache.get_history("AAPL") == [(1.0, 190.00), (2.0, 191.00)]
        assert cache.get_history("GOOGL") == [(1.0, 175.00)]

    def test_history_ring_buffer_evicts_oldest_beyond_capacity(self):
        cache = PriceCache()
        for i in range(HISTORY_MAXLEN + 50):
            cache.update("AAPL", float(i), timestamp=float(i))

        history = cache.get_history("AAPL")

        assert len(history) == HISTORY_MAXLEN
        # The oldest 50 ticks (timestamps 0..49) were evicted; the buffer
        # holds exactly the most recent HISTORY_MAXLEN ticks, oldest-first.
        assert history[0] == (50.0, 50.0)
        assert history[-1] == (float(HISTORY_MAXLEN + 49), float(HISTORY_MAXLEN + 49))

    def test_get_history_respects_limit_returning_most_recent(self):
        cache = PriceCache()
        for i in range(10):
            cache.update("AAPL", float(i), timestamp=float(i))

        history = cache.get_history("AAPL", limit=3)

        assert history == [(7.0, 7.0), (8.0, 8.0), (9.0, 9.0)]

    def test_get_history_limit_larger_than_available_returns_all(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0, timestamp=1.0)

        assert cache.get_history("AAPL", limit=HISTORY_MAXLEN) == [(1.0, 190.0)]

    def test_remove_evicts_history(self):
        cache = PriceCache()
        cache.update("AAPL", 190.0, timestamp=1.0)
        cache.remove("AAPL")

        assert cache.get_history("AAPL") == []
        # Re-adding starts a fresh buffer, not a resurrected one.
        cache.update("AAPL", 200.0, timestamp=2.0)
        assert cache.get_history("AAPL") == [(2.0, 200.0)]
