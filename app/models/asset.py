"""
Asset model
===========

Represents tradable instruments (stocks, crypto, forex).
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Integer, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AssetTypeEnum(str, Enum):  # type: ignore[misc]
    STOCK = "stock"
    CRYPTO = "crypto"
    FOREX = "forex"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Asset(TimestampMixin, Base):
    """Tradable asset with symbol and metadata."""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    type: Mapped[str] = mapped_column(String(16), default="stock", nullable=False)
    exchange: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # Relationships
    signals: Mapped[List["Signal"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    positions: Mapped[List["PortfolioPosition"]] = relationship(back_populates="asset")

    def __repr__(self) -> str:
        return f"Asset(id={self.id}, symbol={self.symbol}, type={self.type})"



