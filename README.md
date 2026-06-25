# Machine Learning-Based Predictive Valuation System for Second-Hand Vehicles

**Final Year Project — BSc (Hons) Computing, Arden University**
**Author:** Syed Shayaan Ali Ali (STU195050) · **Ethics ref:** P17519 (Low Risk, approved)

**🚗 Live demo:** <https://autovalue-fyp.onrender.com> — enter a car's details for a market-adjusted
valuation with a confidence range, deal verdict, value breakdown, 5-year depreciation forecast and
comparable cars. *(Free host — the first load may take ~50 s to wake from idle.)*

A web-based system that predicts the resale price of used vehicles using machine
learning. Real-time market data is collected via web scraping and processed in a
Python backend, where regression models (Linear Regression, Random Forest,
XGBoost) generate price estimates. A responsive frontend lets users enter
vehicle details and receive instant predictions.

## Stack

| Layer | Technology |
|-------|------------|
| Scraping | `requests` + `BeautifulSoup` |
| Data / ML | `pandas`, `numpy`, `scikit-learn`, `xgboost` |
| API | `Flask` + `flask-cors` |
| Frontend | HTML + Tailwind (CDN) + vanilla JS |
| Testing | `pytest` |

## Project structure

```
.
├── data/
│   ├── raw/        # untouched input CSVs (scraped or downloaded)
│   └── cleaned/    # post-pipeline data
├── notebooks/      # EDA / experimentation
├── src/
│   ├── scraper/    # AutoTrader scraper module
│   ├── pipeline/   # cleaning + feature engineering
│   ├── models/     # train / evaluate / serialised .pkl
│   └── api/        # Flask /predict endpoint
├── frontend/       # static UI
├── tests/          # pytest suite
├── docs/           # gantt, supervisor logs, screenshots
└── report/         # 10,000-word dissertation
```

## Quick start

```powershell
# 1. Create venv (using full Python path on Windows)
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Train models (uses dataset in data/raw/)
python -m src.models.train

# 4. Run API
python -m src.api.app

# 5. Open frontend/index.html in a browser
```

## Ethics

- All data is **publicly available, non-personal** vehicle listing information
  (make, model, year, mileage, fuel type, transmission, price).
- No human subjects involved.
- Project authorised under Arden Ethics Project P17519 (Low risk).

