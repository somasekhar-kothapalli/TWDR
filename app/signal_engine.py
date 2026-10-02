"""TWDR Tier 1 signal engine (data only; spec in docs/signal_engine.md).

    python -m app.signal_engine [--once] [--allow-stale]

Start it about 19:59 IST on release day. It reads thresholds, consensus, API crude, the hand-entered API
products and then waits for today's eia_actuals.json, scores the three legs (crude, gasoline, distillate)
and writes data/signal.json. It never reads prices: the candle check at 20:05 is the trader's.

API gasoline and distillate come from data/api_products.json (written by app.api_products, or entered by hand):
    {"release_date": "<the API report's DD-MM-YYYY>", "api_gasoline_mb": -1.2, "api_distillate_mb": 0.4}

Build positive, draw negative, million barrels. Positive deviation is bearish (PUT), negative bullish (CALL).
Status: SIGNAL | LATE (computed after the deadline, trader decides) | NO TRADE | ERROR.
"""
import argparse
import logging
import math
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from app.utils.common import (API_PRODUCTS_FILE, API_REPORT_FILE, CONSENSUS_FILE, EIA_ACTUALS_FILE, IST, ROOT,
                              SIGNAL_DIR, SIGNAL_FILE, THRESHOLDS_FILE, fmt_ts, now_ist, parse_release_date, poll, read_json,
                              setup_logging, write_json)
from app.utils.telegram import send_exception, send_message

log = logging.getLogger("twdr.signal_engine")
NY = ZoneInfo("America/New_York")
LEGS = ("crude", "gasoline", "distillate")
REQUIRED = ("api_weight", "min_leg_dev", "min_net", "api_state_gap", "trap_api_min", "trap_eia_min",
            "conflict_min_crude_dev", "conflict_move_usd", "move_bands", "rule_of_thumb_per_mb", "deadline_min",
            "time_stop_min", "hard_exit_hours", "poll_interval_s", "max_wait_min")


def _sign(x):
    return (x > 0) - (x < 0)


def load_thresholds():
    th = read_json(THRESHOLDS_FILE)
    missing = [k for k in REQUIRED if k not in th]
    if missing:
        raise ValueError(f"{THRESHOLDS_FILE.name} is missing: {', '.join(missing)}")
    return th


def schedule(day, th):
    """IST clock for the release day. The print is 10:30 New York time: 20:00 IST in US summer time, 21:00 in
    winter. MCX closes 23:30 / 23:55; the hard exit stays an hour before close."""
    rel = datetime(day.year, day.month, day.day, 10, 30, tzinfo=NY)
    close = datetime(day.year, day.month, day.day, *((23, 30) if rel.dst() else (23, 55)), tzinfo=IST)
    at = lambda **kw: (rel + timedelta(**kw)).astimezone(IST)  # noqa: E731
    return {"release": at(), "deadline": at(minutes=th["deadline_min"]), "time_stop": at(minutes=th["time_stop_min"]),
            "hard_exit": min(at(hours=th["hard_exit_hours"]), (close - timedelta(minutes=60)).astimezone(IST))}


def api_legs(api_report, products, warnings):
    """API change per leg. Products are valid only for the same API report; otherwise they are missing."""
    api = {"crude": api_report["api_crude_mb"], "gasoline": None, "distillate": None}
    if products and products.get("release_date") == api_report.get("release_date"):
        for leg, key in (("gasoline", "api_gasoline_mb"), ("distillate", "api_distillate_mb")):
            try:
                value = float(products[key])
                if not math.isfinite(value):
                    raise ValueError("not finite")
            except (KeyError, TypeError, ValueError):
                warnings.append(f"api_products.json: {key} is missing or not a number ({products.get(key)!r}): ignored")
                continue
            api[leg] = value
            if abs(value) > 15:
                warnings.append(f"api_products.json: {key} = {value:g} is large; the unit is million barrels")
    elif products:
        warnings.append(f"api_products.json is for {products.get('release_date')}, not the API report of "
                        f"{api_report.get('release_date')}: ignored")
    return api


