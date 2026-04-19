import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings


@dataclass(frozen=True)
class DemoStock:
    symbol: str
    name: str
    board: str
    industry: str
    latest_price: float
    change_pct: float
    turnover_ratio: float
    pe_ttm: float
    market_cap: float
    score: int
    thesis: str
    tags: tuple[str, ...]
    thesis_points: tuple[str, ...]
    risk_notes: tuple[str, ...]
    risk: str
    entry_window: str
    expected_holding_days: int
    signal_breakdown: tuple[tuple[str, int, str], ...]


DEMO_STOCKS: tuple[DemoStock, ...] = (
    DemoStock(
        symbol="300308",
        name="中际旭创",
        board="创业板",
        industry="光模块",
        latest_price=162.30,
        change_pct=3.28,
        turnover_ratio=4.90,
        pe_ttm=28.4,
        market_cap=1820.0,
        score=91,
        thesis="算力链景气度高位延续，趋势和资金共振明显。",
        tags=("算力", "高景气", "趋势延续"),
        thesis_points=(
            "近 20 日强于板块均值，趋势延续性较好。",
            "量价配合顺畅，突破后回踩幅度可控。",
            "资金偏好仍在主线，短中期热度没有明显走弱。",
        ),
        risk_notes=(
            "高位股波动会放大，回撤可能快于预期。",
            "算力链若阶段性降温，主线溢价会下降。",
        ),
        risk="高位波动较大，需要盯住放量滞涨信号。",
        entry_window="回踩 5 日线附近观察",
        expected_holding_days=8,
        signal_breakdown=(
            ("技术面", 94, "均线多头排列，趋势仍然健康。"),
            ("基本面", 84, "景气赛道支撑估值，但已不算便宜。"),
            ("资金面", 93, "换手和强度都保持在高位。"),
            ("情绪面", 90, "主线资金偏好仍然明确。"),
        ),
    ),
    DemoStock(
        symbol="688981",
        name="中芯国际",
        board="科创板",
        industry="半导体",
        latest_price=55.80,
        change_pct=2.42,
        turnover_ratio=3.60,
        pe_ttm=52.1,
        market_cap=4410.0,
        score=88,
        thesis="国产替代逻辑稳定，半导体情绪回暖后弹性较好。",
        tags=("国产替代", "科技主线", "科创板"),
        thesis_points=(
            "半导体板块温度回升，龙头弹性先行释放。",
            "大市值龙头在情绪恢复时更容易承接资金。",
            "价格结构在中期均线上方，具备继续观察价值。",
        ),
        risk_notes=(
            "PE 偏高，估值弹性依赖行业预期。",
            "大盘风险偏好下降时，科技股回撤更明显。",
        ),
        risk="估值不低，适合顺势跟踪，不适合逆势重仓。",
        entry_window="放量突破前高后跟踪",
        expected_holding_days=10,
        signal_breakdown=(
            ("技术面", 86, "中期趋势良好，短线待放量确认。"),
            ("基本面", 82, "国产替代逻辑强，但盈利修复还要跟踪。"),
            ("资金面", 88, "资金承接较稳。"),
            ("情绪面", 88, "科技方向偏好明显改善。"),
        ),
    ),
    DemoStock(
        symbol="002594",
        name="比亚迪",
        board="主板",
        industry="新能源车",
        latest_price=242.60,
        change_pct=1.82,
        turnover_ratio=2.70,
        pe_ttm=24.9,
        market_cap=7060.0,
        score=85,
        thesis="整车龙头具备基本面支撑，适合作为稳健高分核心票。",
        tags=("龙头", "新能源", "基本面稳"),
        thesis_points=(
            "龙头属性明显，回撤后更容易被配置资金承接。",
            "估值处于可接受区间，基本面有支撑。",
            "适合做组合中偏稳健的主仓方向。",
        ),
        risk_notes=(
            "板块轮动过快时，整车可能被高弹性方向分流。",
            "高市值个股向上斜率通常慢于题材股。",
        ),
        risk="向上弹性略逊于小票，需要接受节奏更慢。",
        entry_window="缩量回踩 10 日线",
        expected_holding_days=12,
        signal_breakdown=(
            ("技术面", 82, "趋势温和上行，适合跟踪低吸。"),
            ("基本面", 90, "龙头基本盘扎实。"),
            ("资金面", 80, "资金表现稳定但不算极强。"),
            ("情绪面", 84, "板块情绪平稳偏暖。"),
        ),
    ),
    DemoStock(
        symbol="601899",
        name="紫金矿业",
        board="主板",
        industry="有色金属",
        latest_price=19.42,
        change_pct=1.55,
        turnover_ratio=2.10,
        pe_ttm=17.8,
        market_cap=5120.0,
        score=83,
        thesis="资源品趋势稳，适合作为防御和弹性的平衡仓位。",
        tags=("资源股", "防守反击", "趋势"),
        thesis_points=(
            "资源股在风险偏好切换时表现相对稳定。",
            "估值不高，具备一定安全垫。",
            "适合作为组合里的对冲型方向。",
        ),
        risk_notes=(
            "大宗商品价格回落会直接压制预期。",
            "题材行情极热时，资源方向关注度可能下降。",
        ),
        risk="核心风险来自商品价格和板块轮动。",
        entry_window="沿 5 日线滚动跟踪",
        expected_holding_days=15,
        signal_breakdown=(
            ("技术面", 80, "趋势稳但爆发力一般。"),
            ("基本面", 86, "估值与盈利匹配度较好。"),
            ("资金面", 79, "资金承接稳定。"),
            ("情绪面", 82, "防守偏好升温时更占优。"),
        ),
    ),
    DemoStock(
        symbol="600036",
        name="招商银行",
        board="主板",
        industry="银行",
        latest_price=39.85,
        change_pct=0.96,
        turnover_ratio=1.15,
        pe_ttm=6.2,
        market_cap=10060.0,
        score=80,
        thesis="估值低、分红稳，适合做底仓压波动。",
        tags=("低估值", "红利", "防守"),
        thesis_points=(
            "低估值和高分红适合平衡组合波动。",
            "对系统回撤控制有帮助。",
            "更适合当作组合底仓，而非追求爆发。"),
        risk_notes=(
            "上涨斜率偏慢，强题材行情中容易跑输。",
            "宏观预期走弱时板块波动仍会放大。",
        ),
        risk="收益弹性较弱，更多承担稳定器角色。",
        entry_window="分批吸纳，不追高",
        expected_holding_days=20,
        signal_breakdown=(
            ("技术面", 75, "趋势平稳。"),
            ("基本面", 92, "估值和分红都具备优势。"),
            ("资金面", 71, "节奏偏慢。"),
            ("情绪面", 82, "红利风格回暖时更占优。"),
        ),
    ),
    DemoStock(
        symbol="600519",
        name="贵州茅台",
        board="主板",
        industry="白酒",
        latest_price=1688.00,
        change_pct=0.72,
        turnover_ratio=0.82,
        pe_ttm=23.1,
        market_cap=21210.0,
        score=79,
        thesis="高确定性龙头，适合做稳定性仓位和情绪锚。",
        tags=("消费龙头", "高确定性", "核心资产"),
        thesis_points=(
            "高确定性龙头在风格切换时具备配置价值。",
            "趋势修复后，机构抱团更容易回流。",
            "适合作为系统里的稳定器。"),
        risk_notes=(
            "向上弹性受制于大市值属性。",
            "消费板块若缺少催化，交易热度可能不足。",
        ),
        risk="偏机构风格，节奏慢于弹性板块。",
        entry_window="回调缩量时关注",
        expected_holding_days=18,
        signal_breakdown=(
            ("技术面", 76, "修复中，需耐心。"),
            ("基本面", 91, "高确定性资产。"),
            ("资金面", 70, "资金承接稳定但不激进。"),
            ("情绪面", 78, "消费情绪尚在修复。"),
        ),
    ),
    DemoStock(
        symbol="300750",
        name="宁德时代",
        board="创业板",
        industry="锂电池",
        latest_price=214.70,
        change_pct=1.26,
        turnover_ratio=2.05,
        pe_ttm=21.7,
        market_cap=9450.0,
        score=82,
        thesis="锂电龙头位置清晰，估值回到可跟踪区间。",
        tags=("新能源", "龙头", "估值回落"),
        thesis_points=(
            "龙头资产在板块回暖时更容易先修复。",
            "估值压力较前期缓和。",
            "适合做中等弹性仓位。"),
        risk_notes=(
            "产业链价格波动仍会影响情绪。",
            "高市值决定了单边爆发有限。",
        ),
        risk="更适合右侧跟踪，不适合激进打板逻辑。",
        entry_window="企稳后分批跟踪",
        expected_holding_days=10,
        signal_breakdown=(
            ("技术面", 81, "趋势企稳，待进一步确认。"),
            ("基本面", 87, "龙头地位仍然稳固。"),
            ("资金面", 78, "资金逐步回流。"),
            ("情绪面", 82, "板块情绪温和回暖。"),
        ),
    ),
    DemoStock(
        symbol="002230",
        name="科大讯飞",
        board="主板",
        industry="AI 应用",
        latest_price=47.65,
        change_pct=2.06,
        turnover_ratio=5.42,
        pe_ttm=65.4,
        market_cap=1105.0,
        score=84,
        thesis="AI 应用辨识度高，情绪修复时有交易弹性。",
        tags=("AI", "高弹性", "情绪票"),
        thesis_points=(
            "题材辨识度高，适合作为弹性观察标的。",
            "换手率提升说明短线承接尚可。",
            "若主题回流，容易成为资金选择。"),
        risk_notes=(
            "高估值意味着预期波动非常大。",
            "情绪退潮时回撤会明显放大。",
        ),
        risk="适合轻仓跟踪，重在节奏而不是死拿。",
        entry_window="情绪回流日跟踪",
        expected_holding_days=6,
        signal_breakdown=(
            ("技术面", 84, "短线节奏不错。"),
            ("基本面", 72, "估值要求较高。"),
            ("资金面", 88, "弹性资金活跃。"),
            ("情绪面", 92, "题材辨识度高。"),
        ),
    ),
    DemoStock(
        symbol="603986",
        name="兆易创新",
        board="主板",
        industry="芯片设计",
        latest_price=108.90,
        change_pct=2.65,
        turnover_ratio=4.12,
        pe_ttm=39.7,
        market_cap=725.0,
        score=86,
        thesis="芯片设计景气修复时弹性好，资金认可度较高。",
        tags=("半导体", "弹性", "资金偏好"),
        thesis_points=(
            "行业修复时通常具备高于板块的弹性。",
            "近期价格结构和量能共振较顺。",
            "适合做科技主线里的弹性补充。"),
        risk_notes=(
            "行业景气恢复若不及预期，回撤会较快。",
            "短期涨幅扩大后需要防止追高。"),
        risk="波动较大，更适合顺势分批介入。",
        entry_window="突破后缩量回踩",
        expected_holding_days=7,
        signal_breakdown=(
            ("技术面", 88, "价格结构较强。"),
            ("基本面", 78, "需继续跟踪景气修复。"),
            ("资金面", 88, "资金活跃。"),
            ("情绪面", 88, "科技主线加分明显。"),
        ),
    ),
    DemoStock(
        symbol="000333",
        name="美的集团",
        board="主板",
        industry="家电",
        latest_price=71.40,
        change_pct=0.58,
        turnover_ratio=1.36,
        pe_ttm=12.9,
        market_cap=4998.0,
        score=77,
        thesis="现金流扎实、估值合理，适合作为低波动仓位。",
        tags=("白马", "低波动", "现金流"),
        thesis_points=(
            "白马属性清晰，适合降低组合波动。",
            "估值不高，容错率相对更好。",
            "适合作为系统中性偏稳的配置。"),
        risk_notes=(
            "题材行情中关注度不高，爆发力弱。",
            "消费预期若偏弱，会影响估值修复。"),
        risk="更适合配置而不是追求高弹性。",
        entry_window="回撤时逐步布局",
        expected_holding_days=18,
        signal_breakdown=(
            ("技术面", 73, "走势平稳。"),
            ("基本面", 86, "盈利和现金流较扎实。"),
            ("资金面", 72, "资金风格偏稳。"),
            ("情绪面", 77, "板块偏中性。"),
        ),
    ),
)

