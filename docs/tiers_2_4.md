# Tiers 2 to 4: design notes (not built)

The framework has four tiers. **Tier 1** (crude, gasoline, distillate) is built: see `README.md` for the
runbook and `docs/signal_engine.md` for the spec. This document holds everything about **Tiers 2 to 4** that
was moved out of `docs/signal_engine.md` and out of the original `README.md`. Nothing here is implemented as
logic yet.

**What the code already does for these tiers (record only, no effect on any decision):**
- `eia_actuals.json` carries `cushing_change_mb`, `cushing_level_mb`, `net_imports_change_mb` and
  `refinery_util_change_pct`, filled in after the report is written (null until then).
- `api_products.json` carries `api_cushing_mb` and `api_spr_mb` when the ForexFactory post has them.
- `signal.json` copies the Cushing change, refinery change and net imports into `record_only`.

**Contents**
- Part A: the structure, roles and time horizons of the four tiers (from Inputs 2 and 10)
- Part B: the metrics checklist for Tiers 2 to 4 (from Input 9)
- Part C: the API Cushing line (from Input 8)
- Part D: the original Lite runbook rules for Tiers 2 and 3 (moved from the old `README.md`)
- Part E: data status

---

# Part A: structure, roles and horizons

### Input 2: the 4-tier structure

The engine is planned as four tiers. **Tier 1 is built first**; the others are designed for later and
should plug in without reworking Tier 1.

| Tier | Metric | Source | Role |
|---|---|---|---|
| 1. The Big Three | Commercial crude, gasoline, distillates | EIA vs API / consensus | Directional trigger and net (aggregate) surprise |
| 2. Hub and Engine | Cushing inventory, refinery utilization % | EIA sections 1 and 2 | Validates whether the crude draw was organic or localized |
| 3. Noise Filters | SPR transfers, net trade (imports / exports) | EIA balance summary | Explains erratic swings from government flows or tanker delays |
| 4. Macro Trend | 4-week implied product supplied | EIA Weekly Petroleum Status | Whether large funds sustain the breakout or fade it |

#### Data availability today

| Tier | Needed | Have it? |
|---|---|---|
| 1 | three consensus values, three actuals | Yes (`consensus.json`, `eia_actuals.json`). API exists for crude only; API gasoline and distillate are deliberately not scraped. |
| 2 | Cushing change, refinery utilization change | Yes: `cushing_change_mb`, `refinery_util_change_pct` (written by `eia_actuals`). `cushing_level_mb` is often null. No utilization level. |
| 3 | SPR change, net imports and exports | Partial: net imports (`net_imports_change_mb`, unit unverified). No SPR, no separate exports. |
| 4 | 4-week average implied product supplied | No. Not fetched. A new source and fetcher would be needed. |

#### Relation to the README

- Tier 1 replaces the README trigger (see Input 1 differences).
- Tier 2 corresponds to README veto V2 (Cushing); refinery utilization is new.
- Tier 3 corresponds to README veto V1 (flows, SPR); exports are new.
- Tier 4 is new.

#### Open questions

1. **API in Tier 1:** "EIA vs API / Consensus" is ambiguous. Is the baseline consensus, API, or a blend? API exists for crude only, so the three legs would use different baselines if API is used.
2. **Tier roles:** do Tiers 2 to 4 only validate (veto, downgrade, upgrade confidence) the Tier 1 signal, or can they change its direction? Are they scored or rule-based?
3. **Tier 1 scope:** does the first build output a decision on its own (direction plus bias strength), with later tiers refining it? Or only the Tier 1 classification, with no trade plan yet?
4. **Tier 4 source:** where does implied product supplied come from, and is a 4-week average of the weekly figure enough? Defer until Tier 4 is built.

---


### Input 10: the role and time horizon of each tier

#### Specified

