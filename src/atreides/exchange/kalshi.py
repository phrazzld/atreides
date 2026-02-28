"""Kalshi exchange adapter."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from decimal import Decimal

from kalshi_python import Configuration
from kalshi_python import KalshiClient as KalshiApiClient
from kalshi_python.api.markets_api import MarketsApi
from kalshi_python.api.portfolio_api import PortfolioApi

from atreides.config import Settings
from atreides.models import (
    BidAsk,
    Market,
    OrderBook,
    OrderRequest,
    OrderResponse,
    Position,
    PositionStatus,
    Side,
)

log = logging.getLogger(__name__)

# Kalshi prices are in cents (1-99). We convert to dollars (0.01-0.99).
CENTS = Decimal("100")


def _cents_to_dollars(cents: int | float | None) -> Decimal:
    if cents is None:
        return Decimal("0")
    return Decimal(str(cents)) / CENTS


class KalshiExchange:
    """Kalshi prediction market exchange."""

    name = "kalshi"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._config = Configuration(host=settings.kalshi_api_base)
        self._client: KalshiApiClient | None = None
        self._markets: MarketsApi | None = None
        self._portfolio: PortfolioApi | None = None

    async def connect(self) -> None:
        self._client = KalshiApiClient(self._config)
        if self._settings.kalshi_key_id and self._settings.kalshi_private_key_path:
            self._client.set_kalshi_auth(
                self._settings.kalshi_key_id,
                self._settings.kalshi_private_key_path,
            )
            log.info("Authenticated with Kalshi (key_id=%s)", self._settings.kalshi_key_id[:8])
        else:
            log.info("Connected to Kalshi (unauthenticated — read-only public data)")
        self._markets = MarketsApi(self._client)
        self._portfolio = PortfolioApi(self._client)

    async def close(self) -> None:
        self._client = None
        self._markets = None
        self._portfolio = None

    def _require_client(self) -> KalshiApiClient:
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._client

    def _require_markets_api(self) -> MarketsApi:
        if self._markets is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._markets

    def _require_portfolio_api(self) -> PortfolioApi:
        if self._portfolio is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._portfolio

    # ── Market data ──────────────────────────────────────────────

    async def get_markets(
        self,
        *,
        limit: int = 100,
        cursor: str | None = None,
        status: str = "open",
    ) -> list[Market]:
        api = self._require_markets_api()
        resp = api.get_markets(limit=limit, cursor=cursor, status=status)
        return [self._convert_market(m) for m in (resp.markets or [])]

    async def get_market(self, market_id: str) -> Market:
        api = self._require_markets_api()
        resp = api.get_market(ticker=market_id)
        return self._convert_market(resp.market)

    async def get_market_safe(self, market_id: str) -> Market | None:
        """Get market, returning None if SDK can't parse the response.

        The Kalshi SDK's Market model doesn't include all status values
        (e.g. 'finalized'), causing Pydantic validation errors for some
        markets. This falls back to a raw API call.
        """
        try:
            return await self.get_market(market_id)
        except Exception:
            pass
        # Fallback: raw HTTP request, bypass SDK validation
        return await self._get_market_raw(market_id)

    async def _get_market_raw(self, ticker: str) -> Market | None:
        """Fetch market via raw API call, bypassing SDK model validation."""
        client = self._require_client()
        url = f"{self._settings.kalshi_api_base}/markets/{ticker}"
        try:
            resp = client.call_api("GET", url)
            data = json.loads(resp.data)
            m = data.get("market", {})
            return Market(
                id=m.get("ticker", ""),
                ticker=m.get("ticker", ""),
                title=m.get("title", ""),
                category=m.get("event_ticker", ""),
                yes_bid=_cents_to_dollars(m.get("yes_bid")),
                yes_ask=_cents_to_dollars(m.get("yes_ask")),
                volume=m.get("volume", 0) or 0,
                close_time=None,
                status=m.get("status", "unknown"),
                exchange="kalshi",
            )
        except Exception:
            log.debug("Raw market fetch failed for %s", ticker)
            return None

    async def get_orderbook(self, market_id: str, *, depth: int = 10) -> OrderBook:
        api = self._require_markets_api()
        resp = api.get_market_orderbook(ticker=market_id, depth=depth)
        ob = resp.orderbook
        return OrderBook(
            market_id=market_id,
            yes_bids=[
                BidAsk(price=_cents_to_dollars(level.price), quantity=level.count or 0)
                for level in (ob.var_true or [])
                if level.price is not None
            ],
            yes_asks=[
                BidAsk(price=_cents_to_dollars(level.price), quantity=level.count or 0)
                for level in (ob.var_false or [])
                if level.price is not None
            ],
        )

    # ── Portfolio ────────────────────────────────────────────────

    async def get_balance(self) -> Decimal:
        api = self._require_portfolio_api()
        resp = api.get_balance()
        return _cents_to_dollars(resp.balance)

    async def get_positions(self) -> list[Position]:
        """Reconstruct positions from fill history and settlements.

        The SDK's get_positions() endpoint returns empty for many accounts.
        This rebuilds the portfolio from the ground truth: trade fills
        minus settlement payouts.
        """
        api = self._require_portfolio_api()

        # 1. Paginate all fills
        fills = []
        cursor = None
        for _ in range(50):  # safety cap
            resp = api.get_fills(limit=100, cursor=cursor)
            batch = resp.fills or []
            fills.extend(batch)
            cursor = resp.cursor
            if not cursor or not batch:
                break

        # 2. Paginate all settlements
        settled_tickers: dict[str, Decimal] = {}
        cursor = None
        for _ in range(50):
            resp = api.get_settlements(limit=100, cursor=cursor)
            batch = resp.settlements or []
            for s in batch:
                ticker = s.ticker or ""
                revenue = _cents_to_dollars(s.revenue)
                settled_tickers[ticker] = settled_tickers.get(ticker, Decimal("0")) + revenue
            cursor = resp.cursor
            if not cursor or not batch:
                break

        # 3. Net fills into positions
        agg: dict[str, dict] = defaultdict(
            lambda: {"quantity": 0, "cost": Decimal("0"), "side": "yes"}
        )
        for f in fills:
            key = f.ticker
            if f.action == "buy":
                agg[key]["quantity"] += f.count
                agg[key]["cost"] += Decimal(str(f.count)) * _cents_to_dollars(f.price)
            else:
                agg[key]["quantity"] -= f.count
                agg[key]["cost"] -= Decimal(str(f.count)) * _cents_to_dollars(f.price)
            agg[key]["side"] = f.side

        # 4. Build Position objects, fetch prices for active markets
        positions = []
        for ticker, data in sorted(agg.items()):
            if data["quantity"] == 0:
                continue

            side = Side.YES if data["side"] == "yes" else Side.NO

            if ticker in settled_tickers:
                positions.append(
                    Position(
                        market_id=ticker,
                        side=side,
                        quantity=data["quantity"],
                        cost_basis=data["cost"],
                        settlement_revenue=settled_tickers[ticker],
                        position_status=PositionStatus.SETTLED,
                    )
                )
                continue

            # Active — fetch current price
            market = await self.get_market_safe(ticker)
            current_price = None
            title = ""
            status = PositionStatus.UNKNOWN
            if market is not None:
                title = market.title
                if market.status in ("active", "open"):
                    current_price = market.mid
                    status = PositionStatus.ACTIVE
                else:
                    # closed/settled/finalized but not in settlements yet
                    status = PositionStatus.SETTLED

            positions.append(
                Position(
                    market_id=ticker,
                    market_title=title,
                    side=side,
                    quantity=data["quantity"],
                    cost_basis=data["cost"],
                    current_price=current_price,
                    position_status=status,
                )
            )

        return positions

    # ── Trading (Phase 3) ────────────────────────────────────────

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        raise NotImplementedError("Trading not yet implemented (Phase 3)")

    async def cancel_order(self, order_id: str) -> None:
        raise NotImplementedError("Trading not yet implemented (Phase 3)")

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _convert_market(m) -> Market:
        """Convert Kalshi SDK Market to our domain Market."""
        return Market(
            id=m.ticker or "",
            ticker=m.ticker or "",
            title=m.title or "",
            category=m.event_ticker or "",
            yes_bid=_cents_to_dollars(m.yes_bid),
            yes_ask=_cents_to_dollars(m.yes_ask),
            volume=m.volume or 0,
            close_time=m.close_time,
            status=m.status or "unknown",
            exchange="kalshi",
        )
