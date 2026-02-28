"""Tests for domain models."""

from decimal import Decimal

from atreides.models import BidAsk, Market, OrderBook, Position


class TestMarket:
    def test_mid_price(self):
        m = Market(
            id="TEST",
            ticker="TEST",
            title="Test",
            yes_bid=Decimal("0.40"),
            yes_ask=Decimal("0.60"),
        )
        assert m.mid == Decimal("0.50")

    def test_spread(self):
        m = Market(
            id="TEST",
            ticker="TEST",
            title="Test",
            yes_bid=Decimal("0.40"),
            yes_ask=Decimal("0.60"),
        )
        assert m.spread == Decimal("0.20")

    def test_defaults(self):
        m = Market(id="X", ticker="X", title="X")
        assert m.yes_bid == Decimal("0")
        assert m.yes_ask == Decimal("1")
        assert m.volume == 0


class TestOrderBook:
    def test_best_bid_ask(self):
        book = OrderBook(
            market_id="TEST",
            yes_bids=[
                BidAsk(price=Decimal("0.45"), quantity=10),
                BidAsk(price=Decimal("0.40"), quantity=5),
            ],
            yes_asks=[BidAsk(price=Decimal("0.55"), quantity=8)],
        )
        assert book.best_bid == Decimal("0.45")
        assert book.best_ask == Decimal("0.55")
        assert book.mid == Decimal("0.50")
        assert book.spread == Decimal("0.10")

    def test_empty_book(self):
        book = OrderBook(market_id="EMPTY")
        assert book.best_bid is None
        assert book.best_ask is None
        assert book.mid is None
        assert book.spread is None


class TestPosition:
    def test_market_value_active(self):
        p = Position(
            market_id="TEST",
            quantity=10,
            cost_basis=Decimal("3.00"),
            current_price=Decimal("0.50"),
        )
        assert p.market_value == Decimal("5.00")

    def test_market_value_settled(self):
        p = Position(
            market_id="TEST",
            quantity=10,
            cost_basis=Decimal("3.00"),
            settlement_revenue=Decimal("10.00"),
        )
        assert p.market_value == Decimal("10.00")

    def test_pnl(self):
        p = Position(
            market_id="TEST",
            quantity=10,
            cost_basis=Decimal("3.00"),
            current_price=Decimal("0.50"),
        )
        assert p.pnl == Decimal("2.00")

    def test_pnl_no_price(self):
        p = Position(market_id="TEST", cost_basis=Decimal("5.00"))
        assert p.market_value == Decimal("0")
        assert p.pnl == Decimal("-5.00")
