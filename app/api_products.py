"""Capture the API gasoline and distillate changes -> data/api_products.json.

The API publishes them behind a paywall, but the print is posted on X and ForexFactory lists the post on
its API bulletin event. One plain HTTP request (the repo's browser is blocked by Cloudflare; curl_cffi
impersonating a browser is not) returns the news items as JSON. Nothing is trusted blindly:

  * the post must have been made within 36 h after the API print (16:30 ET on the API release date from
    api_report.json, so a holiday-delayed print follows it) - the page's date label is timezone-dependent
    and is not used;
  * the post's crude must equal api_report.json's crude, within the rounding the post prints.

A post that fails either is ignored. A leg the post lacks or gets wrong is left out and the signal engine falls
back to the consensus for it (with a warning). A hand-entered file ("source": "manual") for the same release
is never overwritten.

Schedule it Wednesday ~18:00 IST (the post has been up for ~15 h); it retries every 5 min until ~19:45.
Run from the repo root:
    python -m app.api_products                 # latest API report, retrying
    python -m app.api_products --once          # one attempt
    python -m app.api_products --allow-stale   # replay a week that is not this one
    python -m app.api_products --force         # re-fetch even if a complete file exists
"""
import argparse
import json
import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from curl_cffi import requests as curl
from dotenv import load_dotenv

from app.utils.common import (API_PRODUCTS_FILE, API_REPORT_FILE, ROOT, fmt_ts, now_ist, parse_release_date, poll,
                              read_json, setup_logging, write_json)
from app.utils.telegram import send_exception

logger = logging.getLogger("twdr.api_products")

URL = "https://www.forexfactory.com/calendar/754-us-api-weekly-statistical-bulletin"
PROFILES = ("chrome", "safari17_0")  # TLS fingerprints to try in order; Cloudflare accepts them unevenly
POLL_INTERVAL_S = 300
POLL_TIMEOUT_S = 105 * 60  # 18:00 -> 19:45 IST, before the signal engine starts
WINDOW_H = 36
NY = ZoneInfo("America/New_York")
LABEL = {"crude": "crude", "gasoline": "gasoline", "gas": "gasoline", "distillates": "distillate",
         "distillate": "distillate", "dist": "distillate", "cushing": "cushing", "cush": "cushing", "spr": "spr"}
_NUM = r"(?:\d{1,3}(?:,\d{3})+|\d*\.\d+|\d+)"
POST = re.compile(
    r"\b(?P<label>crude|gasoline|gas|distillates?|dist|cushing|cush|spr)\b"
    r"(?:\s+(?:oil|stocks?|stock\s+change|inventory|actual|moves?))*"
    r"\s*(?:was\s+a|was|were)?\s*[:=]?\s*"
    r"(?P<word>up|down|build\s+of|draw\s+of|build|draw)?\s*"
    r"(?P<sign>[+\-−–])?\s*(?P<num>" + _NUM + r")\s*(?P<unit>MM|mln|million|M|K|thousand)?",
    re.I)
EXTRA_KEYS = {"gasoline": "api_gasoline_mb", "distillate": "api_distillate_mb", "cushing": "api_cushing_mb",
              "spr": "api_spr_mb"}


def parse_post(text):
    """{leg: (million barrels, rounding tolerance in million barrels)} from a post's text; first mention wins.
    Reads units M/MM/Mln/million/K/thousand and bare thousands with commas ("+300,000"); a missing sign is a build."""
    out = {}
    for m in POST.finditer(re.sub(r"<[^>]+>", " ", text)):
        leg = LABEL[m["label"].lower()]
        if leg in out:
            continue
        raw, unit = m["num"], (m["unit"] or "").lower()
        scale = 0.001 if unit in ("k", "thousand") else 1e-6 if (not unit and ("," in raw or float(raw.replace(",", "")) >= 1000)) else 1.0
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        value = float(raw.replace(",", "")) * scale
        negative = m["sign"] in ("-", "−", "–") or (m["word"] or "").lower().startswith(("down", "draw"))
        out[leg] = (-value if negative else value, 0.5 * 10 ** -decimals * scale)
    return out


def merge_title_and_text(title, text):
    """Title first, the post text for what the title lacks. A leg the two disagree on is dropped."""
    a, b = parse_post(title), parse_post(text)
    merged = {}
    for leg in a.keys() | b.keys():
        if leg in a and leg in b and abs(a[leg][0] - b[leg][0]) > a[leg][1] + b[leg][1] + 1e-9:
            logger.warning("title and text disagree on %s (%s vs %s): dropped", leg, a[leg][0], b[leg][0])
            continue
        merged[leg] = a.get(leg) or b[leg]
    return merged


def fetch_items(get=curl.get):
    """The news items (list of dicts with dateline, title, preview, source) from the bulletin page."""
    problem = None
    for profile in PROFILES:
        try:
            response = get(URL, impersonate=profile, timeout=30)
        except Exception as exc:  # noqa: BLE001 - try the next fingerprint
            problem = f"{profile}: {type(exc).__name__}"
            continue
        if response.status_code != 200:
            problem = f"{profile}: HTTP {response.status_code}"
            continue
        for tag in BeautifulSoup(response.text, "html.parser").find_all(attrs={"data-items": True}):
            try:
                items = json.loads(tag["data-items"])
            except ValueError:
                continue
            if items and isinstance(items, list) and "dateline" in items[0] and "title" in items[0]:
                return items
        problem = f"{profile}: page has no news data (layout changed?)"
    raise RuntimeError(f"ForexFactory unavailable ({problem})")


