from __future__ import annotations

import json
import math
from time import sleep
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from app.core.config import get_settings
from app.services.signal_engine import StrategyWeights, enrich_stock_snapshot

EASTMONEY_SPOT_URLS = (
    "https://82.push2delay.eastmoney.com/api/qt/clist/get",
    "https://82.push2.eastmoney.com/api/qt/clist/get",
)
EASTMONEY_SPOT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/center/gridlist.html#hs_a_board",
    "Accept": "application/json, text/plain, */*",
}
SINA_SPOT_URL = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeData"
)
SINA_SPOT_HEADERS = {
    "User-Agent": EASTMONEY_SPOT_HEADERS["User-Agent"],
    "Referer": "https://vip.stock.finance.sina.com.cn/mkt/#hs_a",
    "Accept": "application/json, text/plain, */*",
}


@dataclass(slots=True)
class CollectedMarketData:
    snapshot_records: list[dict[str, object]]
    history_rows: list[dict[str, object]]
    universe_size: int
    synced_symbols: int
    skipped_symbols: int


class AkshareCollector:
    def __init__(self) -> None:
        self.settings = get_settings()

    def collect_market_dataset(
        self,
        *,
        strategy: StrategyWeights,
    ) -> tuple[CollectedMarketData | None, str]:
        try:
            import akshare as ak
        except Exception as exc:  # pragma: no cover - dependency import guard
            return None, f"AKShare 未就绪: {exc}"

        try:
            spot_frame = self._fetch_spot_frame(ak=ak)
        except Exception as exc:  # pragma: no cover - network/data source dependent
            return None, f"AKShare 快照拉取失败: {exc}"

        if spot_frame.empty:
            return None, "AKShare 快照返回为空。"

        candidates = self._select_candidates(spot_frame=spot_frame, strategy=strategy)
        if not candidates:
            return None, "AKShare 快照里没有符合当前策略过滤条件的股票。"

        lookback_days = max(
            self.settings.akshare_history_days * 2,
            strategy.min_listing_days * 2,
            260,
        )
        end_date = datetime.now(ZoneInfo(self.settings.app_timezone)).date()
        start_date = end_date - timedelta(days=lookback_days)

        history_frames = self._collect_histories(
            ak=ak,
            candidates=candidates,
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )
        financial_data = self._collect_financials(
            ak=ak,
            symbols=[str(candidate["symbol"]) for candidate in candidates],
        )

        snapshot_records: list[dict[str, object]] = []
        history_rows: list[dict[str, object]] = []
        skipped_symbols = 0

        for row in candidates:
            symbol = str(row["symbol"])
            history_df = history_frames.get(symbol)
            if history_df is None or history_df.empty:
                skipped_symbols += 1
                continue

            listing_days = int(history_df.shape[0])
            if strategy.exclude_new_shares and listing_days < strategy.min_listing_days:
                skipped_symbols += 1
                continue

            history_for_store = self._prepare_history_frame(history_df, symbol)
            if history_for_store.empty or len(history_for_store) < 20:
                skipped_symbols += 1
                continue

            record = enrich_stock_snapshot(
                symbol=symbol,
                name=str(row["name"]),
                board=str(row["board"]),
                industry=str(row["industry"]),
                latest_price=float(row["latest_price"]),
                change_pct=float(row["change_pct"]),
                turnover_ratio=float(row["turnover_ratio"]),
                pe_ttm=float(row["pe_ttm"]),
                market_cap=float(row["market_cap"]),
                volume_ratio=float(row["volume_ratio"]),
                history_df=history_for_store,
                strategy=strategy,
                fundamental=financial_data.get(symbol),
            )
            snapshot_records.append(record)
            history_rows.extend(history_for_store.to_dict(orient="records"))

        if not snapshot_records:
            return None, "AKShare 历史数据同步失败，未能生成有效股票池。"

        snapshot_records.sort(key=lambda item: (int(item["score"]), float(item["change_pct"])), reverse=True)
        message = (
            f"已从 AKShare 同步 {len(snapshot_records)} 只股票，"
            f"写入 {len(history_rows)} 条日线记录，"
            f"补到 {sum(1 for item in snapshot_records if item.get('fundamental'))} 只财务快照，"
            f"过滤 {skipped_symbols} 只不满足条件的标的。"
        )
        return (
            CollectedMarketData(
                snapshot_records=snapshot_records,
                history_rows=history_rows,
                universe_size=len(candidates),
                synced_symbols=len(snapshot_records),
                skipped_symbols=skipped_symbols,
            ),
            message,
        )

    def _select_candidates(
        self,
        *,
        spot_frame: pd.DataFrame,
        strategy: StrategyWeights,
    ) -> list[dict[str, object]]:
        frame = spot_frame.copy()
        frame["symbol"] = _series_or_default(frame, "代码").astype(str).str.zfill(6)
        frame["name"] = _series_or_default(frame, "名称").astype(str).str.strip()
        frame["latest_price"] = _series_or_default(frame, "最新价").apply(_safe_float)
        frame["change_pct"] = _series_or_default(frame, "涨跌幅").apply(_safe_float)
        frame["turnover_ratio"] = _series_or_default(frame, "换手率").apply(_safe_float)
        frame["volume_ratio"] = _series_or_default(frame, "量比", 1.0).apply(_safe_float)
        frame["pe_ttm"] = _series_or_default(frame, "市盈率-动态").apply(_safe_float)
        frame["market_cap"] = _series_or_default(frame, "总市值").apply(_safe_float) / 100000000
        frame["amount"] = _series_or_default(frame, "成交额").apply(_safe_float) / 100000000
        frame["industry"] = frame.apply(
            lambda row: _first_non_empty(
                row,
                "所属行业",
                "行业",
                default=_board_from_symbol(str(row["symbol"])),
            ),
            axis=1,
        )
        frame["board"] = frame["symbol"].apply(_board_from_symbol)

        frame = frame[frame["latest_price"] > 0].copy()
        if strategy.exclude_st:
            frame = frame[~frame["name"].str.contains("ST", case=False, na=False)].copy()
        frame = frame[frame["turnover_ratio"] >= strategy.min_turnover].copy()
        frame = frame.sort_values(
            by=["amount", "turnover_ratio", "change_pct"],
            ascending=[False, False, False],
        )

        limit = max(20, self.settings.akshare_stock_limit)
        selected = frame.head(limit)
        return selected[
            [
                "symbol",
                "name",
                "board",
                "industry",
                "latest_price",
                "change_pct",
                "turnover_ratio",
                "volume_ratio",
                "pe_ttm",
                "market_cap",
            ]
        ].to_dict(orient="records")

    def _collect_histories(
        self,
        *,
        ak: Any,
        candidates: list[dict[str, object]],
        start_date: str,
        end_date: str,
    ) -> dict[str, pd.DataFrame]:
        histories: dict[str, pd.DataFrame] = {}
        with ThreadPoolExecutor(max_workers=max(1, self.settings.akshare_max_workers)) as executor:
            future_map = {
                executor.submit(
                    self._fetch_single_history,
                    ak,
                    str(candidate["symbol"]),
                    start_date,
                    end_date,
                    self.settings.akshare_request_timeout,
                    self.settings.akshare_retry_attempts,
                    self.settings.akshare_retry_delay_ms,
                ): str(candidate["symbol"])
                for candidate in candidates
            }
            for future in as_completed(future_map):
                symbol = future_map[future]
                try:
                    history_df = future.result()
                except Exception:  # pragma: no cover - network/data source dependent
                    continue
                if history_df is not None and not history_df.empty:
                    histories[symbol] = history_df
        return histories

    def _collect_financials(
        self,
        *,
        ak: Any,
        symbols: list[str],
    ) -> dict[str, dict[str, object]]:
        financials: dict[str, dict[str, object]] = {}
        max_workers = max(1, min(4, self.settings.akshare_max_workers))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(
                    self._fetch_single_financial,
                    ak,
                    symbol,
                    self.settings.akshare_retry_attempts,
                    self.settings.akshare_retry_delay_ms,
                ): symbol
                for symbol in symbols
            }
            for future in as_completed(future_map):
                symbol = future_map[future]
                try:
                    snapshot = future.result()
                except Exception:  # pragma: no cover - third-party instability
                    continue
                if snapshot:
                    financials[symbol] = snapshot
        return financials

    @staticmethod
    def _fetch_single_history(
        ak: Any,
        symbol: str,
        start_date: str,
        end_date: str,
        request_timeout: int | float | None = None,
        retries: int = 1,
        retry_delay_ms: int = 0,
    ) -> pd.DataFrame | None:
        for attempt in range(max(1, retries)):
            try:
                history_df = AkshareCollector._fetch_history_from_eastmoney(
                    ak=ak,
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    request_timeout=request_timeout,
                )
                if history_df is not None and not history_df.empty:
                    return history_df
            except Exception:
                pass

            if attempt < max(1, retries) - 1 and retry_delay_ms > 0:
                sleep(retry_delay_ms / 1000 * (attempt + 1))

        history_df = AkshareCollector._fetch_history_from_tx(
            ak=ak,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            request_timeout=request_timeout,
            retries=retries,
            retry_delay_ms=retry_delay_ms,
        )
        if history_df is not None and not history_df.empty:
            return history_df

        return AkshareCollector._fetch_history_from_sina(
            ak=ak,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            retries=retries,
            retry_delay_ms=retry_delay_ms,
        )

    @staticmethod
    def _fetch_single_financial(
        ak: Any,
        symbol: str,
        retries: int = 1,
        retry_delay_ms: int = 0,
    ) -> dict[str, object] | None:
        for attempt in range(max(1, retries)):
            try:
                frame = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
                if frame is None or frame.empty:
                    return None
                return _extract_financial_snapshot(frame)
            except Exception:
                if attempt == max(1, retries) - 1:
                    return None
                if retry_delay_ms > 0:
                    sleep(retry_delay_ms / 1000)

        return None

    @staticmethod
    def _prepare_history_frame(history_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        frame = history_df.copy()
        frame["date"] = pd.to_datetime(frame["日期"]).dt.date.astype(str)
        frame["open"] = frame["开盘"].apply(_safe_float)
        frame["close"] = frame["收盘"].apply(_safe_float)
        frame["low"] = frame["最低"].apply(_safe_float)
        frame["high"] = frame["最高"].apply(_safe_float)
        frame["volume"] = frame["成交量"].apply(_safe_float)
        frame["amount"] = frame["成交额"].apply(_safe_float)
        frame = frame[frame["close"] > 0].copy()
        frame = frame.sort_values("date")
        frame["ma5"] = frame["close"].rolling(window=5, min_periods=1).mean().round(2)
        frame["ma20"] = frame["close"].rolling(window=20, min_periods=1).mean().round(2)
        frame["symbol"] = symbol
        return frame[
            ["symbol", "date", "open", "close", "low", "high", "volume", "amount", "ma5", "ma20"]
        ].reset_index(drop=True)

    @staticmethod
    def _fetch_history_from_eastmoney(
        *,
        ak: Any,
        symbol: str,
        start_date: str,
        end_date: str,
        request_timeout: int | float | None = None,
    ) -> pd.DataFrame | None:
        try:
            history_df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
                timeout=request_timeout,
            )
        except TypeError:
            history_df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )
        return AkshareCollector._normalize_eastmoney_history(history_df)

    @staticmethod
    def _fetch_history_from_tx(
        *,
        ak: Any,
        symbol: str,
        start_date: str,
        end_date: str,
        request_timeout: int | float | None = None,
        retries: int = 1,
        retry_delay_ms: int = 0,
    ) -> pd.DataFrame | None:
        market_symbol = _market_prefixed_symbol(symbol)
        for attempt in range(max(1, retries)):
            try:
                try:
                    history_df = ak.stock_zh_a_hist_tx(
                        symbol=market_symbol,
                        start_date=start_date,
                        end_date=end_date,
                        adjust="qfq",
                        timeout=request_timeout,
                    )
                except TypeError:
                    history_df = ak.stock_zh_a_hist_tx(
                        symbol=market_symbol,
                        start_date=start_date,
                        end_date=end_date,
                        adjust="qfq",
                    )
                normalized = AkshareCollector._normalize_tx_history(history_df)
                if normalized is not None and not normalized.empty:
                    return normalized
            except Exception:
                pass

            if attempt < max(1, retries) - 1 and retry_delay_ms > 0:
                sleep(retry_delay_ms / 1000 * (attempt + 1))

        return None

    @staticmethod
    def _fetch_history_from_sina(
        *,
        ak: Any,
        symbol: str,
        start_date: str,
        end_date: str,
        retries: int = 1,
        retry_delay_ms: int = 0,
    ) -> pd.DataFrame | None:
        market_symbol = _market_prefixed_symbol(symbol)
        for attempt in range(max(1, retries)):
            try:
                history_df = ak.stock_zh_a_daily(
                    symbol=market_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq",
                )
                normalized = AkshareCollector._normalize_sina_history(history_df)
                if normalized is not None and not normalized.empty:
                    return normalized
            except Exception:
                pass

            if attempt < max(1, retries) - 1 and retry_delay_ms > 0:
                sleep(retry_delay_ms / 1000 * (attempt + 1))

        return None

    @staticmethod
    def _normalize_eastmoney_history(history_df: pd.DataFrame | None) -> pd.DataFrame | None:
        if history_df is None or history_df.empty:
            return None
        return AkshareCollector._normalize_history_columns(
            history_df=history_df,
            date_col="日期",
            open_col="开盘",
            close_col="收盘",
            high_col="最高",
            low_col="最低",
            volume_col="成交量",
            amount_col="成交额",
        )

    @staticmethod
    def _normalize_tx_history(history_df: pd.DataFrame | None) -> pd.DataFrame | None:
        if history_df is None or history_df.empty:
            return None
        normalized = AkshareCollector._normalize_history_columns(
            history_df=history_df,
            date_col="date",
            open_col="open",
            close_col="close",
            high_col="high",
            low_col="low",
            volume_col="amount",
        )
        if normalized is None or normalized.empty:
            return None
        normalized["成交量"] = normalized["成交量"] * 100
        normalized["成交额"] = normalized["成交量"] * normalized["收盘"]
        return normalized

    @staticmethod
    def _normalize_sina_history(history_df: pd.DataFrame | None) -> pd.DataFrame | None:
        if history_df is None or history_df.empty:
            return None
        return AkshareCollector._normalize_history_columns(
            history_df=history_df,
            date_col="date",
            open_col="open",
            close_col="close",
            high_col="high",
            low_col="low",
            volume_col="volume",
            amount_col="amount",
        )

    @staticmethod
    def _normalize_history_columns(
        *,
        history_df: pd.DataFrame,
        date_col: str,
        open_col: str,
        close_col: str,
        high_col: str,
        low_col: str,
        volume_col: str,
        amount_col: str | None = None,
    ) -> pd.DataFrame | None:
        required_columns = [date_col, open_col, close_col, high_col, low_col, volume_col]
        if any(column not in history_df.columns for column in required_columns):
            return None

        frame = pd.DataFrame(
            {
                "日期": pd.to_datetime(history_df[date_col], errors="coerce"),
                "开盘": pd.to_numeric(history_df[open_col], errors="coerce"),
                "收盘": pd.to_numeric(history_df[close_col], errors="coerce"),
                "最高": pd.to_numeric(history_df[high_col], errors="coerce"),
                "最低": pd.to_numeric(history_df[low_col], errors="coerce"),
                "成交量": pd.to_numeric(history_df[volume_col], errors="coerce"),
            }
        )
        if amount_col and amount_col in history_df.columns:
            frame["成交额"] = pd.to_numeric(history_df[amount_col], errors="coerce")
        else:
            frame["成交额"] = pd.NA

        frame = frame.dropna(subset=["日期", "收盘"]).copy()
        frame["日期"] = frame["日期"].dt.date
        frame["成交量"] = frame["成交量"].fillna(0.0)
        frame["成交额"] = pd.to_numeric(frame["成交额"], errors="coerce").fillna(0.0)
        frame = frame[frame["收盘"] > 0].copy()
        frame = frame.sort_values("日期").drop_duplicates(subset=["日期"], keep="last")
        return frame.reset_index(drop=True)

    def _fetch_spot_frame(self, *, ak: Any) -> pd.DataFrame:
        errors: list[str] = []
        try:
            return self._fetch_lightweight_spot_frame()
        except Exception as exc:
            errors.append(f"轻量快照失败: {exc}")

        try:
            return self._fetch_sina_spot_frame()
        except Exception as exc:
            errors.append(f"新浪快照失败: {exc}")

        for attempt in range(1, self.settings.akshare_retry_attempts + 1):
            try:
                return ak.stock_zh_a_spot_em()
            except Exception as exc:
                errors.append(f"AKShare 默认快照第 {attempt} 次失败: {exc}")
                if attempt < self.settings.akshare_retry_attempts:
                    sleep(self.settings.akshare_retry_delay_ms / 1000 * attempt)

        raise RuntimeError("；".join(errors[:3]))

    def _fetch_lightweight_spot_frame(self) -> pd.DataFrame:
        page_size = 200
        target_rows = max(400, self.settings.akshare_stock_limit * 6)
        total_pages = max(1, math.ceil(target_rows / page_size))
        errors: list[str] = []

        for url in EASTMONEY_SPOT_URLS:
            try:
                return self._fetch_lightweight_spot_frame_from_url(
                    url=url,
                    page_size=page_size,
                    total_pages=total_pages,
                )
            except Exception as exc:
                errors.append(f"{url} -> {exc}")

        raise RuntimeError("；".join(errors))

    def _fetch_lightweight_spot_frame_from_url(
        self,
        *,
        url: str,
        page_size: int,
        total_pages: int,
    ) -> pd.DataFrame:
        params = {
            "pn": "1",
            "pz": str(page_size),
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f6",
            "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
            "fields": "f2,f3,f5,f6,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f24,f25",
        }
        session = requests.Session()
        frames: list[pd.DataFrame] = []
        total_count = None

        for page in range(1, total_pages + 1):
            params["pn"] = str(page)
            data_json = self._request_json_with_retry(session=session, url=url, params=params)
            data = data_json.get("data") or {}
            diff = data.get("diff") or []
            if not diff:
                if page == 1:
                    raise ValueError("返回数据为空")
                break

            frames.append(pd.DataFrame(diff))
            total_count = int(data.get("total") or 0)
            if total_count and page * page_size >= total_count:
                break

        if not frames:
            raise ValueError("未获取到任何分页数据")
        return self._build_spot_frame(pd.concat(frames, ignore_index=True))

    def _fetch_sina_spot_frame(self) -> pd.DataFrame:
        page_size = 80
        target_rows = max(240, self.settings.akshare_stock_limit * 6)
        total_pages = max(1, math.ceil(target_rows / page_size))
        session = requests.Session()
        frames: list[pd.DataFrame] = []

        for page in range(1, total_pages + 1):
            params = {
                "page": str(page),
                "num": str(page_size),
                "sort": "amount",
                "asc": "0",
                "node": "hs_a",
                "symbol": "",
                "_s_r_a": "page",
            }
            response = session.get(
                SINA_SPOT_URL,
                params=params,
                headers=SINA_SPOT_HEADERS,
                timeout=self.settings.akshare_request_timeout,
            )
            response.raise_for_status()
            data = json.loads(response.text)
            if not data:
                if page == 1:
                    raise ValueError("返回数据为空")
                break
            frames.append(pd.DataFrame(data))

        if not frames:
            raise ValueError("未获取到任何分页数据")
        return self._build_sina_spot_frame(pd.concat(frames, ignore_index=True))

    def _request_json_with_retry(
        self,
        *,
        session: requests.Session,
        url: str,
        params: dict[str, str],
    ) -> dict[str, object]:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.akshare_retry_attempts + 1):
            try:
                response = session.get(
                    url,
                    params=params,
                    headers=EASTMONEY_SPOT_HEADERS,
                    timeout=self.settings.akshare_request_timeout,
                )
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_error = exc
                if attempt < self.settings.akshare_retry_attempts:
                    sleep(self.settings.akshare_retry_delay_ms / 1000 * attempt)

        raise RuntimeError(str(last_error) if last_error else "请求失败")

    @staticmethod
    def _build_spot_frame(frame: pd.DataFrame) -> pd.DataFrame:
        renamed = frame.rename(
            columns={
                "f2": "最新价",
                "f3": "涨跌幅",
                "f5": "成交量",
                "f6": "成交额",
                "f8": "换手率",
                "f9": "市盈率-动态",
                "f10": "量比",
                "f12": "代码",
                "f14": "名称",
                "f15": "最高",
                "f16": "最低",
                "f17": "今开",
                "f18": "昨收",
                "f20": "总市值",
                "f21": "流通市值",
                "f24": "60日涨跌幅",
                "f25": "年初至今涨跌幅",
            }
        ).copy()

        for column in (
            "最新价",
            "涨跌幅",
            "成交量",
            "成交额",
            "换手率",
            "市盈率-动态",
            "量比",
            "最高",
            "最低",
            "今开",
            "昨收",
            "总市值",
            "流通市值",
            "60日涨跌幅",
            "年初至今涨跌幅",
        ):
            if column not in renamed.columns:
                renamed[column] = pd.NA
            renamed[column] = pd.to_numeric(renamed[column], errors="coerce")

        if "代码" not in renamed.columns:
            renamed["代码"] = ""
        if "名称" not in renamed.columns:
            renamed["名称"] = ""

        renamed["代码"] = renamed["代码"].astype(str).str.zfill(6)
        renamed["名称"] = renamed["名称"].astype(str).str.strip()
        renamed.sort_values(by=["成交额", "涨跌幅"], ascending=[False, False], inplace=True, ignore_index=True)
        renamed.reset_index(drop=True, inplace=True)
        renamed.index = renamed.index + 1
        renamed.insert(0, "序号", renamed.index)
        return renamed

    @staticmethod
    def _build_sina_spot_frame(frame: pd.DataFrame) -> pd.DataFrame:
        renamed = frame.rename(
            columns={
                "code": "代码",
                "name": "名称",
                "trade": "最新价",
                "changepercent": "涨跌幅",
                "volume": "成交量",
                "amount": "成交额",
                "turnoverratio": "换手率",
                "per": "市盈率-动态",
                "open": "今开",
                "high": "最高",
                "low": "最低",
                "settlement": "昨收",
                "mktcap": "总市值",
                "nmc": "流通市值",
            }
        ).copy()

        for column in (
            "最新价",
            "涨跌幅",
            "成交量",
            "成交额",
            "换手率",
            "市盈率-动态",
            "今开",
            "最高",
            "最低",
            "昨收",
            "总市值",
            "流通市值",
        ):
            if column not in renamed.columns:
                renamed[column] = pd.NA
            renamed[column] = pd.to_numeric(renamed[column], errors="coerce")

        renamed["量比"] = 1.0
        renamed["总市值"] = renamed["总市值"].fillna(0.0) * 10000
        renamed["流通市值"] = renamed["流通市值"].fillna(0.0) * 10000

        if "代码" not in renamed.columns:
            renamed["代码"] = ""
        if "名称" not in renamed.columns:
            renamed["名称"] = ""

        renamed["代码"] = renamed["代码"].astype(str).str.zfill(6)
        renamed["名称"] = renamed["名称"].astype(str).str.strip()
        renamed.sort_values(by=["成交额", "涨跌幅"], ascending=[False, False], inplace=True, ignore_index=True)
        renamed.reset_index(drop=True, inplace=True)
        renamed.index = renamed.index + 1
        renamed.insert(0, "序号", renamed.index)
        return renamed


