"""
Keyboards for Lead Magnet Bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_admin_panel_keyboard(followup_enabled: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура админ-панели. followup_enabled — текущее состояние переключателя follow-up."""
    followup_btn_text = (
        "🔔 Follow-up: ВКЛ (нажми, чтобы выключить)"
        if followup_enabled
        else "🔕 Follow-up: ВЫКЛ (нажми, чтобы включить)"
    )
    keyboard = [
        [InlineKeyboardButton("➕ Создать пост с кнопкой", callback_data="admin:add_button")],
        [InlineKeyboardButton("📊 Статистика по кнопкам", callback_data="admin:button_stats")],
        [InlineKeyboardButton("⚙️ Настройки канала", callback_data="admin:channel_settings")],
        [InlineKeyboardButton("💬 Настройки приветствия", callback_data="admin:welcome_settings")],
        [InlineKeyboardButton(followup_btn_text, callback_data="admin:toggle_followup")],
        [InlineKeyboardButton("📩 Follow-up (неподписавшиеся)", callback_data="admin:followup_lost_settings")],
        [InlineKeyboardButton("📩 Follow-up (подписавшиеся)", callback_data="admin:followup_lead_settings")],
        [InlineKeyboardButton("📝 Список команд", callback_data="admin:commands")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_free_access_keyboard(channel_username: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для проверки подписки на канал.
    
    Args:
        channel_username: Username канала (например: @channel_username или channel_username)
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками
    """
    # Убираем @ если есть для URL
    channel_for_url = channel_username.lstrip('@')
    channel_url = f"https://t.me/{channel_for_url}"
    
    keyboard = [
        [
            InlineKeyboardButton("📢 Подписаться на канал", url=channel_url),
            InlineKeyboardButton("✅ Я подписался", callback_data="payment:check_subscription")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
