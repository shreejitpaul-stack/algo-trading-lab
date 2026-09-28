# algo-trading-lab

Python experiments in backtesting and paper trading, built while learning algorithmic trading.

## Backtester: Bollinger Band mean reversion

`backtest/mean_reversion_backtest.py` tests a mean reversion strategy on daily stock data from Yahoo Finance.

**Strategy**
- 20-day simple moving average with bands 2 standard deviations above and below.
- Buy when the close crosses below the lower band; sell when it crosses above the upper band.
- Long-only, one position at a time, whole shares, all available cash.
- Signals are generated on the close and filled at the next day's open (no look-ahead).
- A flat cost of 5 bps per side (configurable) approximates spread and slippage.
- Any open position is closed at the final close.

**Metrics:** total and annualized return, Sharpe ratio (daily equity returns, 252-day annualization, 0% risk-free rate), max drawdown (mark-to-market), round trips, and win rate. Every trade is saved to `results/trades.csv` (git-ignored).

**Run it**

```bash
pip install yfinance pandas numpy
python3 backtest/mean_reversion_backtest.py
python3 backtest/mean_reversion_backtest.py --ticker AAPL --cost-bps 10
```

Options: `--ticker`, `--start`, `--end`, `--sma`, `--std`, `--cost-bps`.

## Sample results (2022-01-01 to 2024-01-01)

| Ticker | Cost/side | Strategy return | Buy & hold | Sharpe (strategy / B&H) | Max drawdown | Round trips | Win rate |
|--------|-----------|-----------------|------------|-------------------------|--------------|-------------|----------|
| SPY | 5 bps | 8.72% | 2.65% | 0.35 / 0.16 | -22.70% | 5 | 60% |
| AAPL | 10 bps | 26.97% | 6.99% | 0.72 / 0.26 | -21.54% | 6 | 66.7% |

## What the results show

- The strategy beat buy-and-hold on both tickers, but with 5 to 6 trades this is an observation, not evidence of an edge.
- The losing trades on both tickers were entered during the 2022 downtrend. The strategy buys dips with no trend filter.
- Max drawdown (about 22%) is much larger than the worst closed trade (4.3% on SPY, 6.0% on AAPL), so most of the risk came from unrealized swings during long holds with no stop-loss.

## Limitations

- Tiny sample; no statistical significance testing.
- Parameters were not optimized or validated out of sample, and only two tickers and one two-year window were tested.
- Costs are a flat assumption, not a model of spread, market impact, or taxes.
- Sharpe uses a 0% risk-free rate and includes days spent in cash.
- Yahoo Finance re-adjusts historical prices for dividends, so results drift slightly between runs.
- Educational project, not financial advice.

## Next steps

- Equity curve plot against buy-and-hold.
- Trend filter and stop-loss.
- Walk-forward (out-of-sample) testing.
- Live paper trading bot using the Alpaca API in `live/`.
