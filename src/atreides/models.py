"""Shared domain models for prediction market trading."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class Side(StrEnum):
    YES = "yes"
    NO = "no"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(StrEnum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class Market(BaseModel):
    """A binary prediction market."""

    id: str
    ticker: str
    title: str
    category: str = ""
    yes_bid: Decimal = Decimal("0")
    yes_ask: Decimal = Decimal("1")
    volume: int = 0
    open_interest: int = 0
    close_time: datetime | None = None
    status: str = "open"
    exchange: str = ""

    @property
    def mid(self) -> Decimal:
        return (self.yes_bid + self.yes_ask) / 2

    @property
    def spread(self) -> Decimal:
        return self.yes_ask - self.yes_bid


class BidAsk(BaseModel):
    """Single price level in an orderbook."""

    price: Decimal
    quantity: int


class OrderBook(BaseModel):
    """Orderbook snapshot for a market."""

    market_id: str
    yes_bids: list[BidAsk] = Field(default_factory=list)
    yes_asks: list[BidAsk] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def best_bid(self) -> Decimal | None:
        return self.yes_bids[0].price if self.yes_bids else None

    @property
    def best_ask(self) -> Decimal | None:
        return self.yes_asks[0].price if self.yes_asks else None

    @property
    def mid(self) -> Decimal | None:
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2
        return None

    @property
    def spread(self) -> Decimal | None:
        if self.best_bid is not None and self.best_ask is not None:
            return self.best_ask - self.best_bid
        return None


class OrderRequest(BaseModel):
    """Request to place an order."""

    market_id: str
    side: Side
    order_side: OrderSide
    price: Decimal
    quantity: int
    order_type: OrderType = OrderType.LIMIT


class OrderResponse(BaseModel):
    """Result of placing an order."""

    order_id: str
    market_id: str
    status: OrderStatus
    side: Side
    order_side: OrderSide
    price: Decimal
    quantity: int
    filled_quantity: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PositionStatus(StrEnum):
    ACTIVE = "active"
    SETTLED = "settled"
    UNKNOWN = "unknown"


class Position(BaseModel):
    """Current position in a market."""

    market_id: str
    market_title: str = ""
    side: Side = Side.YES
    quantity: int = 0
    cost_basis: Decimal = Decimal("0")
    current_price: Decimal | None = None
    settlement_revenue: Decimal | None = None
    position_status: PositionStatus = PositionStatus.UNKNOWN

    @property
    def market_value(self) -> Decimal:
        if self.settlement_revenue is not None:
            return self.settlement_revenue
        if self.current_price is not None:
            return self.current_price * self.quantity
        return Decimal("0")

    @property
    def pnl(self) -> Decimal:
        return self.market_value - self.cost_basis
