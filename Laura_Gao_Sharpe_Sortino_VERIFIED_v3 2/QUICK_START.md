# Quick start

**Mac:** Open Terminal, `cd` into the extracted project folder, then:

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

**Windows:** Open Command Prompt in the extracted folder:

```bat
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

**GitHub:** Upload the extracted `app.py`, `optimizer.py`, `projections.py`, `market_data.py`, `requirements.txt`, `examples/`, `tests/` into the repository's root (not another folder). On Streamlit Community Cloud, choose `main` and **`app.py`** as Main file path.

**Example mode:** The app opens using synthetic prices without needing Yahoo. Select **Yahoo Finance** for real ticker analysis.

**Annual earnings:** The prefilled 6% is illustrative, not Wharton's required return. You can choose any justified assumption.

## Already deployed but getting `0 complete price rows`?

You do **not** need to create a new repository. Replace `app.py`, `optimizer.py`,
`market_data.py`, and `projections.py` in your GitHub repository root with
these updated versions. Commit changes and let Streamlit redeploy. The error message will identify incomplete tickers or an
empty Yahoo download. If Yahoo blocks Streamlit Cloud, use a CSV of historical
adjusted prices instead.


**Price verification:** Open the fourth tab, *Verify source prices*. It shows
which dates and adjusted closing prices the model actually used. In Yahoo Finance
mode, upload a separately downloaded Yahoo historical CSV containing `Date` and
`Adj Close` to compare ticker values. This feature cannot guarantee that Yahoo
itself is always available on Streamlit Cloud.
