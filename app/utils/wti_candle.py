import logging
import argparse
import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
 
import pandas as pd
import yfinance as yf

import httpx

from app.utils.common import WTI_CANDLE_FILE, write_json

logger = logging.getLogger("twpr.eia_levels")

NY, IST = ZoneInfo("America/New_York"), ZoneInfo("Asia/Kolkata")
TICKER, RELEASE_ET = "CL=F", (10, 30)

def fetch(day):
    start = day - timedelta(days=1)
    df = yf.download(TICKER, start=start.isoformat(), end=(day + timedelta(days=2)).isoformat(),
                     interval="5m", progress=False, auto_adjust=False)
    if isinstance(df.columns, pd.MultiIndex):  # type: ignore # newer yfinance returns (field, ticker) columns
        df.columns = df.columns.get_level_values(0) # type: ignore # newer yfinance returns (field, ticker) columns
    if df.empty: # type: ignore # newer yfinance returns (field, ticker) columns
        sys.exit(f"No 5-minute data for {day}. Yahoo keeps ~60 days; older dates are gone.")
    df.index = (df.index.tz_localize("UTC") if df.index.tz is None else df.index).tz_convert(NY) # type: ignore # newer yfinance returns (field, ticker) columns
    return df
 
 
def release_candle(day):
    df = fetch(day)
    release = datetime(day.year, day.month, day.day, *RELEASE_ET, tzinfo=NY)
    try:
        bar, before = df.loc[release], df.loc[release - timedelta(minutes=5)] # type: ignore # newer yfinance returns (field, ticker) columns
    except KeyError:
        sys.exit(f"No bar at {release:%H:%M} ET on {day} (holiday, or the report moved that week).")
    payload =  {
        "release_date": day.strftime("%d-%m-%Y"),
        "release_ist": release.astimezone(IST).strftime("%H:%M"),
        "price_before_release": round(float(before["Open"]), 2),   # price 5 min before the release  # type: ignore # newer yfinance returns (field, ticker) columns
        "release_candle": {"high": round(float(bar["High"]), 2), "low": round(float(bar["Low"]), 2), "open": round(float(bar["Open"]), 2), "close": round(float(bar["Close"]), 2)},  # type: ignore # newer yfinance returns (field, ticker) columns  # type: ignore # newer yfinance returns (field, ticker) columns
        "unit": "USD/bbl, NYMEX WTI. Not MCX rupee levels.",
    }

    write_json(WTI_CANDLE_FILE, payload)
 