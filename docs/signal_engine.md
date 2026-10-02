# Signal engine: approach, logic, reasoning

Working document. Inputs are collected one at a time; no code is written until the spec is complete.
Each input gets a section below with what was specified, how it maps to our data, and what is still open.
The earlier draft (scrapped) is summarised in `CLAUDE.md`; the Tier 1 trading runbook is `README.md`;
Tiers 2 to 4 live in `docs/tiers_2_4.md`. Input numbers below are kept stable, so a moved input is a stub.

Sign convention (unchanged): build positive, draw negative, million barrels. Negative deviation is bullish,
positive deviation is bearish.

---

## Input 1: EIA report, "Three-Legged Stool" (this is Tier 1)

### Specified

Use all three stocks, each against its own consensus: crude, gasoline, distillate.

```
crude_dev      = crude_actual      - crude_consensus
gasoline_dev   = gasoline_actual   - gasoline_consensus
distillate_dev = distillate_actual - distillate_consensus

total_dev = crude_dev + gasoline_dev + distillate_dev
```

Classification by the signs of the three deviations:

| Case | Condition | Bias | Action |
|---|---|---|---|
| Triple-negative | all three deviations < 0 | Strong BUY | Green light to buy. Upward momentum likely to continue for the next 15 to 30 minutes. |
| Triple-positive | all three deviations > 0 | Strong SELL | Green light to short. Oversupplied market, steady downward pressure. |
| Mixed | signs disagree, e.g. crude strongly negative while gasoline strongly positive | Avoid / scalp only | Do not chase the immediate breakout. Wait 3 to 5 minutes for the algorithmic chopping to end. The market almost always reverses and trades in the direction of the product deviation (gasoline / distillate), not the crude headline. |

### Reasoning (as given)

Crude is the headline, but products show demand. When all three legs agree, the move is a real supply or
demand shift and momentum persists. When crude disagrees with the products, the headline fools the first
move and the market corrects toward the products.

### Maps to our data

All inputs already exist, no new fetcher needed:

| Value | File | Field |
|---|---|---|
| crude / gasoline / distillate consensus | `data/consensus.json` | `crude_consensus_mb`, `gasoline_consensus_mb`, `distillate_consensus_mb` |
| crude / gasoline / distillate actual | `data/eia_actuals.json` | `crude_change_mb`, `gasoline_change_mb`, `distillate_change_mb` |

Consensus values are published to one decimal; actuals carry three.

### Differences from the README runbook

(The README at the time was the original Lite runbook; it has since been rewritten for Tier 1.)

| Topic | README (Lite) | This input |
|---|---|---|
| Crude baseline | `E_c = (consensus + API) / 2` | Plain consensus. Does the API blend stay for crude? Open. |
| Trigger | crude surprise at least 3.0 either way | Sign agreement of three legs. No size threshold given. |
| Gasoline | V3 veto only when opposite sign and at least half the crude surprise | A full leg: it decides the case. |
| Distillate | not used | A full leg. |
| Disagreement | NO TRADE | Wait 3 to 5 minutes, then trade the product direction (a reversal trade). The README dropped fade regimes. |
| Horizon | time stop 20:35 (35 minutes) | momentum for 15 to 30 minutes |
| Cushing, net imports, SPR (V1, V2) | vetoes | not mentioned. Kept, dropped, or secondary? Open. |

### Open questions

1. **Size:** is any non-zero sign enough, or does each leg need a minimum size? What counts as "massive" in the mixed case?
2. **Zero:** how is a deviation of exactly 0.0 treated? Neutral, blocking the triple case, or counted as agreeing?
3. **Role of `total_dev`:** it is defined but never used in the rules. Is it a strength gauge, a size filter, a tiebreaker, or just logged?
4. **Mixed sub-cases:** only crude against products is described. What about crude and gasoline agreeing while distillate disagrees, or gasoline and distillate disagreeing with each other? What is "the product direction" then: sign of gasoline + distillate, or something else?
5. **Mixed trade:** after the 3 to 5 minute wait, what is the entry rule (candle break, a close beyond a level) and the stop? Is it a scalp with a tighter target?
6. **Triple cases:** is the candle-break confirmation from the README still required, or is the triple alignment itself the entry signal?
7. **Weights:** the three legs are unweighted (plain sum, millions of barrels). Confirm that is intended: crude swings are usually larger than distillate, so crude tends to dominate the total.
8. **Data quality:** consensus is the baseline for all three legs, so a wrong or stale consensus flips signs. Should a missing or disagreeing consensus for any leg block the signal entirely?

## Input 2: the 4-tier structure

Moved to `docs/tiers_2_4.md`.

---

## Input 3: Tier 1 complete algorithm (API + EIA scoring)

Tier 1 now combines the Tuesday API print with the Wednesday EIA print. Tier 1 only: no refinery, shipping,
Cushing or SPR data.

### Specified

**Step 0, API Net** (when the API report leaks, Wed about 02:00 IST):

```
api_net = api_crude + api_gasoline + api_distillate        # plain sum of the three API changes, M bbl
```

API bias: heavily negative (example -6M) is a pre-built bullish bias, prices drift up overnight. Heavily
positive (example +5M) is a pre-built bearish bias.

**Step 1, EIA Net Deviancy** (at the print): identical to Input 1's `total_dev`:

```
eia_net_dev = (crude - crude_cons) + (gasoline - gasoline_cons) + (distillate - distillate_cons)
```

**Step 2, API vs EIA reality check:** compare the EIA actuals directly with the API numbers, to see whether
the overnight positioning was right or a trap.

**Setups**

| Setup | Condition | Bias | Execution |
|---|---|---|---|
| A. Unified Trend (strongest) | EIA deviancy deeply negative (draws across the board) AND EIA confirms the bullish API print | Strong bullish, long | Buy the first minor 1-minute pullback. Algorithms chase for 15 to 30 minutes. Mirror for bearish (cheat sheet row 4). |
| B. Rubber-Band Reversal (trap) | API printed a massive build (prices fell overnight), EIA prints a massive draw against consensus | Aggressive bullish, short squeeze | Enter long right after the first 1-minute candle closes green. Mirror for a bear trap. |
| C. Product Conflict (fake-out fade) | Crude headline massive draw, gasoline and distillate unexpected builds | Initial bullish spike, then bearish reversal | Do not buy the spike. Wait 60 to 90 seconds for it to stall, then short. |

**Expected move (Tier 1 scale rule)**, from the size of `eia_net_dev`:

| Net surprise | Expected move (USD/bbl) | Note |
|---|---|---|
| 0 to 2M | 0.30 to 0.50 | quiet, choppy; scale out quickly |
| 2M to 5M | 0.60 to 1.00 | solid, clean push |
| over 5M | 1.20 to 2.00+ | volatile structural trend day |

**Cheat sheet**

| API showed | EIA shows | Net deviancy | Bias | Expected move |
|---|---|---|---|---|
| Massive draw | Massive draw | highly negative | sustained long | full ATR extension, 1.00+ |
| Massive build | surprise draw | highly negative | aggressive long (squeeze) | explosive and fast, 1.20+ |
| Massive draw | headline draw, product build | mixed (conflict) | fade the spike (short) | 0.50 spike then reversal |
| Massive build | massive build | highly positive | sustained short | full ATR extension, 1.00+ |

### Answers earlier questions (confirm)

- **Baseline (Input 2, Q1):** deviancy uses plain consensus for all three legs. API is not blended into the
  expectation; it is a separate bias and "reality check" signal.
- **Role of the total (Input 1, Q3):** `eia_net_dev` sizes the expected move.
- **Mixed case (Input 1, Q5):** now has a rule (Setup C): wait, then short, instead of "avoid".
- **Candle confirmation (Input 1, Q6):** the README 5-minute candle break is replaced by 1-minute entries.

### Data impact

