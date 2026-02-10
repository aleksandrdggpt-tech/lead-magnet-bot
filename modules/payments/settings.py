"""
Settings helpers for Lead Magnet Bot.

Here we store and retrieve configurable texts/links from the database
via the generic BotSettings key/value model.
"""

from __future__ import annotations

import logging
from typing import TypedDict, Optional, List

from sqlalchemy import select

from database import BotSettings
from database.database import get_session
from config import Config

logger = logging.getLogger(__name__)


class WelcomeSettings(TypedDict):
    text: str
    button_text: str
    link: Optional[str]


class FollowupLeadButton(TypedDict):
    text: str
    url: str


class FollowupLeadSettings(TypedDict):
    text: str
    buttons: List[FollowupLeadButton]


WELCOME_TEXT_KEY = "welcome_text"
WELCOME_BUTTON_TEXT_KEY = "welcome_button_text"
WELCOME_LINK_KEY = "welcome_link"

FOLLOWUP_LOST_TEXT_KEY = "followup_lost_text"
FOLLOWUP_LEAD_TEXT_KEY = "followup_lead_text"
FOLLOWUP_LEAD_BTN1_TEXT_KEY = "followup_lead_btn1_text"
FOLLOWUP_LEAD_BTN1_URL_KEY = "followup_lead_btn1_url"
FOLLOWUP_LEAD_BTN2_TEXT_KEY = "followup_lead_btn2_text"
FOLLOWUP_LEAD_BTN2_URL_KEY = "followup_lead_btn2_url"
FOLLOWUP_LEAD_BTN3_TEXT_KEY = "followup_lead_btn3_text"
FOLLOWUP_LEAD_BTN3_URL_KEY = "followup_lead_btn3_url"


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


# ==================== FOLLOWUP LOST (НЕ ПОДПИСАН) ====================

DEFAULT_FOLLOWUP_LOST_TEXT = (
    "👋 Привет! Вчера ты начинал получать чек-лист отдела продаж, но не завершил шаг "
    "с подпиской на канал.\n\n"
    "Подпишись на канал, чтобы открыть доступ к материалу, и нажми кнопку ниже, "
    "чтобы получить чек-лист."
)


async def get_followup_lost_text() -> str:
    """Возвращает текст follow-up сообщения для неподписанных пользователей."""
    text = DEFAULT_FOLLOWUP_LOST_TEXT
    try:
        async with get_session() as session:
            result = await session.execute(
                select(BotSettings).where(BotSettings.key == FOLLOWUP_LOST_TEXT_KEY)
            )
            setting = result.scalar_one_or_none()
            if setting and setting.value:
                text = setting.value
    except Exception as e:
        logger.error(f"Error loading followup_lost_text: {e}")
        import traceback
        logger.error(traceback.format_exc())
    return text


async def set_followup_lost_text(text: str, updated_by: Optional[int] = None) -> None:
    """Сохраняет текст follow-up сообщения для неподписанных пользователей."""
    try:
        async with get_session() as session:
            result = await session.execute(
                select(BotSettings).where(BotSettings.key == FOLLOWUP_LOST_TEXT_KEY)
            )
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = text
                setting.updated_by = updated_by
            else:
                setting = BotSettings(
                    key=FOLLOWUP_LOST_TEXT_KEY,
                    value=text,
                    updated_by=updated_by,
                )
                session.add(setting)
            await session.commit()
            logger.info("Followup lost text updated")
    except Exception as e:
        logger.error(f"Error saving followup_lost_text: {e}")
        import traceback
        logger.error(traceback.format_exc())


# ==================== FOLLOWUP LEAD (ПОДПИСАН) ====================

DEFAULT_FOLLOWUP_LEAD_TEXT = (
    "🔥 **Как использовать чек-лист, чтобы выжать максимум из отдела продаж**\n\n"
    "За последний день ты уже получил чек-лист. Следующий логичный шаг — "
    "внедрить его с нашей помощью и получить результат быстрее:\n\n"
    "1️⃣ Индивидуальный разбор и план внедрения\n"
    "2️⃣ Сопровождение по шагам\n"
    "3️⃣ Ответы на вопросы и разбор кейсов\n\n"
    "Выбери удобный формат работы ниже 👇"
)


