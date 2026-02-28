"""CLI interface for exploring prediction markets."""

from __future__ import annotations

import asyncio
import sys
import time

from kalshi_python.exceptions import ApiException
from rich.console import Console
from rich.live import Live
from rich.table import Table

from atreides.config import settings
from atreides.exchange.kalshi import KalshiExchange

console = Console()


def _make_exchange() -> KalshiExchange:
    return KalshiExchange(settings)


async def _markets_cmd(limit: int = 20, status: str = "open") -> None:
    """List active markets."""
    ex = _make_exchange()
    await ex.connect()
    try:
        markets = await ex.get_markets(limit=limit, status=status)
        table = Table(title=f"Kalshi Markets ({status})", expand=True)
        table.add_column("Ticker", style="cyan", no_wrap=True, ratio=1)
        table.add_column("Title", ratio=2)
        table.add_column("Bid", justify="right", style="green", width=5)
        table.add_column("Ask", justify="right", style="red", width=5)
        table.add_column("Sprd", justify="right", style="yellow", width=5)
        table.add_column("Vol", justify="right", width=7)

        for m in markets:
            table.add_row(
                m.ticker,
                m.title,
                f"{m.yes_bid:.0%}",
                f"{m.yes_ask:.0%}",
                f"{m.spread:.0%}",
                f"{m.volume:,}",
            )
        console.print(table)
        console.print(f"\n[dim]{len(markets)} markets shown[/dim]")
    finally:
        await ex.close()


async def _book_cmd(ticker: str) -> None:
    """Show orderbook for a market."""
    ex = _make_exchange()
    await ex.connect()
    try:
        market = await ex.get_market(ticker)
        book = await ex.get_orderbook(ticker)

        console.print(f"\n[bold]{market.title}[/bold]")
        console.print(f"[dim]{market.ticker} | {market.status}[/dim]\n")

        table = Table(title="Order Book (YES side)")
        table.add_column("Bid Qty", justify="right", style="green")
        table.add_column("Bid $", justify="right", style="green")
        table.add_column("Ask $", justify="right", style="red")
        table.add_column("Ask Qty", justify="right", style="red")

        max_rows = max(len(book.yes_bids), len(book.yes_asks))
        for i in range(min(max_rows, 10)):
            bid_price = f"${book.yes_bids[i].price:.2f}" if i < len(book.yes_bids) else ""
            bid_qty = str(book.yes_bids[i].quantity) if i < len(book.yes_bids) else ""
            ask_price = f"${book.yes_asks[i].price:.2f}" if i < len(book.yes_asks) else ""
            ask_qty = str(book.yes_asks[i].quantity) if i < len(book.yes_asks) else ""
            table.add_row(bid_qty, bid_price, ask_price, ask_qty)

        console.print(table)

        if book.mid is not None:
            console.print(f"\nMid: [bold]${book.mid:.2f}[/bold]  Spread: ${book.spread:.2f}")
    finally:
        await ex.close()


async def _watch_cmd(ticker: str, interval: float = 2.0) -> None:
    """Stream price updates for a market."""
    ex = _make_exchange()
    await ex.connect()
    try:
        market = await ex.get_market(ticker)
        console.print(f"[bold]Watching: {market.title}[/bold]")
        console.print(f"[dim]Ctrl+C to stop. Polling every {interval}s[/dim]\n")

        table = Table()
        table.add_column("Time")
        table.add_column("Bid", style="green")
        table.add_column("Ask", style="red")
        table.add_column("Mid", style="bold")
        table.add_column("Spread", style="yellow")

        with Live(table, console=console, refresh_per_second=1) as live:
            while True:
                book = await ex.get_orderbook(ticker)
                now = time.strftime("%H:%M:%S")

                table = Table(title=f"{market.ticker} — Live")
                table.add_column("Time")
                table.add_column("Bid", style="green")
                table.add_column("Ask", style="red")
                table.add_column("Mid", style="bold")
                table.add_column("Spread", style="yellow")

                bid = f"${book.best_bid:.2f}" if book.best_bid else "—"
                ask = f"${book.best_ask:.2f}" if book.best_ask else "—"
                mid = f"${book.mid:.2f}" if book.mid else "—"
                spread = f"${book.spread:.2f}" if book.spread else "—"
                table.add_row(now, bid, ask, mid, spread)

                live.update(table)
                await asyncio.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")
    finally:
        await ex.close()


