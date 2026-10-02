"""Rupee context for an INR trade on a USD benchmark (MCX Natural Gas on NYMEX Henry Hub; also MCX crude on WTI).

Adapted from the earlier pipeline's module (F:/TradeDesk/twpr/app/currency.py). The signal comes from an EIA
report, which moves the NYMEX price in USD; the instrument is quoted in INR, so roughly

    MCX  ~  NYMEX (USD per unit)  x  USD/INR

This module only NAMES what the rupee has been doing and whether it helps or hurts the trade. It never feeds
the decision: onshore USD/INR trades 09:00-17:00 IST only and the trade is held in the evening, so the currency
market is shut for the whole hold and the move being traded is the NYMEX move. The earlier pipeline measured
WTI against USD/INR over six months of daily data (WTI 7.7x as volatile, the rupee a median 12% of the combined
move, a sign flip on 3.2% of days); the same numbers for natural gas, measured 2026-10-02 over 129 sessions, are
NG=F 5.4x as volatile (mean daily move 1.99% against 0.37%), the rupee a median 12%, a flip on 4.7% of days. The
rupee matters for converting a target into rupees and as a note on the overnight gap, not for direction.
"""

# Below this a 5-session move is noise; at or above SHARP it earns a risk line of its own.
FLAT_TREND_PCT = 0.1
SHARP_TREND_PCT = 0.5


def usdinr_closes(end_day, n=5):
    """The last `n` daily USD/INR closes up to `end_day` (yfinance INR=X). Daily bars are dependable where 5-minute
    ones are sparse. Raises if Yahoo gives nothing."""
    import yfinance as yf  # lazy: heavy import, and the pure functions below need none of it
    h = yf.Ticker("INR=X").history(period="1mo", interval="1d")
    closes = [float(c) for d, c in h["Close"].items() if d.date() <= end_day][-n:]
    if not closes:
        raise RuntimeError("no USD/INR daily closes from yfinance")
    return closes


def trend_pct(series):
    """Percent change from the oldest to the newest value in `series` (None values are skipped)."""
    clean = [v for v in series if v is not None]
    if len(clean) < 2 or not clean[0]:
        return None
    return round((clean[-1] - clean[0]) / clean[0] * 100, 3)


def classify(usd_inr_trend):
    """The rupee's direction. A weakening rupee means USD/INR rising."""
    if usd_inr_trend is None:
        return "unknown"
    if abs(usd_inr_trend) < FLAT_TREND_PCT:
        return "flat"
    return "inr_weakening" if usd_inr_trend > 0 else "inr_strengthening"


def effect_on(direction, currency_direction):
    """Whether the rupee helps or hurts the trade's MCX move. A weakening rupee lifts the rupee price: it works
    against a bearish trade and with a bullish one. Spelled out per case, because the sign conventions invite
    mistakes. `direction` is "bullish", "bearish" or "neutral"."""
    if currency_direction in ("flat", "unknown") or direction == "neutral":
        return "neutral"
    if direction == "bullish":
        return "amplifies" if currency_direction == "inr_weakening" else "dampens"
    return "dampens" if currency_direction == "inr_weakening" else "amplifies"


def risk_notes(usd_inr_trend, direction):
    """The risk lines the rupee earns. Empty when it has nothing to say."""
    if usd_inr_trend is None:
        return ["No USD/INR history: the rupee context is unknown (the NYMEX-to-MCX conversion still uses the live rate)."]
    notes = []
    effect = effect_on(direction, classify(usd_inr_trend))
    moved = "weakened" if usd_inr_trend > 0 else "strengthened"
    if effect == "dampens":
        severity = "sharply " if abs(usd_inr_trend) >= SHARP_TREND_PCT else ""
        notes.append(f"INR {severity}{moved} {abs(usd_inr_trend):.2f}% over 5 sessions, working against a "
                     f"{direction} MCX move.")
    elif effect == "amplifies" and abs(usd_inr_trend) >= SHARP_TREND_PCT:
        notes.append(f"INR {moved} {abs(usd_inr_trend):.2f}% over 5 sessions, amplifying a {direction} MCX move: the "
                     "rupee is doing part of the work, and can give it back.")
    if abs(usd_inr_trend) >= SHARP_TREND_PCT:
        notes.append("Onshore USD/INR is shut 17:00-09:00 IST, so this cannot reverse during the trade: it prices "
                     "the overnight gap, not the session.")
    return notes


def context(usd_inr_trend, direction):
    """The currency block for a record or signal."""
    currency_direction = classify(usd_inr_trend)
    return {"usd_inr_trend_pct": usd_inr_trend, "direction": currency_direction,
            "effect": effect_on(direction, currency_direction), "notes": risk_notes(usd_inr_trend, direction)}
