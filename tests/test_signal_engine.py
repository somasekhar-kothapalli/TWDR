"""Run: python -m tests.test_signal_engine   (or pytest). No network, no data/ files."""
from datetime import date

from app import signal_engine as se

TH = dict(api_weight=0.5, min_leg_dev=0.1, min_net=2.0, api_state_gap=1.0, trap_api_min=4.0, trap_eia_min=2.0,
          conflict_min_crude_dev=2.0, conflict_move_usd=0.5,
          move_bands=[[0, 0.30, 0.50], [2.0, 0.60, 1.00], [5.0, 1.20, 2.00]], rule_of_thumb_per_mb=[0.15, 0.25],
          deadline_min=5, time_stop_min=35, hard_exit_hours=2.5, poll_interval_s=5, max_wait_min=15)


def run(cons=(0, 0, 0), api=(0, 0, 0), eia=(0, 0, 0), products=True):
    c = dict(release_date="30-09-2026", **{f"{k}_consensus_mb": v for k, v in zip(se.LEGS, cons)})
    rep = dict(release_date="29-09-2026", api_crude_mb=api[0])
    prod = dict(release_date="29-09-2026", api_gasoline_mb=api[1], api_distillate_mb=api[2]) if products else None
    e = {f"{k}_change_mb": v for k, v in zip(se.LEGS, eia)}
    return se.evaluate(TH, c, rep, prod, e)


def test_aligned_bullish_strong():
    r = run(cons=(-1.0, 0.5, -0.5), api=(-1.0, 0.5, -0.5), eia=(-3.0, -0.5, -1.0))  # deviations -2.0, -1.0, -0.5
    assert (r["setup"], r["side"], r["conviction"], r["expected_move"]["usd"]) == ("A", "CALL", "high", [0.6, 1.0])


def test_conflict_beats_size():
    r = run(eia=(-3.0, 2.0, 1.0))  # net deviation 0.0, yet crude draw against product builds
    assert (r["setup"], r["side"], r["expected_move"]["usd"]) == ("C", "PUT", [0.5, 0.5])


def test_trap_bull():
    r = run(api=(4.5, 0, 0), eia=(-2.5, 0, 0))  # baseline +2.25, deviation -4.75
    assert (r["setup"], r["side"]) == ("B", "CALL") and r["expected_move"]["usd"] == [0.6, 1.0]


def test_no_trade_small_or_flat_gasoline():
    assert run(eia=(-1.0, -0.5, 0.0))["status"] == "NO TRADE"  # net -1.5 is inside the band
    assert run(eia=(-1.0, -0.5, -0.5))["status"] == "SIGNAL"  # net -2.0 sits on the line and trades
    assert run(eia=(-3.0, 0.05, 0.0))["status"] == "NO TRADE"  # gasoline not moving: crude alone is not enough


def test_small_crude_against_big_products_says_why():
    r = run(eia=(0.5, -3.0, -2.0))  # the 30 Sep 2026 shape: crude barely up, products far down
    assert r["status"] == "NO TRADE" and "too small for Setup C" in r["reason"]


def test_api_states():
    legs = lambda api, cons: se.api_state(TH, {"x": dict(api=api, consensus=cons)})["state"]  # noqa: E731
    assert (legs(-1.8, -1.5), legs(-5.0, -1.5), legs(3.5, -1.5), legs(-0.2, -1.5)) == \
           ("aligned", "shifted", "divergent", "softer")


def test_missing_api_products_flagged():
    r = run(cons=(-1.0, 0.5, -0.5), eia=(-3.0, -0.5, -1.0), products=False)
    assert any("API gasoline missing" in w for w in r["warnings"]) and r["legs"]["gasoline"]["baseline"] == 0.5


def test_stale_products_ignored():
    warnings = []
    api = se.api_legs(dict(release_date="29-09-2026", api_crude_mb=0),
                      dict(release_date="22-09-2026", api_gasoline_mb=9, api_distillate_mb=9), warnings)
    assert api["gasoline"] is None and warnings


def test_setup_c_asks_for_a_stalled_spike_not_a_full_reversal():
    assert se.confirmation("C", 1)["candle_must_close"] == "in the lower half of its range"  # fade after a crude spike up
    assert se.confirmation("C", -1)["candle_must_close"] == "in the upper half of its range"
    assert se.confirmation("A", -1)["candle_must_close"] == "above its open"


def test_bad_api_products_values_are_ignored_not_fatal():
    w = []
    api = se.api_legs(dict(release_date="29-09-2026", api_crude_mb=1.0),
                      dict(release_date="29-09-2026", api_gasoline_mb="-1.2M", api_distillate_mb=0.4), w)
    assert api["gasoline"] is None and api["distillate"] == 0.4 and len(w) == 1
    w = []
    assert se.api_legs(dict(release_date="29-09-2026", api_crude_mb=1.0),
                       dict(release_date="29-09-2026", api_gasoline_mb="nan"), w)["gasoline"] is None and len(w) == 2


def test_rupee_context_follows_the_side_and_reaches_the_summary():
    r = run(cons=(-1.0, 0.5, -0.5), api=(-1.0, 0.5, -0.5), eia=(-3.0, -0.5, -1.0))  # a bullish call
    se.attach_currency(r, -0.6)  # USD/INR down 0.6% over 5 sessions: the rupee strengthened, against a bullish MCX move
    assert r["currency"]["effect"] == "dampens" and r["currency"]["direction"] == "inr_strengthening"
    sched = {"deadline": "20:05", "time_stop": "20:35", "hard_exit": "22:30"}
    assert "RUPEE: INR sharply strengthened 0.60%" in se.summary({**r, "schedule": sched, "status": "SIGNAL"})
    se.attach_currency(run(eia=(0.5, 0, 0)), None)  # no setup, no history: unknown, no crash


def test_summary_is_what_the_trader_needs():
    sched = {"deadline": "20:05", "time_stop": "20:35", "hard_exit": "22:30"}
    r = {**run(cons=(-1.0, 0.5, -0.5), api=(-1.0, 0.5, -0.5), eia=(-3.0, -0.5, -1.0)), "schedule": sched, "status": "SIGNAL"}
    text = se.summary(r)
    assert "Setup A BULLISH CALL (high)" in text and "Check by 20:05" in text and "Stop beyond the low" in text
    flat = {**run(eia=(0.5, 0, 0)), "schedule": sched}
    assert se.summary(flat).splitlines()[:2] == ["TWDR 30-09-2026: NO TRADE", flat["reason"]]


def test_schedule_summer_and_winter():
    s, w = se.schedule(date(2026, 9, 30), TH), se.schedule(date(2026, 11, 4), TH)
    assert (s["release"].hour, s["deadline"].minute, s["hard_exit"].hour, s["hard_exit"].minute) == (20, 5, 22, 30)
    assert (w["release"].hour, w["hard_exit"].hour, w["hard_exit"].minute) == (21, 22, 55)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
