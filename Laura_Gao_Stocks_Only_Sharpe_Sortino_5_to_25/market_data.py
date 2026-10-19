"""Market data sources for the combined Sharpe–Sortino portfolio optimizer.

Yahoo may return partial/empty ticker histories, especially on cloud hosts.  This
adapter diagnoses missing symbols, retries missing ticker histories individually,
and refuses to silently remove requested assets or fabricate unavailable prices.
"""
from __future__ import annotations

import io
from typing import Any

import numpy as np
import pandas as pd
from optimizer import PortfolioError, validate_prices


MIN_PRICES = 127  # 126 daily returns

# A guard against common ETF inputs. This does not replace security-type verification
# for all possible ticker symbols; it prevents the specific separate ETF sleeve
# from accidentally being optimized as an individual stock.
KNOWN_ETFS = frozenset({
    "VTI", "VBR", "VXUS", "SPY", "VOO", "IVV", "ITOT", "SCHB", "SCHD",
    "AVUV", "VB", "IWM", "QQQ", "QQQM", "VT", "VEA", "VWO", "BND",
    "AGG", "SGOV", "SHV", "BIL", "TLT", "IEFA", "IEMG", "SCHX",
})

def validate_stock_only(symbols: list[str]) -> None:
    excluded = sorted({str(t).upper().strip().replace(".", "-") for t in symbols} & KNOWN_ETFS)
    if excluded:
        raise PortfolioError(
            "This optimizer is for individual stocks only; move these ETFs to your "
            "separate ETF allocation: " + ", ".join(excluded) + "."
        )



def parse_tickers(raw: str) -> list[str]:
    # Yahoo Finance uses BRK-B, whereas users often write BRK.B.
    symbols = [s.strip().upper().replace(".", "-") for s in raw.replace("\n", ",").split(",")]
    result = [s for s in symbols if s]
    if len(result) < 2 or len(set(result)) != len(result):
        raise PortfolioError("Enter at least two distinct ticker symbols separated by commas.")
    return result


def load_wide_csv(source: io.BytesIO | str) -> pd.DataFrame:
    try:
        df = pd.read_csv(source, index_col=0)
    except Exception as exc:
        raise PortfolioError(f"Unable to parse the CSV file: {exc}") from exc
    return validate_prices(df)


