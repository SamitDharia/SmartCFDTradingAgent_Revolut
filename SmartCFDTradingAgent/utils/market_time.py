import pandas as pd
import pandas_market_calendars as mcal
from datetime import datetime, timezone

nyse = mcal.get_calendar("XNYS")

def next_session_open(now=None):
    now = now or datetime.now(timezone.utc)
    sched = nyse.schedule(start_date=now.date(), end_date=now.date() + mcal.utils.dpd(5))
    next_open = sched["market_open"].loc[sched["market_open"] > pd.Timestamp(now)].min()
    return next_open.tz_convert(timezone.utc) if pd.notna(next_open) else None

def market_open(now=None):
    now = now or datetime.now(timezone.utc)
    now_ts = pd.Timestamp(now)
    sched = nyse.schedule(start_date=now_ts.date(), end_date=now_ts.date())
    if sched.empty:
        return False
    market_open = sched['market_open'].iloc[0]
    market_close = sched['market_close'].iloc[0]
    return market_open <= now_ts <= market_close
