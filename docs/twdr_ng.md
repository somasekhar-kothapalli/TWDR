# TWDR-NG: natural gas weekly storage report (scoping, nothing built)

Working document, same way of working as the crude side (`docs/signal_engine.md`): the user supplies the rules
one input at a time, each is recorded and analysed here, and no code is written until the spec is complete.
Written 2026-10-02 from what we already have in the repo, a live check of the data sources, and the free
AlgoKing guides listed in `docs/twdr_learning_resources.md` (marketing pages for a paid course: generic and
unverified).

---

## 1. The event, as known so far

| Item | Value | Source / status |
|---|---|---|
| Report | EIA Weekly Natural Gas Storage Report | EIA |
| When | Thursday 10:30 ET = **20:00 IST in US summer time, 21:00 in winter** (same clock as the crude release, one day later); a holiday can move it | EIA; AlgoKing |
| Number | Weekly change in working gas in storage, **Bcf** (billion cubic feet) | EIA |
| Baseline | Analyst consensus (Reuters, Bloomberg surveys), usually out Tuesday or Wednesday. There is **no API-style preview** | AlgoKing |
| Season | Injection (build) roughly April to October, withdrawal (draw) roughly November to March | AlgoKing |
| Surprise | actual minus consensus. A draw smaller than expected is bearish | AlgoKing |
| In-line | within about 3 to 5 Bcf: usually no clear trade. A clear surprise is 5+ Bcf | AlgoKing, unverified |
| Reaction | NG can move 3 to 8%+ in minutes; the first 15 minutes are chaotic | AlgoKing, unverified |
| Price unit | Dollars per MMBtu. One NYMEX NG contract is 10,000 MMBtu at $10 per tick (tick 0.001), micro MNG 1,000 MMBtu | AlgoKing |
| User note | A surprise or deviation moves price **3 to 5 cents per MMBtu** (30 to 50 ticks on NYMEX). The unit it is measured per is still open: see Input 1 | user, 2026-10-02 |
| Sign convention | Same as crude: build positive, draw negative | project convention |

## Input 1: instrument and reaction size

### Specified (user, 2026-10-02)

- **Instrument:** the **MCX Natural Gas OCT future** (a futures contract, not options).
- **Reaction:** **3 to 5 cents per MMBtu for the surprise / deviation.**

### MCX contract facts (from MCX pages via search; check the contract page before relying on them)

| Item | Value |
|---|---|
| Contract | Natural Gas, 1,250 MMBtu lot (a Natural Gas Mini contract also exists; its size was not confirmed here) |
| Quotation | Rupees per MMBtu |
| Tick | 10 paise (0.10 rupees), so one tick is 0.10 x 1,250 = **₹125 per lot** |
| Listing | up to 3 monthly contracts at a time; last trading day per MCX's contract launch calendar |
| Hours | 09:00 to 23:30 (23:55 in US winter time) |
| Daily price limit | 4% slab, relaxed to 6% without a cooling-off period |

