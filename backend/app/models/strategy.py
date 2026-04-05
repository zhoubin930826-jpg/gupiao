from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StrategyProfile(Base):
    __tablename__ = "strategy_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market: Mapped[str] = mapped_column(String(8), default="cn", index=True)
    technical_weight: Mapped[int] = mapped_column(Integer, default=35)
    fundamental_weight: Mapped[int] = mapped_column(Integer, default=25)
    money_flow_weight: Mapped[int] = mapped_column(Integer, default=25)
    sentiment_weight: Mapped[int] = mapped_column(Integer, default=15)
    rebalance_cycle: Mapped[str] = mapped_column(String(24), default="weekly")
    min_turnover: Mapped[float] = mapped_column(Float, default=2.5)
    min_listing_days: Mapped[int] = mapped_column(Integer, default=180)
    exclude_st: Mapped[bool] = mapped_column(Boolean, default=True)
    exclude_new_shares: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
