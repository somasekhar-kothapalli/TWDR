"""Record natural gas storage reports -> data/ng_record.json (record only: nothing trades on it).

Why it exists: Yahoo keeps only ~60 days of 5-minute data, and every rule in docs/twdr_ng.md has to be
calibrated on weeks we have saved. One record per report, keyed by the release date:

    python -m app.ng_recorder pre [--date DD-MM-YYYY]    # ~19:55 IST on release day, before the print
    python -m app.ng_recorder post [--date DD-MM-YYYY]   # >= 90 minutes after the print (the price path)
    python -m app.ng_recorder backfill                    # one-off: the reports Yahoo still has

pre : the consensus (Investing.com) and the USD/INR readings with their ages (yfinance, freecurrencyapi); the
      freshest is chosen and a warning is recorded when it is older than 30 minutes or its age is unknown.
post: EIA's own table (ir.eia.gov/ngs/wngsr.csv: total, salt, 5-year average), the salt ratio variables, the NG=F and
      USD/INR 5-minute bars around the release, the size band and the aligned / divergent / inside-the-box
      result, and the move that followed.
The release day and time come from the hand-kept exceptions below (EIA's holiday schedule); otherwise it is
Thursday 10:30 ET. A rerun never replaces saved bars with fewer.
"""
import argparse
import csv
import io
import logging
import re
import sys
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
from curl_cffi import requests as curl
from dotenv import load_dotenv

from app.scraper.sources import scraper_for, slug_for
from app.scraper.utils.calendar import row_for_release
from app.utils import currency
from app.utils.common import (IST, NG_RECORD_FILE, ROOT, env, fmt_ts, now_ist, parse_release_date, read_json,
                              setup_logging, write_json)
from app.utils.telegram import send_exception, send_message

logger = logging.getLogger("twdr.ng_recorder")
NY = ZoneInfo("America/New_York")
BEFORE_MIN, AFTER_MIN = 30, 90
YAHOO_DAYS = 59  # Yahoo serves 5-minute bars only for the last 60 days
EIA_CSV = "https://ir.eia.gov/ngs/wngsr.csv"
EIA_HISTORY = "https://ir.eia.gov/ngs/ngshistory.xls"
RATE_WARN_MIN = 30
# EIA's holiday schedule (https://ir.eia.gov/ngs/schedule.html): standard Thursday -> actual (date, ET time).
# Hand-kept: add 2027 when EIA publishes it. Everything else is Thursday 10:30 ET.
SCHEDULE_EXCEPTIONS = {date(2026, 11, 12): (date(2026, 11, 13), time(10, 30)),
                       date(2026, 11, 26): (date(2026, 11, 25), time(12, 0))}
# MCX Natural Gas last trading days (hand-kept, from the user): add the next expiry when it is given.
EXPIRIES = {"OCT": date(2026, 10, 27), "NOV": date(2026, 11, 24), "DEC": date(2026, 12, 28),
            "JAN": date(2027, 1, 25), "FEB": date(2027, 2, 23), "MAR": date(2027, 3, 25)}
ROLL_DAYS = 5  # 5 days or fewer to expiry: trade the next contract
BAND_NOTE = {"noise": "stand down", "buffer_a": "stand down", "standard": "standard setup",
             "high_momentum": "reduce size 30-50%, avoid market orders",
             "shock": "trend-follow, trail stops, never fade (runs to about +60 to +90 min)"}
REGIONS = ("East", "Midwest", "Mountain", "Pacific", "South Central", "Salt", "Nonsalt", "Total")


# ---------- schedule ----------
def release_at(day):
    """The ET release datetime scheduled on calendar date `day`, or None if no report is scheduled that day."""
    for _std, (actual, t) in SCHEDULE_EXCEPTIONS.items():
        if actual == day:
            return datetime.combine(actual, t, tzinfo=NY)
    if day.weekday() == 3 and day not in SCHEDULE_EXCEPTIONS:
        return datetime(day.year, day.month, day.day, 10, 30, tzinfo=NY)
    return None


def contract_for(day):
    """The MCX contract to trade on report day `day`: the first whose last trading day is more than ROLL_DAYS
    after it. None when the calendar runs out (add the next expiry)."""
    for name, expiry in EXPIRIES.items():
        if (expiry - day).days > ROLL_DAYS:
            return name
    return None


