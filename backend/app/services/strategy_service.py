from sqlalchemy.orm import Session

from app.core.market_scope import DEFAULT_MARKET_SCOPE, normalize_market_scope
from app.models.strategy import StrategyProfile
from app.schemas.market import StrategyConfig


class StrategyService:
    @staticmethod
    def get_default_profile(db: Session, market: str = DEFAULT_MARKET_SCOPE) -> StrategyProfile:
        profile = db.query(StrategyProfile).filter_by(market=normalize_market_scope(market)).first()
        if profile is None:
            raise RuntimeError("Strategy profile was not initialized.")
        return profile

    @classmethod
    def read_config(cls, db: Session, market: str = DEFAULT_MARKET_SCOPE) -> StrategyProfile:
        return cls.get_default_profile(db, market)

    @classmethod
    def update_config(
        cls,
        db: Session,
        payload: StrategyConfig,
        market: str = DEFAULT_MARKET_SCOPE,
    ) -> StrategyProfile:
        profile = cls.get_default_profile(db, market)
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile
