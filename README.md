# SGSK Backend

This is the Python **FastAPI** backend for the [ShareLot](https://github.com/vipatpolk/ShareLot) investment portfolio tracker. It serves as the data aggregation, calculation, and proxy layer between the Angular frontend and external data sources.

## Features

- **Google Sheets Integration**: Fetches published CSV sheets dynamically to retrieve user transaction logs.
- **FIFO Share Lot Engine**: Computes First-In, First-Out (FIFO) share lots, remaining open positions, cost basis, and realized P/L server-side.
- **Market Data Proxy**: Fetches and aggregates real-time quotes, exchange rates, and metadata from:
  - **Yahoo Finance** (U.S. Stocks, Thai Stocks via `.BK`, USD/THB FX rate)
  - **Binance TH** (Cryptocurrency orderbook prices)
  - **SEC Thailand** (Thai Mutual Fund daily NAV lookups)
- **CORS Management**: Provides clean `/api/backend/*` endpoints for the frontend, avoiding browser CORS restrictions associated with calling third-party financial APIs directly.

## Requirements

- Python 3.9+
- `fastapi[standard]`

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

Start the development server using the FastAPI CLI or Uvicorn:

```bash
fastapi dev main.py
```
Alternatively:
```bash
python main.py
```

The server will run on `http://127.0.0.1:8000` by default.

## API Documentation

FastAPI automatically generates interactive API documentation. Once the server is running, you can explore the endpoints at:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

## Configuration

Google Sheets IDs and other external API configurations can be found in `config/settings.py` or configured via environment variables. Ensure the target Google Sheet is set to "Anyone with the link can view".

## License

This project is private and proprietary.
