"""Portfolio backtest engine: long/flat, daily, with costs."""
from __future__ import annotations

import pandas as pd


def backtest_portfolio(
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    initial_capital: float = 10_000_000.0,
    weights: dict[str, float] | None = None,
    fee_bps: float = 100.0,       # NGX-ish commission+fees per side, default 1.0%
    slippage_bps: float = 25.0,
) -> dict:
    tickers = list(prices.columns)
    n = len(tickers)
    if weights is None:
        weights = {t: 1.0 / n for t in tickers}
    else:
        tot = sum(weights.get(t, 0) for t in tickers) or 1.0
        weights = {t: weights.get(t, 0) / tot for t in tickers}

    signals = signals.reindex(prices.index).fillna(0).clip(0, 1)
    rets = prices.pct_change().fillna(0)

    cost_rate = (fee_bps + slippage_bps) / 10_000.0
    # target naira allocation per ticker
    equity = pd.Series(index=prices.index, dtype=float)
    turnover_series = pd.Series(index=prices.index, dtype=float)
    equity.iloc[0] = initial_capital

    # target weight exposure each day (signal * static weight)
    target_w = signals.mul(pd.Series(weights))
    # turnover = change in target weight (proxy for traded fraction)
    d_w = target_w.diff().abs().sum(axis=1).fillna(target_w.iloc[0].sum())

    port_ret_gross = (target_w.shift(1).fillna(0) * rets).sum(axis=1)
    cost = d_w * cost_rate
    port_ret_net = port_ret_gross - cost

    equity = initial_capital * (1 + port_ret_net).cumprod()
    turnover_series = d_w

    # crude trade count: entries per ticker
    entries = ((signals.diff() > 0).sum()).to_dict()
    trades = int(sum(entries.values()))

    return {
        "equity": equity,
        "target_weights": target_w,
        "turnover": turnover_series,
        "static_weights": weights,
        "num_trades": trades,
        "entries_per_ticker": {k: int(v) for k, v in entries.items()},
    }
