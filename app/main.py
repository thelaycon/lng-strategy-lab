"""FastAPI dashboard for Energy benchmark strategy testing (yfinance-based)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .backtest import backtest_portfolio
from .data_loader import load_portfolio, save_uploaded_csv
from .energy_universe import ENERGY_UNIVERSE, normalize_symbol
from .metrics import summarize
from .strategies.base import load_strategies
from . import paper as paper_engine

app = FastAPI(title="Energy Strategy Lab", version="0.3.0")

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
STATIC.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class BacktestRequest(BaseModel):
    tickers: list[str] = Field(default=["TTF=F", "NG=F", "JKM=F"])
    strategy: str = "atr_trailing_trend"
    params: dict = Field(default={"entry": 20, "atr_window": 14, "atr_mult": 3.0})
    start: Optional[str] = None
    end: Optional[str] = None
    initial_capital: float = 1_000_000.0
    weights: Optional[dict[str, float]] = None
    fee_bps: float = 5.0
    slippage_bps: float = 5.0


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text()


@app.get("/api/universe")
def universe():
    return {"tickers": ENERGY_UNIVERSE, "source": "yfinance + local CSV fallback"}


@app.get("/api/strategies")
def strategies():
    reg = load_strategies()
    return {
        "strategies": [
            {"name": cls.name, "description": cls.description, "defaults": cls.defaults}
            for cls in reg.values()
        ]
    }


@app.get("/api/prices")
def prices(tickers: str, start: Optional[str] = None, end: Optional[str] = None):
    names = [t.strip() for t in tickers.split(",") if t.strip()]
    try:
        px, prov = load_portfolio(names, start=start, end=end)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    out = px.reset_index().rename(columns={"index": "Date"})
    out["Date"] = pd.to_datetime(out["Date"]).dt.strftime("%Y-%m-%d")
    return {"prices": out.to_dict("records"), "provenance": prov}


@app.post("/api/backtest")
def backtest(req: BacktestRequest):
    reg = load_strategies()
    if req.strategy not in reg:
        raise HTTPException(400, f"unknown strategy '{req.strategy}'. Available: {sorted(reg)}")
    try:
        px, prov = load_portfolio(req.tickers, start=req.start, end=req.end)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    strat = reg[req.strategy]()
    merged_params = {**strat.defaults, **(req.params or {})}
    spread_sigs = None
    try:
        spread_sigs = strat.portfolio_signal(px, merged_params)
    except NotImplementedError:
        spread_sigs = None
    if spread_sigs is not None:
        sigs = spread_sigs.reindex(px.index).fillna(0).clip(0, 1).astype(int)
        sigs = sigs.reindex(columns=px.columns, fill_value=0)
    else:
        sigs = pd.DataFrame({t: strat.signal(px[t].dropna(), merged_params).reindex(px.index).fillna(0) for t in px.columns})
    res = backtest_portfolio(px, sigs, req.initial_capital, req.weights, req.fee_bps, req.slippage_bps)
    stats = summarize(res["equity"], req.initial_capital, res["num_trades"])
    if "error" in stats:
        raise HTTPException(400, f"backtest failed: {stats['error']} (tickers used: {list(px.columns)})")
    eq = res["equity"]
    curve = [{"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)} for d, v in eq.items()]
    # per-ticker buy&hold normalisation for chart context
    norm = (px / px.iloc[0] * req.initial_capital).round(2)
    sample_idx = norm.index[:: max(1, len(norm) // 200)]
    underlyings = {
        t: [{"date": d.strftime("%Y-%m-%d"), "value": float(norm.loc[d, t])} for d in sample_idx]
        for t in norm.columns
    }
    return {
        "strategy": req.strategy,
        "params": merged_params,
        "metrics": stats,
        "provenance": prov,
        "warnings": [f"{k}: {v}" for k, v in prov.items() if v.startswith(("SKIPPED", "FAILED"))],
        "tickers_used": list(px.columns),
        "weights": res["static_weights"],
        "entries_per_ticker": res["entries_per_ticker"],
        "equity_curve": curve[:: max(1, len(curve) // 400)],
        "underlyings": underlyings,
    }


@app.post("/api/data/upload")
async def upload(ticker: str, file: UploadFile = File(...)):
    content = await file.read()
    try:
        p = save_uploaded_csv(ticker, content)
    except Exception as exc:
        raise HTTPException(400, f"invalid CSV (need Date,Close columns): {exc}")
    return {"saved": str(p.name), "ticker": normalize_symbol(ticker)}


class PaperCreate(BaseModel):
    tickers: list[str] = Field(default=["TTF=F", "NG=F", "JKM=F"])
    strategy: str = "atr_trailing_trend"
    params: dict = Field(default={})
    initial_capital: float = 1_000_000.0
    weights: Optional[dict[str, float]] = None
    fee_bps: float = 5.0
    slippage_bps: float = 5.0


@app.post("/api/paper")
def paper_create(req: PaperCreate):
    try:
        return paper_engine.create_run(req.tickers, req.strategy, req.params,
                                       req.initial_capital, req.weights,
                                       req.fee_bps, req.slippage_bps)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.get("/api/paper")
def paper_list():
    return {"runs": paper_engine.list_runs()}


@app.get("/api/paper/{rid}")
def paper_get(rid: str):
    try:
        return paper_engine._load(rid)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@app.post("/api/paper/{rid}/step")
def paper_step(rid: str):
    try:
        return paper_engine.step_run(rid)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/paper/{rid}/close")
def paper_close(rid: str):
    try:
        return paper_engine.close_run(rid)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@app.delete("/api/paper/{rid}")
def paper_delete(rid: str):
    paper_engine.delete_run(rid)
    return {"deleted": rid}
