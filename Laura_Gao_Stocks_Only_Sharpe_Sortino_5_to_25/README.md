# Laura Gao — Individual-Stock Sharpe + Sortino Optimizer

**Scope: INDIVIDUAL STOCKS ONLY.** VTI, VBR, VXUS and any other ETFs are managed in a separate portfolio allocation. This optimizer distributes the **individual-stock sleeve** across the stock tickers the user enters. It does not determine what percentage of the full portfolio should be in stocks, ETFs, or bonds.

## Core features

1. **One allocation**: maximizes the existing combined 40% Sharpe + 60% Sortino objective (scales determined from reproducible feasible sampled portfolios). The objective formula has **not changed**.
2. **All submitted stocks remain included**, with a **fixed 5% minimum and 25% maximum per stock** of the stock sleeve and total stock weights equal to 100%. No leverage and no short positions.
3. **Correlation matrix**: Pearson correlations of synchronized daily adjusted returns.
4. **Annual projection**: Wharton's cash flows and year-by-year balances (2027–2042), using a **separate, user-specified whole-portfolio expected return**. This stock optimizer does not know the return of separately managed ETFs/bonds.
5. **Price audit**: inspect the source adjusted closes and optionally compare with a separate Yahoo Finance `Adj Close` CSV export.

### Valid number of stocks

Because every stock receives between 5% and 25% of the stock sleeve:

- **4 to 20 individual stocks** are permitted.
- With **4**, all must be exactly 25% (no allocation freedom).
- With **20**, all must be exactly 5% (no allocation freedom).
- **7 to 12 stocks** can provide more flexibility in this constrained model, but that range is a workflow preference, not a competition requirement.
- An infeasible count is reported; the optimizer will not silently remove stocks.

These percentages are relative to the **stock sleeve only**. Example: a $20,000 stock allocation inside a $100,000 WInS portfolio gives a 5% stock position of $1,000, or 1% of the full portfolio. The $20,000 default is only an illustrative budget, **not a recommendation**.

## Run on your computer

Use Python **3.12**, then:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open in **Offline demo (synthetic)** to validate the interface without Yahoo; the fake tickers begin `DEMO_` and are **not real stocks**. For actual analysis, select Yahoo Finance and enter stock tickers (by default `PGR, MA, JNJ, ADP, ECL, MSFT, RSG`) or upload a wide CSV containing daily adjusted stock prices, with a Date column. The CSV must not contain ETFs. A list of common ETFs is rejected, but the app cannot verify *every* possible financial security's classification.

**Historical prices and estimated Sharpe/Sortino values are not forward forecasts or guarantees.** The estimated return is annual arithmetic based on 252 trading days and shrunk toward a common cross-sectional mean. The downside-deviation denominator includes a regularization floor. Optimization is numerical and in-sample (no guaranteed global optimum).

## Wharton financial projection

- Beginning of **2027**: invest **$300,000**.
- Beginning of **2028**: contribute **$150,000** more.
- Beginning of each year **2033 through 2042**: pay **$50,000** (10 nominal payments = $500,000).
- The interface's annual return, 6% by default, is only an illustration. Wharton **does not mandate a return rate**.
- The projection must represent **Laura's overall investment portfolio**, including the separately determined ETFs and bonds, and does **not** use the optimized stock-only return automatically.
- The WInS simulator balance must not be included in Laura's long-term model.
- This simple deterministic model does not size the 2033 reserve or produce a high-confidence funding probability or facility-contribution range.

## GitHub + Streamlit Community Cloud

Extract this ZIP and upload **its contents** to the GitHub repo root. Both `app.py` and `requirements.txt` must appear immediately upon opening the repository. On Streamlit Cloud, enter **Main file path = `app.py`** and select **Python 3.12** in Advanced settings when creating a new deployment. If your GitHub repository stores the files in a subfolder, use `<subfolder>/app.py` instead.

Installed packages are pinned in `requirements.txt`; actual live Yahoo API access and Streamlit Cloud installation must be verified after deployment. An API rate limit may require you to upload historical CSV files instead.

## Project files

- `app.py`: Streamlit interface with stocks-only limits
- `optimizer.py`: combined Sharpe + Sortino engine, unchanged objective, new default limits
- `market_data.py`: historical price adapters and common ETF guard
- `projections.py`: Wharton cash-flow arithmetic
- `examples/SYNTHETIC_STOCK_PRICES_NOT_REAL.csv`: offline fake-stock test input
- `tests/`: automated financial, price-data and constraint tests
- `QUICK_START.md`: minimal setup instructions
- `AUDIT_REPORT.md`: validation results and remaining limitations

Run tests with `python -m pytest -q` (pytest is required for tests but not for runtime).