async def get_followup_lead_settings() -> FollowupLeadSettings:
    """
    Возвращает текст и кнопки follow-up сообщения для подписанных пользователей.
    Если в БД нет настроек, берёт дефолтный текст и URL-ы из переменных окружения.
    """
    text = DEFAULT_FOLLOWUP_LEAD_TEXT
    # Сначала заполняем кнопки по умолчанию из Config.PAYMENT_URL_*
    buttons: List[FollowupLeadButton] = []
    if Config.PAYMENT_URL_1:
        buttons.append(FollowupLeadButton(text="💳 Тариф 1", url=Config.PAYMENT_URL_1))
    if Config.PAYMENT_URL_2:
        buttons.append(FollowupLeadButton(text="💳 Тариф 2", url=Config.PAYMENT_URL_2))
    if Config.PAYMENT_URL_3:
        buttons.append(FollowupLeadButton(text="💳 Тариф 3", url=Config.PAYMENT_URL_3))

    try:
        async with get_session() as session:
            result = await session.execute(
                select(BotSettings).where(
                    BotSettings.key.in_(
                        [
                            FOLLOWUP_LEAD_TEXT_KEY,
                            FOLLOWUP_LEAD_BTN1_TEXT_KEY,
                            FOLLOWUP_LEAD_BTN1_URL_KEY,
                            FOLLOWUP_LEAD_BTN2_TEXT_KEY,
                            FOLLOWUP_LEAD_BTN2_URL_KEY,
                            FOLLOWUP_LEAD_BTN3_TEXT_KEY,
                            FOLLOWUP_LEAD_BTN3_URL_KEY,
                        ]
                    )
                )
            )
            rows = result.scalars().all()
            raw: dict[str, str] = {row.key: row.value for row in rows}

            if raw.get(FOLLOWUP_LEAD_TEXT_KEY):
                text = raw[FOLLOWUP_LEAD_TEXT_KEY]

            # Собираем кнопки только из БД, если там есть хоть одна ссылка
            btns: List[FollowupLeadButton] = []
            for idx in ("1", "2", "3"):
                t_key = f"followup_lead_btn{idx}_text"
                u_key = f"followup_lead_btn{idx}_url"
                t_val = raw.get(t_key)
                u_val = raw.get(u_key)
                if u_val:
                    btns.append(
                        FollowupLeadButton(
                            text=t_val or f"💳 Тариф {idx}",
                            url=u_val,
                        )
                    )

            if btns:
                buttons = btns
    except Exception as e:
        logger.error(f"Error loading followup_lead settings: {e}")
        import traceback
        logger.error(traceback.format_exc())

    return FollowupLeadSettings(text=text, buttons=buttons)


async def set_followup_lead_settings(
    text: str,
    btn1_text: str,
    btn1_url: str,
    btn2_text: str,
    btn2_url: str,
    btn3_text: str,
    btn3_url: str,
    updated_by: Optional[int] = None,
) -> None:
    """Сохраняет текст и кнопки follow-up сообщения для подписанных пользователей."""
    try:
        async with get_session() as session:
            kv_pairs = [
                (FOLLOWUP_LEAD_TEXT_KEY, text),
                (FOLLOWUP_LEAD_BTN1_TEXT_KEY, btn1_text),
                (FOLLOWUP_LEAD_BTN1_URL_KEY, btn1_url),
                (FOLLOWUP_LEAD_BTN2_TEXT_KEY, btn2_text),
                (FOLLOWUP_LEAD_BTN2_URL_KEY, btn2_url),
                (FOLLOWUP_LEAD_BTN3_TEXT_KEY, btn3_text),
                (FOLLOWUP_LEAD_BTN3_URL_KEY, btn3_url),
            ]
            for key, value in kv_pairs:
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
            logger.info("Followup lead settings updated")
    except Exception as e:
        logger.error(f"Error saving followup_lead settings: {e}")
        import traceback
        logger.error(traceback.format_exc())

