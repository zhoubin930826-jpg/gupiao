from __future__ import annotations

from typing import Literal

MarketScope = Literal["cn"]

DEFAULT_MARKET_SCOPE: MarketScope = "cn"
SUPPORTED_MARKETS: tuple[MarketScope, ...] = ("cn",)

MARKET_LABELS: dict[MarketScope, str] = {
    "cn": "A股",
}

MARKET_LONG_LABELS: dict[MarketScope, str] = {
    "cn": "A股（沪深）",
}


def normalize_market_scope(value: str | None) -> MarketScope:
    return DEFAULT_MARKET_SCOPE


def market_label(value: str | None) -> str:
    return MARKET_LABELS[normalize_market_scope(value)]


def market_long_label(value: str | None) -> str:
    return MARKET_LONG_LABELS[normalize_market_scope(value)]


def is_a_share_symbol(symbol: str | None) -> bool:
    text = str(symbol or "").strip().upper()
    return text.isdigit() and len(text) == 6


def normalize_symbol(symbol: str | None) -> str:
    text = str(symbol or "").strip().upper()
    if text.isdigit():
        return text.zfill(6)
    return text


def scoped_key(market: str | None, key: str) -> str:
    scope = normalize_market_scope(market)
    return f"{scope}:{key}"


def unscoped_key(scoped_value: str) -> str:
    prefix, marker, suffix = str(scoped_value).partition(":")
    if marker and prefix.isalpha() and len(prefix) <= 3:
        return suffix
    return str(scoped_value)
