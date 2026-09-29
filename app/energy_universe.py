"""LNG / gas benchmark universe (yfinance-native).

Unlike NGX (.LG, currently delisted on Yahoo), these all resolve on yfinance
(verified 2026-09-29):
  TTF=F  Dutch TTF front-month (EU benchmark, NYM)
  NG=F   Henry Hub front-month (US benchmark, NYM)
  HH=F   Henry Hub spot-ish (sparse, NYM)
  JKM=F  Platts JKM Asian LNG spot (NYM)
  NBP=F  UK NBP front-month (NYM)
  BZ=F   Brent crude (oil-link context)
  UNG    US Natural Gas Fund ETF (equity wrapper)
  LNG    Cheniere Energy (US LNG bellwether equity)
"""

ENERGY_UNIVERSE = [
    {"symbol": "TTF=F", "name": "Dutch TTF Natural Gas front-month", "region": "EU", "kind": "benchmark", "liquid": True},
    {"symbol": "NG=F", "name": "Henry Hub Natural Gas front-month (use as HH proxy)", "region": "US", "kind": "benchmark", "liquid": True},
    {"symbol": "HH=F", "name": "Henry Hub spot (sparse quote — use NG=F instead)", "region": "US", "kind": "benchmark", "liquid": False},
    {"symbol": "JKM=F", "name": "Platts JKM Asian LNG spot", "region": "Asia", "kind": "benchmark", "liquid": True},
    {"symbol": "NBP=F", "name": "UK NBP Natural Gas front-month", "region": "UK", "kind": "benchmark", "liquid": True},
    {"symbol": "BZ=F", "name": "Brent Crude front-month (oil-link)", "region": "Global", "kind": "context", "liquid": True},
    {"symbol": "UNG", "name": "United States Natural Gas Fund", "region": "US", "kind": "etf", "liquid": True},
    {"symbol": "LNG", "name": "Cheniere Energy (LNG equity)", "region": "US", "kind": "equity", "liquid": True},
]


def normalize_symbol(s: str) -> str:
    """Pass through yfinance symbols verbatim (upper-cased, trimmed)."""
    s = s.strip()
    # equities -> upper; futures keep =F upper already
    if "=" in s or "^" in s:
        return s.strip().upper()
    return s.strip().upper()


def safe_filename(symbol: str) -> str:
    return symbol.replace("=", "_EQ").replace("^", "").replace(".", "_").replace("/", "_").replace(" ", "")
