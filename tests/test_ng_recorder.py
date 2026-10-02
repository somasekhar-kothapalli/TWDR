"""Run: python -m tests.test_ng_recorder   (or pytest). Fake price bars and a real EIA file, no network."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from app import ng_recorder as nr

NY = ZoneInfo("America/New_York")
T0 = datetime(2026, 10, 1, 10, 30, tzinfo=NY)

EIA = '''﻿Energy Information Administration
"Working Gas in Underground Storage, Lower 48"
"Released: October 1, 2026 at 10:30 a.m. (eastern time) for the Week Ending September 25, 2026"
"Next Release: October 8, 2026"
Region,Stocks in billion (Bcf),,,,,,,,,,,,Historical Comparisons
,,,,,,,,,,,,,Year Ago (09/25/25),,,,,,5-Year (2021-25) Average
,25-Sep-26,,,18-Sep-26,,,net change (Bcf),,,implied flow (Bcf),,,stocks (Bcf),,,% change,,,stocks (Bcf),,,% change
East,"840","","","815","",,"25","",,"25",,"","828",,,"1.4",,,"803",,,"4.6",,"",""
South Central,"1,048","","","1,041","",,"7","",,"7",,"","1,187",,,"-11.7",,,"1,074",,,"-2.4",,"",""
  Salt,"213","","","217","",,"-4","",,"-4",,"","293",,,"-27.3",,,"252",,,"-15.5",,"",""
  Nonsalt,"834","","","825","",,"9","",,"9",,"","893",,,"-6.6",,,"822",,,"1.5",,"",""
Total,"3,415","","","3,351","",,"64","",,"64",,"","3,553",,,"-3.9",,,"3,336",,,"2.4",,"",""
'''


def bars(start="09:30", hours=3, price=3.0, day="2026-10-01"):
    idx = pd.date_range(f"{day} {start}", periods=hours * 12, freq="5min", tz=NY)
    return pd.DataFrame({"Open": price, "High": price + 0.005, "Low": price - 0.005, "Close": price, "Volume": 10.0}, index=idx)


def saved(df):
    return nr.window(df, T0)


def test_release_day_and_time_follow_the_eia_schedule():
    assert nr.release_at(date(2026, 10, 8)).strftime("%H:%M") == "10:30"           # a normal Thursday
    assert nr.release_at(date(2026, 11, 25)).strftime("%a %H:%M") == "Wed 12:00"    # Thanksgiving week
    assert nr.release_at(date(2026, 11, 13)).strftime("%a %H:%M") == "Fri 10:30"    # Veterans Day week
    assert nr.release_at(date(2026, 11, 12)) is None and nr.release_at(date(2026, 11, 26)) is None  # the replaced Thursdays
    assert nr.release_at(date(2026, 10, 9)) is None                                  # a Friday


def test_eia_file_parses_total_salt_and_the_average():
    e = nr.parse_eia_csv(EIA)
    assert (e["release"], e["week_ending"]) == (date(2026, 10, 1), date(2026, 9, 25))
    assert e["regions"]["Total"]["net_change"] == 64 and e["regions"]["Total"]["avg5"] == 3336
    assert e["regions"]["Salt"]["net_change"] == -4 and e["regions"]["Salt"]["stocks"] == 213


def test_salt_ratio_variables():
    hist = pd.Series({date(2026, 9, 18): -5.0, date(2026, 9, 25): -4.0, date(2025, 9, 26): 2.0, date(2024, 9, 27): 4.0})
    v = nr.salt_variables(date(2026, 9, 25), -4.0, 5.0, hist)
    assert v["salt_change_prior_week"] == -5.0 and v["ratio_prior_week"] == 0.2   # |-4 - -5| / 5
    assert v["rule_applies"] and v["applied"] is False and v["salt_change_5y_same_week_avg"] == 3.0
    assert nr.salt_variables(date(2026, 9, 25), -4.0, 0.0, hist)["ratio_prior_week"] is None


def test_size_bands():
    assert [nr.size_band(x) for x in (0, 3, 3.5, 4, 10, 11, 12, 12.1, 13, -13)] == \
           ["noise", "noise", "buffer_a", "standard", "standard", "high_momentum", "high_momentum", "shock", "shock", "shock"]


def _with_first_close(close):
    df = bars()
    df.loc[T0, ["Close", "High", "Low"]] = [close, max(close, 3.005), min(close, 2.995)]
    return saved(df)


def test_aligned_divergent_and_inside():
    # a bigger build (+5) is bearish: a first close below the box (2.995) is aligned, above it is divergent
    assert nr.evaluate_rule(_with_first_close(2.98), T0, 5)["status"] == "ALIGNED: enter"
    assert nr.evaluate_rule(_with_first_close(3.02), T0, 5)["status"] == "DIVERGENT: skip"
    assert nr.evaluate_rule(_with_first_close(3.0), T0, 5)["status"].startswith("INSIDE")
    assert nr.evaluate_rule(_with_first_close(2.98), T0, 2)["status"] == "NO TRADE (noise)"
    assert nr.evaluate_rule(_with_first_close(3.02), T0, -5)["status"] == "ALIGNED: enter"  # a draw is bullish


def _inside_then(close2, close3):
    df = bars()
    for k, c in ((5, close2), (10, close3)):
        df.loc[T0 + timedelta(minutes=k), ["Close", "High", "Low"]] = [c, max(c, 3.005), min(c, 2.995)]
    return saved(df)


def test_the_plus_15_minute_fallback_decides_a_first_candle_inside_the_box():
    # +5 Bcf is bearish; the first candle is inside the box (bars() default)
    assert nr.evaluate_rule(_inside_then(3.0, 2.98), T0, 5)["fallback"]["status"] == "ALIGNED at the 10:45 close: enter"
    assert nr.evaluate_rule(_inside_then(3.0, 3.02), T0, 5)["fallback"]["status"] == "DIVERGENT at the 10:45 close: skip"
    assert nr.evaluate_rule(_inside_then(3.0, 3.0), T0, 5)["fallback"]["status"] == "NO TRADE: no breakout by the 10:45 close"
    assert nr.evaluate_rule(_inside_then(3.0, 2.98), T0, 2)["fallback"] is None  # a noise week never gets that far


def _candle(o, h, l, c, box=(2.95, 3.05)):
    """Bars with a wide pre-report box (10 cents) and the given first candle."""
    df = bars()
    for k in (-15, -10, -5):
        df.loc[T0 + timedelta(minutes=k), ["High", "Low"]] = [box[1], box[0]]
    df.loc[T0, ["Open", "High", "Low", "Close"]] = [o, h, l, c]
    return saved(df)


def test_long_wick_rules_veto_the_primary_entry():
    # +5 Bcf is bearish: a first close below the box (2.95) is a downward breakout; the opposing wick is the UPPER one
    clean = nr.evaluate_rule(_candle(2.949, 2.949, 2.94, 2.945), T0, 5)
    assert clean["status"] == "ALIGNED: enter" and clean["first_candle"]["wick_veto"] is False
    a = nr.evaluate_rule(_candle(2.949, 2.951, 2.94, 2.9475), T0, 5)   # wick 0.2c > body 0.15c, small against the box
    assert a["first_candle"]["wick_rule_a"] and not a["first_candle"]["wick_rule_b"] and a["status"].startswith("WICK VETO")
    b = nr.evaluate_rule(_candle(3.0, 3.055, 2.92, 2.93), T0, 5)       # wick 5.5c <= body 7c, but over half the 10c box
    assert b["first_candle"]["wick_rule_b"] and not b["first_candle"]["wick_rule_a"] and b["status"].startswith("WICK VETO")
    assert a["fallback"] is not None  # the +15 minute close then decides
    # an upward breakout against the bearish headline stays DIVERGENT whatever its wicks, and a noise week stays no trade
    assert nr.evaluate_rule(_candle(3.051, 3.06, 3.04, 3.055), T0, 5)["status"] == "DIVERGENT: skip"
    assert nr.evaluate_rule(_candle(2.949, 2.951, 2.94, 2.9475), T0, 2)["status"] == "NO TRADE (noise)"


def test_first_candle_shape_is_recorded_not_used():
    shape = nr.evaluate_rule(_with_first_close(2.98), T0, 5)["first_candle"]
    assert shape["fully_outside"] is False and shape["lower_wick_cents"] >= 0 and "wick" not in nr.evaluate_rule(_with_first_close(2.98), T0, 5)["status"]


def test_contract_of_the_day_follows_the_roll_rule():
    got = {d: nr.contract_for(d) for d in (date(2026, 10, 8), date(2026, 10, 22), date(2026, 11, 13), date(2026, 11, 19),
                                          date(2026, 11, 25), date(2026, 12, 24), date(2027, 1, 21), date(2027, 2, 18), date(2027, 3, 25))}
    assert list(got.values()) == ["OCT", "NOV", "NOV", "DEC", "DEC", "JAN", "FEB", "MAR", None]


def test_pre_survives_a_consensus_that_is_not_posted_yet():
    now = datetime(2026, 10, 8, 19, 55, tzinfo=ZoneInfo("Asia/Kolkata"))
    pre = nr.run_pre(date(2026, 10, 8), get_row=lambda d: {"consensus": None, "previous": 64.0},
                     get_rates=lambda n: [{"source": "a", "value": 96.3, "as_of": "z", "age_min": 4.0}], now=now)
    text = nr.pre_summary(pre)
    assert "Consensus NOT POSTED yet" in text and "Previous 64 Bcf" in text and "Contract: OCT" in text
    none_rate = dict(pre, pre=dict(pre["pre"], usdinr_chosen=None))
    assert "no reading from any source" in nr.pre_summary(none_rate)


def test_the_telegram_summaries_say_what_the_trader_needs():
    now = datetime(2026, 10, 8, 19, 55, tzinfo=ZoneInfo("Asia/Kolkata"))
    pre = nr.run_pre(date(2026, 10, 8), get_row=lambda d: {"consensus": 70.0, "previous": 64.0},
                     get_rates=lambda n: [{"source": "a", "value": 96.3, "as_of": "z", "age_min": 45.0}], now=now)
    text = nr.pre_summary(pre)
    assert "Consensus 70 Bcf" in text and "Contract: OCT" in text and "WARNING: older than 30 minutes" in text and "13+ shock" in text
    rec = {"release_date": "01-10-2026", "actual_bcf": 64.0, "consensus_bcf": 63.0, "surprise_bcf": 1.0,
           "rule": nr.evaluate_rule(_with_first_close(2.98), T0, 1.0), "salt": {"salt_change": -4.0, "ratio_prior_week": 1.0, "ratio_5y_avg": 6.8},
           "currency": {"notes": ["INR weakened 0.6%"]}}
    post = nr.post_summary(rec)
    assert "record (not a signal)" in post and "+1 Bcf: noise (stand down)" in post and "Salt -4 Bcf" in post and "RUPEE: INR weakened" in post


def test_a_divergence_logs_the_warning_and_both_summaries_are_sent():
    import logging
    import tempfile
    from pathlib import Path
    seen, sent = [], []

    class Catch(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())
    handler = Catch()
    logging.getLogger("twdr.ng_recorder").addHandler(handler)
    rule = nr.evaluate_rule(_with_first_close(3.02), T0, 5)  # a bearish headline, price broke UP: divergent
    rec = {"release_date": "01-10-2026", "actual_bcf": 68.0, "consensus_bcf": 63.0, "surprise_bcf": 5.0, "rule": rule,
           "salt": {"salt_change": -4.0, "ratio_prior_week": 1.0, "ratio_5y_avg": 6.8}, "currency": {"notes": []}}
    nr.NG_RECORD_FILE, nr.run_post, nr.send_message = Path(tempfile.mkdtemp()) / "r.json", (lambda *a, **k: rec), sent.append
    try:
        assert nr.main(["post", "--date", "01-10-2026"]) == 0
    finally:
        logging.getLogger("twdr.ng_recorder").removeHandler(handler)
    assert any("DIVERGENCE DETECTED" in m and "SKIP" in m for m in seen)
    assert len(sent) == 1 and "DIVERGENT: skip" in sent[0]


def test_move_after_the_release_is_in_cents_from_the_release_open():
    r = nr.evaluate_rule(_with_first_close(2.98), T0, 5)
    assert r["move_cents"]["close_5"] == -2.0 and r["move_cents"]["max_down"] <= -2.0


def test_the_freshest_usdinr_wins_and_a_missing_age_is_flagged():
    old = {"source": "a", "value": 96.0, "as_of": "x", "age_min": 240.0}
    new = {"source": "b", "value": 96.3, "as_of": "y", "age_min": 3.0}
    assert nr.choose_rate([old, new])["source"] == "b" and nr.choose_rate([old, new])["warning"] is None
    assert nr.choose_rate([old])["warning"] == "older than 30 minutes"
    assert nr.choose_rate([{"source": "c", "value": 96.2, "as_of": None, "age_min": None}])["warning"] == "age unknown"
    assert nr.choose_rate([{"source": "c", "error": "boom"}]) is None


def test_pre_records_consensus_rate_and_minutes_before_the_release():
    now = datetime(2026, 10, 8, 19, 55, tzinfo=ZoneInfo("Asia/Kolkata"))
    rec = nr.run_pre(date(2026, 10, 8), get_row=lambda d: {"consensus": 70.0, "previous": 64.0},
                     get_rates=lambda n: [{"source": "a", "value": 96.3, "as_of": "z", "age_min": 4.0}], now=now)
    assert rec["consensus_bcf"] == 70.0 and rec["release_ist"] == "20:00" and rec["pre"]["minutes_before_release"] == 5.0
    assert rec["pre"]["usdinr_chosen"]["value"] == 96.3


def test_rupee_context_is_a_note_that_follows_the_bias():
    weak = [95.8, 96.0, 96.1, 96.2, 96.3]  # USD/INR up 0.52% over 5 sessions: INR weakening, sharp
    assert nr.currency_block(weak, "up")["effect"] == "amplifies"      # a bullish report: a weaker rupee lifts MCX
    assert nr.currency_block(weak, "down")["effect"] == "dampens"      # a bearish report: it works against it
    assert nr.currency_block(weak, None)["effect"] == "neutral"
    assert nr.currency_block([], "up")["direction"] == "unknown"


def test_window_runs_from_30_minutes_before_to_90_after():
    w = saved(bars())
    assert w[0]["t"].startswith("2026-10-01T10:00") and w[-1]["t"].startswith("2026-10-01T11:55") and len(w) == 24


def test_a_rerun_never_shrinks_saved_bars():
    row = {"release_date": "01-10-2026", "actual": 64.0, "consensus": 63.0, "previous": 53.0}
    full = nr.backfill([row], bars(), bars())
    empty = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"], index=pd.DatetimeIndex([], tz=NY))
    again = nr.backfill([row], empty, empty, full)
    assert len(again["reports"]["2026-10-01"]["ng_bars"]) == 24 and again["reports"]["2026-10-01"]["surprise_bcf"] == 1.0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
