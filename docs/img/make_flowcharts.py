"""Draw the two TWDR flowcharts to PNG (HTML laid out by the browser, rendered with Playwright).

    python docs/img/make_flowcharts.py        # writes docs/img/twdr_cl_flow.png and docs/img/twdr_ng_flow.png

The charts restate README.md (crude) and docs/twdr_ng.md (natural gas): when a rule changes there, change it here and rerun.
Colours: blue = done by the code, orange = you at the chart or terminal, yellow = a decision, red = stand down,
green = trade, grey = information only.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent

CSS = """
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 26px 30px 30px; width: 1240px; background: #fff; color: #1a202c; }
h1 { font-size: 27px; margin: 0 0 4px; text-align: center; }
.sub { text-align: center; font-size: 15px; color: #4a5568; margin-bottom: 12px; line-height: 1.4; }
.legend { display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; font-size: 13px; margin: 8px 0 4px; }
.legend span { padding: 3px 10px; border-radius: 12px; border: 2px solid; }
.phase { border: 2px dashed #1a202c; padding: 6px 16px; font-weight: 700; font-size: 17px; margin: 18px auto 10px; width: fit-content; background: #fff; text-align: center; }
.row { display: flex; gap: 12px; justify-content: center; align-items: stretch; }
.box { border: 2px solid; border-radius: 10px; padding: 8px 11px; font-size: 14px; line-height: 1.34; flex: 1; }
.box b.h { display: block; font-size: 14.5px; margin-bottom: 3px; }
.box .t { display: inline-block; font-size: 12px; font-weight: 700; padding: 0 7px; border-radius: 8px; background: rgba(0,0,0,.09); margin-bottom: 3px; }
.box ul { margin: 3px 0 0; padding-left: 17px; }
.box li { margin: 1px 0; }
.arrow { text-align: center; font-size: 24px; line-height: 20px; margin: 5px 0 1px; color: #1a202c; }
.cond { text-align: center; font-size: 13px; color: #2d3748; margin: 6px 0 3px; font-weight: 600; }
.auto   { background: #e6f0ff; border-color: #2b6cb0; }
.manual { background: #fff0e0; border-color: #c05621; }
.decide { background: #fff8cc; border-color: #b7791f; }
.stop   { background: #fde8e8; border-color: #c53030; }
.go     { background: #e0f6e6; border-color: #2f855a; }
.info   { background: #ececec; border-color: #718096; }
.legend .auto, .legend .manual, .legend .decide, .legend .stop, .legend .go, .legend .info { border-width: 2px; border-style: solid; }
.note { font-size: 13px; color: #4a5568; text-align: center; margin: 8px 40px 0; line-height: 1.4; }
"""

LEGEND = ('<div class="legend"><span class="auto">done by the code</span><span class="manual">you, at the chart or terminal</span>'
          '<span class="decide">decision</span><span class="stop">stand down / skip</span><span class="go">trade</span>'
          '<span class="info">information only</span></div>')


def page(body):
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{body}</body></html>'


def box(kind, head, text="", tag=None, grow=1):
    t = f'<span class="t">{tag}</span><br>' if tag else ""
    return f'<div class="box {kind}" style="flex:{grow}">{t}<b class="h">{head}</b>{text}</div>'


def row(*boxes):
    return '<div class="row">' + "".join(boxes) + "</div>"


def arrow(label=""):
    return f'<div class="arrow">&#9660;</div>' + (f'<div class="cond">{label}</div>' if label else "")


def phase(text):
    return f'<div class="phase">{text}</div>'


# --------------------------------------------------------------------------------------------- crude
def crude():
    b = []
    b.append('<h1>TWDR Tier 1: crude oil, the EIA Wednesday report</h1>')
    b.append('<div class="sub">MCX CRUDEOIL options (buyer only) &middot; release Wednesday 10:30 ET = <b>20:00 IST</b> (21:00 from 2 Nov, everything after shifts one hour)<br>'
             'Sign convention: build positive, draw negative, million barrels &middot; positive deviation = bearish (puts), negative = bullish (calls)</div>')
    b.append(LEGEND)

    b.append(phase("PHASE 1: DATA (Tuesday evening to Wednesday 19:45 IST)"))
    b.append(row(
        box("auto", "EIA consensus", "crude, gasoline, distillate<br>Tuesday evening<br><code>consensus_fetcher</code> (TradingEconomics / Investing.com race)", "Tue"),
        box("auto", "API crude", "published Tue 16:30 ET<br><code>api_monitor</code>, polls every 5 min", "Wed ~02:00 (03:00 winter)"),
        box("auto", "API gasoline and distillate", "paywalled: read from the X post ForexFactory lists<br>post chosen by time window <b>and</b> crude matching the API crude<br><code>api_products</code> retries every 5 min to 19:45<br>fallback: type them into <code>data/api_products.json</code>", "Wed 18:00"),
    ))
    b.append(arrow())
    b.append(phase("PHASE 2: PRE-FLIGHT (19:45 IST), the engine does not check these"))
    b.append(row(
        box("manual", "MCX evening session open?", "holiday: skip the night"),
        box("manual", "Option expiry more than 5 days away?", "5 days or fewer: use next month's options"),
        box("manual", "Bid-ask spread on your strike", "more than 5% of the premium: skip"),
        box("manual", "No major Iran / US headline", "19:45 to 20:10 IST: if one hits, skip"),
    ))
    b.append(arrow())
    b.append(phase("PHASE 3: THE ENGINE (19:55 start <code>eia_actuals</code> &middot; 19:59 start <code>signal_engine</code> &middot; verdict due by 20:05)"))
    b.append(row(
        box("auto", "Wait for the EIA actuals (20:00 release)", "<code>eia_actuals</code> writes crude, gasoline, distillate the moment all three are in; polls every 15 s<br>engine polls the file every 5 s, up to 15 min<br><b>after 20:05 the verdict is marked LATE</b> (you decide)<br>any failure: <b>ERROR</b> written to <code>signal.json</code> + Telegram alert", grow=1.3),
        box("auto", "Score each leg (crude, gasoline, distillate)", "<b>baseline</b> = 0.5 &times; consensus + 0.5 &times; API<br><b>deviation</b> = EIA actual &minus; baseline<br><b>net</b> = sum of the three deviations<br>missing API leg: baseline = consensus alone + warning<br>a leg &ldquo;moves&rdquo; only if |deviation| &ge; 0.1", grow=1.3),
        box("info", "API state (context)", "API trio total vs consensus trio total, gap 1.0:<br><b>aligned</b> / <b>shifted</b> / <b>divergent</b> / <b>softer</b>"),
    ))
    b.append(arrow("Decision order, first match wins"))
    b.append(row(
        box("decide", "1. Product conflict?", "crude |deviation| &ge; 2.0, opposite sign to gasoline (gasoline moving)", "Setup C"),
        box("decide", "2. Size gate", "|net deviation| &lt; 2.0 ?", "gate"),
        box("decide", "3. Trap?", "API crude and EIA crude opposite signs, |API| &ge; 4.0 and |EIA| &ge; 2.0 (actual changes); direction must match the net", "Setup B"),
        box("decide", "4. Aligned?", "crude and gasoline deviate the same way and match the net", "Setup A"),
    ))
    b.append(arrow())
    b.append(row(
        box("go", "C: fade the crude headline", "follow gasoline's direction<br>conviction standard<br>expected move about $0.50, then reversal"),
        box("stop", "NO TRADE", "net inside &plusmn;2.0 (and no conflict), or crude/gasoline do not both move, or the net points the other way"),
        box("go", "B: the Tuesday trap", "trade the EIA crude direction (squeeze / collapse)<br>conviction high"),
        box("go", "A: momentum with the surprise", "conviction <b>high</b> if distillate agrees and the API trio is on the same side, else standard"),
    ))
    b.append(arrow())
    b.append(row(
        box("auto", "Output", "<b>CALL</b> if the deviation is negative (bullish), <b>PUT</b> if positive<br>expected move by |net|: under 2.0 = $0.30-0.50 &middot; 2-5 = $0.60-1.00 &middot; 5+ = $1.20-2.00+ (WTI USD, placeholders)<br>the candle check to make, the stop side, time stop and hard exit<br>rupee context note (5-session USD/INR trend): a note, never a decision input<br>writes <code>signal.json</code> + <code>data/signals/&lt;date&gt;.json</code> and sends the <b>Telegram summary</b> (SIGNAL / LATE / NO TRADE / ERROR)"),
    ))
    b.append(arrow())
    b.append(phase("PHASE 4: 20:05 IST, YOUR CANDLE CHECK on the 20:00 to 20:05 candle (the engine reads no prices)"))
    b.append(row(
        box("manual", "Setup A", "candle closes with the surprise (above its open for calls, below for puts); enter on a pullback test of the break<br><b>stop:</b> beyond the other side of the candle", "check"),
        box("manual", "Setup B", "wait for the first candle to close in the trade direction, then enter<br><b>stop:</b> beyond the other side of the candle", "check"),
        box("manual", "Setup C", "do not chase the crude spike: trade the product direction only once it has <b>stalled</b>: close in the upper half of the range for calls (lower half for puts)<br>a close at the spike extreme = still running: skip<br><b>stop:</b> beyond the spike extreme", "check"),
    ))
    b.append(arrow("check fails, or no setup: no trade"))
    b.append(phase("PHASE 5: THE TRADE (carried over from the original runbook, not computed by the engine)"))
    b.append(row(
        box("manual", "Option selection", "front month, next month if 5 days or fewer remain<br>1 to 2 strikes in the money (&#8377;50-100), never more than 3<br><b>limit order only</b>: a missed fill costs nothing"),
        box("manual", "Position size", "lots = capital &times; 1% &divide; (premium &times; 30% &times; barrels per lot)<br>100 bbl (CRUDEOIL), 10 bbl (CRUDEOILM)<br>under 1 lot: do not trade, never round up"),
        box("manual", "Exits, whichever first", "<b>stop:</b> premium &minus;30%, or a 5-min bar closes back beyond the other side of the candle<br><b>target 1:</b> premium +40%: sell half, stop to breakeven<br><b>time stop</b> 20:35 (exit if not in profit)<br><b>hard exit</b> 22:30 (22:55 in winter)"),
    ))
    b.append(arrow())
    b.append(phase("PHASE 6: AFTER (every Wednesday, trade or not)"))
    b.append(row(
        box("manual", "Journal", "engine side is saved in <code>data/signals/</code> (consensus, API, EIA, baselines, deviations, setup, verdict, when the data arrived)<br>you add: candle check result, entry, exit, P&amp;L, <b>the largest futures move in the first 35 minutes</b>"),
        box("info", "Calibrate after 10 to 15 weeks", "compare that move with the net deviation, then tune the 2.0 gate, the 4.0 / 2.0 trap thresholds, the 0.5 API weight and the move bands<br>every number here is a <b>placeholder</b>, nothing is backtested"),
    ))
    b.append('<div class="note">The framework knows nothing about geopolitics: that is why you confirm on the candle before entering.</div>')
    return page("".join(b))


# --------------------------------------------------------------------------------------------- natural gas
def natural_gas():
    b = []
    b.append('<h1>TWDR-NG: natural gas, the EIA storage report</h1>')
    b.append('<div class="sub">MCX NATURALGAS futures, 1,250 MMBtu lot (tick &#8377;0.10 = &#8377;125 per lot) &middot; reference NYMEX NG (Yahoo <code>NG=F</code>)<br>'
             'Release Thursday 10:30 ET = <b>20:00 IST</b> (21:00 from 2 Nov) &middot; exceptions: <b>Fri 13 Nov</b> 10:30 ET, <b>Wed 25 Nov 12:00 ET</b> (22:30 IST) &middot; read from EIA\'s holiday schedule<br>'
             'Status: the code <b>records and notifies</b> (no automatic trade signal); the box, VWAP and entry are yours at the terminal</div>')
    b.append(LEGEND)

    b.append(phase("PHASE 0: SETUP (known in advance)"))
    b.append(row(
        box("auto", "Contract of the day", "first MCX contract with <b>more than 5 days</b> to its last trading day<br>OCT 27 Oct &middot; NOV 24 Nov &middot; DEC 28 Dec &middot; JAN 25 Jan &middot; FEB 23 Feb &middot; MAR 25 Mar (hand-kept)<br>22 Oct is a NOV trade, 19 Nov a DEC trade"),
        box("auto", "Release day and time", "Thursday 10:30 ET unless EIA's holiday schedule says otherwise (hand-kept exceptions)"),
        box("auto", "Baseline", "<b>consensus</b> from Investing.com (TradingEconomics' consensus turns into the actual after the release)<br><b>whisper number: dropped</b>"),
    ))
    b.append(arrow())
    b.append(phase("PHASE 1: PRE-REPORT, 19:30 to 19:55 IST (10:00 to 10:25 ET)"))
    b.append(row(
        box("auto", "<code>ng_recorder pre</code> at 19:55 IST", "consensus and previous (if not posted yet, the message says so: get it by hand)<br>USD/INR from yfinance and freecurrencyapi: the <b>freshest</b>, its age recorded, <b>warning if older than 30 min or age unknown</b>; never skipped<br>contract of the day &middot; <b>Telegram briefing</b> with the bands and the entry rule", grow=1.4),
        box("manual", "Your chart (NG, 5-minute)", "mark the morning high and low<br>draw the <b>pre-report box</b> from the 10:15 to 10:28 ET range<br>watch VWAP", grow=1.1),
        box("manual", "Option IV, if you trade options", "note the strike's <b>implied volatility</b> before 10:30 ET: it falls at the release<br>0.5 delta: a 10-point fall can erase a correct 3&cent; move; 0.8 delta loses far less (see <code>docs/twdr_ng.md</code>)"),
        box("info", "Context you read yourself", "weather models (GFS, ECMWF: HDD / CDD), storage against the 5-year average, production, LNG feedgas<br>not inputs of the code in v1"),
    ))
    b.append(arrow())
    b.append(phase("PHASE 2: THE RELEASE, 10:30:00 ET (20:00 IST)"))
    b.append(row(
        box("auto", "Headline deviation = actual &minus; consensus", "actual: EIA's own file (<code>ir.eia.gov/ngs/wngsr.csv</code>), whole Bcf<br><b>negative</b> (smaller injection or bigger draw than expected) = <b>BULLISH</b> &middot; <b>positive</b> = <b>BEARISH</b>"),
    ))
    b.append(arrow("size band of |deviation| (whole-Bcf data: 3.1-3.9 cannot occur, 11 and 12 are high momentum, 13+ is the shock)"))
    b.append(row(
        box("stop", "0 to 3 Bcf: noise", "<b>STAND DOWN</b><br>choppy, spread and slippage eat the edge<br>(3.1 to 3.9, buffer A: also stand down)<br>move seen: 0.5-1.5&cent; stated, but our weeks moved 2&cent; or more anyway"),
        box("go", "4 to 10 Bcf: standard", "standard setup<br>expected move <b>2 to 4.5&cent;</b> (about &#8377;1.9-4.3 per MMBtu at 96.3)<br>fixed target; exit at the nearest key daily level"),
        box("go", "10.1 to 12 Bcf: high momentum", "<b>reduce size 30-50%</b>, avoid market orders<br>the first candle may move 5&cent;+: use an intra-candle trigger<br>expected 5 to 7.5&cent;; take 50% at target, trail the rest<br>12.0 itself belongs here"),
        box("go", "Above 12 Bcf (13+): regime shock", "<b>trend-follow, trail stops, never fade</b><br>expected 8 to 15&cent;+; no fixed target<br>can run to 11:30-12:00 ET (21:00-21:30 IST)"),
    ))
    b.append(arrow())
    b.append(phase("PHASE 3: THE FIRST CANDLE, 10:30 to 10:35 ET (20:00 to 20:05 IST): your chart"))
    b.append(row(
        box("decide", "Where does the first 5-minute candle CLOSE?", "&ldquo;outside&rdquo; means the <b>close</b> is beyond the box line (the whole candle need not be)", grow=1.0),
    ))
    b.append(arrow())
    b.append(row(
        box("go", "Closes outside, in the headline direction", "check the <b>wick veto</b> on the side the price came from:<br><b>A</b> opposing wick &gt; body<br><b>B</b> opposing wick &gt; 50% of the box width<br>neither: <b>ENTER at 10:35:00 ET (20:05 IST)</b>, no retest needed<br>either: vetoed, go to the 10:45 filter"),
        box("stop", "Closes outside, AGAINST the headline", "<b>DIVERGENCE: SKIP</b>, no fade<br>(bullish headline and price breaks down, or the reverse)<br>the recorder logs &ldquo;DIVERGENCE DETECTED&rdquo;"),
        box("decide", "Closes inside the box, or wick veto", "wait for the <b>+15 minute close</b> (10:45 ET = 20:15 IST):<br>breakout in the headline direction = <b>enter</b><br>against it = <b>skip</b><br>still inside = <b>no trade today</b>"),
    ))
    b.append(arrow())
    b.append(phase("PHASE 4: THE TRADE (your terminal)"))
    b.append(row(
        box("manual", "Size", "fix the rupee risk first (0.5-1% of capital): lots = risk &divide; (stop points &times; 1,250)<br>under 1 lot: use <b>mini lots</b> (250; 4 = 1 lot) or skip; never widen the stop<br>1 point = &#8377;1,250 per lot, &#8377;250 per mini; high momentum 30-50% smaller"),
        box("manual", "Stop", "just beyond the <b>opposite side of the pre-report box</b><br>a box is typically 0.8 to 2.2&cent; wide: about &#8377;1,000-2,600 per 1,250 lot"),
        box("manual", "Time-out", "30 minutes after the release (11:00 ET = 20:30 IST): target unmet, trail to breakeven or flatten<br>shock regime: keep trailing to about 11:30-12:00 ET<br>MCX session runs to 23:30 (23:55 from 2 Nov)"),
        box("info", "Rupee", "the code converts NYMEX cents to rupees with the USD/INR it recorded (96.3 at the last check): 1&cent; = about &#8377;0.96 per MMBtu = &#8377;1,200 per lot<br>the 5-session USD/INR trend is a note, never a decision input"),
    ))
    b.append(arrow())
    b.append(phase("PHASE 5: AFTER, 90 minutes or more past the release (about 21:35 IST)"))
    b.append(row(
        box("auto", "<code>ng_recorder post</code>", "EIA's table (total, regions, <b>South Central salt</b>, 5-year average)<br>surprise, size band, the rule result (aligned / divergent / inside / wick veto, and the 10:45 fallback), the box and wick numbers<br>the move in cents after the release, the rupee context<br><b>Telegram record</b> (&ldquo;not a signal&rdquo;)"),
        box("info", "Salt cavern: information only", "recorded every week with two ratios (salt change against the prior week, and against its 5-year same-week average, over the headline deviation); a ratio of 0.5 or more would flag &ldquo;Amplified Move&rdquo;<br><b>not applied</b> in v1: it fires in about 3 of 4 weeks, so it does not discriminate yet"),
        box("manual", "Calibrate", "the saved weeks (<code>data/ng_record.json</code>) tune the size bands, the move table, the box and the wick rules<br>9 weeks so far: 1 aligned entry (a small loss), 3 skips, 5 noise weeks"),
    ))
    b.append('<div class="note">Yahoo keeps only about 60 days of 5-minute data, so each report is saved the week it happens.</div>')
    return page("".join(b))


def render(html, name):
    out = HERE / name
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page(viewport={"width": 1300, "height": 900}, device_scale_factor=1.6)
        pg.set_content(html)
        pg.screenshot(path=str(out), full_page=True)
        browser.close()
    print("wrote", out)


if __name__ == "__main__":
    render(crude(), "twdr_cl_flow.png")
    render(natural_gas(), "twdr_ng_flow.png")
