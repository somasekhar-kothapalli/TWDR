"""Run: python -m tests.test_currency   (or pytest)."""
from app.utils import currency as c


def test_trend_and_classification():
    assert c.trend_pct([100.0, None, 100.5]) == 0.5 and c.trend_pct([1.0]) is None and c.trend_pct([0, 1]) is None
    assert [c.classify(x) for x in (None, 0.05, -0.05, 0.3, -0.3)] ==            ["unknown", "flat", "flat", "inr_weakening", "inr_strengthening"]


def test_effect_is_spelled_out_for_every_case():
    assert c.effect_on("bullish", "inr_weakening") == "amplifies" and c.effect_on("bullish", "inr_strengthening") == "dampens"
    assert c.effect_on("bearish", "inr_weakening") == "dampens" and c.effect_on("bearish", "inr_strengthening") == "amplifies"
    assert c.effect_on("neutral", "inr_weakening") == "neutral" and c.effect_on("bullish", "flat") == "neutral"


def test_notes_only_when_the_rupee_has_something_to_say():
    assert c.risk_notes(0.05, "bullish") == []
    assert len(c.risk_notes(0.6, "bearish")) == 2  # dampening and sharp: the risk line plus the overnight-gap note
    assert "No USD/INR history" in c.risk_notes(None, "bullish")[0]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
