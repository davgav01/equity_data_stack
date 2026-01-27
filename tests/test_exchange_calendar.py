from datetime import date

import pandas as pd
import pytest

from equity_data_stack import exchange_calendar as ec


def test_get_trading_days_basic_range():
    start = date(2024, 2, 1)  # Thu
    end = date(2024, 2, 7)  # Wed

    days = ec.get_trading_days(start, end)

    assert days == [
        date(2024, 2, 1),
        date(2024, 2, 2),
        date(2024, 2, 5),
        date(2024, 2, 6),
        date(2024, 2, 7),
    ]


def test_is_trading_day_weekend_false():
    assert ec.is_trading_day(date(2024, 2, 3)) is False  # Saturday


def test_is_trading_day_weekday_true():
    assert ec.is_trading_day(date(2024, 2, 6)) is True  # Tuesday


def test_session_open_close_trading_day():
    trading_day = date(2024, 2, 6)

    open_ts = ec.get_session_open(trading_day)
    close_ts = ec.get_session_close(trading_day)

    assert isinstance(open_ts, pd.Timestamp)
    assert isinstance(close_ts, pd.Timestamp)
    assert open_ts.tzinfo is not None
    assert close_ts.tzinfo is not None
    assert open_ts < close_ts


def test_session_open_close_non_trading_day_raises():
    non_trading_day = date(2024, 2, 3)  # Saturday

    with pytest.raises(ValueError, match="not a trading day"):
        ec.get_session_open(non_trading_day)

    with pytest.raises(ValueError, match="not a trading day"):
        ec.get_session_close(non_trading_day)


def test_get_next_trading_day_same_day_when_session():
    trading_day = date(2024, 2, 6)  # Tuesday
    assert ec.get_next_trading_day(trading_day) == trading_day


def test_get_next_trading_day_from_weekend():
    saturday = date(2024, 2, 3)
    assert ec.get_next_trading_day(saturday) == date(2024, 2, 5)


def test_get_strictly_next_trading_day_from_session():
    trading_day = date(2024, 2, 6)  # Tuesday
    assert ec.get_strictly_next_trading_day(trading_day) == date(2024, 2, 7)


def test_get_strictly_next_trading_day_from_weekend():
    saturday = date(2024, 2, 3)
    assert ec.get_strictly_next_trading_day(saturday) == date(2024, 2, 5)


def test_get_previous_trading_day():
    monday = date(2024, 2, 5)
    assert ec.get_previous_trading_day(monday) == date(2024, 2, 2)
