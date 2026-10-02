"""Run: python -m tests.test_api_products   (or pytest). The texts are real ForexFactory posts; no network."""
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app import api_products as ap

TEXTS = {  # post text -> what a human reads (million barrels)
    "API: Crude: 1.019M, Gasoline: +2.991M, Distillate: -0.286M": {"crude": 1.019, "gasoline": 2.991, "distillate": -0.286},
    "U.s. Api Crude Oil Stock Change Was A Build Of 1.019 Mln, Versus A Forecast 1.9 Mln Draw, With Gasoline Stocks Up 2.991 Mln And Distillate Stocks Down 0.286 Mln":
        {"crude": 1.019, "gasoline": 2.991, "distillate": -0.286},
    "API:  Crude: +1.786M, Cushing: +2.082M, Gasoline: -2.16M,  Distillates: -2.164M":
        {"crude": 1.786, "cushing": 2.082, "gasoline": -2.16, "distillate": -2.164},
    "API: Crude -0.3m, Cushing -0.3m, Distillate +2m, Gasoline - 1.9m":
        {"crude": -0.3, "cushing": -0.3, "distillate": 2.0, "gasoline": -1.9},
    "API Inventory Moves 09/01 Crude -2.6 million Gasoline +300,000 Distillates -300,000 Cushing +200,000 SPR actual -3.1 million #oott #crudeoil #gasoline #api":
        {"crude": -2.6, "gasoline": 0.3, "distillate": -0.3, "cushing": 0.2, "spr": -3.1},
    "Us Api Crude Oil Stock Change Actual 4.2m (forecast -, Previous -0.328m) $macro #API: Crude: +4.2MM Cush: +1.0MM Gas: -3.2MM Dist: -.05MM #OOTT":
        {"crude": 4.2, "cushing": 1.0, "gasoline": -3.2, "distillate": -0.05},
    "API: Crude -328K, Gasoline +1.076M, Distillates -2.797M Cushing -1.438M":
        {"crude": -0.328, "gasoline": 1.076, "distillate": -2.797, "cushing": -1.438},
    "API Inventory Moves 08/18 Crude -328,000 Gasoline +1.076 million Distillates -2.797 million Cushing -1.438 million SPR actual -5.3 million":
        {"crude": -0.328, "gasoline": 1.076, "distillate": -2.797, "cushing": -1.438, "spr": -5.3},
}


def at(day, hour, minute):  # a UNIX timestamp, UTC
    return int(datetime(2026, *day, hour, minute, tzinfo=timezone.utc).timestamp())


ITEMS = [  # (dateline, title) as ForexFactory lists them
    {"dateline": at((9, 29), 20, 46), "title": "API: Crude: 1.019M, Gasoline: +2.991M, Distillate: -0.286M", "preview": "", "source": "@FirstSquawk"},
    {"dateline": at((9, 22), 20, 47), "title": "API:  Crude: +1.786M, Cushing: +2.082M, Gasoline: -2.16M,  Distillates: -2.164M", "preview": "", "source": "@captgirish1"},
    {"dateline": at((9, 9), 20, 48), "title": "API: Crude -0.3m, Cushing -0.3m, Distillate +2m, Gasoline - 1.9m", "preview": "", "source": "@financialjuice"},
    {"dateline": at((8, 25), 20, 55), "title": "US API Crude Oil Stock Change Actual 4.2M (Forecast -, Previous -0.328M)",
     "preview": '<span class="icon"></span>Us Api Crude Oil Stock Change Actual 4.2m $macro #API: Crude: +4.2MM Cush: +1.0MM Gas: -3.2MM Dist: -.05MM #OOTT',
     "source": "@financialjuice"},
]


def report(date, crude):
    return {"release_date": date, "api_crude_mb": crude}


def test_every_observed_format_parses():
    for text, want in TEXTS.items():
        got = {k: v[0] for k, v in ap.parse_post(text).items()}
        assert all(abs(got.get(k, 1e9) - v) < 1e-9 for k, v in want.items()), (text, got)


