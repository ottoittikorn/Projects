"""Fetchers for each free data source, with a local cache in data/raw/.

Each fetcher returns data in the source's own units; loader.py converts to standard units.
Cached files are reused until they are older than the source's refresh interval, so
re-running a notebook does not hit the websites again.
"""
import io
import os
import re
import time
from datetime import datetime

import pandas as pd
import requests
from dotenv import find_dotenv, load_dotenv

from .config import RAW_DIR

load_dotenv(find_dotenv(usecwd=True))  # finds the repo-level .env from any notebook folder

USER_AGENT = "Mozilla/5.0 (personal commodity research project; low-volume, cached)"
TIMEOUT = 60


class SourceError(RuntimeError):
    """A source returned something we could not use."""


class LayoutChangedError(SourceError):
    """A web page or file no longer has the structure the parser expects."""


def _is_fresh(path, max_age_hours):
    return path.exists() and (time.time() - path.stat().st_mtime) < max_age_hours * 3600


def _get(url, **kwargs):
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    return r


# ---------------------------------------------------------------- yfinance continuous futures
def fetch_yahoo(ticker, max_age_hours=12):
    """Full daily OHLCV history of a yfinance continuous front-month future."""
    path = RAW_DIR / "yahoo" / f"{ticker}.csv"
    if not _is_fresh(path, max_age_hours):
        import yfinance as yf

        df = yf.Ticker(ticker).history(period="max", auto_adjust=False)
        if df.empty:
            raise SourceError(f"yfinance returned no data for {ticker}")
        df.index = df.index.tz_localize(None).normalize()
        path.parent.mkdir(parents=True, exist_ok=True)
        df[["Open", "High", "Low", "Close", "Volume"]].to_csv(path)
    return pd.read_csv(path, index_col=0, parse_dates=True)


# ---------------------------------------------------------------- Westmetall (LME settlement)
WESTMETALL_URL = "https://www.westmetall.com/en/markdaten.php"
WESTMETALL_FIRST_YEAR = 2008  # earliest year the site offers
WESTMETALL_DELAY_S = 3        # pause between live requests


def _parse_westmetall(html, field, year):
    """One year's table -> DataFrame[cash, 3m, stock]. Raises LayoutChangedError if the page changed."""
    where = f"{WESTMETALL_URL}?action=table&field={field}&year={year}"
    try:
        tables = pd.read_html(io.StringIO(html))
    except ValueError as e:
        raise LayoutChangedError(f"No HTML table found at {where}. Open it in a browser to check.") from e
    wanted = {"cash": "Cash-Settlement", "3m": "3-month", "stock": "stock"}
    for t in tables:
        cols = {name: next((c for c in t.columns if label in str(c)), None) for name, label in wanted.items()}
        if "date" in t.columns and all(cols.values()):
            break
    else:
        raise LayoutChangedError(
            f"Westmetall layout changed: expected a table with 'date', 'Cash-Settlement', '3-month' and "
            f"'stock' columns at {where}, got {[list(t.columns) for t in tables]}. Update _parse_westmetall."
        )
    dates = pd.to_datetime(t["date"], format="%d. %B %Y", errors="coerce")
    if dates.isna().mean() > 0.05:
        raise LayoutChangedError(f"Westmetall date format changed at {where}: e.g. {t['date'].iloc[0]!r}")
    out = pd.DataFrame(
        {name: pd.to_numeric(t[col].astype(str).str.replace(",", ""), errors="coerce") for name, col in cols.items()}
    )
    out.index = dates
    return out[out.index.notna()].sort_index()


def fetch_westmetall(field, start_year=WESTMETALL_FIRST_YEAR):
    """Daily LME official cash and 3-month settlement prices (USD/t) and LME stocks (t).

    One page per calendar year, cached as data/raw/westmetall/<field>_<year>.csv. Past years never
    change, so they are downloaded once; the current year is refreshed after 12 hours.
    """
    this_year = datetime.now().year
    frames = []
    for year in range(start_year, this_year + 1):
        path = RAW_DIR / "westmetall" / f"{field}_{year}.csv"
        if path.exists() and (year < this_year or _is_fresh(path, 12)):
            frames.append(pd.read_csv(path, index_col=0, parse_dates=True))
            continue
        time.sleep(WESTMETALL_DELAY_S)
        html = _get(WESTMETALL_URL, params={"action": "table", "field": field, "year": year}).text
        df = _parse_westmetall(html, field, year)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path)
        frames.append(df)
    out = pd.concat(frames).sort_index()
    return out[~out.index.duplicated(keep="last")]


# ---------------------------------------------------------------- FRED
def fetch_fred(series_id, max_age_hours=24):
    """A FRED series. Uses fredapi when FRED_API_KEY is set, otherwise FRED's public CSV download."""
    path = RAW_DIR / "fred" / f"{series_id}.csv"
    if not _is_fresh(path, max_age_hours):
        key = os.getenv("FRED_API_KEY")
        if key:
            from fredapi import Fred

            s = Fred(api_key=key).get_series(series_id)
        else:  # keyless fallback; same data, but no rate-limit guarantees
            r = _get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": series_id})
            if not r.text.startswith("observation_date"):
                raise SourceError(f"FRED has no series {series_id!r}")
            s = pd.read_csv(io.StringIO(r.text), index_col=0, parse_dates=True).iloc[:, 0]
        path.parent.mkdir(parents=True, exist_ok=True)
        s.rename(series_id).to_csv(path)
    return pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]


# ---------------------------------------------------------------- World Bank Pink Sheet
WORLDBANK_PAGE = "https://www.worldbank.org/en/research/commodity-markets"


def worldbank_monthly_url():
    """Find the current monthly Pink Sheet link on the Commodity Markets page (it changes each release)."""
    html = _get(WORLDBANK_PAGE).text
    links = re.findall(r'href="([^"]*CMO-Historical-Data-Monthly\.xlsx)"', html)
    if not links:
        raise LayoutChangedError(
            f"No 'CMO-Historical-Data-Monthly.xlsx' link found on {WORLDBANK_PAGE}. "
            "The page layout changed: find the 'Monthly prices' Excel link by hand."
        )
    return links[0]


def fetch_worldbank(max_age_hours=24 * 7):
    """All monthly Pink Sheet prices (nominal USD, monthly averages) as one wide DataFrame."""
    path = RAW_DIR / "worldbank" / "CMO-Historical-Data-Monthly.xlsx"
    if not _is_fresh(path, max_age_hours):
        content = _get(worldbank_monthly_url()).content
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    raw = pd.read_excel(path, sheet_name="Monthly Prices", header=None)
    header_rows = raw.index[raw.eq("Crude oil, Brent").any(axis=1)]
    if len(header_rows) == 0:
        raise LayoutChangedError("Pink Sheet 'Monthly Prices' sheet has no header row containing 'Crude oil, Brent'.")
    h = header_rows[0]
    df = raw.iloc[h + 2:].copy()  # header row, then a units row, then data
    df.columns = ["month"] + [str(c).strip() for c in raw.iloc[h, 1:]]
    df = df[df["month"].astype(str).str.match(r"^\d{4}M\d{2}$")]
    df.index = pd.to_datetime(df.pop("month"), format="%YM%m")
    df.index.name = "date"
    return df.apply(pd.to_numeric, errors="coerce")  # '…' marks missing values
