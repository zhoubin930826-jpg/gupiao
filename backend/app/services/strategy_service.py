from sqlalchemy.orm import Session

from app.models.strategy import StrategyProfile
from app.schemas.market import StrategyConfig


class StrategyService:
    @staticmethod
    def get_default_profile(db: Session) -> StrategyProfile:
        profile = db.query(StrategyProfile).first()
        if profile is None:
            raise RuntimeError("Strategy profile was not initialized.")
        return profile

    @classmethod
    def read_config(cls, db: Session) -> StrategyProfile:
        return cls.get_default_profile(db)

    @classmethod
    def update_config(cls, db: Session, payload: StrategyConfig) -> StrategyProfile:
        profile = cls.get_default_profile(db)
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile
