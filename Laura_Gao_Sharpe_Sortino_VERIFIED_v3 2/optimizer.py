"""Single-portfolio combined Sharpe/Sortino optimization.

All input prices must be corporate-action-adjusted daily prices or a consistently
constructed total-return index. This file deliberately performs no data downloads.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.optimize import minimize

TRADING_DAYS = 252


class PortfolioError(ValueError):
    """An invalid dataset, numerical condition, or infeasible portfolio."""


def validate_prices(prices: pd.DataFrame, min_observations: int = 126) -> pd.DataFrame:
    if not isinstance(prices, pd.DataFrame) or prices.empty:
        raise PortfolioError("Provide a non-empty wide-format price table.")
    p = prices.copy()
    if len(p.columns) < 2:
        raise PortfolioError("At least two investment tickers are required.")
    p.columns = [str(s).strip().upper() for s in p.columns]
    if len(set(p.columns)) != len(p.columns):
        raise PortfolioError("Duplicate tickers are not allowed.")
    try:
        dates = pd.DatetimeIndex(pd.to_datetime(p.index, errors="raise"))
        # All observations represent exchange-local trading dates.  Reject
        # multiple prices per day even if their original timestamps differ.
        if dates.tz is not None:
            dates = dates.tz_localize(None)
        p.index = dates.normalize()
    except (ValueError, TypeError) as exc:
        raise PortfolioError("The first column must contain valid dates.") from exc
    if p.index.has_duplicates:
        raise PortfolioError("Dates must be unique; duplicate dates were found.")
    p = p.sort_index()
    # For a historical portfolio model, today may still have an unfinished
    # session and any future-dated price would necessarily be suspect.
    today_ny = pd.Timestamp.now(tz="America/New_York").date()
    if p.index.max().date() >= today_ny:
        raise PortfolioError(
            "The price history includes today's potentially unfinished session "
            "or a future date. Use only completed dates before today (New York time)."
        )
    try:
        p = p.apply(pd.to_numeric, errors="raise")
    except (ValueError, TypeError) as exc:
        raise PortfolioError("Prices must be numeric.") from exc
    if np.isinf(p.to_numpy(dtype=float)).any():
        raise PortfolioError("Infinite price values are not allowed.")
    # Do NOT invent daily prices via interpolation or forward filling.
    p = p.dropna(axis=0, how="any")
    if len(p) < min_observations + 1:
        raise PortfolioError(
            f"Only {len(p)} complete price rows. At least {min_observations + 1} are required. "
            "Check mismatched listing dates or use a shorter, documented common period."
        )
    if (p.to_numpy(dtype=float) <= 0).any():
        raise PortfolioError("All prices must be strictly positive.")
    # Estimation assumes *daily* observations (252 trading days/year).
    # Merely having 127 dates is not sufficient: 127 weekly observations
    # would silently inflate annualized risk and expected-return estimates.
    if (p.index.dayofweek >= 5).any():
        raise PortfolioError("Prices must be dated on weekdays; daily stock/ETF trading data are expected.")
    weekdays = len(pd.bdate_range(start=p.index.min(), end=p.index.max()))
    coverage = len(p) / max(weekdays, 1)
    if coverage < 0.95:
        raise PortfolioError(
            f"Price history covers only {coverage:.1%} of weekdays in the common date range. "
            "Provide DAILY prices with at least 95% weekday coverage. Weekly/monthly "
            "or severely incomplete histories cannot be annualized as daily returns."
        )
    if p.index.to_series().diff().dt.days.iloc[1:].max() > 7:
        raise PortfolioError("A data gap greater than 7 days was detected; check for missing prices.")
    return p


def daily_returns(prices: pd.DataFrame, min_observations: int = 126) -> pd.DataFrame:
    p = validate_prices(prices, min_observations=min_observations)
    returns = p.pct_change(fill_method=None).iloc[1:]
    if (returns.to_numpy(dtype=float) <= -1).any():
        raise PortfolioError("A non-positive price or total loss was detected.")
    return returns


def annual_to_daily(rate: float) -> float:
    if rate <= -1:
        raise PortfolioError("Annual rate must be greater than -100%.")
    return (1.0 + rate) ** (1.0 / TRADING_DAYS) - 1.0


def bounded_simplex_projection(values: np.ndarray, cap: float) -> np.ndarray:
    """Euclidean projection onto {w: sum(w)=1, 0<=w<=cap}."""
    z = np.asarray(values, dtype=float)
    n = z.size
    if n < 2 or not 0 < cap <= 1 or n * cap < 1 - 1e-10:
        raise PortfolioError(f"Max position {cap:.1%} is infeasible for {n} assets.")
    lo, hi = np.min(z) - cap - 1, np.max(z) + 1
    for _ in range(100):
        mid = (lo + hi) / 2
        weights = np.clip(z - mid, 0, cap)
        if float(weights.sum()) > 1:
            lo = mid
        else:
            hi = mid
    result = np.clip(z - (lo + hi) / 2, 0, cap)
    if abs(result.sum() - 1) > 1e-8:
        raise PortfolioError("Projection numerical failure.")
    return result


@dataclass(frozen=True)
class Metrics:
    expected_return: float
    volatility: float
    downside_deviation: float
    sharpe: float
    sortino: float
    composite: float


@dataclass(frozen=True)
class OptimizationResult:
    tickers: tuple[str, ...]
    weights: np.ndarray
    metrics: Metrics
    correlation: pd.DataFrame
    mean_returns: np.ndarray
    covariance: np.ndarray
    benchmark_return: float
    benchmark_sharpe: float
    benchmark_sortino: float
    sharpe_scale: float
    sortino_scale: float
    downside_floor: float
    concentration_cap: float
    observations: int
    converged: bool
    optimizer_message: str


def portfolio_raw_metrics(
    weights: np.ndarray,
    daily: np.ndarray,
    mu: np.ndarray,
    covariance: np.ndarray,
    risk_free: float,
    mar: float,
    downside_floor: float,
) -> tuple[float, float, float, float, float]:
    w = np.asarray(weights, dtype=float)
    ann_return = float(mu @ w)
    ann_variance = float(w @ covariance @ w)
    vol = float(np.sqrt(max(0.0, ann_variance)))
    portfolio_daily = daily @ w
    mar_daily = annual_to_daily(mar)
    downside = float(np.sqrt(TRADING_DAYS * np.mean(np.square(np.minimum(portfolio_daily - mar_daily, 0.0)))))
    # Floors prevent a nearly zero measured risk from producing an unbounded ratio.
    sharpe = (ann_return - risk_free) / max(vol, 1e-6)
    sortino = (ann_return - mar) / max(downside, downside_floor)
    return ann_return, vol, downside, sharpe, sortino


def optimize_combined(
    returns: pd.DataFrame,
    *,
    sharpe_weight: float = 0.40,
    max_position: float = 0.40,
    risk_free: float = 0.03,
    mar: float | None = None,
    mean_shrinkage: float = 0.50,
    random_seed: int = 2026,
    n_starts: int = 9,
) -> OptimizationResult:
    """One allocation from a 40/60 scaled Sharpe/Sortino objective.

    Each ratio is divided by a robust 10th-to-90th percentile spread of ratios
    computed from *feasible* sampled portfolios. This aligns their observed
    variation without asserting the two raw ratios are interchangeable.
    """
    if not isinstance(returns, pd.DataFrame) or returns.shape[1] < 2 or len(returns) < 126:
        raise PortfolioError("At least 126 joint daily returns and 2 assets are required.")
    if not 0 <= sharpe_weight <= 1:
        raise PortfolioError("Sharpe weight must be between 0 and 1.")
    if not 0 <= mean_shrinkage <= 1:
        raise PortfolioError("Mean shrinkage must be between 0 and 1.")
    if not -0.99 < risk_free < 1 or not -0.99 < (risk_free if mar is None else mar) < 1:
        raise PortfolioError("Risk-free rate and downside threshold must be valid decimal annual rates.")
    n = returns.shape[1]
    if max_position <= 0 or max_position > 1 or n * max_position < 1 - 1e-10:
        raise PortfolioError(f"The maximum position limit ({max_position:.0%}) is infeasible for {n} assets. "
                             f"It must be at least {1/n:.1%}.")
    if not np.isfinite(returns.to_numpy(dtype=float)).all():
        raise PortfolioError("Returns have non-finite values.")
    if (returns.to_numpy(dtype=float) <= -1).any():
        raise PortfolioError("Daily returns must be greater than -100%.")
    data = returns.to_numpy(dtype=float)
    asset_std = np.std(data, axis=0)
    if (asset_std < 1e-12).any():
        affected = [str(returns.columns[i]) for i in np.flatnonzero(asset_std < 1e-12)]
        raise PortfolioError(
            "One or more tickers have constant returns (daily), so their correlation "
            "is undefined: " + ", ".join(affected) + ". Remove the affected input(s)."
        )
    mar = risk_free if mar is None else mar
    empirical_mu = data.mean(axis=0) * TRADING_DAYS
    # Equal-weight cross-sectional prior, deliberately documented as a heuristic.
    pooled_mean = np.mean(empirical_mu)
    mu = (1 - mean_shrinkage) * empirical_mu + mean_shrinkage * pooled_mean
    cov = np.cov(data, rowvar=False, ddof=1) * TRADING_DAYS
    cov = (cov + cov.T) / 2
    if not np.isfinite(cov).all():
        raise PortfolioError("Covariance estimate is invalid.")

    equal_weights = np.full(n, 1.0 / n)
    # The adaptive floor limits extreme Sortino values on low-downside histories.
    eq_downside = portfolio_raw_metrics(equal_weights, data, mu, cov, risk_free, mar, 1e-6)[2]
    floor = max(0.015, 0.15 * eq_downside)
    rng = np.random.default_rng(random_seed)
    sample_weights = [equal_weights]
    # Diverse feasible reference portfolios define common-scale ranges; seeded for reproducibility.
    for i in range(256):
        concentration = (0.45, 1.0, 3.0)[i % 3]
        raw = rng.dirichlet(np.full(n, concentration))
        sample_weights.append(bounded_simplex_projection(raw, max_position))
    array = np.array([portfolio_raw_metrics(w, data, mu, cov, risk_free, mar, floor)[3:]
                      for w in sample_weights])
    sharpe_scale = max(0.10, float(np.quantile(array[:, 0], 0.90) - np.quantile(array[:, 0], 0.10)))
    sortino_scale = max(0.10, float(np.quantile(array[:, 1], 0.90) - np.quantile(array[:, 1], 0.10)))

    def composite(w: np.ndarray) -> float:
        *_, sh, so = portfolio_raw_metrics(w, data, mu, cov, risk_free, mar, floor)
        return float(sharpe_weight * sh / sharpe_scale + (1 - sharpe_weight) * so / sortino_scale)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds = [(0.0, max_position)] * n
    candidates: list[tuple[float, np.ndarray, bool, str]] = []
    # Start near the strongest FEASIBLE reference allocations rather than
    # always using the first few arbitrary Dirichlet samples.
    n_starts = max(1, min(int(n_starts), 25))
    ranked = np.argsort([-composite(w) for w in sample_weights])
    starts = [equal_weights] + [sample_weights[int(j)] for j in ranked if j != 0][:n_starts-1]
    for start in starts:
        solution = minimize(lambda w: -composite(w), start, method="SLSQP",
                            bounds=bounds, constraints=constraints,
                            options={"maxiter": 800, "ftol": 1e-10})
        w = solution.x
        feasible = (np.isfinite(w).all() and abs(w.sum() - 1) < 1e-6 and
                    w.min() >= -1e-7 and w.max() <= max_position + 1e-7)
        if feasible:
            candidates.append((composite(w), w, bool(solution.success), str(solution.message)))
    # A solver's feasibility is necessary, but a nonconverged search does not
    # certify that a locally optimal point has been reached.
    successful = [c for c in candidates if c[2]]
    if not successful:
        raise PortfolioError(
            "The numerical solver did not converge to a validated optimum. "
            "Try adjusting the ticker list, the maximum position cap, or the return threshold."
        )
    score, weights, converged, message = max(successful, key=lambda c: c[0])
    weights = np.clip(weights, 0, max_position)
    # Tiny numeric renormalization (without changing meaningful bound constraints).
    if abs(weights.sum() - 1) > 1e-7:
        raise PortfolioError("Numerical weight-sum error.")
    ann_ret, vol, downside, sharpe, sortino = portfolio_raw_metrics(
        weights, data, mu, cov, risk_free, mar, floor)
    eq_ret, _, _, eq_sharpe, eq_sortino = portfolio_raw_metrics(
        equal_weights, data, mu, cov, risk_free, mar, floor)
    return OptimizationResult(
        tickers=tuple(map(str, returns.columns)), weights=weights,
        metrics=Metrics(ann_ret, vol, downside, sharpe, sortino, score),
        correlation=returns.corr(), mean_returns=mu, covariance=cov,
        benchmark_return=eq_ret, benchmark_sharpe=eq_sharpe, benchmark_sortino=eq_sortino,
        sharpe_scale=sharpe_scale, sortino_scale=sortino_scale,
        downside_floor=floor, concentration_cap=max_position,
        observations=len(returns), converged=converged,
        optimizer_message=message)


def simulate_fixed_allocation(returns: pd.DataFrame, weights: np.ndarray) -> pd.Series:
    """Historical daily portfolio returns assuming daily constant-weight rebalancing.

    Not an out-of-sample backtest; only for descriptive diagnostics.
    """
    if len(weights) != returns.shape[1]:
        raise PortfolioError("Return columns and weights have different lengths.")
    return returns @ np.asarray(weights)


def max_drawdown(returns: pd.Series) -> float:
    growth = (1 + returns).cumprod()
    drawdowns = growth / np.maximum.accumulate(np.r_[1.0, growth.to_numpy()])[1:] - 1.0
    return float(drawdowns.min())