def _board_from_symbol(symbol: str) -> str:
    if symbol.startswith("300"):
        return "创业板"
    if symbol.startswith("688"):
        return "科创板"
    if symbol.startswith(("430", "83", "87")):
        return "北交所"
    return "主板"


def _market_prefixed_symbol(symbol: str) -> str:
    if symbol.startswith("6"):
        return f"sh{symbol}"
    if symbol.startswith(("4", "8", "430", "83", "87")):
        return f"bj{symbol}"
    return f"sz{symbol}"


def _first_non_empty(row: pd.Series, *columns: str, default: str) -> str:
    for column in columns:
        if column in row and pd.notna(row[column]) and str(row[column]).strip():
            return str(row[column]).strip()
    return default


def _safe_float(value: object) -> float:
    try:
        if value in (None, "", "-"):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _series_or_default(frame: pd.DataFrame, column: str, default: object = 0.0) -> pd.Series:
    if column in frame.columns:
        return frame[column]
    return pd.Series([default] * len(frame), index=frame.index)


def _extract_financial_snapshot(frame: pd.DataFrame) -> dict[str, object] | None:
    latest = frame.iloc[-1].to_dict()
    report_period = str(latest.get("报告期", "")).strip() or None
    snapshot = {
        "report_period": report_period,
        "revenue_growth": _parse_percent_value(latest.get("营业总收入同比增长率")),
        "net_profit_growth": _parse_percent_value(latest.get("净利润同比增长率")),
        "deduct_profit_growth": _parse_percent_value(latest.get("扣非净利润同比增长率")),
        "roe": _parse_percent_value(latest.get("净资产收益率"))
        or _parse_percent_value(latest.get("净资产收益率-摊薄")),
        "gross_margin": _parse_percent_value(latest.get("销售毛利率")),
        "debt_ratio": _parse_percent_value(latest.get("资产负债率")),
        "eps": _parse_numeric_value(latest.get("基本每股收益")),
        "operating_cashflow_per_share": _parse_numeric_value(latest.get("每股经营现金流")),
    }
    if not any(value is not None for key, value in snapshot.items() if key != "report_period"):
        return None
    return snapshot


def _parse_percent_value(value: object) -> float | None:
    if value in (None, "", "-", "--") or isinstance(value, bool):
        return None
    text = str(value).replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _parse_numeric_value(value: object) -> float | None:
    if value in (None, "", "-", "--") or isinstance(value, bool):
        return None
    text = str(value).strip()
    multiplier = 1.0
    if text.endswith("亿"):
        multiplier = 100000000.0
        text = text[:-1]
    elif text.endswith("万"):
        multiplier = 10000.0
        text = text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return None
