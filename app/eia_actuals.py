"""Capture the EIA Weekly Petroleum Status Report actuals -> data/eia_actuals.json.

Released Wednesday 10:30 ET (20:00 IST). Unless --once is given this polls until
the report lands. The report is the crude / gasoline / distillate stock CHANGES in
million barrels (negative = draw): both sites are scraped at the same time and the WHOLE
report comes from one of them, the first to return all three for one release date
(`source`). Nothing is written unless all three are valid. The file is written the moment
they are, so the signal engine is never held back by anything else.

Record-only extras are fetched AFTER that write and merged into the same file (best effort,
null if they did not arrive): the Cushing change, the net-imports change, and the refinery
utilisation change (a CHANGE in percentage points, not a level: neither site carries the
level). `cushing_level_mb` (million barrels) comes from EIA's public weekly table
(`utils/eia_levels.py`), is checked against `cushing_change_mb`, and is null if EIA hasn't
updated yet. Nothing downstream needs any of them to trade.

Run from the repo root:
    python -m app.eia_actuals                      # today's report, polling
    python -m app.eia_actuals --once               # one attempt
    python -m app.eia_actuals --date 23-09-2026 --once   # replay a release
"""
import argparse
import contextlib
import logging
import os

from dotenv import load_dotenv

from datetime import datetime

from app.utils.common import EIA_ACTUALS_FILE, ROOT, now_ist, now_utc, poll, setup_logging, write_json
from app.utils.eia_levels import cushing_level
from app.utils.racer import race
from app.utils.telegram import send_exception
from app.scraper.sources import SOURCE_NAMES, scraper_for, slug_for
from app.scraper.utils.calendar import current_release, row_for_release
from app.utils.wti_candle import release_candle

logger = logging.getLogger("twdr.eia_actuals")

SITES = ("tradingeconomics", "investing")
REPORT_LEGS = ("crude", "gasoline", "distillate")  # crude first: it anchors the release date
EXTRA_LEGS = ("cushing", "net_imports", "refinery")  # record-only, fetched after the report is written
RACE_TIMEOUT_S = 420  # investing.com needs one paced browser session per leg
EXTRAS_TIMEOUT_S = 300
POLL_INTERVAL_S = 15  # an attempt takes seconds, so this sleep is most of the lag after the print
POLL_TIMEOUT_S = 90 * 60
TIME_FORMAT = "%d-%m-%Y %H:%M"  # IST


def _leg_row(site, leg, release_date, today, stop, make_scraper):
    """The released row for one leg: today's current release for crude (which sets
    the date), that same date for the others. Raises if absent or not printed."""
    if stop.is_set():
        raise InterruptedError("race over")
    slug = slug_for(f"eia_{leg}", site)
    if slug is None:
        raise LookupError(f"{site} has no slug for eia_{leg}")
    with make_scraper(site) as scraper:
        page = scraper.fetch_page(slug)
    if page is None:
        raise RuntimeError(f"{leg}: page fetch failed ({slug})")
    rows = page["calendar_rows"] or []
    row = row_for_release(rows, release_date) if release_date else current_release(rows, today)
    if row is None:
        raise RuntimeError(f"{leg}: no row for release {release_date}")
    if row["actual"] is None:
        raise RuntimeError(f"{leg}: EIA report for {row['release_date']} not released yet")
    return row


def fetch_candidate(site, release_date, today, stop, make_scraper, legs=REPORT_LEGS):
    """One site's complete report {release_date, <leg>_change_mb for each of `legs`}, or raise."""
    gap = getattr(make_scraper(site), "session_gap_s", 0)
    result = {}
    with contextlib.ExitStack() as stack:
        get = make_scraper
        if not gap:  # no pacing needed: one browser for every leg (a launch costs seconds); paced sites keep one per leg
            shared = stack.enter_context(make_scraper(site))
            get = lambda _site: contextlib.nullcontext(shared)  # noqa: E731
        for i, leg in enumerate(legs):
            if i and stop.wait(gap):  # paced sessions; wakes early if the race ended
                raise InterruptedError("race over")
            row = _leg_row(site, leg, release_date, today, stop, get)
            release_date = release_date or row["release_date"]  # crude anchors the rest
            result.setdefault("release_date", row["release_date"])
            result[f"{leg}_change_mb"] = row["actual"]
    return result


def refinery_candidates(site, stop, make_scraper):
    """One candidate per printed row of the refinery utilisation-change page, so the
    caller can pick the row matching the release it wants."""
    slug = slug_for("eia_refinery", site)
    if stop.is_set():
        raise InterruptedError("race over")
    with make_scraper(site) as scraper:
        page = scraper.fetch_page(slug)
    if page is None:
        raise RuntimeError(f"refinery: page fetch failed ({slug})")
    return [{"release_date": r["release_date"], "value": r["actual"]}
            for r in page["calendar_rows"] or [] if r["actual"] is not None]


def fetch_eia_actuals(release_date=None, sites=SITES, make_scraper=scraper_for,
                     timeout_s=RACE_TIMEOUT_S, today=None):
    """One attempt: race `sites` for the crude/gasoline/distillate report; return the payload (no timestamps)."""
    # Row dates are GMT/ET, so compare against today's UTC date.
    today = today or now_utc().date()

    def job(site, stop, ok, fail):
        try:
            ok("report", fetch_candidate(site, release_date, today, stop, make_scraper))
        except Exception as exc:  # noqa: BLE001 - reported to the race, never lost
            fail("report", exc)

    decided = race(sites, ("report",), job, release_date, timeout_s, what="EIA actuals")
    site, candidate = decided["report"]
    logger.info("%s returned the complete report first", site)
    return {**candidate, "source": SOURCE_NAMES[site]}


