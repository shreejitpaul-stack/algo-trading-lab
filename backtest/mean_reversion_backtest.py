#!/usr/bin/env python3
"""
Mean Reversion Backtester (Bollinger Bands)

Buys when the close crosses below the lower band, sells when it crosses above
the upper band. Signals are generated on the close and filled at the NEXT
day's open, with a per-trade cost applied to model spread and slippage.
"""

import argparse
import os

import numpy as np
import pandas as pd
import yfinance as yf

TRADING_DAYS = 252


class MeanReversionBacktester:
    def __init__(self, ticker, start_date, end_date, sma_period=20,
                 std_dev=2.0, initial_cash=10000, cost_bps=5):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.sma_period = sma_period
        self.std_dev = std_dev
        self.initial_cash = initial_cash
        self.cost_rate = cost_bps / 10_000
        self.cost_bps = cost_bps
        self.df = None
        self.trades = []

    def fetch_data(self):
        print(f"Fetching {self.ticker} from {self.start_date} to {self.end_date}...")
        df = yf.download(self.ticker, start=self.start_date, end=self.end_date,
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty:
            raise ValueError(f"No data found for {self.ticker}")
        self.df = df
        print(f"Downloaded {len(df)} trading days.")

    def calculate_indicators(self):
        close = self.df["Close"]
        self.df["SMA"] = close.rolling(self.sma_period).mean()
        self.df["STD"] = close.rolling(self.sma_period).std()
        self.df["Upper"] = self.df["SMA"] + self.std_dev * self.df["STD"]
        self.df["Lower"] = self.df["SMA"] - self.std_dev * self.df["STD"]

    def generate_signals(self):
        close, lower, upper = self.df["Close"], self.df["Lower"], self.df["Upper"]
        crossed_below = (close <= lower) & (close.shift(1) > lower.shift(1))
        crossed_above = (close >= upper) & (close.shift(1) < upper.shift(1))
        self.df["Signal"] = 0
        self.df.loc[crossed_below, "Signal"] = 1
        self.df.loc[crossed_above, "Signal"] = -1

    def _close_trade(self, entry, exit_date, exit_price):
        pnl = (exit_price - entry["entry_price"]) * entry["shares"]
        self.trades.append({
            "entry_date": entry["entry_date"],
            "exit_date": exit_date,
            "entry_price": round(entry["entry_price"], 4),
            "exit_price": round(exit_price, 4),
            "shares": entry["shares"],
            "pnl": round(pnl, 2),
            "return_pct": round((exit_price / entry["entry_price"] - 1) * 100, 2),
        })

    def backtest(self):
        df = self.df
        cash, shares, entry = float(self.initial_cash), 0, None
        equity = []

        for i in range(len(df)):
            if i > 0:
                prev_signal = df["Signal"].iloc[i - 1]
                open_price = df["Open"].iloc[i]
                date = df.index[i]

                if prev_signal == 1 and shares == 0:
                    buy_price = open_price * (1 + self.cost_rate)
                    qty = int(cash // buy_price)
                    if qty > 0:
                        cash -= qty * buy_price
                        shares = qty
                        entry = {"entry_date": date, "entry_price": buy_price, "shares": qty}
                elif prev_signal == -1 and shares > 0:
                    sell_price = open_price * (1 - self.cost_rate)
                    cash += shares * sell_price
                    self._close_trade(entry, date, sell_price)
                    shares, entry = 0, None

            equity.append(cash + shares * df["Close"].iloc[i])

        # Close any open position at the final close
        if shares > 0:
            sell_price = df["Close"].iloc[-1] * (1 - self.cost_rate)
            cash += shares * sell_price
            self._close_trade(entry, df.index[-1], sell_price)
            equity[-1] = cash

        df["Equity"] = equity

    @staticmethod
    def _sharpe(returns):
        std = returns.std()
        return float(returns.mean() / std * np.sqrt(TRADING_DAYS)) if std > 0 else 0.0

    def calculate_metrics(self):
        df = self.df
        equity = df["Equity"]
        final_value = float(equity.iloc[-1])
        days = (df.index[-1] - df.index[0]).days
        years = days / 365.25

        drawdown = equity / equity.cummax() - 1
        trades_df = pd.DataFrame(self.trades)
        wins = int((trades_df["pnl"] > 0).sum()) if not trades_df.empty else 0

        return {
            "Final value ($)": final_value,
            "Total return (%)": (final_value / self.initial_cash - 1) * 100,
            "Annualized return (%)": ((final_value / self.initial_cash) ** (1 / years) - 1) * 100 if years > 0 else 0.0,
            "Buy & hold return (%)": (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100,
            "Sharpe ratio": self._sharpe(equity.pct_change().dropna()),
            "Buy & hold Sharpe": self._sharpe(df["Close"].pct_change().dropna()),
            "Max drawdown (%)": float(drawdown.min() * 100),
            "Round trips": len(self.trades),
            "Win rate (%)": (wins / len(self.trades) * 100) if self.trades else 0.0,
        }

    def print_results(self):
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)
        print(f"Ticker: {self.ticker} | {self.start_date} to {self.end_date}")
        print(f"SMA={self.sma_period}, std={self.std_dev}, cost={self.cost_bps} bps per side\n")
        for key, value in self.calculate_metrics().items():
            print(f"{key:<26} {value:>12,.2f}")

        if self.trades:
            print("\nTRADES")
            print(pd.DataFrame(self.trades).to_string(index=False))
            os.makedirs("results", exist_ok=True)
            pd.DataFrame(self.trades).to_csv("results/trades.csv", index=False)
            print("\nSaved trade log to results/trades.csv")
        else:
            print("\nNo trades executed.")


def main():
    parser = argparse.ArgumentParser(description="Bollinger Band mean reversion backtester")
    parser.add_argument("--ticker", default="SPY")
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default="2024-01-01")
    parser.add_argument("--sma", type=int, default=20)
    parser.add_argument("--std", type=float, default=2.0)
    parser.add_argument("--cost-bps", type=float, default=5)
    args = parser.parse_args()

    bt = MeanReversionBacktester(args.ticker, args.start, args.end,
                                 args.sma, args.std, cost_bps=args.cost_bps)
    bt.fetch_data()
    bt.calculate_indicators()
    bt.generate_signals()
    bt.backtest()
    bt.print_results()


if __name__ == "__main__":
    main()
