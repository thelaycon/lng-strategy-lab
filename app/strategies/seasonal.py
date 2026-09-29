"""Seasonal storage-cycle hold — long the heating season.

Northern-hemisphere gas draws storage (and typically firms) Nov–Mar and
injects (softer) Apr–Oct. This calendar filter is the baseline seasonal
for TTF/NBP/HH/JKM; combine with trend overlays in research.
"""
import pandas as pd
from .base import Strategy, register


@register
class SeasonalStorage(Strategy):
    name = "seasonal_storage"
    kind = "single"
    description = "Long Nov–Mar (withdrawal season), flat Apr–Oct. Configurable months."
    defaults = {"long_months": [11, 12, 1, 2, 3]}

    def signal(self, close: pd.Series, params: dict) -> pd.Series:
        months = set(int(m) for m in params.get("long_months", [11, 12, 1, 2, 3]))
        return pd.Series(
            [1 if d.month in months else 0 for d in close.index],
            index=close.index, dtype=int,
        )
