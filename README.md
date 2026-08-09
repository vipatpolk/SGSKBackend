# SGSK Backend

This is the Python **FastAPI** backend for the [ShareLot](https://github.com/vipatpolk/ShareLot) investment portfolio tracker. It serves as the data aggregation, calculation, and proxy layer between the Angular frontend and external data sources.

## Features

- **Google Sheets Integration**: Fetches published CSV sheets dynamically to retrieve user transaction logs based on tab IDs (`us-stock`, `thai-stock`, `crypto`, `mutual-fund`, `closed-position`).
- **FIFO Share Lot Engine**: Computes First-In, First-Out (FIFO) share lots, remaining open positions, cost basis, and realized P/L server-side.
- **Decoupled Architecture**: Encapsulates Google Spreadsheet IDs and GID mappings in `config/sheet_config.py`, allowing the frontend to query endpoints cleanly via tab IDs without exposing raw spreadsheet metadata.
- **Market Data Proxy**: Fetches and aggregates real-time quotes, exchange rates, and metadata from:
  - **Yahoo Finance** (U.S. Stocks, Thai Stocks via `.BK`, USD/THB FX rate)
  - **Binance TH** (Cryptocurrency orderbook prices)
  - **SEC Thailand** (Thai Mutual Fund daily NAV lookups)
- **CORS Management**: Provides clean `/api/backend/*` endpoints for the frontend, avoiding browser CORS restrictions associated with calling third-party financial APIs directly.

## API Endpoints

### Share Lot & Transactions
- `GET /share-lot/sheet/{tab_id}` — Fetches transaction logs and calculates FIFO share lots for a specific asset category (`us-stock`, `thai-stock`, `crypto`, `mutual-fund`, `closed-position`).
- `GET /share-lot/sheets` — Fetches and aggregates transaction logs across all active tabs in the portfolio.

### Market Data & Prices
- `GET /price/batch?symbols=AAPL,PTT.BK` — Batch fetches market quotes and currency data from Yahoo Finance and Binance TH.
- `GET /price/symbol/{symbol}` — Fetches single symbol market data.
- `GET /price/rate/usd-thb` — Live USD/THB exchange rate lookup.
- `GET /nav/fund/{symbol}` — Fetches daily NAV data for Thai Mutual Funds via SEC Thailand API.

## Requirements

- Python 3.9+
- `fastapi[standard]`
- `httpx`
- `uvicorn`

## Installation

1. Clone the repository and navigate to the project directory:
   ```bash
   git clone https://github.com/vipatpolk/SGSKBackend.git
   cd SGSKBackend
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On Unix/macOS:
   source .venv/bin/activate

   pip install -r requirements.txt
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

## API Documentation

FastAPI automatically generates interactive API documentation. Once the server is running, you can explore the endpoints at:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

## Configuration

Google Sheets IDs, tab GID mappings, and external API configurations are defined in `config/sheet_config.py`. Ensure the target Google Sheet is set to "Anyone with the link can view".

## License

This project is private and proprietary.
