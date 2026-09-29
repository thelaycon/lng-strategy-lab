"""Inter-basin spreads — the LNG-native trade.

JKM (Asia) vs TTF (EU) vs HH (US) differentials drive cargo routing and LNG
netbacks. This z-score switcher goes long the cheap leg / flat the rich leg:

  z = mean((log A − log B − rolling_mean) / rolling_std)
  z > +entry  → long B (B cheap), flat A
  z < −entry  → long A (A cheap), flat B
  |z| < exit  → unwind to flat/flat (or hold with hysteresis)

Long/flat only (no shorting), so it fits the portfolio engine. Two presets:
  jkm_ttf_arb   (JKM=F vs TTF=F — trans-Atlantic/Asia arb)
  ttf_nbp_basis (TTF=F vs NBP=F — EU/UK basis)
Override legs via params for HH-TTF etc.
"""
import numpy as np
import pandas as pd
from .base import Strategy, register


def _spread_signals(prices: pd.DataFrame, leg_a: str, leg_b: str,
                    window: int, entry: float, exit_: float) -> pd.DataFrame:
    cols = list(prices.columns)
    if leg_a not in cols or leg_b not in cols:
        if len(cols) < 2:
            return pd.DataFrame(0, index=prices.index, columns=cols, dtype=int)
        leg_a, leg_b = cols[0], cols[1]
    a = prices[leg_a].astype(float)
    b = prices[leg_b].astype(float)
    spread = np.log(a / b.replace(0, np.nan))
    mu = spread.rolling(window).mean()
    sd = spread.rolling(window).std()
    z = (spread - mu) / sd.replace(0, np.nan)
    sig = pd.DataFrame(0, index=prices.index, columns=cols, dtype=int)
    state = 0  # +1 long A / flat B, -1 long B / flat A, 0 flat
    for i, v in enumerate(z):
        if pd.isna(v):
            pass
        elif state == 0:
            if v < -entry:
                state = 1
            elif v > entry:
                state = -1
        elif state == 1 and v > -exit_:
            state = 0
        elif state == -1 and v < exit_:
            state = 0
        if state == 1:
            sig.iloc[i, sig.columns.get_loc(leg_a)] = 1
        elif state == -1:
            sig.iloc[i, sig.columns.get_loc(leg_b)] = 1
    return sig


class _SpreadBase(Strategy):
    kind = "spread"
    leg_a: str = "JKM=F"
    leg_b: str = "TTF=F"
    defaults = {"leg_a": "JKM=F", "leg_b": "TTF=F",
                "window": 60, "entry": 1.5, "exit": 0.5}

    def signal(self, close: pd.Series, params: dict) -> pd.Series:
        raise NotImplementedError("spread strategy: use portfolio_signal")

    def portfolio_signal(self, prices: pd.DataFrame, params: dict) -> pd.DataFrame:
        la = params.get("leg_a", self.leg_a)
        lb = params.get("leg_b", self.leg_b)
        return _spread_signals(prices, la, lb, int(params.get("window", 60)),
                               float(params.get("entry", 1.5)), float(params.get("exit", 0.5)))


@register
class JkmTtfArb(_SpreadBase):
    name = "jkm_ttf_arb"
    description = "Long cheap / flat rich leg of JKM vs TTF on z-score (LNG inter-basin arb)."


@register
class TtfNbpBasis(_SpreadBase):
    name = "ttf_nbp_basis"
    leg_a = "TTF=F"
    leg_b = "NBP=F"
    defaults = {"leg_a": "TTF=F", "leg_b": "NBP=F",
                "window": 60, "entry": 1.5, "exit": 0.5}
    description = "Long cheap / flat rich leg of TTF vs NBP (EU/UK basis)."
