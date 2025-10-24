"""
Portfolio models
================

Represents a user's portfolio and its positions in assets.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Portfolio(TimestampMixin, Base):
    """A collection of positions owned by a user."""

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), default="Default", nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="portfolios")
    positions: Mapped[List["PortfolioPosition"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Portfolio(id={self.id}, user_id={self.user_id}, name={self.name})"


class PortfolioPosition(TimestampMixin, Base):
    """A position in a specific asset within a portfolio."""

    __tablename__ = "portfolio_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), index=True, nullable=False)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="RESTRICT"), index=True, nullable=False)

    quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationships
    portfolio: Mapped[Portfolio] = relationship(back_populates="positions")
    asset: Mapped["Asset"] = relationship(back_populates="positions")

    def __repr__(self) -> str:
        return f"Position(id={self.id}, portfolio_id={self.portfolio_id}, asset_id={self.asset_id})"



