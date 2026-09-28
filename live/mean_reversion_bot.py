#!/usr/bin/env python3
"""
Live paper trading bot: Bollinger Band mean reversion on crypto (Alpaca).

- Evaluates signals only on COMPLETED hourly bars, once per bar.
- Buys when the close crosses below the lower band, sells when it crosses
  above the upper band. One position at a time.
- Logs actual fill prices from Alpaca to logs/live_trades.csv.
- Paper trading only.

Requires ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables.
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from alpaca.common.exceptions import APIError
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, OrderStatus, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

LOG_PATH = "logs/live_trades.csv"
LOG_FIELDS = ["timestamp", "symbol", "side", "qty", "fill_price", "notional", "realized_pnl"]
TERMINAL_STATUSES = {OrderStatus.CANCELED, OrderStatus.REJECTED, OrderStatus.EXPIRED}


def get_clients():
    key = os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("ALPACA_SECRET_KEY")
    if not key or not secret:
        sys.exit("Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables first.")
    trading = TradingClient(key, secret, paper=True)  # paper only
    data = CryptoHistoricalDataClient(key, secret)
    return trading, data


def fetch_completed_bars(data_client, symbol, sma, std_mult):
    """Hourly bars that have fully closed, with Bollinger Bands added."""
    request = CryptoBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Hour,
        start=datetime.now(timezone.utc) - timedelta(days=5),
    )
    df = data_client.get_crypto_bars(request).df.reset_index()
    df = df[df["symbol"] == symbol].sort_values("timestamp")
    # A bar starting at time t is complete once t + 1 hour has passed
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    df = df[df["timestamp"] <= cutoff].reset_index(drop=True)

    df["SMA"] = df["close"].rolling(sma).mean()
    df["STD"] = df["close"].rolling(sma).std()
    df["Upper"] = df["SMA"] + std_mult * df["STD"]
    df["Lower"] = df["SMA"] - std_mult * df["STD"]
    return df


def get_position(trading_client, symbol):
    """Return the open position, or None if there isn't one."""
    try:
        return trading_client.get_open_position(symbol.replace("/", ""))
    except APIError as e:
        if getattr(e, "status_code", None) == 404:
            return None
        raise


def submit_and_wait(trading_client, symbol, side, notional=None, qty=None, timeout=30):
    """Submit a market order and wait for it to fill. Returns the order or None."""
    request = MarketOrderRequest(
        symbol=symbol, side=side, time_in_force=TimeInForce.GTC,
        notional=notional, qty=qty,
    )
    order = trading_client.submit_order(request)
    deadline = time.time() + timeout
    while time.time() < deadline:
        order = trading_client.get_order_by_id(order.id)
        if order.status == OrderStatus.FILLED:
            return order
        if order.status in TERMINAL_STATUSES:
            print(f"Order ended with status {order.status}.")
            return None
        time.sleep(1)
    print(f"Order {order.id} not filled after {timeout}s (status: {order.status}).")
    return None


def log_trade(symbol, side, qty, fill_price, realized_pnl=""):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    is_new = not os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "fill_price": round(fill_price, 4),
            "notional": round(qty * fill_price, 2),
            "realized_pnl": realized_pnl,
        })


def run(args):
    trading, data = get_clients()
    symbol = args.symbol
    print(f"Paper trading {symbol} | SMA={args.sma}, std={args.std}, "
          f"${args.notional} per buy, polling every {args.poll}s")
    print("Ctrl+C to stop (any open position stays open).\n")

    last_bar = None  # timestamp of the last bar we evaluated

    while True:
        try:
            df = fetch_completed_bars(data, symbol, args.sma, args.std)
            if len(df) < args.sma + 2:
                print("Not enough completed bars yet, waiting...")
                time.sleep(args.poll)
                continue

            prev, last = df.iloc[-2], df.iloc[-1]
            position = get_position(trading, symbol)
            held = float(position.qty) if position else 0.0
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] bar {last['timestamp']:%m-%d %H:%M} "
                  f"close {last['close']:.2f} | lower {last['Lower']:.2f} "
                  f"upper {last['Upper']:.2f} | holding {held:.6f}")

            if last["timestamp"] != last_bar:  # new completed bar: check signals once
                last_bar = last["timestamp"]
                crossed_below = last["close"] <= last["Lower"] and prev["close"] > prev["Lower"]
                crossed_above = last["close"] >= last["Upper"] and prev["close"] < prev["Upper"]

                if crossed_below and position is None:
                    order = submit_and_wait(trading, symbol, OrderSide.BUY, notional=args.notional)
                    if order:
                        qty, price = float(order.filled_qty), float(order.filled_avg_price)
                        log_trade(symbol, "buy", qty, price)
                        print(f"  BUY filled: {qty:.6f} @ {price:.2f}")

                elif crossed_above and position is not None:
                    entry = float(position.avg_entry_price)
                    order = submit_and_wait(trading, symbol, OrderSide.SELL, qty=float(position.qty))
                    if order:
                        qty, price = float(order.filled_qty), float(order.filled_avg_price)
                        pnl = round((price - entry) * qty, 2)
                        log_trade(symbol, "sell", qty, price, pnl)
                        print(f"  SELL filled: {qty:.6f} @ {price:.2f} | realized P&L ${pnl:+.2f}")

            time.sleep(args.poll)

        except KeyboardInterrupt:
            print("\nStopped. Check the Alpaca dashboard for any open position.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(args.poll)


def main():
    parser = argparse.ArgumentParser(description="Live paper trading: Bollinger mean reversion")
    parser.add_argument("--symbol", default="BTC/USD")
    parser.add_argument("--sma", type=int, default=20)
    parser.add_argument("--std", type=float, default=2.0)
    parser.add_argument("--notional", type=float, default=100, help="USD per buy")
    parser.add_argument("--poll", type=int, default=60, help="seconds between checks")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
