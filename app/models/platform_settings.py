from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

class PlatformSettings(BaseModel):
    __tablename__ = "platform_settings"

    platform_name: Mapped[str] = mapped_column(String(255), default="Laundry SaaS")
    logo_url: Mapped[str] = mapped_column(String(500), nullable=True)
    smtp_host: Mapped[str] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[str] = mapped_column(String(20), nullable=True)
    smtp_username: Mapped[str] = mapped_column(String(255), nullable=True)
    smtp_password: Mapped[str] = mapped_column(String(255), nullable=True)
    sms_api_key: Mapped[str] = mapped_column(String(255), nullable=True)
    whatsapp_api_key: Mapped[str] = mapped_column(String(255), nullable=True)
    google_maps_api_key: Mapped[str] = mapped_column(String(255), nullable=True)
    payment_gateway_client_id: Mapped[str] = mapped_column(String(255), nullable=True)
    payment_gateway_secret: Mapped[str] = mapped_column(String(255), nullable=True)
