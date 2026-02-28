"""Risk controls — hard limits on position sizes and losses."""

from __future__ import annotations

import logging
from decimal import Decimal

from atreides.config import Settings
from atreides.models import OrderRequest, Position, PositionStatus

log = logging.getLogger(__name__)


class RiskManager:
    """Enforces position limits, exposure caps, and daily loss limits."""

    def __init__(self, settings: Settings) -> None:
        self.max_position_per_market = settings.max_position_per_market
        self.max_total_exposure = settings.max_total_exposure
        self.max_daily_loss = settings.max_daily_loss
        self._daily_pnl = Decimal("0")
        self._kill_switch = False

    @property
    def is_killed(self) -> bool:
        return self._kill_switch

    def check_order(self, order: OrderRequest, positions: list[Position]) -> str | None:
        """Return rejection reason, or None if order is allowed."""
        if self._kill_switch:
            return "Kill switch active — all trading halted"

        # Position limit per market
        cost = order.price * order.quantity
        if cost > self.max_position_per_market:
            return (
                f"Order cost ${cost:.2f} exceeds per-market limit ${self.max_position_per_market}"
            )

        # Total exposure — settled positions are resolved, only active ones carry risk
        active = [p for p in positions if p.position_status != PositionStatus.SETTLED]
        total = sum(p.market_value for p in active) + cost
        if total > self.max_total_exposure:
            return f"Total exposure ${total:.2f} would exceed limit ${self.max_total_exposure}"

        # Daily loss
        if self._daily_pnl < -self.max_daily_loss:
            self._kill_switch = True
            return f"Daily loss ${self._daily_pnl:.2f} exceeds limit ${self.max_daily_loss}"

        return None

    def record_pnl(self, pnl: Decimal) -> None:
        self._daily_pnl += pnl
        if self._daily_pnl < -self.max_daily_loss:
            log.warning("KILL SWITCH: daily loss $%.2f exceeds limit", self._daily_pnl)
            self._kill_switch = True

    def reset_daily(self) -> None:
        self._daily_pnl = Decimal("0")
        self._kill_switch = False
