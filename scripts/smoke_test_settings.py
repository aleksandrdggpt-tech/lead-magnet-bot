"""
Небольшой скрипт для локальной проверки новых настроек:
- welcome (приветствие)
- followup_lost (для неподписавшихся)
- followup_lead (текст + кнопки)

Скрипт:
1. Включает DEV_MODE=1, чтобы использовать SQLite локально.
2. Инициализирует БД.
3. Ставит тестовые значения и читает их обратно.
4. Печатает результаты в консоль.
"""

import asyncio
import os


def _prepare_env():
    # Включаем DEV_MODE, чтобы использовать SQLite
    os.environ.setdefault("DEV_MODE", "1")
    # Очищаем DATABASE_URL, чтобы сработал fallback на SQLite
    os.environ.pop("DATABASE_URL", None)


async def main() -> None:
    _prepare_env()

    from database.database import init_db
    from modules.payments.settings import (
        get_welcome_settings,
        set_welcome_settings,
        get_followup_lost_text,
        set_followup_lost_text,
        get_followup_lead_settings,
        set_followup_lead_settings,
    )

    print("Initializing database...")
    await init_db()
    print("Database initialized.\n")

    # --- Welcome settings ---
    print("=== TEST: WELCOME SETTINGS ===")
    await set_welcome_settings(
        text="👋 Тестовое приветствие\n\nЭто тестовый текст.",
        button_text="📋 Тестовая кнопка",
        link="https://example.com/test-welcome",
        updated_by=0,
    )
    welcome = await get_welcome_settings()
    print("Welcome text:", welcome["text"])
    print("Welcome button_text:", welcome["button_text"])
    print("Welcome link:", welcome["link"], "\n")

    # --- Followup lost ---
    print("=== TEST: FOLLOWUP LOST (НЕПОДПИСАН) ===")
    await set_followup_lost_text(
        "Тестовый follow-up для неподписавшихся. Подпишись и забери материал.",
        updated_by=0,
    )
    lost_text = await get_followup_lost_text()
    print("Followup lost text:", lost_text, "\n")

    # --- Followup lead ---
    print("=== TEST: FOLLOWUP LEAD (ПОДПИСАН) ===")
    await set_followup_lead_settings(
        text="Тестовый продающий текст для подписавшихся.",
        btn1_text="Тест Тариф 1",
        btn1_url="https://example.com/pay1",
        btn2_text="Тест Тариф 2",
        btn2_url="https://example.com/pay2",
        btn3_text="Тест Тариф 3",
        btn3_url="https://example.com/pay3",
        updated_by=0,
    )
    lead = await get_followup_lead_settings()
    print("Followup lead text:", lead["text"])
    print("Followup lead buttons:")
    for btn in lead["buttons"]:
        print(" -", btn["text"], "=>", btn["url"])


if __name__ == "__main__":
    asyncio.run(main())

