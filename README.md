# LNG Strategy Lab

Portfolio backtester for **LNG / gas benchmarks (TTF, HH, JKM, NBP)**, data layer **based on yfinance** with local fallback.

## Coverage (verified 2026-09-29, all live on yfinance)

| Symbol | Market | Notes |
|---|---|---|
| `TTF=F` | Dutch TTF front-month (EU) | full 3y history |
| `NG=F` | Henry Hub front-month (US) | full 3y — use as HH proxy |
| `HH=F` | Henry Hub spot | **excluded**: sparse Yahoo quote (~1 bar) — backtests skip it with a warning; use `NG=F` |
| `JKM=F` | Platts JKM Asian LNG spot | full history |
| `NBP=F` | UK NBP front-month | full history |
| `BZ=F` | Brent (oil-link context) | full history |
| `UNG`, `LNG` | ETF / Cheniere equity | full history |

Loader tries yfinance verbatim, falls back to `data/cache/<SAFE>.csv` then
`data/sample/<SAFE>.csv` (`=` → `_EQ`, e.g. `TTF=F` → `TTF_EQF.csv`), and caches
every successful download. `data/sample/` currently holds **real 3y yfinance
history** (except HH=F which is inherently sparse).

## Quickstart

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# open http://localhost:8000  (defaults: TTF=F, NG=F, JKM=F)
pytest -q
```

UI is Tailwind (CDN) + Chart.js, no build step. Tabs: **Backtest** and
**Paper Trading**.

## API

- `GET /api/universe` — LNG benchmark list
- `GET /api/strategies` — registered strategies + defaults
- `GET /api/prices?tickers=TTF=F,NG=F,JKM=F&start=2024-01-01`
- `POST /api/backtest` — `{tickers, strategy, params, start, end, initial_capital, weights, fee_bps, slippage_bps}`
- `POST /api/data/upload?ticker=TTF=F` — upload CSV with `Date,Close`

## Forward Performance Testing (paper trading)

Runs track strategies **forward** from creation (400d warmup, starts flat):

- `POST /api/paper` — `{tickers, strategy, params, initial_capital, weights, fee_bps, slippage_bps}` → run (state in `data/paper/<id>.json`)
- `POST /api/paper/{id}/step` — advance to latest yfinance close (signals × weights, costs deducted, equity appended; no-op if no new bar)
- `GET /api/paper` / `GET /api/paper/{id}` — list / detail with equity history, cash, units
- `POST /api/paper/{id}/close`, `DELETE /api/paper/{id}`

Step daily by hand in the Paper Trading tab, or via cron:
`curl -X POST localhost:8000/api/paper/<id>/step`.

Strategies: trend + range + seasonal + spreads (all long/flat).

| Strategy | Kind | Idea | Defaults |
|---|---|---|---|
| `atr_trailing_trend` | single | breakout + ATR trailing stop (futures CTA staple) | entry 20 / atr 14 / mult 3.0 |
| `ts_momentum` | single | trailing-return momentum | lookback 90 / thresh 0 |
| `bollinger_mean_reversion` | single | range dip-buy at lower band | 20 / 2σ / exit mid |
| `seasonal_storage` | single | long Nov–Mar withdrawal season | long_months 11,12,1,2,3 |
| `buy_hold` | single | benchmark | — |
| `jkm_ttf_arb` | spread | long cheap / flat rich leg of JKM-TTF z-score | 60d / entry 1.5 / exit 0.5 |
| `ttf_nbp_basis` | spread | same for TTF-NBP | 60d / entry 1.5 / exit 0.5 |

Removed as redundant for gas: `sma_crossover` (covered by ATR/TSMOM),
`donchian_breakout` (strictly dominated by ATR-stop version),
`rsi_mean_reversion` (covered by Bollinger range logic).

## Add your own alpha

Create `app/strategies/custom_<name>.py` with a `@register` class (see README history / `custom_ema_example.py`), restart — it appears in `/api/strategies` and the dashboard.

## Engine notes

Long/flat daily portfolio, static weights (default equal) × 0/1 signals.
Costs default 5+5 bps (futures-like; raise for physical). Metrics: total return,
CAGR, ann. vol, Sharpe, max drawdown, win rate, trades.

Legacy NGX code (`app/ngx_universe.py`, old `data/sample/DANGCEM.csv` etc.) is
kept for reference but no longer the default universe.
