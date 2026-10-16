"""Independent mathematical and Yahoo-field audit tests; all deterministic/offline."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from io import BytesIO
import numpy as np
import pandas as pd
import pytest
from market_data import _history_window, _extract_series, compare_yahoo_csv, fetch_yahoo_prices
from optimizer import (PortfolioError, TRADING_DAYS, optimize_combined,
                       portfolio_raw_metrics, daily_returns, validate_prices, max_drawdown)
from projections import project_wharton


def test_manual_two_asset_annual_return_and_volatility():
    # Deliberately nontrivial correlation structure, not a data vendor call.
    data = np.array([[.01, -.02],[-.005, .015],[.02, .001],[-.012, .008]])
    w = np.array([.6, .4])
    mu = data.mean(axis=0) * 252
    cov = np.cov(data, rowvar=False,ddof=1)*252
    expected = float(np.mean(data @ w)*252)
    expected_vol = float(np.std(data @ w, ddof=1)*np.sqrt(252))
    ret, vol, downside, sh, so = portfolio_raw_metrics(w, data, mu, cov, .03, .0, .015)
    assert ret == pytest.approx(expected)
    assert vol == pytest.approx(expected_vol)
    assert sh == pytest.approx((expected - .03)/expected_vol)
    assert so == pytest.approx(expected/max(downside,.015))


def test_pearson_correlation_hand_calculation():
    dates = pd.bdate_range('2024-01-01', periods=150)
    x = np.linspace(-.03,.04,150)
    y = -2*x + .005*np.cos(np.arange(150))
    rets = pd.DataFrame({'X':x,'Y':y},index=dates)
    opt=optimize_combined(rets, max_position=.75)
    assert opt.correlation.loc['X','Y'] == pytest.approx(np.corrcoef(x,y)[0,1])


def test_nonlinear_two_asset_numeric_optimum_grid_check():
    rng=np.random.default_rng(8)
    a = rng.normal(.00065, .018, 180)
    b = rng.normal(.00043, .006, 180)
    rets=pd.DataFrame({'A':a,'B':b})
    result=optimize_combined(rets,sharpe_weight=.4,max_position=.70,n_starts=12)
    values=rets.to_numpy()
    grid=np.linspace(.30,.70,801)
    scores=[]
    for p in grid:
        w=np.array([p,1-p])
        *_,sh,so=portfolio_raw_metrics(w,values,result.mean_returns,result.covariance,
                                         .03,.03,result.downside_floor)
        scores.append(.4*sh/result.sharpe_scale+.6*so/result.sortino_scale)
    assert result.metrics.composite >= max(scores)-2e-3


def test_constant_single_asset_caught_undefined_correlation():
    rng=np.random.default_rng(22)
    rets=pd.DataFrame({'REAL':rng.normal(0,.01,210),'FLAT':np.zeros(210)})
    with pytest.raises(PortfolioError,match='FLAT'):
        optimize_combined(rets,max_position=.7)


def test_date_window_excludes_current_trading_day():
    start,end=_history_window(3, pd.Timestamp('2026-10-16T14:00:00-04:00'))
    assert (start,end)==('2023-10-16','2026-10-16')


def test_date_window_timezone_converts_from_utc():
    # 01:00 UTC Oct 17 is still October 16 in NY; exclude Oct 16.
    _,end=_history_window(2,pd.Timestamp('2026-10-17T01:00:00Z'))
    assert end=='2026-10-16'


def test_ny_naive_timestamp_rejected():
    with pytest.raises(PortfolioError,match='timezone'):
        _history_window(2,pd.Timestamp('2026-10-16'))


def test_actual_yahoo_published_adj_close_sample_values():
    # Yahoo Finance VTI historical page: Oct 14 2026 376.88, Oct 15 378.42.
    # This checks extraction and return arithmetic, NOT a live Yahoo API response.
    raw=pd.DataFrame({'Close':[376.88,378.42]}, index=pd.DatetimeIndex(['2026-10-14','2026-10-15']))
    s=_extract_series(raw,'VTI',single=True)
    assert s.iloc[0]==pytest.approx(376.88)
    assert s.iloc[1]==pytest.approx(378.42)
    assert s.iloc[1]/s.iloc[0]-1 == pytest.approx((378.42-376.88)/376.88)


def test_yahoo_csv_independent_comparison_exact_match():
    prices=pd.DataFrame({'VTI':[376.88,378.42]},index=pd.to_datetime(['2026-10-14','2026-10-15']))
    csv=BytesIO(b'Date,Close,Adj Close\n2026-10-14,376.88,376.88\n2026-10-15,378.42,378.42\n')
    diff=compare_yahoo_csv(prices,'VTI',csv)
    assert len(diff)==2
    assert diff['Absolute difference'].max()==pytest.approx(0)
    assert diff['Relative difference (%)'].max()==pytest.approx(0)


def test_yahoo_compare_mismatch_is_detected():
    prices=pd.DataFrame({'VTI':[99,101]}, index=pd.to_datetime(['2026-10-14','2026-10-15']))
    csv=BytesIO(b'Date,Adj Close\n2026-10-14,100\n2026-10-15,100\n')
    diff=compare_yahoo_csv(prices,'VTI',csv)
    assert diff['Relative difference (%)'].max()==pytest.approx(1.0)


def test_yahoo_comparison_rejects_close_only():
    prices=pd.DataFrame({'VTI':[99]},index=pd.to_datetime(['2026-10-14']))
    with pytest.raises(PortfolioError, match='Adj Close'):
        compare_yahoo_csv(prices,'VTI',BytesIO(b'Date,Close\n2026-10-14,99\n'))


def test_yahoo_comparison_no_date_overlap():
    prices=pd.DataFrame({'VTI':[99]}, index=pd.to_datetime(['2026-10-14']))
    with pytest.raises(PortfolioError,match='overlapping'):
        compare_yahoo_csv(prices,'VTI',BytesIO(b'Date,Adj Close\n2026-10-15,99\n'))


def test_funding_recursion_manual_at_zero_return():
    df=project_wharton(0)
    assert df[df.Year==2032]['End-of-year balance'].iloc[0]==pytest.approx(450000)
    assert df[df.Year==2033]['End-of-year balance'].iloc[0]==pytest.approx(400000)
    assert df[df.Year==2041]['End-of-year balance'].iloc[0]==pytest.approx(0)
    assert df[df.Year==2042]['Operating payment shortfall'].iloc[0]==pytest.approx(50000)


def test_2033_facility_whatif_preserves_current_operating_priority():
    df=project_wharton(0,initial_contribution=50000,second_contribution=0,facility_payment_2033=70000)
    y=df.loc[df.Year==2033].iloc[0]
    assert y['Operating payment funded']==pytest.approx(50000)
    assert y['Facility payment funded']==0
    assert y['Facility payment shortfall']==pytest.approx(70000)


def test_csv_weekly_is_rejected_not_annualized_as_daily():
    d=pd.bdate_range('2021-01-04',periods=200)[::5]
    p=pd.DataFrame({'X':100+np.arange(len(d)), 'Y':200+np.arange(len(d))},index=d)
    with pytest.raises(PortfolioError):
        validate_prices(p,min_observations=20)


def test_prices_with_3pct_missing_exchange_days_accepted():
    # 1000 pure business days, 3% missing, still enough for annualization.
    d=pd.bdate_range('2021-01-04',periods=1000)
    p=pd.DataFrame({'X':100+np.arange(len(d)), 'Y':200+np.arange(len(d))},index=d)
    p=p.drop(p.index[::40])
    assert len(validate_prices(p)) == len(p)


def test_prices_with_8pct_missing_exchange_days_rejected():
    d=pd.bdate_range('2021-01-04',periods=1000)
    p=pd.DataFrame({'X':100+np.arange(len(d)), 'Y':200+np.arange(len(d))},index=d)
    p=p.drop(p.index[::12])
    with pytest.raises(PortfolioError,match='DAILY prices'):
        validate_prices(p)


def test_max_drawdown_no_loss_is_zero():
    assert max_drawdown(pd.Series([.1,.07,.03])) == pytest.approx(0)


def test_max_drawdown_known_loss():
    assert max_drawdown(pd.Series([.2,-.25,.1])) == pytest.approx(-.25)


def test_yahoo_rejects_stale_but_mathematically_valid_histories(monkeypatch):
    import types
    fake_dates = pd.bdate_range('2021-01-04',periods=180)
    mock_data=pd.DataFrame({('Close','VTI'):100+np.arange(180),('Close','VXUS'):80+np.arange(180)},
                           index=fake_dates)
    mock_data.columns=pd.MultiIndex.from_tuples(mock_data.columns)
    mock=types.SimpleNamespace(download=lambda **kwargs:mock_data,
                               Ticker=lambda symbol:None)
    monkeypatch.setitem(sys.modules,'yfinance',mock)
    with pytest.raises(PortfolioError,match='stale'):
        fetch_yahoo_prices(['VTI','VXUS'],3)


def test_yahoo_request_is_explicitly_adjusted_and_complete_days(monkeypatch):
    import types
    calls=[]
    last=(pd.Timestamp.now(tz='America/New_York').tz_localize(None).normalize()
          - pd.offsets.BDay(1))
    idx=pd.bdate_range(end=last,periods=180)
    raw=pd.DataFrame({('Close','VTI'):100+np.arange(180)*.01,
                      ('Close','VXUS'):80+np.arange(180)*.01},index=idx)
    raw.columns=pd.MultiIndex.from_tuples(raw.columns)
    def download(**kwargs):
        calls.append(kwargs)
        return raw
    mock=types.SimpleNamespace(download=download,Ticker=lambda _:None)
    monkeypatch.setitem(sys.modules,'yfinance',mock)
    out=fetch_yahoo_prices(['VTI','VXUS'],3)
    assert out.index[-1] <= pd.Timestamp(calls[0]['end']) - pd.Timedelta(days=1)
    assert calls[0]['auto_adjust'] is True
    assert calls[0]['interval']=='1d'
    assert len(out)==180


def test_future_price_rows_are_rejected():
    today = pd.Timestamp.now(tz='America/New_York').tz_localize(None).normalize()
    dates = pd.bdate_range(end=today+pd.offsets.BDay(5), periods=200)
    prices = pd.DataFrame({'A':100+np.arange(200)*.1,'B':120+np.arange(200)*.2}, index=dates)
    with pytest.raises(PortfolioError,match='future date'):
        validate_prices(prices)


def test_latest_yahoo_completed_prices_can_pass():
    today=pd.Timestamp.now(tz='America/New_York').tz_localize(None).normalize()
    dates=pd.bdate_range(end=today-pd.offsets.BDay(1),periods=200)
    p=pd.DataFrame({'A':100+np.arange(200)*.2,'B':110+np.arange(200)*.1},index=dates)
    assert len(validate_prices(p))==200
