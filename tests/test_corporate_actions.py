from pathlib import Path

import pandas as pd

from equity_data_stack.corporate_actions import (
    apply_price_adjustments,
    apply_volume_adjustments,
    build_corporate_actions_tables,
    compute_dividend_factors,
    load_dividend_cash_table,
    load_split_ratio_table,
)


def test_build_and_load_corporate_actions_tables(tmp_path: Path) -> None:
    corp_dir = tmp_path / "corporate_actions"
    corp_dir.mkdir(parents=True, exist_ok=True)

    splits = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "execution_date": "2024-01-02",
                "split_from": 1,
                "split_to": 2,
            }
        ]
    )
    dividends = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "ex_dividend_date": "2024-01-03",
                "cash_amount": 1.0,
            }
        ]
    )
    splits.to_parquet(corp_dir / "splits.parquet", index=False)
    dividends.to_parquet(corp_dir / "dividends.parquet", index=False)

    split_path, dividend_path = build_corporate_actions_tables(tmp_path)
    assert split_path.exists()
    assert dividend_path.exists()

    split_ratios = load_split_ratio_table(tmp_path)
    dividend_cash = load_dividend_cash_table(tmp_path)
    assert "AAA" in split_ratios.columns
    assert "AAA" in dividend_cash.columns


def test_apply_price_and_volume_adjustments(tmp_path: Path) -> None:
    corp_dir = tmp_path / "corporate_actions"
    corp_dir.mkdir(parents=True, exist_ok=True)

    splits = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "execution_date": "2024-01-02",
                "split_from": 1,
                "split_to": 2,
            }
        ]
    )
    dividends = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "ex_dividend_date": "2024-01-03",
                "cash_amount": 1.0,
            }
        ]
    )
    splits.to_parquet(corp_dir / "splits.parquet", index=False)
    dividends.to_parquet(corp_dir / "dividends.parquet", index=False)

    build_corporate_actions_tables(tmp_path)
    split_ratios = load_split_ratio_table(tmp_path)
    dividend_cash = load_dividend_cash_table(tmp_path)

    prices = pd.DataFrame(
        {
            "AAA": [100.0, 120.0, 110.0],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
    )
    volumes = pd.DataFrame(
        {
            "AAA": [1000.0, 1200.0, 1100.0],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
    )

    adjusted_prices = apply_price_adjustments(prices, split_ratios, dividend_cash)
    adjusted_volumes = apply_volume_adjustments(volumes, split_ratios)

    dividend_ratio = (120.0 - 1.0) / 120.0
    expected_jan1 = 100.0 * 0.5 * dividend_ratio
    expected_jan2 = 120.0 * dividend_ratio
    expected_jan3 = 110.0

    assert adjusted_prices.loc[pd.Timestamp("2024-01-01"), "AAA"] == expected_jan1
    assert adjusted_prices.loc[pd.Timestamp("2024-01-02"), "AAA"] == expected_jan2
    assert adjusted_prices.loc[pd.Timestamp("2024-01-03"), "AAA"] == expected_jan3

    assert adjusted_volumes.loc[pd.Timestamp("2024-01-01"), "AAA"] == 2000.0
    assert adjusted_volumes.loc[pd.Timestamp("2024-01-02"), "AAA"] == 1200.0
    assert adjusted_volumes.loc[pd.Timestamp("2024-01-03"), "AAA"] == 1100.0


def test_dividend_factor_uses_previous_available_close() -> None:
    prices = pd.DataFrame(
        {"AAA": [100.0, None, 90.0]},
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
    )
    dividend_cash = pd.DataFrame(
        {"AAA": [1.0]},
        index=[pd.Timestamp("2024-01-03").date()],
    )

    factors = compute_dividend_factors(prices, dividend_cash)
    expected_ratio = (100.0 - 1.0) / 100.0

    assert factors.loc[pd.Timestamp("2024-01-01"), "AAA"] == expected_ratio
    assert factors.loc[pd.Timestamp("2024-01-02"), "AAA"] == expected_ratio
    assert factors.loc[pd.Timestamp("2024-01-03"), "AAA"] == 1.0
