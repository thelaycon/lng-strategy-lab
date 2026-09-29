import pandas as pd
from .base import Strategy, register


@register
class BuyHold(Strategy):
    name = "buy_hold"
    description = "Always long (benchmark)."
    defaults = {}

    def signal(self, close: pd.Series, params: dict) -> pd.Series:
        return pd.Series(1, index=close.index, dtype=int)
