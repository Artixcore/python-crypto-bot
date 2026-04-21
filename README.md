# Binance Spot AI Trading Agent

Rule-first Spot trading stack: historical data and caching, backtesting, risk-governed execution, paper and live modes, optional ML filter.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
```

Fetch klines (read-only):

```bash
python -m crypto_bot.cli fetch-klines --symbol BTC/USDT --timeframe 1h --limit 500
```

Run a backtest:

```bash
python -m crypto_bot.cli backtest --symbol BTC/USDT --timeframe 1h
```

Paper trading (simulated broker):

```bash
CRYPTO_BOT_PROFILE=paper python -m crypto_bot.cli run --interval-sec 60
```

Live trading requires `CRYPTO_BOT_PROFILE=live`, valid API keys, and `CRYPTO_BOT_LIVE_CONFIRM=yes`.

### Local live dashboard (HTML)

Read-only Binance Spot data in the browser: balances, tickers, open orders, recent trades, exchange time. API secrets never leave the server; bind defaults to **127.0.0.1** only.

```bash
python -m crypto_bot.dashboard
```

Open `http://127.0.0.1:8765` (or your `CRYPTO_BOT_DASHBOARD_PORT`). Optional: `CRYPTO_BOT_DASHBOARD_SYMBOLS=BTC/USDT,ETH/USDT` in `.env`.

See [RUNBOOK.md](RUNBOOK.md) for operations and promotion workflow.

## Disclaimer

Automated trading can result in total loss of capital. For personal or educational use only.
