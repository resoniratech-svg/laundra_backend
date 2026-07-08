from sqlalchemy import ForeignKey, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel
from datetime import datetime
from typing import Optional

class Attendance(BaseModel):
    __tablename__ = "attendance"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    clock_in: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    clock_out: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    gps_lat_in: Mapped[Optional[float]] = mapped_column(Float)
    gps_lng_in: Mapped[Optional[float]] = mapped_column(Float)
    gps_lat_out: Mapped[Optional[float]] = mapped_column(Float)
    gps_lng_out: Mapped[Optional[float]] = mapped_column(Float)