Sources: [MCX Natural Gas product page](https://www.mcxindia.com/products/energy/natural-gas) and its
[options specification](https://www.mcxindia.com/docs/default-source/options/natural-gas-(1250-mmbtu)-options-january-2025-contract-onwards.pdf?sfvrsn=f77e519e_0).

**Expiry of the OCT contract.** Not confirmed. A notice about the June 2026 contract says it expired on
25 June 2026, so the October contract probably expires around **25 October 2026**; if so, the reports on 8, 15 and
22 October fall inside its life and the 29 October report would be a November-contract trade. Confirm the exact
last trading day in MCX's launch calendar. (Another search result about Natural Gas *options* showed an
October 2026 expiry of 21 October; not the futures contract.)

### What 3 to 5 cents means in rupees (illustration)

One cent per MMBtu is about 10 ticks of $0.001 on NYMEX, and the MCX price is in rupees, so the move depends on
the exchange rate. **Assuming USD/INR of 88 (an assumption, not today's rate):**

| | per MMBtu | MCX ticks (₹0.10) | per 1,250 MMBtu lot |
|---|---|---|---|
| 3 cents | ₹2.64 | about 26 | about ₹3,300 |
| 5 cents | ₹4.40 | about 44 | about ₹5,500 |

### The open reading of "for the surprise / deviation"

| Reading | Meaning | A 5 Bcf surprise would move |
|---|---|---|
| A. Per surprise, whatever its size | A typical clear surprise moves price 3 to 5 cents | 3 to 5 cents |
| B. Per Bcf of surprise | Each Bcf of deviation is worth 3 to 5 cents | 15 to 25 cents |

At an assumed gas price of $3 per MMBtu (not a given figure), A is about 1 to 1.7% and B about 5 to 8%. The
AlgoKing guide says storage surprises can move NG 3 to 8%+ in minutes, which sits closer to B but is generic and
unverified. Which reading is right changes everything downstream (the size gate, targets and stops).

### What a futures instrument changes (compared with the crude options plan)

- The loss is not capped by a premium. The crude plan's "stop at 30% of premium" and lot sizing from the premium
  do not carry over; stops and sizing would be in rupees per MMBtu and per lot, with margin as a constraint.
- Daily price limits (4%, relaxed to 6%) bound a one-day move.
- The MCX contract tracks NYMEX Henry Hub through USD/INR plus a basis. The NYMEX October contract expired in
  late September, so the NYMEX reference for a MCX October trade is the next contract; how the two line up is
  unchecked.

### Clarification and first measurement (2026-10-02)

**Clarified by the user:** the 3 to 5 cents per MMBtu is the move "or equivalent points on futures/CFDs in
**NG=F**". NG=F is Yahoo Finance's ticker for the NYMEX Henry Hub natural gas front-month future, in dollars
per MMBtu (3 to 5 cents is 30 to 50 ticks of 0.001). It still does not say per what.

**Measured on the last 9 reports** (NG=F 5-minute bars from Yahoo, cents against the 10:30 ET open; surprise =
Investing.com actual minus consensus, Bcf; a positive surprise is a bigger build, so bearish):

| Release | Surprise | Close 10:35 | Close 10:45 | Close 11:00 | Max up | Max down |
|---|---|---|---|---|---|---|
| 06 Aug | +3 | -1.6 | -2.0 | -2.4 | +0.0 | -2.8 |
| 13 Aug | +5 | -1.9 | -0.6 | -0.7 | +0.0 | -3.6 |
| 20 Aug | +1 | -0.7 | -2.3 | -2.5 | +1.0 | -3.0 |
| 27 Aug | -4 | -3.8 | -4.0 | -4.4 | +1.3 | -4.5 |
| 03 Sep | 0 | -0.1 | -3.1 | -6.4 | +1.7 | -7.2 |
| 10 Sep | +5 | +0.3 | +1.7 | +0.7 | +2.2 | -1.7 |
| 17 Sep | -5 | -1.7 | -2.2 | -1.8 | +2.1 | -2.4 |
| 24 Sep | +3 | -0.6 | +2.5 | +8.9 | +15.0 | -3.4 |
| 01 Oct | +1 | +0.0 | +0.0 | -1.7 | +1.7 | -2.1 |

- **The largest move in the first 30 minutes** was between 2.1 and 15.0 cents, **median 3.0 cents**. That fits "3 to
  5 cents" read as **the typical move after a report (reading A)**.
- **It does not fit reading B** (3 to 5 cents *per Bcf*): the two 5 Bcf surprises (13 Aug, 10 Sep) moved at most
  3.6 and 2.2 cents, and 5 Bcf at 3 to 5 cents per Bcf would be 15 to 25.
- **No clean link between the surprise and the direction yet:** the correlation of surprise against the 11:00
  move is +0.43 (the wrong sign for a build being bearish), driven by the 24 Sep outlier (+15 cents, +3 Bcf).
  Several of the biggest moves came with a surprise of 0 or 1 Bcf (3 Sep: -7 cents on a zero). With 9 reports
  this is noise, not a result.
- **Caveats:** the consensus is Investing.com's, which may not be the number the market used; Yahoo's front
  month rolls (the NYMEX October contract expired in late September), which does not affect a within-day move; the
  moves also contain whatever else was happening at 10:30 ET.
- **Yahoo keeps only about 60 days of 5-minute data**, so these prices disappear from Yahoo after early
  December. Any rule calibration needs our own recorder to keep them (the reason to build the recorder first).

---

---

## Input 2: the natural gas analytical flow (checklist, thresholds, chart-based entry)

The flow chart is saved as `docs/img/twdr_ng_flow.png` (redrawn on 2026-10-02 with every later ruling, by `docs/img/make_flowcharts.py`; the first version only had this input). Times are Eastern; the IST column is the US summer-time
clock (add one hour in winter). The release is 10:30 ET = 20:00 IST.

### Specified

| Phase | ET | IST | What |
|---|---|---|---|
| 1. Pre-report checklist | 10:00 to 10:25 | 19:30 to 19:55 | **Consensus against the whisper** (Estimize / Reuters; a higher whisper is bearish, lower bullish). **Weather models** (GFS, ECMWF): are HDDs / CDDs being added or removed. **Storage against the 5-year average:** the current surplus or deficit. **Chart:** a 5-minute Henry Hub chart with the morning high and low drawn, and a shaded box around the tight range between 10:15 and 10:28 |
| 2. The release | 10:30:00 | 20:00 | **Headline deviation = actual - consensus** (example: forecast +60 Bcf, actual +40 Bcf, deviation -20 Bcf, bullish) |
| 3. Bias and confirmation | 10:31 to 10:45 (the text says from 10:35) | 20:01 to 20:15 | Size filter below, then the bias and its confirmation |
| 4. Execution | 10:45 to 11:00 (the text says from 10:35) | 20:15 to 20:30 | Enter after a 5-minute candle closes: the price breaks out of the pre-report boundary, pulls back to retest it and holds, enter on the bounce. **Stop** just beyond the opposite side of the 10:15 to 10:28 box. **Time-out** 11:00 ET: if the target is unmet, trail the stop to break-even or flatten |

**Size filter (headline deviation, in Bcf):**

| Deviation | Reading |
|---|---|
| 0 to ±3 | in-line: **pass** (no trade, high-risk chop) |
| ±4 to ±10 | standard setup. Negative (smaller injection or bigger withdrawal than expected) is **bullish**; positive is **bearish** |
| more than ±12 | major shock; likely a structural trend day |

**Bias confirmation (from the chart):**

| | Bullish | Bearish |
|---|---|---|
| Storage | South Central Salt draw | South Central Salt build |
| Price | holds above VWAP | rejects under VWAP |
| Breakout | above the pre-report high, then a clean retest | below the pre-report low, then a clean retest |

**Ultra-trader filter:** cross-check the headline with the South Central **salt cavern** change. A mildly bearish
headline with a massive, unexpected salt withdrawal means the bearish move will probably fail: a chance to fade
the first spike. (Salt caverns are fast-cycling storage used by LNG exporters and Texas power generators.)

**Other data points named:**
- **Historical comparison shift:** does this week's number widen or narrow the 5-year surplus or deficit? A report
  that shrinks a seasonal surplus fuels an intraday rally.
- **Regional breakdown:** the South Central salt data above (an EIA table inside the release).
- **Context drivers during the week** (they decide how violent the reaction is): weather models (GWDD, HDD, CDD;
  a sudden cold or heat swing the day before magnifies the reaction); daily dry gas production (above about
  103 Bcf/d caps rallies; freeze-offs or maintenance trigger spikes); LNG feedgas flows (14 to 15 Bcf/d is max
  capacity and drains domestic supply); the monthly EIA STEO.

### What it adds, and how it relates to the crude work

- It has the same shape as the crude framework: a surprise size filter, a conflict check (here **salt against
  the headline**, there products against crude), and a confirmation before entry. The salt cavern rule is the
  natural analogue of crude's Setup C.
- Unlike crude (data-only engine, candle check by hand), this flow is **mostly chart-based**: the box, VWAP and
  the breakout and retest cannot be computed from the report. What can be automated is the headline deviation,
  the size bucket, the 5-year context and the salt cavern read.
- It also supplies the missing exit: a stop at the far side of the pre-report box and an 11:00 ET time-out.

### Data it needs, against what we have

| Need | Status |
|---|---|
| Consensus, actual, previous (Bcf) | Have, Investing.com (TradingEconomics' consensus looks unusable, see section 3) |
| Whisper number (Estimize) | Not available; a subscription site, unverified whether scrapable |
| 5-year average, surplus or deficit, change in the surplus | In EIA's own report table (`ir.eia.gov/ngs/ngs.html`); not on the aggregators. Needs a new EIA fetcher; speed unmeasured |
| South Central salt change | Same EIA regional table; not on the aggregators |
| Weather model changes (GFS, ECMWF, HDD, CDD) | Not available. NOAA CPC outlooks are free but are not the model runs |
| Daily production, LNG feedgas | Not available (paid or third-party: S&P Global, NatGasWeather, LSEG) |
| EIA STEO | Monthly EIA page; not fetched |
| Pre-report box, morning high and low, VWAP | Price data. NG=F 5-minute bars exist on Yahoo (with volume), but the trade is on the MCX OCT future: its chart is the trader's |

### Tested on the last 9 reports (NG=F 5-minute bars; surprise = Investing.com actual minus consensus)

| Release | Surprise | Filter | Pre-report box width | First 5-min close outside the box | Headline bias | Same direction? |
|---|---|---|---|---|---|---|
| 06 Aug | +3 | pass | 1.7 c | 10:30 down | down | yes |
| 13 Aug | +5 | standard | 1.4 c | 10:30 down | down | yes |
| 20 Aug | +1 | pass | 0.8 c | 10:35 down | down | yes |
| 27 Aug | -4 | standard | 1.5 c | 10:30 down | up | **no** |
| 03 Sep | 0 | pass | 1.5 c | 10:35 down | none | n/a |
| 10 Sep | +5 | standard | 1.3 c | 10:40 up | down | **no** |
| 17 Sep | -5 | standard | 2.1 c | 10:30 down | up | **no** |
| 24 Sep | +3 | pass | 2.2 c | 10:40 up | down | **no** |
| 01 Oct | +1 | pass | 1.8 c | 10:50 down | down | yes |

- **Tradable weeks:** under the filter only 4 of 9 weeks are "standard" (a deviation of 4 to 10) and none is a
  major shock; 5 of 9 are passes. Of the 4 standard weeks, the first break matched the headline bias in **1**;
  across all 8 weeks with a non-zero surprise, 4 of 8. That is a coin flip, and 9 weeks is far too few to say
  anything. Seven of nine first breaks were down: this was a falling market, which the headline rule does not
  explain.
- **Box width** was 0.8 to 2.2 cents (median 1.5), small next to the median first-30-minute move of 3 cents
  found earlier. A stop at the far side of the box is therefore tight, about 1.5 cents or 15 ticks (roughly
  ₹1,650 per 1,250 MMBtu lot at an assumed USD/INR 88), and a stop-out by noise is plausible.
- Caveats: Investing.com's consensus may not be the market's; the 10:30 bar is the release bar itself, so a
  "first close outside the box" at 10:30 is not a retest entry; nothing here tests the VWAP or salt cavern
  conditions.

### Conflicts and gaps

1. **Gaps in the size filter:** nothing for 3 to 4 and for 10 to 12 Bcf; the boundaries (is 4 in?) are not set.
2. **What a major shock changes:** it "sparks a trend day", but entry, stop and target are described once for all
   sizes. Is it the same flow, a different one, or a bigger size?
3. **Phase timing differs between the chart and the text** (Phase 3 starts 10:31 or 10:35; Phase 4 starts 10:45
   or 10:35) and from AlgoKing ("wait for 10:45"). It decides the entry window in IST (20:15 or 20:05).
4. **Salt cavern rule has two roles:** on the chart it is a confirmation (a draw confirms bullish, a build
   confirms bearish); in the text it can **override and flip** a mild headline (fade). With no number for
   "massive" and no expected value (there is no consensus for a regional number), it cannot be coded. What is
   the reference: the 5-year average change, last week, or a fixed size?
5. **Consensus against the whisper:** the deviation uses consensus, and the whisper is sentiment only. How is
   the whisper used (a veto, a size change)? Where does the number come from?
6. **No profit target** (only "if the target is unmet"). The stop is the far side of the box; the exit is the
   11:00 ET time-out.
7. **Box timing:** "10:15 to 10:28" (text) against a "15m pre-report box" (chart). Minor.
8. **The context drivers have no thresholds** apart from production above 103 Bcf/d and LNG at 14 to 15 Bcf/d:
   how do they change the decision (size, skip, bias)?
9. **Chart levels are on NG=F or on MCX?** The trade is the MCX OCT future, whose chart differs from Henry Hub
   (different session hours, thinner trading, the USD/INR factor).

### Open questions

1. Settle the size filter: boundaries and the 3 to 4 and 10 to 12 gaps, and what ±12 and over changes.
2. Which parts must the code do and which are yours at the terminal? Suggestion: code the headline deviation,
   the size bucket, the 5-year context and the salt cavern read (data-only, as for crude); you do the box,
   VWAP, breakout and retest and the entry by hand.
3. Define the salt cavern rule (reference, size, confirm against override), or leave it manual.
4. Entry window: 10:35 or 10:45 ET start (20:05 or 20:15 IST)?
5. How is the whisper obtained and used, or is it dropped?
6. Targets and exits: a profit target, and is 11:00 ET (20:30 IST) the hard time-out?
7. Are weather, production and LNG feedgas to be inputs of the decision or only context you read yourself?

---

## Input 3: how the MCX contract relates to Henry Hub, and the rupee

### Specified (user, with six reference pages, now in the reading list)

MCX Natural Gas is a rupee-denominated reflection of NYMEX Henry Hub. Trading the report on MCX means watching
two variables at once:
- **The commodity (NYMEX):** US weather models, LNG feedgas flows and the weekly EIA report. A bullish surprise
  buys NYMEX and lifts MCX.
- **The currency (USD/INR):** *multiplier effect:* NYMEX up and the rupee weaker (USD/INR up) amplifies the MCX
  rise; *cushion effect:* NYMEX down but the rupee much weaker softens the MCX fall.

### What the pages add (broker and educational pages; check against MCX before relying on them)

| Fact | Detail |
|---|---|
| Pricing chain | Henry Hub (USD/MMBtu) -> USD/INR -> MCX (₹/MMBtu) |
| Settlement | Cash-settled, no delivery. At expiry MCX settles on the NYMEX **front-month** settlement converted at the latest RBI USD/INR reference rate (Ventura) |
| Lots | 1,250 MMBtu; Mini 250 MMBtu (two sources; earlier unconfirmed) |
| Tick | ₹0.10, so ₹125 per standard lot (₹25 per mini lot) |
| Hours | 09:00 to 23:30 IST in summer: the 20:00 IST report is inside the session |
| Expiry | The 25th of the delivery month (Zerodha Varsity, an older chapter; a June 2026 contract expired on 25 June). So **the OCT contract probably expires about 25 October 2026**; still to confirm in MCX's calendar |
| Margin | Rises with volatility (Mastertrust). An old Varsity example showed about 15% overnight and 7% intraday; current figures come from the broker |
| Implied USD/INR | Ventura's example, MCX about ₹307 to 309 against Henry Hub about $3.28, implies **about ₹94 to 95 per dollar** (page date not stated; this replaces the 88 assumed earlier) |
| Tracking | A cold-weather episode: MCX +17% while NYMEX +16% (Investing.com); Mastertrust says a US move "shows up almost immediately" on MCX |

**This answers two earlier questions.** *Which NYMEX contract does the MCX October contract follow?* The NYMEX
front month: that is NG=F on Yahoo (the November contract now that the NYMEX October contract has expired), so
NG=F is the right reference. *How does it line up?* Through USD/INR, per the pricing chain above, plus small
deviations the pages mention but do not size.

### What the rupee does inside the report window (arithmetic, illustrative)

The reaction measured earlier is in NYMEX cents. The MCX move is that times the rate, plus the price times any
rate change. At the implied ₹94.5 per dollar and a gas price of $3.28 (₹310):

| | per MMBtu | MCX ticks (₹0.10) | per standard lot | per mini lot |
|---|---|---|---|---|
| A 3-cent NYMEX move | ₹2.84 | 28 | about ₹3,500 | about ₹700 |
| A 5-cent NYMEX move | ₹4.73 | 47 | about ₹5,900 | about ₹1,200 |
| The pre-report box stop (about 1.5 cents) | ₹1.42 | 14 | about ₹1,800 | about ₹350 |

- A USD/INR change of 0.1% moves the MCX price about ₹0.31, equal to about **0.33 cents** of NYMEX; 0.3% is
  about 1 cent. Against a 3-to-5-cent report move that is second-order if the rate moves little in 30 minutes
  (a typical size for that window was not measured), but it is not nothing, and over a day it matters.
- So the multiplier and cushion effects are real but small inside the first 30 minutes; they matter more for
  holding longer, and for converting a NYMEX target into an MCX target.

### Conflicts and gaps

1. **The pages are secondary** and several give no date; the 94 to 95 rate is an inference from one example.
2. **No source yet for USD/INR** at the time of the trade, and no figure for how far MCX deviates from
   NYMEX x USD/INR in practice (the pages say "minor").
3. **MCX versus NYMEX trading hours and liquidity at 20:00 IST:** NYMEX is in its report window; MCX liquidity
   at that hour and its bid-ask are unmeasured. The earlier crude work required a spread check.
4. **Two lot sizes:** 1,250 or 250 MMBtu changes the rupee risk by five times.
5. **Margin:** no current figure; it decides how many lots are possible.

### Open questions

1. Where does the USD/INR come from (RBI reference rate once a day, or a live quote), and is converting NYMEX
   cents to MCX rupees something the code should do, or do you read MCX directly?
2. Which lot do you trade (1,250 or the 250 mini)?
3. Current margin per lot at your broker, and your rupee loss limit per trade.
4. Confirm the OCT contract's last trading day (probably about 25 Oct) and when you roll to NOV.
5. Will the code ever need MCX prices (a feed or a hand-kept file), or only NYMEX?

### Answers received (2026-10-02)

| # | Answer | Effect |
|---|---|---|
| 1 | USD/INR from **yfinance** (`INR=X`), **freecurrencyapi** as the fallback; the code converts NYMEX cents to MCX rupees | See the check below |
| 2 | **1,250 MMBtu** lot | Rupee risk is for the standard lot |
| 3 | not answered (current margin per lot, rupee loss limit per trade) | still open |
| 4 | **OCT expires 27 Oct 2026; NOV expires 24 Nov 2026** | Contract calendar below |
| 5 | **MCX price feed out of scope for now** | The code works in NYMEX (NG=F) space plus the rate; the box, stop and entry on the MCX chart are the trader's |

**The exchange-rate sources, checked today:**

| Source | Result | Notes |
|---|---|---|
| yfinance `INR=X` | 96.30 (5-minute bars; the latest bar was hours old when checked) | Free; how fresh it is at 20:00 IST is not measured. Same library as the other Yahoo data |
| freecurrencyapi (`FREECURRENCYAPI_KEY` is in `.env`) | 96.225, HTTP 200 | Quota and update frequency of the free plan not checked; the response has no timestamp |

- The two differ by about 0.08%, roughly 0.27 cent of NYMEX. Fine for converting a target, noticeable if used to
  judge a 3-cent move.
- **The rate is about 96.3, not the 94.5 inferred from the Ventura page.** At 96.3: 3 cents = ₹2.89 per MMBtu
  (29 ticks, about ₹3,600 per 1,250 lot); 5 cents = ₹4.82 (48 ticks, about ₹6,000); the 1.5-cent box stop = ₹1.44
  (14 ticks, about ₹1,800).

**Contract calendar** (calendar days from the report to the expiry; the EIA report is Thursday):

| Report | Contract | Days to its expiry |
|---|---|---|
| 8 Oct | OCT (27 Oct) | 19 |
| 15 Oct | OCT | 12 |
| 22 Oct | OCT | **5** |
| 29 Oct | NOV (OCT expired 27 Oct) | 26 |
| 5 Nov | NOV (24 Nov) | 19 |
| 12 Nov | NOV | 12 |
| 19 Nov | NOV | **5** |
| 25 or 26 Nov (Thanksgiving week; EIA usually moves it to Wednesday, verify) | DEC (NOV expired 24 Nov) | after expiry |

- The user's dates (27 Oct, 24 Nov) differ from the "25th" rule seen on an older page, so the exchange calendar
  governs, not the rule.
- Two reports (22 Oct, 19 Nov) fall exactly 5 days before expiry, the boundary of the crude rule ("5 days or
  fewer: use the next month").

**New open questions**
1. **Roll rule:** trade the next month when 5 days or fewer remain (so NOV on 22 Oct and DEC on 19 Nov), or stay in
   the expiring contract until later? Liquidity usually moves to the next month before expiry.
2. **Which rate and when:** one reading at the start of the run (say 19:55 IST) or a live one? How old may a
   yfinance rate be before the fallback is used?
3. **freecurrencyapi:** confirm its quota and how often the free plan updates.
4. Margin per 1,250 lot and the rupee loss limit per trade (still unanswered).

---

### Further facts from the added references (2026-10-02)

- **EIA STEO (September edition, next 6 Oct 2026):** natural gas inventories are forecast at 3,969 Bcf on 31 Oct 2026
  (end of the injection season), **5% above the 5-year average**. A surplus is the case the AlgoKing guide says
  damps bullish surprises; it is relevant to the "storage against the 5-year average" context in Input 2.
- **MCX hours (ICICI Direct):** the evening close is 23:30 IST during US daylight saving time and 23:55 otherwise;
  US DST ends on Sunday 1 Nov 2026, so from Monday 2 Nov the close is 23:55 and the report moves to 21:00 IST.
  The 11:00 ET time-out is 20:30 IST now and 21:30 IST after the change; both are inside the session.
- The CME introduction course, the Switch Markets CFD guide and the ICICI natural gas primer were added to the
  reading list; none gave rules that change this scoping.

---

## Input 4: the size filter, boundary by boundary (answers question 2)

To avoid a clash with the crude framework's Tiers 1 to 4, these are called **size bands** here.

### Specified

Deviation = |actual - consensus| in Bcf.

| Band | Deviation | Flow profile | What to do |
|---|---|---|---|
| Noise | 0.0 to 3.0 | tight spread, a 5 to 10 second flicker, mean reversion | Do not trade |
| Buffer A | 3.1 to 3.9 | modest burst, lacks momentum to break the morning range | Wait for the candle close; need technical confluence. Trade only if the salt cavern shows a standalone surprise **and** price breaks and holds beyond the 15-minute box through the close of the 10:35 ET candle |
| Standard | **4.0 to 10.0** (4 is in) | breaks the pre-report range, pulls back cleanly to test | Standard setup: enter on the 5-minute retest |
| Buffer B | 10.1 to 11.9 | high volume, aggressive slippage, no pause; the first 5-minute candle may move $0.05 to 0.08 | Reduce size by 30 to 50%; avoid market orders; replace the retest with an intra-candle trigger (a 1-minute flag, or a break of the 10:30 candle's extreme) |
| Regime shift | 12.0 and over | institutional repricing, one-way flow, stops cascade | Trend-follow: trail stops, **never fade**; expect the trend to run to about 11:30 to 12:00 ET (21:00 to 21:30 IST) |

What over 12 changes: balance models are invalidated (a 2 to 3 sigma outlier, per the text), forced liquidation and short covering
produce a trend day, mean-reversion exits stop applying, and the move is larger (below).

### Findings on the text

1. **The data are whole Bcf, so some bands are empty in practice.** Consensus and actual come as integers (every
   Investing.com row so far). The deviation is therefore 0, 1, 2, ..., and **Buffer A (3.1 to 3.9) cannot occur**,
   and Buffer B is only **11**. In practice: 0 to 3 noise, 4 to 10 standard, 11 buffer, 12+ shock. (A fractional
   consensus, for example a survey median, would make the buffers real.)
2. **Boundary clash with Input 5 below:** here 12.0 is the regime shift (">= 12.0"); Input 5 puts 12.0 in the
   "high momentum" bucket (10.1 to 12.0) and starts the shock above 12.0.
3. **Hold time clash:** a shock trend runs to 11:30 to 12:00 ET, but Input 2's time-out is 11:00 ET.
4. **Entry method changes by band** (5-minute retest, intra-candle trigger, trail only): three entry rules.
5. **"Standalone salt surprise" is undefined** (see Input 5 findings).
6. **"2 to 3 sigma" check:** the 9 recorded surprises have a standard deviation of about 3.6 Bcf, so 12 Bcf would
   be about 3.4 sigma. Nine weeks is far too few to trust that.
7. **Rupee figures in the text use roughly ₹83 to 84 per dollar** (for example $0.05 to 0.08 = ₹4.00 to 6.50). The
   rate is about 96.3 now, so each rupee figure is about 15% low.

---

## Input 5: the move is not fixed: a target matrix by size bucket (answers question 7)

### Specified

The 3 to 5 cents is only the historical average response to a baseline report. The target must scale with the
size of the headline deviation (a 15 Bcf miss reprices the front-month contract; large deviations trigger stop
cascades). Read the data at about 10:30:05 ET, bucket the deviation, then project:

| Bucket | Expected NYMEX move (stated) | Expected MCX move (stated) | Playbook |
|---|---|---|---|
| 0.0 to 3.0 Bcf (noise) | $0.005 to 0.015 (0.5 to 1.5 cents) | ₹0.40 to 1.20 | Stand down |
| 4.0 to 10.0 (standard) | $0.020 to 0.045 (2 to 4.5 cents) | ₹1.70 to 3.80 | Fixed targets: the 5-minute retest, exit at the nearest key daily level |
| 10.1 to 12.0 (high momentum) | $0.050 to 0.075 (5 to 7.5 cents) | ₹4.20 to 6.30 | Take 50% at the target, trail the rest |
| over 12.0 (regime shock) | $0.080 to 0.150+ (8 to 15+ cents) | ₹6.70 to 12.50+ | Pure trailing stop, no fixed target |

**Salt cavern overlay** (to place the move within its bucket): if a standard-bucket deviation is more than 60%
South Central Salt, expect the upper bound (about $0.045, ₹3.80), because salt reflects fast industrial and
power-burn demand; if a large deviation comes only from East or Midwest residential regions in a mild season,
expect the move to fall short of the bucket.

### The matrix against our recorded data (9 reports, NG=F, largest move in the first 30 minutes after 10:30 ET)

| Bucket (our weeks) | Stated move | Observed (cents) | Fits? |
|---|---|---|---|
| Standard: 13 Aug (+5), 27 Aug (-4), 10 Sep (+5), 17 Sep (-5) | 2 to 4.5 | 3.6, 4.5, 2.2, 2.4 | **Yes, all four** |
| Noise: 6 Aug (+3), 20 Aug (+1), 3 Sep (0), 24 Sep (+3), 1 Oct (+1) | 0.5 to 1.5 | 2.8, 3.0, 7.2, 15.0, 2.1 | **No, all five were larger** (at least 2.1) |
| High momentum, shock | 5 to 15+ | none occurred | untested |

- The standard-bucket projection held in every sample week. The noise projection is far too low: even small
  surprises moved price 2 cents or more within 30 minutes (and 7 and 15 cents on 3 Sep and 24 Sep), which is
  also movement unrelated to the report (weather, other flow). So "noise = stand down" may be right as a
  *rule*, but "noise = tiny move" is not what the data show.
- Caveats: "largest move in 30 minutes" is a magnitude from the open, not the directional target; 9 reports;
  Investing.com's consensus.
- **Converted at 96.3 per dollar** (not the 84 behind the stated rupees): noise ₹0.48 to 1.44; standard ₹1.93 to
  4.33 (₹2,400 to 5,400 per 1,250 lot); high momentum ₹4.82 to 7.22; shock ₹7.70 to 14.45+.

### Findings and gaps

1. **"Salt contributes more than 60% of that miss" cannot be computed as written.** The miss is the total versus
   consensus; there is no consensus for a region, so a region's share *of the miss* is undefined. What the EIA
   file gives is the salt net change and its share of the total change (in the 1 Oct week: -4 of +64). A usable
   version needs an expected salt change, for instance its 5-year average for that week; the report page links a
   history download (April 2015 onward) that could give it (unverified).
2. **No band for 3.1 to 3.9**, and the 12.0 boundary clash with Input 4.
3. **Stated moves differ slightly between the two texts** (shock lower bound $0.06 in Input 4, $0.08 here).
4. **The stated figures are unsourced assertions**; our recorder is the way to replace them with measured ones.
5. **Exits:** "the nearest key daily level" needs the chart (the trader's). Partial profit and trailing are chart
   actions too.

### What this decides

- Question 2 (size boundaries): **4 is in; 10.1 to 11.9 and 3.1 to 3.9 are buffer bands; 12 and over is a regime
  shift**, with the clashes above still to settle.
- Question 7 (expected move): **by size bucket, not fixed.** The matrix is the starting set, to be recalibrated
  from the recorder.
- Still open from the earlier list: the salt rule (3), the entry window (4), the roll rule (5), the rate
  freshness and whisper (6).

---

## Rulings on the open points (Inputs 4 and 5 follow-up, 2026-10-02)

| # | Question | Ruling |
|---|---|---|
| 1 | Is 12.0 a shock? | **12.0 is high momentum; the shock is strictly above 12.0** (12.1 or more). With whole-Bcf data: 11 and 12 are high momentum (the reduced-size band), **13 and over is the shock** |
| 2 | Salt rule | v1 records the salt net change and applies the overlay: if the headline deviation is at least 4.0 Bcf and **salt accounts for 50% or more of it, trigger "Amplified Move"** (the earlier text said 60%) |
| 3 | Entry window | **Primary entry at the 10:35 ET close (20:05 IST)**: the first post-report 5-minute candle, if it has broken out of the pre-report box and retested it. **Fallback:** if at 10:35 price is still inside the box or the candle is a long-wick whipsaw, wait for the 10:45 ET close (20:15 IST, the third candle); if there is no sustained breakout by then, **no trade that day** |
| 4 | Roll rule | **5 days or fewer to expiry: trade the next contract** (22 Oct: NOV; 19 Nov: DEC) |
| 5 | Rate staleness | USD/INR must be **no more than 5 minutes old at the release**; the answer suggests a live spot feed up to 10:29 ET |
| 6 | Whisper | **Keep it, but only as a directional amplifier**, never in the deviation (always actual minus Wall Street consensus) |

**Contract of the day** (OCT expires 27 Oct 2026, NOV 24 Nov 2026; the December expiry is not known yet):

| Report | Contract |
|---|---|
| 8 Oct, 15 Oct | OCT |
| 22 Oct (5 days before the OCT expiry) | **NOV** |
| 29 Oct, 5 Nov, 12 Nov | NOV |
| 19 Nov (5 days before the NOV expiry) | **DEC** |
| 25 or 26 Nov (Thanksgiving week) and after | DEC, until its own roll |

Each month's expiry date is hand-maintained, like the crude holiday table.

### Problems with the rulings

1. **Salt "accounts for 50% of the headline deviation" still cannot be computed.** There is no salt consensus, so
   salt has no deviation, only a net change (the 1 Oct week: -4 Bcf of a +64 total). The ruling also says "from
   recorded history" and then states a fixed 50%. A computable version needs an expected salt change; see the
   finding below. Until then the 50% rule can only be **recorded as information**, not applied.
2. **The 10:35 entry needs a breakout and a retest inside the first 5-minute candle.** A retest of the box cannot
   be seen on the 10:30 to 10:35 candle itself: it shows only that the candle closed beyond the box. In
   practice 10:35 is "first candle closed beyond the box", and the retest comes later, so the 10:45 fallback is
   probably the real retest entry. This also differs from the high-momentum band (intra-candle trigger) and from
   the standard band's retest in Input 4. The entry rules now: 10:35 close, 10:45 close, or an intra-candle
   trigger in the high-momentum band.
3. **A 5-minute-old rate is probably not obtainable with our sources.** Measured today: Yahoo's `INR=X` had its
   latest 5-minute bar about four hours old, and only 0 to 7 of 24 bars in each report window; freecurrencyapi
   gave one rate with no timestamp and an unknown update frequency. TradingView's `FX_IDC:USDINR` has no feed we
   can call. To be tested live on Thursday 8 Oct at 19:55 IST: log both sources' values and ages.
4. **The size of the error is smaller than the text implies.** A 15 to 30 paise move in USD/INR is 0.16 to 0.31%,
   about 0.5 to 1 cent of NYMEX, or ₹0.5 to 1.0 per MMBtu (₹600 to 1,250 per lot): material against a 3-cent
   target (a fifth to a third), but not "several rupees". The rate only converts a projected target; it does not
   set an entry, because the MCX price feed is out of scope.
5. **The whisper reasoning looks reversed.** The example: consensus +45, whisper +52, actual +55: against the
   consensus the miss is +10 (the standard band), against the whisper only +3. If the market already leaned to
   +52, the surprise relative to what is priced is smaller, which usually *mutes* the reaction, not amplifies
   it. We have no whisper source (Estimize needs a subscription) and no history, so neither reading can be tested;
   it stays a manual note.
6. **12.0 versus floating point:** the rule is clear (shock is above 12.0); the stated reason (inequality
   mechanics) is not evidence. With whole-Bcf data it makes 12 high momentum and 13 the shock.

### New finding: EIA publishes the history we need for the salt reference

The storage page links `https://ir.eia.gov/ngs/ngshistory.xls` (the weekly history, 760 KB) and
`ngsstats.xls` (five-year averages, maximum, minimum and year-ago), plus `cvhistory.xls`. Both fetched
fine, but they are old-format `.xls` files and the project has no reader for them (`xlrd` is not installed), so
their contents (whether they hold South Central Salt by week) are **unchecked**. If they do, the expected salt
change for a week (its five-year average weekly change) and a real "salt deviation" become computable, and
the 50% rule could be applied and calibrated.

### Questions

1. May I add `xlrd` (a small library) so the EIA history files can be read and checked for the salt series?
2. Define "salt deviation" for the 50% rule: salt's net change minus its five-year average weekly change (needs the
   history above), or something else? Until then: record only?
3. The entry: is the 10:35 entry "first candle closed beyond the box" (retest later), as in point 2?
4. Rate: accept a reading as old as the best our sources give (to be measured on 8 Oct) or hold the 5-minute rule
   and skip the rupee conversion when no fresh rate exists?
5. Whisper: leave it as a manual note, since there is no source?
6. The December contract's expiry date, for the roll rule after 19 Nov.

---

### Answers to the last two points (2026-10-02)

- **Whisper: dropped.** Not in the deviation, not as an amplifier, not recorded. (The earlier "directional amplifier"
  ruling is withdrawn; no source existed for it anyway.)
- **December contract expires 28 Dec 2026**, so the contract-of-the-day calendar now runs to the new year
  (days from the report to the expiry; the roll is at 5 days or fewer):

| Report | Contract | Days to its expiry |
|---|---|---|
| 8 Oct, 15 Oct | OCT (27 Oct) | 19, 12 |
| 22 Oct, 29 Oct | NOV (24 Nov) | 33, 26 |
| 5 Nov, 12 Nov | NOV | 19, 12 |
| 19 Nov, 25 or 26 Nov | DEC (28 Dec) | 39, 32 |
| 3 Dec, 10 Dec, 17 Dec | DEC | 25, 18, 11 |
| 24 Dec (Christmas Eve; EIA holiday timing to verify) | **JAN** (expiry not known yet) | 4 |

The January expiry is the next date to supply when the calendar is extended.

---

## Third round of rulings, and what the EIA history files show (2026-10-02)

### Symbols and tooling

- **MCX symbol `NATURALGAS`; NYMEX symbol `NG`** (Yahoo Finance calls the NYMEX front month `NG=F`, which is what the
  recorder uses).
- **`xlrd` 2.0.2 is installed and added to `requirements.txt`** (old-format `.xls` files). Both EIA history files now read.

### What the EIA history files contain (checked)

| File | Content |
|---|---|
| `ir.eia.gov/ngs/ngshistory.xls` | Sheet `html_report_history`: stocks by region by week, with **Salt, NonSalt** and Total, from 2010-01-01. Sheet `weekly_net_changes`: the weekly net change by the same regions (874 weeks to 25 Sep 2026) |
| `ir.eia.gov/ngs/ngsstats.xls` | One sheet per year (2015 to 2026): the **5-year average stocks by region including "So. Cent. Salt"** by report date, plus 5-year maximum and minimum |

- The weekly net change totals in the history match all nine recorded actuals (33, 36, 16, 15, 30, 40, 44, 53, 64 Bcf), so
  the weeks line up. A weekly **salt change history exists**, so a salt reference can be built (a prior-week
  baseline, or the same week's average over the last five years).

### Rulings received

| # | Point | Ruling |
|---|---|---|
| 1 | The 50% salt rule | `Salt Deviation Ratio = abs(salt change this week - salt change prior week) / abs(headline actual - consensus)`; at 0.50 or more, flag **Amplified Momentum**. **Information only in v1**; log the variables every Thursday to tune the threshold later |
| 2 | The 10:35 ET entry | If the 10:30 to 10:35 candle **closes completely outside the pre-report box**, enter at 10:35:00 ET (20:05:00 IST); **no separate retest** is needed (it happens inside that candle's wicks). If it closes inside the box or leaves a big fake-out wick, pause and use the 10:45 ET filter (no sustained breakout by then: no trade) |
| 3 | The rate guardrail | If no USD/INR reading under 5 minutes old exists at 10:29 ET, **use the freshest available; never skip the rupee conversion** (skipping would leave no reference for tick values, margin or targets). The evening rate moves slowly, so a 15 to 30 minute old rate is accurate enough |

### Test 1: the salt ratio on the 9 recorded weeks

Headline deviation from Investing.com's consensus; salt changes from the history file. Variant A is the ruling's
formula (prior-week baseline); variant B uses the average salt change of the same week over the previous five years
instead of the prior week.

| Release | Headline deviation | Salt change | Prior week | Ratio A | 5-yr same-week average | Ratio B |
|---|---|---|---|---|---|---|
| 6 Aug | +3 | -11 | -14 | 1.00 | -11.8 | 0.27 |
| 13 Aug | **+5** | -6 | -11 | **1.00** | -6.4 | 0.08 |
| 20 Aug | +1 | -18 | -6 | 12.00 | -8.4 | 9.60 |
| 27 Aug | **-4** | -20 | -18 | **0.50** | -9.0 | 2.75 |
| 3 Sep | 0 | -10 | -20 | undefined | -5.2 | undefined |
| 10 Sep | **+5** | -11 | -10 | **0.20** | -0.2 | 2.16 |
| 17 Sep | **-5** | -5 | -11 | **1.20** | +6.4 | 2.28 |
| 24 Sep | +3 | -5 | -5 | 0.00 | +5.8 | 3.60 |
| 1 Oct | +1 | -4 | -5 | 1.00 | +2.8 | 6.80 |

(bold: the weeks with a headline deviation of 4 or more, where the rule applies)

- **The threshold barely discriminates.** Weekly salt changes are large (5 to 20 Bcf either way) next to typical
  surprises (1 to 5 Bcf), so the ratio is usually 0.5 or more: in 3 of the 4 applicable weeks under A (13 Aug, 27 Aug,
  17 Sep) and 3 of 4 under B (a different three: 27 Aug, 10 Sep, 17 Sep), and the ratio is not even bounded by 1.
  A flag that fires about three weeks in four does not separate anything.
- **The two numbers use different baselines:** the salt change is measured against last week, the headline
  against consensus, so the ratio mixes them.
- **No price link visible:** among the 4 standard weeks, the largest 30-minute moves were 3.6, 4.5, 2.2 and 2.4 cents;
  flagged by A: 3.6, 4.5, 2.4; not flagged: 2.2. Too few weeks to say anything.
- **Consequence:** record both variants every Thursday (as ruled), apply neither in v1, and revisit the threshold and
  the definition once weeks accumulate.

### Test 2: the 10:35 entry rule on the recorded price bars

Pre-report box = high and low of the 10:15, 10:20 and 10:25 bars; entry at the close of the 10:30 bar if it closes
outside the box in the direction of the headline bias (a bigger build is bearish), standard band only; stop at the far side
of the box; exit at 11:00 ET.

| Release | Band | 10:30 candle closed | Headline bias | Rule fires? |
|---|---|---|---|---|
| 6 Aug, 20 Aug, 3 Sep, 24 Sep, 1 Oct | noise | various | | no (stand down) |
| 13 Aug (+5) | standard | outside, down | down | **yes**: short at 2.729, held to 11:00, **-1.2 cents** (best +0.1, box risk 1.4) |
| 27 Aug (-4) | standard | outside, **down** | **up** | no: price broke against the headline |
| 10 Sep (+5) | standard | inside | down | no (10:45 fallback case) |
| 17 Sep (-5) | standard | outside, **down** | **up** | no: price broke against the headline |

- **One entry in nine weeks, and it lost** (a small -1.2 cents; the price barely moved in the trade's favour). Both
  weeks where a bullish headline met a downward break would have been skipped; the rule does not say what to do with that conflict
  (the "Ultra-trader" fade idea is the nearest).
- The test says nothing about the 10:45 fallback beyond the one week it applies to, and nine weeks cannot establish
  an edge. It does show the recorder's bars are usable for exactly this kind of test.

### The rate guardrail

- Rule accepted: freshest available, never skip. Suggested addition: **record the rate's age and warn when it is over
  30 minutes** (the ruling's own accuracy window), without stopping.
- "Indian currency markets are closed in the evening, so the rate moves slowly" is an assertion; the onshore market
  closes in the afternoon but offshore quotes keep moving, and Yahoo's own bars are sparse. The age of each source is
  measured on Thursday 8 Oct at 19:55 IST, as agreed.

### Answers to the open questions

| # | Question | Status |
|---|---|---|
| xlrd | add it | **Done** |
| Salt deviation | definition | **The ratio above; recorded, not applied** |
| 10:35 entry | what it means | **First candle closed outside the box = enter; no retest** |
| Rate | no fresh rate | **Use the freshest; warn above 30 minutes (suggested)** |

---

### Expiry dates received (2026-10-02) and the extended contract calendar

| Contract | Last trading day |
|---|---|
| OCT 2026 | 27 Oct 2026 (Tue) |
| NOV 2026 | 24 Nov 2026 (Tue) |
| DEC 2026 | 28 Dec 2026 (Mon) |
| JAN 2027 | **25 Jan 2027** (Mon) |
| FEB 2027 | **23 Feb 2027** (Tue) |
| MAR 2027 | **25 Mar 2027** (Thu) |

Contract of the day for each Thursday report, by the rule "trade the next contract when 5 days or fewer remain"
(this table replaces the earlier ones):

| Report (Thursday) | Contract | Days to its expiry |
|---|---|---|
| 08 Oct 2026 | OCT | 19 |
| 15 Oct 2026 | OCT | 12 |
| 22 Oct 2026 | NOV **(roll)** | 33 |
| 29 Oct 2026 | NOV | 26 |
| 05 Nov 2026 | NOV | 19 |
| 12 Nov 2026 | NOV | 12 |
| 19 Nov 2026 | DEC **(roll)** | 39 |
| 26 Nov 2026 | DEC | 32 |
| 03 Dec 2026 | DEC | 25 |
| 10 Dec 2026 | DEC | 18 |
| 17 Dec 2026 | DEC | 11 |
| 24 Dec 2026 | JAN **(roll)** | 32 |
| 31 Dec 2026 | JAN | 25 |
| 07 Jan 2027 | JAN | 18 |
| 14 Jan 2027 | JAN | 11 |
| 21 Jan 2027 | FEB **(roll)** | 33 |
| 28 Jan 2027 | FEB | 26 |
| 04 Feb 2027 | FEB | 19 |
| 11 Feb 2027 | FEB | 12 |
| 18 Feb 2027 | MAR **(roll)** | 35 |
| 25 Feb 2027 | MAR | 28 |
| 04 Mar 2027 | MAR | 21 |
| 11 Mar 2027 | MAR | 14 |
| 18 Mar 2027 | MAR | 7 |
| 25 Mar 2027 | APR **(roll)** | expiry not given |

- 25 Mar 2027 is itself a Thursday: it is the MAR expiry day, so that report would be a April trade (the April
  expiry is the next date needed).
- The EIA report moves to Wednesday when the Thursday is a federal holiday (Thanksgiving, 26 Nov 2026, and possibly
  24 Dec, 31 Dec): the dates above are Thursdays and the real release dates are to be taken from EIA's schedule.
- Expiry dates are hand-maintained, like the crude holiday table; the April date is the next to supply.

---

### Ruling: headline against first-candle breakout = skip, no fade (2026-10-02)

When the headline bias and the direction of the first-candle breakout disagree at the 10:35 ET close, **skip the
trade. The "Ultra-trader fade" is not part of v1.**

| Headline bias (deviation of 4 or more) | First 5-minute candle (10:30 to 10:35) | V1 action |
|---|---|---|
| Bullish (smaller injection or bigger draw than expected) | closes above the box | **Enter at 10:35:00 ET** |
| Bearish (bigger injection or smaller draw) | closes below the box | **Enter at 10:35:00 ET** |
| Bullish | closes below the box | **Skip (no-trade zone)** |
| Bearish | closes above the box | **Skip (no-trade zone)** |
| either | closes inside the box, or a long-wick candle | wait for the 10:45 ET filter; no sustained breakout, or a divergence then, means no trade |

The reasons given: a fundamental headline can be pre-empted by weather already priced in (a mildly bullish number
that is "not bullish enough" gets sold hard), and the salt cavern and production numbers move price at the same
instant, so a fixed rule cannot tell a false spike from a real trend until the sub-metrics are weighed in V2.
The suggested filter is a plain check: bullish and upward breakout means long, bearish and downward breakout
means short, otherwise log "DIVERGENCE DETECTED, SKIPPING" and stand down.

**How it splits between code and the trader** (the code never sees the MCX chart): the code gives the fundamental
bias and the size band at about 20:00 IST; the trader reads the 10:30 candle against the box at 20:05 IST and
applies the table. The recorder can evaluate the breakout side afterwards from the NG=F bars, so every Thursday's
aligned, divergent or inside-the-box outcome is logged as the test of this rule.

**Check on the four standard-band weeks** (the bars are in `ng_record.json`). The explanation offered for 27 Aug and
17 Sep (weather priced in) cannot be verified from our data; what the data show is the following.

| Week | Headline | First close outside the box | V1 | Result of simply following that break, entry to 11:00 ET |
|---|---|---|---|---|
| 13 Aug | bearish | 10:30, down | **trade** | -1.2 cents (box risk 1.4) |
| 27 Aug | bullish | 10:30, down | skip | +0.6 |
| 10 Sep | bearish | 10:40, up | skip | -1.0 |
| 17 Sep | bullish | 10:30, down | skip | +0.1 |

- Skipping the three divergent weeks gave up almost nothing: following the breakout in them would have netted
  -0.3 cents, within the noise of a 1.3 to 2.1 cent box. The one trade V1 takes in these four weeks lost 1.2 cents.
- So the skip rule is safe in this sample, but the sample also shows no edge in any of the four weeks (-1.5 cents
  in total); four weeks decide nothing. The recorder is what will.

### EIA holiday release schedule, checked against EIA's page (2026-10-02)

A pasted note claimed the schedule for the holiday weeks. I read EIA's official page
(`https://ir.eia.gov/ngs/schedule.html`). Its table lists only these exceptions for 2026 (the standard release is
Thursday 10:30 a.m. ET):

| Standard Thursday | **Actual release (EIA)** | Time ET | IST (US winter time, UTC-5) | Reason |
|---|---|---|---|---|
| 12 Nov 2026 | **Friday 13 Nov 2026** | 10:30 a.m. | 21:00 | Veterans Day |
| 26 Nov 2026 | **Wednesday 25 Nov 2026** | 12:00 p.m. | **22:30** | Thanksgiving Day |

- **The note's Thanksgiving claim is right** (Wednesday 25 Nov, noon ET, 22:30 IST; MCX is open until 23:55).
- **The note missed Veterans Day:** the report moves to **Friday 13 Nov**, not Thursday 12 Nov. In the contract
  calendar that report is still NOV (11 days to the 24 Nov expiry).
- **The note's claim for 24 Dec and 31 Dec 2026 is not supported:** EIA's page lists nothing for them. Christmas
  Day (25 Dec 2026) and New Year's Day (1 Jan 2027) are Fridays, whereas the holidays that moved reports in
  the past fell on Thursdays or Wednesdays (the 2025 entries: 25 Dec 2025 moved to Monday 29 Dec, 1 Jan 2026 to
  Wednesday 31 Dec 2025). Treat 24 Dec and 31 Dec as normal Thursdays until EIA publishes otherwise; 2027 dates are not
  on the page yet.
- **The release date and time must come from this table, not from "Thursday 10:30":** the daemon's trigger has to
  read the schedule (a hand-kept list that is checked against the EIA page), because the day (Wednesday or Friday)
  and the time (noon) both change. The size filter, entry and time-out rules are measured from the release, so a
  noon release gives an entry at 12:05 ET (22:35 IST) and a time-out about 30 minutes after the release (23:00 IST).
- Other points in that note were not adopted: a May contract line "to compute spreads" (spreads are not in scope), and a
  `FX_IDC:USDINR` feed (not a source we have; the rate sources are yfinance and freecurrencyapi, with the age logged).
  The March expiry-day point agrees with the existing calendar (25 Mar 2027 is an April trade).

---

### The earlier pipeline's currency module, and the weekly recorder (2026-10-02)

**Reference:** `F:/TradeDesk/twpr/app/currency.py` (the earlier pipeline). Its point: the rupee is *context*, never a
decision input. Onshore USD/INR trades only 09:00 to 17:00 IST and the trade is held in the evening, so the
currency market is shut during the hold and the move being traded is the NYMEX move. That agrees with the rulings
(never skip the conversion; accept the freshest rate) and shows why a 5-minute-old rate is not essential.

**The same statistics for natural gas** (measured 2026-10-02, 129 daily sessions, NG=F against USD/INR):

| Measure | Earlier pipeline (WTI, 6 months) | Natural gas now |
|---|---|---|
| Mean absolute daily move: benchmark / USD/INR | 2.89% / 0.38% (7.7x) | 1.99% / 0.37% (**5.4x**) |
| Rupee's median share of the combined MCX move | 12% | **12%** |
| Combined MCX move flips sign against the benchmark | 3.2% of days | **4.7%** of days |

The rupee is a small part of an NG day (12% of the move) and rarely changes its sign. (The 5-session USD/INR
trend today is +0.53%, "sharp" by the module's scale: 95.79 to 96.30, a weakening rupee that lifts MCX against
a bearish call and with a bullish one.)

**Adapted into the repo as `app/utils/currency.py`:** the same functions (trend, direction, effect, notes), wording made
generic (NYMEX benchmark), and the NG figures above in its header. It is a note only.

**Weekly recorder built (`app/ng_recorder.py`, record only; 11 + 3 tests):**

- `python -m app.ng_recorder pre` (about 19:55 IST on release day): the consensus (Investing.com) and USD/INR from
  yfinance and freecurrencyapi, each with its value, quote time and age; the freshest is chosen and a warning is
  recorded when it is over 30 minutes old or its age is unknown.
- `python -m app.ng_recorder post` (at least 90 minutes after the release): EIA's table (`wngsr.csv`: total, salt, 5-year
  average), the salt ratio variables (both definitions, `applied: false`), the NG=F and USD/INR bars, the size
  band, the aligned / divergent / inside-the-box result (and the 10:45 close if inside), the move after the release
  in cents, and a `currency` block (5-session USD/INR trend, direction, effect against the report's bias).
- The release day and time come from `SCHEDULE_EXCEPTIONS` (EIA's holiday schedule: Friday 13 Nov and Wednesday
  25 Nov 12:00 ET in 2026), otherwise Thursday 10:30 ET. 2027 exceptions are to be added when EIA publishes them.
- Tested live on the 1 Oct report: the pre step read both rate sources (yfinance 96.30 but 272 minutes old,
  freecurrencyapi 96.225 with no timestamp: both warnings fire as designed), and the post step parsed EIA's file
  (total +64, salt -4) and recorded: surprise +1, band noise, salt ratio A 1.00 and B 6.80, 5-session rupee trend -0.24%.

---

### Complete-flow test on the last report, 1 Oct 2026 (2026-10-02, scratch record)

Run from a clean scratch record so nothing real was touched: `pre`, then `post`, then two failure paths.

| Step | Result |
|---|---|
| `pre` | 16.7 s. Consensus 63 Bcf (previous 53); release 10:30 ET = 20:00 IST; USD/INR chosen yfinance 96.30, **280 minutes old, warning "older than 30 minutes"**; freecurrencyapi 96.225, age unknown |
| `post` | 3.8 s. EIA file parsed (total +64, salt -4, 5-year average 3,336); actual 64, surprise +1; band noise; NO TRADE (noise); salt ratio A 1.00, B 6.80, not applied; 24 NG=F bars; rupee trend -0.24% (INR strengthening, effect amplifies the bearish bias, no note) |
| Failure: no report that day (Fri 2 Oct) | exit 1, error logged, alert path called |
| Failure: EIA's file is another release (24 Sep) | exit 1, "EIA's file is for the 2026-10-01 release" |

- **The entry-rule status path was not exercised by a live run:** 1 Oct was a noise week. The rule evaluator was run
  on all nine saved reports and gives the statuses the earlier analysis found (13 Aug aligned; 27 Aug, 17 Sep
  divergent; 10 Sep inside the box; the five noise weeks no trade).
- **The rate is the weak point, as expected:** yfinance's latest USD/INR bar was hours old on both runs and only one
  USD/INR bar falls inside a report window. The daily-close trend works; the evening rate stays "freshest
  available, warn when old".
- **Timing fits the Thursday plan:** `pre` at 19:55 IST finishes by about 19:56; `post` takes seconds.
- **The crude signal now carries the same rupee block** (`currency` in `signal.json`, and a "RUPEE:" line in the
  Telegram summary when it has a note); the 30 Sep replay shows a +0.32% 5-session trend, INR weakening,
  neutral effect for a no-trade.

---

### Telegram summaries and the review of the entry logic (2026-10-02)

**Telegram (recorder, record only):** `pre` now sends, before the release, the consensus and previous, the contract of the
day (from the hand-kept expiries and the 5-day roll rule), the USD/INR reading with its age and any warning, and a
reminder of the bands and the entry rule. `post` sends a record (headed "not a signal"): actual against consensus,
the band and its note, the rule result and the 10:45 fallback if there was one, the move in cents, the salt figures
(information only) and any rupee note. Both go out only after the record is written; failures still alert as before.

**The review's three points against the code**

| Review point | State |
|---|---|
| 1. Exactly 12.0 is high momentum; shock only above 12.0 (12.1, so 13 in whole Bcf) | **Already so** (`size_band`); a test for 12.1 was added |
| 2. 10:35 entry if the first candle closes completely outside the box; wicks or a range-bound candle go to the 10:45 fallback | **Partly:** the close-outside entry was there, but the fallback result was not evaluated. **Added:** when the first candle closes inside, the +15 minute close decides (aligned: enter; divergent: skip; inside: no trade), plus the second candle's side. **Not defined, so recorded only:** the wick (upper and lower wick in cents) and whether the whole candle sits outside the box (`fully_outside`); the status still uses the close |
| 3. Divergence skips and logs a warning | **Gap fixed:** the status said "DIVERGENT: skip" but nothing was logged. Now a warning "DIVERGENCE DETECTED ... SKIP, stand down" is logged (tested) |

- The review speaks of "this script", but only text was pasted; nothing else was available to compare.
- **Open:** a measurable wick rule (for example the opposite-side wick larger than the body or than the box) and
  whether "closes completely outside" means the close or the whole candle. Until defined, the data is recorded and the
  rule uses the close.

---

### Rulings: the wick rule and "completely outside" (2026-10-02)

**"Completely outside" = the CLOSE.** The 5-minute candle must close beyond the box boundary; the whole candle does
not have to clear it (requiring that would mean entering after the market has already extended). If the 10:35 close
crosses the boundary, enter at 10:35:00 ET. (The recorder still stores `fully_outside` as information.)

**Long-wick veto of the 10:35 entry.** With the *opposing wick* being the one on the side the price came from (the
lower wick for an upward breakout, the upper wick for a downward one), the candle is vetoed if either holds:

| Rule | Condition | Meaning |
|---|---|---|
| A | opposing wick > body | the wick dominates the body: absorption, a probable fake-out |
| B | opposing wick > 50% of the pre-report box width | the move cuts back through over half the box: no structural momentum |

A veto means stand down and use the +15 minute (10:45 ET) filter. Divergence still skips whatever the wicks are,
and noise weeks stay no trade.

**Implemented in `evaluate_rule`:** the status `WICK VETO: ... wait for the 10:45 filter`, the fallback result
(aligned: enter, divergent: skip, no breakout: no trade) after a veto or an inside first candle, and the numbers
behind it (opposing wick, body, box width, rule A, rule B) in each record. 17 recorder tests cover clean, A-only,
B-only, divergent and noise cases.

**On the nine saved weeks the wick veto changes nothing:** the one aligned entry (13 Aug) had no opposing wick (0.0
cents against a 1.9 cent body), and the only candles with such wicks (27 Aug, 17 Sep) were already divergent skips.
10 Sep was inside the box and its fallback result is divergent at the 10:45 close: skip.

### Operational schedule for the live test week (6 to 8 Oct 2026)

| When (IST) | Command |
|---|---|
| Tue 6 Oct | `python -m app.consensus_fetcher` (crude consensus) |
| Wed 7 Oct about 02:00 | `python -m app.api_monitor` (API crude) |
| Wed 7 Oct 18:00 | `python -m app.api_products` (API gasoline and distillate) |
| Wed 7 Oct 19:55 / 19:59 | `python -m app.eia_actuals` / `python -m app.signal_engine` (crude) |
| Thu 8 Oct 19:55 | `python -m app.ng_recorder pre` (consensus, rate and its age, contract OCT) |
| Thu 8 Oct 20:00 | NG release: your chart check at 20:05 (the first candle's close against the box, the wick rules, divergence) |
| Thu 8 Oct 21:30 or later | `python -m app.ng_recorder post` (it refuses before release + 90 minutes) |

Things to read afterwards: the rate's age and source in the `pre` record, the crude `data_first_seen` times in
`data/signals/`, and the natural gas record for the aligned / divergent / inside outcome.

---

### Readiness check for the live validation on 8 Oct 2026 (2026-10-02)

**Complete flow on the 1 Oct report, with real Telegram:** `pre` (19.0 s) and `post` (4.8 s) both ran and both messages
were delivered (send returned True twice). Record: surprise +1 Bcf, noise band, NO TRADE (noise), salt -4.

**A bug found by probing the real next report (8 Oct) and fixed:** the consensus is **not posted yet** (Investing.com
shows none), and `pre` crashed formatting it (`TypeError`) after writing the record. Now the message says "Consensus
NOT POSTED yet: get it by hand (Reuters, Bloomberg)" and a warning is logged; `post` refuses clearly if the consensus is
still missing after the release. A test was added (18 recorder tests).

| Item | State |
|---|---|
| Recording and the two Telegram summaries | **Ready**, tested end to end |
| A tradable signal at 20:00 IST | **Not built:** the NG signal engine (read the EIA file at the release, give the band and the checklist) does not exist; the 20:05 chart check is yours |
| Scheduling | **Nothing is scheduled for TWDR.** The commands must be run by hand or scheduled (the machine must be on at 19:55 and about 21:35 IST) |
| Other scheduled tasks on this machine | Six `WBOS_*` tasks (an older project, `F:\WB-OS`, "Wednesday Barrel Operating System") are still registered: weekly on Wednesday 19:00 and 19:45, and one-off tasks at 19:50, 20:00, 20:03 and 20:06. **They are stale:** the code they call (`src.scheduler`) was removed from that project on 17 Sep, so they fail when they run (the two weekly ones failed on 30 Sep) and cannot send Telegram. They were removed by the user on 2 Oct, after this check |
| Consensus for 8 Oct | Not posted yet; check on Wednesday evening |
| USD/INR age | The yfinance reading was 292 minutes old today; the real age at 19:55 IST is measured on 8 Oct |
| EIA file at the release | `post` runs 90 minutes later, so its release-time update speed does not matter for the recorder |
| Release timing | 8 Oct is a normal Thursday 10:30 ET (20:00 IST); contract OCT (19 days to expiry) |

**Verdict:** ready to validate the **record-and-notify flow** on 8 Oct; not a live trading signal. The tradable part
stays your chart check against the box, using the bands and wick rules in the `pre` message.

---

### Sizing and instrument: lot size, delta and IV (2026-10-02, illustration, not a ruling)

**Position type.** the strategy is a directional option buyer who purchases either a single Call (CE) or a single Put (PE), but not both simultaneously. No straddles or strangles, no selling or writing options, no hedging with the opposite option. The loss is capped at the premium; spreads are a variant to be decided separately.

**Lot arithmetic.** Futures are linear: 1 rupee per MMBtu = Rs 1,250 per lot (Rs 250 per mini lot), up or down. At 96.3 a
cent is about Rs 0.96, so the standard band (2 to 4.5 cents) is about Rs 2,400-5,400 per lot (Rs 480-1,080 mini), the shock band
(8 to 15 cents) about Rs 9,600-18,000, and a 3 to 10 cent box stop Rs 3,600-12,000 per lot. An option pays delta x points x 1,250
(at the money about Rs 625 per point) and a bought option loses at most its premium.

**Sizing rule (professional practice, to confirm).** Fix the rupee risk first (0.5 to 1% of capital), then lots = risk / (stop in
points x 1,250); for a bought option, lots = risk / (premium x stop fraction x 1,250). Never widen the stop to fit a lot; if the
answer is under 1 lot, use mini lots (4 minis = 1 lot) or skip. High momentum: 30-50% smaller; shock: trail, never fade.

**IV after the release, 0.5 against 0.8 delta** (Black-76 estimate, not MCX quotes: futures Rs 300, 20 days, IV 70% to 60%):

| | 0.5 delta (at the money) | 0.8 delta (in the money, strike about 265) |
|---|---|---|
| Premium | about Rs 17.8 (Rs 22.2k per lot; strike 304) | about Rs 41 (Rs 51k per lot) |
| Delta P&L per Rs 1 | Rs 625 | Rs 1,000 |
| Vega per IV point | about Rs 350 per lot | about Rs 246 per lot |
| 10-point IV fall | -Rs 3,500 (14% of premium) | -Rs 2,460 (5% of premium) |
| 5-point IV fall | -Rs 1,750 | -Rs 1,230 |

A correct 3 cent call is about Rs 2.9 on futures. At 0.5 delta the gain (about Rs 1,850) is cancelled by a 5-point crush (+Rs 83)
and turned into a loss by a 10-point one (-Rs 1,683). At 0.8 delta the gain (about Rs 2,900) survives (+Rs 686 after a 10-point
crush, +Rs 1,769 after 5). Full tables for deltas 0.4 to 0.9, calls and puts, are in `docs/img/twdr_ng_iv_tables.png` (drawn by
`python docs/img/make_iv_tables.py`; change its PARAMETERS and rerun). The cost: twice the capital and cash risk per lot, and in-the-money MCX strikes can be illiquid.
IV is bid up before the report and falls at the release itself, not over the 30 minutes; a shock band can lift it instead.

**Consequences.** Note the option's IV before 10:30 ET (not a code input; the recorder does not read it), buy in the money or use a
debit spread when it is high, keep limit orders and a spread cap of about 5% of the premium, and compare with futures (no IV risk,
no loss cap, margin). The 30-minute time-out suits options because theta barely moves in that window. Open: capital, risk
percent, futures or options.

---

### Spec: the natural gas signal engine, `ng_signal` (draft, nothing coded, 2026-10-02)

**Purpose.** On report day, deliver within seconds of the EIA print what the code can know without a price chart: the headline
deviation, the size band, the direction, the contract, the expected move in cents and in rupees per lot, and the checklist for
the first-candle entry. Same pattern as the crude engine (`app/signal_engine.py`): data only, verdict before 20:05 IST,
Telegram summary, every failure loud. The chart steps stay yours.

**What it does not do (v1).** It does not read prices (free Yahoo data is delayed, live latency unmeasured; the 10:35 ET first
candle is judged on your chart), does not pick strikes or lots, does not apply the salt ratios (information only), and does not
use weather, production, LNG feedgas or a whisper number. Options selection stays manual until capital, risk percent and the
futures-or-options choice are given; v1 prints futures rupees per lot and the delta multiple (a 0.8-delta option earns about
0.8 of it, before the spread).

**Reuse, do not rewrite.** `app/ng_recorder.py` already has the release schedule with holiday exceptions (`release_at`), the
contract roll (`contract_for`, `EXPIRIES`, `ROLL_DAYS`), the size bands (`size_band`, `BAND_NOTE`), the EIA CSV and table parsing
(`parse_eia_csv`), the rate choice with its age warning (`choose_rate`, `currency_block`) and the Telegram helpers. `ng_signal`
imports them; the entry-rule evaluation (`evaluate_rule`) stays in the recorder, where it judges the saved bars after the fact.

**Inputs**

| Input | Source | Missing or late |
|---|---|---|
| Release day and time | `release_at()` (Thursday 10:30 ET, holiday exceptions) | unknown date is an ERROR |
| Consensus (Bcf) | the `pre` record in `data/ng_record.json`, else the Investing.com row, else `--consensus <Bcf>` typed by hand | none of the three: ERROR with a Telegram alert (a wrong baseline is worse than none) |
| Actual net change (Bcf) | `ir.eia.gov/ngs/wngsr.csv`, polled until the report for this release appears; fallback the Investing.com actual | still absent after the wait: ERROR |
| Contract of the day | `contract_for(release day)` | calendar exhausted: warn, say "add the next expiry" |
| USD/INR | the reading in the `pre` record, else a fresh `choose_rate()` | older than 30 minutes or unknown: warn in the message, never skip |

**Run.** `python -m app.ng_signal [--once] [--consensus <Bcf>] [--allow-stale]`, started about 19:59 IST on release day (after
`ng_recorder pre` at 19:55). It polls the EIA file every 5 seconds up to 15 minutes, as the crude engine does. The report is
recognised by its week-ending date (the Friday before the release); a file whose week is the old one is not the print. Stale
data is refused unless `--allow-stale`.

**Steps**
1. Contract and release time, consensus, rate (as above).
2. Wait for the actual. Record when it first appeared and from which source (`data_first_seen`, `data_source`), to measure the
   EIA file's lead over the aggregators on 8 Oct.
3. `deviation = actual - consensus`; `bias = BULLISH` when negative (smaller injection or bigger draw than expected), `BEARISH`
   when positive, none at zero. Band from `size_band(abs(deviation))`.
4. Status: noise and buffer A are **NO TRADE** (stand down); standard, high momentum and shock are **SIGNAL**; computed after the
   deadline (20:05 IST, `deadline_min` 5 as for crude) is **LATE** (you decide); any failure is **ERROR**.
5. Expected move from the band table (standard 2 to 4.5 cents, high momentum 5 to 7.5, shock 8 to 15 and more, no fixed
   target), converted with the chosen rate: `cents x rate / 100 x 1,250` rupees per lot (about 1,200 per cent at 96.3).
6. Write `data/ng_signal.json` and `data/ng_signals/<YYYY-MM-DD>.json`, then send the Telegram message.

**Message (draft, SIGNAL).**

```
TWDR-NG 08-10-2026 SIGNAL: BULLISH, standard band (OCT)
Actual 58 vs consensus 63 = -5 Bcf (EIA file, first seen 20:00:07)
Expected move 2 to 4.5 cents = Rs 2,400-5,400 per lot (USD/INR 96.3, 4 min old)
Check at 20:05 on the first 5-min candle: closes ABOVE your pre-report box
  - against the headline (closes below) = skip, no fade
  - a long opposing wick (bigger than the body, or over half the box) = wait for the 20:15 close
  - still inside = wait for the 20:15 close; inside again = no trade
Stop just beyond the opposite side of the box. Time-out 20:30 IST (11:00 ET).
Options: a 0.8-delta option earns about 80% of the futures figure, before the spread.
```

NO TRADE states the band and "stand down"; high momentum adds "reduce size 30 to 50%, no market orders"; shock adds "trend-follow,
trail stops, never fade, may run to 21:00-21:30 IST".

**Output file (`data/ng_signal.json`).** `status`, `release_date`, `release_et`, `release_ist`, `contract`, `consensus_bcf`,
`consensus_source`, `actual_bcf`, `data_source`, `data_first_seen`, `deviation_bcf`, `bias`, `band`, `expected_move_cents`
(low, high), `expected_move_rupees_per_lot`, `usdinr` (value, source, age_min, warning), `checklist` (the lines above),
`reasons`, `warnings`, `deadline_ist`, `generated_at`. The ERROR form carries the error text only.

**Tests (no network, fake sources, `python -m tests.test_ng_signal`).** The deviation sign and the bias; every band edge
(3, 3.5, 4, 10, 11, 12, 12.1, 13) to the right status; noise is NO TRADE; LATE after the deadline; consensus missing from all
three sources is ERROR; the old week's file is not accepted as the print; the manual `--consensus` override; the holiday release
time (Fri 13 Nov, Wed 25 Nov 12:00 ET); the rupee conversion; an ERROR run overwrites a stale `ng_signal.json`.

**Build order.** (1) The 8 Oct live test of the recorder, to measure the EIA file latency, the real rate age and the real option
spread at 10:35 ET. (2) `ng_signal` as above, then its tests. (3) Later, from the saved weeks: the rupee-per-band table for
options, spread and break-even fields in the recorder, and the calibration of the bands.

**Open before coding.** Capital and risk percent; futures or options for v1; the EIA CSV's update speed at 10:30 ET (unmeasured);
the entry rule has fired once in 9 weeks, so every threshold is a placeholder until the recorder has more weeks; consensus is
still not posted for 8 Oct (check Wednesday evening).

---

## 2. What already exists in the repo (checked 2026-10-02)

- `app/scraper/sources.py` has an `ng_storage` entry for both sites (TradingEconomics
  `united-states/natural-gas-stocks-change`, Investing.com `natural-gas-storage-386`); `to_mb_suffixed` keeps the
  Bcf unit as is. The shared scrapers, calendar row helpers and race pattern are reusable as they are.
- `common.py` reserves `NG_RECORD_FILE` ("natural gas storage prints and price paths; v0.2, record only"). No stage
  exists yet.
- Live fetch today, rows as `(release date IST, actual, consensus, previous)` in Bcf:

| Release | Investing: actual | Investing: consensus | Surprise | Previous | TradingEconomics: actual / consensus |
|---|---|---|---|---|---|
| 03 Sep | 30 | 30 | 0 | 15 | not listed |
| 10 Sep | 40 | 35 | +5 | 30 | not listed |
| 17 Sep | 44 | 49 | -5 | 40 | not listed |
| 24 Sep | 53 | 50 | +3 | 44 | 53 / 53 |
| 01 Oct | 64 | 63 | +1 | 53 | 64 / 64 |
| 08 Oct | pending | pending | | 64 | pending |

## 3. Findings that matter for the design

1. **TradingEconomics' consensus equals the actual after the release** (53 / 53 and 64 / 64) while Investing's
   differs. So after the fact TradingEconomics' consensus looks overwritten, or is not a real survey number.
   Investing is the only usable history here; whether TradingEconomics posts a real consensus *before* the
   print is unverified. (The crude pages do not show this: crude consensus differs from actual on both sites.)
2. **Investing returns a 403 when its pages are loaded quickly one after another.** That is why the existing
   fetchers pace their sessions; any NG fetcher must too.
3. **The surprises so far are small:** 0, +5, -5, +3, +1 Bcf. Only two of five reach the "5+ Bcf" size, so by the
   AlgoKing thresholds most weeks would be "no trade". The reaction size in cents per MMBtu per Bcf is unknown
   and is the first thing to measure.
4. **The aggregator lag problem is the same as for crude:** these sites show the actual some time after 20:00 IST.
   EIA's own pages (`ir.eia.gov/ngs/ngs.html` for gas) are the candidate for a faster source, unmeasured.

## 4. What differs from the crude framework

| Topic | Crude (TWDR-CL) | Natural gas |
|---|---|---|
| Numbers in play | three stocks (crude, gasoline, distillate) | one number: the storage change |
| Preview before the print | API (Tuesday) shifts the baseline | none; consensus is the baseline |
| Context | API state, product conflict | storage against the 5-year average, season (injection or withdrawal), weather forecasts |
| Day | Wednesday | Thursday |
| Unit and move | million barrels, USD per barrel | Bcf, USD per MMBtu |
| Instrument | MCX crude options | MCX natural gas (lot size, option availability and liquidity not checked) |

## 5. Open questions (the first inputs wanted)

1. *(Answered: the MCX Natural Gas OCT future; see Input 1.)*
2. **The rules:** please send the NG framework one input at a time, as for crude: what is the trigger (surprise
   size in Bcf; is the 3 to 5 Bcf in-line band right?), the entry timing (AlgoKing waits for 10:45 ET; crude used
   the 20:05 IST candle), setups, and exits.
3. **Baseline:** consensus from Investing.com (TradingEconomics looks unusable after the fact). Any other source,
   or a whisper number?
4. **Context:** are storage against the 5-year average and the injection or withdrawal season part of the
   rules? Is weather (HDD/CDD, forecast changes) in scope or a separate strategy?
5. **First build:** record only first (the planned `ng_recorder`: each report's prints plus the price path after
   it, to measure the cents per MMBtu reaction before any rules), or a signal engine from the start? Recording
   first is the cheaper way to learn how big the moves really are.
6. *(Partly answered: 3 to 5 cents per MMBtu "for the surprise / deviation"; see Input 1.)*
7. **Which reading of the 3 to 5 cents:** the data points to A (a typical move per report, median 3.0 cents in the
   first 30 minutes), not B (per Bcf). Confirm: is it the typical size of the move after a report in NG=F?
8. *(Answered: yfinance `INR=X` with freecurrencyapi as the fallback, the code converts; see Input 3 answers.)*
9. *(Answered: OCT expires 27 Oct 2026, NOV 24 Nov 2026; the roll rule is still open.)*
10. **Futures risk rules:** the stop in rupees per MMBtu, lot size (1,250 or the mini), and any rupee loss cap per
    trade (the crude premium-based rules do not apply).

## Proposed scope v1 (draft for confirmation, nothing coded)

### New finding: EIA publishes the whole table we need as one small CSV

`https://ir.eia.gov/ngs/wngsr.csv` (public, no key; the same release server idea as the crude lead) holds, for the
latest report, by region: stocks this week and last week, **net change**, year-ago stocks and % change, and the
**5-year average stocks and % change**, including **South Central Salt and Nonsalt**. The 1 Oct 2026 report
(week ending 25 Sep) reads, in Bcf:

| | Stocks | Net change | 5-year average | vs the average |
|---|---|---|---|---|
| Total Lower 48 | 3,415 | **+64** | 3,336 | +79 (+2.4%) |
| South Central, Salt | 213 | **-4** | 252 | -15.5% |
| South Central, Nonsalt | 834 | +9 | 822 | +1.5% |

- It matches the aggregator figure (actual +64, consensus 63). One file gives the headline, the 5-year context
  and the salt cavern change: everything the Input 2 flow reads from the report itself.
- **Unmeasured:** how fast the file updates at 10:30 ET (the crude release file was not measured either), and
  whether the page and the CSV update together. The HTML page `ngs.html` carries the same table.
- **The file has no weekly 5-year-average change**, only the stock level, so "does this week widen or narrow the
  surplus" needs last week's gap from our own record (the recorder provides it).
- In the 1 Oct week the salt cavern **drew 4 Bcf while the total built 64**: a salt draw against a build, the
  kind of divergence the Ultra-trader filter looks for. Whether 4 Bcf is "massive" is unknown: there is no
  history of salt changes yet.

### Decided so far

- Instrument: MCX Natural Gas future, standard 1,250 MMBtu lot; OCT expires 27 Oct 2026, NOV 24 Nov 2026.
- The MCX price feed is out of scope. The code works in NG=F (NYMEX) space and converts cents to rupees with
  USD/INR (yfinance `INR=X`, freecurrencyapi as fallback).
- Report: Thursday 10:30 ET = 20:00 IST in summer (21:00 from 2 Nov); typical reaction 3 to 5 cents in NG=F
  (measured median 3.0 cents in the first 30 minutes, 9 reports).
- Framework to follow: Input 2 (size filter, salt cavern cross-check, 5-year context, box-and-retest entry on
  the chart, 11:00 ET time-out).

### Proposed pieces

| # | Piece | What it does | When |
|---|---|---|---|
| 1 | **`ng_recorder`** (record only) | Backfill the last 9 reports from Yahoo now, then every Thursday: the actual, consensus, previous and surprise, the EIA table (total, salt, nonsalt, 5-year average), the NG=F 5-minute path from 30 minutes before to 60 minutes after, and USD/INR. Writes `ng_record.json` | **First, and time-sensitive:** see below |
| 2 | **`ng_signal`** (data only, like the crude engine) | Thursday about 19:59 IST: reads the EIA CSV, computes the headline deviation, the size bucket (pass, standard, shock), the 5-year context and the salt read, picks the contract of the day from the roll calendar, converts the expected 3 to 5 cents into rupees per lot, and prints your chart checklist and the 11:00 ET time-out. Telegram summary, ERROR on failure | After the rules are settled |
| 3 | **Not in v1** | MCX price feed; the box, VWAP, breakout and retest (yours, at the terminal); weather, production and LNG feedgas; the whisper number; options | |

**Why the recorder comes first and cannot wait long:** Yahoo keeps only about 60 days of 5-minute data. Today the
6 August report is still inside the window; it drops out around **5 October**, the 13 August one around 12
October, and so on. The backfill saves the nine reports still available; each later week is lost unless recorded.
It also gives the numbers every rule here needs: how far price moves per Bcf of surprise, how big a salt draw is
"massive", and how wide the box really is.

### Recorder backfill: done 2026-10-02 (`python -m app.ng_recorder`)

- Saved the 9 reports available from Yahoo (6 Aug to 1 Oct 2026) into `data/ng_record.json`: actual, consensus
  (Investing.com), previous, surprise, and for each the NG=F 5-minute bars from 10:00 to 11:55 ET (24 bars each) and
  the USD/INR bars. A rerun never replaces saved bars with fewer.
- **USD/INR 5-minute bars on Yahoo are sparse in that window: 0 to 7 of 24 per report.** The rate during a report
  window cannot be rebuilt from Yahoo; a single reading at run time is what is practical (supports question 5).
- The weekly Thursday recorder, the EIA table (salt, 5-year average) and the surplus history are not built yet.

### Decisions needed to finalise piece 2

1. **Size filter:** the boundaries (is 4 in?), the 3 to 4 and 10 to 12 gaps, and what over 12 changes.
2. **Salt cavern rule:** suggestion: record the salt change only in v1 and set the "massive" threshold from the
   recorded history, instead of guessing one now.
3. **Entry window:** the 10:35 or the 10:45 ET start (20:05 or 20:15 IST).
4. **Roll rule:** the next contract when 5 days or fewer remain (22 Oct and 19 Nov are exactly 5)?
5. **Rate freshness:** one reading near the start, and the maximum age before the fallback.
6. **Whisper:** dropped, unless you have a source.
7. **Expected move in rupees:** a fixed 3 to 5 cents, or by size bucket once the recorder has data?

---

## 6. Decision log

| Date | Decision |
|---|---|
| 2026-10-02 | Scoping document started. Nothing decided. |
| 2026-10-02 | Input 1: instrument is the MCX Natural Gas OCT future; reaction 3 to 5 cents per MMBtu per surprise or deviation (unit still to be fixed). |
| 2026-10-02 | Clarified: 3 to 5 cents per MMBtu is measured in NG=F (NYMEX front month). First measurement on 9 reports: median largest 30-minute excursion 3.0 cents (range 2.1 to 15.0), supporting reading A (per report) over B (per Bcf); surprise-to-direction link not visible in 9 samples. |
| 2026-10-02 | Input 2: the natural gas analytical flow recorded (phases, size filter 0-3 pass / 4-10 standard / over 12 shock, salt cavern cross-check, box-and-retest entry, 11:00 ET time-out). Tested on 9 reports: 4 of 9 weeks tradable, first break matched the headline bias in 1 of 4. Nothing decided. |
| 2026-10-02 | Input 3: MCX Natural Gas follows NYMEX front month through USD/INR (about 94 to 95 implied); NG=F is the right NYMEX reference; lots 1,250 and mini 250, tick Rs 0.10; OCT expiry probably about 25 Oct. Six reference pages added to the reading list. Rupee effect is second-order in the first 30 minutes (0.1% rate move = about 0.33 cent). Nothing decided. |
| 2026-10-02 | Input 3 answers: USD/INR from yfinance (INR=X, 96.30 checked) with freecurrencyapi fallback (96.225 checked), code converts NYMEX cents to rupees; lot 1,250; OCT expires 27 Oct 2026 and NOV 24 Nov 2026; MCX price feed out of scope for now. Open: roll rule, margin and loss limit, rate freshness. |
| 2026-10-02 | Five more references added to the reading list (CME course already listed; STEO main page; Switch Markets; two ICICI Direct pages). Notes: STEO storage forecast 5% above the 5-year average; MCX evening close 23:30 in US DST, 23:55 from 2 Nov 2026. |
| 2026-10-02 | Found `ir.eia.gov/ngs/wngsr.csv` (headline, salt, 5-year average in one file). Drafted scope v1: recorder first (backfill before Yahoo drops the oldest reports, about 5 Oct), then a data-only Thursday signal; chart steps stay manual. Awaiting confirmation. |
| 2026-10-02 | Backfill done (9 reports saved by `app/ng_recorder.py`). Input 4 (size bands: 4 is in, buffers, 12+ shock) and Input 5 (dynamic move matrix by bucket) recorded. Against the 9 weeks: the standard-bucket move (2 to 4.5 cents) held in all 4 weeks, the noise-bucket move (0.5 to 1.5) failed in all 5. Whole-Bcf data make Buffer A empty and Buffer B just 11. Salt overlay as written is not computable. |
| 2026-10-02 | Rulings: 12.0 is high momentum, shock above 12.0; salt overlay at 50% of the headline (recorded only until a salt reference exists); entry 10:35 ET primary, 10:45 fallback, else no trade; roll at 5 days or fewer (22 Oct NOV, 19 Nov DEC); USD/INR at most 5 minutes old (probably not obtainable, to test 8 Oct); whisper kept as a directional amplifier, not in the deviation. EIA history .xls files found (unread: needs xlrd). |
| 2026-10-02 | Whisper dropped entirely. December contract expires 28 Dec 2026; contract calendar extended (24 Dec rolls to JAN, expiry still needed). |
| 2026-10-02 | Third round: symbols NATURALGAS (MCX) and NG (NYMEX); xlrd installed, EIA history files read (weekly salt series from 2010, 5-year averages incl. salt). Ruled: salt ratio recorded only; 10:35 entry = first candle closes outside the box, no retest; use the freshest USD/INR, never skip. Tested on 9 weeks: the salt ratio fires in 3 of 4 applicable weeks (no discrimination); the entry rule fired once and lost 1.2 cents. |
| 2026-10-02 | Expiry dates: JAN 25 Jan 2027, FEB 23 Feb 2027, MAR 25 Mar 2027. Contract calendar extended to March 2027 (rolls on 22 Oct, 19 Nov, 24 Dec, 21 Jan, 18 Feb). |
| 2026-10-02 | Ruling: headline bias against first-candle breakout disagree = skip; the fade is out of v1. Check on 4 standard-band weeks: V1 takes 1 trade (-1.2 cents) and skips 3 (following the break would have netted -0.3 cents). |
| 2026-10-02 | EIA holiday schedule verified on EIA's page: Friday 13 Nov 2026 (Veterans Day) and Wednesday 25 Nov 2026 12:00 ET (Thanksgiving). 24 Dec and 31 Dec not listed (treated as normal Thursdays). Release day and time must be read from the schedule. |
| 2026-10-02 | Weekly recorder built (pre and post, record only). Currency module adapted from the earlier pipeline into app/utils/currency.py (rupee as context, never a decision input); NG replication: 5.4x volatility ratio, rupee 12% of the move, sign flip on 4.7% of days. Rate rule: freshest available, record the age, warn above 30 minutes. April expiry deferred. |
| 2026-10-02 | Complete flow tested on the 1 Oct report (pre, post, two failure paths): all as designed. Crude engine now carries the rupee context block in signal.json and the Telegram summary. |
| 2026-10-02 | Recorder now sends a pre and a post Telegram summary (record only). Review addressed: 12.1 shock boundary already correct (test added); 10:45 fallback result added; divergence warning logged; wick and whole-candle-outside recorded but not used (undefined). |
| 2026-10-02 | Wick rule ruled and built: veto if the opposing wick is bigger than the body (A) or over half the box width (B); a veto waits for the +15 minute filter. "Completely outside" = the close. No change to the nine saved weeks. Live test schedule for 6 to 8 Oct written down. |
| 2026-10-02 | Readiness check: complete flow on the 1 Oct report with real Telegram (2 messages delivered); consensus-not-posted crash found on the 8 Oct probe and fixed. Not ready for a live NG trading signal (not built); ready to validate recording and notification. TWDR has no scheduled tasks; six stale WBOS tasks (an older project) still fire near the same times but fail and send nothing. |
| 2026-10-02 | Flowcharts redrawn: natural gas chart rebuilt with every ruling (IST times and holiday releases, contract roll, rupee conversion, high-momentum band, wick veto, divergence skip, 10:45 fallback, salt as information only, whisper dropped, code versus you); a crude chart added; both used in the README. Generator: docs/img/make_flowcharts.py. |
| 2026-10-02 | Sizing and IV note added: lot arithmetic (Rs 1,250 per point per lot), risk-first sizing with mini lots, and the 0.5 against 0.8 delta IV-crush table. Illustration, no ruling; pre-report IV note added to the flowchart. |
| 2026-10-02 | Position type recorded: a directional option buyer who buys either a single CE or a single PE, never both at once (no straddle or strangle, no writing, no opposite-side hedge). The delta and IV tables are for that buyer. |
| 2026-10-02 | `ng_signal` spec drafted (data-only engine, same pattern as the crude one: reuse the recorder's schedule, roll, bands and rate; wait for the EIA file; verdict, rupees per lot and the chart checklist by 20:05 IST; no price reading, no strikes). Nothing coded; build after the 8 Oct live test. |
