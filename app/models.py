from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, utcnow


class FishingSpot(Base):
    __tablename__ = "fishing_spots"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    forecast_caches: Mapped[list["ForecastCache"]] = relationship(
        back_populates="spot",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ForecastCache(Base):
    __tablename__ = "forecast_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    spot_id: Mapped[int] = mapped_column(ForeignKey("fishing_spots.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    forecast_datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    spot: Mapped[FishingSpot] = relationship(back_populates="forecast_caches")