def _bounded_score(value: int) -> int:
    return max(68, min(95, int(value)))


def _settings_timezone() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone)


def _trading_days(count: int) -> list[datetime]:
    current = datetime.now(_settings_timezone()).replace(hour=0, minute=0, second=0, microsecond=0)
    days: list[datetime] = []
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current -= timedelta(days=1)
    days.reverse()
    return days


def build_demo_snapshot_records(market: str = "cn") -> list[dict[str, object]]:
    updated_at = datetime.now(_settings_timezone())
    stocks = DEMO_STOCKS
    return [
        {
            "symbol": stock.symbol,
            "name": stock.name,
            "board": stock.board,
            "industry": stock.industry,
            "latest_price": stock.latest_price,
            "change_pct": stock.change_pct,
            "turnover_ratio": stock.turnover_ratio,
            "pe_ttm": stock.pe_ttm,
            "market_cap": stock.market_cap,
            "score": stock.score,
            "thesis": stock.thesis,
            "tags": list(stock.tags),
            "thesis_points": list(stock.thesis_points),
            "risk_notes": list(stock.risk_notes),
            "risk": stock.risk,
            "entry_window": stock.entry_window,
            "expected_holding_days": stock.expected_holding_days,
            "fundamental": _build_demo_fundamental(stock),
            "event_analysis": _build_demo_event_analysis(stock),
            "signal_breakdown": [
                {"dimension": dim, "score": score, "takeaway": takeaway}
                for dim, score, takeaway in stock.signal_breakdown
            ],
            "updated_at": updated_at,
        }
        for stock in stocks
    ]


