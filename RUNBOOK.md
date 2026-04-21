# Operations runbook — Binance Spot agent

## Modes

| Profile | Purpose |
|---------|---------|
| `dev` | Signals and sizing logged; no broker orders (journal `dev_skip`). |
| `paper` | `PaperBroker` simulates fills; SQLite journal under `data/journal/trades.db`. |
| `live` | Real Spot orders; requires `CRYPTO_BOT_LIVE_CONFIRM=yes` and API keys. |

`CRYPTO_BOT_DRY_RUN=true` logs intended orders without sending (any profile).

## Promotion workflow (manual gate)

1. **Backtest** — `python -m crypto_bot.cli backtest --symbol BTC/USDT --timeframe 1h`
2. **Walk-forward / OOS** — `python -m crypto_bot.cli walk-forward --train-bars 400 --test-bars 100`
3. **Paper** — run for weeks; compare journal fills to backtest assumptions (slippage, frequency).
4. **Live** — smallest viable size; monitor daily loss limit and kill switch.

Do not enable `CRYPTO_BOT_LIVE_CONFIRM=yes` until paper validation passes your criteria.

## Kill switch

Set `CRYPTO_BOT_KILL_SWITCH=true` in the environment and restart the process. The risk layer returns `HALT` for new risk.

## ML filter

1. Train: `python -m crypto_bot.cli train-ml-filter --out models/ml_filter.joblib`
2. Point `CRYPTO_BOT_ML_MODEL_PATH` at the file.
3. Use `CRYPTO_BOT_ML_SHADOW=true` to log scores without blocking trades; remove shadow after review.

## Continuous optimization

Re-run walk-forward when you change parameters or data regime. Treat parameter changes as a new strategy version; keep a short changelog and retain prior artifacts for comparison.

## Failure handling

- Repeated API errors: check Binance status, rate limits, and API key permissions (Spot only; no withdraw).
- SSL or timeout: verify network path to `https://api.binance.com` (public klines use Spot REST directly).

## Disaster recovery

- Stop the runner (Ctrl+C or process supervisor).
- Set kill switch before investigating.
- Journal SQLite file can be copied for audit; do not delete while debugging open issues.
