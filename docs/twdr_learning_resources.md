# TWDR learning resources: MCX, WTI, EIA, API, options

Compiled 30 Sep 2026 for the TWDR (crude oil, natural gas) setup.

**How this list was built.** Web links come from searches run in this conversation. YouTube picks are chosen from titles, descriptions and timestamps; they have not been watched in full. Books are listed from general knowledge and have no links. Where a link was not confirmed in search, it says so.

---

## 1. Suggested order

| When | Do this |
|---|---|
| Week 1 | Varsity crude chapters and the Karthik Rangappa video; read the MCX options spec for the contract month you trade |
| Week 2 | CME "Introduction to Crude Oil" course; EIA WPSR Appendix B; the Energy Rogue WPSR video |
| Weeks 3-4 | Euan Sinclair conversations (below), then Natenberg on volatility and the Greeks |
| Before building TWDR-NG | EIA natural gas storage methodology and the two gas storage videos |
| Ongoing | Weekly: MCX circulars, EIA *This Week in Petroleum*, OPEC+ calendar |

---

## 2. MCX contracts and options

### Official
- **MCX Crude Oil product page** (specs, product leaflets, options PDFs): https://www.mcxindia.com/products/energy/crude-oil
  - Lists options specs by contract start (e.g. "March 2026 Contract Onwards"). Read the one that matches your expiry.
- **MCX option chain**: https://www.mcxindia.com/market-data/option-chain
- **Older options spec (Jan 2020 onwards), for reference only**: https://www.mcxindia.com/docs/default-source/products/contract-specification/crude-oil-options/crude-oil-(100-barrels)-options-january-2020-onwards.pdf?sfvrsn=e237b090_0
- **MCX Awareness Corner and Options Calculator**: linked from the MCX site menu under Options (exact URL not retrieved).

### Zerodha Varsity
- **Commodities, Currency and Government Securities module** (chapters 10-12 are the crude oil series): https://zerodha.com/varsity/module/commodities-currency-government-securities/
- **Crude Oil Part 3: the crude oil contract** (lot sizes, expiry logic, margins, arbitrage): https://zerodha.com/varsity/chapter/crude-oil-part-3-the-crude-oil-contract/
- **All Varsity modules** (includes the Option Theory module; direct module URL not confirmed in search): https://zerodha.com/varsity/modules/
- **Zerodha commodities page** (margin calculator, option chain, continuous futures charts): https://zerodha.com/commodities/

### Broker and third-party guides (secondary)
- Sahi, MCX crude guide (margins, lot sizes, risks): https://www.sahi.com/blogs/crude-oil-trading-mcx-guide
- Sahi, MCX crude beginners' guide 2026: https://www.sahi.com/blogs/crude-oil-trading-on-mcx-beginners-guide-2026
- Navia, MCX crude specs and WTI vs Brent: https://navia.co.in/blog/crude-oil-on-mcx-specs-insights-market-dynamics/
- Stoxbox, MCX crude contract details, expiry logic: https://stoxbox.in/marketopedia/currency-commodities-trading/crude-oil-mcx/
- NiftyTrader, live MCX crude option chain with OI and IV: https://www.niftytrader.in/commodities-option-chain-nse/crudeoil

---

## 3. WTI and the crude market

### CME Group
- **Introduction to Crude Oil (free course)**: https://www.cmegroup.com/education/courses/introduction-to-crude-oil
- **WTI weekly options** (designed partly for midweek releases like the EIA report): https://www.cmegroup.com/education/courses/introduction-to-crude-oil/product-overview/monday-and-wednesday-weekly-options-on-wti-crude-oil-futures.html
- **WTI Crude Oil overview, including CVOL** (30-day implied volatility index for WTI): https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.html
- **Crude Oil futures and options hub**: https://www.cmegroup.com/markets/energy/crude-oil.html
- **Basic principles of Micro WTI futures**: https://www.cmegroup.com/education/courses/basic-principles-of-micro-wti-crude-oil-futures
- **Micro WTI futures overview**: https://www.cmegroup.com/education/courses/understanding-micro-futures-contracts-at-cme-group/micro-crude-futures/micro-wti-crude-oil-futures-overview.html

### Books (no links; from general knowledge)
- *Oil 101*, Morgan Downey: how the physical market works, from well to refinery to pricing.

---

## 4. EIA reports

### Weekly Petroleum Status Report (WPSR)
- **WPSR main page** (every release, archive, appendices, holiday schedule): https://eia.gov/petroleum/supply/weekly
- **Appendix B: Explanatory Notes and Detailed Methods** (how each number is estimated, including exports and the adjustment factor): https://www.eia.gov/petroleum/supply/weekly/pdf/appendixb.pdf
- **WPSR Sources** (how each table is built): https://eia.gov/petroleum/supply/weekly/pdf/sources.pdf
- **"EIA now using near-real-time export data"** (why exports distort both stocks and implied demand): https://www.eia.gov/todayinenergy/detail.php?id=27752
- **Petroleum Supply Monthly explanatory notes** (for reconciling weekly vs monthly data): https://www.eia.gov/petroleum/supply/monthly/pdf/psmnotes.pdf
- **Short-Term Energy Outlook** (monthly; next release Oct 6, 2026): https://www.eia.gov/outlooks/steo/report/petro_prod.php
- **This Week in Petroleum**: EIA's Wednesday written commentary on the report (link not retrieved; find it under the WPSR page).

