# Project: Atreides

## Vision
Prediction market trading bot that runs Avellaneda-Stoikov market making on Kalshi and Polymarket.

**North Star:** Autonomous MM bot profitably quoting 10+ markets across exchanges, compounding returns.
**Target User:** Solo trader (the developer) running the bot with real money.
**Current Focus:** Phase 2 — data collection, volatility estimation, market opportunity scoring.
**Key Differentiators:** Exchange-abstracted (same strategy runs anywhere), grounded in academic MM theory (A-S 2006), built incrementally with hard risk limits.

## Domain Glossary

| Term | Definition |
|------|-----------|
| Binary market | Contract that pays $1 if YES, $0 if NO. Price = implied probability. |
| Yes bid / Yes ask | Best bid and ask prices for the YES side of a binary contract. |
| Spread | Ask minus bid. Revenue opportunity for market makers. |
| Mid | (Bid + Ask) / 2. Fair value estimate. |
| Reservation price | A-S concept: inventory-adjusted fair value. Skews quotes away from risk. |
| Fill | A completed trade. Kalshi records all fills with ticker, side, action, price, count. |
| Settlement | Final resolution of a market. Revenue = payout for correct predictions. |
| Cents vs dollars | Kalshi API uses cents (1-99). We convert to dollars (0.01-0.99) internally. |

## Active Focus

- **Milestone:** Phase 2 — Data Collection + Analytics
- **Key Issues:** TBD (this grooming session)
- **Theme:** Gather data, estimate volatility, identify MM opportunities before risking capital.

## Quality Bar

- [ ] All exchange interactions go through the Exchange protocol (no SDK calls outside adapter)
- [ ] Prices stored as Decimal, never float
- [ ] Risk limits enforced before any order placement
- [ ] Tests cover model properties and exchange adapter logic
- [ ] CLI commands work against live Kalshi production API

## Patterns to Follow

### Exchange adapter pattern
```python
# All exchange methods are async, return domain models (not SDK types)
async def get_market(self, market_id: str) -> Market:
    api = self._require_markets_api()
    resp = api.get_markets(ticker=market_id)
    return self._convert_market(resp.market)
```

### SDK workarounds
```python
# Kalshi SDK has gaps. Always provide a safe fallback.
async def get_market_safe(self, market_id: str) -> Market | None:
    try:
        return await self.get_market(market_id)
    except Exception:
        pass
    return await self._get_market_raw(market_id)
```

### Cents-to-dollars conversion
```python
CENTS = Decimal("100")
def _cents_to_dollars(cents: int | float | None) -> Decimal:
    if cents is None:
        return Decimal("0")
    return Decimal(str(cents)) / CENTS
```

## Lessons Learned

| Decision | Outcome | Lesson |
|----------|---------|--------|
| Trust `get_positions()` SDK endpoint | Returns empty for real accounts | Reconstruct from `get_fills()` + `get_settlements()` |
| Trust SDK Market model validation | Rejects "finalized" status enum | Need raw API fallback for any SDK model parse |
| Use demo API for initial testing | 401 — keys are production-only | User's keys are prod; test read-only ops first |

---
*Last updated: 2026-02-27*
*Updated during: /groom session*
