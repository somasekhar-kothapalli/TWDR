# TWPR Lite: crude-first framework, no TLS or Z-score

**The idea:** one trigger number (the crude surprise), three vetoes, one price confirmation, then fixed option and risk rules. The whole calculation takes about 2 minutes with a calculator.

**Dropped from the full engine:** TLS weighting, Z-score and sigma history, the Cushing multiplier, Regimes 2 and 3 (fade and sell-the-fact), the scorecard, and OVX-based delta selection. What's left is momentum trades only, in the direction of the surprise.

---

## 1. Data points

**Sign convention:** a build is positive and a draw is negative, in millions of barrels (M bbl). A positive surprise is bearish; a negative surprise is bullish.

| # | Data point | Unit | When (IST, summer time) | Source |
|---|---|---|---|---|
| D1 | EIA crude consensus | M bbl | Tue evening | Investing.com calendar / Reuters poll |
| D2 | EIA gasoline consensus | M bbl | Tue evening | Same. If missing, use D4 |
| D3 | API crude change | M bbl | Wed ~02:00 | Investing.com calendar (API Weekly Crude Stock) |
| D4 | API gasoline change | M bbl | Wed ~02:00 | Same |
| D5 | MCX crude futures price (front month) | ₹ | 19:55 | Broker chart |
| D6 | Option expiry date and days left | date | Before 19:45 | MCX contract calendar (October options: 15 Oct) |
| D7 | Chosen strike: premium, bid, ask | ₹ | 19:45, rechecked 20:10 | Broker option chain |
| D8 | Capital and risk per trade | ₹, % | Fixed | You |
| D9 | EIA crude change | M bbl | 20:00 | EIA WPSR page (eia.gov/petroleum/supply/weekly) |
| D10 | EIA gasoline change | M bbl | 20:00 | Same |
| D11 | EIA Cushing change | M bbl | 20:00 | Same |
| D12 | Net crude imports change | thousand b/d | 20:00 | WPSR highlights / Table 1 |
| D13 | SPR change (a release is negative) | M bbl | 20:00 | WPSR Table 1 |
| D14 | High and low of the 20:00–20:05 candle | ₹ | 20:05 | Broker 5-minute chart |

That's 14 inputs, 6 of them arriving at 20:00.

---

## 2. Pre-release worksheet (19:45)

**Step 1: Expected numbers.** The market has already seen the API print, so split the difference between consensus and API:
- Expected crude (E_c) = (D1 + D3) ÷ 2
- Expected gasoline (E_g) = (D2 + D4) ÷ 2. If D2 is missing, use D4.

**Step 2: Write down the trigger levels.**
- **Bearish trade** needs EIA crude ≥ E_c + 3.0
- **Bullish trade** needs EIA crude ≤ E_c − 3.0
- Anything in between: no trade, and you're done at 20:01.

**Step 3: Pre-flight checks.** Skip the night if any of these fail:
- MCX's evening session is closed (holiday).
- Option expiry is 5 days away or fewer. In that case use the next month's options.
- The bid–ask spread on your strike is more than 5% of the premium.
- Major Iran or US headline news hits between 19:45 and 20:10.

---

## 3. At the release (20:00–20:02)

**Step 4: Trigger.** Crude surprise S = D9 − E_c.
- S ≥ +3.0: bearish, buy puts.
- S ≤ −3.0: bullish, buy calls.
- Otherwise: **NO TRADE.**

**Step 5: Three vetoes.** Any one of these means NO TRADE.

| Veto | Rule | Why it matters |
|---|---|---|
| **V1 Flows** | Underlying crude U = D9 − (D12 × 0.007) + D13. If U − E_c has flipped sign, or is less than half of S, veto. | The build or draw came from imports, exports or the SPR, not demand |
| **V2 Cushing** | D11 moves 1.0M or more in the direction opposite to S | WTI's delivery hub disagrees with the headline |
| **V3 Gasoline** | Gasoline surprise (D10 − E_g) has the opposite sign to S *and* at least half its size | Products cancel the crude signal |

---

## 4. Price confirmation (20:05–20:20)

**Step 6.** Wait for the 20:00–20:05 candle (D14) to close.
- **Bearish:** enter only on a 5-minute close **below the candle low**.
- **Bullish:** enter only on a 5-minute close **above the candle high**.
- If there's no break by 20:20, **NO TRADE**. The data said one thing and price didn't agree.

Entering after 20:05 also lets part of the post-release IV crush happen before you pay for the option.

---

## 5. Option selection

| Rule | Value |
|---|---|
| Expiry | Front month, unless 5 days or fewer remain; then the next month |
| Strike | 1–2 strikes in the money (₹50–100). Never more than 3 |
| Order | Limit order only. A missed fill costs nothing |

For a put, "in the money" means a strike above the futures price. For a call, a strike below it.

---

## 6. Risk and exits

**Position size**
- Lots = (Capital × 1%) ÷ (Premium × 30% × barrels per lot)
- Barrels per lot: 100 for CRUDEOIL, 10 for CRUDEOILM.
- **Example:** premium ₹320 means a stop of ₹96. On CRUDEOIL that's ₹9,600 risk per lot, so ₹10 lakh capital at 1% gives 1 lot. On CRUDEOILM it's ₹960 per lot, so 10 lots.
- If the result is less than 1 lot, don't trade. Don't round up.

**Exits (whichever comes first)**

| Exit | Rule |
|---|---|
| Stop | Premium falls 30%, *or* futures close a 5-minute bar back beyond the other side of the candle |
| Target 1 | Premium +40%: sell half and move the stop to breakeven |
| Time stop | 20:35. If you're not in profit, exit |
| Hard exit | 22:30. Everything closed |

**From 2 November** (US winter time), everything shifts one hour: release 21:00, entry window 21:10–21:20, time stop 21:35, hard exit 22:55.

---

## 7. Journal (after every Wednesday, trade or not)

Record: date, D1, D3, E_c, D9, S, U, which vetoes fired, decision, entry, exit, P&L, and **the largest futures move in the first 35 minutes**.

That last column is how you calibrate the model. After 10–15 weeks, compare it against S. If surprises of ±2.0 reliably moved futures ₹100 or more, lower the 3.0 trigger. If ±3.0 surprises often went nowhere, raise it.

---

## Last week's replay (September 23)

- E_c = (−0.641 + 1.786) ÷ 2 = **+0.57**
- S = 2.969 − 0.57 = **+2.40**, below 3.0, so **NO TRADE** at Step 4.
- V1 would also have vetoed: U = 2.969 − 2.58 − 0.4 = −0.01, and U − E_c = −0.58, which has flipped sign.
- The market was flat after the release, so the framework made the right call.

## Tonight (September 30)

Already calculated from the published consensus and API:

- E_c = (−1.9 + 1.019) ÷ 2 = **−0.44**
- **Bearish trigger:** EIA crude ≥ **+2.56M**
- **Bullish trigger:** EIA crude ≤ **−3.44M**
- E_g = +2.99. Gasoline consensus wasn't published as a number, so this is the API figure.

---

**Known limits.** The 3.0 trigger, the ½-size veto thresholds and the 30% / 40% exits are starting values, not backtested ones. The journal is what turns them into your numbers. The framework also knows nothing about geopolitics, which drives this market right now. That's why Step 6 requires price to confirm before you enter.

If you want to keep this as a runbook, I can turn it into a Claude Doc.