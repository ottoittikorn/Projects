"""Screener and CFD-risk metrics. Every function takes prices in standard units and returns plain pandas."""
import numpy as np
import pandas as pd
from scipy import stats

from .quality import simple_returns

TRADING_DAYS = 252


def log_returns(price):
    """Daily log returns; NaN wherever either price is <= 0."""
    p = price.where(price > 0)
    return np.log(p / p.shift())


def trailing(s, years=None, months=None):
    """The last `years`/`months` of a series, measured back from its own last date."""
    s = s.dropna()
    start = s.index[-1] - pd.DateOffset(years=years or 0, months=months or 0)
    return s[s.index > start]


def period_return(price, months):
    """% change from the last price on or before `months` ago to the latest price."""
    p = price.dropna()
    then = p.asof(p.index[-1] - pd.DateOffset(months=months))
    return p.iloc[-1] / then - 1 if pd.notna(then) and then > 0 else np.nan


def annualised_vol(price, years=1, jumps=None):
    """Standard deviation of daily log returns, scaled to a year by sqrt(252).

    `jumps`: dates to drop first, e.g. suspected contract-roll jumps that no trader earned.
    """
    r = trailing(log_returns(price), years=years)
    if jumps is not None:
        r = r.drop(r.index.intersection(jumps))
    return r.std() * np.sqrt(TRADING_DAYS)


def max_drawdown(price):
    """Worst peak-to-trough fall within the series."""
    p = price.dropna()
    return (p / p.cummax() - 1).min()


def trend(price):
    """Price relative to its 50- and 200-day moving averages, plus a simple regime label."""
    p = price.dropna()
    ma50, ma200 = p.rolling(50).mean().iloc[-1], p.rolling(200).mean().iloc[-1]
    last = p.iloc[-1]
    if last > ma50 > ma200:
        label = "Uptrend"
    elif last < ma50 < ma200:
        label = "Downtrend"
    else:
        label = "Mixed"
    return {"vs_50d": last / ma50 - 1, "vs_200d": last / ma200 - 1, "50d_vs_200d": ma50 / ma200 - 1, "trend": label}


def screener_row(price, jumps=None):
    """All daily screener statistics for one commodity. `jumps`: suspected-jump dates (see quality.py)."""
    p = price.dropna()
    r1y = trailing(simple_returns(p), years=1)
    return pd.Series({
        "last": p.iloc[-1],
        "as_of": p.index[-1].date(),
        "vol_1y": annualised_vol(p, 1),
        "vol_1y_ex_jumps": annualised_vol(p, 1, jumps),
        "vol_5y": annualised_vol(p, 5),
        "avg_daily_move": r1y.abs().mean(),
        "ret_1m": period_return(p, 1),
        "ret_3m": period_return(p, 3),
        "ret_1y": period_return(p, 12),
        "ret_5y": period_return(p, 60),
        "max_dd_5y": max_drawdown(trailing(p, years=5)),
        **trend(p),
    }, name=price.name)


def screener_table(prices, jumps=None):
    """One row per commodity column of a wide price DataFrame. `jumps`: {column: dates} to drop from vol."""
    jumps = jumps or {}
    return pd.DataFrame([screener_row(prices[c], jumps.get(c)) for c in prices.columns])


def panel_log_returns(prices):
    """Log returns of each column on its own trading days, then aligned.

    Aluminium (LME, London) and the NYMEX/COMEX contracts have different holidays. Taking returns on
    the joined panel would turn every holiday in either calendar into a missing return for both.
    """
    return pd.concat([log_returns(prices[c].dropna()) for c in prices], axis=1)


def rolling_vol(prices, window=63):
    """Rolling annualised volatility (63 trading days is about one quarter)."""
    return pd.concat([log_returns(prices[c].dropna()).rolling(window).std() for c in prices], axis=1) \
        * np.sqrt(TRADING_DAYS)


