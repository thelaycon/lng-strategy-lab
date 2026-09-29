import pandas as pd
from app.backtest import backtest_portfolio
from app.data_loader import load_portfolio
from app.metrics import summarize
from app.strategies.base import load_strategies

SINGLES = {"buy_hold", "bollinger_mean_reversion", "atr_trailing_trend",
           "seasonal_storage", "ts_momentum"}
SPREADS = {"jkm_ttf_arb", "ttf_nbp_basis"}


def _signals_for(strat, px, params):
    try:
        out = strat.portfolio_signal(px, params)
    except NotImplementedError:
        out = None
    if out is not None:
        return out
    return pd.DataFrame({t: strat.signal(px[t], params) for t in px.columns})


def test_all_strategies_run():
    reg = load_strategies()
    assert SINGLES | SPREADS <= set(reg)
    assert not ({"sma_crossover", "rsi_mean_reversion", "donchian_breakout"} & set(reg))
    px, _ = load_portfolio(["TTF=F", "NG=F", "JKM=F", "NBP=F"], start="2024-01-01")
    assert len(px) > 50
    for name, cls in reg.items():
        s = cls()
        params = dict(s.defaults)
        if s.kind == "spread":
            params.update({"leg_a": "JKM=F" if "jkm" in name else "TTF=F",
                           "leg_b": "TTF=F" if "jkm" in name else "NBP=F"})
        sigs = _signals_for(s, px, params)
        assert set(sigs.columns) == set(px.columns), name
        assert sigs.isin([0, 1]).all().all(), name
        res = backtest_portfolio(px, sigs, 1_000_000, fee_bps=5, slippage_bps=5)
        stats = summarize(res["equity"], 1_000_000, res["num_trades"])
        assert "sharpe" in stats, name