# ---------- price bars ----------
def download(ticker, today):
    """5-minute OHLCV bars for `ticker` as a DataFrame indexed in New York time."""
    df = yf.download(ticker, start=(today - timedelta(days=YAHOO_DAYS)).isoformat(),
                     end=(today + timedelta(days=2)).isoformat(), interval="5m", progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):  # newer yfinance returns (field, ticker) columns
        df.columns = df.columns.get_level_values(0)
    if df.empty:
        raise RuntimeError(f"no 5-minute data for {ticker}")
    df.index = (df.index.tz_localize("UTC") if df.index.tz is None else df.index).tz_convert(NY)
    return df


def window(df, t0):
    """The bars from BEFORE_MIN before to AFTER_MIN after the release `t0` (ET), as plain dicts."""
    part = df.loc[t0 - timedelta(minutes=BEFORE_MIN): t0 + timedelta(minutes=AFTER_MIN - 5)]
    volume = lambda v: None if v != v else int(v)  # noqa: E731 - NaN-safe
    return [{"t": ts.isoformat(), "open": round(float(r["Open"]), 4), "high": round(float(r["High"]), 4),
             "low": round(float(r["Low"]), 4), "close": round(float(r["Close"]), 4), "volume": volume(r["Volume"])}
            for ts, r in part.iterrows()]


def keep_longer(new, old):
    return new if len(new) >= len(old or []) else old


# ---------- the size band and the entry rule (docs/twdr_ng.md rulings) ----------
def size_band(surprise):
    d = abs(surprise)
    return ("noise" if d <= 3 else "buffer_a" if d < 4 else "standard" if d <= 10
            else "high_momentum" if d <= 12 else "shock")


def side_of(close, lo, hi):
    return "up" if close > hi else "down" if close < lo else "inside"


def evaluate_rule(bars, t0, surprise):
    """The aligned / divergent / inside result from NG=F bars, and the move after the release (cents vs the
    release open). bars are the saved dicts. The pre-report box is the three bars before the release."""
    by = {b["t"][11:16]: b for b in bars}
    key = lambda minutes: (t0 + timedelta(minutes=minutes)).strftime("%H:%M")  # noqa: E731
    box = [by[key(m)] for m in (-15, -10, -5) if key(m) in by]
    if not box or key(0) not in by:
        return {"band": size_band(surprise), "status": "NO DATA"}
    lo, hi = min(b["low"] for b in box), max(b["high"] for b in box)
    first = side_of(by[key(0)]["close"], lo, hi)
    bias = "down" if surprise > 0 else "up" if surprise < 0 else None  # a bigger build is bearish
    band = size_band(surprise)
    f0 = by[key(0)]
    upper = (f0["high"] - max(f0["open"], f0["close"])) * 100
    lower = (min(f0["open"], f0["close"]) - f0["low"]) * 100
    body, width = abs(f0["close"] - f0["open"]) * 100, (hi - lo) * 100
    opposing = lower if first == "up" else upper if first == "down" else None  # the wick on the side we came from
    rule_a = opposing is not None and opposing > body          # the wick dominates the body
    rule_b = opposing is not None and opposing > 0.5 * width   # it cuts back through over half of the box
    shape = {"upper_wick_cents": round(upper, 2), "lower_wick_cents": round(lower, 2), "body_cents": round(body, 2),
             "box_width_cents": round(width, 2), "opposing_wick_cents": None if opposing is None else round(opposing, 2),
             "wick_rule_a": rule_a, "wick_rule_b": rule_b, "wick_veto": bool(rule_a or rule_b),
             "fully_outside": f0["low"] > hi or f0["high"] < lo}  # information only: "outside" means the CLOSE
    if band in ("noise", "buffer_a") or bias is None:
        status = f"NO TRADE ({band})"
    elif first == "inside":
        status = "INSIDE the box: wait for the 10:45 filter"
    elif first != bias:
        status = "DIVERGENT: skip"
    elif shape["wick_veto"]:
        status = "WICK VETO: the 10:35 entry is vetoed, wait for the 10:45 filter"
    else:
        status = "ALIGNED: enter"
    fallback = None
    wait = first == "inside" or (first == bias and shape["wick_veto"])  # the primary entry did not happen
    if wait and band in ("standard", "high_momentum", "shock") and bias:
        s2 = side_of(by[key(5)]["close"], lo, hi) if key(5) in by else None
        s3 = side_of(by[key(10)]["close"], lo, hi) if key(10) in by else None
        at = (t0 + timedelta(minutes=15)).strftime("%H:%M")
        result = ("NO DATA" if s3 is None else f"NO TRADE: no breakout by the {at} close" if s3 == "inside"
                  else f"ALIGNED at the {at} close: enter" if s3 == bias else f"DIVERGENT at the {at} close: skip")
        fallback = {"candle2_close_side": s2, "candle3_close_side": s3, "status": result}
    after = [by[key(m)] for m in range(0, 30, 5) if key(m) in by]
    o = by[key(0)]["open"]
    move = {"close_5": round((by[key(0)]["close"] - o) * 100, 2)}
    for label, minutes in (("close_15", 10), ("close_30", 25)):
        if key(minutes) in by:
            move[label] = round((by[key(minutes)]["close"] - o) * 100, 2)
    if after:
        move["max_up"] = round((max(b["high"] for b in after) - o) * 100, 2)
        move["max_down"] = round((min(b["low"] for b in after) - o) * 100, 2)
    return {"band": band, "bias": bias, "box_low": lo, "box_high": hi, "first_close_side": first,
            "first_close": by[key(0)]["close"], "first_candle": shape, "status": status, "fallback": fallback,
            "move_cents": move}


