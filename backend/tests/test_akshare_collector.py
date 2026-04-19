import pandas as pd

from app.services.akshare_collector import (
    AkshareCollector,
    _effective_min_turnover,
    _market_prefixed_symbol,
)
from app.services.market_environment_service import build_sample_benchmark_records
from app.services.sample_market import build_demo_snapshot_records


def test_build_spot_frame_maps_fields_and_sorts_by_amount() -> None:
    frame = AkshareCollector._build_spot_frame(
        frame=pd.DataFrame(
            [
                {
                    "f2": 15.2,
                    "f3": 2.1,
                    "f5": 1000,
                    "f6": 2300000000,
                    "f8": 4.2,
                    "f9": 18.6,
                    "f10": 1.4,
                    "f12": "2",
                    "f14": "万科A",
                    "f20": 120000000000,
                },
                {
                    "f2": 162.3,
                    "f3": 3.2,
                    "f5": 2000,
                    "f6": 9800000000,
                    "f8": 5.1,
                    "f9": 28.4,
                    "f10": 1.8,
                    "f12": "300308",
                    "f14": "中际旭创",
                    "f20": 182000000000,
                },
            ]
        )
    )

    assert frame.iloc[0]["代码"] == "300308"
    assert frame.iloc[0]["名称"] == "中际旭创"
    assert frame.iloc[1]["代码"] == "000002"
    assert "成交额" in frame.columns
    assert int(frame.iloc[0]["序号"]) == 1


def test_build_sina_spot_frame_maps_turnover_and_market_cap() -> None:
    frame = AkshareCollector._build_sina_spot_frame(
        pd.DataFrame(
            [
                {
                    "code": "300308",
                    "name": "中际旭创",
                    "trade": "606.520",
                    "changepercent": 4.213,
                    "volume": 29027106,
                    "amount": 17694513705,
                    "turnoverratio": 2.6257,
                    "per": 61.89,
                    "open": "600.000",
                    "high": "625.000",
                    "low": "594.350",
                    "settlement": "582.000",
                    "mktcap": 67391549.193768,
                    "nmc": 67050730.321464,
                }
            ]
        )
    )

    assert frame.iloc[0]["代码"] == "300308"
    assert frame.iloc[0]["换手率"] == 2.6257
    assert frame.iloc[0]["量比"] == 1.0
    assert round(float(frame.iloc[0]["总市值"]), 2) == 673915491937.68


def test_normalize_tx_history_converts_hands_to_volume_and_amount() -> None:
    frame = AkshareCollector._normalize_tx_history(
        pd.DataFrame(
            [
                {
                    "date": "2026-04-03",
                    "open": 10.0,
                    "close": 12.0,
                    "high": 12.5,
                    "low": 9.8,
                    "amount": 1234,
                }
            ]
        )
    )

    assert frame is not None
    assert frame.iloc[0]["成交量"] == 123400
    assert frame.iloc[0]["成交额"] == 1480800


def test_market_prefixed_symbol_maps_exchange_prefix() -> None:
    assert _market_prefixed_symbol("600519") == "sh600519"
    assert _market_prefixed_symbol("300308") == "sz300308"
    assert _market_prefixed_symbol("830799") == "bj830799"


def test_effective_min_turnover_keeps_cn_threshold() -> None:
    assert _effective_min_turnover("cn", 2.5) == 2.5


def test_build_demo_snapshot_records_keeps_a_share_symbols() -> None:
    records = build_demo_snapshot_records()

    assert records
    assert all(str(item["symbol"]).isdigit() and len(str(item["symbol"])) == 6 for item in records)


def test_build_sample_benchmark_records_keeps_cn_indexes() -> None:
    records = build_sample_benchmark_records(
        [
            {"symbol": "300308", "change_pct": 3.28, "score": 91},
            {"symbol": "688981", "change_pct": 2.42, "score": 88},
        ]
    )

    assert [item["code"] for item in records] == ["sh000001", "sz399001", "sz399006", "sh000300"]