def _close_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Return a ticker-column frame of *auto-adjusted* closing prices."""
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        levels = raw.columns
        if "Close" in levels.get_level_values(0):
            close = raw.xs("Close", axis=1, level=0)
        elif "Close" in levels.get_level_values(1):
            close = raw.xs("Close", axis=1, level=1)
        else:
            return pd.DataFrame()
    elif "Close" in raw.columns:
        close = raw[["Close"]].copy()
    else:
        return pd.DataFrame()
    if isinstance(close, pd.Series):
        close = close.to_frame()
    close = close.copy()
    close.columns = [str(c).strip().upper().replace(".", "-") for c in close.columns]
    return close


def _to_daily_series(source: pd.Series) -> pd.Series:
    """Keep the source exchange date, not an inferred UTC date."""
    s = pd.to_numeric(source, errors="coerce").copy()
    try:
        dates = pd.DatetimeIndex(pd.to_datetime(s.index, errors="raise"))
        if dates.tz is not None:
            dates = dates.tz_localize(None)
        s.index = dates.normalize()
    except (TypeError, ValueError) as exc:
        raise PortfolioError(f"Yahoo returned dates that cannot be parsed: {exc}") from exc
    s = s.sort_index()
    if s.index.has_duplicates:
        s = s[~s.index.duplicated(keep="last")]
    s = s.replace([np.inf, -np.inf], np.nan)
    # Invalid prices remain missing rather than being imputed.
    return s.where(s > 0)


def _extract_series(raw: Any, ticker: str, *, single: bool = False) -> pd.Series | None:
    frame = _close_frame(raw)
    if frame.empty:
        return None
    ticker = ticker.upper()
    if ticker in frame.columns:
        s = frame[ticker]
    elif single and frame.shape[1] == 1:
        # yf.Ticker.history() normally has a flat "Close" column.
        s = frame.iloc[:, 0]
    else:
        return None
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return _to_daily_series(s).rename(ticker)


def _history_window(history_years: int, now: pd.Timestamp | None = None) -> tuple[str, str]:
    """Exclusive Yahoo end date in NY market time, avoiding unfinished sessions.

    Yahoo may serve an incomplete intraday candle for the current date. Always
    exclude the current New York calendar day. The last returned day is the
    latest completed trading day available to the provider.
    """
    current = pd.Timestamp.now(tz="America/New_York") if now is None else pd.Timestamp(now)
    if current.tzinfo is None:
        raise PortfolioError("A timezone-aware timestamp is required for the data cutoff.")
    end = current.tz_convert("America/New_York").normalize()
    start = end - pd.DateOffset(years=history_years)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def compare_yahoo_csv(prices: pd.DataFrame, ticker: str, source: io.BytesIO | str) -> pd.DataFrame:
    """Compare downloaded adjusted closes against a separately exported Yahoo CSV.

    Comparison takes place by exact date without imputing either source.
    Yahoo exports may be rounded or revised retroactively after distributions.
    """
    symbol = ticker.strip().upper().replace(".", "-")
    if symbol not in prices.columns:
        raise PortfolioError(f"Ticker {symbol} is not in the current price table.")
    try:
        reference = pd.read_csv(source)
        fields = {str(c).strip().lower(): c for c in reference.columns}
        date_col = fields.get("date")
        price_col = fields.get("adj close") or fields.get("adj close**") or fields.get("adj close*")
        if date_col is None or price_col is None:
            raise PortfolioError("Yahoo comparison CSV needs Date and Adj Close columns (not Close).")
        dates = pd.to_datetime(reference[date_col], errors="raise")
        values = pd.to_numeric(reference[price_col], errors="raise")
        if pd.DatetimeIndex(dates).tz is not None:
            dates = dates.dt.tz_localize(None)
        ref = pd.Series(values.to_numpy(dtype=float), index=pd.DatetimeIndex(dates).normalize(), name="Yahoo exported Adj Close")
    except PortfolioError:
        raise
    except Exception as exc:
        raise PortfolioError(f"Could not read the Yahoo history export: {exc}") from exc
    if ref.index.has_duplicates:
        raise PortfolioError("Yahoo comparison file contains duplicate dates.")
    if not np.isfinite(ref.to_numpy(dtype=float)).all() or (ref <= 0).any():
        raise PortfolioError("Yahoo comparison adjusted closing prices must be positive and finite.")
    selected = pd.to_numeric(prices[symbol], errors="raise").rename("Downloaded adjusted close")
    comparison = pd.concat([selected, ref], axis=1, join="inner").dropna().sort_index()
    if comparison.empty:
        raise PortfolioError("No overlapping dates between the download and Yahoo comparison CSV.")
    comparison["Absolute difference"] = (comparison.iloc[:, 0] - comparison.iloc[:, 1]).abs()
    comparison["Relative difference (%)"] = 100 * comparison["Absolute difference"] / comparison.iloc[:, 1]
    comparison.index.name = "Date"
    return comparison


def fetch_yahoo_prices(tickers: list[str], history_years: int = 5) -> pd.DataFrame:
    """Get Yahoo-adjusted closes, diagnose zero-overlap histories explicitly.

    A single batch download is attempted first. Tickers with inadequate coverage
    are individually retried via Ticker.history; missing investments are NEVER
    silently omitted from the optimized universe.
    """
    if not 2 <= history_years <= 15:
        raise PortfolioError("Historical period must be between 2 and 15 years.")
    if len(tickers) < 2 or len(tickers) != len(set(tickers)):
        raise PortfolioError("Provide two or more distinct tickers.")
    try:
        import yfinance as yf
    except ImportError as exc:
        raise PortfolioError("yfinance is not installed. Install requirements.txt.") from exc

    start, end = _history_window(history_years)
    args = {"start": start, "end": end, "interval": "1d", "auto_adjust": True}
    errors: dict[str, str] = {}
    try:
        batch = yf.download(tickers=tickers, progress=False, threads=False, **args)
    except Exception as exc:
        batch = pd.DataFrame()
        errors["batch"] = f"{type(exc).__name__}: {str(exc)[:160]}"

    series: dict[str, pd.Series] = {}
    for ticker in tickers:
        s = _extract_series(batch, ticker, single=(len(tickers) == 1))
        if s is not None:
            series[ticker] = s

    # Individual requests often succeed when the bulk request partially fails.
    for ticker in tickers:
        current = series.get(ticker)
        if current is not None and int(current.notna().sum()) >= MIN_PRICES:
            continue
        try:
            history = yf.Ticker(ticker).history(actions=False, **args)
            candidate = _extract_series(history, ticker, single=True)
            if candidate is not None and (current is None or
                                         candidate.notna().sum() > current.notna().sum()):
                series[ticker] = candidate
        except Exception as exc:
            errors[ticker] = f"{type(exc).__name__}: {str(exc)[:130]}"

    if not series:
        detail = "; ".join(f"{symbol}: {why}" for symbol, why in errors.items())
        raise PortfolioError(
            "Yahoo Finance returned no valid adjusted prices for your tickers. "
            "On Streamlit Cloud this can be caused by Yahoo rate limits or network blocking. "
            "Try one of: wait and retry; test VTI, VXUS with 5 years; or use Upload CSV. "
            + (f"Download errors: {detail}" if detail else "")
        )

    # Outer join shows missing observations; never forward-fill prices.
    close = pd.concat(series, axis=1).reindex(columns=tickers).sort_index()
    counts = {ticker: int(close[ticker].notna().sum()) for ticker in tickers}
    complete_rows = int(close.dropna(how="any").shape[0])
    if complete_rows < MIN_PRICES:
        details = ", ".join(f"{ticker}: {counts[ticker]}" for ticker in tickers)
        missing = [t for t in tickers if counts[t] < MIN_PRICES]
        explanation = (
            f"Yahoo Finance provided only {complete_rows} dates with prices for ALL "
            f"{len(tickers)} requested tickers (minimum {MIN_PRICES}). "
            f"Per-ticker valid price rows: {details}. "
        )
        if missing:
            explanation += f"Tickers with insufficient data: {', '.join(missing)}. "
        else:
            explanation += "Each ticker has some data but their date ranges do not overlap enough. "
        explanation += (
            "Try removing or correcting the affected ticker(s) in the sidebar; "
            "BRK.B is automatically mapped to BRK-B. You can also retry in a few minutes "
            "or use Upload CSV. No ticker has been silently excluded."
        )
        if errors:
            explanation += " Download errors: " + "; ".join(
                f"{key}: {why}" for key, why in errors.items())
        raise PortfolioError(explanation)

    # Reject stale or future/intraday histories even when enough rows exist.
    last_available = pd.Timestamp(close.dropna(axis=0, how="any").index.max()).normalize()
    cutoff = pd.Timestamp(end)
    age_days = (cutoff - last_available).days
    if age_days < 1:
        raise PortfolioError("Yahoo returned a current-day or future price despite the completed-day cutoff. Refusing potentially incomplete session data.")
    if age_days > 10:
        raise PortfolioError(
            f"Latest common Yahoo adjusted close is {last_available.date()}, "
            f"{age_days} calendar days before the data cutoff. The history may be stale "
            "or one ticker may have stopped trading; retry or upload a verified CSV."
        )
    return validate_prices(close)
