"""Collect Investing.com "Forecast" values for the EIA weekly petroleum report into Vismaya's wpsr.forecasts.

    python -m app.vismaya_forecasts [--indicators eia_crude eia_gasoline ...] [--since 2011-08-01] [--dry-run] [--db PATH]

Each run opens the five crude-report event pages (crude, gasoline, distillate, Cushing, refinery), one browser
session per page and 60 s apart (investing.com 403s anything faster, so a full run takes about 5 minutes), keeps every page
untouched under raw/ (registered in ref.raw_files, so each value traces to its download) and parses the 10 most
recent releases each page lists; with --since it also clicks the table's "Show More" control (10 older releases per
click, about 80 clicks back to 2011) until the oldest row reaches that date. Values are stored in the report's own unit (thousand barrels; refinery in percentage points),
a blank forecast is NULL, never 0. A row is inserted only when its release matches a ref.calendar row (the
release within 2 days of the expected one); rows with no match are counted and left out. Natural gas
(wngsr.forecasts) is a later extension: add the ng_storage indicator and a second table.

History back to 2011 (--from-capture): a scripted browser cannot expand the history (investing.com's CDN returns 403 to
it, so the page never hydrates). The table was instead expanded by hand in the Claude desktop browser pane and its rows
copied out as "YYYYMMDD,actual,forecast,previous" lines, one set of <slug>_c<N>.txt chunk files per page, each chunk
checked against a checksum taken in the page. `--from-capture DIR` joins the chunks of every page found in DIR, keeps the
joined text under raw/ as the raw file (content type text/csv, source_tz Asia/Kolkata: the pane's display zone; release
times were not captured) and loads it like a fetched page. Cushing and refinery pages hold forecasts only for some weeks,
so their captures hold just the rows that have one.
"""
import argparse
import hashlib
import logging
import os
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from app import vismaya_db
from app.scraper import sources
from app.scraper.sites.investing import InvestingCalendarScraper
from app.scraper.utils.calendar import parse_date, to_mb_suffixed
from app.utils.common import RAW_DIR, ROOT, VISMAYA_DB_FILE, setup_logging

logger = logging.getLogger("twdr.vismaya_forecasts")

SOURCE = "investing_com"
SOURCE_TZ = "UTC"  # the table's time column reads 14:30 for the 10:30 ET release (checked 21 Oct 2026)
MATCH_WINDOW = timedelta(days=2)
# indicator -> (canonical field, unit after parsing, factor from the displayed number): the page shows
# million barrels ("-8.557M"), the database keeps thousand barrels; refinery utilisation is a weekly change in points.
FIELDS = {
    "eia_crude": ("crude_stocks_change", "thousand_barrels", 1000),
    "eia_gasoline": ("gasoline_stocks_change", "thousand_barrels", 1000),
    "eia_distillate": ("distillate_stocks_change", "thousand_barrels", 1000),
    "eia_cushing": ("cushing_stocks_change", "thousand_barrels", 1000),
    "eia_refinery": ("refinery_util_change", "percentage_points", 1),
}


def parse_table(html, factor):
    """The occurrence table -> [{release_date, release_time, actual, forecast, previous}] (values scaled by `factor`,
    blank = None). Rows with no date, or with no number at all (a release nobody has forecast yet), are skipped."""
    table = BeautifulSoup(html, "html.parser").find("table", {"data-test": "occurrence-table"})
    body = table.find("tbody") if table is not None else None
    out = []
    for tr in (body.find_all("tr") if body is not None else []):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        day = parse_date(cells[0]) if len(cells) >= 5 else None
        if day is None:
            continue
        values = [to_mb_suffixed(c) for c in cells[2:5]]
        if all(v is None for v in values):
            continue
        actual, forecast, previous = (None if v is None else round(v * factor, 6) for v in values)
        try:
            at = datetime.strptime(cells[1], "%H:%M").time()
        except ValueError:
            at = None
        out.append({"release_date": day, "release_time": at, "actual": actual, "forecast": forecast, "previous": previous})
    return out


def match_seq(calendar, release_date):
    """(report_seq, days apart) of the calendar row whose expected release DATE (UTC) is closest to this release date,
    within MATCH_WINDOW; (None, None) when none is. The time column is not used: it is the display zone's and, on the
    older rows, unreliable. `calendar`: [(report_seq, expected_release_utc)]."""
    gap, seq = min(((abs((e.astimezone(timezone.utc).date() - release_date).days), s) for s, e in calendar), default=(None, None))
    return (seq, gap) if gap is not None and gap <= MATCH_WINDOW.days else (None, None)


