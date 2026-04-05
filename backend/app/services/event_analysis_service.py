from __future__ import annotations

from typing import Any, Literal, Mapping

EventTone = Literal["positive", "neutral", "caution"]

POSITIVE_FORECAST_TYPES = {"预增", "略增", "扭亏", "续盈", "大幅上升", "预盈"}
CAUTION_FORECAST_TYPES = {"预减", "略减", "首亏", "续亏", "增亏", "大幅下降"}

POSITIVE_NOTICE_KEYWORDS: dict[str, str] = {
    "中标": "中标催化",
    "回购": "回购计划",
    "增持": "增持信号",
    "签订": "订单催化",
    "合同": "订单催化",
    "调研": "调研催化",
    "获批": "审批进展",
    "分红": "分红方案",
}
CAUTION_NOTICE_KEYWORDS: dict[str, str] = {
    "风险": "风险提示",
    "减持": "减持压力",
    "质押": "质押风险",
    "诉讼": "诉讼事项",
    "终止": "事项终止",
    "问询": "监管问询",
    "处罚": "监管处罚",
    "退市": "退市风险",
    "异常波动": "异动核查",
}


def build_event_analysis(
    *,
    notices: list[Mapping[str, Any]] | None = None,
    earnings_forecast: Mapping[str, Any] | None = None,
    external_items: list[Mapping[str, Any]] | None = None,
) -> dict[str, object]:
    notice_rows = notices or []
    extra_items = external_items or []
    items: list[dict[str, object]] = []
    tags: list[str] = []
    watch_points: list[str] = []
    positive_points: list[str] = []
    caution_points: list[str] = []

    if earnings_forecast:
        forecast_item = _build_forecast_item(earnings_forecast)
        items.append(forecast_item)
        forecast_type = _safe_text(earnings_forecast.get("预告类型"))
        if forecast_item["tone"] == "positive":
            positive_points.append(f"最近披露了 {forecast_type or '偏正面'} 的业绩预告。")
            watch_points.append("重点看正式财报能否兑现预告强度，避免只停留在预期层。")
        elif forecast_item["tone"] == "caution":
            caution_points.append(f"最近披露了 {forecast_type or '偏弱'} 的业绩预告。")
            watch_points.append("若下一份正式财报继续走弱，事件层压力会明显放大。")
        else:
            watch_points.append("业绩预告偏中性，更要看后续量价和财务兑现是否同步。")
        tags.extend(forecast_item.get("tags", []))

    for notice in notice_rows[:3]:
        notice_item = _build_notice_item(notice)
        items.append(notice_item)
        if notice_item["tone"] == "positive":
            positive_points.append(str(notice_item["headline"]))
        elif notice_item["tone"] == "caution":
            caution_points.append(str(notice_item["headline"]))
        tags.extend(notice_item.get("tags", []))
        watch_points.extend(notice_item.get("watch_points", []))

    for external_item in extra_items[:4]:
        normalized_item = _build_external_item(external_item)
        items.append(normalized_item)
        if normalized_item["tone"] == "positive":
            positive_points.append(str(normalized_item["headline"]))
        elif normalized_item["tone"] == "caution":
            caution_points.append(str(normalized_item["headline"]))
        tags.extend(normalized_item.get("tags", []))
        watch_points.extend(normalized_item.get("watch_points", []))

    tone = _resolve_tone(items)
    summary = _build_summary(
        tone=tone,
        positive_points=positive_points,
        caution_points=caution_points,
        has_forecast=earnings_forecast is not None,
        notice_count=len(notice_rows),
        external_count=len(extra_items),
    )

    if not items:
        watch_points.append("最近没有抓到明显的结构化事件催化，短线更依赖趋势和资金面自己走出来。")
    elif tone == "positive":
        watch_points.append("事件催化偏正面时，更要盯后续量能能否接住，而不是只看标题。")
    elif tone == "caution":
        watch_points.append("事件层偏谨慎时，更适合先看风险是否消化，再决定是否提前参与。")

    return {
        "tone": tone,
        "summary": summary,
        "tags": _unique(tags)[:3],
        "items": items[:4],
        "watch_points": _unique(watch_points)[:3],
    }