def return_correlation(prices, years=5):
    """Correlation of daily log returns over the last `years`, on days where both series traded."""
    r = panel_log_returns(prices)
    return r[r.index > r.index.max() - pd.DateOffset(years=years)].corr()


def seasonality(monthly_price, start="1990"):
    """Average month-on-month return by calendar month, with t-stat and hit rate.

    Pink Sheet prices are monthly averages, so a 'month' return compares one month's average with
    the previous month's. That smooths out noise but also lags turning points.
    """
    r = monthly_price[start:].pct_change().dropna()
    g = r.groupby(r.index.month)
    out = pd.DataFrame({
        "mean": g.mean(),
        "median": g.median(),
        "hit_rate": g.apply(lambda x: (x > 0).mean()),
        "n": g.size(),
    })
    out["t_stat"] = out["mean"] / (g.std() / np.sqrt(out["n"]))
    out["p_value"] = 2 * stats.t.sf(out["t_stat"].abs(), out["n"] - 1)
    out.index.name = "month"
    return out


def seasonality_table(monthly_prices, start="1990", stat="mean"):
    """Commodities x months grid of one seasonality statistic."""
    return pd.DataFrame({c: seasonality(monthly_prices[c].dropna(), start)[stat] for c in monthly_prices}).T


# ---------------------------------------------------------------- CFD risk
def cfd_risk(price, leverage, years=5, jumps=None):
    """Daily moves translated into % of the margin a leveraged CFD position ties up.

    With leverage L, margin is 1/L of the position, so a 1% price move is L% of margin. Under FCA
    rules a broker closes positions when equity falls to 50% of required margin, so a move of 0.5/L
    against an account holding only the margin triggers a close-out.
    `jumps`: suspected roll dates, excluded from the "normal" stats but kept in the worst case.
    """
    r_all = trailing(simple_returns(price), years=years).dropna()
    r = r_all.drop(r_all.index.intersection(jumps)) if jumps is not None else r_all
    a = r.abs()
    return pd.Series({
        "leverage": leverage,
        "avg_move_x_lev": a.mean() * leverage,
        "p99_move_x_lev": a.quantile(0.99) * leverage,
        "worst_day_x_lev": a.max() * leverage,
        "worst_day_incl_jumps_x_lev": r_all.abs().max() * leverage,
        "days_move_>=_half_margin": (a >= 0.5 / leverage).mean(),
        "days_move_>=_full_margin": int((r_all.abs() >= 1 / leverage).sum()),
        "excess_kurtosis": stats.kurtosis(r),
    }, name=price.name)


def weekend_gaps(ohlc, years=5, jumps=None):
    """|Monday open / Friday close - 1|, the move you cannot react to while the market is shut.

    yfinance's Close is the official settlement, and trading continues for a while after it, so even
    weekday opens differ from the prior close. The weekday gap is reported alongside as the baseline.
    """
    df = trailing(ohlc["Close"], years=years).to_frame("close").join(ohlc["Open"])
    gap = (df["Open"] / df["close"].shift() - 1).abs()
    if jumps is not None:
        gap = gap.drop(gap.index.intersection(jumps))
    after_weekend = df.index.to_series().diff().dt.days >= 3
    weekend, weekday = gap[after_weekend].dropna(), gap[~after_weekend].dropna()
    return pd.Series({"mean_weekend_gap": weekend.mean(), "mean_weekday_gap": weekday.mean(),
                      "p95_weekend_gap": weekend.quantile(0.95), "max_weekend_gap": weekend.max()})


def monthly_seasonal_strength(monthly_price, start="1990"):
    """How seasonal a commodity is: spread between best and worst month, and count of months with p < 0.05."""
    s = seasonality(monthly_price.dropna(), start)
    return pd.Series({"best_minus_worst_month": s["mean"].max() - s["mean"].min(),
                      "months_p<0.05": int((s["p_value"] < 0.05).sum())})