def score_legs(th, cons, api, eia, warnings):
    """Per leg: baseline = consensus pulled toward the API by api_weight; deviation = EIA actual - baseline."""
    w, legs = th["api_weight"], {}
    for leg in LEGS:
        c, x = cons.get(f"{leg}_consensus_mb"), eia.get(f"{leg}_change_mb")
        if c is None or x is None:
            raise ValueError(f"{leg}: consensus or EIA actual is missing")
        a = api[leg]
        if a is None:
            warnings.append(f"API {leg} missing: baseline is the consensus alone")
        base = c if a is None else (1 - w) * c + w * a
        legs[leg] = {"consensus": c, "api": a, "baseline": base, "actual": x, "deviation": x - base,
                     "deviation_vs_consensus": x - c}  # the last one is recorded only
    return legs


def api_state(th, legs):
    """Tuesday: how the API print moved the market's baseline, on the trio totals of the legs that have an API value."""
    have = [v for v in legs.values() if v["api"] is not None]
    api_net, cons_net = sum(v["api"] for v in have), sum(v["consensus"] for v in have)
    gap = api_net - cons_net
    if abs(gap) < th["api_state_gap"]:
        state = "aligned"
    elif _sign(api_net) * _sign(cons_net) < 0:
        state = "divergent"
    else:  # same side as consensus, or consensus flat: further out is a shift, closer in is "softer"
        state = "shifted" if _sign(gap) == _sign(api_net) else "softer"
    return {"api_net": api_net, "consensus_net": cons_net, "gap": gap, "state": state}


def decide(th, legs, net):
    """Order matters (spec): conflict, then size, then trap, then aligned. Returns (setup, side_sign, reason)."""
    crude, gas, dist = (legs[k]["deviation"] for k in LEGS)
    moving = lambda d: abs(d) >= th["min_leg_dev"]  # noqa: E731
    if moving(gas) and abs(crude) >= th["conflict_min_crude_dev"] and _sign(crude) != _sign(gas):
        return "C", _sign(gas), "crude headline against gasoline: fade the crude, follow the product"
    if abs(net) < th["min_net"]:
        return None, 0, f"net deviation {net:+.2f} is inside ±{th['min_net']:g}"
    api_c, eia_c = legs["crude"]["api"], legs["crude"]["actual"]
    if (_sign(api_c) * _sign(eia_c) < 0 and abs(api_c) >= th["trap_api_min"] and abs(eia_c) >= th["trap_eia_min"]):
        side = _sign(eia_c)
        if side == _sign(net):
            return "B", side, f"API crude {api_c:+.2f} trapped by EIA crude {eia_c:+.2f}"
        return None, 0, "trap on crude, but the trio net deviation points the other way"
    if moving(crude) and moving(gas) and _sign(crude) == _sign(gas):
        if _sign(crude) == _sign(net):
            return "A", _sign(crude), "crude and gasoline deviate the same way"
        return None, 0, "crude and gasoline agree but the trio net deviation points the other way"
    if moving(crude) and moving(gas):  # opposite directions, but crude is too small to count as Setup C
        return None, 0, (f"crude {crude:+.2f} and gasoline {gas:+.2f} deviate in opposite directions, but crude is "
                         f"under {th['conflict_min_crude_dev']:g}: too small for Setup C")
    return None, 0, "crude and gasoline do not both move"


def conviction(th, setup, legs, side, api):
    if setup == "B":
        return "high"
    if setup == "A":  # triple agreement and the API print on the same side
        dist_ok = abs(legs["distillate"]["deviation"]) >= th["min_leg_dev"] and _sign(legs["distillate"]["deviation"]) == side
        api_ok = _sign(api["api_net"]) == side
        return "high" if dist_ok and api_ok else "standard"
    return "standard"