# ---------- EIA's table and the salt variables ----------
def parse_eia_csv(text):
    """{release (ET date), week_ending, regions: {name: stocks, prior, net_change, year_ago, avg5, ...}}."""
    head = re.search(r"Released: (\w+ \d+, \d{4}).*Week Ending (\w+ \d+, \d{4})", text)
    if not head:
        raise RuntimeError("unexpected EIA storage file: no release header")
    regions = {}
    for row in csv.reader(io.StringIO(text)):
        name = row[0].strip() if row else ""
        if name in REGIONS and len(row) > 22:
            num = lambda i: float(row[i].replace(",", "")) if row[i].strip() else None  # noqa: E731
            regions[name] = {"stocks": num(1), "prior_stocks": num(4), "net_change": num(7), "year_ago": num(13),
                             "avg5": num(19), "avg5_pct": num(22)}
    if not {"Total", "Salt"} <= regions.keys():
        raise RuntimeError("unexpected EIA storage file: Total or Salt row missing")
    fmt = lambda s: datetime.strptime(s, "%B %d, %Y").date()  # noqa: E731
    return {"release": fmt(head.group(1)), "week_ending": fmt(head.group(2)), "regions": regions}


def salt_variables(week_ending, salt_now, headline_deviation, history):
    """The 50% salt rule's inputs, recorded only. `history`: weekly salt net change indexed by week-ending date.
    A: prior-week baseline (the ruling). B: the previous five years' same-week average instead."""
    prior = history.get(week_ending - timedelta(days=7))
    same = []
    for years in range(1, 6):
        t = week_ending - timedelta(days=365 * years)
        near = [d for d in history.index if abs((d - t).days) <= 3]
        if near:
            same.append(history[near[0]])
    avg5 = sum(same) / len(same) if same else None
    ratio = lambda base: (abs(salt_now - base) / abs(headline_deviation)  # noqa: E731
                          if base is not None and headline_deviation else None)
    return {"salt_change": salt_now, "salt_change_prior_week": prior, "salt_change_5y_same_week_avg": avg5,
            "headline_deviation": headline_deviation, "ratio_prior_week": ratio(prior), "ratio_5y_avg": ratio(avg5),
            "rule_applies": abs(headline_deviation) >= 4, "applied": False}


def salt_history(content):
    """Weekly Salt net change from EIA's history workbook as a Series indexed by week-ending date."""
    raw = pd.read_excel(io.BytesIO(content), sheet_name="weekly_net_changes", header=None)
    df = raw.iloc[7:, [0, 7]].copy()
    df.columns = ["week", "salt"]
    df["week"] = pd.to_datetime(df["week"], errors="coerce")
    df["salt"] = pd.to_numeric(df["salt"], errors="coerce")
    df = df.dropna()
    return pd.Series(df["salt"].values, index=[d.date() for d in df["week"]])


