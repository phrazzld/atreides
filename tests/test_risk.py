"""Tests for risk controls."""

from decimal import Decimal

from atreides.config import Settings
from atreides.models import OrderRequest, OrderSide, Position, PositionStatus, Side
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

    def test_rejects_when_exposure_plus_order_exceeds_limit(self):
        # AC: given positions=$8 and limit=$10, a $3 order is rejected
        position = Position(
            market_id="EXISTING",
            quantity=10,
            cost_basis=Decimal("8.00"),
            current_price=Decimal("0.80"),
            position_status=PositionStatus.ACTIVE,
        )
        rm = RiskManager(_settings(max_total_exposure=10))
        # cost = 0.50 * 6 = $3.00; total = $8.00 + $3.00 = $11.00 > $10.00
        reason = rm.check_order(_order(price="0.50", quantity=6), [position])
        assert reason is not None
        assert "exposure" in reason

    def test_allows_when_exposure_plus_order_within_limit(self):
        # AC: given positions=$8 and limit=$10, a $1 order is allowed
        position = Position(
            market_id="EXISTING",
            quantity=10,
            cost_basis=Decimal("8.00"),
            current_price=Decimal("0.80"),
            position_status=PositionStatus.ACTIVE,
        )
        rm = RiskManager(_settings(max_total_exposure=10))
        # cost = 0.50 * 2 = $1.00; total = $8.00 + $1.00 = $9.00 <= $10.00
        reason = rm.check_order(_order(price="0.50", quantity=2), [position])
        assert reason is None

    def test_settled_positions_excluded_from_exposure(self):
        # AC: settled positions don't count toward total exposure
        settled = Position(
            market_id="SETTLED",
            quantity=100,
            cost_basis=Decimal("50.00"),
            settlement_revenue=Decimal("100.00"),  # would be $100 if counted
            position_status=PositionStatus.SETTLED,
        )
        active = Position(
            market_id="ACTIVE",
            quantity=5,
            cost_basis=Decimal("3.00"),
            current_price=Decimal("0.60"),
            position_status=PositionStatus.ACTIVE,
        )
        rm = RiskManager(_settings(max_total_exposure=10))
        # active market_value = 0.60 * 5 = $3.00; settled is excluded
        # order cost = 0.50 * 6 = $3.00; total = $3.00 + $3.00 = $6.00 <= $10.00
        reason = rm.check_order(_order(price="0.50", quantity=6), [settled, active])
        assert reason is None
