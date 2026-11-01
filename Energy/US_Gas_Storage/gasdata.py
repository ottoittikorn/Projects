"""Shared data helpers for the US gas storage project."""
import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

# Large US metro areas and approximate 2020 metro populations (millions), spread across the
# main gas-heating regions. Used to build a population-weighted degree-day index.
CITIES = {
    "New York": (40.71, -74.01, 19.8), "Los Angeles": (34.05, -118.24, 13.2),
    "Chicago": (41.88, -87.63, 9.6), "Dallas": (32.78, -96.80, 7.6),
    "Houston": (29.76, -95.37, 7.1), "Washington": (38.90, -77.04, 6.4),
    "Philadelphia": (39.95, -75.17, 6.2), "Miami": (25.76, -80.19, 6.1),
    "Atlanta": (33.75, -84.39, 6.1), "Boston": (42.36, -71.06, 4.9),
    "Phoenix": (33.45, -112.07, 4.8), "Detroit": (42.33, -83.05, 4.4),
    "Seattle": (47.61, -122.33, 4.0), "Minneapolis": (44.98, -93.27, 3.7),
    "Denver": (39.74, -104.99, 3.0), "St Louis": (38.63, -90.20, 2.8),
    "Pittsburgh": (40.44, -80.00, 2.4),
}
BASE_TEMP_F = 65  # US convention: heating needed below 65°F, cooling above


def expiry_and_roll_days(trading_days):
    """Henry Hub futures expire 3 business days before the delivery month; the next day is the roll."""
    bday = CustomBusinessDay(calendar=USFederalHolidayCalendar())  # close to, not exactly, the NYMEX calendar
    month_starts = pd.date_range(trading_days[0], trading_days[-1], freq="MS")
    expiries = pd.DatetimeIndex([m - 3 * bday for m in month_starts])
    expiry_days = trading_days[trading_days.searchsorted(expiries, side="left")]
    roll_days = trading_days[trading_days.searchsorted(expiries, side="right")]
    return expiry_days, roll_days


def fetch_degree_days(start, end):
    """Daily population-weighted heating and cooling degree days (°F) from Open-Meteo's free ERA5 archive."""
    lats, lons, pops = zip(*CITIES.values())
    r = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": ",".join(map(str, lats)), "longitude": ",".join(map(str, lons)),
            "start_date": start, "end_date": end, "daily": "temperature_2m_mean",
            "temperature_unit": "fahrenheit", "timezone": "America/New_York",
        },
        timeout=120,
    )
    r.raise_for_status()
    temps = pd.DataFrame(
        {city: loc["daily"]["temperature_2m_mean"] for city, loc in zip(CITIES, r.json())},
        index=pd.to_datetime(r.json()[0]["daily"]["time"]),
    )
    weights = np.array(pops) / sum(pops)
    return pd.DataFrame({
        "hdd": (BASE_TEMP_F - temps).clip(lower=0) @ weights,
        "cdd": (temps - BASE_TEMP_F).clip(lower=0) @ weights,
    })


def surprise_regression(df, surprise="surprise_bcf", y="thu_ret"):
    """Regress the report-day return on a storage surprise; negative slope = market trades the surprise."""
    fit = sm.OLS(df[y], sm.add_constant(df[surprise])).fit(cov_type="HC1")  # robust to fat tails / uneven variance
    signed = df[df[surprise] != 0]
    hit = (np.sign(-signed[surprise]) == np.sign(signed[y])).mean()
    return {"n": len(df), "slope_%_per_10bcf": fit.params[surprise] * 10,
            "t_stat": fit.tvalues[surprise], "p_value": fit.pvalues[surprise],
            "r2": fit.rsquared, "hit_rate": hit}


def rolling_forecast(data, y, x_cols, window=156):
    """Out-of-sample forecast: for each week, fit OLS on the previous `window` weeks only, then predict."""
    X = np.column_stack([np.ones(len(data))] + [data[c].to_numpy(float) for c in x_cols])
    Y = data[y].to_numpy(float)
    preds = np.full(len(data), np.nan)
    for i in range(window, len(data)):
        Xi, Yi = X[i - window : i], Y[i - window : i]
        ok = ~np.isnan(Xi).any(axis=1) & ~np.isnan(Yi)
        if ok.sum() > 50 and not np.isnan(X[i]).any():
            beta = np.linalg.lstsq(Xi[ok], Yi[ok], rcond=None)[0]
            preds[i] = X[i] @ beta
    return pd.Series(preds, index=data.index)