# ---------- USD/INR ----------
def rate_readings(now):
    """USD/INR from each source: value, when it was quoted, its age in minutes (None if the source gives no time)."""
    out = []
    try:
        h = yf.Ticker("INR=X").history(period="1d", interval="1m")
        if h.empty:
            h = yf.Ticker("INR=X").history(period="5d", interval="5m")
        as_of = h.index[-1].to_pydatetime()
        out.append({"source": "yfinance INR=X", "value": round(float(h["Close"].iloc[-1]), 4), "as_of": as_of.isoformat(),
                    "age_min": round((now - as_of).total_seconds() / 60, 1)})
    except Exception as exc:  # noqa: BLE001 - one source failing must not stop the other
        out.append({"source": "yfinance INR=X", "error": f"{type(exc).__name__}: {exc}"})
    key = env("FREECURRENCYAPI_KEY")
    try:
        if not key:
            raise RuntimeError("FREECURRENCYAPI_KEY not set")
        r = curl.get("https://api.freecurrencyapi.com/v1/latest", params={"apikey": key, "base_currency": "USD",
                     "currencies": "INR"}, timeout=15)
        r.raise_for_status()
        out.append({"source": "freecurrencyapi", "value": round(float(r.json()["data"]["INR"]), 4), "as_of": None,
                    "age_min": None})
    except Exception as exc:  # noqa: BLE001 - never print the key
        out.append({"source": "freecurrencyapi", "error": type(exc).__name__})
    return out


def currency_block(closes, bias):
    """The rupee context (app/utils/currency.py) for a report: a note only, it never changes the rule."""
    direction = {"down": "bearish", "up": "bullish"}.get(bias, "neutral")
    return currency.context(currency.trend_pct(closes), direction)


def choose_rate(readings):
    """The freshest reading; never none if any source gave a value. A warning when it is old or its age is unknown."""
    ok = [r for r in readings if "value" in r]
    if not ok:
        return None
    known = [r for r in ok if r["age_min"] is not None]
    best = min(known, key=lambda r: r["age_min"]) if known else ok[0]
    warn = None
    if best["age_min"] is None:
        warn = "age unknown"
    elif best["age_min"] > RATE_WARN_MIN:
        warn = f"older than {RATE_WARN_MIN} minutes"
    return {**best, "warning": warn}


# ---------- records ----------
def consensus_row(release_day):
    with scraper_for("investing") as scraper:
        page = scraper.fetch_page(slug_for("ng_storage", "investing"))
    row = row_for_release((page or {}).get("calendar_rows") or [], release_day.strftime("%d-%m-%Y"))
    if row is None:
        raise RuntimeError(f"no Investing.com row for {release_day}")
    return row


def released_reports(rows):
    """Investing.com calendar rows -> reports with an actual and a consensus."""
    return [r for r in rows if r["actual"] is not None and r["consensus"] is not None]


def build(row, ng, fx, old=None):
    """A backfilled report: numbers from an Investing row, bars from Yahoo (saved bars are kept if more complete)."""
    day = parse_release_date(row["release_date"])
    t0 = release_at(day) or datetime(day.year, day.month, day.day, 10, 30, tzinfo=NY)
    record = {"release_date": row["release_date"], "release_et": t0.isoformat(), "actual_bcf": row["actual"],
              "consensus_bcf": row["consensus"], "previous_bcf": row["previous"],
              "surprise_bcf": row["actual"] - row["consensus"], "consensus_source": "investing.com",
              "recorded_at": fmt_ts(now_ist()),
              "bars_note": "yfinance 5-minute bars, ET timestamps: NG=F in USD/MMBtu, INR=X is USD/INR"}
    for key, df in (("ng_bars", ng), ("usdinr_bars", fx)):
        record[key] = keep_longer(window(df, t0), (old or {}).get(key))
    return record


def backfill(rows, ng, fx, existing=None):
    """Merge every released report in `rows` into the record; returns the updated record."""
    data = existing or {"reports": {}}
    for row in released_reports(rows):
        key = parse_release_date(row["release_date"]).isoformat()
        data["reports"][key] = {**data["reports"].get(key, {}), **build(row, ng, fx, data["reports"].get(key))}
    data["reports"] = dict(sorted(data["reports"].items()))
    return data


def load_record():
    try:
        return read_json(NG_RECORD_FILE)
    except (FileNotFoundError, ValueError):
        return {"reports": {}}


