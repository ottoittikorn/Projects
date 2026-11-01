"""One entry point for prices: load_price(commodity, source).

Whatever the source, the result is a float Series in the commodity's standard unit, indexed by
date, named after the commodity, with .attrs describing where it came from. Analysis code only
ever calls these functions, so swapping a source is a one-word change.
"""
import pandas as pd

from .config import COMMODITIES, DAILY_SOURCE, MONTHLY_SOURCE, PROCESSED_DIR
from .sources import fetch_fred, fetch_westmetall, fetch_worldbank, fetch_yahoo

SOURCES = ("yahoo", "lme_cash", "lme_3m", "fred", "worldbank")
MONTHLY_SOURCES = ("fred", "worldbank")


def _raw(source, spec_id):
    if source == "yahoo":
        return fetch_yahoo(spec_id)["Close"]
    if source in ("lme_cash", "lme_3m"):
        return fetch_westmetall(spec_id)["cash" if source == "lme_cash" else "3m"]
    if source == "fred":
        return fetch_fred(spec_id)
    if source == "worldbank":
        wb = fetch_worldbank()
        if spec_id not in wb.columns:
            raise KeyError(f"Pink Sheet has no column {spec_id!r}; columns include {list(wb.columns)[:10]}...")
        return wb[spec_id]
    raise ValueError(f"Unknown source {source!r}; choose from {SOURCES}")


def load_price(key, source=None):
    """Price history of one commodity from one source, in the commodity's standard unit."""
    c = COMMODITIES[key]
    source = source or DAILY_SOURCE.get(key, MONTHLY_SOURCE)
    if source not in c.sources:
        raise ValueError(f"{key} is not available from {source!r}; available: {list(c.sources)}")
    spec = c.sources[source]
    s = (_raw(source, spec.id).astype(float) * spec.factor).dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")].rename(key)
    s.index.name = "date"
    s.attrs = {"source": source, "id": spec.id, "unit": c.unit,
               "freq": "M" if source in MONTHLY_SOURCES else "D"}
    return s


def load_panel(keys, source=None):
    """Wide DataFrame of several commodities. source: one name for all, a {key: source} dict, or None for defaults."""
    def pick(k):
        return source.get(k) if isinstance(source, dict) else source
    return pd.concat([load_price(k, pick(k)) for k in keys], axis=1)


def load_ohlc(key):
    """Daily OHLCV from yfinance in standard units (Open/High/Low/Close scaled, Volume untouched)."""
    spec = COMMODITIES[key].sources["yahoo"]
    df = fetch_yahoo(spec.id).copy()
    df[["Open", "High", "Low", "Close"]] *= spec.factor
    return df


def build_panels(keys):
    """Build the daily (DAILY_SOURCE) and monthly (MONTHLY_SOURCE) panels and save them to data/processed/."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    daily = load_panel(keys, DAILY_SOURCE)
    monthly = load_panel(keys, MONTHLY_SOURCE)
    daily.to_csv(PROCESSED_DIR / "daily_prices.csv")
    monthly.to_csv(PROCESSED_DIR / "monthly_prices.csv")
    return daily, monthly


def read_panel(name):
    """A panel saved by build_panels: 'daily' or 'monthly'."""
    path = PROCESSED_DIR / f"{name}_prices.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run notebooks/01_data_sources.ipynb first")
    return pd.read_csv(path, index_col=0, parse_dates=True)