| Tier | Role | How it works | Trading utility |
|---|---|---|---|
| 1 | Immediate liquidity and momentum. Used by HFT, momentum scalpers, retail. | Machines read the headline and compute the deviation in microseconds; this is the vertical spike or drop at exactly 10:30:00 ET. | Sets the boundaries of the morning's initial range. If Tier 1 is heavily misaligned with expectations, it creates the velocity to spark a trade. |
| 2 | Validation or refutation of Tier 1. Used by professional intraday and spread traders. | Decides whether the Tier 1 spike is real or a mirage. Example: crude draw but refinery utilization jumped to 96%, so the oil only moved from tanks to refinery pipes. Cushing building while national stocks draw is a local bottleneck. | Main driver of the 2 to 5 minute reversal. When Tier 2 contradicts Tier 1, human traders fade the initial algorithmic spike. |
| 3 | Isolating anomalies from true demand. Used by hedgers, physical traders, swing traders. | Strips out government and logistics. Example: a 4M bbl SPR release into commercial tanks shows as a build (political supply, not a slowdown). Fog in the Houston Ship Channel cuts imports and creates an artificial crude draw. | Protects you from staying in a trade based on bad structural data. Explains the "unexplainable" weekly swings. |
| 4 | Long-term trend bias. Used by macro funds, asset managers, position traders. | Looks at 4-week rolling product supplied (implied demand). Ignores a single week's shipping delay. | Dictates the afternoon trend. Example: Tier 1 drops oil at 10:30, but the 4-week average of gasoline demand is at a multi-year high, so funds buy the "discount" and the market rallies the rest of the day. |

| Tier | Function | Time horizon | Question it answers |
|---|---|---|---|
| 1 | Volatility trigger | 0 to 2 minutes | What is the surface surprise? |
| 2 | Directional validator | 2 to 10 minutes | Is the surprise structurally sound? |
| 3 | Fundamental cleaner | 10 to 30 minutes | Did logistics or politics distort the data? |
| 4 | Trend sustainer | 30 minutes to end of day | What is the underlying economic health? |

#### Partly answers earlier questions (to confirm)

- **Role of the tiers (Input 2 Q2, Input 9 Q1):** not vetoes. Tier 2 validates or refutes and, when it
  refutes, it becomes the reversal (a fade, so it can flip direction). Tier 3 cleans the data. Tier 4 sets
  the bias for the rest of the day (sustain or fade the breakout).
- **Mirror cases:** Tier 3 adds one: an import drop (fog) causes an artificial draw (Input 9 only had the
  import spike causing a build). Tier 4 now states both sides: strong demand turns a drop into a buying
  discount (Input 9 had the sell-the-spike side).
- **Examples add thresholds:** refinery utilization at 96% (a level); SPR release of 4M bbl.

#### What it means for our timeline (observations)

1. **The 20:05 entry lands after Tier 1's window and inside Tier 2's.** Entry at the 20:05 candle close is
   5 minutes after the print. Tier 1's spike (0 to 2 minutes) is over. Tier 2's window (2 to 10 minutes) is
   the one that drives the reversal. A Tier 1-only engine therefore trades into the period where the
   validator decides whether the move holds. The 5-minute price confirmation (the candle going the signal's
   way) can act as a stand-in validator, but it is not Tier 2 data.
2. **The README exits line up with the tier horizons.** Time stop 20:35 sits just after Tier 3's window
   (10 to 30 minutes, ending 20:30). The hard exit at 22:30 falls inside Tier 4's window. A possible reading:
   the hold is meant to run through Tiers 1 to 3, with Tier 4 only deciding whether to stay longer.
3. **Horizons describe the market's reaction, not when we know the data.** All four tiers' EIA data is
   published together at the print, so the engine can score all of them at 20:05. The horizons say when each
   tier tends to move price.
4. **Utilization level is needed**, not just the change: the example is "jumped to 96%". We only have the
   change (points), not the level.

#### Gaps

1. **Tier 3 timing is ambiguous.** "Strips away" suggests adjusting the data before use (underlying crude);
   "protects you from staying in a trade" suggests a post-entry exit signal. Which?