def test_tolerance_follows_the_posts_precision():
    assert ap.parse_post("Crude -0.3m")["crude"][1] == 0.05
    assert abs(ap.parse_post("Crude -328K")["crude"][1] - 0.0005) < 1e-12


def test_the_right_post_is_picked_by_crude_and_window_not_by_date_label():
    f = ap.find_products(ITEMS, report("22-09-2026", 1.786))
    assert f["from"] == "@captgirish1" and f["legs"]["gasoline"][0] == -2.16 and f["legs"]["cushing"][0] == 2.082
    # holiday week: the print was Wednesday 9 Sep, the API report may carry either date; -0.328 vs "-0.3m" is rounding
    for date in ("08-09-2026", "09-09-2026"):
        assert ap.find_products(ITEMS, report(date, -0.328))["legs"]["distillate"][0] == 2.0


def test_wrong_crude_or_wrong_week_is_rejected():
    assert ap.find_products(ITEMS, report("29-09-2026", 1.5)) == {}  # in the window, crude disagrees
    assert ap.find_products(ITEMS, report("06-10-2026", 1.019)) == {}  # right crude, a week early: outside the window


def test_gas_and_distillate_come_from_the_text_when_the_title_lacks_them():
    f = ap.find_products(ITEMS, report("25-08-2026", 4.2))
    assert (f["legs"]["gasoline"][0], f["legs"]["distillate"][0]) == (-3.2, -0.05)


def test_disagreeing_title_and_text_drop_the_leg():
    legs = ap.merge_title_and_text("API: Crude 1.0M, Gasoline +2.0M", "Crude 1.0M Gasoline -2.0M Distillate +0.5M")
    assert "gasoline" not in legs and legs["distillate"][0] == 0.5


def test_fetch_items_reads_the_json_and_falls_back_across_fingerprints():
    blob = json.dumps(ITEMS).replace('"', "&quot;")
    html = f'<div data-items="{blob}"></div>'
    calls = []

    def get(url, impersonate, timeout):
        calls.append(impersonate)
        return SimpleNamespace(status_code=403 if impersonate == "chrome" else 200, text=html)
    assert len(ap.fetch_items(get)) == 4 and calls == ["chrome", "safari17_0"]
    try:
        ap.fetch_items(lambda *a, **k: SimpleNamespace(status_code=403, text=""))
    except RuntimeError as exc:
        assert "unavailable" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_partial_post_retries_and_is_remembered():
    partial = {}
    items = [{"dateline": at((9, 29), 20, 46), "title": "API: Crude: 1.019M, Gasoline: +2.991M", "preview": "", "source": "@x"}]
    get = lambda *a, **k: SimpleNamespace(status_code=200, text=f'<div data-items="{json.dumps(items).replace(chr(34), "&quot;")}"></div>')  # noqa: E731
    try:
        ap.attempt(report("29-09-2026", 1.019), partial, get)
    except RuntimeError as exc:
        assert "distillate" in str(exc) and partial["legs"]["gasoline"][0] == 2.991
    else:
        raise AssertionError("expected RuntimeError")


def test_manual_file_is_never_overwritten():
    d = Path(tempfile.mkdtemp())
    ap.API_REPORT_FILE, ap.API_PRODUCTS_FILE = d / "r.json", d / "p.json"
    ap.API_REPORT_FILE.write_text(json.dumps(report("29-09-2026", 1.019)), encoding="utf-8")
    manual = {"release_date": "29-09-2026", "source": "manual", "api_gasoline_mb": 9.9, "api_distillate_mb": 9.9}
    ap.API_PRODUCTS_FILE.write_text(json.dumps(manual), encoding="utf-8")
    ap.poll = lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not fetch"))
    assert ap.main(["--allow-stale", "--once", "--force"]) == 0
    assert json.loads(ap.API_PRODUCTS_FILE.read_text(encoding="utf-8")) == manual


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
