-- =====================================================================
-- Vismaya: EIA energy release surprise dataset
-- DuckDB schema, v1. Rebuildable from raw/ via pipeline; never hand-edit.
-- Phase 1 = WPSR + WNGSR (build now). Phase 3 = market reactions.
-- No FOREIGN KEYs on purpose: DuckDB's FK checks block updates on
-- referenced tables. Integrity is enforced by the checks in meta.v_orphans.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS wpsr;
CREATE SCHEMA IF NOT EXISTS wngsr;
CREATE SCHEMA IF NOT EXISTS market;
CREATE SCHEMA IF NOT EXISTS meta;

-- ---------------------------------------------------------------------
-- ref: reference data shared by all reports                  [Phase 1]
-- ---------------------------------------------------------------------

-- One row per expected release. Seeded from wpsr_expected_calendar_2011_2026.csv
CREATE TABLE IF NOT EXISTS ref.calendar (
  report_type            VARCHAR NOT NULL CHECK (report_type IN ('WPSR','WNGSR')),
  report_seq             INTEGER NOT NULL,
  week_ending            DATE    NOT NULL,   -- survey reference week (Friday)
  expected_release_utc   TIMESTAMPTZ NOT NULL,
  holiday_shift          BOOLEAN NOT NULL DEFAULT FALSE,
  holiday_name           VARCHAR,
  actual_release_utc     TIMESTAMPTZ,        -- from EIA archive only
  archive_file_found     BOOLEAN,
  covid_flag             BOOLEAN NOT NULL DEFAULT FALSE,  -- Mar-Jun 2020; exclude from test
  notes                  VARCHAR,
  PRIMARY KEY (report_type, report_seq)
);

-- Canonical dictionary of every field Vismaya knows about
CREATE TABLE IF NOT EXISTS ref.fields (
  report_type    VARCHAR NOT NULL,
  field          VARCHAR NOT NULL,   -- crude_stocks, crude_stocks_change, refinery_util, ...
  description    VARCHAR NOT NULL,
  unit           VARCHAR NOT NULL CHECK (unit IN ('thousand_barrels','thousand_bpd','percent','percentage_points','bcf','days')),
  eia_table      VARCHAR,            -- e.g. 'Table 1', 'Table 4'
  eia_series_id  VARCHAR,            -- EIA API v2 series id, for revised values
  tier           VARCHAR NOT NULL CHECK (tier IN ('must','should','nice')),
  has_consensus  BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (report_type, field)
);

-- Maps each source's URL slug to a canonical field (sites rename URLs)
CREATE TABLE IF NOT EXISTS ref.source_fields (
  source       VARCHAR NOT NULL CHECK (source IN ('investing_com','tradingeconomics')),
  source_slug  VARCHAR NOT NULL,     -- economic-calendar/gasoline-inventories-485
  report_type  VARCHAR NOT NULL,
  field        VARCHAR NOT NULL,
  unit         VARCHAR NOT NULL,     -- unit AFTER parsing (e.g. 'M' -> thousand_barrels x1000)
  scale_factor DOUBLE  NOT NULL DEFAULT 1,  -- multiply displayed number by this
  active       BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (source, source_slug)
);

-- Registry of every untouched download in raw/
CREATE TABLE IF NOT EXISTS ref.raw_files (
  sha256             VARCHAR PRIMARY KEY,
  raw_file           VARCHAR NOT NULL UNIQUE,   -- relative path under raw/
  source             VARCHAR NOT NULL,          -- eia_archive | eia_api | investing_com | tradingeconomics | broker
  url                VARCHAR,
  downloaded_at_utc  TIMESTAMPTZ NOT NULL,
  bytes              BIGINT,
  content_type       VARCHAR,
  source_tz          VARCHAR,                   -- tz the page displayed in, if any
  report_type        VARCHAR,
  report_seq         INTEGER                    -- NULL for multi-report files (e.g. history pages)
);

-- ---------------------------------------------------------------------
-- wpsr: Weekly Petroleum Status Report                       [Phase 1]
-- ---------------------------------------------------------------------

