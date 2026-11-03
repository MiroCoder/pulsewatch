from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey
from .database import Base
from sqlalchemy import DateTime, func
from datetime import datetime
from sqlalchemy import Boolean, true

class Monitor(Base):
    __tablename__ = "monitors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable = False)
    url: Mapped[str] = mapped_column(String(2048), nullable = False)
    interval_seconds: Mapped[int] = mapped_column(nullable = False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable = False, server_default=true())
    checks : Mapped[list["CheckResult"]] = relationship(back_populates="monitor", cascade= "all, delete-orphan")

class CheckResult(Base):
    __tablename__ = "check_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    monitor_id : Mapped[int] = mapped_column(ForeignKey("monitors.id"))
    status_code: Mapped[int | None] = mapped_column(nullable = True)
    latency_ms: Mapped[float | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable = True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    monitor: Mapped["Monitor"] = relationship(back_populates="checks")