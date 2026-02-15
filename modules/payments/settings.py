"""
Settings helpers for Lead Magnet Bot.

Here we store and retrieve configurable texts/links from the database
via the generic BotSettings key/value model.
"""

from __future__ import annotations

import logging
from typing import TypedDict, Optional, List, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import BotSettings
from database.database import get_session
from config import Config

logger = logging.getLogger(__name__)


# ==================== KEY CONSTANTS (single source of truth) ====================

WELCOME_TEXT_KEY = "welcome_text"
WELCOME_BUTTON_TEXT_KEY = "welcome_btn_text"
WELCOME_LINK_KEY = "welcome_link"

# Legacy key: в БД мог остаться welcome_button_text
WELCOME_BUTTON_TEXT_LEGACY_KEY = "welcome_button_text"

FOLLOWUP_ENABLED_KEY = "followup_enabled"

FUP_LOST_TEXT_KEY = "fup_lost_text"

FUP1_LEAD_TEXT_KEY = "fup1_lead_text"
FUP2_LEAD_TEXT_KEY = "fup2_lead_text"
FUP3_LEAD_TEXT_KEY = "fup3_lead_text"

DIAG_SELECTION_TEXT_KEY = "diag_selection_text"

DIAG1_BTN_TEXT_KEY = "diag1_price_btn"
DIAG1_URL_KEY = "diag1_url"
DIAG2_BTN_TEXT_KEY = "diag2_price_btn"
DIAG2_URL_KEY = "diag2_url"
DIAG3_BTN_TEXT_KEY = "diag3_price_btn"
DIAG3_URL_KEY = "diag3_url"

# Legacy keys (для обратной совместимости с существующими админ-диалогами)
FOLLOWUP_LOST_TEXT_LEGACY_KEY = "followup_lost_text"
FOLLOWUP_LEAD_TEXT_KEY = "followup_lead_text"
FOLLOWUP_LEAD_BTN1_TEXT_KEY = "followup_lead_btn1_text"
FOLLOWUP_LEAD_BTN1_URL_KEY = "followup_lead_btn1_url"
FOLLOWUP_LEAD_BTN2_TEXT_KEY = "followup_lead_btn2_text"
FOLLOWUP_LEAD_BTN2_URL_KEY = "followup_lead_btn2_url"
FOLLOWUP_LEAD_BTN3_TEXT_KEY = "followup_lead_btn3_text"
FOLLOWUP_LEAD_BTN3_URL_KEY = "followup_lead_btn3_url"


# ==================== GENERIC HELPERS ====================

async def get_setting(
    session: AsyncSession,
    key: str,
    default: str | None = None,
) -> str | None:
    """Возвращает значение настройки по ключу из текущей сессии."""
    result = await session.execute(
        select(BotSettings).where(BotSettings.key == key)
    )
    row = result.scalar_one_or_none()
    if row and row.value is not None:
        return row.value
    return default


async def set_setting(
    session: AsyncSession,
    key: str,
    value: str,
    updated_by: int | None = None,
) -> None:
    """Записывает значение настройки в БД (в рамках текущей сессии)."""
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


# ==================== TYPED DICTS ====================

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


# Минимальные fallback-значения (без длинных русских текстов; полные — в БД/миграции)
DEFAULT_WELCOME_TEXT = ""
DEFAULT_WELCOME_BUTTON_TEXT = ""


async def _get_welcome_settings(session: AsyncSession) -> dict[str, Any]:
    """
    Получает настройки приветствия из БД (в рамках переданной сессии).
    Поддерживает ключи welcome_btn_text и welcome_button_text (legacy).
    """
    keys = [
        WELCOME_TEXT_KEY,
        WELCOME_BUTTON_TEXT_KEY,
        WELCOME_LINK_KEY,
        WELCOME_BUTTON_TEXT_LEGACY_KEY,
    ]
    result = await session.execute(
        select(BotSettings).where(BotSettings.key.in_(keys))
    )
    rows = result.scalars().all()
    raw: dict[str, str] = {row.key: row.value for row in rows if row.value}

    text = raw.get(WELCOME_TEXT_KEY) or DEFAULT_WELCOME_TEXT
    button_text = (
        raw.get(WELCOME_BUTTON_TEXT_KEY)
        or raw.get(WELCOME_BUTTON_TEXT_LEGACY_KEY)
        or DEFAULT_WELCOME_BUTTON_TEXT
    )
    link = raw.get(WELCOME_LINK_KEY)

    return {"text": text, "button_text": button_text, "link": link}


