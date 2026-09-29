"""Forward Performance Testing (paper trading).

A paper run tracks a strategy *forward* from creation: signals are computed
on the latest yfinance data (with ~400d warmup for indicators) and the run
stores cash/units/equity in data/paper/<id>.json. Call step() daily (or via
cron) to advance: it re-fetches latest closes, applies target
signal x static-weight positions at the close, deducts costs, and appends
an equity point. No real orders — long/flat futures-style proxy.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .backtest import backtest_portfolio  # noqa: F401 (re-export convenience)
from .data_loader import load_portfolio
from .energy_universe import normalize_symbol
from .strategies.base import load_strategies

ROOT = Path(__file__).resolve().parent.parent
PAPER_DIR = ROOT / "data" / "paper"
PAPER_DIR.mkdir(parents=True, exist_ok=True)
WARMUP_DAYS = 400


def _path(rid: str) -> Path:
    return PAPER_DIR / f"{rid}.json"


def _compute_signals(strategy_name: str, prices: pd.DataFrame, params: dict) -> pd.DataFrame:
    reg = load_strategies()
    if strategy_name not in reg:
        raise ValueError(f"unknown strategy '{strategy_name}'. Available: {sorted(reg)}")
    strat = reg[strategy_name]()
    merged = {**strat.defaults, **(params or {})}
    try:
        out = strat.portfolio_signal(prices, merged)
    except NotImplementedError:
        out = None
    if out is not None:
        sigs = out.reindex(prices.index).fillna(0).clip(0, 1).astype(int)
        return sigs.reindex(columns=prices.columns, fill_value=0), merged
    sigs = pd.DataFrame(
        {t: strat.signal(prices[t].dropna(), merged).reindex(prices.index).fillna(0)
         for t in prices.columns}
    )
    return sigs, merged


def _static_weights(tickers: list[str], weights: dict | None) -> dict:
    if not weights:
        return {t: 1.0 / len(tickers) for t in tickers}
    tot = sum(weights.get(t, 0) for t in tickers) or 1.0
    return {t: weights.get(t, 0) / tot for t in tickers}


def create_run(tickers: list[str], strategy: str, params: dict | None = None,
               initial_capital: float = 1_000_000.0, weights: dict | None = None,
               fee_bps: float = 5.0, slippage_bps: float = 5.0) -> dict:
    syms = [normalize_symbol(t) for t in tickers]
    if not syms:
        raise ValueError("need at least one ticker")
    warmup_start = (date.today() - timedelta(days=WARMUP_DAYS)).isoformat()
    px, prov = load_portfolio(syms, start=warmup_start)
    sigs, merged = _compute_signals(strategy, px, params or {})
    last_date = px.index[-1].strftime("%Y-%m-%d")
    last_px = {t: float(px[t].iloc[-1]) for t in px.columns}
    sw = _static_weights(list(px.columns), weights)
    rid = uuid.uuid4().hex[:8]
    run = {
        "id": rid,
        "created": date.today().isoformat(),
        "tickers": list(px.columns),
        "strategy": strategy,
        "params": merged,
        "initial_capital": initial_capital,
        "cash": initial_capital,
        "units": {t: 0.0 for t in px.columns},
        "static_weights": sw,
        "fee_bps": fee_bps,
        "slippage_bps": slippage_bps,
        "last_date": last_date,
        "last_prices": last_px,
        "provenance": prov,
        "status": "open",
        "history": [{"date": last_date, "equity": round(initial_capital, 2),
                     "cash": round(initial_capital, 2), "note": "created (flat)"}],
        "trades": 0,
    }
    _path(rid).write_text(json.dumps(run, indent=2))
    return run


def _load(rid: str) -> dict:
    p = _path(rid)
    if not p.exists():
        raise ValueError(f"unknown paper run '{rid}'")
    return json.loads(p.read_text())


def step_run(rid: str) -> dict:
    run = _load(rid)
    if run["status"] != "open":
        raise ValueError(f"run {rid} is {run['status']}")
    warmup_start = (date.today() - timedelta(days=WARMUP_DAYS)).isoformat()
    px, prov = load_portfolio(run["tickers"], start=warmup_start)
    sigs, _ = _compute_signals(run["strategy"], px, run["params"])
    cur_date = px.index[-1].strftime("%Y-%m-%d")
    if cur_date <= run["last_date"] and len(run["history"]) > 1:
        run["note"] = f"already up to date ({run['last_date']})"
        return run
    if cur_date <= run["last_date"]:
        # first step with no new bar yet: still record signal state
        pass
    prices = {t: float(px[t].iloc[-1]) for t in px.columns}
    target_row = sigs.iloc[-1]
    cost_rate = (run["fee_bps"] + run["slippage_bps"]) / 10_000.0
    port_val = run["cash"] + sum(run["units"].get(t, 0.0) * prices[t] for t in px.columns)
    new_units: dict[str, float] = {}
    turnover_value = 0.0
    for t in px.columns:
        tgt_val = float(target_row.get(t, 0)) * run["static_weights"].get(t, 0) * port_val
        cur_val = run["units"].get(t, 0.0) * prices[t]
        turnover_value += abs(tgt_val - cur_val)
        new_units[t] = tgt_val / prices[t] if prices[t] else 0.0
    cost = turnover_value * cost_rate
    # cash adjusts by net sales minus cost: cash += (old_value - new_value) - cost
    old_val = sum(run["units"].get(t, 0.0) * prices[t] for t in px.columns)
    new_val = sum(new_units[t] * prices[t] for t in px.columns)
    run["cash"] = run["cash"] + (old_val - new_val) - cost
    run["units"] = new_units
    equity = run["cash"] + new_val
    if cur_date != run["last_date"]:
        run["history"].append({
            "date": cur_date,
            "equity": round(equity, 2),
            "cash": round(run["cash"], 2),
            "cost": round(cost, 2),
            "signal": {t: int(target_row.get(t, 0)) for t in px.columns},
        })
        if turnover_value > 0:
            run["trades"] += 1
    run["last_date"] = cur_date
    run["last_prices"] = prices
    run["provenance"] = prov
    run.pop("note", None)
    _path(rid).write_text(json.dumps(run, indent=2))
    return run


def list_runs() -> list[dict]:
    out = []
    for p in sorted(PAPER_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            r = json.loads(p.read_text())
            eq = r["history"][-1]["equity"] if r["history"] else r["initial_capital"]
            out.append({"id": r["id"], "created": r["created"], "tickers": r["tickers"],
                        "strategy": r["strategy"], "status": r["status"],
                        "last_date": r["last_date"], "equity": eq,
                        "return_pct": round((eq / r["initial_capital"] - 1) * 100, 2),
                        "steps": len(r["history"])})
        except Exception:
            continue
    return out


def close_run(rid: str) -> dict:
    run = _load(rid)
    run["status"] = "closed"
    _path(rid).write_text(json.dumps(run, indent=2))
    return run


def delete_run(rid: str) -> None:
    _path(rid).unlink(missing_ok=True)