-- EIA numbers, long format: one row per report per field
CREATE TABLE IF NOT EXISTS wpsr.values (
  report_seq        INTEGER NOT NULL,
  field             VARCHAR NOT NULL,
  value_first       DOUBLE,          -- as published that week (archive) -> model inputs & labels
  value_revised     DOUBLE,          -- latest from EIA API -> context only
  revised_as_of     DATE,
  unit              VARCHAR NOT NULL,
  first_raw_sha256  VARCHAR,         -- archive file the first print came from
  PRIMARY KEY (report_seq, field)
);

-- Market expectations from Investing.com / TradingEconomics
CREATE TABLE IF NOT EXISTS wpsr.forecasts (
  report_seq       INTEGER NOT NULL,   -- matched to ref.calendar (+/-2 days)
  field            VARCHAR NOT NULL,
  source           VARCHAR NOT NULL CHECK (source IN ('investing_com','tradingeconomics')),
  source_slug      VARCHAR NOT NULL,
  release_date     DATE,               -- as shown by source (cross-check only)
  release_time     TIME,               -- as shown by source (cross-check only)
  source_tz        VARCHAR NOT NULL,
  actual           DOUBLE,             -- cross-check only, NEVER the EIA value
  forecast         DOUBLE,             -- NULL if blank, never 0
  previous         DOUBLE,
  unit             VARCHAR NOT NULL,
  captured_at_utc  TIMESTAMPTZ NOT NULL,
  raw_sha256       VARCHAR NOT NULL,
  PRIMARY KEY (report_seq, field, source, captured_at_utc)
);

-- EIA's own narrative text per report (Highlights, data notes) -> RAG
CREATE TABLE IF NOT EXISTS wpsr.texts (
  report_seq   INTEGER NOT NULL,
  text_type    VARCHAR NOT NULL CHECK (text_type IN ('highlights','data_note','revision_note')),
  content      VARCHAR NOT NULL,
  raw_sha256   VARCHAR NOT NULL,
  PRIMARY KEY (report_seq, text_type)
);

-- ---------------------------------------------------------------------
-- wngsr: Weekly Natural Gas Storage Report                   [Phase 1]
-- Not a mirror of wpsr: values are per REGION, units are Bcf, and EIA
-- reports reclassifications/revisions explicitly (net change vs implied flow).
-- ---------------------------------------------------------------------

-- Storage regions; scheme changed over time, so each region has validity dates
CREATE TABLE IF NOT EXISTS ref.regions (
  report_type    VARCHAR NOT NULL CHECK (report_type IN ('WPSR','WNGSR')),
  region         VARCHAR NOT NULL,   -- lower48, east, midwest, mountain, pacific,
                                     -- south_central, salt, nonsalt
  region_scheme  VARCHAR NOT NULL,   -- e.g. 'five_region' (current) / 'three_region' (older)
  parent_region  VARCHAR,            -- salt -> south_central -> lower48
  valid_from     DATE,               -- first week_ending this region is reported
  valid_to       DATE,               -- NULL = still reported
  description    VARCHAR,
  PRIMARY KEY (report_type, region, region_scheme)
);

-- EIA numbers, long format: one row per report per region per field
-- fields: working_gas, net_change, implied_flow, year_ago, five_yr_avg,
--         five_yr_max, five_yr_min (EIA-published values, point-in-time)
CREATE TABLE IF NOT EXISTS wngsr.values (
  report_seq        INTEGER NOT NULL,
  region            VARCHAR NOT NULL,
  field             VARCHAR NOT NULL,
  value_first       DOUBLE,          -- as published that week
  value_revised     DOUBLE,          -- latest from EIA API, context only
  revised_as_of     DATE,
  unit              VARCHAR NOT NULL CHECK (unit IN ('bcf','percent')),
  first_raw_sha256  VARCHAR,
  PRIMARY KEY (report_seq, region, field)
);