def run_pre(release_day, get_row=consensus_row, get_rates=rate_readings, now=None):
    now = now or now_ist()
    t0 = release_at(release_day)
    if t0 is None:
        raise RuntimeError(f"no report is scheduled on {release_day} (see SCHEDULE_EXCEPTIONS)")
    row = get_row(release_day)
    readings = get_rates(now)
    chosen = choose_rate(readings)
    rec = {"release_date": release_day.strftime("%d-%m-%Y"), "release_et": t0.isoformat(),
           "release_ist": t0.astimezone(IST).strftime("%H:%M"), "contract": contract_for(release_day),
           "consensus_bcf": row["consensus"],
           "previous_bcf": row["previous"], "consensus_source": "investing.com",
           "pre": {"captured_at": now.isoformat(), "minutes_before_release": round((t0 - now).total_seconds() / 60, 1),
                   "usdinr_readings": readings, "usdinr_chosen": chosen}}
    return rec


def run_post(release_day, get_row=consensus_row, now=None, record=None):
    now = now or now_ist()
    t0 = release_at(release_day)
    if t0 is None:
        raise RuntimeError(f"no report is scheduled on {release_day} (see SCHEDULE_EXCEPTIONS)")
    if now < t0 + timedelta(minutes=AFTER_MIN) and release_day == now_ist().date():
        raise RuntimeError(f"too early: run post at least {AFTER_MIN} minutes after the release ({t0:%H:%M} ET)")
    eia = parse_eia_csv(curl.get(EIA_CSV, impersonate="chrome", timeout=30).text)
    if eia["release"] != release_day:
        raise RuntimeError(f"EIA's file is for the {eia['release']} release, not {release_day}")
    total, salt = eia["regions"]["Total"], eia["regions"]["Salt"]
    old = (record or {}).get(release_day.isoformat(), {})
    consensus = old.get("consensus_bcf")
    row = None
    if consensus is None or old.get("previous_bcf") is None:
        row = get_row(release_day)
        consensus = row["consensus"]
    if consensus is None:
        raise RuntimeError("no consensus for this report: the surprise cannot be computed")
    actual = total["net_change"]
    surprise = actual - consensus
    history = salt_history(curl.get(EIA_HISTORY, impersonate="chrome", timeout=60).content)
    today = now.date()
    ng, fx = download("NG=F", today), download("INR=X", today)
    ng_bars, fx_bars = window(ng, t0), window(fx, t0)
    rec = {"release_date": release_day.strftime("%d-%m-%Y"), "release_et": t0.isoformat(),
           "release_ist": t0.astimezone(IST).strftime("%H:%M"), "actual_bcf": actual, "consensus_bcf": consensus,
           "previous_bcf": (row or {}).get("previous", old.get("previous_bcf")), "surprise_bcf": surprise,
           "consensus_source": "investing.com", "week_ending": eia["week_ending"].isoformat(),
           "eia_table": eia["regions"], "salt": salt_variables(eia["week_ending"], salt["net_change"], surprise, history),
           "ng_bars": keep_longer(ng_bars, old.get("ng_bars")), "usdinr_bars": keep_longer(fx_bars, old.get("usdinr_bars")),
           "rule": evaluate_rule(keep_longer(ng_bars, old.get("ng_bars")), t0, surprise), "recorded_at": fmt_ts(now),
           "bars_note": "yfinance 5-minute bars, ET timestamps: NG=F in USD/MMBtu, INR=X is USD/INR"}
    try:
        closes = currency.usdinr_closes(release_day)
    except Exception as exc:  # noqa: BLE001 - a context note must never sink the record
        logger.warning("no USD/INR daily history: %s", exc)
        closes = []
    rec["currency"] = currency_block(closes, rec["rule"].get("bias"))
    return rec


def _bcf(value):
    return "n/a" if value is None else f"{value:g} Bcf"


def pre_summary(rec):
    """The Telegram text before the release: the numbers to read the print against, the rate, the contract."""
    p = rec["pre"]
    rate = p["usdinr_chosen"]
    rate_line = ("USD/INR: no reading from any source" if rate is None else
                 f"USD/INR {rate['value']} ({rate['source']}, "
                 f"{'age unknown' if rate['age_min'] is None else str(round(rate['age_min'])) + ' min old'})"
                 + (f" WARNING: {rate['warning']}" if rate.get("warning") else ""))
    return "\n".join([
        f"TWDR-NG {rec['release_date']} before the release ({rec['release_et'][11:16]} ET = {rec['release_ist']} IST)",
        ("Consensus NOT POSTED yet: get it by hand (Reuters, Bloomberg). " if rec["consensus_bcf"] is None else
         f"Consensus {rec['consensus_bcf']:g} Bcf. ") + f"Previous {_bcf(rec['previous_bcf'])}. Contract: "
        f"{rec['contract'] or 'unknown: add the next expiry'}",
        rate_line,
        "Bands (|actual - consensus|): 0-3 stand down | 4-10 standard | 11-12 high momentum (reduce size) | 13+ shock (never fade)",
        "Entry: the first 5-min candle must CLOSE outside your pre-report box in the headline direction; against "
        "the headline = skip; inside, or a long wick (opposite wick bigger than the body, or over half the box) = "
        "wait for the +15 min close"])


