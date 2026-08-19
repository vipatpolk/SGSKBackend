# SGSK Backend

This is the Python **FastAPI** backend for the [ShareLot](https://github.com/vipatpolk/ShareLot) investment portfolio tracker. It serves as the data aggregation, calculation, and proxy layer between the Angular frontend and external data sources.

## Features

- **Google Sheets Integration**: Fetches published CSV sheets dynamically to retrieve user transaction logs based on tab IDs (`us-stock`, `thai-stock`, `crypto`, `mutual-fund`, `closed-position`).
- **FIFO Share Lot Engine**: Computes First-In, First-Out (FIFO) share lots, remaining open positions, cost basis, and realized P/L server-side, with support for mutual fund exchange dispositions (`EX-OUT` and `EX-IN`).
- **Strict Asset Type Rules**: Identifies Thai Mutual Funds strictly by `.BKFUND` suffix (no symbol prefix heuristics).
- **100% API-Driven Dividend Engine**: Calculates historical dividend cash flows and forward income projections purely from live API feeds (Yahoo Finance for US & Thai equities, SEC Thailand API for Mutual Funds) with exact share balance reconstruction on dividend ex-dates.
- **Decoupled Architecture**: Encapsulates Google Spreadsheet IDs and GID mappings in `config/sheet_config.py`, allowing the frontend to query endpoints cleanly via tab IDs without exposing raw spreadsheet metadata.
- **Market Data Proxy**: Fetches and aggregates real-time quotes, exchange rates, and metadata from:
  - **Yahoo Finance** (U.S. Stocks, Thai Stocks via `.BK`, USD/THB FX rate)
  - **Binance TH** (Cryptocurrency orderbook prices)
  - **SEC Thailand** (Thai Mutual Fund daily NAV lookups)
- **CORS Management**: Provides clean `/api/backend/*` endpoints for the frontend, avoiding browser CORS restrictions associated with calling third-party financial APIs directly.

## API Endpoints

### Portfolio & Holdings
- `GET /portfolio/holdings` — Unified holdings valuation endpoint returning fully calculated open positions, closed positions, lot-level valuations, and portfolio KPI summary metrics in target currency (`THB` or `USD`).
- `GET /portfolio/performance` — Comprehensive investment returns analytics with dynamic timeframe filtering (`YTD`, `1M`, `3M`, `6M`, `1Y`, `ALL`, or custom date bounds), asset class performance, and Top Gainers / Losers leaderboards.
- `GET /portfolio/dividends` — 100% API-driven dividend analytics and income tracking endpoint returning ex-date share-weighted historical payouts, withholding taxes (15% US, 10% TH), monthly cashflow breakdowns, Yield on Cost (YOC), and forward projected annual income.
- `POST /portfolio/allocation` — Target asset allocation and rebalancing engine calculating actual vs target weights, actionable monetary buy/sell deltas, currency exposure (USD vs THB), and concentration weights.

### Share Lot & Transactions
- `GET /share-lot/sheet/{tab_id}` — Fetches transaction logs and calculates FIFO share lots for a specific asset category (`us-stock`, `thai-stock`, `crypto`, `mutual-fund`, `closed-position`).
- `GET /share-lot/sheets` — Fetches and aggregates transaction logs across all active tabs in the portfolio.

### Market Data & Prices
- `POST /price/fetch-prices` — Batch fetches market quotes and currency data for a list of portfolio asset summaries across Yahoo Finance, Binance TH, and SEC Thailand.
- `GET /price/exchange-rate` — Live exchange rate lookup (defaults to `from_currency=USD&to_currency=THB`).

### Financial Tools & Simulation
- `POST /portfolio/tools/simulate-order` — Forward Buy / Sell order simulation calculating projected average cost, breakeven, and P/L impact with custom brokerage fees.
- `POST /portfolio/tools/solve-target-cost` — Target average cost solver computing exact required shares and capital outlay to achieve a desired cost basis.
- `POST /portfolio/tools/tvm` — Time Value of Money (TVM) multi-solve calculation engine supporting 5 solve modes ($FV$, $PMT$, $PV$, $N$, $Rate$), 8 compounding frequencies, and year-by-year accumulation schedule generation.
- `POST /portfolio/tools/rebalance` — Multi-asset class portfolio rebalance planning engine supporting Standard Two-Way rebalancing and No-Sell minimum cash inflow ($\Delta C_{\text{min}}$) & custom deposit budget allocation.


### Mutual Fund NAVs
- `POST /nav/fetch` — Fetches daily NAV data for Thai Mutual Funds via the SEC Thailand API.

## Requirements

- Python 3.9+
- `fastapi`
- `httpx`
- `uvicorn`
- `pydantic`

## Installation

1. Clone the repository and navigate to the project directory:
   ```bash
   git clone https://github.com/vipatpolk/SGSKBackend.git
   cd SGSKBackend
   ```

2. Create a virtual environment and install production dependencies:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On Unix/macOS:
   source .venv/bin/activate

   pip install -r requirements.txt
   ```

3. (Optional) Install developer dependencies for testing, linting, and type checking:
   ```bash
   pip install -r requirements-dev.txt
   ```

## Running the Server

Start the development server using Python or FastAPI CLI:

```bash
python main.py
```
Alternatively:
```bash
fastapi dev main.py
```

The server will run on `http://127.0.0.1:8000` by default.

## Interactive API Documentation

FastAPI automatically generates interactive API documentation. Once the server is running, explore the endpoints at:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

## Testing & Quality Assurance

`SGSKBackend` uses `pytest`, `respx` (for HTTP mocking), `ruff` (linter/formatter), and `mypy` (static type checker).

### Running Unit & Deterministic E2E Tests

Run the test suite with coverage enforcement ($\ge 80\%$ threshold):

```bash
pytest -m "not live_e2e" --cov=. --cov-report=term-missing
```

### Running Live External API Health Checks

To run integration tests against live Google Sheets, Yahoo Finance, Binance TH, and SEC Thailand APIs:

```bash
pytest -m "live_e2e" --verbose
```

### Code Formatting & Linting

Run Ruff to lint code:

```bash
ruff check .
```

To automatically fix fixable lint issues:

```bash
ruff check --fix .
```

### Static Type Checking

Run Mypy type checker across all Python files:

```bash
mypy .
```

## Continuous Integration (CI/CD)

The repository includes GitHub Actions workflows under `.github/workflows/`:

- **Backend CI Pipeline (`backend-ci.yml`)**: Triggered on pull requests and pushes to `main`/`master`. Runs Ruff linting, Mypy type checks, Pytest unit/E2E test suite, and uploads code coverage reports.
- **Live Health Check Cron (`live-e2e-cron.yml`)**: Scheduled daily cron workflow verifying live third-party financial API connectivity.

## Configuration

Google Sheets IDs, tab GID mappings, and external API configurations are defined in `config/sheet_config.py`. Ensure the target Google Sheet is set to "Anyone with the link can view".

## License

This project is private and proprietary.