async def get_welcome_settings(
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """
    Получает настройки приветственного сообщения из БД.
    Если session не передан, открывает свою сессию (для вызовов из bot.py и т.д.).
    """
    if session is not None:
        return await _get_welcome_settings(session)
    try:
        async with get_session() as s:
            return await _get_welcome_settings(s)
    except Exception as e:
        logger.error(f"Error loading welcome settings: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "text": DEFAULT_WELCOME_TEXT,
            "button_text": DEFAULT_WELCOME_BUTTON_TEXT,
            "link": None,
        }


async def set_welcome_settings(
    text: str,
    button_text: str,
    link: str,
    updated_by: Optional[int] = None,
) -> None:
    """Сохраняет настройки приветственного сообщения в БД."""
    try:
        async with get_session() as session:
            for key, value in (
                (WELCOME_TEXT_KEY, text),
                (WELCOME_BUTTON_TEXT_KEY, button_text),
                (WELCOME_LINK_KEY, link),
                (WELCOME_BUTTON_TEXT_LEGACY_KEY, button_text),
            ):
                await set_setting(session, key, value, updated_by)
            await session.commit()
            logger.info("Welcome settings updated")
    except Exception as e:
        logger.error(f"Error saving welcome settings: {e}")
        import traceback
        logger.error(traceback.format_exc())


# ==================== FOLLOWUP ENABLED ====================

async def get_followup_enabled(session: AsyncSession | None = None) -> bool:
    """Возвращает, включена ли отправка follow-up сообщений."""
    if session is not None:
        val = await get_setting(session, FOLLOWUP_ENABLED_KEY, "1")
        return (val or "").strip().lower() in ("1", "true", "yes", "вкл")
    try:
        async with get_session() as s:
            return await get_followup_enabled(s)
    except Exception as e:
        logger.error(f"Error loading followup_enabled: {e}")
        return True


async def set_followup_enabled(
    session: AsyncSession,
    enabled: bool,
    updated_by: int | None = None,
) -> None:
    """Включает или выключает отправку follow-up сообщений."""
    await set_setting(
        session,
        FOLLOWUP_ENABLED_KEY,
        "1" if enabled else "0",
        updated_by,
    )


# ==================== FOLLOWUP LOST (НЕ ПОДПИСАН) ====================

DEFAULT_FOLLOWUP_LOST_TEXT = ""


async def get_followup_lost_text(session: AsyncSession | None = None) -> str:
    """
    Возвращает текст follow-up для неподписавшихся.
    Поддерживает ключи fup_lost_text и followup_lost_text (legacy).
    """
    if session is not None:
        text = await get_setting(session, FUP_LOST_TEXT_KEY)
        if not text:
            text = await get_setting(session, FOLLOWUP_LOST_TEXT_LEGACY_KEY)
        return (text or "").strip() or DEFAULT_FOLLOWUP_LOST_TEXT
    try:
        async with get_session() as s:
            return await get_followup_lost_text(s)
    except Exception as e:
        logger.error(f"Error loading followup_lost_text: {e}")
        return DEFAULT_FOLLOWUP_LOST_TEXT


async def set_followup_lost_text(text: str, updated_by: Optional[int] = None) -> None:
    """Сохраняет текст follow-up для неподписанных (пишет в оба ключа для совместимости)."""
    try:
        async with get_session() as session:
            await set_setting(session, FUP_LOST_TEXT_KEY, text, updated_by)
            await set_setting(session, FOLLOWUP_LOST_TEXT_LEGACY_KEY, text, updated_by)
            await session.commit()
            logger.info("Followup lost text updated")
    except Exception as e:
        logger.error(f"Error saving followup_lost_text: {e}")
        import traceback
        logger.error(traceback.format_exc())


# ==================== FOLLOWUP TEXTS (FUP1, FUP2, FUP3) ====================

async def get_followup_texts(session: AsyncSession | None = None) -> dict[str, str]:
    """
    Возвращает тексты трёх follow-up сообщений для подписавшихся:
    fup1_text, fup2_text, fup3_text.
    """
    keys = [FUP1_LEAD_TEXT_KEY, FUP2_LEAD_TEXT_KEY, FUP3_LEAD_TEXT_KEY]

    async def _get(s: AsyncSession) -> dict[str, str]:
        result = await s.execute(
            select(BotSettings).where(BotSettings.key.in_(keys))
        )
        rows = result.scalars().all()
        raw = {row.key: (row.value or "").strip() for row in rows}
        return {
            "fup1_text": raw.get(FUP1_LEAD_TEXT_KEY) or "",
            "fup2_text": raw.get(FUP2_LEAD_TEXT_KEY) or "",
            "fup3_text": raw.get(FUP3_LEAD_TEXT_KEY) or "",
        }

    if session is not None:
        return await _get(session)
    try:
        async with get_session() as s:
            return await _get(s)
    except Exception as e:
        logger.error(f"Error loading followup texts: {e}")
        return {"fup1_text": "", "fup2_text": "", "fup3_text": ""}


# ==================== DIAG SELECTION (2.2.2) ====================

async def get_diag_selection_settings(
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """
    Возвращает настройки экрана «Выбор типа диагностики»:
    text, diag1: {btn_text, url}, diag2: {btn_text, url}, diag3: {btn_text, url}.
    """
    keys = [
        DIAG_SELECTION_TEXT_KEY,
        DIAG1_BTN_TEXT_KEY,
        DIAG1_URL_KEY,
        DIAG2_BTN_TEXT_KEY,
        DIAG2_URL_KEY,
        DIAG3_BTN_TEXT_KEY,
        DIAG3_URL_KEY,
    ]

    async def _get(s: AsyncSession) -> dict[str, Any]:
        result = await s.execute(
            select(BotSettings).where(BotSettings.key.in_(keys))
        )
        rows = result.scalars().all()
        raw = {row.key: (row.value or "").strip() for row in rows}
        # Fallback URL из конфига, если в БД пусто
        def url(k: str, env_url: str) -> str:
            return raw.get(k) or env_url or ""

        return {
            "text": raw.get(DIAG_SELECTION_TEXT_KEY) or "",
            "diag1": {
                "btn_text": raw.get(DIAG1_BTN_TEXT_KEY) or "Диагностика 1",
                "url": url(DIAG1_URL_KEY, getattr(Config, "PAYMENT_URL_1", "") or ""),
            },
            "diag2": {
                "btn_text": raw.get(DIAG2_BTN_TEXT_KEY) or "Диагностика 2",
                "url": url(DIAG2_URL_KEY, getattr(Config, "PAYMENT_URL_2", "") or ""),
            },
            "diag3": {
                "btn_text": raw.get(DIAG3_BTN_TEXT_KEY) or "Диагностика 3",
                "url": url(DIAG3_URL_KEY, getattr(Config, "PAYMENT_URL_3", "") or ""),
            },
        }

    if session is not None:
        return await _get(session)
    try:
        async with get_session() as s:
            return await _get(s)
    except Exception as e:
        logger.error(f"Error loading diag selection settings: {e}")
        return {
            "text": "",
            "diag1": {"btn_text": "Диагностика 1", "url": ""},
            "diag2": {"btn_text": "Диагностика 2", "url": ""},
            "diag3": {"btn_text": "Диагностика 3", "url": ""},
        }


# ==================== FOLLOWUP LEAD (ПОДПИСАН) — legacy admin ====================

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

