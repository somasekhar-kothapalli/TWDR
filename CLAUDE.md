# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

TWDR: data pipeline for the "TWPR Lite" MCX crude-oil options framework described in `README.md` (the trading runbook: trigger = EIA crude surprise vs expected `E_c = (consensus + API)/2`, three vetoes, candle-break confirmation, fixed risk rules). `README.md` is strategy, not dev docs. `docs/twdr_learning_resources.md` is a reading list. Times are IST; EIA releases Wed 20:00 IST (21:00 after US winter-time switch).

## Commands

Python venv is `.venv` (Windows). Run everything from repo root as modules, not scripts. Needs Playwright chromium (`playwright install chromium`).

```
pip install -r requirements.txt            # file is UTF-16 encoded
python -m app.consensus_fetcher [--date DD-MM-YYYY] [--sites tradingeconomics investing]
python -m app.api_monitor [--once] [--date DD-MM-YYYY]     # polls every 5 min up to 4h
python -m app.eia_actuals [--once] [--date DD-MM-YYYY]     # polls every 60s up to 90 min
python -m app.utils.wti_candle                              # see note below
python -m app.scraper.sites.investing --slug <slug> [--date DD-MM-YYYY]   # debug one scraper (cli.py)
```

No test suite exists yet (`sources.py` mentions `tests/test_sources.py`, which is absent). No linter config.

## Architecture

Pipeline of independent CLI stages; each writes one JSON file in `data/`, and file paths are constants in `app/utils/common.py` (import them, never re-spell names). `common.py` also lists files for stages not yet in the repo (`signal_engine`, `market_data`, `surprise_history`, `journal`, `crude_recorder`, `ng_recorder`) — `data/` contents (`consensus.json`, `api_report.json`, `eia_actuals.json`, `wti_candle.json`, `twdr.db`) are the only outputs so far.

Stages: `consensus_fetcher` (Tue, consensus crude/gasoline/distillate) -> `api_monitor` (Wed ~02:00 IST, API crude) -> `eia_actuals` (Wed 20:00 IST, crude/Cushing/gasoline/distillate/net-imports changes, optional refinery util change and Cushing level) -> `utils/wti_candle` (NYMEX WTI 5-min release candle via yfinance, USD not MCX rupees).

Scraping layer (`app/scraper/`):
- `sources.py` is the single registry mapping indicator -> per-site slug (tradingeconomics, investing.com). Add/fix URLs here. A missing entry means that site doesn't carry the indicator.
- `utils/base.py` `CalendarScraper`: shared contract. `fetch_page(slug)` returns `{"calendar_rows": [{release_date, time, actual, consensus, previous}] | None, "stats": {...}}` or `None` on failure. Site classes in `sites/` only implement `parse_rows`/`parse_stats`. `utils/calendar.py` has row selection (`row_for_release`, `pending_row`, `current_release`).
- `browser.py`: headless Playwright chromium sessions (sites block plain HTTP).

Race pattern (`utils/racer.py`): every fetcher runs both sites concurrently in threads; per indicator, first valid value wins and the output records the source. Missing/inconsistent data fails loudly (wrong baseline is worse than none), sends a Telegram alert via `utils/telegram.py` (`send_exception`). Entry points end with `os._exit(code)` deliberately so losing daemon Playwright threads can't hang shutdown — keep that.

Gotchas:
- Sign convention: build positive, draw negative, in million barrels.
- API Cushing/gasoline/distillate are deliberately NOT scraped (paywalled, stale/dead on sites). Don't re-add.
- `eia_levels.cushing_level` scrapes EIA's public table and cross-checks level delta against the change to reject stale pages.
- `wti_candle.py` has a `fetch`/`release_candle` but no CLI despite `argparse`/logger copy-paste from `eia_levels`; `sys.exit` on missing data. Yahoo keeps ~60 days of 5m data.
- `app/main.py` only calls `load_dotenv()`.

## Config

`.env` (gitignored; don't print): `EIA_API_KEY`, `EIA_API_KEY_2`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Use `common.env()` to read (treats blank/`#` placeholders as unset). Logging via `setup_logging()` (mutes httpx/httpcore because Telegram token is in URL path).