-- Explicit revisions/reclassifications EIA announces in a report
-- (why net_change differs from implied_flow that week)
CREATE TABLE IF NOT EXISTS wngsr.adjustments (
  report_seq       INTEGER NOT NULL,   -- report that announced it
  region           VARCHAR NOT NULL,
  adjustment_type  VARCHAR NOT NULL CHECK (adjustment_type IN ('reclassification','revision')),
  amount_bcf       DOUBLE  NOT NULL,   -- signed
  affects_week     DATE,               -- week_ending the change applies to, if stated
  description      VARCHAR,
  raw_sha256       VARCHAR NOT NULL,
  PRIMARY KEY (report_seq, region, adjustment_type)
);

-- Market expectations (usually only lower48 net_change has consensus)
CREATE TABLE IF NOT EXISTS wngsr.forecasts (
  report_seq       INTEGER NOT NULL,
  region           VARCHAR NOT NULL DEFAULT 'lower48',
  field            VARCHAR NOT NULL,   -- net_change
  source           VARCHAR NOT NULL CHECK (source IN ('investing_com','tradingeconomics')),
  source_slug      VARCHAR NOT NULL,
  release_date     DATE,
  release_time     TIME,
  source_tz        VARCHAR NOT NULL,
  actual           DOUBLE,             -- cross-check only, NEVER the EIA value
  forecast         DOUBLE,             -- NULL if blank, never 0
  previous         DOUBLE,
  unit             VARCHAR NOT NULL CHECK (unit IN ('bcf')),
  captured_at_utc  TIMESTAMPTZ NOT NULL,
  raw_sha256       VARCHAR NOT NULL,
  PRIMARY KEY (report_seq, region, field, source, captured_at_utc)
);

-- EIA narrative text per report -> RAG
CREATE TABLE IF NOT EXISTS wngsr.texts (
  report_seq   INTEGER NOT NULL,
  text_type    VARCHAR NOT NULL CHECK (text_type IN ('summary','data_note','revision_note','reclassification_note')),
  content      VARCHAR NOT NULL,
  raw_sha256   VARCHAR NOT NULL,
  PRIMARY KEY (report_seq, text_type)
);
-- ---------------------------------------------------------------------

-- ---------------------------------------------------------------------
-- market: prices and reaction labels                         [Phase 3]
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS market.instruments (
  symbol       VARCHAR PRIMARY KEY,   -- CL, BZ, RB, HO, NG, MCX_CRUDEOIL, MCX_NATURALGAS, USDINR
  exchange     VARCHAR NOT NULL,      -- NYMEX, ICE, MCX, NSE
  description  VARCHAR NOT NULL,
  currency     VARCHAR NOT NULL,
  exchange_tz  VARCHAR NOT NULL,
  roll_rule    VARCHAR                -- how front month is chosen
);

-- Raw price bars (minute for live capture, daily for backfill)
CREATE TABLE IF NOT EXISTS market.bars (
  symbol       VARCHAR NOT NULL,
  contract     VARCHAR NOT NULL,      -- CLZ26, CRUDEOIL26NOVFUT
  granularity  VARCHAR NOT NULL CHECK (granularity IN ('1m','5m','1d')),
  ts_utc       TIMESTAMPTZ NOT NULL,  -- bar open time
  open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
  volume       DOUBLE,
  open_interest DOUBLE,
  source       VARCHAR NOT NULL,
  PRIMARY KEY (symbol, contract, granularity, ts_utc, source)
);

-- Reaction labels per release per instrument
CREATE TABLE IF NOT EXISTS market.reactions (
  report_type        VARCHAR NOT NULL,
  report_seq         INTEGER NOT NULL,
  symbol             VARCHAR NOT NULL,
  contract           VARCHAR NOT NULL,
  label_granularity  VARCHAR NOT NULL CHECK (label_granularity IN ('minute','daily')),
  baseline_ts_utc    TIMESTAMPTZ NOT NULL,   -- release - 5 min (or prior close for daily)
  baseline_price     DOUBLE NOT NULL,
  ret_1m DOUBLE, ret_5m DOUBLE, ret_15m DOUBLE, ret_30m DOUBLE, ret_60m DOUBLE,
  ret_close          DOUBLE,
  range_15m_pct      DOUBLE,                 -- whipsaw measure
  PRIMARY KEY (report_type, report_seq, symbol, label_granularity)
);

