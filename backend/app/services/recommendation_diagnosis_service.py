from __future__ import annotations

from typing import Any, Mapping

from app.schemas.market import StrategyConfig


class RecommendationDiagnosisService:
    @staticmethod
    def build(
        *,
        detail: Mapping[str, Any],
        ranking: Mapping[str, Any],
        strategy: StrategyConfig,
    ) -> dict[str, object]:
        current_rank = int(ranking.get("current_rank") or 0)
        total_candidates = int(ranking.get("total_candidates") or 0)
        recommendation_limit = int(ranking.get("recommendation_limit") or 8)
        cutoff_score = _to_int(ranking.get("cutoff_score"))
        cutoff_name = _to_text(ranking.get("cutoff_name"))
        cutoff_symbol = _to_text(ranking.get("cutoff_symbol"))
        current_score = _to_int(detail.get("score")) or 0
        is_recommended = current_rank > 0 and current_rank <= recommendation_limit
        gap_to_limit = max(current_rank - recommendation_limit, 0)
        score_gap_to_cutoff = None
        if cutoff_score is not None and not is_recommended:
            score_gap_to_cutoff = max(cutoff_score - current_score, 0)

        signal_breakdown = [
            item for item in detail.get("signal_breakdown", []) if isinstance(item, Mapping)
        ]
        strong_signals = sorted(
            signal_breakdown,
            key=lambda item: int(item.get("score") or 0),
            reverse=True,
        )
        weak_signals = sorted(signal_breakdown, key=lambda item: int(item.get("score") or 0))
        move_analysis = detail.get("move_analysis") if isinstance(detail.get("move_analysis"), Mapping) else None
        risk_notes = [str(item) for item in detail.get("risk_notes", []) if str(item).strip()]

        reason_points: list[str] = []
        blocking_points: list[str] = []
        action_points: list[str] = []

        if is_recommended:
            reason_points.append(
                f"当前综合评分 {current_score} 分，排在候选池第 {current_rank}/{total_candidates}，已经进入今日前 {recommendation_limit}。"
            )
        else:
            if score_gap_to_cutoff is not None:
                blocker = f"当前综合评分 {current_score} 分，距离第 {recommendation_limit} 名"
                if cutoff_name:
                    blocker += f" {cutoff_name}"
                blocker += f" 的 {cutoff_score} 分还差 {score_gap_to_cutoff} 分。"
                blocking_points.append(blocker)
            else:
                blocking_points.append(
                    f"当前排在候选池第 {current_rank}/{total_candidates}，暂时还没进入今日前 {recommendation_limit}。"
                )

        for signal in strong_signals[:2]:
            dimension = str(signal.get("dimension") or "信号")
            reason_points.append(
                f"{dimension} {int(signal.get('score') or 0)} 分，{str(signal.get('takeaway') or '').strip()}"
            )

        if move_analysis:
            summary = str(move_analysis.get("summary") or "").strip()
            if summary:
                if is_recommended:
                    reason_points.append(summary)
                else:
                    blocking_points.append(summary)

        for signal in weak_signals[:2]:
            dimension = str(signal.get("dimension") or "信号")
            score = int(signal.get("score") or 0)
            takeaway = str(signal.get("takeaway") or "").strip()
            if score < 78:
                blocking_points.append(f"{dimension} 只有 {score} 分，{takeaway}")

        change_pct = _to_float(detail.get("change_pct")) or 0.0
        turnover_ratio = _to_float(detail.get("turnover_ratio")) or 0.0
        if not is_recommended and change_pct < 0:
            blocking_points.append(f"当日涨跌幅 {change_pct:.2f}%，短线强度不足，系统不会优先给到前排。")
        if not is_recommended and turnover_ratio < max(strategy.min_turnover * 1.35, 2.0):
            blocking_points.append(
                f"当前换手率 {turnover_ratio:.2f}% 虽然过了最低门槛，但相对今日前排候选仍偏弱。"
            )

        if risk_notes:
            blocking_points.append(risk_notes[0])

        action_points.extend(_move_watch_points(move_analysis))
        weakest_signal = weak_signals[0] if weak_signals else None
        if weakest_signal is not None:
            action_points.append(_signal_action(weakest_signal))
        if not is_recommended and score_gap_to_cutoff and score_gap_to_cutoff > 0:
            action_points.append("更适合等下一次评分重新抬升后再看，不用急着把它当成今日主选。")

        summary = _build_summary(
            is_recommended=is_recommended,
            current_rank=current_rank,
            total_candidates=total_candidates,
            recommendation_limit=recommendation_limit,
            strong_signals=strong_signals,
            weak_signals=weak_signals,
            cutoff_name=cutoff_name,
            cutoff_score=cutoff_score,
        )

        return {
            "is_recommended": is_recommended,
            "current_rank": current_rank,
            "total_candidates": total_candidates,
            "recommendation_limit": recommendation_limit,
            "gap_to_limit": gap_to_limit,
            "score_gap_to_cutoff": score_gap_to_cutoff,
            "cutoff_symbol": cutoff_symbol,
            "cutoff_name": cutoff_name,
            "cutoff_score": cutoff_score,
            "summary": summary,
            "reason_points": _unique(reason_points)[:3],
            "blocking_points": _unique(blocking_points)[:4],
            "action_points": _unique(action_points)[:3],
        }


def _build_summary(
    *,
    is_recommended: bool,
    current_rank: int,
    total_candidates: int,
    recommendation_limit: int,
    strong_signals: list[Mapping[str, Any]],
    weak_signals: list[Mapping[str, Any]],
    cutoff_name: str | None,
    cutoff_score: int | None,
) -> str:
    best_dimension = str(strong_signals[0].get("dimension") or "强项") if strong_signals else "综合强度"
    weak_dimension = str(weak_signals[0].get("dimension") or "短板") if weak_signals else "短板"
    if is_recommended:
        return (
            f"这只票今天排在第 {current_rank}/{total_candidates}，已经进入推荐池，当前更像由 {best_dimension} 领先带动的入选。"
        )

    cutoff_hint = ""
    if cutoff_name and cutoff_score is not None:
        cutoff_hint = f"，当前前 {recommendation_limit} 的门槛大致在 {cutoff_name} 的 {cutoff_score} 分附近"
    return (
        f"这只票今天排在第 {current_rank}/{total_candidates}，还没进前 {recommendation_limit}{cutoff_hint}，主要是 {weak_dimension} 暂时拖了后腿。"
    )


def _move_watch_points(move_analysis: Mapping[str, Any] | None) -> list[str]:
    if not move_analysis:
        return []
    return [
        str(item)
        for item in move_analysis.get("watch_points", [])
        if str(item).strip()
    ]


def _signal_action(signal: Mapping[str, Any]) -> str:
    dimension = str(signal.get("dimension") or "")
    if dimension == "技术面":
        return "技术面是当前短板，更适合等趋势重新确认，比如站稳关键均线或回踩承接后再看。"
    if dimension == "资金面":
        return "资金面是当前短板，更适合等换手和量能重新放大后，再看能不能往前排走。"
    if dimension == "基本面":
        return "基本面是当前短板，这类票更需要财务增速或估值端给出更强支撑。"
    if dimension == "情绪面":
        return "情绪面是当前短板，可以先等板块热度和短线强度回暖。"
    return "更适合等弱项修复后，再把它放回今天的重点观察池。"


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _to_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
