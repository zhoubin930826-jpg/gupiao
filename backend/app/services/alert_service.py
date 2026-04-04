from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.alert import AlertEvent
from app.models.portfolio import PortfolioPosition
from app.models.trade_plan import TradePlanEntry
from app.models.watchlist import WatchlistEntry
from app.schemas.market import AlertStatusUpdateRequest
from app.services.market_store import MarketDataStore
from app.services.portfolio_service import PortfolioService
from app.services.trade_plan_service import TradePlanService
from app.services.watchlist_service import WatchlistService

_ACTIVE_STATUS_ORDER = {"active": 0, "handled": 1, "resolved": 2}
_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
_CONCENTRATION_THRESHOLD = 35.0
_PLAN_TRIGGER_GAP_PCT = 1.5
_TARGET_NEAR_PCT = 0.98
_WATCHLIST_SCORE_THRESHOLD = 85
_WATCHLIST_STRENGTH_CHANGE_PCT = 5.0


class AlertService:
    @classmethod
    def refresh_alerts(
        cls,
        db: Session,
        market_store: MarketDataStore,
    ) -> dict[str, object]:
        now = _now()
        candidates = cls._build_candidates(db, market_store)
        existing_rows = db.query(AlertEvent).all()
        existing_map = {row.event_key: row for row in existing_rows}
        seen_keys: set[str] = set()

        for candidate in candidates:
            event_key = str(candidate["event_key"])
            seen_keys.add(event_key)
            row = existing_map.get(event_key)
            if row is None:
                row = AlertEvent(
                    event_key=event_key,
                    last_seen_at=now,
                    **cls._model_payload(candidate),
                )
            else:
                previous_severity = row.severity
                if row.status == "resolved":
                    row.status = "active"
                    row.resolved_at = None
                elif row.status == "handled" and candidate["severity"] == "critical" and previous_severity != "critical":
                    row.status = "active"
                for field, value in cls._model_payload(candidate).items():
                    setattr(row, field, value)
                row.last_seen_at = now
                row.resolved_at = None if row.status != "resolved" else row.resolved_at
            db.add(row)

        for row in existing_rows:
            if row.event_key in seen_keys or row.status == "resolved":
                continue
            row.status = "resolved"
            row.last_seen_at = now
            row.resolved_at = now
            db.add(row)

        db.commit()
        return cls.build_overview(db)

    @classmethod
    def build_overview(
        cls,
        db: Session,
        *,
        status: str | None = None,
        severity: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        rows = db.query(AlertEvent).all()
        serialized = [cls._serialize(row) for row in rows]
        serialized.sort(key=lambda item: item["updated_at"], reverse=True)
        serialized.sort(key=lambda item: _SEVERITY_ORDER.get(str(item["severity"]), 99))
        serialized.sort(key=lambda item: _ACTIVE_STATUS_ORDER.get(str(item["status"]), 99))

        filtered = [
            item
            for item in serialized
            if (status is None or item["status"] == status)
            and (severity is None or item["severity"] == severity)
            and (category is None or item["category"] == category)
        ]

        latest_evaluated_at = None
        if serialized:
            latest_evaluated_at = max(
                str(item["last_seen_at"])
                for item in serialized
            )

        return {
            "total_count": len(serialized),
            "filtered_count": len(filtered),
            "active_count": sum(1 for item in serialized if item["status"] == "active"),
            "handled_count": sum(1 for item in serialized if item["status"] == "handled"),
            "resolved_count": sum(1 for item in serialized if item["status"] == "resolved"),
            "critical_count": sum(1 for item in serialized if item["severity"] == "critical"),
            "warning_count": sum(1 for item in serialized if item["severity"] == "warning"),
            "info_count": sum(1 for item in serialized if item["severity"] == "info"),
            "latest_evaluated_at": latest_evaluated_at,
            "items": filtered[:limit],
        }

    @classmethod
    def update_status(
        cls,
        db: Session,
        *,
        alert_id: int,
        payload: AlertStatusUpdateRequest,
    ) -> dict[str, object]:
        row = db.query(AlertEvent).filter_by(id=alert_id).first()
        if row is None:
            raise KeyError(str(alert_id))

        row.status = payload.status
        row.resolved_at = _now() if payload.status == "resolved" else None
        db.add(row)
        db.commit()
        db.refresh(row)
        return cls._serialize(row)

    @staticmethod
    def _serialize(row: AlertEvent) -> dict[str, object]:
        payload = json.loads(row.payload_json) if row.payload_json else {}
        return {
            "id": row.id,
            "event_key": row.event_key,
            "status": row.status,
            "severity": row.severity,
            "category": row.category,
            "kind": row.kind,
            "symbol": row.symbol,
            "name": row.name,
            "title": row.title,
            "message": row.message,
            "action_path": row.action_path,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "last_value": _rounded_optional(row.last_value),
            "threshold_value": _rounded_optional(row.threshold_value),
            "payload": payload,
            "created_at": row.created_at.isoformat(timespec="seconds"),
            "last_seen_at": row.last_seen_at.isoformat(timespec="seconds"),
            "resolved_at": row.resolved_at.isoformat(timespec="seconds") if row.resolved_at else None,
            "updated_at": row.updated_at.isoformat(timespec="seconds"),
        }

    @staticmethod
    def _model_payload(candidate: dict[str, object]) -> dict[str, object]:
        payload = dict(candidate)
        payload.pop("event_key", None)
        payload["payload_json"] = json.dumps(payload.get("payload") or {}, ensure_ascii=False)
        payload.pop("payload", None)
        return payload

    @classmethod
    def _build_candidates(
        cls,
        db: Session,
        market_store: MarketDataStore,
    ) -> list[dict[str, object]]:
        candidates: list[dict[str, object]] = []
        candidates.extend(cls._trade_plan_candidates(db, market_store))
        candidates.extend(cls._portfolio_candidates(db, market_store))
        candidates.extend(cls._watchlist_candidates(db, market_store))
        return candidates

    @classmethod
    def _trade_plan_candidates(
        cls,
        db: Session,
        market_store: MarketDataStore,
    ) -> list[dict[str, object]]:
        rows = TradePlanService.list_items(db, market_store)
        candidates: list[dict[str, object]] = []
        for item in rows:
            latest_price = _optional_float(item.get("latest_price"))
            planned_entry = _optional_float(item.get("planned_entry_price"))
            stop_loss = _optional_float(item.get("stop_loss_price"))
            target_price = _optional_float(item.get("target_price"))
            symbol = str(item["symbol"])
            name = str(item["name"])
            source_id = int(item["id"])
            status = str(item["status"])

            if status == "planned" and latest_price and planned_entry and planned_entry > 0:
                gap_pct = abs(_optional_float(item.get("plan_gap_pct")) or 0.0)
                if gap_pct <= _PLAN_TRIGGER_GAP_PCT:
                    candidates.append(
                        cls._candidate(
                            event_key=f"trade_plan:{source_id}:entry-zone",
                            severity="warning",
                            category="trade_plan",
                            kind="entry_zone",
                            symbol=symbol,
                            name=name,
                            title=f"{name} 接近计划买点",
                            message=f"最新价 {latest_price:.2f}，距离计划价 {planned_entry:.2f} 仅 {gap_pct:.2f}%，可以决定是否开始执行计划。",
                            action_path="/trade-plans",
                            source_type="trade_plan",
                            source_id=source_id,
                            last_value=latest_price,
                            threshold_value=planned_entry,
                            payload={"gap_pct": round(gap_pct, 2), "status": status},
                        )
                    )
                if stop_loss is not None and latest_price <= stop_loss:
                    candidates.append(
                        cls._candidate(
                            event_key=f"trade_plan:{source_id}:plan-invalidated",
                            severity="critical",
                            category="trade_plan",
                            kind="plan_invalidated",
                            symbol=symbol,
                            name=name,
                            title=f"{name} 计划已接近失效位",
                            message=f"最新价 {latest_price:.2f} 已低于计划止损价 {stop_loss:.2f}，原计划需要重新评估。",
                            action_path="/trade-plans",
                            source_type="trade_plan",
                            source_id=source_id,
                            last_value=latest_price,
                            threshold_value=stop_loss,
                            payload={"status": status},
                        )
                    )

            if status == "active" and latest_price:
                if stop_loss is not None and latest_price <= stop_loss:
                    candidates.append(
                        cls._candidate(
                            event_key=f"trade_plan:{source_id}:stop-loss",
                            severity="critical",
                            category="trade_plan",
                            kind="stop_loss",
                            symbol=symbol,
                            name=name,
                            title=f"{name} 活动计划触及止损",
                            message=f"最新价 {latest_price:.2f} 已落到止损价 {stop_loss:.2f} 下方，建议确认是否退出计划。",
                            action_path="/trade-plans",
                            source_type="trade_plan",
                            source_id=source_id,
                            last_value=latest_price,
                            threshold_value=stop_loss,
                            payload={"status": status},
                        )
                    )
                elif target_price is not None and latest_price >= target_price * _TARGET_NEAR_PCT:
                    candidates.append(
                        cls._candidate(
                            event_key=f"trade_plan:{source_id}:target-near",
                            severity="info",
                            category="trade_plan",
                            kind="target_near",
                            symbol=symbol,
                            name=name,
                            title=f"{name} 活动计划接近目标位",
                            message=f"最新价 {latest_price:.2f} 已接近目标价 {target_price:.2f}，可以提前规划止盈动作。",
                            action_path="/trade-plans",
                            source_type="trade_plan",
                            source_id=source_id,
                            last_value=latest_price,
                            threshold_value=target_price,
                            payload={"status": status},
                        )
                    )
        return candidates

    @classmethod
    def _portfolio_candidates(
        cls,
        db: Session,
        market_store: MarketDataStore,
    ) -> list[dict[str, object]]:
        overview = PortfolioService.build_overview(db, market_store)
        candidates: list[dict[str, object]] = []
        for item in overview["positions"]:
            if item["status"] != "holding":
                continue

            latest_price = _optional_float(item.get("latest_price"))
            stop_loss = _optional_float(item.get("stop_loss_price"))
            target_price = _optional_float(item.get("target_price"))
            weight_pct = _optional_float(item.get("weight_pct"))
            unrealized_return = _optional_float(item.get("unrealized_return"))
            symbol = str(item["symbol"])
            name = str(item["name"])
            source_id = int(item["id"])

            if latest_price is not None and stop_loss is not None and latest_price <= stop_loss:
                candidates.append(
                    cls._candidate(
                        event_key=f"portfolio:{source_id}:stop-loss",
                        severity="critical",
                        category="portfolio",
                        kind="stop_loss",
                        symbol=symbol,
                        name=name,
                        title=f"{name} 持仓触及止损",
                        message=f"持仓最新价 {latest_price:.2f} 已落到止损价 {stop_loss:.2f} 下方，建议优先处理。",
                        action_path="/portfolio",
                        source_type="portfolio",
                        source_id=source_id,
                        last_value=latest_price,
                        threshold_value=stop_loss,
                        payload={"unrealized_return": unrealized_return},
                    )
                )
            if latest_price is not None and target_price is not None and latest_price >= target_price * _TARGET_NEAR_PCT:
                candidates.append(
                    cls._candidate(
                        event_key=f"portfolio:{source_id}:target-near",
                        severity="warning",
                        category="portfolio",
                        kind="target_near",
                        symbol=symbol,
                        name=name,
                        title=f"{name} 持仓接近目标位",
                        message=f"持仓最新价 {latest_price:.2f} 已接近目标价 {target_price:.2f}，可以准备分批止盈。",
                        action_path="/portfolio",
                        source_type="portfolio",
                        source_id=source_id,
                        last_value=latest_price,
                        threshold_value=target_price,
                        payload={"weight_pct": weight_pct},
                    )
                )
            if weight_pct is not None and weight_pct >= _CONCENTRATION_THRESHOLD:
                candidates.append(
                    cls._candidate(
                        event_key=f"portfolio:{source_id}:concentration",
                        severity="warning",
                        category="portfolio",
                        kind="concentration",
                        symbol=symbol,
                        name=name,
                        title=f"{name} 单票仓位偏重",
                        message=f"当前持仓权重大约 {weight_pct:.2f}%，已经接近或超过集中度阈值 {_CONCENTRATION_THRESHOLD:.0f}%。",
                        action_path="/portfolio",
                        source_type="portfolio",
                        source_id=source_id,
                        last_value=weight_pct,
                        threshold_value=_CONCENTRATION_THRESHOLD,
                        payload={"latest_price": latest_price},
                    )
                )
            if unrealized_return is not None and unrealized_return <= -8:
                candidates.append(
                    cls._candidate(
                        event_key=f"portfolio:{source_id}:drawdown",
                        severity="warning",
                        category="portfolio",
                        kind="drawdown",
                        symbol=symbol,
                        name=name,
                        title=f"{name} 持仓回撤扩大",
                        message=f"当前浮动收益约 {unrealized_return:.2f}%，已经进入需要复核纪律的位置。",
                        action_path="/portfolio",
                        source_type="portfolio",
                        source_id=source_id,
                        last_value=unrealized_return,
                        threshold_value=-8.0,
                        payload={"latest_price": latest_price},
                    )
                )
        return candidates

    @classmethod
    def _watchlist_candidates(
        cls,
        db: Session,
        market_store: MarketDataStore,
    ) -> list[dict[str, object]]:
        rows = WatchlistService.list_items(db, market_store)
        candidates: list[dict[str, object]] = []
        for item in rows:
            if item["status"] != "watching":
                continue

            score = _optional_float(item.get("score"))
            change_pct = _optional_float(item.get("change_pct"))
            latest_price = _optional_float(item.get("latest_price"))
            symbol = str(item["symbol"])
            name = str(item["name"])

            if score is not None and score >= _WATCHLIST_SCORE_THRESHOLD:
                candidates.append(
                    cls._candidate(
                        event_key=f"watchlist:{symbol}:high-score",
                        severity="info",
                        category="watchlist",
                        kind="high_score",
                        symbol=symbol,
                        name=name,
                        title=f"{name} 进入高分观察区",
                        message=f"自选股当前评分 {score:.0f} 分，已经进入值得优先复核的高分区间。",
                        action_path="/watchlist",
                        source_type="watchlist",
                        source_id=None,
                        last_value=score,
                        threshold_value=float(_WATCHLIST_SCORE_THRESHOLD),
                        payload={"change_pct": change_pct, "latest_price": latest_price},
                    )
                )
            if (
                score is not None
                and score >= 75
                and change_pct is not None
                and change_pct >= _WATCHLIST_STRENGTH_CHANGE_PCT
            ):
                candidates.append(
                    cls._candidate(
                        event_key=f"watchlist:{symbol}:turning-strong",
                        severity="warning",
                        category="watchlist",
                        kind="turning_strong",
                        symbol=symbol,
                        name=name,
                        title=f"{name} 自选股出现异动转强",
                        message=f"自选股当日涨幅 {change_pct:.2f}%，评分 {score:.0f} 分，适合重新放回重点观察池。",
                        action_path="/watchlist",
                        source_type="watchlist",
                        source_id=None,
                        last_value=change_pct,
                        threshold_value=_WATCHLIST_STRENGTH_CHANGE_PCT,
                        payload={"score": score, "latest_price": latest_price},
                    )
                )
        return candidates

    @staticmethod
    def _candidate(
        *,
        event_key: str,
        severity: str,
        category: str,
        kind: str,
        symbol: str | None,
        name: str | None,
        title: str,
        message: str,
        action_path: str | None,
        source_type: str | None,
        source_id: int | None,
        last_value: float | None,
        threshold_value: float | None,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return {
            "event_key": event_key,
            "status": "active",
            "severity": severity,
            "category": category,
            "kind": kind,
            "symbol": symbol,
            "name": name,
            "title": title,
            "message": message,
            "action_path": action_path,
            "source_type": source_type,
            "source_id": source_id,
            "last_value": last_value,
            "threshold_value": threshold_value,
            "payload": payload or {},
        }


def _now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().app_timezone))


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rounded_optional(value: object) -> float | None:
    number = _optional_float(value)
    return round(number, 2) if number is not None else None
