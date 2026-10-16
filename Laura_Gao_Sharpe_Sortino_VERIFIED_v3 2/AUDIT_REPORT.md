# Independent audit — Laura Gao Sharpe–Sortino Optimizer (Version 3)

Audit date: 2026-10-16. Tests and local execution apply to **this archive**, not to older GitHub commits.

## Outcome

- **66/66 automated tests passed**: `python -m pytest -q`.
- Source compiles: `python -m compileall -q app.py optimizer.py market_data.py projections.py`.
- Tested full offline and simulated Yahoo app execution through a substitute Streamlit API, including Plotly figure generation and the annual and price-audit tables. This is **not a real Streamlit runtime test**.
- `app.py` and `requirements.txt` are in the archive root. Repository main file path should be `app.py`.
- This execution environment has no installed `streamlit` or `yfinance`, and cannot connect to the package download index. Live Streamlit and live Yahoo data downloads **cannot be certified here**.

## Price inputs and comparison to Yahoo

- `yfinance.download` and ticker fallback are requested with `interval='1d', auto_adjust=True`.
- With `auto_adjust=True`, yfinance's `Close` represents Yahoo's **Adj Close** (dividend/split adjusted), not necessarily Yahoo's raw `Close` or its live quote.
- Recent published historical reference values (Yahoo Finance historical pages checked 2026-10-16):
  - VTI 2026-10-14: $376.88; 2026-10-15: $378.42. Sample adjusted-price return = **+0.40861813%**.
  - VXUS 2026-10-14: $83.58; 2026-10-15: $83.84. Sample adjusted-price return = **+0.31107921%**.
- These **public page values** and extraction arithmetic were independently checked with offline tests. **A genuine live yfinance API response was not obtained here**. Therefore, no statement that "all downloaded values exactly equal Yahoo" is warranted.
- The new fourth dashboard tab shows the first/last common price dates, actual input adjusted closes, downloadable price data, and comparison against an independently downloaded Yahoo `Date, Adj Close` CSV.
- The CSV comparison matches by date, reports absolute and relative differences and flags relative differences greater than 0.10%. Due to display rounding, time and corporate-action revisions, precise equality cannot always be expected.
- Market-data safeguards: all symbols present; no forward filling; weekday-only prices; >=127 aligned prices; >=95% weekday coverage; no gaps >7 days; excludes today's New York date to avoid unfinished candles; Yahoo downloaded last common price must be within 10 calendar days of its cutoff. Validates nonpositive, nonnumeric, duplicated and future-dated inputs.
- **Market-data limitations**: A Yahoo API rate limit/network block cannot be fixed by local code. Historical adjusted prices can be revised. CSV imports are assumed to be consistently adjusted and in a common currency; the app does not independently verify such claims. Securities eligible for the WInS simulator are not auto-validated.

## Verified calculation formulas

Use daily decimal returns for each security, `r(i,t) = adjusted_close(i,t)/adjusted_close(i,t-1) - 1`, with simultaneous price dates.

- Historical annual arithmetic asset return `mu_hist[i] = 252 × mean_t(r[i,t])`.
- Forecast shrinkage `mu[i] = (1-s) × mu_hist[i] + s × mean_i(mu_hist[i])`; `s` default `0.50` is **a heuristic**.
- Annual covariance `Sigma = 252 × sample_cov(daily_returns)` (sample `ddof=1`).
- Portfolio arithmetic expected return `mu_p = weights @ mu`; annual volatility `sqrt(weights @ Sigma @ weights)`.
- Portfolio daily series assumes constant daily rebalancing: `r_p,t = sum_i(w_i * r_i,t)`.
- Sharpe `S = (mu_p - rf)/max(annual_vol, 1e-6)`.
- Daily minimum acceptable return `MAR_daily = (1 + MAR_annual)^(1/252)-1`.
- Downside deviation `D = sqrt(252 × mean_t(min(r_p,t - MAR_daily, 0)^2))`.
- Regularized Sortino `(mu_p - MAR_annual)/max(D, max(.015, .15 * equal_weight_downside))`. **Because of this floor and forecast shrinkage, this is a regularized, estimated Sortino—not an unmodified historical Sortino.**
- Objective `alpha*(Sharpe / sharpe_scale) + (1-alpha)*(Sortino / sortino_scale)` with default `alpha=.40`. Each scale is `max(.10, p90-p10)` from a reproducible set of 256 feasible portfolios. Weights sum to 1, lie in `[0, maximum_position]`, and are non-short. SLSQP multi-start is a local/nonconvex solution, **not proof of global optimality**.
- Correlation uses the ordinary Pearson sample correlation of aligned daily returns.
- Numerical formulas were checked against independent numpy and hand-computed two-asset cases, and a grid search over feasible two-asset allocations.

## Wharton financial model

- 2026 is Year 0, before investing.
- Beginning of 2027: contribute $300,000.
- Beginning of 2028: contribute $150,000.
- Beginning of each 2033–2042: pay $50,000 (10 nominal payments).
- If user supplies an optional facility what-if in 2033, current-year operations are funded first; facility can use only remaining available assets. This feature does **not** ensure future payments are protected by a separately funded reserve.
- Per-year recursion: `available = opening_wealth + beginning_contribution`; deduct required current operating payment up to available funds; deduct optional facility amount up to remaining assets; `year_earnings = invested_amount × assumed_annual_rate`; `ending_wealth = invested_amount + year_earnings`. Explicit shortfall flags prevent fictional negative holdings.
- An independent **Decimal** arithmetic model agreed to the cent using an illustrative, user-editable 6% annual rate:

| Year | Projected end-of-year balance |
|---|---:|
| 2027 | $318,000.00 |
| 2028 | $496,080.00 |
| 2032 | $626,289.57 |
| 2033 | $610,866.94 |
| 2042 | $423,007.10 |

Wharton does **not** require 6% returns; only its specified cash flows are mandatory. This deterministic scenario is not a probabilistic funding or reserve adequacy analysis. WInS account illustration ($100,000 default) is separate and is never added to the 2027–2042 projections.

## Streamlit Cloud compatibility

- Official Streamlit documentation confirms the repository-root app and root `requirements.txt` structure.
- Imports use valid `streamlit`, `plotly`, `pandas`, `numpy`, `scipy`, `yfinance` APIs as far as static checks and simulated execution can establish.
- Plotly charts and all dashboard tabs were rendered as Python figure/table objects during offline simulations.
- **NOT VERIFIED**: actual Streamlit installed package/runtime, Streamlit Cloud build log, Yahoo Finance connectivity from Streamlit Cloud, browser visual rendering. These require a live deployment.

## Remaining risks

The optimizer is a simplified research model. It does not forecast future returns reliably, find a proven global optimum, adjust for transaction costs, guarantee against equity drawdowns, choose a 2033 operating reserve, or estimate the probability of meeting Laura's 10 cash-flow commitments. The annual return used for projected earnings must remain an explicit assumption. Compare actual Yahoo source values before relying on a live investment decision.