### Natural gas storage (for TWDR-NG)
- **Methodology for EIA weekly underground natural gas storage estimates**: https://ir.eia.gov/ngs/methodology.html
- **Weekly Natural Gas Storage Report** (Thursday, 10:30 ET): https://ir.eia.gov/ngs/ngs.html
- **EIA natural gas storage overview**: https://www.eia.gov/naturalgas/storage/
- **Sampling variability in the storage estimates**: https://www.eia.gov/todayinenergy/detail.php?id=29712

---

## 5. API weekly survey (Tuesday)

- **API Weekly Statistical Bulletin**: https://www.api.org/energy-insights/statistics/wsb
  - API states that its Q1 2025 crude, gasoline and distillate stock levels matched EIA within 1%. That compares levels, not weekly changes, which can still disagree.
- **API weekly crude stock, live calendar** (Investing.com event 656): https://www.investing.com/economic-calendar/api-weekly-crude-stock-656
- **API crude stock change, history and consensus** (Trading Economics): https://tradingeconomics.com/united-states/api-crude-oil-stock-change
- **EIA crude inventories, calendar** (Investing.com event 75): https://www.investing.com/economic-calendar/eia-crude-oil-inventories-75
- **EIA crude stocks change, history** (Trading Economics): https://tradingeconomics.com/united-states/crude-oil-stocks-change

---

## 6. OPEC+, positioning and market commentary

- **OPEC press release, 6 Sep 2026 meeting** (core-7 kept October output unchanged; next meeting 4 Oct 2026): https://www.opec.org/pr-detail/1835613-6-september-2026.html
- **CFTC Commitments of Traders**: https://www.cftc.gov (exact report page not retrieved). Read the "disaggregated" explanation before building the fetcher; managed money is your crowding signal.
- **Kotak Securities via Business Standard, "Crude Oil at crossroads" (30 Sep 2026)**: https://www.business-standard.com/markets/commodities/crude-oil-at-crossroads-as-supply-recovery-meets-geopolitical-risk-in-october-126093000562_1.html
- **OilPrice.com** (daily headlines, API/EIA summaries): https://oilprice.com
- **Rigzone weekly EIA summaries**: https://www.rigzone.com
- **Baker Hughes rig count** (Fridays): https://rigcount.bakerhughes.com (not retrieved in search)
- **RBI USD/INR reference rate**: on rbi.org.in. MCX converts NYMEX WTI with the last RBI reference rate for final settlement.

---

## 7. Options and volatility

### Books (no links; from general knowledge)
- **Sheldon Natenberg, *Option Volatility and Pricing***: the standard reference. Start with volatility, the Greeks and risk.
- **Euan Sinclair, *Volatility Trading***: implied vs realized volatility, the variance premium, sizing.
- **Euan Sinclair, *Positional Option Trading***: closest to your setup (event volatility, when stops help or hurt).
- **John Hull, *Options, Futures, and Other Derivatives***: a reference for Black-76, the model your `options.py` uses.

---

## 8. YouTube videos

### MCX, crude oil and natural gas
- **Trading Crude Oil & Natural Gas on MCX**, Zerodha Varsity, 14 min: https://www.youtube.com/watch?v=rcQN4h3T_tY
  - Best starting point. Inventory data from 5:51, technical analysis from 11:18, natural gas from 11:40.
- **How to Trade Crude Oil Using Futures and Options?**, Trading with Groww, 14 min: https://www.youtube.com/watch?v=lYc32tH-yoA
- **Varsity: Complete Guide to Options Trading (playlist)**: https://youtube.com/playlist?list=PLX2SHiKfualFiusiT9G5uE9jU3vetvW2x
- **Varsity: Complete Guide to Futures Trading (playlist)**: https://youtube.com/playlist?list=PLX2SHiKfualFUupnwJajd2DQhSvvvUwTe
- **Varsity: Technical Analysis (playlist)**: https://youtube.com/playlist?list=PLX2SHiKfualH_xMbGM-3zWC47s9gUjGR_

### WTI and CME
- **What is WTI Crude Oil?**, CME Group, 4 min: https://www.youtube.com/watch?v=NgX2HYEYBWw
- **Product: WTI Crude Oil**, CME Group, 2 min: https://www.youtube.com/watch?v=1Qaedrdfmi4
- **Crude Oil: Futures vs. ETFs**, CME Group, 4 min: https://www.youtube.com/watch?v=bstH4PIYhNM
- **Crude Oil Futures Explained: Two Sizes, One Benchmark**, tastylive x CME, 12 min (2026): https://www.youtube.com/watch?v=Nbd9Q091uuU
  - Contract sizes, how SPAN margin changes when volatility spikes, CME's OPEC Watch tool.
