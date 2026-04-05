from __future__ import annotations

from typing import Literal

MarketScope = Literal["cn", "hk", "us"]

DEFAULT_MARKET_SCOPE: MarketScope = "cn"
SUPPORTED_MARKETS: tuple[MarketScope, ...] = ("cn", "hk", "us")

MARKET_LABELS: dict[MarketScope, str] = {
    "cn": "A股",
    "hk": "港股",
    "us": "美股",
}

MARKET_LONG_LABELS: dict[MarketScope, str] = {
    "cn": "A股（沪深）",
    "hk": "港股",
    "us": "美股",
}


def normalize_market_scope(value: str | None) -> MarketScope:
    normalized = str(value or DEFAULT_MARKET_SCOPE).strip().lower()
    if normalized in SUPPORTED_MARKETS:
        return normalized  # type: ignore[return-value]
    return DEFAULT_MARKET_SCOPE


def market_label(value: str | None) -> str:
    return MARKET_LABELS[normalize_market_scope(value)]


def market_long_label(value: str | None) -> str:
    return MARKET_LONG_LABELS[normalize_market_scope(value)]


def infer_market_from_symbol(symbol: str | None) -> MarketScope:
    text = str(symbol or "").strip().upper()
    if text.endswith(".HK"):
        return "hk"
    if text.isdigit() and len(text) == 6:
        return "cn"
    return "us"


def normalize_symbol(symbol: str | None) -> str:
    text = str(symbol or "").strip().upper()
    if text.endswith(".HK"):
        prefix = text[:-3]
        if prefix.isdigit():
            return f"{prefix.zfill(4)}.HK"
        return text
    if text.isdigit():
        return text.zfill(6)
    return text


def scoped_key(market: str | None, key: str) -> str:
    scope = normalize_market_scope(market)
    return f"{scope}:{key}"


def unscoped_key(scoped_value: str) -> str:
    prefix, marker, suffix = str(scoped_value).partition(":")
    if marker and prefix in SUPPORTED_MARKETS:
        return suffix
    return str(scoped_value)
