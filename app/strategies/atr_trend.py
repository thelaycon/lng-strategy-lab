"""ATR-stop trend (Donchian entry + Chandelier-style ATR trailing stop).

The workhorse of gas futures trend-following: enter on an N-day breakout,
then trail a stop at highest-close-since-entry − mult×ATR. Lets winners run
through storage/weather trends, cuts chops quickly.
"""
import pandas as pd
from .base import Strategy, _atr_proxy, register


@register
class ATRTrailingTrend(Strategy):
    name = "atr_trailing_trend"
    kind = "single"
    description = "N-day breakout entry with ATR trailing stop (gas futures trend staple)."
    defaults = {"entry": 20, "atr_window": 14, "atr_mult": 3.0}

    def signal(self, close: pd.Series, params: dict) -> pd.Series:
        n = int(params.get("entry", 20))
        aw = int(params.get("atr_window", 14))
        mult = float(params.get("atr_mult", 3.0))
        hi = close.shift(1).rolling(n).max()
        atr = _atr_proxy(close, aw)
        sig = pd.Series(0, index=close.index, dtype=int)
        pos, peak = 0, float("nan")
        for i in range(len(close)):
            c = close.iloc[i]
            if pos == 0:
                if pd.notna(hi.iloc[i]) and c > hi.iloc[i]:
                    pos, peak = 1, c
            else:
                peak = max(peak, c)
                stop = peak - mult * (atr.iloc[i] if pd.notna(atr.iloc[i]) else 0)
                if c < stop:
                    pos = 0
            sig.iloc[i] = pos
        return sig