| Need | Have it? |
|---|---|
| API crude | Yes (`api_report.json`) |
| **API gasoline and distillate** | **No.** Deliberately not scraped (paywalled, stale or dead on the sites). `api_net` cannot be computed without them. Conflicts with the "don't re-add" rule in `CLAUDE.md`. |
| EIA consensus and actuals, three legs | Yes |
| 1-minute WTI bars | Not fetched. `wti_candle` uses 5-minute bars from Yahoo; Yahoo keeps 1-minute data for only about 7 days. |
| ATR | Not available anywhere |
| USD to INR | Not available. Expected moves are WTI USD; the trade is MCX rupee options. |

### Conflicts and inconsistencies in the input

1. **Timing for the product conflict:** Input 1 says wait 3 to 5 minutes; Setup C says wait 60 to 90 seconds.
2. **Chart-free but chart-based:** "do not look at the charts", yet entries are a "minor 1-minute pullback" and a "green 1-minute candle". Neither is defined precisely enough to code (how deep a pullback, measured from what).
3. **Latency vs the window:** the pipeline polls EIA every 60 seconds from aggregator sites that lag the release. Setups B and C act inside 60 to 90 seconds. At best the data arrives after the first move.
4. **Scale vs cheat sheet:** a "highly negative" net deviancy gives "1.00+ full ATR" in the sheet, but the scale rule gives 0.60 to 1.00 for 2 to 5M. ATR is never defined or sourced.
5. **Setup C summed away:** crude -4, gasoline +3, distillate +1 gives net 0 ("minor"), yet it is a clear conflict. Conflict detection must come before the size scale.
6. **"Massive" and "heavily" are undefined** for both API and EIA (only the examples -6M and +5M).
7. **"Draws across the board":** actual below zero, or below consensus? Setup A says draws; Input 1 says deviations. Not the same.
8. **API role in Setup A and the first cheat sheet row:** is the API confirmation required, or does a triple-negative EIA deviancy suffice on its own?
9. **Mirror cases not written out:** bear trap (API draw, EIA build) and bear product conflict (crude build, product draws). The cheat sheet only has the four rows above.
10. **No setup covers:** API near zero, or API and EIA agreeing in direction but net deviancy small, or API bullish with EIA deviancy only mildly negative.
11. **Precedence:** a week can satisfy B and C together (API build, crude draw, products build). No ordering given.
12. **Units:** API Net is a sum of raw changes, EIA Net Deviancy a sum of surprises. They are compared in the reality check but live on different scales.
13. **README overlap:** README vetoes (flows, Cushing, gasoline), 5-minute confirmation and the 3.0 crude trigger are not mentioned. Does Tier 1 alone replace them?
14. **Execution:** no stops, targets or time stops for these setups. README exits (30% stop, +40% target, 20:35 time stop) were built for momentum, not for scalps of 0.30 to 0.50.
15. **Instrument:** Long and Short here read as futures. The README is an options buyer on MCX; shorts mean buying puts.

### Open questions (blockers first)

**Blockers (cannot define the engine without these):**
1. **API gasoline and distillate:** where do they come from? Is the "don't scrape" rule lifted, entered by hand, or is `api_net` replaced by something computable (API crude only)?
2. **Thresholds:** numeric cutoffs for "massive" and "heavily" (API net), "deeply" (EIA net), and for "unexpected" product builds.
3. **Setup A condition:** triple-negative deviations, or net deviancy only, and is the API confirmation required?
4. **Reality check definition:** exact comparison. Sign of API net vs sign of EIA net deviancy? Per leg? Magnitude too?
5. **Execution timing:** 60 to 90 seconds (Setup C) or 3 to 5 minutes (Input 1)? Does this engine produce 1-minute entries at all, or only publish setup and bias while you execute by hand?

**Important:**
6. Define the pullback and the "first green candle" precisely, or leave them manual.
7. Precedence when several setups apply, and the missing mirror cases.
8. Is expected move used for anything (skip small ones, set targets, size)? Source of ATR if so.
9. Conversion from USD to MCX rupees (USD/INR, and option delta).
10. Stops, targets and time stops for each setup.
11. Boundary handling at exactly 2M and 5M (absolute value assumed).
12. Does the 3.0 crude trigger or any README veto still apply?

---

## Input 4: crude vs products interpretation matrix

### Specified

| Crude | Products (gasoline, distillate) | Interpretation | Oil price action |
|---|---|---|---|
| down (draw) | down (draw) | True high demand across the whole system | Bullish (prices rise) |
| down (draw) | up (build) | Refineries over-processing; consumer demand weak | Bearish / neutral |
| up (build) | down (draw) | Refineries offline or in maintenance, but underlying demand strong | Neutral / bullish |
| up (build) | up (build) | Massive oversupply or economic slowdown | Bearish (prices fall) |

### What it adds

This is the reasoning behind Inputs 1 and 3, in a 2x2 form:

| Quadrant | Same as |
|---|---|
| crude down, products down | Input 1 triple-negative; Input 3 Setup A (bullish side) |
| crude up, products up | Input 1 triple-positive; Input 3 Setup A mirror (cheat sheet row 4) |
| crude down, products up | Input 1 mixed; Input 3 Setup C (product conflict) |
| crude up, products down | The mirror of Setup C, which Input 3 never wrote out. It now has a lean: neutral / bullish. |

It is consistent with Input 1's claim that, in a conflict, the market follows the product direction:
products up gives bearish / neutral, products down gives neutral / bullish.

