"""
Signal model
============

Stores generated technical analysis signals for assets.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Signal(TimestampMixin, Base):
    """
    Technical signal for an asset at a specific time.

    Fields include popular indicators to allow quick retrieval
    without recomputation for the same snapshot.
    """

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), default="1d", nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    rsi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema_fast: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ema_slow: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bb_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bb_middle: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bb_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    decision: Mapped[str] = mapped_column(String(8), default="HOLD", nullable=False)  # BUY/SELL/HOLD

    # Relationship
    asset: Mapped["Asset"] = relationship(back_populates="signals")

    def __repr__(self) -> str:
        return f"Signal(id={self.id}, asset_id={self.asset_id}, decision={self.decision})"



