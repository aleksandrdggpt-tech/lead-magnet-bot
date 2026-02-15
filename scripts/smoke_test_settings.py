"""
Скрипт проверки настроек бота (BotSettings и геттеры).
- Инициализация БД, наличие ключей из спецификации.
- get_welcome_settings, get_followup_enabled, get_followup_texts, get_diag_selection_settings.

Запуск из корня: PYTHONPATH=. python scripts/smoke_test_settings.py
При необходимости: DEV_MODE=1 (SQLite) или DATABASE_URL для PostgreSQL.
"""

import asyncio
import os


def _prepare_env():
    os.environ.setdefault("DEV_MODE", "1")
    os.environ.pop("DATABASE_URL", None)


async def main() -> None:
    _prepare_env()

    from database.database import init_db
    from database import BotSettings
    from sqlalchemy import select
    from modules.payments.settings import (
        get_welcome_settings,
        set_welcome_settings,
        get_followup_enabled,
        set_followup_enabled,
        get_followup_lost_text,
        set_followup_lost_text,
        get_followup_texts,
        get_followup_lead_settings,
        set_followup_lead_settings,
        get_diag_selection_settings,
        WELCOME_TEXT_KEY,
        WELCOME_BUTTON_TEXT_KEY,
        WELCOME_LINK_KEY,
        FOLLOWUP_ENABLED_KEY,
        FUP_LOST_TEXT_KEY,
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
    from database.database import get_session

    print("Initializing database...")
    await init_db()
    print("Database initialized.\n")

    # --- 1) Наличие ключей BotSettings ---
    print("=== 1) BOT SETTINGS KEYS ===")
    required_keys = [
        WELCOME_TEXT_KEY,
        WELCOME_BUTTON_TEXT_KEY,
        WELCOME_LINK_KEY,
        FOLLOWUP_ENABLED_KEY,
        FUP_LOST_TEXT_KEY,
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
    ]
    async with get_session() as session:
        result = await session.execute(
            select(BotSettings.key).where(BotSettings.key.in_(required_keys))
        )
        present = {row[0] for row in result.scalars().all()}
    for k in required_keys:
        status = "OK" if k in present else "MISSING"
        print(f"  {k}: {status}")
    print()

    # --- 2) Welcome ---
    print("=== 2) WELCOME SETTINGS ===")
    await set_welcome_settings(
        text="Тестовое приветствие",
        button_text="Тест кнопка",
        link="https://example.com/welcome",
        updated_by=0,
    )
    welcome = await get_welcome_settings()
    assert welcome.get("text"), "welcome.text empty"
    assert welcome.get("button_text"), "welcome.button_text empty"
    print("  text:", welcome["text"][:50] + "...")
    print("  button_text:", welcome["button_text"])
    print("  link:", welcome.get("link"))
    print()

    # --- 3) Follow-up enabled ---
    print("=== 3) FOLLOWUP ENABLED ===")
    async with get_session() as session:
        await set_followup_enabled(session, True)
    on = await get_followup_enabled()
    print("  get_followup_enabled():", on)
    async with get_session() as session:
        await set_followup_enabled(session, False)
    off = await get_followup_enabled()
    print("  after set False:", off)
    async with get_session() as session:
        await set_followup_enabled(session, True)
    print()

    # --- 4) Follow-up lost ---
    print("=== 4) FOLLOWUP LOST TEXT ===")
    await set_followup_lost_text("Тест fup_lost", updated_by=0)
    lost = await get_followup_lost_text()
    print("  get_followup_lost_text():", lost[:50] + "..." if len(lost) > 50 else lost)
    print()

    # --- 5) Follow-up texts (fup1, fup2, fup3) ---
    print("=== 5) FOLLOWUP TEXTS (fup1, fup2, fup3) ===")
    fup = await get_followup_texts()
    for key in ("fup1_text", "fup2_text", "fup3_text"):
        val = (fup.get(key) or "").strip()
        print(f"  {key}: {'(set)' if val else '(empty)'}")
    print()

    # --- 6) Diag selection ---
    print("=== 6) DIAG SELECTION SETTINGS ===")
    diag = await get_diag_selection_settings()
    print("  text:", "(set)" if (diag.get("text") or "").strip() else "(empty)")
    for k in ("diag1", "diag2", "diag3"):
        d = diag.get(k) or {}
        print(f"  {k}: btn_text={d.get('btn_text')}, url={bool(d.get('url'))}")
    print()

    # --- 7) Legacy followup_lead (admin) ---
    print("=== 7) FOLLOWUP LEAD (legacy) ===")
    await set_followup_lead_settings(
        text="Тест lead текст",
        btn1_text="Т1",
        btn1_url="https://example.com/1",
        btn2_text="",
        btn2_url="",
        btn3_text="",
        btn3_url="",
        updated_by=0,
    )
    lead = await get_followup_lead_settings()
    print("  text:", lead.get("text", "")[:40] + "...")
    print("  buttons:", len(lead.get("buttons", [])))
    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
