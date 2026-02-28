# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                          # install deps
uv run pytest                    # all tests
uv run pytest tests/test_models.py  # single file
uv run ruff check src tests      # lint
uv run ruff format src tests     # format
python -m atreides markets       # list open markets (requires .env)
python -m atreides balance       # portfolio + P&L
python -m atreides book <ticker> # orderbook snapshot
python -m atreides watch <ticker># stream price updates
```

## Architecture

Prediction market trading bot. Phase 1 (done): read-only Kalshi integration. Phase 2 (active): data collection and volatility estimation. Phase 3: live trading with hard risk limits. Phase 4: Avellaneda-Stoikov market making.

```
src/atreides/
  config.py         # pydantic-settings; env prefix ATREIDES_; singleton `settings`
  models.py         # all domain types: Market, OrderBook, Position, OrderRequest, etc.
  cli.py            # rich terminal UI; entry point via `python -m atreides`
  exchange/
    base.py         # Exchange Protocol (structural typing, runtime_checkable)
    kalshi.py       # Kalshi adapter: SDK calls + raw HTTP fallback
  strategy/
    base.py         # Strategy Protocol (Phase 4 stub)
  risk.py           # RiskManager: per-market limits, total exposure, daily loss, kill switch
```

**Exchange abstraction:** `exchange/base.py` defines a `Protocol`; all strategy/risk code uses that protocol, never importing from `exchange/kalshi.py` directly. New exchanges implement the same interface.

**Kalshi adapter quirks:**
- `get_positions()` SDK endpoint returns empty — positions are reconstructed from `get_fills()` + `get_settlements()`
- Some markets have status values not in the SDK enum (e.g. `"finalized"`) — `get_market_safe()` falls back to raw HTTP
- Orderbook bids are in `ob.var_true`, asks in `ob.var_false` (SDK naming artifact)

**Price invariant:** Kalshi API sends prices in cents (1–99). Convert immediately with `_cents_to_dollars()`. Store and compute all prices as `Decimal`, never `float`.

## Domain Glossary

| Term | Definition |
|------|-----------|
| Binary market | Contract that pays $1 YES, $0 NO. Price = implied probability. |
| yes_bid / yes_ask | Best bid/ask for the YES side. |
| Mid | (bid + ask) / 2. Fair value estimate. |
| Fill | A completed trade. Ground truth for position reconstruction. |
| Settlement | Final market resolution. Revenue = payout for correct side. |

## Key Patterns

```python
# Cents → dollars: always use this, never ad-hoc division
def _cents_to_dollars(cents: int | float | None) -> Decimal:
    if cents is None:
        return Decimal("0")
    return Decimal(str(cents)) / CENTS

# SDK workaround: always provide raw fallback
async def get_market_safe(self, market_id: str) -> Market | None:
    try:
        return await self.get_market(market_id)
    except Exception:
        pass
    return await self._get_market_raw(market_id)
```

## Quality Bar

- All exchange interactions go through the `Exchange` protocol — no SDK calls outside `kalshi.py`
- Prices stored as `Decimal`, never `float`
- Risk limits enforced before any order placement (Phase 3)
- `tests/` uses mocked SDK — no live API calls in tests

## Config

`.env` with `ATREIDES_` prefix. Key vars:

| Var | Default | Note |
|-----|---------|------|
| `ATREIDES_KALSHI_API_BASE` | demo URL | Change to prod URL for live trading |
| `ATREIDES_KALSHI_KEY_ID` | `""` | RSA key ID from Kalshi dashboard |
| `ATREIDES_KALSHI_PRIVATE_KEY_PATH` | `""` | Path to RSA private key file |
| `ATREIDES_MAX_TOTAL_EXPOSURE` | `50` | Hard dollar cap across all positions |
| `ATREIDES_MAX_DAILY_LOSS` | `20` | Triggers kill switch |

Keys are production-only (demo endpoint returns 401 with real keys).