def drop_monthly(rows):
    """The distillate page's history before mid-2013 is a MONTHLY series dated the 1st of each month: a row dated the
    1st whose neighbours are all more than 20 days away is not a weekly release, so it is dropped."""
    days = sorted(r["release_date"] for r in rows)
    def isolated(d):
        gaps = [min((abs((d - o).days) for o in days if o < d), default=None), min((abs((o - d).days) for o in days if o > d), default=None)]
        return d.day == 1 and all(g is None or g > 20 for g in gaps) and any(g is not None for g in gaps)
    return [r for r in rows if not isolated(r["release_date"])]


def parse_capture(text, factor):
    """Browser-pane capture lines 'YYYYMMDD,actual,forecast,previous' (million barrels or points; blank = None) -> rows like
    parse_table, scaled by `factor`; release_time is None (not captured)."""
    out = []
    for line in text.splitlines():
        d, *vals = line.strip().split(",")
        if not line.strip():
            continue
        v = [None if x == "" else round(float(x) * factor, 6) for x in vals]
        out.append({"release_date": datetime.strptime(d, "%Y%m%d").date(), "release_time": None,
                    "actual": v[0], "forecast": v[1], "previous": v[2]})
    return out


def save_raw(html, slug, captured):
    """Write the page as downloaded to raw/investing_com/<slug>/<UTC timestamp>.html -> (sha256, path relative to raw/, bytes)."""
    data = html.encode("utf-8")
    rel = f"{SOURCE}/{slug}/{captured:%Y%m%dT%H%M%SZ}.html"
    path = RAW_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest(), rel, len(data)


def collect(indicators, get_html):
    """({indicator: (slug, html, rows)} for the pages that gave rows, [indicators that did not]).
    `get_html(slug)` returns the page HTML or None."""
    got, failed = {}, []
    for indicator in indicators:
        slug = sources.slug_for(indicator, "investing")
        html = get_html(slug)
        rows = parse_table(html, FIELDS[indicator][2]) if html else []
        if rows:
            got[indicator] = (slug, html, rows)
        else:
            failed.append(indicator)
    return got, failed


def load(con, got, captured, save=save_raw, source_tz=SOURCE_TZ, content_type="text/html"):
    """Write the raw files and the forecast rows. Returns (inserted, unmatched, duplicates): rows with no calendar match,
    and rows dropped because another row of the same page already took that report (nearest date wins; on a tie the row
    with a forecast does: the page has glitches such as two rows dated 15 Nov 2023)."""
    calendar = con.execute("SELECT report_seq, expected_release_utc FROM ref.calendar WHERE report_type = 'WPSR'").fetchall()
    inserted = unmatched = duplicates = 0
    for indicator, (slug, html, rows) in got.items():
        field, unit, _ = FIELDS[indicator]
        sha, rel, size = save(html, slug, captured)
        con.execute("INSERT INTO ref.raw_files VALUES (?,?,?,?,?,?,?,?,'WPSR',NULL) ON CONFLICT DO NOTHING",
                    [sha, rel, SOURCE, f"{InvestingCalendarScraper.base_url}{slug}", captured, size, content_type, source_tz])
        best = {}
        for r in rows:
            seq, gap = match_seq(calendar, r["release_date"])
            if seq is None:
                unmatched += 1
            elif seq not in best:
                best[seq] = (gap, r["forecast"] is None, r)
            else:
                duplicates += 1
                if (gap, r["forecast"] is None) < best[seq][:2]:
                    best[seq] = (gap, r["forecast"] is None, r)
        for seq, (_, _, r) in best.items():
            con.execute("INSERT INTO wpsr.forecasts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [seq, field, SOURCE, slug, r["release_date"], r["release_time"], source_tz,
                         r["actual"], r["forecast"], r["previous"], unit, captured, sha])
            inserted += 1
    return inserted, unmatched, duplicates


def capture_files(directory):
    """{indicator: (slug, joined text)} for every page with chunk files '<slug>_c<N>.txt' in `directory`."""
    found = {}
    for indicator in FIELDS:
        slug = sources.slug_for(indicator, "investing")
        chunks = sorted(Path(directory).glob(f"{slug}_c*.txt"), key=lambda p: int(p.stem.rsplit("_c", 1)[1]))
        if chunks:
            found[indicator] = (slug, "\n".join(c.read_text(encoding="utf-8") for c in chunks))
    return found


def save_capture(text, slug, captured):
    """Keep the joined capture under raw/ -> (sha256, path relative to raw/, bytes). Same shape as save_raw."""
    data = text.encode("utf-8")
    rel = f"{SOURCE}/{slug}/{captured:%Y%m%dT%H%M%SZ}_browser_capture.csv"
    path = RAW_DIR / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest(), rel, len(data)


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or None
    except OSError:
        return None


