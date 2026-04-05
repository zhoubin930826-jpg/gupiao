from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd

from app.core.market_scope import DEFAULT_MARKET_SCOPE, market_label, normalize_market_scope


def collect_market_capital_flow_bundle(
    *,
    ak: Any,
    market: str = DEFAULT_MARKET_SCOPE,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    normalized_market = normalize_market_scope(market)
    if normalized_market != "cn":
        return build_placeholder_market_capital_flow_overview(normalized_market), []

    northbound_frame = _safe_frame(lambda: ak.stock_hsgt_fund_flow_summary_em())
    market_flow_frame = _safe_frame(lambda: ak.stock_market_fund_flow())
    lhb_frame = _safe_frame(lambda: ak.stock_lhb_stock_statistic_em(symbol="近一月"))
    lhb_rows = normalize_lhb_statistics_rows(lhb_frame)
    overview = build_cn_market_capital_flow_overview(
        northbound_frame=northbound_frame,
        market_flow_frame=market_flow_frame,
        lhb_rows=lhb_rows,
    )
    return overview, lhb_rows


def collect_cn_stock_capital_flow_map(
    *,
    ak: Any,
    symbols: list[str],
    lhb_rows: list[dict[str, object]] | None = None,
    max_workers: int = 2,
) -> dict[str, dict[str, object]]:
    if not symbols:
        return {}

    lhb_map = {
        str(row["symbol"]): row
        for row in (lhb_rows or [])
        if row.get("symbol")
    }

    result: dict[str, dict[str, object]] = {}
    worker_count = max(1, min(max_workers, 3))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_map = {
            executor.submit(
                collect_cn_stock_capital_flow_analysis,
                ak=ak,
                symbol=symbol,
                lhb_row=lhb_map.get(symbol),
            ): symbol
            for symbol in symbols
        }
        for future in as_completed(future_map):
            symbol = future_map[future]
            try:
                payload = future.result()
            except Exception:
                continue
            if payload:
                result[symbol] = payload

    return result


def collect_cn_stock_capital_flow_analysis(
    *,
    ak: Any,
    symbol: str,
    lhb_row: dict[str, object] | None = None,
) -> dict[str, object] | None:
    market_code = "sh" if str(symbol).startswith("6") else "sz"
    try:
        frame = ak.stock_individual_fund_flow(stock=symbol, market=market_code)
    except Exception:
        return build_placeholder_stock_capital_flow_analysis(symbol=symbol, lhb_row=lhb_row)
    return build_cn_stock_capital_flow_analysis_from_frame(
        symbol=symbol,
        flow_frame=frame,
        lhb_row=lhb_row,
    )


def build_cn_market_capital_flow_overview(
    *,
    northbound_frame: pd.DataFrame,
    market_flow_frame: pd.DataFrame,
    lhb_rows: list[dict[str, object]],
) -> dict[str, object]:
    northbound = northbound_frame.copy() if northbound_frame is not None else pd.DataFrame()
    latest_market_flow = _latest_market_flow_row(market_flow_frame)

    if northbound.empty and latest_market_flow is None and not lhb_rows:
        return {
            "status": "placeholder",
            "scope_label": "A股 资金面",
            "summary": "当前还没有拿到稳定的北向、主力资金和龙虎榜摘要，先以价格结构为主。",
            "watch_points": [
                "先完成一次新的 A 股同步，确认资金面摘要是否恢复。",
                "若当天市场分化明显，不要只看高分就直接放大仓位。",
            ],
            "metrics": _placeholder_flow_metrics("A股"),
        }

    northbound = northbound.fillna(0)
    if "资金方向" in northbound.columns:
        northbound = northbound[northbound["资金方向"].astype(str).str.contains("北向", na=False)].copy()
    sh_flow = _row_value(northbound, "板块", "沪股通", "成交净买额")
    sz_flow = _row_value(northbound, "板块", "深股通", "成交净买额")
    northbound_total = round(sh_flow + sz_flow, 2)
    northbound_up = int(_row_value(northbound, "板块", "沪股通", "上涨数") + _row_value(northbound, "板块", "深股通", "上涨数"))
    northbound_down = int(_row_value(northbound, "板块", "沪股通", "下跌数") + _row_value(northbound, "板块", "深股通", "下跌数"))

    main_net_inflow = _scaled_amount(latest_market_flow.get("主力净流入-净额")) if latest_market_flow else None
    main_ratio = _safe_float(latest_market_flow.get("主力净流入-净占比")) if latest_market_flow else None
    ultra_large = _scaled_amount(latest_market_flow.get("超大单净流入-净额")) if latest_market_flow else None

    lhb_count = len(lhb_rows)
    institution_positive = sum(1 for row in lhb_rows if _safe_float(row.get("institution_net_buy")) > 0)
    hot_positive = [row for row in lhb_rows if _safe_float(row.get("net_buy_amount")) > 0]
    top_row = max(hot_positive, key=lambda item: _safe_float(item.get("net_buy_amount")), default=None)
    if top_row is None and lhb_rows:
        top_row = max(lhb_rows, key=lambda item: _safe_float(item.get("on_list_count")))

    summary, watch_points = _market_capital_flow_commentary(
        northbound_total=northbound_total,
        main_net_inflow=main_net_inflow,
        main_ratio=main_ratio,
        northbound_up=northbound_up,
        northbound_down=northbound_down,
        lhb_count=lhb_count,
        institution_positive=institution_positive,
    )

    return {
        "status": "ready",
        "scope_label": "A股 资金面",
        "summary": summary,
        "watch_points": watch_points,
        "metrics": [
            {
                "label": "北向净买额",
                "value": _format_amount(northbound_total),
                "change": f"沪股通 {_format_amount(sh_flow)} / 深股通 {_format_amount(sz_flow)}",
                "tone": _tone_from_amount(northbound_total, positive_threshold=10.0, negative_threshold=-10.0),
                "description": "北向更适合当环境资金温度参考，不适合直接当作单票买点。",
            },
            {
                "label": "主力净流入",
                "value": _format_amount(main_net_inflow),
                "change": "净占比 " + _format_percent(main_ratio, digits=2),
                "tone": _tone_from_amount(main_net_inflow, positive_threshold=20.0, negative_threshold=-20.0),
                "description": "主力净流入更能反映当天主动性买盘是否愿意继续做趋势。",
            },
            {
                "label": "龙虎榜活跃度",
                "value": f"{lhb_count} 只",
                "change": f"机构净买占优 {institution_positive} 只",
                "tone": "positive" if institution_positive >= max(10, lhb_count * 0.18) else "neutral",
                "description": "龙虎榜更像交易热度和游资/机构参与度的放大镜，不代表全部都能持续。",
            },
            {
                "label": "最热上榜股",
                "value": str(top_row["name"]) if top_row else "暂无",
                "change": (
                    f"净买额 {_format_amount(_safe_float(top_row.get('net_buy_amount')))}"
                    if top_row
                    else f"超大单 {_format_amount(ultra_large)}"
                ),
                "tone": _tone_from_amount(
                    _safe_float(top_row.get("net_buy_amount")) if top_row else ultra_large,
                    positive_threshold=1.0,
                    negative_threshold=-1.0,
                ),
                "description": "它只是在提醒当前活跃焦点在哪里，不适合作为单独追涨理由。",
            },
        ],
    }


def build_placeholder_market_capital_flow_overview(
    market: str = DEFAULT_MARKET_SCOPE,
) -> dict[str, object]:
    market_name = market_label(market)
    return {
        "status": "placeholder",
        "scope_label": f"{market_name} 资金面",
        "summary": f"{market_name} 资金面模块这一版还没接入可靠摘要，先以价格、财务和事件层为主。",
        "watch_points": [
            "先看指数环境和市场状态，不要把 A 股资金面逻辑直接套到其他市场。",
            "当前市场的推荐更适合作为候选池，而不是资金驱动结论。",
        ],
        "metrics": _placeholder_flow_metrics(market_name),
    }


def build_sample_market_capital_flow_overview(
    records: list[dict[str, object]],
    market: str = DEFAULT_MARKET_SCOPE,
) -> dict[str, object]:
    normalized_market = normalize_market_scope(market)
    if normalized_market != "cn":
        return build_placeholder_market_capital_flow_overview(normalized_market)

    frame = pd.DataFrame(records)
    avg_change = _safe_float(frame.get("change_pct").mean()) if not frame.empty and "change_pct" in frame.columns else 0.0
    avg_turnover = _safe_float(frame.get("turnover_ratio").mean()) if not frame.empty and "turnover_ratio" in frame.columns else 0.0
    northbound_total = round(avg_change * 8.0, 1)
    main_net_inflow = round((avg_turnover - 3.0) * 18.0, 1)
    lhb_count = max(8, int(frame.shape[0] * 0.25)) if not frame.empty else 12
    institution_positive = max(2, int(lhb_count * 0.28))
    summary, watch_points = _market_capital_flow_commentary(
        northbound_total=northbound_total,
        main_net_inflow=main_net_inflow,
        main_ratio=round(main_net_inflow / 20, 2),
        northbound_up=max(int(frame.shape[0] * 0.45), 12),
        northbound_down=max(int(frame.shape[0] * 0.35), 8),
        lhb_count=lhb_count,
        institution_positive=institution_positive,
    )

    return {
        "status": "derived",
        "scope_label": "A股 资金面",
        "summary": summary,
        "watch_points": watch_points,
        "metrics": [
            {
                "label": "北向净买额",
                "value": _format_amount(northbound_total),
                "change": "样例推断",
                "tone": _tone_from_amount(northbound_total, positive_threshold=8.0, negative_threshold=-8.0),
                "description": "示例环境下用样本池强弱推断资金温度，只用于界面占位。",
            },
            {
                "label": "主力净流入",
                "value": _format_amount(main_net_inflow),
                "change": "样例推断",
                "tone": _tone_from_amount(main_net_inflow, positive_threshold=15.0, negative_threshold=-15.0),
                "description": "示例环境下用样本池活跃度拟合主力强弱。",
            },
            {
                "label": "龙虎榜活跃度",
                "value": f"{lhb_count} 只",
                "change": f"机构净买占优 {institution_positive} 只",
                "tone": "neutral",
                "description": "示例环境下不代表真实龙虎榜，只用来占位说明热度。",
            },
                {
                    "label": "最热上榜股",
                    "value": _sample_hot_name(records),
                    "change": "样例推断",
                    "tone": "positive" if avg_change >= 0 else "negative",
                    "description": "示例环境下用高分候选代替热门上榜股。",
                },
            ],
    }


def build_sample_stock_capital_flow_analysis(record: dict[str, object]) -> dict[str, object]:
    score = int(record.get("score") or 0)
    change_pct = _safe_float(record.get("change_pct"))
    turnover_ratio = _safe_float(record.get("turnover_ratio"))
    net_1d = round((change_pct * max(turnover_ratio, 1.0)) / 2.2, 1)
    net_5d = round(net_1d * 2.8, 1)
    positive_days = 4 if score >= 85 else 3 if score >= 75 else 2
    tone = "positive" if score >= 85 and change_pct >= 0 else "caution" if change_pct < -2 else "neutral"
    summary = (
        f"样例环境下，这只票的资金面更像 {positive_days} 天里有持续助攻的强势样本。"
        if tone == "positive"
        else "样例环境下，这只票的资金面暂时更像来回切换的轮动样本。"
        if tone == "neutral"
        else "样例环境下，这只票最近更像资金分歧扩大的高波动样本。"
    )
    return {
        "status": "derived",
        "tone": tone,
        "summary": summary,
        "latest_trade_date": None,
        "main_net_inflow_1d": net_1d,
        "main_net_ratio_1d": round(net_1d / 2.4, 2),
        "main_net_inflow_5d": net_5d,
        "active_days_5d": positive_days,
        "ultra_large_net_inflow_1d": round(net_1d * 0.6, 1),
        "lhb_on_list_count": 2 if score >= 88 else 1 if score >= 80 else 0,
        "lhb_recent_date": None,
        "lhb_net_buy_amount": round(max(net_1d, 0) * 0.8, 1),
        "watch_points": [
            "这是一份基于样本池强弱和换手推断的占位资金面，不代表真实成交明细。",
            "如果以后切到真实同步，优先看最近 5 日主力净流入是否还在延续。",
        ],
    }


def build_placeholder_stock_capital_flow_analysis(
    *,
    symbol: str,
    lhb_row: dict[str, object] | None = None,
) -> dict[str, object]:
    if lhb_row:
        on_list_count = int(lhb_row.get("on_list_count") or 0)
        summary = (
            f"{symbol} 近一月有 {on_list_count} 次龙虎榜记录，但当前主力资金明细接口暂未稳定返回，"
            "先把龙虎榜活跃度当作辅助提示。"
        )
        watch_points = [
            "如果后续能补到主力资金明细，再判断上榜后有没有持续承接。",
            "龙虎榜活跃不等于必然继续上涨，重点看上榜后次日量价是否失真。",
        ]
    else:
        summary = f"{symbol} 当前还没有拿到稳定的个股资金面明细，先把价格结构和事件催化放在前面。"
        watch_points = [
            "等下一次同步后再看是否能补到稳定的个股主力资金明细。",
            "没有资金面时，高分只代表候选价值，不代表交易质量已经确认。",
        ]
    return {
        "status": "placeholder",
        "tone": "neutral",
        "summary": summary,
        "latest_trade_date": None,
        "main_net_inflow_1d": None,
        "main_net_ratio_1d": None,
        "main_net_inflow_5d": None,
        "active_days_5d": None,
        "ultra_large_net_inflow_1d": None,
        "lhb_on_list_count": int(lhb_row.get("on_list_count") or 0) if lhb_row else None,
        "lhb_recent_date": str(lhb_row.get("recent_list_date")) if lhb_row and lhb_row.get("recent_list_date") else None,
        "lhb_net_buy_amount": _safe_float(lhb_row.get("net_buy_amount")) if lhb_row else None,
        "watch_points": watch_points,
    }


def build_cn_stock_capital_flow_analysis_from_frame(
    *,
    symbol: str,
    flow_frame: pd.DataFrame,
    lhb_row: dict[str, object] | None = None,
) -> dict[str, object]:
    normalized = _normalize_stock_flow_frame(flow_frame)
    if normalized.empty:
        return build_placeholder_stock_capital_flow_analysis(symbol=symbol, lhb_row=lhb_row)

    recent = normalized.tail(5).reset_index(drop=True)
    latest = recent.iloc[-1]
    main_net_inflow_1d = _safe_float(latest["main_net_inflow"])
    main_net_ratio_1d = _safe_float(latest["main_net_ratio"])
    main_net_inflow_5d = round(float(recent["main_net_inflow"].sum()), 2)
    active_days_5d = int((recent["main_net_inflow"] > 0).sum())
    ultra_large_net_inflow_1d = _safe_float(latest["ultra_large_net_inflow"])
    lhb_on_list_count = int(lhb_row.get("on_list_count") or 0) if lhb_row else None
    lhb_net_buy_amount = _safe_float(lhb_row.get("net_buy_amount")) if lhb_row else None
    lhb_recent_date = str(lhb_row.get("recent_list_date")) if lhb_row and lhb_row.get("recent_list_date") else None

    if (main_net_inflow_5d >= 5 and active_days_5d >= 3) or (
        lhb_on_list_count and lhb_on_list_count >= 2 and (lhb_net_buy_amount or 0) > 0
    ):
        tone = "positive"
        summary = (
            f"{symbol} 近 5 日主力净流入 {_format_amount(main_net_inflow_5d)}，"
            f"其中 {active_days_5d} 天是净流入，资金助攻还在。"
        )
    elif (main_net_inflow_5d <= -5) or ((main_net_ratio_1d or 0) <= -5):
        tone = "caution"
        summary = (
            f"{symbol} 近 5 日主力净流出 {_format_amount(main_net_inflow_5d)}，"
            f"最新一日净占比 {_format_percent(main_net_ratio_1d, digits=2)}，资金分歧还没收完。"
        )
    else:
        tone = "neutral"
        summary = (
            f"{symbol} 近 5 日主力资金在来回切换，"
            f"目前更像轮动博弈，先别把资金面理解成单边助攻。"
        )

    if lhb_on_list_count:
        summary += (
            f" 近一月还有 {lhb_on_list_count} 次龙虎榜记录，"
            f"累计净买额 {_format_amount(lhb_net_buy_amount)}。"
        )

    watch_points = [
        (
            "近 5 日主力净流入天数过半，后面重点看量能是否能继续放大。"
            if active_days_5d >= 3
            else "近 5 日主力净流入天数不多，强势延续还需要成交和价格再确认。"
        ),
        (
            f"最新一日超大单净流入 {_format_amount(ultra_large_net_inflow_1d)}，说明大单承接还在。"
            if (ultra_large_net_inflow_1d or 0) > 0
            else f"最新一日超大单净流入 {_format_amount(ultra_large_net_inflow_1d)}，说明大单承接偏弱。"
        ),
        (
            f"龙虎榜最近上榜日在 {lhb_recent_date}，如果再次上榜，要看净买额能否继续放大。"
            if lhb_recent_date
            else "近一月没有明显龙虎榜活跃记录，资金判断更依赖主力净流入和量价结构。"
        ),
    ]

    return {
        "status": "ready",
        "tone": tone,
        "summary": summary,
        "latest_trade_date": str(latest["trade_date"]),
        "main_net_inflow_1d": main_net_inflow_1d,
        "main_net_ratio_1d": main_net_ratio_1d,
        "main_net_inflow_5d": main_net_inflow_5d,
        "active_days_5d": active_days_5d,
        "ultra_large_net_inflow_1d": ultra_large_net_inflow_1d,
        "lhb_on_list_count": lhb_on_list_count,
        "lhb_recent_date": lhb_recent_date,
        "lhb_net_buy_amount": lhb_net_buy_amount,
        "watch_points": watch_points,
    }


def normalize_lhb_statistics_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame is None or frame.empty:
        return []

    rows: list[dict[str, object]] = []
    for row in frame.to_dict(orient="records"):
        symbol = str(row.get("代码") or "").strip().zfill(6)
        if not symbol:
            continue
        rows.append(
            {
                "symbol": symbol,
                "name": str(row.get("名称") or "").strip(),
                "recent_list_date": _safe_date(row.get("最近上榜日")),
                "close_price": _safe_float(row.get("收盘价")),
                "change_pct": _safe_float(row.get("涨跌幅")),
                "on_list_count": int(_safe_float(row.get("上榜次数")) or 0),
                "net_buy_amount": round(_safe_float(row.get("龙虎榜净买额")) / 100000000, 2),
                "buy_amount": round(_safe_float(row.get("龙虎榜买入额")) / 100000000, 2),
                "sell_amount": round(_safe_float(row.get("龙虎榜卖出额")) / 100000000, 2),
                "total_amount": round(_safe_float(row.get("龙虎榜总成交额")) / 100000000, 2),
                "institution_buy_count": int(_safe_float(row.get("买方机构次数")) or 0),
                "institution_sell_count": int(_safe_float(row.get("卖方机构次数")) or 0),
                "institution_net_buy": round(_safe_float(row.get("机构买入净额")) / 100000000, 2),
                "return_1m": _safe_optional_float(row.get("近1个月涨跌幅")),
                "return_3m": _safe_optional_float(row.get("近3个月涨跌幅")),
                "return_6m": _safe_optional_float(row.get("近6个月涨跌幅")),
                "return_1y": _safe_optional_float(row.get("近1年涨跌幅")),
            }
        )
    return rows


def _normalize_stock_flow_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()

    normalized = frame.copy()
    normalized["trade_date"] = pd.to_datetime(normalized["日期"], errors="coerce").dt.date.astype(str)
    normalized["main_net_inflow"] = pd.to_numeric(
        normalized["主力净流入-净额"], errors="coerce"
    ).fillna(0) / 100000000
    normalized["main_net_ratio"] = pd.to_numeric(
        normalized["主力净流入-净占比"], errors="coerce"
    ).fillna(0)
    normalized["ultra_large_net_inflow"] = pd.to_numeric(
        normalized["超大单净流入-净额"], errors="coerce"
    ).fillna(0) / 100000000
    normalized = normalized.dropna(subset=["trade_date"])
    normalized = normalized.sort_values("trade_date")
    return normalized[["trade_date", "main_net_inflow", "main_net_ratio", "ultra_large_net_inflow"]]


def _latest_market_flow_row(frame: pd.DataFrame) -> dict[str, object] | None:
    if frame is None or frame.empty or "日期" not in frame.columns:
        return None
    normalized = frame.copy()
    normalized["日期"] = pd.to_datetime(normalized["日期"], errors="coerce")
    normalized = normalized.dropna(subset=["日期"]).sort_values("日期")
    if normalized.empty:
        return None
    return normalized.iloc[-1].to_dict()


def _market_capital_flow_commentary(
    *,
    northbound_total: float,
    main_net_inflow: float | None,
    main_ratio: float | None,
    northbound_up: int,
    northbound_down: int,
    lhb_count: int,
    institution_positive: int,
) -> tuple[str, list[str]]:
    main_net = main_net_inflow or 0.0
    ratio = main_ratio or 0.0

    if northbound_total >= 20 and main_net >= 20:
        summary = (
            f"北向和主力资金今天都偏正面，分别是 {_format_amount(northbound_total)} 和 "
            f"{_format_amount(main_net)}，环境更像顺势窗口。"
        )
    elif northbound_total <= -20 and main_net <= -20:
        summary = (
            f"北向和主力资金今天都偏流出，分别是 {_format_amount(northbound_total)} 和 "
            f"{_format_amount(main_net)}，高分票也要防冲高回落。"
        )
    else:
        summary = (
            f"今天资金面更像分化轮动，北向 {_format_amount(northbound_total)}、"
            f"主力 {_format_amount(main_net)}，需要把环境和个股结构一起看。"
        )

    watch_points = [
        (
            f"北向相关样本里上涨家数 {northbound_up}、下跌家数 {northbound_down}，"
            "如果下跌占优，高分票更适合等回踩确认。"
        ),
        (
            f"主力净占比 {ratio:+.2f}% 说明主动性资金还在表态。"
            if ratio >= 0
            else f"主力净占比 {ratio:+.2f}% 说明主动性资金还在撤退。"
        ),
        (
            f"近一月龙虎榜活跃股 {lhb_count} 只，其中机构净买占优 {institution_positive} 只。"
            if lhb_count
            else "近一月龙虎榜热度不算高，短线情绪扩散度有限。"
        ),
    ]
    return summary, watch_points


def _placeholder_flow_metrics(scope: str) -> list[dict[str, object]]:
    return [
        {
            "label": "北向净买额",
            "value": "--",
            "change": "等待接入",
            "tone": "neutral",
            "description": f"{scope} 暂时没有稳定的跨市场资金净流入摘要。",
        },
        {
            "label": "主力净流入",
            "value": "--",
            "change": "等待接入",
            "tone": "neutral",
            "description": "当前先把资金面当缺失值处理，不要硬给结论。",
        },
        {
            "label": "龙虎榜活跃度",
            "value": "--",
            "change": "等待接入",
            "tone": "neutral",
            "description": "龙虎榜更适合 A 股语境，这一版还没有扩展到其他市场。",
        },
        {
            "label": "最热上榜股",
            "value": "--",
            "change": "等待接入",
            "tone": "neutral",
            "description": "等稳定源接上以后，这里再展示真实热点股。",
        },
    ]


def _sample_hot_name(records: list[dict[str, object]]) -> str:
    if not records:
        return "暂无"
    first = records[0]
    if isinstance(first, dict):
        if first.get("name"):
            return str(first["name"])
        if first.get("industry"):
            return f"{first['industry']} 主线"
    return "高分样本"


def _safe_frame(loader: Any) -> pd.DataFrame:
    try:
        frame = loader()
    except Exception:
        return pd.DataFrame()
    return frame if isinstance(frame, pd.DataFrame) else pd.DataFrame()


def _row_value(frame: pd.DataFrame, match_column: str, match_value: str, target_column: str) -> float:
    if frame.empty or match_column not in frame.columns or target_column not in frame.columns:
        return 0.0
    matched = frame[frame[match_column].astype(str) == match_value]
    if matched.empty:
        return 0.0
    return _safe_float(matched.iloc[0].get(target_column))


def _scaled_amount(raw_value: object) -> float | None:
    if raw_value in (None, "", "null"):
        return None
    return round(_safe_float(raw_value) / 100000000, 2)


def _format_amount(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:+.1f} 亿"


def _format_percent(value: float | None, *, digits: int = 1) -> str:
    if value is None:
        return "--"
    return f"{value:+.{digits}f}%"


def _tone_from_amount(
    value: float | None,
    *,
    positive_threshold: float,
    negative_threshold: float,
) -> str:
    if value is None:
        return "neutral"
    if value >= positive_threshold:
        return "positive"
    if value <= negative_threshold:
        return "negative"
    return "neutral"


def _safe_float(value: object) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_optional_float(value: object) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_date(value: object) -> str | None:
    if value in (None, "", "null"):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return str(parsed.date())