def find_products(items, api_report):
    """{leg: (value, tolerance)} plus the post's details, from the posts that pass both checks, or {} if none."""
    d = parse_release_date(api_report["release_date"])
    start = datetime(d.year, d.month, d.day, 16, 30, tzinfo=NY)
    end = start + timedelta(hours=WINDOW_H)
    crude, passing = api_report["api_crude_mb"], []
    for item in sorted(items, key=lambda i: -i["dateline"]):
        posted = datetime.fromtimestamp(item["dateline"], timezone.utc)
        if not start <= posted <= end:
            continue
        legs = merge_title_and_text(item["title"], item.get("preview", ""))
        if "crude" not in legs:
            continue
        value, tol = legs["crude"]
        if abs(value - crude) > tol + 0.001:
            logger.warning("post by %s has crude %+.3f, the API report has %+.3f: ignored", item.get("source"), value, crude)
            continue
        passing.append((item, legs, posted))
    legs, details = {}, None
    for item, post_legs, posted in passing:  # newest first
        details = details or {"from": item.get("source"), "posted_at": posted.isoformat(),
                              "text": re.sub(r"<[^>]+>|\s+", " ", f"{item['title']} | {item.get('preview', '')}").strip()}
        for leg, (value, tol) in post_legs.items():
            if leg == "crude":
                continue
            if leg not in legs:
                legs[leg] = (value, tol)
            elif abs(legs[leg][0] - value) > legs[leg][1] + tol + 1e-9:
                logger.warning("posts disagree on %s: dropped", leg)
                legs[leg] = None
    legs = {k: v for k, v in legs.items() if v is not None}
    return ({"legs": legs, **details} if details else {})


def record(api_report, found):
    out = {"release_date": api_report["release_date"], "source": "forexfactory", "from": found["from"],
           "posted_at": found["posted_at"], "matched_crude_mb": api_report["api_crude_mb"], "text": found["text"],
           "fetched_at": fmt_ts(now_ist())}
    for leg, (value, _tol) in found["legs"].items():
        out[EXTRA_KEYS[leg]] = round(value, 6)
    return out


def attempt(api_report, partial, get=curl.get):
    """One fetch. Returns the record when both legs are found; raises RuntimeError (retry) otherwise."""
    found = find_products(fetch_items(get), api_report)
    if not found:
        raise RuntimeError("no post in the window with a matching crude yet")
    if not {"gasoline", "distillate"} <= found["legs"].keys():
        partial.clear()
        partial.update(found)
        raise RuntimeError(f"post by {found['from']} lacks {sorted({'gasoline', 'distillate'} - found['legs'].keys())}")
    return record(api_report, found)


def main(argv=None):
    setup_logging()
    load_dotenv(ROOT / ".env")  # Telegram credentials for the failure alert
    parser = argparse.ArgumentParser(description="Capture the API gasoline and distillate from ForexFactory")
    parser.add_argument("--once", action="store_true", help="a single attempt, no retrying")
    parser.add_argument("--force", action="store_true", help="re-fetch even if a complete file exists")
    parser.add_argument("--allow-stale", action="store_true", help="replay a week that is not this one")
    args = parser.parse_args(argv)
    try:
        api_report = read_json(API_REPORT_FILE)
        age = (now_ist().date() - parse_release_date(api_report["release_date"])).days
        if not args.allow_stale and not 0 <= age <= 2:
            raise ValueError(f"api_report.json is for {api_report['release_date']}, {age} days ago: "
                             "run api_monitor first, or use --allow-stale to replay")
        try:
            existing = read_json(API_PRODUCTS_FILE)
        except (FileNotFoundError, ValueError):
            existing = {}
        if existing.get("release_date") == api_report["release_date"]:
            if existing.get("source") == "manual":
                logger.info("a hand-entered api_products.json for %s exists: not touching it", existing["release_date"])
                return 0
            if not args.force and {"api_gasoline_mb", "api_distillate_mb"} <= existing.keys():
                logger.info("api_products.json for %s is already complete (use --force to re-fetch)", existing["release_date"])
                return 0
        partial = {}
        try:
            payload = poll(lambda: attempt(api_report, partial), args.once, POLL_INTERVAL_S, POLL_TIMEOUT_S, logger)
        except RuntimeError:
            if partial:  # keep the one leg we do have; the engine uses the consensus for the other
                write_json(API_PRODUCTS_FILE, record(api_report, partial))
            raise
        write_json(API_PRODUCTS_FILE, payload)
        logger.info("API %s from %s: gasoline %+.3f | distillate %+.3f | cushing %s | SPR %s", payload["release_date"],
                    payload["from"], payload["api_gasoline_mb"], payload["api_distillate_mb"],
                    payload.get("api_cushing_mb", "n/a"), payload.get("api_spr_mb", "n/a"))
        logger.info("post: %s", payload["text"])
        return 0
    except Exception as exc:  # noqa: BLE001 - top-level guard
        logger.exception("api_products failed")
        send_exception("api_products.py", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