def run_capture(args, captured):
    """Load browser-pane capture chunk files (see the module docstring)."""
    files = capture_files(args.from_capture)
    got = {}
    for indicator, (slug, text) in files.items():
        if indicator not in args.indicators:
            continue
        rows = parse_capture(text, FIELDS[indicator][2])
        if indicator == "eia_distillate":
            rows = drop_monthly(rows)
        got[indicator] = (slug, text, rows)
        logger.info("%s: %d rows, %s to %s, %d with a forecast", indicator, len(rows), rows[-1]["release_date"], rows[0]["release_date"],
                    sum(r["forecast"] is not None for r in rows))
    if args.dry_run:
        return 0
    con = vismaya_db.connect(args.db)
    run_id = str(uuid.uuid4())
    con.execute("INSERT INTO meta.pipeline_runs VALUES (?,?,?,?,NULL,'running',NULL,NULL)",
                [run_id, "app.vismaya_forecasts --from-capture", git_commit(), captured])
    inserted, unmatched, duplicates = load(con, got, captured, save=save_capture, source_tz="Asia/Kolkata", content_type="text/csv")
    message = f"{inserted} inserted, {unmatched} rows with no ref.calendar match, {duplicates} duplicates dropped (browser capture)"
    con.execute("UPDATE meta.pipeline_runs SET finished_at_utc = ?, status = 'success', rows_loaded = ?, message = ? WHERE run_id = ?",
                [datetime.now(timezone.utc), inserted, message, run_id])
    con.close()
    logger.info(message)
    return 0


def main(argv=None):
    setup_logging()
    parser = argparse.ArgumentParser(description="Collect Investing.com forecasts for the EIA petroleum report into Vismaya")
    parser.add_argument("--indicators", nargs="+", choices=list(FIELDS), default=list(FIELDS))
    parser.add_argument("--since", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
                        help="history: click Show More on each page until its oldest release is on or before this date "
                             "(e.g. 2011-08-01); default: only the 10 latest releases")
    parser.add_argument("--from-capture", metavar="DIR", help="load browser-pane capture chunk files from DIR instead of fetching")
    parser.add_argument("--dry-run", action="store_true", help="fetch and print; write nothing")
    parser.add_argument("--db", default=str(VISMAYA_DB_FILE))
    args = parser.parse_args(argv)
    captured = datetime.now(timezone.utc).replace(microsecond=0)

    loaded = []  # slugs fetched so far: the 2nd page and later wait out the site's session gap

    def get_html(slug):
        """One browser session per page, session_gap_s apart: investing.com 403s a second page in one session
        and back-to-back sessions (twpr v0.1 finding)."""
        if loaded:
            time.sleep(InvestingCalendarScraper.session_gap_s)
        loaded.append(slug)
        with InvestingCalendarScraper() as scraper:
            scraper.show_more_until = args.since
            page, _ = scraper.fetch_with_soup(slug)
            return scraper.last_html if page else None

    if args.from_capture:
        return run_capture(args, captured)
    try:
        got, failed = collect(args.indicators, get_html)
        for indicator, (_, _, rows) in got.items():
            logger.info("%s: %d releases, newest %s (forecast %s)", indicator, len(rows), rows[0]["release_date"], rows[0]["forecast"])
        if failed:
            logger.error("no usable page for: %s", ", ".join(failed))
        if args.dry_run:
            return 1 if failed else 0
        con = vismaya_db.connect(args.db)
        run_id = str(uuid.uuid4())
        con.execute("INSERT INTO meta.pipeline_runs VALUES (?,?,?,?,NULL,'running',NULL,NULL)",
                    [run_id, "app.vismaya_forecasts", git_commit(), captured])
        inserted, unmatched, duplicates = load(con, got, captured)
        message = (f"{inserted} inserted, {unmatched} rows with no ref.calendar match, {duplicates} duplicates dropped"
                   + (f", failed: {failed}" if failed else ""))
        con.execute("UPDATE meta.pipeline_runs SET finished_at_utc = ?, status = ?, rows_loaded = ?, message = ? WHERE run_id = ?",
                    [datetime.now(timezone.utc), "failed" if failed else "success", inserted, message, run_id])
        con.close()
        logger.info(message)
        return 1 if failed else 0
    except Exception:  # noqa: BLE001 - top-level guard
        logger.exception("vismaya_forecasts failed")
        return 1


if __name__ == "__main__":
    os._exit(main())  # as the other entry points: a losing browser thread must not hang shutdown
