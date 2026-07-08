from sqlalchemy import String, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel
from uuid import UUID

class CompanyFeature(BaseModel):
    __tablename__ = "company_features"

    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    feature_key: Mapped[str] = mapped_column(String(100)) # e.g. REPORTS, SMS, WHATSAPP, API_ACCESS
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
