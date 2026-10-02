"""Run: python -m tests.test_eia_actuals   (or pytest). Fake scrapers, no network, no browser."""
import json
import tempfile
from datetime import date
from pathlib import Path

from app import eia_actuals as ea
from app import signal_engine as se

REL = "30-09-2026"
SLUGS = {  # slug -> actual, per site; a slug that is missing is a page that fails
    "tradingeconomics": {"united-states/crude-oil-stocks-change": 1.0, "united-states/gasoline-stocks-change": -1.7,
                         "united-states/distillate-stocks": -2.2, "united-states/cushing-crude-oil-stocks": 0.3,
                         "united-states/crude-oil-imports": 0.4},
    "investing": {"eia-crude-oil-inventories-75": 1.0, "weekly-gasoline-inventories-485": -1.7,
                  "eia-weekly-distillates-stocks-917": -2.2, "eia-weekly-cushing-oil-inventories-1657": 0.3,
                  "eia-weekly-refinery-utilization-rates-1961": -2.8},
}


def fake(down=()):
    """A scraper factory; sites in `down` return no page at all."""
    class Scraper:
        session_gap_s = 0

        def __init__(self, site):
            self.site = site

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def fetch_page(self, slug):
            value = SLUGS[self.site].get(slug)
            if self.site in down or value is None:
                return None
            return {"calendar_rows": [{"release_date": REL, "time": None, "actual": value, "consensus": None,
                                       "previous": None}], "stats": {}}
    return Scraper


def test_report_needs_only_three_legs_and_either_site_can_win():
    for down in (("investing",), ("tradingeconomics",)):  # investing has no net-imports page: it must still win
        r = ea.fetch_eia_actuals(REL, make_scraper=fake(down), today=date(2026, 9, 30))
        assert (r["crude_change_mb"], r["gasoline_change_mb"], r["distillate_change_mb"]) == (1.0, -1.7, -2.2)
        assert r["source"] == ("tradingeconomics" if down == ("investing",) else "investing.com")
        assert "cushing_change_mb" not in r


def test_one_browser_for_unpaced_sites_one_per_leg_for_paced_ones():
    opened = []

    def counting(site, gap):
        base = fake()

        class S(base):
            session_gap_s = gap

            def __enter__(self):
                opened.append(site)
                return self
        return S(site)

    ea.fetch_candidate("tradingeconomics", REL, date(2026, 9, 30), __import__("threading").Event(), counting_factory(counting, 0))
    assert len(opened) == 1
    opened.clear()
    ea.fetch_candidate("investing", REL, date(2026, 9, 30), __import__("threading").Event(), counting_factory(counting, 0.01))
    assert len(opened) == 3


def counting_factory(counting, gap):
    return lambda site: counting(site, gap)


def test_extras_arrive_after_and_are_best_effort():
    got = ea.fetch_extras(REL, make_scraper=fake(), today=date(2026, 9, 30), timeout_s=5)
    assert {k: v[1]["value"] for k, v in got.items()} == {"cushing": 0.3, "net_imports": 0.4, "refinery": -2.8}
    assert ea.fetch_extras(REL, make_scraper=fake(("investing", "tradingeconomics")), timeout_s=5) == {}


def test_add_extras_never_raises_and_fills_the_file():
    ea.EIA_ACTUALS_FILE = Path(tempfile.mkdtemp()) / "eia.json"
    payload = {"release_date": REL, "cushing_change_mb": None, "cushing_level_mb": None,
               "net_imports_change_mb": None, "refinery_util_change_pct": None}
    ea.add_extras(payload, fetch=lambda *a: {"cushing": ("x", {"value": 0.3}), "refinery": ("x", {"value": -2.8})},
                  level=lambda change: 20.5)
    saved = json.loads(ea.EIA_ACTUALS_FILE.read_text(encoding="utf-8"))
    assert (saved["cushing_change_mb"], saved["cushing_level_mb"], saved["refinery_util_change_pct"]) == (0.3, 20.5, -2.8)
    ea.add_extras({"release_date": REL}, fetch=lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))  # no raise


def test_engine_retries_on_an_unreadable_file():
    se.EIA_ACTUALS_FILE = Path(tempfile.mkdtemp()) / "eia.json"
    se.EIA_ACTUALS_FILE.write_text('{"release_date": "30-0', encoding="utf-8")  # caught mid-write
    try:
        se.wait_for_eia(REL, {"poll_interval_s": 1, "max_wait_min": 1}, once=True)
    except RuntimeError as exc:
        assert "not readable" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