2. **Tier 4 needs history.** "Multi-year high" needs a multi-year series of 4-week gasoline demand; we have
   none. It also names gasoline demand, while Input 9 named total product supplied.
3. **Tier 2 reversal rule is not defined.** What counts as "contradicts Tier 1", how strong, and what trade
   follows (a fade entry after the 2 to 5 minute window?).
4. **Overlap with Setup C.** The crude-against-products conflict (Input 3) sits inside Tier 1 yet produces a
   reversal like Tier 2's. Are they one mechanism or two?
5. **User types** (HFT, hedgers, funds) are background, not rules.

(The question at the end of the pasted text, about a historical case study or a monitoring layout, is not
part of the spec and is not addressed here.)

#### Open questions

1. **Confirm the role of each tier:** Tier 2 can flip a signal into a fade; Tier 3 cleans or discounts;
   Tier 4 sets a trend bias for holds beyond the first window. Right?
2. **First build:** a Tier 1-only engine enters at 20:05, inside Tier 2's window. Accept that, using the
   5-minute price confirmation as the stand-in, or pull Tier 2 into the first build?
3. **Tier 3:** a pre-entry data adjustment, a post-entry exit trigger, or both?
4. **Time stop:** should the hold time follow the tier horizons (for example end of Tier 3, about 20:30), or
   stay at the README's 35 minutes?
5. **Tier 4 later:** which series (gasoline or total product supplied) and how much history counts as
   "multi-year high"?

---


---

# Part B: the metrics checklist

### Input 9: Tiers 2 to 4 checklist (metrics beyond the Big Three)

Tier 1 is still the first build. This input is the content for Tiers 2 to 4, recorded now so the design
leaves room for it.

#### Specified

| # | Metric (tier) | Logic as given |
|---|---|---|
| 1 | **Refinery utilization %** (Tier 2). Level as % of operable capacity, e.g. 91.5% | Run rate is the engine of the complex. A 4M crude draw with utilization up 2.5 points was refinery intake, not consumer appetite. **Tell:** crude draws while runs drop means genuinely organic demand. Low runs in turnaround (maintenance) season explain sudden crude builds. |
| 2 | **Cushing hub stocks** (Tier 2). Operational capacity roughly 70M to 80M bbl | Tank tops versus tank bottoms: extreme levels skew price regardless of national trends. A 5M national draw with Cushing up 2M: WTI often fails to rally; local delivery bottlenecks anchor front-month WTI down. |
| 3 | **SPR transfers** (Tier 3). Weekly line "Strategic Petroleum Reserve Stocks" | Headline crude is commercial stocks only. A government refill (buying commercial crude) makes an artificial commercial draw; an SPR release makes an artificial commercial build. Adjust for it. |
| 4 | **Net imports, gross imports versus gross exports** (Tier 3) | Tanker timing, Gulf weather or Houston fog swing weekly stocks by 3M to 6M bbl. After a big build, check imports: a jump (example +1.5M bpd) means a logistics anomaly, not a demand decline, and the market often fades the move. |
| 5 | **Product supplied, 4-week moving average** (Tier 4). Implied demand = refinery production + imports - stock change - exports | The final bias test: even if stocks draw across the board, a sharp drop in 4-week total product supplied (million bpd) makes institutional macro funds treat the draw as transient and sell any spike. |

#### Effect on a Tier 1 signal (reading of the text)

| Check | Condition | Reading | Effect on the signal |
|---|---|---|---|
| Utilization | crude draw and utilization up | draw is refinery intake, not demand | weaken bullish |
| Utilization | crude draw and utilization down | organic demand | strengthen bullish |
| Utilization | crude build and utilization down (maintenance) | build is explained | weaken bearish |
| Cushing | crude draw and Cushing build | hub bottleneck | weaken or cap bullish (stronger wording than Input 8: "fails to rally", "anchor down") |
| Cushing level | at tank tops or tank bottoms | extreme levels skew price | no direction or size given |
| SPR | release (commercial build inflated) / refill (draw inflated) | headline is artificial | discount the headline crude number |
| Imports | big build and imports spike | logistics anomaly | fade the build (bearish signal is not credible) |
| Product supplied | draw and sharp drop in 4-week average | draw is transient | sell spikes (weaken bullish) |

