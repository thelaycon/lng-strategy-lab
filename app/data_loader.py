"""Data layer: yfinance-first, local CSV fallback.

Flow for each symbol (e.g. TTF=F, NG=F, JKM=F):
  1. Try yfinance verbatim for [start, end].
  2. If empty -> try data/cache/<SAFE>.csv, then data/sample/<SAFE>.csv.
  3. Cache any successful yfinance download to data/cache/.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import yfinance as yf

from .energy_universe import normalize_symbol, safe_filename

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"
SAMPLE_DIR = ROOT / "data" / "sample"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)


def _download_one_yahoo(symbol: str, start: str | None, end: str | None) -> pd.Series | None:
    try:
        df = yf.download(
            symbol, start=start, end=end,
            progress=False, auto_adjust=True, actions=False,
        )
    except Exception as exc:
        log.warning("yfinance error %s: %s", symbol, exc)
        return None
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        for key in ("Close", "Adj Close"):
            if key in df.columns.get_level_values(0):
                s = df[key]
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
                return s.rename(symbol)
        s = df.iloc[:, 0]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        return s.rename(symbol)
    for col in ("Close", "Adj Close", "close"):
        if col in df.columns:
            return df[col].rename(symbol)
    return df.iloc[:, 0].rename(symbol)


def _read_local_csv(symbol: str) -> pd.Series | None:
    fn = safe_filename(symbol) + ".csv"
    for d in (CACHE_DIR, SAMPLE_DIR):
        p = d / fn
        if p.exists():
            try:
                df = pd.read_csv(p, parse_dates=["Date"], index_col="Date")
                col = "Close" if "Close" in df.columns else df.columns[0]
                return df[col].rename(symbol)
            except Exception as exc:
                log.warning("bad csv %s: %s", p, exc)
    return None


def load_portfolio(
    tickers: list[str],
    start: str | None = None,
    end: str | None = None,
    allow_fallback: bool = True,
    min_bars: int = 60,
) -> tuple[pd.DataFrame, dict]:
    """Return (prices DataFrame dates x symbols, provenance dict).

    Series with fewer than `min_bars` valid observations (e.g. HH=F, a sparse
    Yahoo spot quote with ~1 bar) are skipped with a SKIPPED provenance note
    instead of silently dead-weighting the equal-weight portfolio.
    """
    symbols = [normalize_symbol(t) for t in tickers]
    series: dict[str, pd.Series] = {}
    provenance: dict[str, str] = {}
    for sym in symbols:
        s = _download_one_yahoo(sym, start, end)
        if s is not None and len(s.dropna()) >= min_bars:
            series[sym] = s
            provenance[sym] = f"yfinance:{sym}"
            try:
                s.to_csv(CACHE_DIR / (safe_filename(sym) + ".csv"), header=True)
            except Exception:
                pass
            continue
        if s is not None and len(s.dropna()) > 0:
            # live but sparse (e.g. HH=F spot): fall through to local files,
            # which are checked for depth below
            pass
        if allow_fallback:
            local = _read_local_csv(sym)
            if local is not None:
                if start:
                    local = local[local.index >= pd.Timestamp(start)]
                if end:
                    local = local[local.index < pd.Timestamp(end) + pd.Timedelta(days=1)]
                if len(local.dropna()) >= min_bars:
                    series[sym] = local
                    provenance[sym] = "local-csv-fallback"
                    continue
                if len(local.dropna()) > 0:
                    provenance[sym] = (
                        f"SKIPPED: only {len(local.dropna())} bars (min {min_bars}). "
                        + ("HH=F is a sparse Yahoo spot quote — use NG=F (Henry Hub front-month) instead."
                           if sym == "HH=F" else "Symbol has insufficient history for the selected window.")
                    )
                    continue
        if s is not None and len(s.dropna()) > 0:
            provenance[sym] = (
                f"SKIPPED: only {len(s.dropna())} bars from yfinance (min {min_bars}). "
                + ("HH=F is a sparse Yahoo spot quote — use NG=F (Henry Hub front-month) instead."
                   if sym == "HH=F" else "Symbol has insufficient history for the selected window.")
            )
        else:
            provenance[sym] = "FAILED: no yfinance data and no local CSV"
    if not series:
        details = "; ".join(f"{k}: {v}" for k, v in provenance.items())
        raise ValueError(
            "No usable price data for: " + ", ".join(symbols)
            + ". " + details
            + ". Add data/sample/<SYM>.csv or upload via POST /api/data/upload."
        )
    prices = pd.DataFrame(series).sort_index().ffill().dropna(how="all")
    if start:
        prices = prices[prices.index >= pd.Timestamp(start)]
    if end:
        prices = prices[prices.index <= pd.Timestamp(end)]
    return prices, provenance


def save_uploaded_csv(symbol: str, content: bytes) -> Path:
    symbol = normalize_symbol(symbol)
    p = CACHE_DIR / (safe_filename(symbol) + ".csv")
    p.write_bytes(content)
    df = pd.read_csv(p, parse_dates=["Date"], index_col="Date")
    if "Close" not in df.columns:
        df = df.rename(columns={df.columns[0]: "Close"})
        df.to_csv(p)
    return p
