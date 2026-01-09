"""
Keyboards for Lead Magnet Bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


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


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели."""
    keyboard = [
        [InlineKeyboardButton("➕ Создать пост с кнопкой", callback_data="admin:add_button")],
        [InlineKeyboardButton("📊 Статистика по кнопкам", callback_data="admin:button_stats")],
        [InlineKeyboardButton("⚙️ Настройки канала", callback_data="admin:channel_settings")],
        [InlineKeyboardButton("📝 Список команд", callback_data="admin:commands")]
    ]
    return InlineKeyboardMarkup(keyboard)
