"""Time-series momentum (TSMOM, Moskowitz-Ooi-Pedersen style, long/flat).

Long when past lookback return (skipping the most recent day) exceeds
threshold. The standard CTA filter for gas benchmarks.
"""
import pandas as pd
from .base import Strategy, register


@register
class TimeSeriesMomentum(Strategy):
    name = "ts_momentum"
    kind = "single"
    description = "Long when trailing lookback return > threshold (CTA time-series momentum)."
    defaults = {"lookback": 90, "threshold": 0.0, "skip": 1}

    def signal(self, close: pd.Series, params: dict) -> pd.Series:
        lb = int(params.get("lookback", 90))
        th = float(params.get("threshold", 0.0))
        skip = int(params.get("skip", 1))
        past = close.shift(skip)
        roc = past / past.shift(lb) - 1
        sig = (roc > th).astype(int)
        return sig.fillna(0)
