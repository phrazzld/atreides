# Atreides

Prediction market trading bot. Connects to Kalshi (Polymarket planned), reconstructs portfolio from trade history, and will eventually run Avellaneda-Stoikov market-making.

## Status

Phase 1 complete — read-only Kalshi integration with live portfolio tracking.

## Quick Start

```bash
uv sync
cp .env.example .env  # add your Kalshi API credentials
```

```bash
python -m atreides markets          # list active markets
python -m atreides book <ticker>    # show orderbook
python -m atreides watch <ticker>   # stream price updates
python -m atreides balance          # portfolio + P&L
```

## Architecture

```
src/atreides/
  config.py           # pydantic-settings, env vars
  models.py           # Market, OrderBook, Position, Order types
  cli.py              # rich terminal UI
  exchange/
    base.py           # Exchange protocol (structural typing)
    kalshi.py         # Kalshi SDK adapter + raw API fallback
  strategy/
    base.py           # Strategy protocol (Phase 4)
  risk.py             # Position limits, loss limits, kill switch (Phase 3)
```

Exchange abstraction lets the same strategy run on any platform. Portfolio reconstruction works around Kalshi SDK gaps (empty `get_positions()`, missing status enums).

## Roadmap

1. ~~Foundation + Kalshi read-only~~ done
2. Data collection + volatility estimation
3. Live trading with hard risk limits ($50 max exposure)
4. Avellaneda-Stoikov market making
5. Polymarket + cross-exchange arbitrage

## License

MIT
