"""Data-quality checks for continuous futures and scraped series.

yfinance "=F" tickers splice front-month contracts together without adjusting for the price
difference between them, so on roll days the series jumps even if the market did not move.
Those jumps are not P&L anyone earned, so they must be found before computing returns.
"""
import pandas as pd


def simple_returns(price):
    """Daily % change, set to NaN where the previous price was <= 0 (WTI went to -$37.63 in April 2020)."""
    prev = price.shift()
    return (price / prev - 1).where(prev > 0)


def flag_jumps(price, z=6.0, window=63):
    """Days whose return is more than `z` robust standard deviations from normal.

    The scale is a rolling median absolute deviation (MAD), which a single big jump cannot inflate
    the way it inflates a standard deviation. Flagged days are suspects (a roll or a bad print),
    not proof: a real shock looks the same, so check them against a second source.
    """
    r = simple_returns(price)
    mad = r.abs().rolling(window, min_periods=20).median().shift() / 0.6745  # MAD -> sigma
    score = r / mad
    out = pd.DataFrame({"return": r, "robust_z": score})[score.abs() > z]
    # Front-month energy contracts expire in the second half of the month, metals roll every 1-2 months.
    out["late_month"] = out.index.day >= 15
    return out


def calendar_gaps(index, max_days=4):
    """Stretches with no data longer than a long weekend."""
    d = pd.Series(index, index=index).diff().dt.days
    gaps = d[d > max_days]
    return pd.DataFrame({"last_before": [index[index.get_loc(i) - 1] for i in gaps.index],
                         "resumes": gaps.index, "days": gaps.values.astype(int)})


def stale_runs(price, min_len=3):
    """Runs of identical prices on consecutive rows: the contract probably did not trade."""
    same = price.diff().eq(0)
    run_id = (~same).cumsum()
    lengths = same.groupby(run_id).sum() + 1
    starts = price.groupby(run_id).apply(lambda s: s.index[0])
    keep = lengths >= min_len
    return pd.DataFrame({"start": starts[keep].values, "rows": lengths[keep].values.astype(int)})


def quality_summary(ohlc, name):
    """One row of data-quality stats for a yfinance OHLCV frame."""
    close, volume = ohlc["Close"], ohlc["Volume"]
    jumps = flag_jumps(close)
    recent = volume[volume.index > volume.index[-1] - pd.DateOffset(years=1)]
    return pd.Series({
        "first_date": close.index[0].date(),
        "rows": len(close),
        "zero_volume_%": 100 * (volume == 0).mean(),
        "zero_volume_last_1y_%": 100 * (recent == 0).mean(),
        "gaps_>4d": len(calendar_gaps(close.index)),
        "stale_runs_>=3": len(stale_runs(close)),
        "non_positive_prices": int((close <= 0).sum()),
        "suspected_jumps": len(jumps),
    }, name=name)