def expected_move(th, setup, net):
    size = abs(net)
    lo, hi = ([th["conflict_move_usd"]] * 2 if setup == "C"
              else next(b[1:] for b in reversed(th["move_bands"]) if size >= b[0]))
    return {"usd": [lo, hi], "rule_of_thumb_usd": [round(k * size, 2) for k in th["rule_of_thumb_per_mb"]],
            "note": "WTI USD per bbl, first ~30 min; bands are unbacktested"}


def confirmation(setup, side):
    """What the trader checks on the 20:00-20:05 candle (the engine reads no prices)."""
    close = "above its open" if side < 0 else "below its open"
    if setup == "C":  # a fade: the first candle is the crude spike, so it must have STALLED, not reversed outright
        close = f"in the {'lower' if side > 0 else 'upper'} half of its range"
    text = {"A": f"enter on a pullback test of the break; the 20:00-20:05 candle must close {close}",
            "B": f"enter after the first candle closes {close}",
            "C": f"do not chase the crude spike; trade the product direction only once the spike has stalled: the "
                 f"20:00-20:05 candle must close {close} (a close at the spike extreme means it is still running: skip)"}[setup]
    return {"candle_must_close": close, "stop_beyond": ("high" if side > 0 else "low") + " of the 20:00-20:05 candle",
            "check": text}


def evaluate(th, cons, api_report, products, eia):
    """Pure scoring: no clock, no I/O."""
    warnings = []
    api = api_legs(api_report, products, warnings)
    legs = score_legs(th, cons, api, eia, warnings)
    net = sum(v["deviation"] for v in legs.values())
    state = api_state(th, legs)
    setup, side, reason = decide(th, legs, net)
    r = {"release_date": cons["release_date"], "status": "NO TRADE" if setup is None else "SIGNAL", "reason": reason,
         "legs": legs, "net_deviation": net, "api_state": state, "warnings": warnings,
         "record_only": {"net_deviation_vs_consensus": sum(v["deviation_vs_consensus"] for v in legs.values()),
                         "cushing_change_mb": eia.get("cushing_change_mb"),
                         "refinery_util_change_pct": eia.get("refinery_util_change_pct"),
                         "net_imports_change_mb": eia.get("net_imports_change_mb")}}
    if setup:
        r.update(setup=setup, side="PUT" if side > 0 else "CALL", bias="BEARISH" if side > 0 else "BULLISH",
                 conviction=conviction(th, setup, legs, side, state), expected_move=expected_move(th, setup, net),
                 confirm=confirmation(setup, side))
        if setup == "C" and _sign(legs["crude"]["deviation"]) > 0:
            warnings.append("crude build vs product draw: the mirror of Setup C, treated symmetrically (not in the spec)")
    return r


def summary(r):
    """The Telegram text: the verdict and what to check at 20:05, in a few lines."""
    lines = [f"TWDR {r['release_date']}: {r['status']}", r["reason"]]
    if "setup" in r:
        lo, hi = r["expected_move"]["usd"]
        lines += [f"Setup {r['setup']} {r['bias']} {r['side']} ({r['conviction']})",
                  f"Expected move ${lo:.2f} to ${hi:.2f} (net deviation {r['net_deviation']:+.2f})",
                  f"Check by {r['schedule']['deadline']}: {r['confirm']['check']}",
                  f"Stop beyond the {r['confirm']['stop_beyond']}; time stop {r['schedule']['time_stop']}, "
                  f"hard exit {r['schedule']['hard_exit']}"]
    return "\n".join(lines + [f"WARNING: {w}" for w in r["warnings"]])


def check_week(cons, api_report, today, allow_stale):
    """The files must belong to the same week and (unless replaying) to today's release."""
    rel_day = parse_release_date(cons["release_date"])
    lag = (rel_day - parse_release_date(api_report["release_date"])).days
    if not 0 <= lag <= 3:
        raise ValueError(f"api_report.json is for {api_report['release_date']}, {lag} days from the EIA release "
                         f"{cons['release_date']}: wrong week")
    if not allow_stale and rel_day != today:
        raise ValueError(f"consensus.json is for {cons['release_date']}, not today ({today:%d-%m-%Y}): "
                         "use --allow-stale to replay an old week")
    return rel_day