It also supplies the missing "why" for Tier 2: the refinery explanations ("over-processing", "offline or in
maintenance") can be checked against `refinery_util_change_pct`, which `eia_actuals` already writes. Parked
for Tier 2.

### Conflicts and gaps

1. **Strength mismatch with Setup C.** Setup C says short (fade the spike). The matrix says only
   "bearish / neutral". The mixed quadrants are hedged here; Setup C is a trade instruction. Which one wins,
   and is "neutral" a no-trade?
2. **Mixed quadrants are asymmetric and soft.** "Bearish / neutral" and "neutral / bullish" are ranges, not
   signals. The engine needs one output per quadrant (for example: bias, plus whether it is tradeable).
3. **"Down" and "up" are undefined.** The explanations ("refineries over-processing", "demand strong") are
   about the physical stock change (a draw or a build). Inputs 1 and 3 use the surprise (actual minus
   consensus). Those can differ. Example, the 23 Sep week in our data:
   - Actuals: crude +2.97, gasoline -1.69, distillate -0.43. By the matrix: crude up, products down, neutral / bullish.
   - Deviations: crude +3.57, gasoline -1.79, distillate +0.17, net about +1.96. By Input 1: not a triple, mixed.
   - The week was flat after the print (README replay).
   The two readings are not guaranteed to agree, so the engine must pick one.
4. **"Products" is one bucket.** Gasoline and distillate can disagree (gasoline down, distillate up, as in
   the example above). The matrix gives no rule: sum, average, both required, or a leading product?
   (Same question as Input 1, Q4.)
5. **No size.** A crude draw of 0.1M counts the same as 6M. No threshold for a "meaningful" move in either
   column.
6. **Setup B and API are absent.** The matrix is EIA only. The squeeze / trap logic from Input 3 does not
   appear in it, and it does not say how API changes the reading.
7. **No timeframe or trade rule.** It is an interpretation table, not an entry. Entry, wait time, stop and
   target still come from Input 3, which was not reconciled with it (see its conflicts 1 to 3).

### Working model (a proposal for discussion, not a decision)

Three layers, so each input has a clear job:

1. **Quadrant** (Input 4): crude direction x products direction gives a base bias and a regime label.
2. **Overlay** (Input 3): API net bias confirms the quadrant (Setup A) or contradicts it (Setup B squeeze or
   trap), and whether products conflict with crude (Setup C).
3. **Size** (Input 3): `eia_net_dev` scale rule gives the expected move.

The open choice is the basis of "direction" in layer 1: actual change or surprise.

### Open questions

1. **Actual or surprise?** Is "up / down" the sign of the actual stock change or of the deviation from consensus? (This also decides Input 3 conflict 7, "draws across the board".)
2. **Products:** how are gasoline and distillate combined into one direction when they disagree?
3. **Neutral:** is "neutral" a no-trade? How should the two hedged quadrants be treated: lean only, or tradeable?
4. **Setup C vs the matrix:** is Setup C's short the instruction for the "crude down, products up" quadrant, with "bearish / neutral" just its description?
5. **Mirror of Setup C** (crude up, products down): is there a fade-long rule, or is it only a bullish lean?
6. **Minimum size** for a leg to count as up or down? (Zero and near-zero values.)
7. **Is the three-layer model right?** Or should the setups from Input 3 be the primary structure and the matrix only documentation?

---

## Input 5: estimating the target dollar move

### Specified

Estimate the expected price expansion to set profit targets and manage risk:

1. **Crude option implied volatility (IV):** before 10:30 ET, check the front-month WTI options chain on CME
   Group and note the implied market-maker move for the day.
2. **Average WPSR expansion:** an average EIA report moves front-month WTI futures (CL) by $0.50 to $1.20 in
   the first 30 minutes. High-deviation reports (extreme surprises) can reach $1.50 to $2.50+.
3. **Rule of thumb:** for every 1M bbl of aggregate deviation from the combined consensus (crude + gasoline +
   distillate), expect about $0.15 to $0.25 of immediate price momentum in WTI.

### How it relates to Input 3's scale rule

All figures are WTI USD per barrel.

| Net deviation | Input 3 band | Input 5 rule of thumb (0.15 to 0.25 per 1M) | Input 5 report-level ranges |
|---|---|---|---|
| 1M | 0.30 to 0.50 | 0.15 to 0.25 | average report: 0.50 to 1.20 |
| 2M | 0.30 to 0.50 (edge of next band: 0.60 to 1.00) | 0.30 to 0.50 | average report: 0.50 to 1.20 |
| 3.5M | 0.60 to 1.00 | 0.53 to 0.88 | average report: 0.50 to 1.20 |
| 5M | 0.60 to 1.00 (edge of next band: 1.20 to 2.00+) | 0.75 to 1.25 | average report: 0.50 to 1.20 |
| 8M | 1.20 to 2.00+ | 1.20 to 2.00 | high-deviation: 1.50 to 2.50+ |

- **Broadly consistent in the middle.** At 2M to 5M the rule of thumb and Input 3's bands overlap.
- **Small deviations differ.** Input 3 has a floor of 0.30 even for tiny nets; the rule of thumb goes to
  zero (0.5M gives 0.08 to 0.13). Input 5's "average report moves 0.50 to 1.20" also implies a baseline move
  that does not depend on the deviation. So neither the straight line through zero nor the floor is clearly
  right; likely a baseline plus a slope.
- **"Extreme" is defined differently.** Input 3: over 5M gives 1.20 to 2.00+. Under the rule of thumb, 5M
  gives only 0.75 to 1.25; reaching Input 5's 1.50 to 2.50+ needs roughly 6M to 10M.
- **Horizons.** Input 3: momentum for 15 to 30 minutes. Input 5: first 30 minutes. README time stop: 35
  minutes. These are close but not identical.

### What the CME implied move can do (illustration, assumed numbers)

The implied one-day move is roughly `F x IV / sqrt(252)`. With an assumed F of $92 and IV of 35%, that is
about $2.03 for the full day, so a 30-minute expansion of 0.50 to 1.20 sits inside it. The implied move is
therefore a natural sanity cap or scaling reference for the expected move, and it could stand in for the
undefined "ATR" in Input 3. The input does not say how it should be used, only that it should be recorded.

### Data impact

| Need | Have it? |
|---|---|
| Net deviation (crude + gasoline + distillate) | Yes (Input 1 data) |
| **CME front-month WTI options IV / implied move** | **No.** No source in the pipeline. CME data is delayed and its pages are script-heavy, so scraping is uncertain (unverified). Likely a manual input or a broker feed. |
| **Must be captured BEFORE 10:30 ET (20:00 IST)** | A new pre-release snapshot is needed. We removed the engine's `pre` stage because `post` recomputes everything, but this input, like the API print, must be collected before the report. It would be a data stage, not part of the engine. |
| MCX IV | Separate from CME IV. The README used MCX ATM IV from a broker chain for strike choice. Still no source (Input 3 Q9). |
| USD to INR | Still missing. All moves here are WTI USD; trades are MCX rupee options. |
| Backtest of the quoted ranges | None. "Historically" has no data behind it in the repo. The planned `crude_recorder` and journal stages (listed in `common.py`) could calibrate these over time. |

### Gaps in the input

1. **Net or absolute?** "Aggregate deviation" read as the signed net can cancel in conflicts (crude -4,
   gasoline +3, distillate +1 gives 0). A sum of absolute deviations would measure surprise volume instead.
   Direction would then come from elsewhere (the Input 4 quadrant).
2. **Equal weights.** 1M bbl of crude counts the same as 1M of distillate in the rule of thumb.
3. **Targets are not defined.** The move estimate is meant to set targets and manage risk, but there is no
   rule: target at the low end, midpoint, a fraction of the estimate? And nothing on stops.
4. **Implied move usage.** Record only, cap, scale, or compare against the estimate?
5. **Rupee conversion.** Option premiums do not move one-for-one with futures (delta, IV change), so a USD
   target needs conversion into premium points; not specified.

### Open questions

1. Which estimator is authoritative for the expected move: Input 3's bands, Input 5's rule of thumb, or a
   baseline plus slope? If a combination, how?
2. Net deviation or the sum of absolute deviations as the size measure?
3. How is the CME implied move used (cap, scale, record only)? Where does it come from, and who captures it
   before the print?
4. How are profit target, stop and time stop derived from the expected move?
5. Are these quoted ranges starting values to be calibrated from our own recorded weeks?

---

## Input 6: execution timeline

### Specified

"EST" is read as US Eastern time (the report is 10:30 ET all year). In IST this is 20:00 in US summer time and
21:00 in winter. The IST column below is the summer-time clock.

| Phase | Time (ET) | IST (summer) | Action |
|---|---|---|---|
| Pre-release | 10:15 | 19:45 | Note the consensus numbers. Check the Average True Range (ATR) on the 5-minute WTI chart. |
| The release | 10:30:00 | 20:00:00 | Do not chase the first 15 seconds. Algorithms create extreme bid/ask spreads and slippage. |
| The analysis | 10:31:00 | 20:01:00 | Calculate the Net Deviancy. Look for alignment between crude and gasoline. |
| The entry | 10:32 to 10:35 | 20:02 to 20:05 | Wait for the first 1-minute or 5-minute candle to close. Enter on a pullback test of the initial directional breakout vector. |

### What it settles

- **ATR is defined:** ATR on the 5-minute WTI chart. We already fetch 5-minute WTI bars (yfinance, used by
  `wti_candle`), so ATR is computable with no new source. (Input 3's undefined "ATR".)
- **Pre-release capture moves to 10:15 ET (19:45 IST).** This matches the README pre-flight time, and it
  now holds three items: consensus, ATR and (Input 5) the CME implied move.
- **First 15 seconds are dead time.** No decision, no entry; spreads are unreliable. Fits Input 3's
  "wait" instructions.
- **Analysis window:** the engine's result is needed at 10:31:00 ET, one minute after the print.

### Conflicts and gaps

1. **Entry window versus earlier inputs.**
   - Setup B (Input 3): enter after the first 1-minute candle closes green. That closes at 10:31:00, before
     this input's earliest entry (10:32).
   - Setup C (Input 3): wait 60 to 90 seconds, then short. That is 10:31:00 to 10:31:30, also before 10:32.
   - Input 1 mixed case: wait 3 to 5 minutes (10:33 to 10:35), which sits inside this window.
   - README: confirmation on the 20:00 to 20:05 five-minute candle, entry until 20:20. This input closes
     the window at 20:05 (10:35 ET).
2. **"1-minute or 5-minute" is ambiguous.** Which one, and who chooses? The first 5-minute candle closes at
   10:35, the end of the window; the first 1-minute candle closes at 10:31, before it. They give very
   different entries.
3. **"Initial directional breakout vector" is undefined.** Breakout beyond what level: the high or low of
   the release candle (README step 6), the first 1-minute candle, or a pre-release level? And a
   "pullback test" needs a definition: retrace how far, to what, held for how long?
4. **No pullback case.** If price never pulls back inside 10:32 to 10:35, is it a skip or a market entry?
5. **"Alignment between crude and gasoline" ignores distillate.** The Three-Legged Stool and the Input 4
   matrix use all three, with products meaning gasoline plus distillate. Here only gasoline is named. Is
   gasoline the product proxy, or a slip?
6. **Latency.** The analysis must run at 10:31:00 ET, so EIA actuals must be in by about then. `eia_actuals`
   polls every 60 seconds from aggregator sites that lag the release, so it can miss this window. A faster
   source is needed (an EIA API key exists in `.env`; whether its data lands within the first minute is
   unverified).
7. **Slippage applies to MCX too?** The warning is about NYMEX algos. The traded instrument is MCX options,
   whose own spread and delay at 20:00 are not covered (README caps spread at 5% of premium).
8. **No exit or stop** in this table (same gap as Inputs 3 and 5).

### Open questions

1. **One entry rule:** with Inputs 1, 3 and 6 all giving different waits, which governs? Suggestion to
   confirm: Input 6's 10:32 to 10:35 window for every setup, with the 5-minute option equal to the README
   confirmation.
2. 1-minute or 5-minute candle? Does the choice depend on the setup?
3. Define "initial directional breakout vector" and "pullback test", or leave them to manual execution.
4. If no pullback occurs by 10:35, is it no trade?
5. Is the crude and gasoline alignment intentionally gasoline-only?
6. Does the entry deadline move from 20:20 (README) to 20:05, and is the 35-minute time stop still valid?
7. Which faster source for EIA actuals, and is catching the 10:31 deadline a hard requirement?

### Answers received (Input 6 follow-up)

| # | Answer | Effect |
|---|---|---|
| 1 | Use the suggested approach: Input 6's entry window for every setup; the 5-minute option equals the README confirmation | One entry rule for all setups. Setup B's "enter after the first 1-minute candle" and Setup C's "wait 60 to 90 seconds" no longer apply as timings. |
| 2 | 5-minute candle | No 1-minute logic. The 1-minute bar data gap in the running list disappears. |
| 3, 4 | not answered | Breakout vector, pullback test, and the no-pullback case still undefined (may be moot, see below). |
| 5 | Crude and gasoline alignment only, because gasoline is a product of crude oil | Gasoline is the product proxy for the alignment check. |
| 6 | Yes (entry deadline moves from 20:20 to 20:05, 35-minute time stop stays) | See the problem below. |
| 7 | No: analysis does not have to be ready at 20:01. It must be ready to trade at 20:05 | Latency requirement relaxed to about 20:04. |

### What this settles

- **Latency:** the engine runs at the 20:05 candle close, not 20:01. A 60-second poll of the EIA aggregators
  can now plausibly deliver in time. (Whether those sites publish within about four minutes is still
  unverified.)
- **Data:** only 5-minute WTI bars are needed, which we already fetch.
- **Entry timing:** no entry before 20:05, for any setup.

### New problem: the 20:05 deadline leaves no window

- The first 5-minute candle (20:00 to 20:05) closes at 20:05, and the analysis is ready at 20:05.
- An entry deadline of 20:05 means the only possible entry moment is the instant that candle closes.
  A "pullback test of the breakout" cannot happen inside a zero-width window: a pullback comes after the
  close.
- The README confirmation needs a later bar: after the 20:00 to 20:05 release candle closes, the entry is a
  5-minute close beyond its high or low, the earliest being the 20:05 to 20:10 bar, closing at 20:10. That
  is after the new deadline.
- So answers 1 (5-minute option equals the README confirmation) and 6 (deadline 20:05) cannot both hold.
  The suggestion in the Input 6 question 1 assumed a window; I should have caught that the 5-minute close
  falls on its end. (Question 6 also bundled two things, the deadline and the time stop, so "yes" may have
  meant only one of them.)

Ways to make it consistent (pick one):

| Option | Entry rule | Cost |
|---|---|---|
| A | Enter at the 20:05 close of the release candle, direction from the analysis; the candle itself is the confirmation if it closes in the signal direction. No pullback wait. | Drops the README break-of-candle test and the pullback idea. Simplest. |
| B | Keep the README confirmation (5-minute close beyond the release candle's far side) and keep the 20:20 deadline. | Reverses answer 6. Entry is no earlier than 20:10. |
| C | Deadline at 20:10: one more 5-minute candle after the release candle, entry on its close if it breaks the release candle's high or low in the signal direction. | Compromise: a window of one bar. Reverses answer 6 partially. |

### Open questions (follow-up)

1. Which option (A, B or C), or something else? What exactly does "deadline 20:05" mean in your mind?
2. Was the "yes" to question 6 for the deadline, the time stop, or both?
3. Distillate: with a gasoline-only alignment check, does distillate count only inside the net deviation sum?
   Do Input 1's triple rules (all three legs) still require distillate's sign, or are they replaced by
   crude-and-gasoline alignment?
4. The 20:05 candle must be available by about 20:05 from Yahoo. Yahoo's delay for the current 5-minute bar
   is unverified; if it lags, the engine cannot read the release candle in time. Is a delayed candle
   acceptable (the entry would slip to when the data arrives)?
5. Still unanswered: define the breakout vector and pullback test, or drop them (they may be moot under
   option A).

---

## Input 7: briefing, aggregate baseline and net surprise (worked example)

### Specified

Before the report, sum the three consensus values into one aggregate baseline. After the report, compare the
net actual change against it.

| Leg | Consensus (M bbl) |
|---|---|
| Crude | -1.0 |
| Gasoline | +0.5 |
| Distillate | -0.5 |
| **Aggregate baseline** | **-1.0** |

If the actual net change is -4.0M, the report is a 3.0M bullish surprise (-4.0 minus -1.0): an immediate
long bias.

### Note

- **Same number as before.** Net actual minus net consensus equals the sum of the three per-leg deviations,
  so this is Input 1's `total_dev` and Input 3's `eia_net_dev`, reached from the aggregate side. Nothing new
  to compute; it is a second way to read the same figure.
- **Pre-report baseline:** the aggregate consensus (-1.0 here) can be fixed ahead of the print from
  `consensus.json`. The engine can store it at the 19:45 snapshot.
- **Plain consensus again:** the baseline uses consensus only, with no API blend. This agrees with the
  reading in Input 3 (consensus is the baseline; API is a separate signal).
- **Size link:** a 3.0M surprise is in Input 3's 2M to 5M band (0.60 to 1.00) and gives 0.45 to 0.75 under
  Input 5's 0.15 to 0.25 per 1M. Both land in the "solid, clean push" range.
- **Sign:** draw negative, consistent with the project convention. Negative surprise is bullish.

### Tension with Inputs 1, 3 and 4

The briefing draws an "immediate long bias" from the net surprise alone. The net hides how it is made up.
Both cases below have the same consensus and the same net actual of -4.0M, hence the same -3.0M surprise:

| | Crude actual | Gasoline actual | Distillate actual | Deviations (crude, gasoline, distillate) | Regime |
|---|---|---|---|---|---|
| Aligned | -2.5 | -0.5 | -1.0 | -1.5, -1.0, -0.5 | Triple-negative: Setup A, long |
| Conflict | -5.5 | +1.0 | +0.5 | -4.5, +0.5, +1.0 | Crude draw, products build: Setup C, fade the spike |

So the net alone gives the same long bias in both, while Inputs 1, 3 and 4 give opposite trades. The net
should therefore work as a size measure, not as a direction rule, unless leg conflict is checked first
(already noted in Input 3, conflict 5).

### Open questions

1. **Precedence:** is the net surprise an immediate bias on its own (the briefing), or is the leg-conflict
   check done first and allowed to override it (Inputs 1, 3, 4)? Suggested: conflict check first, then net
   for direction in aligned cases and for size.
2. Is there a minimum net size before the net gives a bias at all (the briefing's example is 3.0M)?

---

## Input 8: the API report (Tuesday preview of the EIA print)

### Specified

The API report comes out Tuesday 4:30 PM ET (about 02:00 IST Wednesday in US summer time). It is built from
voluntary company submissions, so it is the main tool for adjusting expectations before the official data.

**1. Baseline shift.** The API redefines the market's baseline. Example: consensus for the EIA is a 2M draw,
but the API shows a 6M draw. The market prices in tighter supply, WTI tends to drift up Tuesday evening or
Wednesday morning, and at 10:30 ET the EIA is measured against the API preview, not only against the
original consensus.

**2. API vs EIA divergence ("rubber band" trade).** The API and EIA directions match roughly 75% to 80% of
the time. The opportunity is the other 20% to 25% of weeks, when they contradict each other and price
reverts after the EIA.

| Setup | API (Tuesday) | Price into Wednesday | EIA (Wednesday) | Result |
|---|---|---|---|---|
| Bull trap | massive build, +4M | drops | surprise draw, -3M | shorts caught, violent snap-back up |
| Bear trap | massive draw, -5M | rises | surprise build, +2M | longs liquidate, price collapses |

**3. Cushing, Oklahoma** (the API Cushing line, Tier 2): moved to `docs/tiers_2_4.md`.

### Overlaps with earlier inputs

- **Bull and bear trap = Input 3 Setup B.** Same logic, now with a base rate and with both directions
  written out (answers part of Input 3, conflict 9, the missing mirror case).
- Cushing: see `docs/tiers_2_4.md`.
- **API timing** matches `api_monitor` (Wednesday about 02:00 IST).
- **Hints for thresholds** ("massive" and the contradicting print), taken from the examples only (not
  decisions): API crude about 4M or more in size; the contradicting EIA print 2M to 3M in the opposite
  direction.

### Possible resolution: API crude may be enough

Every example here uses API **crude** only. Nothing mentions API gasoline or distillate. Input 3's `api_net`
was the sum of all three API legs, which we cannot get (deliberately not scraped). If the API bias and the
trap setups run on API crude alone, the Input 3 data blocker goes away. To be confirmed.

### Conflicts and gaps

1. **Baseline: plain consensus or API-adjusted?** This is the direct conflict.
   - Inputs 3 and 7: deviancy against plain consensus, API kept separate.
   - Input 8 (and the README's `E_c = (consensus + API) / 2`): the market measures the EIA against an
     API-adjusted hurdle.
   - Example (crude, assumed 50% weight): consensus -2.0, API -6.0, adjusted baseline -4.0. If the EIA prints
     -4.0, the deviancy is -2.0 against plain consensus (bullish) but 0.0 against the adjusted baseline
     (nothing). The trigger fires in one reading and not the other.
   - With API legs for gasoline and distillate unavailable, an adjusted baseline could apply to crude only.
   - If the baseline already includes the API, the trap setups would also be scoring API twice (once in the
     baseline, once as the contradiction), unless handled.
2. *(Cushing: moved to `docs/tiers_2_4.md`.)*
3. *(Cushing: moved to `docs/tiers_2_4.md`.)*
4. **Trap precondition: overnight price move.** The trap setups say prices dropped or rose overnight. Is the
   move verified (WTI move from the API print to 10:15 ET), or is the API sign enough? The data exists
   (5-minute WTI from Yahoo), but it is not in the spec.
5. **The 75% to 80% figure has no source.** It is context; the engine does not need it.
6. **Units of "massive":** API 4M to 5M look like size hints, but the EIA side ("surprise draw -3M", "+2M")
   does not say whether that is the actual change or the deviation from consensus.

### Open questions

1. **Baseline:** plain consensus (Inputs 3 and 7) or API-adjusted (Input 8, README)? If adjusted: the weight
   (the README's 0.5?), and applied to crude only?
2. **API scope:** confirm the API signal and the trap setups use API crude only, so API gasoline and
   distillate are not needed.
3. *(Cushing: moved to `docs/tiers_2_4.md`.)*
4. **Trap thresholds:** confirm candidates (API crude at least 4M in size; the contradicting EIA print at
   least 2M, as a deviation or as an actual change).
5. **Overnight drift:** must the overnight WTI move confirm the trap, or is the API sign enough?
6. *(Cushing: moved to `docs/tiers_2_4.md`.)*

---

## Input 9: Tiers 2 to 4 checklist (metrics beyond the Big Three)

Moved to `docs/tiers_2_4.md`.

---

## Input 10: the role and time horizon of each tier

Moved to `docs/tiers_2_4.md`.

---

## Input 11: API versus consensus baseline, and why API crude alone is not enough

### Specified

The consensus (Reuters or Bloomberg, published early in the week) is the market's first expectation. The API
print on Tuesday 4:30 PM ET alters it. Three structural baseline states, by how API compares with consensus:

| State | API vs consensus | Example (consensus, API) | Market impact |
|---|---|---|---|
| **Alignment** (expected volatility) | closely matches | -1.5M, -1.8M | Baseline unchanged. The market is efficiently priced; the Wednesday EIA deviancy drives 100% of the volatility. |
| **Shifted** (priced-in momentum) | exceeds consensus, same direction | -1.5M, -5.0M | Baseline shifts aggressively; oil often rallies overnight. A -1.5M EIA draw is no longer enough to lift prices; the market needs a massive draw to hold, because the psychological floor moved. |
| **Divergent** (coiled spring) | contradicts consensus | -1.5M, +3.5M | The baseline is broken: erratic pre-report chopping as bulls and bears fight for positioning before the EIA's ruling. |

**Verdict: API crude alone is not enough**, even for a Tier 1 strategy. Track the trio (crude, gasoline,
distillate) across both reports:

```
[Wall Street consensus] -> adjusted by -> [API trio, Tue 4:30 PM ET] -> settled by -> [EIA trio, Wed 10:30 AM ET]
```

- **Reason A, product overhang:** crude can draw because refineries run hard. If API crude draws massively
  while API gasoline and distillate build massively, finished-product demand is dead. The EIA confirms the
  backup Wednesday and the market sells off, wiping out anyone who bought on the API crude draw alone.
- **Reason B, divergence illusion:** API and EIA crude sometimes diverge from methodology differences, but
  finished products are easier to track, so API product data is often still accurate. With all three API
  legs you can spot weeks when product demand is structurally strong and hold the trade through messy crude.

(The closing offer in the pasted text, to set up a monitoring task, is not part of the spec and is not
addressed here.)

### What it settles

- **Input 8 Q2 (API crude only?):** no. The API trio is required. This reverses the "possible resolution"
  noted under Input 8, and **re-instates the Input 3 blocker**: we have no API gasoline or distillate data
  (see below).
- **Input 8 Q1 (baseline):** leans to an **API-adjusted baseline**: "consensus adjusted by the API trio,
  settled by the EIA trio", and the Shifted example ("-1.5M is no longer enough"). The README's
  `E_c = (consensus + API) / 2` and the user-owned `thresholds.json` (`api_weight` 0.5) already point the
  same way. The text does not give a formula or weight.

### Worked example (crude only, assumed 50% weight)

Taking the three examples and an EIA print equal to consensus (-1.5M in each):

| State | Consensus | API | Blended baseline | EIA | Deviation vs plain consensus | Deviation vs blended baseline |
|---|---|---|---|---|---|---|
| Alignment | -1.5 | -1.8 | -1.65 | -1.5 | 0.0 | +0.15 |
| Shifted | -1.5 | -5.0 | -3.25 | -1.5 | 0.0 | +1.75 (bearish) |
| Divergent | -1.5 | +3.5 | +1.0 | -1.5 | 0.0 | -2.5 (bullish) |

Against plain consensus the Shifted and Divergent weeks look like nothing happened. Against the blended
baseline they are real surprises in the direction the text describes (Shifted: "not enough", bearish;
Divergent: a draw into a build expectation, bullish). This is the argument for the adjusted baseline, and
the conflict with the plain-consensus deviancy of Inputs 3 and 7.

### Two comparisons, not one

- **Tuesday:** API against consensus gives the baseline state (aligned, shifted, divergent). New in this
  input.
- **Wednesday:** EIA against API gives confirmed or contradicted (Input 3 reality check, Setups A and B).
- The engine needs both. How the state combines with the Wednesday outcome is not specified (see gaps).

### Data impact

| Need | Have it? |
|---|---|
| API gasoline and distillate (Tue about 02:00 IST) | **No, and now required.** `CLAUDE.md` says they are deliberately not scraped (paywalled, stale or dead on the sites) and "don't re-add". That rule must change, or another source (or hand entry) is needed. |
| API crude | Yes |
| Consensus trio | Yes |

### Gaps

1. **State cutoffs.** Only three examples; no number for "closely matches" (the example gap is 0.3M) or "significantly exceeds" (3.5M). And on what quantity: API crude alone, the aggregate trio, or each leg?
2. **Formula missing.** "Adjusted by" has no weight or per-leg rule. The blend (and the 0.5) is only implied.
3. **State x EIA matrix missing.** For example: Shifted state and an in-line EIA print (bearish), Shifted and a bigger draw (continuation), Divergent and either outcome (Setup B trap?).
4. **Reason A is Setup C seen from the API side.** An API conflict (crude draw, product builds) may predict a Wednesday Setup C. Not stated as a rule.
5. **Reason B has no rule.** "Hold the trade when API products are strong" lacks a definition: compare API product direction with the EIA product direction? Which wins?
6. **Divergent pre-report chopping** concerns the hours before the print; our engine acts after it. Informational only?
7. **Claims unsourced:** that API products are "easier to track" and "highly accurate" is asserted, not backed by data we hold.

### Open questions

1. **Baseline:** does the Tier 1 deviation use the API-adjusted baseline (this input, README, `api_weight`), or plain consensus (Inputs 3 and 7) with the API state as context only? If adjusted: weight (0.5?), and per leg (trio) or aggregate?
2. **State cutoffs:** what gap sets aligned, shifted and divergent, measured on which quantity?
3. **API gasoline and distillate:** lift the "don't scrape" rule and find a source, enter them by hand into `api_report.json`, or something else? (Hand entry of two numbers once a week is the quickest fallback.)
4. **State x EIA matrix:** what trade or bias does each combination give?
5. **API product data:** used as an early warning of Setup C, as a tie-breaker when API and EIA crude diverge, or both? How exactly?

---

## Running list: data needed so far

| Data | Timing | Status |
|---|---|---|
| EIA consensus: crude, gasoline, distillate | Tue | Have |
| API crude | Wed about 02:00 IST | Have |
| API gasoline, distillate | Wed about 02:00 IST | **Missing, now required** (Inputs 3 and 11); the scrape ban in `CLAUDE.md` must change or another source be found |
| WTI price move from API print to 19:45 IST | pre | Computable from the 5-minute bars; only if overnight drift is required (Input 8) |
| CME WTI options IV / implied move | before 20:00 IST | **Missing** (Input 5) |
| MCX futures price, option IV, expiry, spread | before 20:00 IST | **Missing** (hand-kept in the old draft) |
| USD to INR | at the print | **Missing** |
| EIA actuals: crude, gasoline, distillate | needed by about 20:04 IST | Have; 60 s polling plausibly fits the relaxed 20:05 deadline (unverified) |
| 1-minute WTI bars | | Not needed: 5-minute candle chosen (Input 6 follow-up) |
| ATR on 5-minute WTI | 19:45 IST | Computable from the 5-minute bars we already fetch (Input 6); not implemented |
| Tier 2 to 4 data | later | See `docs/tiers_2_4.md` |

---

## Tier 1 consolidated spec (v1, implemented)

Gathers Inputs 1 to 11 and the timing decision into one proposal. Nothing here is final until confirmed. All
numbers are placeholders for `thresholds.json` and are unbacktested.

### Run window and data flow

- Engine starts about 19:59 IST (20:59 in winter) and must finish by about 20:04:30. It uses no price data.
- It polls for today's `eia_actuals.json` (same `release_date` as `consensus.json`). If the data is not there
  by 20:04:30, the status is `LATE` (no trade).
- Inputs: `thresholds.json`; `consensus.json` (three legs); `api_report.json` (API crude);
  `api_products.json` (new, hand-entered Tuesday night: API gasoline and distillate; a separate file because
  `api_monitor` overwrites `api_report.json`); `eia_actuals.json`.
- Output: `signal.json`. Any failure writes `{"status": "ERROR"}` and sends a Telegram alert.

### Computation

For each leg `i` in crude, gasoline, distillate (million bbl, build +, draw -):

```
baseline_i  = consensus_i + w * (api_i - consensus_i)        w = api_weight (0.5)
dev_i       = eia_actual_i - baseline_i
net_dev     = sum of dev_i
```

- If an API leg is missing, `baseline_i = consensus_i` and the output flags it.
- Record only (no effect on the decision): the plain-consensus deviations `actual_i - consensus_i`.
- A leg counts as moving only if `|dev_i| >= min_leg_dev` (0.1).
- API state, from the trio totals: `gap = api_net - consensus_net`. `|gap| < 1.0` aligned; API beyond the
  consensus in the same direction: shifted; API of opposite sign to the consensus: divergent. (API same sign
  but weaker than consensus has no name in the input; recorded as `softer`.)
- API vs EIA (trap test, **crude only**, confirmed): API crude and EIA crude have opposite signs, with
  `|API crude| >= trap_api_min` (4.0) and `|EIA crude| >= trap_eia_min` (2.0). Whether the EIA 2.0 is the
  actual change or the deviation from the adjusted baseline is still to be confirmed.

### Decision order

1. Missing or late data: `LATE` or `ERROR`, no signal.
2. `|net_dev| < min_net` (2.0): `NO TRADE`.
3. **Conflict (Setup C):** crude and gasoline deviations have opposite signs. Side follows gasoline (the
   product direction); the crude headline is the fade.
4. **Trap (Setup B):** the crude-only test above passes. Side follows the EIA crude direction; the trio
   `net_dev` then sizes the expected move (confirmed).
5. **Aligned (Setup A):** crude and gasoline deviations agree. Conviction is strong if distillate also agrees
   and the API confirms; otherwise standard.
6. Otherwise `NO TRADE`.

Side: `net_dev < 0` is bullish (CALL), `net_dev > 0` is bearish (PUT), except in Setup C where the side follows gasoline.

### Output (`signal.json`)

Status; setup (A, B or C); side; conviction; `net_dev` and the three deviations; API state and API-vs-EIA
result; expected move in USD (bands by `|net_dev|`: under 2M 0.30 to 0.50, 2M to 5M 0.60 to 1.00, over 5M 1.20
to 2.00+; Input 5's 0.15 to 0.25 per 1M recorded as a cross-check); a **confirmation condition** for the trader
to check on the 20:00 to 20:05 candle (the candle must close in the signal direction; stop beyond its far
side); the schedule (entry 20:05, time stop 20:35, hard exit 22:30, DST-aware); warnings; record-only Tier 2
and 3 values (utilization change, Cushing change, net imports); `config_version`.

### Not in v1

MCX strike, lots, USD/INR, CME IV, ATR, Tier 2 to 4 logic, the pre-print snapshot, and candle reading in the engine.

### Confirmation status (2026-10-01)

| # | Point | Status |
|---|---|---|
| 1 | API-adjusted baseline per leg: `0.5 x consensus + 0.5 x API` | Confirmed |
| 2 | Data-only engine; candle and pullback checks are manual on the trading terminal | Confirmed |
| 3 | API gasoline and distillate entered by hand into `api_products.json` | **Not answered** |
| 4 | Decision order conflict, then trap, then aligned | Confirmed (what counts as a conflict: see open points) |
| 5 | Placeholder numbers (`min_leg_dev` 0.1M bbl, `min_net` 2.0M, gap 1.0M, trap 4.0M and 2.0M) | Confirmed |
| 6 | Trap thresholds on crude only; trio net deviation then sizes the expected move | Confirmed |
| 7 | Poll `eia_actuals` every 10 s so the engine finishes by 20:04:30 | **Rejected: the data cannot arrive that fast** (see latency below) |

### Latency (answer to point 7)

Reported: at 20:00 Investing.com and Trading Economics take time to show the report, and EIA's own API
responds late. So the engine cannot count on having the actuals before 20:05 via the current sources.

Lead found on 2026-10-01 (read-only check, not yet measured at a release): EIA's release server,
`https://ir.eia.gov/wpsr/table1.csv`, is public (no key) and redirects to a signed link. The link's policy
starts at the release instant (10:30 ET) and runs to the next release, so the file is served from the print
itself. It holds Table 1 (stocks: crude commercial and SPR, gasoline, distillate, with week-on-week
differences). Table 2 (`table2.csv` style content in the same file set) has imports, exports, net imports and
product supplied in thousand b/d. This is a different host from `api.eia.gov` and from the `www.eia.gov`
pages. Unverified: how fast it flips to the new week at 20:00, and whether it carries Cushing and refinery
utilization.

Options (not decided):

- **A. Measure first.** At the 7 Oct release, poll that file and the two aggregator sites from 19:59:50 and
  log when each shows the new week.
- **B. Deadline policy.** The engine starts at about 19:59 and finishes whenever the data arrives. If it is
  after 20:05 the signal is marked `LATE` with its age and the trader decides, instead of a hard no trade.
- **C. Scenario card.** Before the print, the engine writes the trigger levels for each leg (what crude,
  gasoline and distillate prints give which setup), so the trader can read the headline themselves if the data
  is late. This reintroduces a pre-print step.

### `data/api_products.json` schema (hand-entered or produced by any script)

Read by the signal engine only; `api_monitor` never touches it. Written once per week after the API print
(Tuesday about 16:30 ET, 02:00 IST Wednesday) and before the engine starts.

```json
{
  "release_date": "29-09-2026",
  "api_gasoline_mb": -1.2,
  "api_distillate_mb": 0.4
}
```

| Field | Type | Rule |
|---|---|---|
| `release_date` | string `DD-MM-YYYY` | The API report's own date (the Tuesday). Must equal `release_date` in `api_report.json`; otherwise the file is ignored with a warning (it is last week's). |
| `api_gasoline_mb` | number | API gasoline stock change, million barrels. Build positive, draw negative. |
| `api_distillate_mb` | number | API distillate stock change, million barrels. Build positive, draw negative. |

Behaviour: the file may be missing. A leg that is missing, not a number (for example `"-1.2M"`) or not finite
is ignored with a warning, and that leg's baseline falls back to the consensus alone. A value above 15 in
size gets a "check the unit" warning but is still used. Extra keys are ignored, so a producer can add
`source` or `entered_at`. Write it atomically (temp file then replace) if a script produces it.

### Setup C check (changed 2026-10-02)

The earlier condition asked the 20:00 to 20:05 candle to close in the trade direction. For a fade that is
close to impossible: the first candle is the crude spike, which moves the other way. The check is now that
the spike has **stalled**: the candle closes in the lower half of its range for a PUT fade (after a spike up),
or the upper half for a CALL fade; a close at the spike extreme means it is still running and the trade is
skipped. The stop stays beyond the spike extreme. The half-range rule is an interpretation of "wait for the
spike to stall" and is for you to tune.

## Input 12: API gasoline and distillate from ForexFactory (built as `app/api_products.py`)

Context: the API gasoline and distillate are paywalled and cannot be scraped from the usual sites, but the
print is posted on X and ForexFactory collects it on the calendar event
`https://www.forexfactory.com/calendar/754-us-api-weekly-statistical-bulletin`. Warning from the user: the
posting may not be on the same day as the API report, and the wording differs, so no single fixed approach
can be assumed. Investigated on 2026-10-02 (read-only).

### What the page holds

- The calendar rows carry **no numbers**: history shows only dates (no actual, forecast or previous).
- The numbers are in the **News** block: one item per release, a tweet picked up by ForexFactory, with
  `title`, `preview` (the tweet text), `source` (the account), `dateline` (a UNIX timestamp) and an event id.
  Only the latest 8 releases are listed.
- Server-rendered, so a plain HTTP fetch gets it: the news items are in a JSON attribute (`data-items`) and
  also in the DOM. No JavaScript needed.

### What the 8 releases looked like

| Release (ET) | Account | Title as posted | Notes |
|---|---|---|---|
| Tue 29 Sep | @FirstSquawk | `API: Crude: 1.019M, Gasoline: +2.991M, Distillate: -0.286M` | no `+` on crude; prose in the preview ("Stocks Up 2.991 Mln") |
| Tue 22 Sep | @captgirish1 | `API:  Crude: +1.786M, Cushing: +2.082M, Gasoline: -2.16M,  Distillates: -2.164M` | has Cushing; double spaces |
| Tue 15 Sep | @captgirish1 | `... Crude: +7.14M, Cushing: -0.246M, Gasoline: +1.46M, Distillates: +1.61M` | |
| **Wed 9 Sep** | @financialjuice | `API: Crude -0.3m, Cushing -0.3m, Distillate +2m, Gasoline - 1.9m` | **a day late** (Monday holiday); order differs; `- 1.9m` has a space after the sign; lower-case `m`; rounded |
| Tue 1 Sep | @JuliOnTwtr | `API: Crude -2.6M, Gasoline +0.3M, Distillates -0.3M, Cushing +0.2M` | preview uses `+300,000` and `-3.1 million`, and carries SPR |
| Tue 25 Aug | @financialjuice | `US API Crude Oil Stock Change Actual 4.2M (Forecast -, Previous -0.328M)` | **title has crude only**; gasoline and distillate are in the preview as `Gas: -3.2MM Dist: -.05MM` |
| Tue 18 Aug | @JuliOnTwtr | `API: Crude -328K, Gasoline +1.076M, Distillates -2.797M Cushing -1.438M` | `K` units, no comma |
| Tue 11 Aug | @JuliOnTwtr | `API: Crude 9.072M, Gasoline -1.531M, Distillates -596K, Cushing +1.571M` | |

Variety seen: units `M`, `m`, `MM`, `Mln`, `million`, `K`, plain thousands with commas; labels `Gasoline`/`Gas`,
`Distillate`/`Distillates`/`Dist`, `Cushing`/`Cush`; sign before or after a space, or missing; leading dot
(`-.05MM`); different order; prose with "up/down"; some weeks the title lacks gasoline and distillate.

### Findings that decide the approach

1. **The repo's browser is blocked.** The existing headless Playwright session gets HTTP 403 and Cloudflare's
   "Just a moment..." page; headed Chromium and installed Chrome were blocked the same way. A normal browser
   (the Claude app's) was let through.
2. **Plain HTTP with browser TLS impersonation works.** `curl_cffi` (already in `requirements.txt`) with
   `impersonate="chrome"` and `"safari17_0"` returned the full page 5 of 5 times; the `chrome124` profile
   was refused (403) once. So it works but is not guaranteed, and may stop at any time.
3. **The date label is not a safe key.** "Released on" dates follow the viewer's timezone (IST here), and the
   9 Sep release (posted Wed 16:48 ET, Thursday 10 Sep in IST) shows the holiday shift. The `dateline` UNIX
   timestamp is timezone-independent, and the tweets landed 9 to 25 minutes after the 16:30 ET print.
4. **A free anchor exists: crude.** Every post carries API crude, and we already have API crude from
   `api_report.json` (Trading Economics / Investing.com). A post whose crude disagrees is the wrong week or a
   typo. The tolerance must follow the precision the tweet prints (`-0.3m` against a true `-0.328` differs by
   0.028).
5. **One post per release, one account, no second opinion** for gasoline and distillate. Only the crude
   anchor checks it.
6. A throwaway parser (label plus number plus unit, handling the variants above) read **14 of 14** titles and
   previews correctly. That proves little: it was shaped on those same samples, so unseen wording will happen.

### Recommended approach (for approval)

1. **Fetch:** `curl_cffi`, `chrome` profile with `safari17_0` as fallback; one request per poll to the event
   page; read the `data-items` JSON (fall back to the DOM). No Playwright.
2. **Choose the post by evidence, not by date:** the `dateline` must fall in a window after the API print
   (anchored on the API release date already in `api_report.json`, so a holiday shift follows it), AND the
   parsed crude must match `api_report.json`'s crude within the post's own rounding. Otherwise reject.
3. **Parse:** tolerant label, sign, number and unit rules; read the title first and the preview for what the
   title lacks (the 25 Aug case). Also keep Cushing and SPR when present (Tier 2 and 3, record only).
4. **Validate:** both legs present and plausible in size (the engine already ignores a bad or missing leg and
   falls back to the consensus, with a warning).
5. **Write** `data/api_products.json` with the schema in this doc plus provenance (`source`, account,
   `posted_at`, matched crude, the raw tweet text); a hand-entered file (`"source": "manual"`) is never
   overwritten.
6. **Timing:** poll every 5 minutes from the API print for up to 4 hours (as `api_monitor` does). The engine
   starts about 18 hours later, so there is ample slack.
7. **Alert** on Telegram if nothing valid is found by the end of the window; show the account and the raw
   text in the engine's log so the trader can see what was used.
8. **Separate stage** (`app/api_products.py`), not inside the production-tested `api_monitor`.

### Risks to accept or mitigate

- One third-party tweet is the only source for the two legs: a mis-typed number passes unless it also breaks
  the crude anchor. Mitigation: print the account and tweet text; the manual override.
- Cloudflare can change what it accepts; the fallback is the existing manual entry.
- ForexFactory's terms of use were not checked and automated access may not be allowed. Keep it light (one
  request every 5 minutes, only on Tuesday night) and the decision is the user's.
- New wording will appear; the parser returns a partial or no result, never a guess, and the run falls back
  to the consensus for the missing legs.

### Open questions

1. Approve the approach above (HTTP fetch, evidence-based post selection, separate stage)?
2. Comfortable with the terms-of-use risk?
3. Manual file wins over a scraped one, and a scraped one never overwrites a manual one. Agree?
4. Also record API Cushing and SPR when the post has them?
5. Poll window and cadence (5 minutes for 4 hours from the API print) acceptable?
6. If the post is missing or fails the crude check, is falling back to the consensus (with the warning and a
   Telegram alert) acceptable, or should the engine refuse to run without it?

---

## Decision log

| Date | Decision |
|---|---|
| 2026-10-01 | Input 1 recorded. Nothing decided on its open questions. |
| 2026-10-01 | Input 2: four-tier structure adopted; Tier 1 is built first, Tiers 2 to 4 later. |
| 2026-10-01 | Input 3: full Tier 1 algorithm recorded (API net, EIA net deviancy, setups A/B/C, scale rule). Not coding yet. Blockers listed under Input 3. |
| 2026-10-01 | Input 4: crude vs products 2x2 interpretation matrix recorded. Proposed three-layer model (quadrant, overlay, size) is for discussion only. |
| 2026-10-01 | Input 5: target dollar move estimation recorded (CME IV, average and extreme WPSR moves, 0.15 to 0.25 per 1M rule). Added a running data-needs list. |
| 2026-10-01 | Input 6: execution timeline recorded (10:15, 10:30, 10:31, 10:32 to 10:35 ET). ATR defined as 5-minute WTI ATR. Entry-timing conflicts with Inputs 1, 3 and the README listed. |
| 2026-10-01 | Input 6 answers: one entry rule for all setups; 5-minute candle; alignment is crude and gasoline only (gasoline is a crude product); engine ready at 20:05, not 20:01. Deadline 20:05 conflicts with the README confirmation and a pullback (zero-width window): options A/B/C awaiting choice. |
| 2026-10-01 | Input 7: briefing recorded (aggregate baseline, net surprise worked example). Same quantity as `total_dev`; net-only bias conflicts with the leg-conflict rules, precedence question open. |
| 2026-10-01 | Input 8: API report recorded (baseline shift, bull/bear trap, Cushing pivot). Conflicts with the plain-consensus baseline of Inputs 3 and 7. May remove the API gasoline/distillate blocker if API crude alone is enough. |
| 2026-10-01 | Input 9: Tiers 2 to 4 checklist recorded (refinery utilization, Cushing, SPR, imports, 4-week product supplied). Tier 1 remains the first build; role of the tiers (veto, weaken, flip) still open. |
| 2026-10-01 | Input 10: role and time horizon of each tier recorded (T1 0 to 2 min, T2 2 to 10, T3 10 to 30, T4 30 min to end of day). Tier 2 can flip a signal into a fade. The 20:05 entry sits after Tier 1 and inside Tier 2; to be discussed. |
| 2026-10-01 | Input 11: API versus consensus baseline (aligned, shifted, divergent) recorded. Verdict: API crude alone is not enough, the trio is required. Re-instates the API gasoline/distillate data blocker. Leans to an API-adjusted baseline; formula and cutoffs open. |
| 2026-10-01 | Timing decision: the engine must run and COMPLETE before 20:05 IST, not after. Consequence: it cannot read the 20:00 to 20:05 candle, so it is data-only (consensus, API trio, EIA actuals). Candle confirmation becomes a stated condition for the trader at 20:05 (to confirm). EIA actuals must arrive between about 20:00 and 20:04. |
| 2026-10-01 | Draft v1 of the consolidated Tier 1 spec written (section above the log). Awaiting confirmation of the seven listed points. |
| 2026-10-01 | Confirmed: points 1, 2, 4, 5, 6 of the draft. Point 7 rejected (sources lag at 20:00). Point 3 unanswered. Found `ir.eia.gov/wpsr/table1.csv` as a possible faster source (unmeasured). |
| 2026-10-01 | Point 3 confirmed (hand entry) and latency options A plus B chosen. Tier 1 engine built (`app/signal_engine.py`) with tests. Trap EIA threshold read as the actual change, conflict as crude vs gasoline, mirror of Setup C symmetric: assumptions, not confirmed. |
| 2026-10-02 | Setup C check changed from "candle closes in the trade direction" to "spike has stalled" (close in the opposite half of its range). api_products.json schema documented; non-numeric values are ignored with a warning. Telegram summary on every run. |
| 2026-10-02 | Input 12: ForexFactory API bulletin investigated for API gasoline and distillate. Repo headless browser is blocked by Cloudflare; curl_cffi works. Approach recommended, nothing coded, awaiting approval. |
| 2026-10-02 | Input 12 approved and built (`app/api_products.py`): scheduled Wednesday ~18:00 IST, retries every 5 min to ~19:45. Differences from the proposal: no DOM fallback (JSON only), a partial post is written when the other leg never appears, a complete file is not re-fetched without --force. Verified live on the 22 Sep post (gasoline -2.16, distillate -2.164, Cushing +2.082). |
| 2026-10-02 | Tiers 2 to 4 material moved to `docs/tiers_2_4.md` (Inputs 2, 9, 10 and the Cushing parts of Input 8 are now stubs or pointers); `README.md` rewritten as the Tier 1 runbook. Flow test on the 30 Sep release: NO TRADE (crude +0.56 against gasoline -2.93: crude too small for Setup C); the reason text was misleading and was fixed. |
| 2026-10-02 | `thresholds.json` pruned to the Tier 1 keys: removed `trigger_mb`, `veto_flow_ratio`, `veto_cushing_mb`, `veto_gas_ratio`, `entry_by_min`, `roll_within_days`, `max_spread_pct`, `min_delta`, `max_itm_strikes`, `strike_step`, `tp_points`, `sl_points`, `risk_pct`, `max_lots`, `lot_barrels` (the points-based sizing numbers are gone; the README percentage rules are the only sizing rules). peewee and groq kept in requirements.txt by decision. |

## Inputs still to come

To be filled as they arrive (candidates: entry and confirmation, vetoes, option selection, sizing, exits,
journal, data sources for MCX price and IV, output format).