def _build_demo_fundamental(stock: DemoStock) -> dict[str, object]:
    base_growth = round(max(-8.0, min(28.0, stock.change_pct * 3.2 + 6)), 1)
    profit_growth = round(base_growth + 3.5, 1)
    roe = round(max(8.0, min(28.0, 10 + stock.score * 0.12)), 1)
    gross_margin = round(max(18.0, min(68.0, 24 + stock.score * 0.28)), 1)
    debt_ratio = round(max(18.0, min(62.0, 55 - stock.score * 0.25)), 1)
    return {
        "report_period": "2025-12-31",
        "revenue_growth": base_growth,
        "net_profit_growth": profit_growth,
        "deduct_profit_growth": round(profit_growth - 1.8, 1),
        "roe": roe,
        "gross_margin": gross_margin,
        "debt_ratio": debt_ratio,
        "eps": round(max(0.2, stock.latest_price / max(stock.pe_ttm, 1)), 2),
        "operating_cashflow_per_share": round(max(0.3, roe / 10), 2),
    }


def _build_demo_event_analysis(stock: DemoStock) -> dict[str, object]:
    positive = stock.score >= 84
    tone = "positive" if positive else "neutral"
    summary = (
        f"最近事件层偏正面，{stock.industry}方向仍有业绩或调研催化，适合结合趋势继续跟踪。"
        if positive
        else f"最近有一些常规事件更新，但 {stock.industry} 方向暂时没有特别强的结构化催化。"
    )
    items = [
        {
            "date": "2026-04-04",
            "category": "业绩预告",
            "title": "业绩预告更新",
            "headline": "最近披露了偏正面的业绩预告" if positive else "最近披露了常规业绩更新",
            "detail": "景气和订单兑现继续提供支撑。" if positive else "事件层偏中性，更要结合趋势和量能判断。",
            "tone": tone,
            "source": "sample-event",
            "url": None,
        },
        {
            "date": "2026-04-03",
            "category": "公告",
            "title": "调研活动",
            "headline": "近期存在投资者调研或业务交流记录",
            "detail": "这类公告更偏情绪催化，需要继续看成交量能否接住。",
            "tone": "positive" if stock.turnover_ratio >= 3 else "neutral",
            "source": "sample-event",
            "url": None,
        },
    ]
    tags = ["业绩预告", "调研催化"] if positive else ["公告动态"]
    watch_points = [
        "重点看事件催化能否转成持续量能，而不是只停留在标题层。",
        "如果后续没有新的事件确认，强弱最终还是会回到价格和资金本身。",
    ]
    return {
        "tone": tone,
        "summary": summary,
        "tags": tags,
        "items": items,
        "watch_points": watch_points,
    }