-- ---------------------------------------------------------------------
-- meta: lineage and versioning                               [Phase 1]
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS meta.pipeline_runs (
  run_id          VARCHAR PRIMARY KEY,     -- uuid
  script          VARCHAR NOT NULL,
  git_commit      VARCHAR,
  started_at_utc  TIMESTAMPTZ NOT NULL,
  finished_at_utc TIMESTAMPTZ,
  status          VARCHAR CHECK (status IN ('running','success','failed')),
  rows_loaded     BIGINT,
  message         VARCHAR
);

CREATE TABLE IF NOT EXISTS meta.dataset_versions (
  version         VARCHAR PRIMARY KEY,     -- vismaya-v1-2026-10-20
  created_at_utc  TIMESTAMPTZ NOT NULL,
  git_commit      VARCHAR,
  export_path     VARCHAR NOT NULL,
  row_counts      JSON,                    -- {"wpsr.values": 41280, ...}
  notes           VARCHAR
);

-- ---------------------------------------------------------------------
-- Views: derived, never stored
-- ---------------------------------------------------------------------

-- Latest capture per source, then median across sources = consensus
CREATE OR REPLACE VIEW wpsr.v_consensus AS
WITH latest AS (
  SELECT *, row_number() OVER (PARTITION BY report_seq, field, source
                               ORDER BY captured_at_utc DESC) AS rn
  FROM wpsr.forecasts WHERE forecast IS NOT NULL
)
SELECT report_seq, field,
       median(forecast)      AS consensus,
       count(*)              AS n_sources,
       list(source ORDER BY source) AS sources
FROM latest WHERE rn = 1
GROUP BY report_seq, field;

-- Surprise = EIA first print - consensus
CREATE OR REPLACE VIEW wpsr.v_surprise AS
SELECT k.report_seq, cal.week_ending, cal.actual_release_utc,
       k.field, v.value_first AS actual_first, k.consensus, k.n_sources,
       v.value_first - k.consensus AS surprise
FROM wpsr.v_consensus k
JOIN wpsr.values v ON v.report_seq = k.report_seq AND v.field = k.field
JOIN ref.calendar cal ON cal.report_type = 'WPSR' AND cal.report_seq = k.report_seq;

-- Was each forecast captured before release (live) or after (backfill)?
CREATE OR REPLACE VIEW wpsr.v_forecast_quality AS
SELECT f.*,
       CASE WHEN cal.actual_release_utc IS NULL THEN 'unknown_release'
            WHEN f.captured_at_utc < cal.actual_release_utc THEN 'live'
            ELSE 'backfill_asof_unknown' END AS quality
FROM wpsr.forecasts f
JOIN ref.calendar cal ON cal.report_type = 'WPSR' AND cal.report_seq = f.report_seq;

-- Source 'actual' vs EIA first print: mismatches = parsing errors somewhere
CREATE OR REPLACE VIEW wpsr.v_actual_mismatch AS
SELECT f.report_seq, f.field, f.source, f.actual AS source_actual,
       v.value_first, f.actual - v.value_first AS diff
FROM wpsr.forecasts f
JOIN wpsr.values v USING (report_seq, field)
WHERE f.actual IS NOT NULL AND abs(f.actual - v.value_first) > 1e-6;

-- WNGSR: latest capture per source, median across sources
CREATE OR REPLACE VIEW wngsr.v_consensus AS
WITH latest AS (
  SELECT *, row_number() OVER (PARTITION BY report_seq, region, field, source
                               ORDER BY captured_at_utc DESC) AS rn
  FROM wngsr.forecasts WHERE forecast IS NOT NULL
)
SELECT report_seq, region, field,
       median(forecast) AS consensus,
       count(*)         AS n_sources,
       list(source ORDER BY source) AS sources
FROM latest WHERE rn = 1
GROUP BY report_seq, region, field;