Mirror cases are not stated for most rows (for example crude build, utilization up).

#### Data availability today

| Metric | Have it? |
|---|---|
| Refinery utilization **change** (points) | Yes (`refinery_util_change_pct`, e.g. -2.8 in the 23 Sep week). No utilization **level**. |
| Cushing change | Yes. Cushing **level**: optional and often null (`cushing_level_mb`, from the EIA public table with a cross-check). Capacity is given (70M to 80M); no level is given for "tank bottoms". |
| SPR change | **No.** Not scraped. The EIA weekly report carries it; a new fetcher would be needed (source unverified). |
| Gross imports and gross exports | **No.** Only one net-imports field (unit unverified). |
| 4-week product supplied | **No.** A new source and fetcher. |

Note for the 23 Sep week in our data: crude +2.97 build with utilization -2.8 points. That is the
"low runs explain a build" case in item 1.

#### Conflicts and gaps

1. **Role of the tiers (still open from Input 2).** These read as explanations and discounts, not vetoes.
   The README treated flows and Cushing as hard vetoes. Do the tiers veto, weaken, strengthen or flip?
2. **Do Tier 3 items change the crude number itself?** "Adjust for it" for SPR (and for imports) suggests
   computing an underlying crude (as the README's `U = crude - imports x 7 + SPR`) and feeding that to
   Tier 1. That would put Tier 3 before Tier 1's deviation, not after it.
3. **No numeric thresholds:** "surged" (utilization points), "massive", "significant build", "extreme"
   Cushing levels, "jump" in imports, "drops sharply" in product supplied. The only numbers are the
   examples: crude -4M with utilization +2.5; crude -5M with Cushing +2M; imports +1.5M bpd; Cushing
   capacity 70M to 80M.
4. **Units on imports.** "+1.5M bpd" is a daily rate; over a week that is about 10.5M bbl, well above the
   quoted 3M to 6M weekly swing. Which is the unit of the check? (Also reflects on our unverified
   `net_imports_change_mb` field, and on `sources.py`, where the "net imports" entry points at a TradingEconomics
   page named `crude-oil-imports`, which may be gross imports; worth verifying.)
5. **Cushing wording differs from Input 8:** "dampen momentum, can cap a rally" versus "WTI often fails to
   rally, anchors prices down". Same direction, different strength.
6. **Net versus gross:** the check compares gross exports with gross imports, but we only have a net figure.
7. **Mirror and neutral cases** are not given (see the table).
8. **Product supplied definition:** drop sharply versus what (the prior 4-week average, year-ago level)?
   Formula given is the identity; the weekly EIA table already publishes the number.

#### Open questions

1. **Role:** veto, weaken or strengthen, or flip? Is it the same for all tiers? (Input 2 Q2.)
2. **Placement:** does Tier 3's adjustment replace the crude number before Tier 1, or act on the signal after
   it?
3. **Scope of the first build:** Tier 1 only, as agreed. Suggestion for discussion: also record the Tier 2
   and 3 values we already have (utilization change, Cushing change, net imports) in the output as
   "record only", with no effect on the decision, so we can calibrate them later from our own weeks. Agree?
4. **Thresholds** for each check, or leave them to calibration after paper trading?
5. **Imports unit and definition:** gross or net, per day or per week? Verify the current scraper field.
6. **Sources** for SPR, gross imports and exports, and 4-week product supplied, when those tiers are built.

---


---

# Part C: the API Cushing line (moved from Input 8)

**3. Cushing, Oklahoma.** The API report has a Cushing line (the NYMEX WTI delivery point). Always check it.
If total US crude draws but Cushing builds, oil is backing up at the hub: this dampens bullish momentum and
can cap a post-report rally.

Conflicts and open questions recorded at the time:

2. **Cushing is an API line item**, which is another thing `CLAUDE.md` says we deliberately do not scrape
   (paywalled, stale or dead). We do have the EIA Cushing change from `eia_actuals`, but that arrives at the
   print, not as a Tuesday preview.
3. **Cushing rule is one-sided.** "Crude draw, Cushing build" dampens bullish. Nothing for the reverse
   (crude build, Cushing draw), and "dampen" and "cap" have no numbers (a size? a target cut? a skip?).

3. **Cushing:** is the API Cushing line required? We do not have it. Should the Cushing rule wait for Tier 2
   and use the EIA Cushing change, or be part of the Tier 1 build?
6. **Cushing damping:** what does "dampen" do to the signal (cut size, cut target, skip)? And does the
   reverse case matter?

---

# Part D: original Lite runbook rules for Tiers 2 and 3 (moved from the old README)

The first version of the framework (before the Tier 1 rewrite) used a crude-only trigger (surprise of 3.0
against `E_c = (consensus + API) / 2`) and three vetoes. Two of them belong to these tiers. They are kept here
as written, for when Tiers 2 and 3 are designed. Sign convention as everywhere: build positive, draw negative.

**Data points they used**

| # | Data point | Unit | When (IST, summer) | Source |
|---|---|---|---|---|
| D11 | EIA Cushing change | M bbl | 20:00 | EIA WPSR page |
| D12 | Net crude imports change | thousand b/d | 20:00 | WPSR highlights / Table 1 |
| D13 | SPR change (a release is negative) | M bbl | 20:00 | WPSR Table 1 |

(D9 was the EIA crude change and S the crude surprise, `S = D9 - E_c`.)

**V1 Flows (Tier 3).** Underlying crude `U = D9 - (D12 x 0.007) + D13`. If `U - E_c` has flipped sign, or is
less than half of `S`, veto. Why: the build or draw came from imports, exports or the SPR, not demand.
Unit note: 0.007 converts thousand barrels per day to million barrels per week. In our pipeline
`net_imports_change_mb` looks like million barrels per day (0.369 times 7 gives the 2.58 used in the old
replay), which is unverified.

**V2 Cushing (Tier 2).** Veto if D11 moves 1.0M or more in the direction opposite to `S`. Why: WTI's delivery
hub disagrees with the headline.

**The old replay of 23 September (illustrating V1).** `E_c = +0.57`, `S = +2.40`, below 3.0, so no trade at
the trigger. V1 would also have vetoed: `U = 2.969 - 2.58 - 0.4 = -0.01`, `U - E_c = -0.58`, a flipped sign.
The market was flat afterwards.

**Dropped from the earlier full engine** (kept for history): TLS weighting, Z-score and sigma history, the
Cushing multiplier, Regimes 2 and 3 (fade and sell-the-fact), the scorecard, and OVX-based delta selection.

---

# Part E: data status

| Need | Status |
|---|---|
| Cushing change | Have (`eia_actuals`, filled after the report) |
| Cushing level | Optional and often null: EIA's page is stale at the print (`utils/eia_levels.py`); no level is given for "tank bottoms" |
| Refinery utilization change (points) | Have, Investing.com only, optional; no level |
| Net imports change | Have (TradingEconomics, unit unverified; the source page may be gross imports, not net) |
| SPR change | Not scraped. Appears in some ForexFactory API posts (`api_spr_mb`) and in EIA's release file `ir.eia.gov/wpsr/table1.csv` (unverified for timing) |
| Gross imports and exports | Not available |
| 4-week product supplied | Not available; a new source and fetcher would be needed |
| API Cushing | Captured when the ForexFactory post carries it (`api_cushing_mb`) |

The original running-list rows (API Cushing: missing, deliberately not scraped; Tier 2 to 4 data: have Cushing change, refinery change and net imports, missing the rest) are folded into the table above.
