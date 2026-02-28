"""Exchange protocol — the contract all exchanges implement."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, runtime_checkable

from atreides.models import Market, OrderBook, OrderRequest, OrderResponse, Position


@runtime_checkable
class Exchange(Protocol):
    """Prediction market exchange interface."""

    name: str

    async def connect(self) -> None:
        """Authenticate and establish connection."""
        ...

    async def close(self) -> None:
        """Clean up connection resources."""
        ...

    async def get_markets(
        self,
        *,
        limit: int = 100,
        cursor: str | None = None,
        status: str = "open",
    ) -> list[Market]:
        """List available markets."""
        ...

    async def get_market(self, market_id: str) -> Market:
        """Get a single market by ID."""
        ...

    async def get_orderbook(self, market_id: str) -> OrderBook:
        """Get current orderbook for a market."""
        ...

    async def get_balance(self) -> Decimal:
        """Get account balance in dollars."""
        ...

    async def get_positions(self) -> list[Position]:
        """Get all open positions."""
        ...

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """Place an order. Phase 3."""
        ...

    async def cancel_order(self, order_id: str) -> None:
        """Cancel an open order. Phase 3."""
        ...
