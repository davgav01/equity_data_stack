"""NYSE trading calendar utilities.

Functions for working with NYSE trading days via exchange_calendars.

Notes on Sessions:

- A session date is a pandas timestamp with date of that day and
    time of 00:00:00.
- Session open is the first minute of a trading day
- Session close is the last minute of a trading day


References:
    https://pypi.org/project/exchange-calendars
"""

from datetime import UTC, date, datetime
from functools import lru_cache

import exchange_calendars as xcals
import pandas as pd

NYSE_EXCHANGE_CODE = "XNYS"


@lru_cache(maxsize=1)
def _get_nyse_calendar() -> xcals.ExchangeCalendar:
    """Cached function for retrieving the NYSE calendar"""
    return xcals.get_calendar(NYSE_EXCHANGE_CODE)


def get_trading_days(start: date, end: date) -> list[date]:
    """Get all valid trading dates in a date range"""
    cal = _get_nyse_calendar()

    sessions = cal.sessions_in_range(start, end)
    trading_days = [ts.date() for ts in sessions]

    return trading_days


def is_trading_day(input_date: date) -> bool:
    """Check if a date is a trading day"""
    cal = _get_nyse_calendar()
    return cal.is_session(input_date)


def get_session_open(input_date: date) -> pd.Timestamp:
    """Get the open of a trading day"""
    cal = _get_nyse_calendar()

    if cal.is_session(input_date):
        return cal.session_open(input_date)

    raise ValueError(f"{input_date} is not a trading day")


def get_session_close(input_date: date) -> pd.Timestamp:
    """Get the close of a trading day"""
    cal = _get_nyse_calendar()

    if cal.is_session(input_date):
        return cal.session_close(input_date)

    raise ValueError(f"{input_date} is not a trading day")


def get_next_trading_day(input_date: date | None = None) -> date:
    """Get the next trading day on or after a given date."""
    cal = _get_nyse_calendar()

    if input_date is None:
        input_date = datetime.now(UTC).date()

    # This will move to the next session if input_date is not a session.
    next_session = cal.date_to_session(input_date, direction="next")
    return next_session.date()


def get_strictly_next_trading_day(input_date: date) -> date:
    """Get the next trading day strictly after a given date.

    If input_date is a trading day, return the following trading day.
    If input_date is not a trading day, return the first trading day after it.
    """
    cal = _get_nyse_calendar()

    if cal.is_session(input_date):
        # input_date is a trading session; move to the *next* session
        return cal.next_session(input_date).date()

    # input_date is not a trading session; find the next session after it
    return get_next_trading_day(input_date)


def get_previous_trading_day(input_date: date) -> date:
    cal = _get_nyse_calendar()
    return cal.previous_session(input_date).date()


if __name__ == "__main__":
    test_start = date(2024, 1, 1)
    test_end = date(2024, 1, 11)

    trading_days = get_trading_days(test_start, test_end)
    print(trading_days)

    print(is_trading_day(test_start))
    print(is_trading_day(test_end))

    print("Session open of test_start:")
    print(get_session_open(test_end))
    print("Session close of test_end:")
    print(get_session_close(test_end))

    print(f"Next trading day after {test_start}:")
    print(get_next_trading_day(test_start))
    print("Previous trading day of test_end:")
    print(get_previous_trading_day(test_end))
