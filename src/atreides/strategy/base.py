"""Strategy protocol — the contract all strategies implement."""

from __future__ import annotations

from typing import Protocol

from atreides.models import OrderBook, OrderRequest, Position


class Strategy(Protocol):
    """Trading strategy interface."""

    name: str

    def compute_orders(
        self,
        book: OrderBook,
        position: Position | None,
    ) -> list[OrderRequest]:
        """Given current book and position, return desired orders."""
        ...
