"""Tests for Kalshi exchange adapter (unit tests with mocked SDK)."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from atreides.config import Settings
from atreides.exchange.kalshi import KalshiExchange, _cents_to_dollars


def _settings() -> Settings:
    return Settings(
        kalshi_api_base="https://demo-api.kalshi.co/trade-api/v2",
        kalshi_key_id="",
        kalshi_private_key_path="",
    )


class TestCentsToDollars:
    def test_converts_integer(self):
        assert _cents_to_dollars(50) == Decimal("0.50")

    def test_converts_zero(self):
        assert _cents_to_dollars(0) == Decimal("0")

    def test_converts_none(self):
        assert _cents_to_dollars(None) == Decimal("0")

    def test_converts_float(self):
        assert _cents_to_dollars(33.0) == Decimal("0.33")


class TestKalshiExchange:
    @pytest.fixture
    def exchange(self):
        return KalshiExchange(_settings())

    @pytest.mark.asyncio
    async def test_raises_before_connect(self, exchange):
        with pytest.raises(RuntimeError, match="Not connected"):
            await exchange.get_markets()

    @pytest.mark.asyncio
    async def test_get_markets(self, exchange):
        mock_market = MagicMock()
        mock_market.ticker = "TICKER-A"
        mock_market.title = "Will X happen?"
        mock_market.event_ticker = "EVENT-X"
        mock_market.yes_bid = 40
        mock_market.yes_ask = 60
        mock_market.volume = 1000
        mock_market.close_time = None
        mock_market.status = "open"

        mock_resp = MagicMock()
        mock_resp.markets = [mock_market]

        with patch("atreides.exchange.kalshi.MarketsApi") as mock_api:
            mock_api.return_value.get_markets.return_value = mock_resp
            await exchange.connect()
            markets = await exchange.get_markets()

        assert len(markets) == 1
        m = markets[0]
        assert m.ticker == "TICKER-A"
        assert m.yes_bid == Decimal("0.40")
        assert m.yes_ask == Decimal("0.60")
        assert m.exchange == "kalshi"

    @pytest.mark.asyncio
    async def test_get_orderbook(self, exchange):
        mock_bid = MagicMock()
        mock_bid.price = 45
        mock_bid.count = 10

        mock_ask = MagicMock()
        mock_ask.price = 55
        mock_ask.count = 8

        mock_ob = MagicMock()
        mock_ob.var_true = [mock_bid]
        mock_ob.var_false = [mock_ask]

        mock_resp = MagicMock()
        mock_resp.orderbook = mock_ob

        with patch("atreides.exchange.kalshi.MarketsApi") as mock_api:
            mock_api.return_value.get_market_orderbook.return_value = mock_resp
            await exchange.connect()
            book = await exchange.get_orderbook("TEST")

        assert book.best_bid == Decimal("0.45")
        assert book.best_ask == Decimal("0.55")
        assert book.yes_bids[0].quantity == 10

    @pytest.mark.asyncio
    async def test_context_manager_connects_and_closes(self, exchange):
        with patch("atreides.exchange.kalshi.KalshiApiClient"):
            async with exchange as ex:
                assert ex._client is not None
            assert ex._client is None

    @pytest.mark.asyncio
    async def test_place_order_not_implemented(self, exchange):
        with patch("atreides.exchange.kalshi.MarketsApi"):
            await exchange.connect()
        with pytest.raises(NotImplementedError):
            from atreides.models import OrderRequest, OrderSide, Side

            await exchange.place_order(
                OrderRequest(
                    market_id="X",
                    side=Side.YES,
                    order_side=OrderSide.BUY,
                    price=Decimal("0.50"),
                    quantity=1,
                )
            )
