"""Tests for PriceUpdate's day_change/day_change_percent (PLAN §13.A1),
added alongside the existing PriceUpdate test suite in test_models.py
rather than editing it. `open_price` is optional/defaulted so every
existing PriceUpdate(...) call site (including in test_models.py) that
doesn't pass it is unaffected.
"""

from app.market.models import PriceUpdate


class TestDayChange:
    def test_no_open_price_yields_zero_not_error(self):
        update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1.0)
        assert update.open_price is None
        assert update.day_change == 0.0
        assert update.day_change_percent == 0.0

    def test_day_change_up(self):
        update = PriceUpdate(
            ticker="AAPL", price=110.0, previous_price=105.0, timestamp=1.0, open_price=100.0
        )
        assert update.day_change == 10.0
        assert update.day_change_percent == 10.0

    def test_day_change_down(self):
        update = PriceUpdate(
            ticker="AAPL", price=90.0, previous_price=95.0, timestamp=1.0, open_price=100.0
        )
        assert update.day_change == -10.0
        assert update.day_change_percent == -10.0

    def test_day_change_zero_open_price_does_not_divide_by_zero(self):
        update = PriceUpdate(
            ticker="AAPL", price=5.0, previous_price=5.0, timestamp=1.0, open_price=0.0
        )
        assert update.day_change_percent == 0.0

    def test_first_tick_open_equals_price_gives_zero_day_change(self):
        update = PriceUpdate(
            ticker="AAPL", price=190.50, previous_price=190.50, timestamp=1.0, open_price=190.50
        )
        assert update.day_change == 0.0
        assert update.day_change_percent == 0.0

    def test_to_dict_includes_day_change_fields_alongside_tick_fields(self):
        update = PriceUpdate(
            ticker="AAPL", price=110.0, previous_price=109.0, timestamp=1.0, open_price=100.0
        )
        d = update.to_dict()
        # Existing tick fields are untouched (frontend flash animation
        # depends on these).
        assert d["change"] == 1.0
        assert d["change_percent"] == round(1.0 / 109.0 * 100, 4)
        assert d["direction"] == "up"
        # New day-change fields, computed against open_price.
        assert d["day_change"] == 10.0
        assert d["day_change_percent"] == 10.0