def wait_for_eia(release_date, th, once):
    """eia_actuals.json for this release (it still holds last week's until the report is captured)."""
    def attempt():
        try:
            eia = read_json(EIA_ACTUALS_FILE)
        except (OSError, ValueError) as exc:  # missing, locked or caught mid-write: try again
            raise RuntimeError(f"eia_actuals.json not readable yet ({type(exc).__name__})")
        if eia.get("release_date") != release_date:
            raise RuntimeError(f"eia_actuals.json is for {eia.get('release_date')}, waiting for {release_date}")
        return eia
    return poll(attempt, once, th["poll_interval_s"], th["max_wait_min"] * 60, log)


def run(once, allow_stale):
    th = load_thresholds()
    cons, api_report = read_json(CONSENSUS_FILE), read_json(API_REPORT_FILE)
    try:
        products = read_json(API_PRODUCTS_FILE)
    except FileNotFoundError:
        products = None
    rel_day = check_week(cons, api_report, now_ist().date(), allow_stale)
    eia = wait_for_eia(cons["release_date"], th, once)
    now, sched = now_ist(), schedule(rel_day, th)
    r = evaluate(th, cons, api_report, products, eia)
    late = not allow_stale and now > sched["deadline"]
    if late and r["status"] == "SIGNAL":
        r["status"] = "LATE"
        r["reason"] += f" (computed {now:%H:%M:%S}, after the {sched['deadline']:%H:%M} deadline: trader decides)"
    r.update(config_version=th.get("version"), late=late, schedule={k: f"{v:%H:%M}" for k, v in sched.items()},
             data_source=eia.get("source"), data_first_seen=eia.get("released_at"), computed_at=fmt_ts(now))
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0]) # type: ignore
    ap.add_argument("--once", action="store_true", help="do not wait for the EIA actuals")
    ap.add_argument("--allow-stale", action="store_true", help="replay a week that is not today's")
    args = ap.parse_args(argv)
    setup_logging()
    load_dotenv(ROOT / ".env")  # Telegram credentials for the alerts
    try:
        r = run(args.once, args.allow_stale)
        write_json(SIGNAL_FILE, r)
    except Exception as exc:  # noqa: BLE001 - never leave a previous run's signal in place
        log.exception("signal_engine failed")
        write_json(SIGNAL_FILE, {"status": "ERROR", "reason": f"{type(exc).__name__}: {exc}", "computed_at": fmt_ts(now_ist())})
        send_exception("signal_engine.py", exc)
        return 1
    for leg, v in r["legs"].items():
        log.info("%-10s consensus %+.2f api %s baseline %+.2f actual %+.2f deviation %+.2f", leg, v["consensus"],
                 "n/a" if v["api"] is None else f"{v['api']:+.2f}", v["baseline"], v["actual"], v["deviation"])
    log.info("net deviation %+.2f | API %s (gap %+.2f)", r["net_deviation"], r["api_state"]["state"], r["api_state"]["gap"])
    for w in r["warnings"]:
        log.warning(w)
    if "setup" in r:
        log.info("Setup %s %s %s (%s) | expected move $%.2f to $%.2f", r["setup"], r["bias"], r["side"], r["conviction"],
                 *r["expected_move"]["usd"])
        log.info("Check at %s: %s", r["schedule"]["deadline"], r["confirm"]["check"])
    log.info("%s: %s", r["status"], r["reason"])
    send_message(summary(r))  # after the file and the log, so a slow Telegram never delays them
    try:
        write_json(SIGNAL_DIR / f"{parse_release_date(r['release_date']).isoformat()}.json", r)
    except Exception as exc:  # noqa: BLE001 - the history copy must never turn a good signal into an error
        log.warning("signal history not written: %s: %s", type(exc).__name__, exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
