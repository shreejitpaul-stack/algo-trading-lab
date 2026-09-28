#!/usr/bin/env python3
"""
Mean Reversion Stock Backtester
Bollinger Bands mean reversion strategy on historical stock data.
"""

import yfinance as yf
import pandas as pd


class MeanReversionBacktester:
    def __init__(self, ticker, start_date, end_date, sma_period=20, std_dev=2, initial_cash=10000):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.sma_period = sma_period
        self.std_dev = std_dev
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.shares = 0
        self.trades = []
        self.df = None

    def fetch_data(self):
        print(f"Fetching data for {self.ticker} from {self.start_date} to {self.end_date}...")
        self.df = yf.download(self.ticker, start=self.start_date, end=self.end_date, progress=False)
        if isinstance(self.df.columns, pd.MultiIndex):
            self.df.columns = self.df.columns.get_level_values(0)
        if self.df.empty:
            raise ValueError(f"No data found for {self.ticker}")
        print(f"Downloaded {len(self.df)} days of data.")

    def calculate_indicators(self):
        self.df['SMA'] = self.df['Close'].rolling(window=self.sma_period).mean()
        self.df['STD'] = self.df['Close'].rolling(window=self.sma_period).std()
        self.df['Upper_Band'] = self.df['SMA'] + (self.df['STD'] * self.std_dev)
        self.df['Lower_Band'] = self.df['SMA'] - (self.df['STD'] * self.std_dev)

    def generate_signals(self):
        self.df['Signal'] = 0
        for i in range(self.sma_period, len(self.df)):
            if self.df['Close'].iloc[i] <= self.df['Lower_Band'].iloc[i] and self.df['Close'].iloc[i-1] > self.df['Lower_Band'].iloc[i-1]:
                self.df.loc[self.df.index[i], 'Signal'] = 1
            elif self.df['Close'].iloc[i] >= self.df['Upper_Band'].iloc[i] and self.df['Close'].iloc[i-1] < self.df['Upper_Band'].iloc[i-1]:
                self.df.loc[self.df.index[i], 'Signal'] = -1

    def backtest(self):
        print("\nRunning backtest...")
        for i in range(len(self.df)):
            date = self.df.index[i]
            close_price = self.df['Close'].iloc[i]
            signal = self.df['Signal'].iloc[i]
            if signal == 1 and self.cash > 0:
                shares_to_buy = int(self.cash / close_price)
                if shares_to_buy > 0:
                    cost = shares_to_buy * close_price
                    self.shares += shares_to_buy
                    self.cash -= cost
                    self.trades.append({'Date': date, 'Type': 'BUY', 'Price': close_price, 'Shares': shares_to_buy, 'Amount': cost})
            elif signal == -1 and self.shares > 0:
                proceeds = self.shares * close_price
                self.cash += proceeds
                self.trades.append({'Date': date, 'Type': 'SELL', 'Price': close_price, 'Shares': self.shares, 'Amount': proceeds})
                self.shares = 0
        if self.shares > 0:
            final_price = self.df['Close'].iloc[-1]
            proceeds = self.shares * final_price
            self.cash += proceeds
            self.trades.append({'Date': self.df.index[-1], 'Type': 'SELL (EOD)', 'Price': final_price, 'Shares': self.shares, 'Amount': proceeds})
            self.shares = 0

    def calculate_metrics(self):
        final_value = self.cash
        total_return = final_value - self.initial_cash
        return_pct = (total_return / self.initial_cash) * 100
        days_held = (self.df.index[-1] - self.df.index[0]).days
        years = days_held / 365.25
        annualized_return = ((final_value / self.initial_cash) ** (1 / years) - 1) * 100 if years > 0 else 0
        num_trades = len([t for t in self.trades if t['Type'] == 'BUY'])
        return {
            'Initial Investment': self.initial_cash,
            'Final Value': final_value,
            'Total Return ($)': total_return,
            'Total Return (%)': return_pct,
            'Annualized Return (%)': annualized_return,
            'Number of Trades': num_trades,
            'Days Held': days_held,
            'Buy & Hold Return (%)': ((self.df['Close'].iloc[-1] / self.df['Close'].iloc[0]) - 1) * 100,
        }

    def print_results(self):
        metrics = self.calculate_metrics()
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)
        print(f"Strategy: Mean Reversion (Bollinger Bands)")
        print(f"Ticker: {self.ticker} | Period: {self.start_date} to {self.end_date}")
        print(f"Parameters: SMA={self.sma_period}, Std Dev={self.std_dev}\n")
        for key, value in metrics.items():
            print(f"{key:<28} {value:>14,.2f}")
        print("\nTRADE LOG")
        print(pd.DataFrame(self.trades).to_string(index=False) if self.trades else "No trades executed.")


def main():
    try:
        bt = MeanReversionBacktester("SPY", "2022-01-01", "2024-01-01", 20, 2, 10000)
        bt.fetch_data()
        bt.calculate_indicators()
        bt.generate_signals()
        bt.backtest()
        bt.print_results()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
