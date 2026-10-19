# Streamlit deployment notes

Target **Python 3.12** with the provided pinned `requirements.txt`.

1. Extract the ZIP and upload its contents, not the ZIP itself, to GitHub.
2. Keep `app.py`, `requirements.txt`, `optimizer.py`, `market_data.py`, and `projections.py` together, along with `examples/`.
3. In Streamlit select the correct branch and the entrypoint path matching your GitHub layout. For root uploads: **`app.py`**.
4. Python version is selected in **Advanced settings** when creating a Streamlit Cloud deployment.
5. Check Streamlit build logs if package installation fails. Errors mentioning `import plotly` often indicate dependencies did not install or the requirements file was not discovered.
6. If Yahoo is blocked on the cloud host, use **Upload CSV** with valid daily adjusted prices for **individual stocks**.

No network/Cloud deployment could be performed in the offline audit environment.
