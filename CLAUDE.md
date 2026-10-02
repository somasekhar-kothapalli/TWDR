# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

TWDR: data pipeline plus Tier 1 signal engine for an EIA-inventory-surprise strategy on MCX crude options. `README.md` is the Tier 1 trading runbook (strategy, not dev docs): per-stock deviations of crude, gasoline and distillate against API-adjusted baselines, the setup order, the 20:05 candle check, option/risk/exit rules. Tiers 2 to 4 (Cushing, refinery, SPR, imports, product supplied) are design notes only, in `docs/tiers_2_4.md`. `docs/signal_engine.md` is the developer spec and decision log; `docs/twdr_ng.md` is the natural gas (TWDR-NG) scoping doc, nothing built; `docs/twdr_learning_resources.md` is a reading list. Times are IST; EIA releases Wed 20:00 IST (21:00 after US winter-time switch).

## Commands

Python venv is `.venv` (Windows). Run everything from repo root as modules, not scripts. Needs Playwright chromium (`playwright install chromium`).

```
pip install -r requirements.txt            # file is UTF-16 encoded
python -m app.consensus_fetcher [--date DD-MM-YYYY] [--sites tradingeconomics investing]
python -m app.api_monitor [--once] [--date DD-MM-YYYY]     # polls every 5 min up to 4h
python -m app.eia_actuals [--once] [--date DD-MM-YYYY]     # polls every 15s up to 90 min
python -m app.api_products [--once] [--force] [--allow-stale]   # API gasoline/distillate from ForexFactory, schedule Wed ~18:00 IST
python -m app.signal_engine [--once] [--allow-stale]       # Tier 1 signal, start ~19:59 IST (no brackets when typing)
python docs/img/make_iv_tables.py                          # redraw docs/img/twdr_ng_iv_tables.png (NG option delta/IV tables, computed from PARAMETERS in the script)
python docs/img/make_flowcharts.py                         # redraw docs/img/twdr_cl_flow.png and twdr_ng_flow.png (used in README.md); edit the script when a rule changes
python -m app.ng_recorder [pre|post|backfill] [--date DD-MM-YYYY]   # natural gas, record only -> data/ng_record.json: pre ~19:55 IST (consensus, USD/INR with age), post >=90 min after the release (EIA table, salt ratios, NG=F bars, entry-rule result), backfill = the reports Yahoo still has (~60 days); pre and post send a Telegram summary (record only, not a signal)
python -m app.utils.wti_candle                              # see note below
python -m app.scraper.sites.investing --slug <slug> [--date DD-MM-YYYY]   # debug one scraper (cli.py)
```

Tests (no pytest installed; each file also runs as a module, fake scrapers, no network): `python -m tests.test_signal_engine`, `python -m tests.test_eia_actuals`, `python -m tests.test_api_products`, `python -m tests.test_ng_recorder`, `python -m tests.test_currency`. `sources.py` mentions `tests/test_sources.py`, which is absent. No linter config.

## Architecture

Pipeline of independent CLI stages; each writes one JSON file in `data/`, and file paths are constants in `app/utils/common.py` (import them, never re-spell names). `common.py` also lists files for stages not yet in the repo (`signal_engine`, `market_data`, `surprise_history`, `journal`, `crude_recorder`, `ng_recorder`) — `data/` contents (`consensus.json`, `api_report.json`, `eia_actuals.json`, `wti_candle.json`, `twdr.db`) are the only outputs so far.

Stages: `consensus_fetcher` (Tue, consensus crude/gasoline/distillate) -> `api_monitor` (Wed ~02:00 IST, API crude) -> `eia_actuals` (Wed 20:00 IST; the file is written as soon as crude/gasoline/distillate are in, then Cushing change/level, net-imports change and refinery util change are merged in best effort, null until then) -> `utils/wti_candle` (NYMEX WTI 5-min release candle via yfinance, USD not MCX rupees).

Scraping layer (`app/scraper/`):
- `sources.py` is the single registry mapping indicator -> per-site slug (tradingeconomics, investing.com). Add/fix URLs here. A missing entry means that site doesn't carry the indicator.
- `utils/base.py` `CalendarScraper`: shared contract. `fetch_page(slug)` returns `{"calendar_rows": [{release_date, time, actual, consensus, previous}] | None, "stats": {...}}` or `None` on failure. Site classes in `sites/` only implement `parse_rows`/`parse_stats`. `utils/calendar.py` has row selection (`row_for_release`, `pending_row`, `current_release`).
- `browser.py`: headless Playwright chromium sessions (sites block plain HTTP).

