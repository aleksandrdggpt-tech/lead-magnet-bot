"""
Settings helpers for Lead Magnet Bot.

Here we store and retrieve configurable texts/links from the database
via the generic BotSettings key/value model.
"""

from __future__ import annotations

import logging
from typing import TypedDict, Optional

from sqlalchemy import select

from database import BotSettings
from database.database import get_session

logger = logging.getLogger(__name__)


class WelcomeSettings(TypedDict):
    text: str
    button_text: str
    link: Optional[str]


WELCOME_TEXT_KEY = "welcome_text"
WELCOME_BUTTON_TEXT_KEY = "welcome_button_text"
WELCOME_LINK_KEY = "welcome_link"


DEFAULT_WELCOME_TEXT = (
    "👋 Добро пожаловать!\n\n"
    "Этот бот выдает полезные материалы по продаже и систематизации работы отдела продаж.\n\n"
    "Нажмите кнопку ниже, чтобы получить чек‑лист отдела продаж."
)

DEFAULT_WELCOME_BUTTON_TEXT = "📋 Получить чек-лист отдела продаж"


async def get_welcome_settings() -> WelcomeSettings:
    """
    Получает настройки приветственного сообщения из БД.
    Если настроек нет, возвращает значения по умолчанию.
    """
    text = DEFAULT_WELCOME_TEXT
    button_text = DEFAULT_WELCOME_BUTTON_TEXT
    link: Optional[str] = None

    try:
        async with get_session() as session:
            result = await session.execute(
                select(BotSettings).where(
                    BotSettings.key.in_(
                        [WELCOME_TEXT_KEY, WELCOME_BUTTON_TEXT_KEY, WELCOME_LINK_KEY]
                    )
                )
            )
            rows = result.scalars().all()
            for row in rows:
                if row.key == WELCOME_TEXT_KEY and row.value:
                    text = row.value
                elif row.key == WELCOME_BUTTON_TEXT_KEY and row.value:
                    button_text = row.value
                elif row.key == WELCOME_LINK_KEY and row.value:
                    link = row.value
    except Exception as e:
        logger.error(f"Error loading welcome settings: {e}")
        import traceback
        logger.error(traceback.format_exc())

    return WelcomeSettings(text=text, button_text=button_text, link=link)


async def set_welcome_settings(
    text: str,
    button_text: str,
    link: str,
    updated_by: Optional[int] = None,
) -> None:
    """
    Сохраняет настройки приветственного сообщения в БД.
    """
    try:
        async with get_session() as session:
            for key, value in (
                (WELCOME_TEXT_KEY, text),
                (WELCOME_BUTTON_TEXT_KEY, button_text),
                (WELCOME_LINK_KEY, link),
            ):
                result = await session.execute(
                    select(BotSettings).where(BotSettings.key == key)
                )
                setting = result.scalar_one_or_none()
                if setting:
                    setting.value = value
                    setting.updated_by = updated_by
                else:
                    setting = BotSettings(
                        key=key,
                        value=value,
                        updated_by=updated_by,
                    )
                    session.add(setting)

            await session.commit()
            logger.info("Welcome settings updated")
    except Exception as e:
        logger.error(f"Error saving welcome settings: {e}")
        import traceback
        logger.error(traceback.format_exc())