def build_history_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    trading_days = _trading_days(60)
    history_rows: list[dict[str, object]] = []

    for record in records:
        symbol = str(record["symbol"])
        latest_price = float(record["latest_price"])
        change_pct = float(record["change_pct"])
        base_volume = max(1.5, float(record["turnover_ratio"])) * 10_000_000
        rng = random.Random(symbol)
        price_cursor = latest_price * 0.82
        closes: list[float] = []

        for index, trade_day in enumerate(trading_days, start=1):
            remain_ratio = index / len(trading_days)
            anchor = latest_price * (0.82 + remain_ratio * 0.18)
            drift = (anchor - price_cursor) * 0.18 + rng.uniform(-1.6, 1.8)
            open_price = max(1.0, price_cursor + rng.uniform(-1.6, 1.4))
            close_price = max(1.0, open_price + drift + change_pct * 0.05)
            high_price = max(open_price, close_price) + abs(rng.uniform(0.4, 2.2))
            low_price = min(open_price, close_price) - abs(rng.uniform(0.3, 1.8))
            volume = base_volume * (0.82 + rng.random() * 0.42)
            closes.append(close_price)
            ma5 = sum(closes[-5:]) / min(len(closes), 5)
            ma20 = sum(closes[-20:]) / min(len(closes), 20)

            history_rows.append(
                {
                    "symbol": symbol,
                    "date": trade_day.date().isoformat(),
                    "open": round(open_price, 2),
                    "close": round(close_price, 2),
                    "low": round(max(0.01, low_price), 2),
                    "high": round(high_price, 2),
                    "volume": round(volume, 2),
                    "ma5": round(ma5, 2),
                    "ma20": round(ma20, 2),
                }
            )
            price_cursor = close_price

        if history_rows:
            history_rows[-1]["close"] = round(latest_price, 2)

    return history_rows


def build_market_pulse_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    trading_days = _trading_days(20)
    avg_score = sum(int(record["score"]) for record in records) / len(records)
    total_turnover = sum(float(record["turnover_ratio"]) for record in records) * 100
    rows: list[dict[str, object]] = []

    for index, trade_day in enumerate(trading_days):
        oscillation = math.sin(index / 3.1) * 5.8
        score = max(45, min(96, round(avg_score - 5 + index * 0.3 + oscillation)))
        turnover = round(total_turnover * (0.88 + index * 0.01) + oscillation * 12, 2)
        rows.append(
            {
                "date": trade_day.date().isoformat(),
                "score": score,
                "turnover": max(1000.0, turnover),
            }
        )

    return rows


def build_industry_heat_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    buckets: dict[str, list[dict[str, object]]] = {}
    for record in records:
        buckets.setdefault(str(record["industry"]), []).append(record)

    industry_rows: list[dict[str, object]] = []
    for industry, items in buckets.items():
        avg_score = round(sum(int(item["score"]) for item in items) / len(items))
        avg_change = sum(float(item["change_pct"]) for item in items) / len(items)
        if avg_change >= 2:
            momentum = "主线热度强，适合优先复核。"
        elif avg_change >= 1:
            momentum = "趋势稳步抬升，适合放进关注池。"
        else:
            momentum = "节奏平稳，偏配置型方向。"

        industry_rows.append(
            {
                "industry": industry,
                "score": avg_score,
                "momentum": momentum,
            }
        )

    industry_rows.sort(key=lambda row: row["score"], reverse=True)
    return industry_rows[:6]


def build_recommendation_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    sorted_records = sorted(
        records,
        key=lambda item: (int(item["score"]), float(item["change_pct"])),
        reverse=True,
    )

    recommendations: list[dict[str, object]] = []
    for record in sorted_records[:8]:
        recommendations.append(
            {
                "symbol": record["symbol"],
                "name": record["name"],
                "score": int(record["score"]),
                "entry_window": record["entry_window"],
                "expected_holding_days": int(record["expected_holding_days"]),
                "thesis": record["thesis"],
                "risk": record["risk"],
                "tags": list(record["tags"]),
            }
        )

    return recommendations


def dumps_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)