def post_summary(rec):
    """The Telegram text after the release: what happened, as a record."""
    r, s, m = rec["rule"], rec["salt"], rec["rule"].get("move_cents", {})
    lines = [f"TWDR-NG {rec['release_date']} record (not a signal)",
             f"Actual {rec['actual_bcf']:g} vs consensus {rec['consensus_bcf']:g} = {rec['surprise_bcf']:+g} Bcf: "
             f"{r['band']} ({BAND_NOTE[r['band']]})",
             f"Rule: {r['status']}" + (f" | fallback: {r['fallback']['status']}" if r.get("fallback") else "")]
    if m:
        lines.append("Move from the release open (cents): " + ", ".join(
            f"{k.replace('_', ' ')} {v:+g}" for k, v in m.items()))
    lines.append(f"Salt {s['salt_change']:+g} Bcf (ratio vs prior week {s['ratio_prior_week']}, vs 5y average {s['ratio_5y_avg']}; information only)")
    lines += [f"RUPEE: {n}" for n in rec.get("currency", {}).get("notes", [])]
    return "\n".join(lines)


def merge(data, key, rec):
    data["reports"][key] = {**data["reports"].get(key, {}), **rec}
    data["reports"] = dict(sorted(data["reports"].items()))
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description="Record natural gas storage reports (record only)")
    parser.add_argument("mode", nargs="?", default="backfill", choices=("pre", "post", "backfill"))
    parser.add_argument("--date", help="release date DD-MM-YYYY (default: today in IST)")
    args = parser.parse_args(argv)
    setup_logging()
    load_dotenv(ROOT / ".env")
    try:
        data = load_record()
        if args.mode == "backfill":
            with scraper_for("investing") as scraper:
                page = scraper.fetch_page(slug_for("ng_storage", "investing"))
            if not page or not page["calendar_rows"]:
                raise RuntimeError("no natural gas storage rows from Investing.com")
            today = now_ist().date()
            data = backfill(page["calendar_rows"], download("NG=F", today), download("INR=X", today), data)
            for key, rec in data["reports"].items():
                logger.info("%s: actual %s, consensus %s, surprise %+g | %d NG=F bars", key, rec["actual_bcf"],
                            rec["consensus_bcf"], rec["surprise_bcf"], len(rec["ng_bars"]))
        else:
            day = parse_release_date(args.date) if args.date else now_ist().date()
            key = day.isoformat()
            rec = run_pre(day) if args.mode == "pre" else run_post(day, record=data["reports"])
            data = merge(data, key, rec)
            if args.mode == "post" and rec["rule"]["status"].startswith("DIVERGENT"):
                logger.warning("DIVERGENCE DETECTED - the first candle broke %s against a %s headline: SKIP, stand down",
                               rec["rule"]["first_close_side"], rec["rule"]["bias"])
            if args.mode == "pre":
                p = rec["pre"]
                if rec["consensus_bcf"] is None:
                    logger.warning("the consensus is not posted yet: the pre message says so")
                logger.info("%s pre: consensus %s Bcf | USD/INR chosen %s | release %s ET (%s IST)", key, rec["consensus_bcf"],
                            p["usdinr_chosen"], rec["release_et"][11:16], rec["release_ist"])
            else:
                r, s = rec["rule"], rec["salt"]
                logger.info("%s post: actual %s, consensus %s, surprise %+g | band %s | %s | salt %+g (ratio A %s, B %s)", key,
                            rec["actual_bcf"], rec["consensus_bcf"], rec["surprise_bcf"], r["band"], r["status"],
                            s["salt_change"], s["ratio_prior_week"], s["ratio_5y_avg"])
        write_json(NG_RECORD_FILE, data)
        if args.mode != "backfill":
            send_message(pre_summary(rec) if args.mode == "pre" else post_summary(rec))
        return 0
    except Exception as exc:  # noqa: BLE001 - top-level guard
        logger.exception("ng_recorder failed")
        send_exception("ng_recorder.py", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
