# Streamlit Community Cloud deployment fix

## Reported error

```
installer returned a non-zero exit code
Error during processing dependencies
```

Those are summary lines, not a diagnosis. The real reason appears ABOVE them in Streamlit's build logs (look for `ERROR:`, `Could not find a version`, `Failed building wheel`, or `ResolutionImpossible`).

## Changes from audited v3

- Replaced broad dependency ranges with pinned packages compatible with **Python 3.12**.
- Removed `pytest` from runtime requirements (tests do not need to be installed in production).
- **No math, optimizer, CSV, or projection source code was changed.**

### New `requirements.txt`

```
streamlit==1.53.0
numpy==1.26.4
pandas==2.2.3
scipy==1.14.1
plotly==6.2.0
yfinance==0.2.65
```

## How to deploy

1. Open your existing GitHub repo in branch `main`.
2. Upload **all extracted files** from this ZIP, overwriting the existing ones; especially `requirements.txt`.
3. Check that both `app.py` and `requirements.txt` are visible in the repo root, not inside another folder.
4. Open Streamlit Community Cloud. On the app's deployment screen, set `Main file path` to `app.py`.
5. In **Advanced settings** choose **Python 3.12** (do not add `python==3.12` to requirements.txt).
6. Deploy. If the app already exists using another Python version, Community Cloud requires redeployment to change Python (check Streamlit docs).
7. If dependency installation fails, open **Manage app > Logs** and copy the first error line and 15 lines above it.

## Validation status

- Original 66 pytest tests pass in the sandbox's Python 3.13 environment on existing installed numpy/pandas/scipy.
- Source Python files compiled successfully and the ZIP has its entrypoint in the root.
- The pinned dependency combination was selected for Python 3.12 compatibility, but **package downloading, installation, and live Cloud startup could not be reproduced here** because PyPI is not reachable from the sandbox.
- A failed installer message by itself does not prove the old dependencies are invalid; a network failure or configuration issue is also possible.
