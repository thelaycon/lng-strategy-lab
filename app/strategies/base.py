"""Pluggable strategy interface.

To add your own alpha, create `app/strategies/custom_<name>.py`:

    from .base import register, Strategy
    import pandas as pd

    @register
    class MyAlpha(Strategy):
        name = "my_alpha"
        kind = "single"  # or "spread" if it uses portfolio_signal
        defaults = {"lookback": 20}
        def signal(self, close: pd.Series, params: dict) -> pd.Series:
            ...return 0/1 Series aligned to close...

    Spread strategies override portfolio_signal(prices, params) instead,
    returning a 0/1 DataFrame (columns = tickers). The engine uses it when
    available, so e.g. JKM-TTF arb can go long the cheap leg / flat the rich one.

It is auto-discovered on import via `load_strategies()`.
"""
from __future__ import annotations

import importlib
import pkgutil
from abc import ABC

import pandas as pd

REGISTRY: dict[str, type["Strategy"]] = {}


def register(cls: type["Strategy"]) -> type["Strategy"]:
    REGISTRY[cls.name] = cls
    return cls


class Strategy(ABC):
    name: str = "base"
    kind: str = "single"  # "single" | "spread"
    defaults: dict = {}
    description: str = ""

    def signal(self, close: pd.Series, params: dict) -> pd.Series:
        """Single-name 0/1 exposure. Overridden by single-name strategies."""
        raise NotImplementedError(f"{self.name} is a {self.kind} strategy; no single-name signal")

    def portfolio_signal(self, prices: pd.DataFrame, params: dict) -> pd.DataFrame | None:
        """Multi-asset 0/1 signals. Return None to fall back to per-ticker signal()."""
        return None


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    out = 100 - 100 / (1 + rs)
    return out.fillna(50.0)


def _atr_proxy(close: pd.Series, window: int = 14) -> pd.Series:
    """ATR proxy from closes only (loaders carry Close). mean(|Δ|) rolling."""
    tr = close.diff().abs()
    return tr.rolling(window).mean().bfill()


def load_strategies() -> dict[str, type[Strategy]]:
    # import all sibling modules so @register runs
    package = "app.strategies"
    try:
        mod = importlib.import_module(package)
        for info in pkgutil.iter_modules(mod.__path__):
            if info.name in ("base",):
                continue
            try:
                importlib.import_module(f"{package}.{info.name}")
            except Exception:
                pass
    except Exception:
        pass
    # ensure builtins imported even if discovery failed
    for m in ("buy_hold", "bollinger", "atr_trend", "seasonal",
              "ts_momentum", "spreads"):
        try:
            importlib.import_module(f"app.strategies.{m}")
        except Exception:
            pass
    return dict(REGISTRY)
