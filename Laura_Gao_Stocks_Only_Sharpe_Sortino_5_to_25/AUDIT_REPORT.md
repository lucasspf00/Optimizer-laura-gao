# Stocks-only 5%–25% update — verification report

## Scope

Starting from the previous all-assets package, this update changed the **default allocation bounds** to minimum 5% and maximum 25% **of the stock sleeve only**. The existing combined scaled Sharpe/Sortino objective is unchanged. The Streamlit app no longer asks for ETF tickers and defaults to seven individual stocks.

## Verified locally

- **85 automated tests passed** in the available Python environment, including an offline mocked-Streamlit rendering test; this is not a real Streamlit Cloud installation.

- Constraints: each stock >= 5%, <= 25%; weights sum to 100% of the stock allocation.
- Feasibility: 4 stocks force 25% each, 20 stocks force 5% each; three or 21 are rejected.
- Combined score still equals `0.4 × Sharpe/SharpeScale + 0.6 × Sortino/SortinoScale` for the default settings.
- Known ETF inputs such as VTI/VBR/VXUS are rejected (not an exhaustive classification system).
- The offline demonstration dataset is 100% synthetic stock-like price data and is expressly labeled not real.
- Wharton projection: $300,000 at the start of 2027, $150,000 at the start of 2028, ten $50,000 operating payments at the beginning of 2033–2042. The projection uses a **user-entered whole-portfolio scenario return**, not stock-only historical returns.
- Python source compilation and ZIP root file structure are checked.

## Limitations

- The optimizer gives an **in-sample**, nonconvex numerical solution; it does not certify the global mathematical optimum or true future Sharpe or Sortino performance.
- User-entered custom tickers are not comprehensively classified as stocks vs. ETFs; common ETF ticker checks catch only known examples.
- Position weights are relative to the **stock sleeve**, not the total Wharton portfolio.
- This is not a multi-asset allocation or high-certainty operating-reserve optimizer.
- Yahoo rate limiting and a real Streamlit Cloud installation cannot be certified from the offline test environment.
