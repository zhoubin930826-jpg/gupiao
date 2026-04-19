from __future__ import annotations

from typing import Any, Literal, Mapping


def data_mode_from_source(source: str) -> Literal["demo", "live"]:
    return "demo" if str(source).startswith("sample") else "live"


def build_recommendation_trust(
    *,
    source: str,
    snapshot_updated_at: str,
    signal_breakdown: list[Mapping[str, Any]],
    risk_notes: list[str],
) -> dict[str, object]:
    strongest_signals = [
        {
            "dimension": str(item.get("dimension") or "信号"),
            "score": int(item.get("score") or 0),
            "takeaway": str(item.get("takeaway") or "").strip(),
        }
        for item in sorted(
            signal_breakdown,
            key=lambda item: int(item.get("score") or 0),
            reverse=True,
        )[:2]
    ]
    data_mode = data_mode_from_source(source)
    primary_risk = next(
        (item.strip() for item in risk_notes if item.strip()),
        "当前仍需人工复核主要风险。",
    )
    signal_base = (
        round(sum(int(item["score"]) for item in strongest_signals) / len(strongest_signals))
        if strongest_signals
        else 55
    )
    mode_bonus = 10 if data_mode == "live" else -10
    risk_penalty = 8 if any(item.strip() for item in risk_notes) else 0
    confidence_score = int(max(20, min(95, round(signal_base * 0.7 + mode_bonus - risk_penalty))))
    confidence_notice = (
        "当前基于真实同步快照，适合优先人工复核，但仍需结合主要风险控制节奏。"
        if data_mode == "live"
        else "当前基于示例快照，只适合流程演示，不宜直接当成真实效果判断。"
    )
    return {
        "data_mode": data_mode,
        "snapshot_updated_at": snapshot_updated_at,
        "strongest_signals": strongest_signals,
        "primary_risk": primary_risk,
        "confidence_score": confidence_score,
        "confidence_notice": confidence_notice,
    }
