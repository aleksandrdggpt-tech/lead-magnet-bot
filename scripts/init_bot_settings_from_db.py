"""
Одноразовый скрипт: заполняет BotSettings недостающими ключами значениями по умолчанию.
Запуск из корня проекта: PYTHONPATH=. python scripts/init_bot_settings_from_db.py

Тексты по умолчанию соответствуют спецификации «Цепочка сообщений c лид-магнитом».
"""

import asyncio
import os
import sys

# Корень проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from database import BotSettings
from database.database import get_session, init_db
from modules.payments.settings import (
    get_setting,
    set_setting,
    WELCOME_TEXT_KEY,
    WELCOME_BUTTON_TEXT_KEY,
    WELCOME_LINK_KEY,
    WELCOME_BUTTON_TEXT_LEGACY_KEY,
    FOLLOWUP_ENABLED_KEY,
    FUP_LOST_TEXT_KEY,
    FOLLOWUP_LOST_TEXT_LEGACY_KEY,
    FUP1_LEAD_TEXT_KEY,
    FUP2_LEAD_TEXT_KEY,
    FUP3_LEAD_TEXT_KEY,
    DIAG_SELECTION_TEXT_KEY,
    DIAG1_BTN_TEXT_KEY,
    DIAG1_URL_KEY,
    DIAG2_BTN_TEXT_KEY,
    DIAG2_URL_KEY,
    DIAG3_BTN_TEXT_KEY,
    DIAG3_URL_KEY,
)
from config import Config


DEFAULT_WELCOME_TEXT = (
    "Добрый день! Я бот-помощник Александра Готальского. "
    "Вы запросили чек-лист «Стадия развития отдела продаж» — нажмите кнопку ниже, "
    "чтобы получить его после подписки на канал."
)

DEFAULT_WELCOME_BUTTON_TEXT = "Получите чек-лист продаж"

DEFAULT_FUP_LOST_TEXT = (
    "Привет! Вчера вы начинали получать чек-лист «Стадия развития отдела продаж», "
    "но не завершили подписку на канал. Подпишитесь и нажмите кнопку ниже, "
    "чтобы получить материал."
)

DEFAULT_FUP1_LEAD_TEXT = (
    "Вы уже получили чек-лист. Следующий шаг — диагностика отдела продаж: "
    "выявим узкие места и составим план. Выберите тип диагностики ниже."
)

DEFAULT_FUP2_LEAD_TEXT = (
    "Напоминаем: вы можете пройти диагностику отдела продаж и получить план действий. "
    "Ниже — отзыв и кнопка выбора формата."
)

DEFAULT_FUP3_LEAD_TEXT = (
    "Последнее напоминание: без диагностики «узкое горлышко» в отделе продаж "
    "часто остаётся скрытым. Выберите формат диагностики ниже."
)

DEFAULT_DIAG_SELECTION_TEXT = (
    "**Выберите тип диагностики:**\n\n"
    "1️⃣ Разовая диагностика — разбор кейса и рекомендации.\n"
    "2️⃣ Диагностика с сопровождением — план внедрения и поддержка.\n"
    "3️⃣ Глубокая диагностика — полный аудит и стратегия.\n\n"
    "Нажмите на кнопку ниже для перехода к оплате выбранного формата."
)

DEFAULT_DIAG1_BTN = "Диагностика 1"
DEFAULT_DIAG2_BTN = "Диагностика 2"
DEFAULT_DIAG3_BTN = "Диагностика 3"


async def ensure_key(session, key: str, default: str, source_key: str | None = None) -> bool:
    """Если ключа нет (или source_key передан и есть — копируем оттуда), записываем default. Возвращает True если что-то создали/обновили."""
    existing = await get_setting(session, key)
    if existing and existing.strip():
        return False
    if source_key:
        from_source = await get_setting(session, source_key)
        if from_source and from_source.strip():
            await set_setting(session, key, from_source)
            print(f"  [COPY] {key} <- {source_key}")
            return True
    await set_setting(session, key, default)
    print(f"  [SET]  {key}")
    return True


async def run():
    await init_db()
    created = 0
    async with get_session() as session:
        # Welcome: если есть welcome_text / welcome_button_text — используем; иначе дефолты
        if await ensure_key(session, WELCOME_TEXT_KEY, DEFAULT_WELCOME_TEXT):
            created += 1
        if await ensure_key(
            session,
            WELCOME_BUTTON_TEXT_KEY,
            DEFAULT_WELCOME_BUTTON_TEXT,
            source_key=WELCOME_BUTTON_TEXT_LEGACY_KEY,
        ):
            created += 1
        if await ensure_key(session, WELCOME_LINK_KEY, ""):
            created += 1
        if await ensure_key(
            session,
            WELCOME_BUTTON_TEXT_LEGACY_KEY,
            DEFAULT_WELCOME_BUTTON_TEXT,
            source_key=WELCOME_BUTTON_TEXT_KEY,
        ):
            created += 1

        if await ensure_key(session, FOLLOWUP_ENABLED_KEY, "1"):
            created += 1

        if await ensure_key(
            session,
            FUP_LOST_TEXT_KEY,
            DEFAULT_FUP_LOST_TEXT,
            source_key=FOLLOWUP_LOST_TEXT_LEGACY_KEY,
        ):
            created += 1
        if await ensure_key(
            session,
            FOLLOWUP_LOST_TEXT_LEGACY_KEY,
            DEFAULT_FUP_LOST_TEXT,
            source_key=FUP_LOST_TEXT_KEY,
        ):
            created += 1

        if await ensure_key(session, FUP1_LEAD_TEXT_KEY, DEFAULT_FUP1_LEAD_TEXT):
            created += 1
        if await ensure_key(session, FUP2_LEAD_TEXT_KEY, DEFAULT_FUP2_LEAD_TEXT):
            created += 1
        if await ensure_key(session, FUP3_LEAD_TEXT_KEY, DEFAULT_FUP3_LEAD_TEXT):
            created += 1

        if await ensure_key(session, DIAG_SELECTION_TEXT_KEY, DEFAULT_DIAG_SELECTION_TEXT):
            created += 1
        if await ensure_key(session, DIAG1_BTN_TEXT_KEY, DEFAULT_DIAG1_BTN):
            created += 1
        if await ensure_key(session, DIAG1_URL_KEY, getattr(Config, "PAYMENT_URL_1", "") or ""):
            created += 1
        if await ensure_key(session, DIAG2_BTN_TEXT_KEY, DEFAULT_DIAG2_BTN):
            created += 1
        if await ensure_key(session, DIAG2_URL_KEY, getattr(Config, "PAYMENT_URL_2", "") or ""):
            created += 1
        if await ensure_key(session, DIAG3_BTN_TEXT_KEY, DEFAULT_DIAG3_BTN):
            created += 1
        if await ensure_key(session, DIAG3_URL_KEY, getattr(Config, "PAYMENT_URL_3", "") or ""):
            created += 1

    print(f"Done. Created/updated {created} settings.")


if __name__ == "__main__":
    asyncio.run(run())
