"""Offline Yahoo adapter tests: no network needed."""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import pytest

from market_data import fetch_yahoo_prices, parse_tickers
from optimizer import PortfolioError

# A real Yahoo download should reach the latest completed trading session.
LAST_COMPLETED = (pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()
                  - pd.offsets.BDay(1))
DATES = pd.bdate_range(end=LAST_COMPLETED, periods=180)


def batch_frame(with_missing=False, reverse=False):
    # The two layouts are both produced by different yfinance versions/options.
    prices = np.column_stack([100 + np.arange(180)*0.10, 80 + np.arange(180)*0.06])
    if with_missing:
        prices[:, 1] = np.nan
    if reverse:
        columns = pd.MultiIndex.from_product([["VTI", "VXUS"], ["Close"]])
    else:
        columns = pd.MultiIndex.from_product([["Close"], ["VTI", "VXUS"]])
    return pd.DataFrame(prices, index=DATES, columns=columns)


@pytest.mark.parametrize("reverse", [False, True])
def test_multilevel_yahoo_layouts(monkeypatch, reverse):
    mock = types.SimpleNamespace(
        download=lambda **kwargs: batch_frame(reverse=reverse),
        Ticker=lambda t: (_ for _ in ()).throw(AssertionError("No fallback expected")),
    )
    monkeypatch.setitem(sys.modules, "yfinance", mock)
    prices = fetch_yahoo_prices(["VTI", "VXUS"], 3)
    assert prices.columns.to_list() == ["VTI", "VXUS"]
    assert len(prices) == len(DATES)
    assert prices.notna().all().all()


def test_retry_missing_ticker_individually(monkeypatch):
    class Single:
        def __init__(self, ticker):
            self.ticker = ticker
        def history(self, **kwargs):
            assert self.ticker == "VXUS"
            return pd.DataFrame({"Close":80+np.arange(180)*0.06}, index=DATES)
    mock = types.SimpleNamespace(
        download=lambda **kwargs: batch_frame(with_missing=True),
        Ticker=lambda ticker: Single(ticker),
    )
    monkeypatch.setitem(sys.modules, "yfinance", mock)
    prices = fetch_yahoo_prices(["VTI", "VXUS"], 3)
    assert len(prices) == 180
    assert prices['VXUS'].iloc[0] == pytest.approx(80)


def test_complete_failure_explains_rate_limit_and_csv(monkeypatch):
    class Single:
        def history(self, **kwargs):
            return pd.DataFrame()
    mock = types.SimpleNamespace(download=lambda **kwargs: pd.DataFrame(), Ticker=lambda ticker: Single())
    monkeypatch.setitem(sys.modules, "yfinance", mock)
    with pytest.raises(PortfolioError) as exc:
        fetch_yahoo_prices(["VTI", "VXUS"], 3)
    msg = str(exc.value)
    assert "Yahoo Finance returned no valid" in msg
    assert "Upload CSV" in msg


def test_insufficient_ticker_is_named(monkeypatch):
    class Single:
        def history(self, **kwargs):
            return pd.DataFrame()
    mock = types.SimpleNamespace(download=lambda **kwargs: batch_frame(with_missing=True), Ticker=lambda ticker: Single())
    monkeypatch.setitem(sys.modules, "yfinance", mock)
    with pytest.raises(PortfolioError) as exc:
        fetch_yahoo_prices(["VTI", "VXUS"], 3)
    assert "VTI: 180" in str(exc.value)
    assert "VXUS: 0" in str(exc.value)
    assert "insufficient data: VXUS" in str(exc.value)


def test_symbol_translation():
    assert parse_tickers("VTI, BRK.B, VXUS") == ["VTI", "BRK-B", "VXUS"]
