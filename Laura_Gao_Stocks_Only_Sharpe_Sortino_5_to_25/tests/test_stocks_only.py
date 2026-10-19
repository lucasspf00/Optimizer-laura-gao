"""Regression tests for stocks-only sleeve and 5%–25% limits."""
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from market_data import parse_tickers, validate_stock_only, load_wide_csv
from optimizer import (optimize_combined, daily_returns, PortfolioError,
                       DEFAULT_MIN_STOCK_WEIGHT, DEFAULT_MAX_STOCK_WEIGHT,
                       bounded_simplex_projection)
from projections import project_wharton

ROOT=Path(__file__).resolve().parents[1]

def demo_returns():
    prices=load_wide_csv(str(ROOT/'examples'/'SYNTHETIC_STOCK_PRICES_NOT_REAL.csv'))
    return daily_returns(prices)

def test_defaults_are_5_to_25():
    assert DEFAULT_MIN_STOCK_WEIGHT == .05
    assert DEFAULT_MAX_STOCK_WEIGHT == .25
    res=optimize_combined(demo_returns())
    assert len(res.tickers)==7
    assert min(res.weights)>=.05-1e-7
    assert max(res.weights)<=.25+1e-7
    assert abs(res.weights.sum()-1)<1e-7
    assert res.minimum_position==pytest.approx(.05)
    assert res.concentration_cap==pytest.approx(.25)

def test_sharpe_sortino_formula_unchanged():
    res=optimize_combined(demo_returns())
    assert res.metrics.composite == pytest.approx(
        .4*res.metrics.sharpe/res.sharpe_scale +
        .6*res.metrics.sortino/res.sortino_scale)

def test_can_use_4_stocks_with_exact_25_percent_each():
    r=demo_returns().iloc[:,:4]
    res=optimize_combined(r)
    assert np.allclose(res.weights, .25, atol=1e-7)

def test_can_use_20_stocks_with_exact_5_percent_each():
    r=demo_returns()
    rng=np.random.default_rng(2000)
    data=r.copy()
    for i in range(13):
        data[f'ADDITIONAL_STOCK_{i}']=r.iloc[:,i%7]*.90+rng.normal(0,.0001,len(r))
    res=optimize_combined(data, n_starts=3)
    assert len(res.weights)==20
    assert np.allclose(res.weights,.05, atol=1e-7)

def test_3_stocks_infeasible_by_cap():
    with pytest.raises(PortfolioError, match='infeasible'):
        optimize_combined(demo_returns().iloc[:,:3])

def test_21_stocks_infeasible_by_floor():
    r=demo_returns()
    large=r.copy()
    for i in range(14):
        large[f'EXTRA_{i}']=r.iloc[:,i%7]*(.9+.005*i)
    with pytest.raises(PortfolioError, match='infeasible'):
        optimize_combined(large)

def test_known_etfs_rejected():
    for symbol in ['VTI','VBR','VXUS','VOO','SPY','SGOV']:
        with pytest.raises(PortfolioError,match='individual stocks only'):
            validate_stock_only(parse_tickers(f'PGR,MA,JNJ,ADP,{symbol}'))

def test_stocks_accepted():
    validate_stock_only(['PGR','MA','JNJ','ADP','ECL','MSFT','RSG'])

def test_stock_projection_is_not_conflated_with_model_sharpe_return():
    # Official cash flows are unchanged and use a separately chosen overall return.
    df=project_wharton(.06)
    assert df.iloc[0]['Annual investment earnings'] == pytest.approx(18000)
    assert df.iloc[1]['End-of-year balance'] == pytest.approx(496080)
    assert df['Required operating payment'].sum()==500000

def test_feasible_boundary_projection():
    w=bounded_simplex_projection(np.array([10.,-5.,3.,1.,0.,7.,8.]),.25,.05)
    assert w.min()>=.05-1e-8
    assert w.max()<=.25+1e-8
    assert w.sum()==pytest.approx(1)
