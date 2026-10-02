"""Draw the MCX natural gas option tables (call and put, delta 0.4 to 0.9) to PNG: what a correct 3 cent move earns,
and what an implied-volatility (IV) fall takes back. HTML laid out by the browser, rendered with Playwright.

    python docs/img/make_iv_tables.py        # writes docs/img/twdr_ng_iv_tables.png

Every number is computed here (Black-76, no interest, no time decay: the hold is 30 minutes), not typed in. To update
the picture, change the PARAMETERS below and rerun. These are estimates for learning, not MCX quotes.
"""
from math import erf, exp, log, sqrt
from pathlib import Path
from statistics import NormalDist

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent

# ---------------------------------------------------------------------------------------------- PARAMETERS
FUTURES = 300.0          # MCX futures price, Rs per MMBtu (about $3.10 x 96.3)
DAYS = 20                # days to option expiry
IV = 0.70                # implied volatility before the report (70%)
LOT = 1250               # MMBtu per lot (mini lot: 250)
MOVE_CENTS = 3.0         # the report's price move in NYMEX cents
RUPEE = 96.3             # USD/INR used to turn cents into rupees
IV_FALLS = (5, 10)       # IV points lost at the release
DELTAS = (0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
STOP_FRACTION = 0.30     # the stop used elsewhere: premium falls 30%

MOVE = MOVE_CENTS / 100 * RUPEE      # Rs per MMBtu
T = DAYS / 365
N = NormalDist()


def cdf(x):
    return 0.5 * (1 + erf(x / sqrt(2)))


def price(kind, f, k, iv):
    """Black-76 option price in Rs per MMBtu (no discounting)."""
    s = iv * sqrt(T)
    d1 = (log(f / k) + 0.5 * s * s) / s
    d2 = d1 - s
    return f * cdf(d1) - k * cdf(d2) if kind == "CE" else k * cdf(-d2) - f * cdf(-d1)


def strike_for(kind, delta):
    """The strike whose option has this delta (call delta N(d1); put delta N(d1) - 1)."""
    d1 = N.inv_cdf(delta) if kind == "CE" else N.inv_cdf(1 - delta)
    s = IV * sqrt(T)
    return FUTURES * exp(-(d1 * s - 0.5 * s * s))


def wipeout(kind, k, premium):
    """IV points that must fall to erase the gain of a correct move (None if more than 60)."""
    f = FUTURES + MOVE if kind == "CE" else FUTURES - MOVE
    for x in range(0, 61):
        if price(kind, f, k, IV - x / 100) - premium <= 0:
            return x
    return None


def rows(kind):
    out = []
    for d in DELTAS:
        k = strike_for(kind, d)
        p0 = price(kind, FUTURES, k, IV)
        up = FUTURES + MOVE if kind == "CE" else FUTURES - MOVE      # a move in the trade's favour
        down = FUTURES - MOVE if kind == "CE" else FUTURES + MOVE    # a move against it
        gain = lambda f, iv: (price(kind, f, k, iv) - p0) * LOT
        vega = (p0 - price(kind, FUTURES, k, IV - 0.01)) * LOT
        out.append({
            "delta": d, "k": k, "p": p0, "cost": p0 * LOT,
            "per_pt": abs(price(kind, FUTURES + 0.5, k, IV) - price(kind, FUTURES - 0.5, k, IV)) * LOT,
            "vega": vega, "stop": p0 * STOP_FRACTION * LOT,
            "right": gain(up, IV), "right_f": [gain(up, IV - x / 100) for x in IV_FALLS],
            "wrong": gain(down, IV - IV_FALLS[0] / 100), "wipe": wipeout(kind, k, p0),
            "itm": (k < FUTURES) if kind == "CE" else (k > FUTURES), "gap": abs(k - FUTURES),
        })
    return out


# ---------------------------------------------------------------------------------------------- HTML
CSS = """
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 26px 30px 30px; width: 1500px; background: #fff; color: #1a202c; }
h1 { font-size: 28px; margin: 0 0 4px; text-align: center; }
h2 { font-size: 21px; margin: 26px 0 8px; padding: 6px 14px; border-radius: 8px; }
h2.ce { background: #e0f6e6; border-left: 8px solid #2f855a; }
h2.pe { background: #fde8e8; border-left: 8px solid #c53030; }
.sub { text-align: center; font-size: 15px; color: #4a5568; margin-bottom: 12px; line-height: 1.45; }
.cards { display: flex; gap: 12px; margin: 10px 0; }
.card { flex: 1; border: 2px solid #2b6cb0; background: #e6f0ff; border-radius: 10px; padding: 9px 12px; font-size: 14px; line-height: 1.4; }
.card.w { border-color: #b7791f; background: #fff8cc; }
.card b.h { display: block; font-size: 15px; margin-bottom: 2px; }
table { border-collapse: collapse; width: 100%; font-size: 14.5px; }
th { background: #2d3748; color: #fff; padding: 7px 6px; font-weight: 600; line-height: 1.25; border: 1px solid #fff; }
th small { display: block; font-weight: 400; font-size: 12px; opacity: .85; }
td { text-align: center; padding: 8px 6px; border: 1px solid #cbd5e0; }
td.d { font-weight: 700; font-size: 17px; }
td small { display: block; color: #4a5568; font-size: 12px; }
tr.itm td { background: #f7fafc; } tr.atm td { background: #fffbe6; } tr.otm td { background: #fff; }
td.pos { color: #276749; font-weight: 700; } td.neg { color: #c53030; font-weight: 700; }
td.zero { color: #c53030; font-weight: 700; background: #fde8e8 !important; }
.note { font-size: 13.5px; color: #4a5568; margin: 8px 6px 0; line-height: 1.45; }
.take { border: 2px solid #718096; background: #ececec; border-radius: 10px; padding: 10px 16px; margin-top: 22px; font-size: 14.5px; line-height: 1.5; }
.take b.h { font-size: 16px; display: block; margin-bottom: 3px; }
.take ul { margin: 2px 0 0; padding-left: 20px; }
"""


def rs(x, sign=False):
    s = f"{abs(x):,.0f}"
    return ("+" if x > 0 else "−" if x < 0 else "") + "₹" + s if sign else "₹" + s


def cell(x):
    return f'<td class="{"pos" if x > 0 else "neg"}">{rs(x, True)}</td>'


def table(kind):
    word = "CALL (CE): you win if gas goes UP" if kind == "CE" else "PUT (PE): you win if gas goes DOWN"
    direction = "rises" if kind == "CE" else "falls"
    head = (f'<tr><th>Delta<small>speed of the option</small></th><th>Strike<small>and how far from futures</small></th>'
            f'<th>Premium<small>₹ per MMBtu</small></th><th>Cost of 1 lot<small>premium × {LOT:,}</small></th>'
            f'<th>Gain per ₹1 move<small>in futures, per lot</small></th><th>Lost per IV point<small>per lot</small></th>'
            f'<th>Right call: gas {direction} {MOVE_CENTS:g}¢<small>IV unchanged</small></th>'
            f'<th>…and IV falls {IV_FALLS[0]} points</th><th>…and IV falls {IV_FALLS[1]} points</th>'
            f'<th>Wrong call: gas moves {MOVE_CENTS:g}¢ against you<small>and IV falls {IV_FALLS[0]}</small></th>'
            f'<th>IV fall that erases the {MOVE_CENTS:g}¢ gain<small>points</small></th></tr>')
    body = []
    for r in rows(kind):
        near = r["gap"] <= 6   # delta 0.5 sits a few rupees from the futures price
        itm = r["itm"] and not near
        cls = "itm" if itm else "atm" if near else "otm"
        label = "in the money" if itm else "at the money" if near else "out of the money"
        wipe = "never (over 60)" if r["wipe"] is None else f'{r["wipe"]} points'
        wcls = "zero" if r["wipe"] is not None and r["wipe"] <= IV_FALLS[1] else "pos"
        body.append(
            f'<tr class="{cls}"><td class="d">{r["delta"]:.1f}</td>'
            f'<td><b>{r["k"]:.0f}</b><small>{label}, ₹{r["gap"]:.0f} from {FUTURES:.0f}</small></td>'
            f'<td>₹{r["p"]:.1f}</td><td>{rs(r["cost"])}<small>30% stop: {rs(r["stop"])}</small></td>'
            f'<td>{rs(r["per_pt"])}</td><td class="neg">−{rs(r["vega"])}</td>'
            f'{cell(r["right"])}{cell(r["right_f"][0])}{cell(r["right_f"][1])}{cell(r["wrong"])}'
            f'<td class="{wcls}">{wipe}</td></tr>')
    return f'<h2 class="{kind.lower()}">{word}</h2><table>{head}{"".join(body)}</table>'


def page():
    ce, pe = rows("CE"), rows("PE")
    cents = MOVE_CENTS
    mid = lambda rs_, d: next(r for r in rs_ if r["delta"] == d)
    c5, c8, p5, p8 = mid(ce, 0.5), mid(ce, 0.8), mid(pe, 0.5), mid(pe, 0.8)
    b = [
        '<h1>MCX natural gas options: what delta and implied volatility do to a correct call</h1>',
        f'<div class="sub">Futures ₹{FUTURES:.0f} per MMBtu (about ${FUTURES / RUPEE:.2f} × {RUPEE}) &middot; {DAYS} days to expiry &middot; '
        f'IV {IV * 100:.0f}% before the report &middot; lot {LOT:,} MMBtu (mini 250: divide every rupee figure by 5)<br>'
        f'Scenario: the EIA storage report moves NYMEX gas {cents:g}¢ (≈ ₹{MOVE:.2f} per MMBtu) in your direction and implied volatility falls at the release. '
        f'Estimates from a pricing model, not MCX quotes.<br>For a directional buyer of a single CE or a single PE, never both at once.</div>',
        '<div class="cards">'
        '<div class="card"><b class="h">Delta</b>How much the option price moves when futures move ₹1. Delta 0.5 = the option earns 50 paise per ₹1 move. '
        'Higher delta = behaves more like the future itself, and costs more.</div>'
        '<div class="card"><b class="h">Implied volatility (IV)</b>How much movement the market has already priced into the option. '
        'It is high before a big report and drops once the number is out, even when the price moved your way.</div>'
        '<div class="card w"><b class="h">The tug of war</b>After a correct call, delta pays you and falling IV takes some back. '
        'The last column shows how many points of IV fall would cancel the whole gain.</div></div>',
        table("CE"), table("PE"),
        f'<div class="note">PE rows are mirror images of CE rows: a put with delta 0.8 is in the money (strike above futures), like a call with delta 0.8 (strike below). '
        f'Gains use the model price after the move, so they include gamma. "Gain per ₹1 move" is the option delta times {LOT:,}. '
        f'Time decay is left out: the hold is about 30 minutes. A red last-column cell means a {IV_FALLS[1]}-point fall or less erases the gain.</div>',
        '<div class="take"><b class="h">What the tables say</b><ul>'
        f'<li><b>At delta 0.5</b> a correct {cents:g}¢ call gains {rs(c5["right"], True)} (call) / {rs(p5["right"], True)} (put) per lot with IV unchanged, '
        f'but {rs(c5["right_f"][1], True)} / {rs(p5["right_f"][1], True)} after a {IV_FALLS[1]}-point IV fall: a correct call can still lose.</li>'
        f'<li><b>At delta 0.8</b> the same move gains {rs(c8["right"], True)} / {rs(p8["right"], True)}, and still {rs(c8["right_f"][1], True)} / {rs(p8["right_f"][1], True)} after the {IV_FALLS[1]}-point fall: '
        f'it needs {rs(c8["cost"])} per lot instead of {rs(c5["cost"])}.</li>'
        '<li><b>Higher delta</b> = more rupees per move and more protection from an IV fall, but more cash at risk per lot. '
        'Size by the rupee stop, not by the number of lots.</li>'
        '<li><b>Lower delta</b> (0.4) is cheap but needs a bigger move and is the most exposed to the IV fall per rupee paid.</li>'
        '<li>If IV is already low before the report there is little to lose. Check the strike\'s IV before 10:30 ET (20:00 IST).</li></ul></div>',
    ]
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(b)}</body></html>'


def render(html, name):
    out = HERE / name
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1560, "height": 900}, device_scale_factor=1.4)
        pg.set_content(html)
        pg.screenshot(path=str(out), full_page=True)
        browser.close()
    print("wrote", out)


if __name__ == "__main__":
    render(page(), "twdr_ng_iv_tables.png")