-- WNGSR surprise. Also shows implied_flow, because a reclassification can
-- make net_change misleading for that week.
CREATE OR REPLACE VIEW wngsr.v_surprise AS
SELECT k.report_seq, cal.week_ending, cal.actual_release_utc,
       k.region, k.field, v.value_first AS actual_first,
       f.value_first AS implied_flow_first,
       k.consensus, k.n_sources,
       v.value_first - k.consensus AS surprise,
       (SELECT count(*) FROM wngsr.adjustments a
         WHERE a.report_seq = k.report_seq
           AND (a.region = k.region OR k.region = 'lower48')) > 0 AS has_adjustment  -- lower48 includes every region
FROM wngsr.v_consensus k
JOIN wngsr.values v ON v.report_seq = k.report_seq AND v.region = k.region AND v.field = k.field
LEFT JOIN wngsr.values f ON f.report_seq = k.report_seq AND f.region = k.region AND f.field = 'implied_flow'
JOIN ref.calendar cal ON cal.report_type = 'WNGSR' AND cal.report_seq = k.report_seq;

CREATE OR REPLACE VIEW wngsr.v_forecast_quality AS
SELECT f.*,
       CASE WHEN cal.actual_release_utc IS NULL THEN 'unknown_release'
            WHEN f.captured_at_utc < cal.actual_release_utc THEN 'live'
            ELSE 'backfill_asof_unknown' END AS quality
FROM wngsr.forecasts f
JOIN ref.calendar cal ON cal.report_type = 'WNGSR' AND cal.report_seq = f.report_seq;

CREATE OR REPLACE VIEW wngsr.v_actual_mismatch AS
SELECT f.report_seq, f.region, f.field, f.source, f.actual AS source_actual,
       v.value_first, f.actual - v.value_first AS diff
FROM wngsr.forecasts f
JOIN wngsr.values v USING (report_seq, region, field)
WHERE f.actual IS NOT NULL AND abs(f.actual - v.value_first) > 1e-6;

-- Integrity checks replacing foreign keys: every row should return 0
CREATE OR REPLACE VIEW meta.v_orphans AS
SELECT 'wpsr.values without calendar' AS check_name, count(*) AS n
  FROM wpsr.values v ANTI JOIN ref.calendar c
  ON c.report_type='WPSR' AND c.report_seq=v.report_seq
UNION ALL
SELECT 'wpsr.forecasts without calendar', count(*)
  FROM wpsr.forecasts f ANTI JOIN ref.calendar c
  ON c.report_type='WPSR' AND c.report_seq=f.report_seq
UNION ALL
SELECT 'wpsr.values with unknown field', count(*)
  FROM wpsr.values v ANTI JOIN ref.fields r
  ON r.report_type='WPSR' AND r.field=v.field
UNION ALL
SELECT 'wpsr.forecasts with unknown raw file', count(*)
  FROM wpsr.forecasts f ANTI JOIN ref.raw_files r ON r.sha256=f.raw_sha256
UNION ALL
SELECT 'wngsr.values without calendar', count(*)
  FROM wngsr.values v ANTI JOIN ref.calendar c
  ON c.report_type='WNGSR' AND c.report_seq=v.report_seq
UNION ALL
SELECT 'wngsr.forecasts without calendar', count(*)
  FROM wngsr.forecasts f ANTI JOIN ref.calendar c
  ON c.report_type='WNGSR' AND c.report_seq=f.report_seq
UNION ALL
SELECT 'wngsr.values with unknown region', count(*)
  FROM wngsr.values v ANTI JOIN ref.regions r
  ON r.report_type='WNGSR' AND r.region=v.region
UNION ALL
SELECT 'wngsr.values with unknown field', count(*)
  FROM wngsr.values v ANTI JOIN ref.fields r
  ON r.report_type='WNGSR' AND r.field=v.field
UNION ALL
SELECT 'wngsr.forecasts with unknown raw file', count(*)
  FROM wngsr.forecasts f ANTI JOIN ref.raw_files r ON r.sha256=f.raw_sha256
UNION ALL
SELECT 'calendar rows missing archive file (' || report_type || ')', count(*)
  FROM ref.calendar WHERE archive_file_found IS NOT TRUE
  GROUP BY report_type;
