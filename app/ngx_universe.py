"""Curated NGX universe.

Yahoo/yfinance historically used the `.LG` (Lagos) suffix for NGX names,
e.g. DANGCEM.LG. As of Sep 2026 Yahoo returns "symbol may be delisted"
for these, so the loader auto-tries yfinance first, then local CSV
cache/sample data. Keep this list as the canonical human-friendly names.
"""

NGX_UNIVERSE = [
    {"base": "DANGCEM", "name": "Dangote Cement Plc", "sector": "Industrial Goods"},
    {"base": "MTNN", "name": "MTN Nigeria Communications Plc", "sector": "Telecoms"},
    {"base": "GTCO", "name": "Guaranty Trust Holding Company Plc", "sector": "Banking"},
    {"base": "ZENITHBANK", "name": "Zenith Bank Plc", "sector": "Banking"},
    {"base": "SEPLAT", "name": "Seplat Energy Plc", "sector": "Oil & Gas"},
    {"base": "BUACEMENT", "name": "BUA Cement Plc", "sector": "Industrial Goods"},
    {"base": "BUAFOODS", "name": "BUA Foods Plc", "sector": "Consumer Goods"},
    {"base": "NESTLE", "name": "Nestle Nigeria Plc", "sector": "Consumer Goods"},
    {"base": "ACCESSCORP", "name": "Access Holdings Plc", "sector": "Banking"},
    {"base": "UBA", "name": "United Bank for Africa Plc", "sector": "Banking"},
    {"base": "FBNH", "name": "FBN Holdings Plc", "sector": "Banking"},
    {"base": "STANBIC", "name": "Stanbic IBTC Holdings Plc", "sector": "Banking"},
    {"base": "DANGSUGAR", "name": "Dangote Sugar Refinery Plc", "sector": "Consumer Goods"},
    {"base": "NASCON", "name": "NASCON Allied Industries Plc", "sector": "Consumer Goods"},
    {"base": "WAPCO", "name": "Lafarge Africa Plc", "sector": "Industrial Goods"},
]

NGX_SUFFIX = ".LG"


def to_yahoo(base: str) -> str:
    base = base.strip().upper()
    if "." in base:
        return base
    return base + NGX_SUFFIX


def to_base(symbol: str) -> str:
    return symbol.strip().upper().split(".")[0]