def _build_forecast_item(payload: Mapping[str, Any]) -> dict[str, object]:
    forecast_type = _safe_text(payload.get("预告类型")) or "业绩预告"
    prediction = _safe_text(payload.get("业绩变动")) or _safe_text(payload.get("预测指标")) or "最新业绩预告"
    reason = _safe_text(payload.get("业绩变动原因"))
    detail = prediction
    if reason:
        detail = f"{prediction} 原因：{_truncate(reason, 82)}"

    tone: EventTone = "neutral"
    tags: list[str] = ["业绩预告"]
    if forecast_type in POSITIVE_FORECAST_TYPES:
        tone = "positive"
        tags.append("业绩预喜")
    elif forecast_type in CAUTION_FORECAST_TYPES:
        tone = "caution"
        tags.append("业绩承压")

    return {
        "date": _serialize_date(payload.get("公告日期")),
        "category": "业绩预告",
        "title": f"{forecast_type} 业绩预告",
        "headline": f"业绩预告显示 {forecast_type}",
        "detail": detail,
        "tone": tone,
        "source": "业绩预告",
        "url": None,
        "tags": tags,
        "watch_points": [],
    }


def _build_notice_item(payload: Mapping[str, Any]) -> dict[str, object]:
    title = _safe_text(payload.get("公告标题")) or "公告更新"
    notice_type = _safe_text(payload.get("公告类型")) or "公告"
    combined = f"{title} {notice_type}"
    tone: EventTone = "neutral"
    tags: list[str] = ["公告动态"]
    watch_points: list[str] = []

    for keyword, tag in POSITIVE_NOTICE_KEYWORDS.items():
        if keyword in combined:
            tone = "positive"
            tags.append(tag)
            if tag == "调研催化":
                watch_points.append("调研活动更偏情绪催化，关键还是看后续成交和价格承接。")
            break

    if tone == "neutral":
        for keyword, tag in CAUTION_NOTICE_KEYWORDS.items():
            if keyword in combined:
                tone = "caution"
                tags.append(tag)
                watch_points.append("先看公告事项会不会继续发酵，再决定是否提前把它提到前排。")
                break

    detail = f"{notice_type}：{title}"
    return {
        "date": _serialize_date(payload.get("公告日期")),
        "category": "公告",
        "title": notice_type,
        "headline": title,
        "detail": _truncate(detail, 88),
        "tone": tone,
        "source": "公告",
        "url": _safe_text(payload.get("网址")),
        "tags": tags,
        "watch_points": watch_points,
    }


def _resolve_tone(items: list[Mapping[str, Any]]) -> EventTone:
    score = 0
    for item in items:
        tone = item.get("tone")
        if tone == "positive":
            score += 2
        elif tone == "caution":
            score -= 2
    if score >= 2:
        return "positive"
    if score <= -2:
        return "caution"
    return "neutral"


def _build_summary(
    *,
    tone: EventTone,
    positive_points: list[str],
    caution_points: list[str],
    has_forecast: bool,
    notice_count: int,
    external_count: int,
) -> str:
    if tone == "positive":
        lead = positive_points[0] if positive_points else "最近事件层偏正面"
        suffix = "公告和业绩催化对情绪有加分。"
        if has_forecast and notice_count:
            suffix = "业绩预告和公告动态同时给到正向催化。"
        elif external_count:
            suffix = "财报日历或外部事件也在给情绪加分。"
        return f"{lead}，{suffix}"
    if tone == "caution":
        lead = caution_points[0] if caution_points else "最近事件层偏谨慎"
        suffix = "相关事项还需要继续验证，短线不宜只看标题追高。"
        return f"{lead}，{suffix}"
    if has_forecast or notice_count or external_count:
        return "最近有结构化事件更新，但整体偏中性，更适合结合量价和趋势一起看。"
    return "最近没有捕捉到明显的公告或业绩预告催化，事件层暂时中性。"


def _build_external_item(payload: Mapping[str, Any]) -> dict[str, object]:
    title = _safe_text(payload.get("title")) or _safe_text(payload.get("category")) or "事件更新"
    headline = _safe_text(payload.get("headline")) or title
    detail = _safe_text(payload.get("detail")) or headline
    tone = payload.get("tone")
    if tone not in {"positive", "neutral", "caution"}:
        tone = "neutral"
    tags = payload.get("tags")
    watch_points = payload.get("watch_points")
    return {
        "date": _serialize_date(payload.get("date")),
        "category": _safe_text(payload.get("category")) or "事件",
        "title": title,
        "headline": headline,
        "detail": _truncate(detail, 88),
        "tone": tone,
        "source": _safe_text(payload.get("source")) or "外部事件",
        "url": _safe_text(payload.get("url")),
        "tags": [str(item).strip() for item in tags] if isinstance(tags, list) else [],
        "watch_points": [str(item).strip() for item in watch_points] if isinstance(watch_points, list) else [],
    }


def _serialize_date(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truncate(value: str, limit: int) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}..."


def _safe_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan" or text == "NaT":
        return None
    return text


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