- **Understanding Options on Micro WTI Crude Oil Futures**, CME Group, 2 min: https://www.youtube.com/watch?v=Ebk53QVpkBE
- **Why It Might Finally Be Time to Sell Upside in Crude Oil**, tastylive, 5 min (28 Sep 2026): https://www.youtube.com/watch?v=3RA-jKrtG_w
  - The other side of your trade: a seller's view of the current crude regime.

### EIA reports
- **How to Read the EIA Weekly Petroleum Status Report**, Energy Rogue, 34 min (2026): https://www.youtube.com/watch?v=i6-hEqOOhWg
  - Stocks vs SPR, refinery utilization, crack spreads, imports and exports. Small channel; the channel also sells a paid product.
- **How To Read The Weekly EIA Natural Gas & Crude Oil Reports**, Ricky Gutierrez, 7 min: https://www.youtube.com/watch?v=wJxLcHna4z4
  - Quick orientation only (2019).

### Natural gas storage (TWDR-NG)
- **Why the EIA Storage Report Moves Markets**, ELK Trading, 3 min (2026): https://www.youtube.com/watch?v=58e0jM-i_j0
- **How To Read Natural Gas Storage Report Accurately**, Money Markers, 9 min: https://www.youtube.com/watch?v=25S7vdF2US0

### Options and volatility
- **30 Years of Options Trading: The Truth About What Actually Works**, Groww x Euan Sinclair, 71 min (2026): https://www.youtube.com/watch?v=Rzae3gyhpwc
  - Watch 44:50 (stops: when they help vs hurt) and 1:06:43 (why event trades are operationally dangerous).
- **Find Edge and Trade Volatility with Euan Sinclair**, Outlier Trading, 62 min: https://www.youtube.com/watch?v=YDA449Fkwj4
- **Euan Sinclair on How to Build Options Strategies That Work**, Outlier Trading, 63 min: https://www.youtube.com/watch?v=uOY6kRco6r4
- **Euan Sinclair: The Man Who Wrote The Book On Volatility Trading**, The Sophron Network, 57 min (2026): https://www.youtube.com/watch?v=9cLs5VvaYdM
  - Model edge vs situation edge; theta is not an edge.
- **Options Volatility Trading: Concepts & Strategies (course intro)**, Quantra, 5 min: https://www.youtube.com/watch?v=qX8_zBXoeGo
- **The ONLY Options Trading Course You Need**, Volatility Vibes, 3.5 hr (2026): https://www.youtube.com/watch?v=D_FZCL8A32U
  - Greeks from 52:12, implied vs realized volatility from 1:38:32. Leans toward option selling.
- **Sheldon Natenberg interview**, tastylive, 19 min: https://www.youtube.com/watch?v=dfXzwZ8Zl3M

### Positioning
- **COT Report Best Practices**, Barchart x Carley Garner, 12 min: https://www.youtube.com/watch?v=GcZ6pXFTYaA

### Broker-made MCX crude strategy videos (use with care)
These are indicator and price-action strategy videos from a broker channel (Dhan). They are not related to the inventory-surprise method, and they promote the broker's products.
- Crude Oil Trading Strategy for Every Market Condition, 8 min (Sep 2026): https://www.youtube.com/watch?v=T8069pp8grc
- Crude Mini Trading Using Options Chart, 11 min: https://www.youtube.com/watch?v=jf7K_ogAxaY
- Crude Oil Intraday Trading Strategy, 11 min: https://www.youtube.com/watch?v=ZniDTRbVMsw

---

## 9. Weekly routine (sources to check)

| Day | Source | Why |
|---|---|---|
| Sun / Mon | OPEC+ calendar (next: Sun 4 Oct 2026) | Weekend gap risk |
| Mon | MCX circulars, holiday list | Margin changes, session timings, closed evening sessions |
| Tue night | API survey (Investing.com / Trading Economics) | Feeds the "expected" number |
| Wed | EIA WPSR, *This Week in Petroleum* | The release itself and EIA's own commentary |
| Thu | EIA natural gas storage | TWDR-NG |
| Fri | Baker Hughes rig count, CFTC COT | Slow-moving positioning and supply signals |
| Monthly | EIA STEO (next: 6 Oct 2026), MCX contract calendar | Backdrop and expiry dates |

---

## 10. Base-rate reminder

SEBI's own study of the equity derivatives segment found that about nine in ten individual F&O traders lose money. It covers equity F&O, not commodities specifically, but it is the right prior to hold yourself against. Keep a journal, size small, and treat "no trade" as a valid weekly outcome.