Race pattern (`utils/racer.py`): every fetcher runs both sites concurrently in threads; per indicator, first valid value wins and the output records the source. Missing/inconsistent data fails loudly (wrong baseline is worse than none), sends a Telegram alert via `utils/telegram.py` (`send_exception`). Entry points end with `os._exit(code)` deliberately so losing daemon Playwright threads can't hang shutdown — keep that.

Gotchas:
- Sign convention: build positive, draw negative, in million barrels.
- API Cushing/gasoline/distillate are deliberately NOT in `sources.py` (paywalled, stale/dead on tradingeconomics/investing.com). Don't re-add them there. API gasoline/distillate (plus Cushing and SPR when posted) come from a separate stage, `app/api_products.py`, which reads the X post that ForexFactory lists on its API bulletin event (`curl_cffi` browser impersonation; the repo's Playwright is blocked by Cloudflare there). It picks the post by timestamp window and by matching `api_report.json` crude, never by the page's date label, and never overwrites a `"source": "manual"` file.
- `app/utils/currency.py` (adapted from the earlier pipeline) gives the rupee as CONTEXT only (5-session USD/INR trend vs the trade direction); it never feeds a decision. The NG recorder uses it.
- `xlrd` is in `requirements.txt` only to read EIA's old-format `.xls` history files (`ir.eia.gov/ngs/ngshistory.xls`, `ngsstats.xls`) for the natural gas (TWDR-NG) work; see `docs/twdr_ng.md`.
- `write_json` is atomic (temp file + replace, retried on Windows PermissionError) because the signal engine polls `eia_actuals.json` while it is written.
- `eia_levels.cushing_level` scrapes EIA's public table and cross-checks level delta against the change to reject stale pages.
- `wti_candle.py` has a `fetch`/`release_candle` but no CLI; it raises RuntimeError on missing data (`eia_actuals` logs that as a warning, the candle is record-only). Yahoo keeps ~60 days of 5m data.
- `app/main.py` only calls `load_dotenv()`.

## signal_engine (Tier 1, built)

`app/signal_engine.py`: data-only scoring of the EIA report. Spec and open points: `docs/signal_engine.md`. Run `python -m app.signal_engine [--once] [--allow-stale]` from about 19:59 IST on release day; tests: `python -m tests.test_signal_engine` (no pytest installed).
- Reads `thresholds.json` (user-owned; exactly the Tier 1 keys in `REQUIRED` plus `version`, the older option/veto/sizing keys were removed), `consensus.json`, `api_report.json`, `api_products.json` (`{"release_date": <API report date>, "api_gasoline_mb": x, "api_distillate_mb": y}`, schema in `docs/signal_engine.md`; written by `app.api_products` or entered by hand with `"source": "manual"`), then polls `eia_actuals.json` until its `release_date` matches. Writes `data/signal.json` and `data/signals/<YYYY-MM-DD>.json`.
- Per leg (crude, gasoline, distillate): baseline = consensus pulled toward API by `api_weight`; deviation = EIA actual - baseline. Order: crude-vs-gasoline conflict (Setup C) -> `min_net` size gate -> trap on crude only (Setup B) -> aligned (Setup A). Positive deviation = PUT, negative = CALL.
- Never reads prices: the 20:00-20:05 candle check is the trader's (stated in `confirm`). Status SIGNAL / LATE (computed after `deadline_min`, trader decides) / NO TRADE / ERROR. Every run (SIGNAL, LATE, NO TRADE) sends a short Telegram summary (what to check at 20:05, stop, time stop); any failure overwrites `signal.json` with ERROR and sends a Telegram alert. A failed history write only logs a warning.
- Assumptions not confirmed by the user: trap EIA threshold uses the actual change; conflict is crude vs gasoline only (distillate only sets conviction); crude-build/product-draw mirror of Setup C is treated symmetrically; `softer` API state; numeric thresholds are placeholders.
- Latency: aggregator sites lag at 20:00. `eia_actuals.json` has `released_at` and `source`, kept per release in `data/signals/` as `data_first_seen`/`data_source` to measure it. Lead (unmeasured): `ir.eia.gov/wpsr/table1.csv`.
- Not built: MCX strike/lots/exits, Tiers 2-4 logic (their values are recorded only), CME IV/ATR.

## Config

`.env` (gitignored; don't print): `EIA_API_KEY`, `EIA_API_KEY_2`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Use `common.env()` to read (treats blank/`#` placeholders as unset). Logging via `setup_logging()` (mutes httpx/httpcore because Telegram token is in URL path).