def fetch_extras(release_date, sites=SITES, make_scraper=scraper_for, timeout_s=EXTRAS_TIMEOUT_S, today=None):
    """Best effort, after the report is on disk: {leg: (site, {"release_date", "value"})} for the EXTRA_LEGS
    that arrived for `release_date`. Whatever is missing is simply absent."""
    today = today or now_utc().date()

    def job(site, stop, ok, fail):
        gap = getattr(make_scraper(site), "session_gap_s", 0)
        first = True
        for leg in EXTRA_LEGS:
            if not slug_for(f"eia_{leg}", site):
                continue  # this site doesn't carry it
            if not first and stop.wait(gap):  # paced sessions; wakes early if the race ended
                return
            first = False
            try:
                if leg == "refinery":
                    for cand in refinery_candidates(site, stop, make_scraper):
                        ok(leg, cand)
                else:
                    row = _leg_row(site, leg, release_date, today, stop, make_scraper)
                    ok(leg, {"release_date": row["release_date"], "value": row["actual"]})
            except Exception as exc:  # noqa: BLE001 - optional; reported to the race
                fail(leg, exc)

    # every field is optional; grace_s = timeout_s keeps waiting for the slower ones until the timeout
    return race(sites, EXTRA_LEGS, job, release_date, timeout_s, what="EIA extras",
                optional=EXTRA_LEGS, grace_s=timeout_s)


def add_extras(payload, sites=SITES, fetch=fetch_extras, level=cushing_level):
    """Fill the record-only fields of `payload` and rewrite the file. Never raises: the report is already out."""
    try:
        got = fetch(payload["release_date"], sites)
        for leg, key in (("cushing", "cushing_change_mb"), ("net_imports", "net_imports_change_mb"),
                         ("refinery", "refinery_util_change_pct")):
            if leg in got:
                payload[key] = got[leg][1]["value"]
        if payload["cushing_change_mb"] is not None:
            payload["cushing_level_mb"] = level(payload["cushing_change_mb"])
        write_json(EIA_ACTUALS_FILE, payload)
        refinery = payload["refinery_util_change_pct"]
        logger.info("extras: cushing %s (level %s) | net imports %s | refinery util change %s",
                    payload["cushing_change_mb"], payload["cushing_level_mb"], payload["net_imports_change_mb"],
                    f"{refinery:+.1f}%" if refinery is not None else "n/a")
    except Exception as exc:  # noqa: BLE001 - record-only data must never fail the run
        logger.warning("extras not captured: %s: %s", type(exc).__name__, exc)


def main(argv=None):
    setup_logging()
    load_dotenv(ROOT / ".env")   # Telegram credentials for the failure alert
    parser = argparse.ArgumentParser(description="Capture the EIA weekly petroleum report actuals")
    parser.add_argument("--date", help="EIA release date, DD-MM-YYYY (default: today's report)")
    parser.add_argument("--once", action="store_true", help="a single attempt, no polling")
    parser.add_argument("--sites", nargs="+", choices=SITES, default=list(SITES))
    args = parser.parse_args(argv)
    try:
        result = poll(lambda: fetch_eia_actuals(args.date, tuple(args.sites)),
                      args.once, POLL_INTERVAL_S, POLL_TIMEOUT_S, logger)
        released_at = now_ist().strftime(TIME_FORMAT)  # when the numbers were first seen

        payload = {
            "release_date": result["release_date"],
            "released_at": released_at,
            "crude_change_mb": result["crude_change_mb"],
            "cushing_change_mb": None,
            "cushing_level_mb": None,
            "gasoline_change_mb": result["gasoline_change_mb"],
            "distillate_change_mb": result["distillate_change_mb"],
            "net_imports_change_mb": None,
            "refinery_util_change_pct": None,
            "source": result["source"],
            "fetched_at": now_ist().strftime(TIME_FORMAT),
        }
        write_json(EIA_ACTUALS_FILE, payload)  # the signal engine can read it from here on
        logger.info("EIA %s (%s): crude %+.3f | gasoline %+.3f | distillate %+.3f", payload["release_date"],
                    payload["source"], payload["crude_change_mb"], payload["gasoline_change_mb"],
                    payload["distillate_change_mb"])
        add_extras(payload, tuple(args.sites))
        if args.date:  # a replay also saves that day's release candle (record only)
            try:
                release_candle(datetime.strptime(args.date, "%d-%m-%Y").date())
            except Exception as exc:  # noqa: BLE001 - the report is already written
                logger.warning("release candle not saved: %s", exc)
        return 0
    except Exception as exc:  # noqa: BLE001 - top-level guard
        logger.exception("eia_actuals failed")
        send_exception("eia_actuals.py", exc)
        return 1


if __name__ == "__main__":
    code = main()
    logging.shutdown()
    # A losing site's daemon thread may still be inside a browser call; exit hard
    # so an abandoned Playwright thread can't hang or crash interpreter shutdown.
    os._exit(code)
