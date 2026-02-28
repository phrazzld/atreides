"""Tests for risk controls."""

from decimal import Decimal

from atreides.config import Settings
from atreides.models import OrderRequest, OrderSide, Side
from atreides.risk import RiskManager


def _settings(**overrides) -> Settings:
    defaults = {
        "kalshi_api_base": "https://demo-api.kalshi.co/trade-api/v2",
        "max_position_per_market": 10,
        "max_total_exposure": 50,
        "max_daily_loss": 20,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _order(market_id: str = "TEST", price: str = "0.50", quantity: int = 5) -> OrderRequest:
    return OrderRequest(
        market_id=market_id,
        side=Side.YES,
        order_side=OrderSide.BUY,
        price=Decimal(price),
        quantity=quantity,
    )


class TestRiskManager:
    def test_allows_small_order(self):
        rm = RiskManager(_settings())
        reason = rm.check_order(_order(price="0.50", quantity=5), [])
        assert reason is None  # $2.50 cost < $10 limit

    def test_rejects_oversized_order(self):
        rm = RiskManager(_settings(max_position_per_market=5))
        reason = rm.check_order(_order(price="0.50", quantity=20), [])
        assert reason is not None
        assert "per-market limit" in reason

    def test_kill_switch_on_daily_loss(self):
        rm = RiskManager(_settings(max_daily_loss=10))
        rm.record_pnl(Decimal("-11"))
        assert rm.is_killed
        reason = rm.check_order(_order(), [])
        assert reason is not None
        assert "Kill switch" in reason

    def test_reset_daily_clears_kill_switch(self):
        rm = RiskManager(_settings(max_daily_loss=10))
        rm.record_pnl(Decimal("-15"))
        assert rm.is_killed
        rm.reset_daily()
        assert not rm.is_killed
