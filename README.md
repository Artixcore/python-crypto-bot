# Binance Spot — BTC & SOL focused bot

Minimal Spot stack for **BTC/USDT** and **SOL/USDT** only: MA+RSI strategy, fixed-% position sizing, stop/take-profit, concurrent two-pair paper/live runner, and optional Telegram UI.

## Scope

- **Universe:** `BTC`, `SOL`, quote `USDT` ([`universe.py`](src/crypto_bot/universe.py)).
- **Strategy:** SMA crossover + RSI filter ([`strategies/ma_rsi.py`](src/crypto_bot/strategies/ma_rsi.py)).
- **Risk:** `CRYPTO_BOT_POSITION_SIZE_PCT_OF_EQUITY` (default 2%), shared SL/TP policy, up to **two** open positions (one per pair).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
```

Backtest (defaults follow `.env` strategy params):

```bash
python -m crypto_bot.cli backtest --symbol BTC/USDT --timeframe 1h
```

Concurrent paper/live runner:

```bash
CRYPTO_BOT_PROFILE=paper python -m crypto_bot.cli run --interval-sec 60
# Optional: --symbols BTC/USDT,SOL/USDT
```

Live requires `CRYPTO_BOT_PROFILE=live`, API keys, and `CRYPTO_BOT_LIVE_CONFIRM=yes`.

### Telegram

```bash
python -m crypto_bot.telegram_bot
```

`/balance` shows **BTC, SOL, USDT** only. `/snapshot` is restricted to configured pairs. `/buy` and `/sell` need `CRYPTO_BOT_TELEGRAM_TRADING_ENABLED=yes` and **live** profile with confirmation.

See [RUNBOOK.md](RUNBOOK.md) for operations.

## Disclaimer

Automated trading can result in total loss of capital. For personal or educational use only.
