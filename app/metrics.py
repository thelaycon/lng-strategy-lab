"""Performance metrics from an equity curve."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252  # NGX ~250; 252 is standard


def summarize(equity: pd.Series, initial_capital: float, num_trades: int = 0,
              turnover: pd.Series | None = None) -> dict:
    equity = equity.dropna()
    if len(equity) < 2:
        return {"error": "not enough data"}
    rets = equity.pct_change().dropna()
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1)
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1 / 365.25)
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)
    vol = float(rets.std() * np.sqrt(TRADING_DAYS)) if len(rets) > 1 else 0.0
    sharpe = float(rets.mean() / rets.std() * np.sqrt(TRADING_DAYS)) if rets.std() else 0.0
    roll_max = equity.cummax()
    dd = (equity - roll_max) / roll_max
    max_dd = float(dd.min())
    win_rate = float((rets > 0).mean()) if len(rets) else 0.0
    exposure = None
    if turnover is not None:
        exposure = float((equity.pct_change().abs() > 0).mean())
    return {
        "initial_capital": initial_capital,
        "final_value": float(equity.iloc[-1]),
        "total_return_pct": round(total_return * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "ann_vol_pct": round(vol * 100, 2),
        "sharpe": round(sharpe, 3),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "win_rate_pct": round(win_rate * 100, 2),
        "num_trades": int(num_trades),
        "start": str(equity.index[0].date()),
        "end": str(equity.index[-1].date()),
        "n_days": int(len(equity)),
    }