async def _balance_cmd() -> None:
    """Show account balance and portfolio."""
    from atreides.models import PositionStatus

    ex = _make_exchange()
    await ex.connect()
    try:
        balance = await ex.get_balance()
        positions = await ex.get_positions()

        active = [p for p in positions if p.position_status == PositionStatus.ACTIVE]
        settled = [p for p in positions if p.position_status != PositionStatus.ACTIVE]

        # Active positions
        if active:
            table = Table(title="Active Positions")
            table.add_column("Ticker", style="cyan", no_wrap=True)
            table.add_column("Side", width=4)
            table.add_column("Qty", justify="right")
            table.add_column("Cost", justify="right")
            table.add_column("Value", justify="right")
            table.add_column("P&L", justify="right")

            for p in active:
                pnl_style = "green" if p.pnl >= 0 else "red"
                table.add_row(
                    p.market_id,
                    p.side.upper(),
                    str(p.quantity),
                    f"${p.cost_basis:.2f}",
                    f"${p.market_value:.2f}",
                    f"[{pnl_style}]${p.pnl:+.2f}[/{pnl_style}]",
                )
            console.print(table)

        active_value = sum(p.market_value for p in active)
        settled_pnl = sum(p.pnl for p in settled)
        total_pnl = sum(p.pnl for p in positions)

        # Summary
        console.print()
        console.print(f"  Cash:            [bold]${balance:.2f}[/bold]")
        console.print(
            f"  Active positions: [bold]${active_value:.2f}[/bold]  ({len(active)} markets)"
        )
        console.print(f"  Portfolio total:  [bold]${balance + active_value:.2f}[/bold]")

        pnl_style = "green" if total_pnl >= 0 else "red"
        console.print(
            f"  Settled P&L:      [{pnl_style}]${settled_pnl:+.2f}[/{pnl_style}]"
            f"  ({len(settled)} markets)"
        )
    finally:
        await ex.close()


def _usage() -> None:
    env = "DEMO" if settings.is_demo else "PRODUCTION"
    console.print(f"\n[bold]atreides[/bold] — prediction market trading bot [{env}]\n")
    console.print("Usage: python -m atreides <command> [args]\n")
    console.print("Commands:")
    console.print("  [cyan]markets[/cyan] [limit]       List active markets")
    console.print("  [cyan]book[/cyan] <ticker>         Show orderbook")
    console.print("  [cyan]watch[/cyan] <ticker>        Stream price updates")
    console.print("  [cyan]balance[/cyan]               Show account balance & positions")


def app() -> None:
    args = sys.argv[1:]
    if not args:
        _usage()
        return

    cmd, *rest = args

    try:
        match cmd:
            case "markets":
                limit = int(rest[0]) if rest else 20
                asyncio.run(_markets_cmd(limit=limit))
            case "book":
                if not rest:
                    console.print("[red]Usage: atreides book <ticker>[/red]")
                    sys.exit(1)
                asyncio.run(_book_cmd(rest[0]))
            case "watch":
                if not rest:
                    console.print("[red]Usage: atreides watch <ticker>[/red]")
                    sys.exit(1)
                interval = float(rest[1]) if len(rest) > 1 else 2.0
                asyncio.run(_watch_cmd(rest[0], interval))
            case "balance":
                asyncio.run(_balance_cmd())
            case _:
                console.print(f"[red]Unknown command: {cmd}[/red]")
                _usage()
                sys.exit(1)
    except ApiException as e:
        console.print(f"[red]API error: {e.reason} ({e.status})[/red]")
        sys.exit(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    app()
