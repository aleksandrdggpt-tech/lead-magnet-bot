"""
SQLAlchemy models for Lead Magnet Bot.
Channel button tracking models.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    Integer, BigInteger, String, ForeignKey, DateTime
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Use Base from base_models to ensure all models are in the same metadata
from .base_models import Base

# Type checking only - avoid circular imports
if TYPE_CHECKING:
    from .base_models import User


class ChannelButton(Base):
    """Information about created channel buttons."""
    __tablename__ = "channel_buttons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    post_title: Mapped[str] = mapped_column(String(500), nullable=False)  # Название поста
    button_text: Mapped[str] = mapped_column(String(255), nullable=False)  # Название кнопки
    lead_magnet_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "bot" or "external"
    link: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Telegram ID админа

    # Relationships
    clicks: Mapped[list["ChannelButtonClick"]] = relationship(
        "ChannelButtonClick",
        back_populates="button",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ChannelButton(message_id={self.message_id}, post='{self.post_title}', button='{self.button_text}', type={self.lead_magnet_type})>"


class ChannelButtonClick(Base):
    """Tracking clicks on channel button."""
    __tablename__ = "channel_button_clicks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    button_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("channel_buttons.id"), nullable=True, index=True)
    clicked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Legacy fields (для обратной совместимости)
    post_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    button: Mapped[Optional["ChannelButton"]] = relationship("ChannelButton", back_populates="clicks")

    def __repr__(self) -> str:
        return f"<ChannelButtonClick(telegram_id={self.telegram_id}, button_id={self.button_id}, clicked_at={self.clicked_at})>"
