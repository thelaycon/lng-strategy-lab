"""Bollinger mean-reversion — gas-range staple.

Long the dip (close < lower band), exit at the middle (or upper).
Gas benchmarks spend long periods range-bound between storage/weather
shocks, so this complements trend strategies.
"""
import pandas as pd
from .base import Strategy, register


@register
class BollingerMeanReversion(Strategy):
    name = "bollinger_mean_reversion"
    kind = "single"
    description = "Long when close < lower Bollinger band; exit at middle (or upper if exit_at_upper)."
    defaults = {"window": 20, "num_std": 2.0, "exit_at_upper": False}

    def signal(self, close: pd.Series, params: dict) -> pd.Series:
        w = int(params.get("window", 20))
        k = float(params.get("num_std", 2.0))
        exit_upper = bool(params.get("exit_at_upper", False))
        mid = close.rolling(w).mean()
        std = close.rolling(w).std()
        lower = mid - k * std
        upper = mid + k * std
        sig = pd.Series(0, index=close.index, dtype=int)
        pos = 0
        for i in range(len(close)):
            c, lo, m, hi = close.iloc[i], lower.iloc[i], mid.iloc[i], upper.iloc[i]
            if pd.isna(lo):
                sig.iloc[i] = 0
                continue
            if pos == 0 and c < lo:
                pos = 1
            elif pos == 1 and (c > hi if exit_upper else c > m):
                pos = 0
            sig.iloc[i] = pos
        return sig
