# algo-trading-lab

Python experiments in backtesting and paper trading, built while learning algorithmic trading.

## Backtester: Bollinger Band mean reversion

`backtest/mean_reversion_backtest.py` tests a simple mean reversion strategy on daily stock data from Yahoo Finance.

**Strategy**
- Compute a 20-day simple moving average and bands 2 standard deviations above and below it.
- Buy (whole shares, all available cash) when the close crosses below the lower band.
- Sell the full position when the close crosses above the upper band.
- Close any open position on the final day.

**Run it**

```bash
pip install yfinance pandas
python3 backtest/mean_reversion_backtest.py
```

## Sample result

| Ticker | Period | Strategy return | Buy & hold | Round trips |
|--------|--------|-----------------|------------|-------------|
| SPY | 2022-01-01 to 2024-01-01 | 6.91% | 2.65% | 5 |

## Limitations

- Only 5 round trips, so this is far too small a sample to conclude the strategy has an edge.
- No transaction costs, spreads, or slippage are modeled.
- Parameters (20 days, 2 std) were not optimized or validated out of sample.
- Results shift slightly between runs because Yahoo Finance re-adjusts historical prices for dividends.
- Educational project, not financial advice.

## Next steps

- Add Sharpe ratio and max drawdown.
- Model transaction costs and slippage.
- Add live paper trading bots using the Alpaca API.
