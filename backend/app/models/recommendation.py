from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RecommendationJournal(Base):
    __tablename__ = "recommendation_journal"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_key: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64))
    score: Mapped[int] = mapped_column()
    entry_window: Mapped[str] = mapped_column(String(128))
    expected_holding_days: Mapped[int] = mapped_column()
    thesis: Mapped[str] = mapped_column(Text)
    risk: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64), default="sample")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    price_at_publish: Mapped[float] = mapped_column(Float, default=0.0)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
