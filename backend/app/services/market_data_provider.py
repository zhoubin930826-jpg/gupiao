from __future__ import annotations

from dataclasses import dataclass

from app.core.market_scope import DEFAULT_MARKET_SCOPE, normalize_market_scope
from app.services.akshare_collector import AkshareCollector, CollectedMarketData
from app.services.signal_engine import StrategyWeights


@dataclass(slots=True)
class ProviderSyncResult:
    provider_key: str
    source_label: str
    success: bool
    used_fallback: bool
    dataset: CollectedMarketData | None
    message: str


class MarketDataProvider:
    provider_key: str
    source_label: str

    def sync(self, *, strategy: StrategyWeights) -> ProviderSyncResult:
        raise NotImplementedError


class AkshareMarketDataProvider(MarketDataProvider):
    provider_key = "akshare"
    source_label = "akshare-live"

    def __init__(self, market: str = DEFAULT_MARKET_SCOPE) -> None:
        self.market = normalize_market_scope(market)
        self.collector = AkshareCollector()

    def sync(self, *, strategy: StrategyWeights) -> ProviderSyncResult:
        dataset, message = self.collector.collect_market_dataset(strategy=strategy, market=self.market)
        return ProviderSyncResult(
            provider_key=self.provider_key,
            source_label=self.source_label,
            success=dataset is not None,
            used_fallback=False,
            dataset=dataset,
            message=message,
        )


class SampleMarketDataProvider(MarketDataProvider):
    provider_key = "sample"
    source_label = "sample"

    def __init__(self, market: str = DEFAULT_MARKET_SCOPE) -> None:
        self.market = normalize_market_scope(market)

    def sync(self, *, strategy: StrategyWeights) -> ProviderSyncResult:
        return ProviderSyncResult(
            provider_key=self.provider_key,
            source_label=self.source_label,
            success=True,
            used_fallback=True,
            dataset=None,
            message="已回退到示例数据。",
        )


def build_provider(provider_key: str, market: str = DEFAULT_MARKET_SCOPE) -> MarketDataProvider:
    normalized = provider_key.strip().lower()
    if normalized == "akshare":
        return AkshareMarketDataProvider(market=market)
    if normalized == "sample":
        return SampleMarketDataProvider(market=market)
    raise KeyError(provider_key)
