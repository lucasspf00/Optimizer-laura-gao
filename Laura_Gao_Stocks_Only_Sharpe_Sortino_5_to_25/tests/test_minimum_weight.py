"""Allocation floor regression tests: do not drop weaker assets."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
import pytest
from optimizer import optimize_combined, PortfolioError, bounded_simplex_projection
from market_data import load_wide_csv
from optimizer import daily_returns

@pytest.fixture(scope="module")
def returns():
    p=load_wide_csv(str(Path(__file__).resolve().parents[1] / "examples/SYNTHETIC_PRICES_NOT_REAL.csv"))
    return daily_returns(p)

def test_default_forces_positive_allocations(returns):
    outcome=optimize_combined(returns,max_position=.40)
    assert len(outcome.tickers)==returns.shape[1]
    assert all(outcome.weights>=.05-1e-7)
    assert outcome.weights.sum()==pytest.approx(1.0,abs=1e-7)
    assert outcome.minimum_position==pytest.approx(.05)

def test_configurable_floor(returns):
    outcome=optimize_combined(returns,min_position=.07,max_position=.4)
    assert min(outcome.weights)>=.07-1e-7
    assert max(outcome.weights)<=.4+1e-7

def test_impossible_minimum_rejected(returns):
    with pytest.raises(PortfolioError,match="infeasible"):
        optimize_combined(returns,min_position=.25,max_position=.45)

def test_maximum_below_minimum_rejected(returns):
    with pytest.raises(PortfolioError,match="infeasible"):
        optimize_combined(returns,min_position=.30,max_position=.20)

def test_projection_respects_floor_and_cap():
    w=bounded_simplex_projection(np.array([50., 4., -3., 2., 1.]),cap=.35,min_position=.05)
    assert np.sum(w)==pytest.approx(1.0, abs=1e-8)
    assert min(w)>=.05-1e-8
    assert max(w)<=.35+1e-8

def test_exact_equal_weights_boundary():
    w=bounded_simplex_projection(np.array([7., 0., -8., 2., 1.]),cap=.3,min_position=.2)
    assert np.allclose(w, np.full(5,.2))

def test_flexible_min_zero_still_supported(returns):
    outcome=optimize_combined(returns,min_position=0,max_position=.4)
    assert outcome.weights.sum()==pytest.approx(1)
    assert min(outcome.weights)>=-1e-8

def test_composite_unchanged(returns):
    outcome=optimize_combined(returns,sharpe_weight=.4,min_position=.01,max_position=.4)
    expected=.4*outcome.metrics.sharpe/outcome.sharpe_scale+.6*outcome.metrics.sortino/outcome.sortino_scale
    assert outcome.metrics.composite==pytest.approx(expected)
