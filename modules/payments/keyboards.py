"""
Keyboards for Lead Magnet Bot.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_free_access_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для проверки подписки на канал."""
    keyboard = [
        [
            InlineKeyboardButton("📢 Подписаться на канал", url="https://t.me/TaktikaKutuzova"),
            InlineKeyboardButton("✅ Я подписался", callback_data="payment:check_subscription")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели."""
    keyboard = [
        [InlineKeyboardButton("➕ Создать пост с кнопкой", callback_data="admin:add_button")],
        [InlineKeyboardButton("📊 Статистика по кнопкам", callback_data="admin:button_stats")],
        [InlineKeyboardButton("📝 Список команд", callback_data="admin:commands")]
    ]
    return InlineKeyboardMarkup(keyboard)
