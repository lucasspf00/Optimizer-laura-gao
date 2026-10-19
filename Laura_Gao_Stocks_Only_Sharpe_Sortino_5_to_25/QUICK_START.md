# Quick start — Laura Gao Stocks-Only Optimizer

## What changed

- Input **individual stocks only**; VTI, VBR, VXUS and other ETFs are allocated separately.
- Every stock is assigned **at least 5% and at most 25% of the individual-stock allocation**.
- The Sharpe/Sortino objective remains **40%/60%** by default; it is not changed.
- The Wharton 2027–2042 financial projection remains available, using a separate assumed return for the **full portfolio**.

**Required universe:** 4–20 stocks (the 4- and 20-stock boundary cases force equal weights).

## Upload to GitHub

1. Download and extract the ZIP.
2. Open your existing GitHub repository on branch `main`.
3. Upload **all extracted files** at the exact directory that contains the deployed `app.py`, replacing `app.py`, `optimizer.py`, `market_data.py`, `projections.py`, plus the `examples/` folder, tests and docs.
4. Commit your changes. Keep the current Streamlit **Main file path** pointing at the actual location of `app.py` (e.g. `app.py` if in the repo root).
5. Redeploy or refresh Streamlit. Use Python 3.12 as the pinned-dependency target.

## Run locally

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open in offline **synthetic** demo first; then switch to Yahoo Finance and enter your own 4–20 individual stock tickers.

### Example stocks

`PGR, MA, JNJ, ADP, ECL, MSFT, RSG`

### Example whole-portfolio projection

The 6% scenario is **not** obtained from those seven stocks. It is a user-entered return assumption for the complete portfolio, including separately managed ETFs and bonds. Wharton contributes $300,000 in 2027, $150,000 in 2028, and withdraws $50,000 annually at the beginning of 2033–2042.
