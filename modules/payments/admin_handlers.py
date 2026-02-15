"""
Admin handlers for Lead Magnet Bot.
Handles admin panel and channel button management.
"""

import logging
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)
from telegram.constants import ParseMode
from sqlalchemy import select, func
from enum import IntEnum

from database.database import get_session
from database import ChannelButton, ChannelButtonClick, BotSettings
from services.channel_button_service import ChannelButtonService
from .keyboards import get_admin_panel_keyboard
from .subscription import get_subscription_channel
from .settings import (
    get_welcome_settings,
    set_welcome_settings,
    get_followup_enabled,
    set_followup_enabled,
    get_followup_lost_text,
    set_followup_lost_text,
    get_followup_lead_settings,
    set_followup_lead_settings,
)
from config import Config

logger = logging.getLogger(__name__)


class AdminButtonStates(IntEnum):
    """States for button addition dialog."""
    WAITING_BUTTON_TEXT = 1
    WAITING_LEAD_MAGNET_TYPE = 2
    WAITING_EXTERNAL_LINK = 3
    WAITING_CHANNEL = 4
    WAITING_POST_CONTENT = 5
    WAITING_SUBSCRIPTION_CHANNEL = 6  # Для настройки канала подписки
    WAITING_WELCOME_TEXT = 7
    WAITING_WELCOME_BUTTON_TEXT = 8
    WAITING_WELCOME_LINK = 9
    WAITING_FOLLOWUP_LOST_TEXT = 10
    WAITING_FOLLOWUP_LEAD_TEXT = 11
    WAITING_FOLLOWUP_LEAD_BTN1_TEXT = 12
    WAITING_FOLLOWUP_LEAD_BTN1_URL = 13
    WAITING_FOLLOWUP_LEAD_BTN2_TEXT = 14
    WAITING_FOLLOWUP_LEAD_BTN2_URL = 15
    WAITING_FOLLOWUP_LEAD_BTN3_TEXT = 16
    WAITING_FOLLOWUP_LEAD_BTN3_URL = 17


# ==================== ADMIN AUTHENTICATION ====================

def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id in Config.ADMIN_USER_IDS


# ==================== ADMIN COMMAND ====================

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command - show admin panel."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа к админ-панели.")
        return
    
    message = """
🔧 **АДМИН-ПАНЕЛЬ**

**Доступные команды:**
`/admin` - Админ-панель
`/add_button` - Создать пост с кнопкой
`/set_channel` - Настроить канал для проверки подписки

Выберите действие ниже:
"""
    
    followup_on = await get_followup_enabled()
    await update.message.reply_text(
        message,
        reply_markup=get_admin_panel_keyboard(followup_enabled=followup_on),
        parse_mode=ParseMode.MARKDOWN
    )


# ==================== ADMIN CALLBACK HANDLERS ====================

async def admin_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to admin panel."""
    query = update.callback_query
    await query.answer()
    
    message = """
🔧 **АДМИН-ПАНЕЛЬ**

Выберите действие:
"""
    
    followup_on = await get_followup_enabled()
    await query.edit_message_text(
        message,
        reply_markup=get_admin_panel_keyboard(followup_enabled=followup_on),
        parse_mode=ParseMode.MARKDOWN
    )


async def admin_toggle_followup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключатель follow-up: вкл/выкл."""
    query = update.callback_query
    await query.answer()
    telegram_id = query.from_user.id
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    try:
        async with get_session() as session:
            current = await get_followup_enabled(session)
            await set_followup_enabled(session, not current, updated_by=telegram_id)
        new_state = not current
    except Exception as e:
        logger.error(f"Error toggling followup_enabled: {e}")
        await query.edit_message_text("❌ Ошибка при изменении настройки.")
        return
    message = (
        "🔧 **АДМИН-ПАНЕЛЬ**\n\n"
        "Follow-up сообщения: **" + ("включены" if new_state else "выключены") + "**.\n\n"
        "Выберите действие ниже:"
    )
    await query.edit_message_text(
        message,
        reply_markup=get_admin_panel_keyboard(followup_enabled=new_state),
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_commands_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of admin commands."""
    query = update.callback_query
    await query.answer()
    
    telegram_id = query.from_user.id
    
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    message = """
📝 **СПИСОК АДМИН-КОМАНД**

**Основные команды:**
`/admin` - Админ-панель
`/add_button` - Создать пост с кнопкой в канале
`/set_channel` - Настроить канал для проверки подписки
`/set_welcome` - Настроить приветственное сообщение в боте
`/set_followup_lost` - Настроить follow-up для неподписавшихся
`/set_followup_lead` - Настроить follow-up для подписавшихся

**Действия через меню:**
• ➕ Создать пост с кнопкой
• 📊 Статистика по кнопкам
• ⚙️ Настройки канала
• 💬 Настройки приветствия
"""
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data="admin:back")]
        ])
    )


async def admin_button_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed statistics for each button."""
    query = update.callback_query
    await query.answer()
    
    telegram_id = query.from_user.id
    
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    try:
        async with get_session() as session:
            # Получаем все кнопки
            buttons_result = await session.execute(
                select(ChannelButton).order_by(ChannelButton.created_at.desc())
            )
            buttons = buttons_result.scalars().all()
            
            if not buttons:
                await query.edit_message_text(
                    "📊 **СТАТИСТИКА ПО КНОПКАМ**\n\n"
                    "Кнопки еще не созданы.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("◀️ Назад", callback_data="admin:back")]
                    ])
                )
                return
            
            # Собираем статистику по каждой кнопке
            stats_lines = []
            for button in buttons:
                # Считаем нажатия для этой кнопки
                clicks_result = await session.execute(
                    select(func.count(ChannelButtonClick.id))
                    .where(ChannelButtonClick.button_id == button.id)
                )
                clicks_count = clicks_result.scalar() or 0
                
                # Считаем уникальных пользователей
                unique_result = await session.execute(
                    select(func.count(func.distinct(ChannelButtonClick.telegram_id)))
                    .where(ChannelButtonClick.button_id == button.id)
                )
                unique_count = unique_result.scalar() or 0
                
                # Форматируем тип
                type_emoji = "🤖" if button.lead_magnet_type == "bot" else "🔗"
                type_name = "Бот" if button.lead_magnet_type == "bot" else "Внешняя ссылка"
                
                # Обрезаем длинные тексты
                post_title_short = button.post_title[:40] + "..." if len(button.post_title) > 40 else button.post_title
                button_text_short = button.button_text[:30] + "..." if len(button.button_text) > 30 else button.button_text
                
                stats_lines.append(
                    f"**🔘 {button_text_short}**\n"
                    f"📝 Пост: {post_title_short}\n"
                    f"{type_emoji} Тип: {type_name}\n"
                    f"👆 Нажатий: {clicks_count} | 👥 Уникальных: {unique_count}\n"
                )
            
            # Формируем сообщение (ограничиваем длину)
            message = "📊 **СТАТИСТИКА ПО КНОПКАМ**\n\n"
            message += "\n".join(stats_lines[:10])  # Показываем первые 10
            
            if len(buttons) > 10:
                message += f"\n\n... и еще {len(buttons) - 10} кнопок"
            
            await query.edit_message_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад", callback_data="admin:back")]
                ])
            )
    
    except Exception as e:
        logger.error(f"Error getting button stats: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await query.edit_message_text("❌ Ошибка загрузки статистики.")


# ==================== CHANNEL BUTTON MANAGEMENT ====================

async def add_button_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add_button command - создать пост с кнопкой в канале."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🔘 **СОЗДАНИЕ ПОСТА С КНОПКОЙ**\n\n"
        "Отправьте текст для кнопки.\n\n"
        "Например: \"Получить лид-магнит\" или \"Попробовать бота\"\n\n"
        "Используйте /cancel для отмены.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    return AdminButtonStates.WAITING_BUTTON_TEXT


async def add_button_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button text input."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    button_text = update.message.text.strip()
    
    if not button_text:
        await update.message.reply_text("❌ Текст кнопки не может быть пустым.")
        return AdminButtonStates.WAITING_BUTTON_TEXT
    
    # Сохраняем текст кнопки
    context.user_data['button_text'] = button_text
    
    # Показываем выбор типа лид-магнита
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Доступ к боту", callback_data="button:type:bot")],
        [InlineKeyboardButton("🔗 Внешняя ссылка", callback_data="button:type:external")],
    ])
    
    await update.message.reply_text(
        "✅ Текст кнопки сохранен!\n\n"
        "Теперь выберите тип лид-магнита:",
        reply_markup=keyboard
    )
    
    return AdminButtonStates.WAITING_LEAD_MAGNET_TYPE


async def add_button_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle lead magnet type selection."""
    query = update.callback_query
    await query.answer()
    
    telegram_id = query.from_user.id
    
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    # Извлекаем тип из callback_data
    lead_magnet_type = query.data.split(":")[-1]  # "bot" или "external"
    
    # Сохраняем тип
    context.user_data['lead_magnet_type'] = lead_magnet_type
    
    if lead_magnet_type == "bot":
        # Для бота не нужна дополнительная ссылка
        await query.edit_message_text(
            "✅ Тип выбран: Доступ к боту\n\n"
            "Отправьте username канала, в который нужно опубликовать пост.\n\n"
            "Формат:\n"
            "• @channel_username\n"
            "• channel_username (без @)\n\n"
            "Бот должен быть администратором канала."
        )
        return AdminButtonStates.WAITING_CHANNEL
    
    else:
        # Для внешней ссылки нужна ссылка
        await query.edit_message_text(
            "✅ Тип выбран: Внешняя ссылка\n\n"
            "Отправьте ссылку.\n\n"
            "Примеры:\n"
            "• Google Drive: https://drive.google.com/file/d/...\n"
            "• Опрос: https://t.me/poll/...\n"
            "• Любая другая ссылка"
        )
        
        return AdminButtonStates.WAITING_EXTERNAL_LINK


async def add_button_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle external link input."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    external_link = update.message.text.strip()
    
    if not external_link or not (external_link.startswith('http://') or external_link.startswith('https://')):
        await update.message.reply_text(
            "❌ Неверный формат ссылки. Отправьте полную ссылку (начинается с http:// или https://)"
        )
        return AdminButtonStates.WAITING_EXTERNAL_LINK
    
    # Сохраняем ссылку
    context.user_data['external_link'] = external_link
    
    await update.message.reply_text(
        "✅ Ссылка сохранена!\n\n"
        "Отправьте username канала, в который нужно опубликовать пост.\n\n"
        "Формат:\n"
        "• @channel_username\n"
        "• channel_username (без @)\n\n"
        "Бот должен быть администратором канала."
    )
    
    return AdminButtonStates.WAITING_CHANNEL


async def add_button_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel selection."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    channel_input = update.message.text.strip()
    
    # Обрабатываем формат канала
    if channel_input.startswith('@'):
        channel_id = channel_input
    else:
        channel_id = f"@{channel_input}"
    
    # Проверяем, что бот может работать с каналом
    try:
        # Пытаемся получить информацию о канале
        chat = await context.bot.get_chat(chat_id=channel_id)
        
        # Проверяем, что это канал
        if chat.type not in ['channel', 'supergroup']:
            await update.message.reply_text(
                "❌ Это не канал. Отправьте username канала.\n\n"
                "Формат: @channel_username или channel_username"
            )
            return AdminButtonStates.WAITING_CHANNEL
        
        # Сохраняем канал
        context.user_data['button_channel_id'] = channel_id
        
        await update.message.reply_text(
            f"✅ Канал выбран: {channel_id}\n\n"
            "Теперь отправьте пост, который нужно опубликовать в канале.\n\n"
            "Вы можете отправить:\n"
            "• Текст поста\n"
            "• Текст с изображением\n"
            "• Переслать сообщение из другого чата"
        )
        
        return AdminButtonStates.WAITING_POST_CONTENT
        
    except Exception as e:
        logger.error(f"Error checking channel: {e}")
        await update.message.reply_text(
            f"❌ Ошибка при проверке канала: {e}\n\n"
            "Убедитесь, что:\n"
            "• Бот является администратором канала\n"
            "• Username канала указан правильно\n"
            "• Канал существует и доступен"
        )
        return AdminButtonStates.WAITING_CHANNEL


async def add_button_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle post content input and publish it with button."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    # Получаем сохраненные данные
    button_text = context.user_data.get('button_text')
    lead_magnet_type = context.user_data.get('lead_magnet_type')
    
    if not button_text or not lead_magnet_type:
        await update.message.reply_text("❌ Ошибка: данные не найдены. Начните заново.")
        return ConversationHandler.END
    
    # Получаем ID канала из сохраненных данных
    channel_id = context.user_data.get('button_channel_id')
    if not channel_id:
        await update.message.reply_text("❌ Ошибка: канал не выбран. Начните заново.")
        return ConversationHandler.END
    
    try:
        # Получаем контент поста
        post_text = None
        photo_file_id = None
        
        # Обрабатываем пересланное сообщение
        if update.message.forward_from_chat or update.message.forward_from:
            if update.message.text:
                post_text = update.message.text
            elif update.message.caption:
                post_text = update.message.caption
                if update.message.photo:
                    photo_file_id = update.message.photo[-1].file_id
            elif update.message.photo:
                photo_file_id = update.message.photo[-1].file_id
                post_text = ""
        else:
            # Обычное сообщение
            if update.message.text:
                post_text = update.message.text
            elif update.message.caption:
                post_text = update.message.caption
                if update.message.photo:
                    photo_file_id = update.message.photo[-1].file_id
            elif update.message.photo:
                # Только фото без текста
                photo_file_id = update.message.photo[-1].file_id
                post_text = ""
        
        if not post_text and not photo_file_id:
            await update.message.reply_text(
                "❌ Не удалось получить контент поста.\n\n"
                "Отправьте текст или текст с изображением."
            )
            return AdminButtonStates.WAITING_POST_CONTENT
        
        # Если текст пустой, используем дефолтный
        if not post_text:
            post_text = "🔘 " + button_text
        
        # Генерируем ссылку
        if lead_magnet_type == "bot":
            # Получаем информацию о боте
            bot_info = await context.bot.get_me()
            bot_username = bot_info.username
            # Сначала создаем временную ссылку (без message_id)
            temp_link = ChannelButtonService.generate_bot_link(bot_username)
            link = temp_link
        else:
            # Внешняя ссылка
            link = context.user_data.get('external_link')
            if not link:
                await update.message.reply_text("❌ Ошибка: ссылка не найдена. Начните заново.")
                return ConversationHandler.END
        
        # Публикуем пост с кнопкой
        message_id = await ChannelButtonService.publish_post_with_button(
            bot=context.bot,
            channel_id=channel_id,
            post_content=post_text,
            button_text=button_text,
            link=link,
            photo_file_id=photo_file_id,
            lead_magnet_type=lead_magnet_type
        )
        
        if message_id:
            # Обновляем ссылку для бота с реальным message_id
            if lead_magnet_type == "bot":
                bot_info = await context.bot.get_me()
                bot_username = bot_info.username
                # Генерируем правильную ссылку с message_id
                link = ChannelButtonService.generate_bot_link(bot_username, message_id)
                logger.info(f"🔗 Generated bot link with message_id {message_id}: {link}")
                # Обновляем кнопку в посте с правильной ссылкой
                keyboard = ChannelButtonService.create_button_keyboard(link, button_text)
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=channel_id,
                        message_id=message_id,
                        reply_markup=keyboard
                    )
                    logger.info(f"✅ Button updated with correct link for message_id {message_id}")
                except Exception as e:
                    logger.error(f"❌ Failed to update button with correct link: {e}")
            
            # Сохраняем информацию о кнопке в БД
            try:
                # Используем первые 100 символов текста как название поста
                post_title = post_text[:100] + "..." if len(post_text) > 100 else post_text
                if not post_title:
                    post_title = f"Пост {message_id}"
                
                async with get_session() as session:
                    button = ChannelButton(
                        channel_id=str(channel_id),
                        message_id=message_id,
                        post_title=post_title,
                        button_text=button_text,
                        lead_magnet_type=lead_magnet_type,
                        link=link,
                        created_by=telegram_id
                    )
                    session.add(button)
                    await session.commit()
                    logger.info(f"Button info saved: ID {button.id}")
            except Exception as e:
                logger.error(f"Error saving button info: {e}")
            
            # Используем HTML для безопасного отображения
            escaped_button_text = html.escape(button_text)
            escaped_link = html.escape(link)
            escaped_post_title = html.escape(post_title[:50])
            
            await update.message.reply_text(
                f"✅ <b>Пост опубликован!</b>\n\n"
                f"📊 ID поста: <code>{message_id}</code>\n"
                f"📝 Название: {escaped_post_title}\n"
                f"🔘 Текст кнопки: {escaped_button_text}\n"
                f"{'🤖' if lead_magnet_type == 'bot' else '🔗'} Тип: {'Доступ к боту' if lead_magnet_type == 'bot' else 'Внешняя ссылка'}\n"
                f"🔗 Ссылка: <code>{escaped_link}</code>",
                parse_mode=ParseMode.HTML
            )
            logger.info(f"Post with button '{button_text}' published in channel {channel_id}, message_id: {message_id}")
        else:
            await update.message.reply_text(
                f"❌ <b>Ошибка при публикации поста.</b>\n\n"
                "Возможные причины:\n"
                "• Бот не является администратором канала\n"
                "• У бота нет прав на отправку сообщений\n"
                "• Недостаточно прав для работы с каналом",
                parse_mode=ParseMode.HTML
            )
        
        # Очищаем данные
        context.user_data.pop('button_text', None)
        context.user_data.pop('lead_magnet_type', None)
        context.user_data.pop('external_link', None)
        context.user_data.pop('button_channel_id', None)
        
    except Exception as e:
        logger.error(f"Error publishing post: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await update.message.reply_text(f"❌ Ошибка: {e}")
    
    return ConversationHandler.END


async def cancel_button_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel button addition."""
    # Очищаем сохраненные данные
    context.user_data.pop('button_channel_id', None)
    context.user_data.pop('button_text', None)
    context.user_data.pop('lead_magnet_type', None)
    context.user_data.pop('external_link', None)
    
    await update.message.reply_text("❌ Добавление кнопки отменено.")
    return ConversationHandler.END


# ==================== CHANNEL SETTINGS ====================

async def set_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_channel command - настройка канала для проверки подписки."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return
    
    # Получаем текущий канал
    try:
        current_channel = await get_subscription_channel()
        message = f"""
⚙️ **НАСТРОЙКА КАНАЛА ДЛЯ ПРОВЕРКИ ПОДПИСКИ**

**Текущий канал:** {current_channel}

Отправьте username канала для проверки подписки.

**Формат:**
• @channel_username
• channel_username (без @)

**Важно:** Бот должен быть администратором канала для проверки подписки.

Используйте /cancel для отмены.
"""
    except Exception as e:
        logger.error(f"Error getting current channel: {e}")
        message = """
⚙️ **НАСТРОЙКА КАНАЛА ДЛЯ ПРОВЕРКИ ПОДПИСКИ**

Отправьте username канала для проверки подписки.

**Формат:**
• @channel_username
• channel_username (без @)

**Важно:** Бот должен быть администратором канала для проверки подписки.

Используйте /cancel для отмены.
"""
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    return AdminButtonStates.WAITING_SUBSCRIPTION_CHANNEL


async def set_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel username input for subscription check."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    channel_input = update.message.text.strip()
    
    # Обрабатываем формат канала
    if channel_input.startswith('@'):
        channel_username = channel_input
    else:
        channel_username = f"@{channel_input}"
    
    # Проверяем, что бот может работать с каналом
    try:
        # Пытаемся получить информацию о канале
        chat = await context.bot.get_chat(chat_id=channel_username)
        
        # Проверяем, что это канал
        if chat.type not in ['channel', 'supergroup']:
            await update.message.reply_text(
                "❌ Это не канал. Отправьте username канала.\n\n"
                "Формат: @channel_username или channel_username"
            )
            return AdminButtonStates.WAITING_SUBSCRIPTION_CHANNEL
        
        # Сохраняем в БД
        async with get_session() as session:
            result = await session.execute(
                select(BotSettings).where(BotSettings.key == "subscription_channel")
            )
            setting = result.scalar_one_or_none()
            
            if setting:
                # Обновляем существующую настройку
                setting.value = channel_username
                setting.updated_by = telegram_id
            else:
                # Создаем новую настройку
                setting = BotSettings(
                    key="subscription_channel",
                    value=channel_username,
                    updated_by=telegram_id
                )
                session.add(setting)
            
            await session.commit()
            logger.info(f"Subscription channel updated to {channel_username} by {telegram_id}")
        
        await update.message.reply_text(
            f"✅ **Канал успешно настроен!**\n\n"
            f"Канал для проверки подписки: {channel_username}\n\n"
            f"Теперь бот будет проверять подписку на этот канал.",
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error setting channel: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        await update.message.reply_text(
            f"❌ Ошибка при настройке канала: {e}\n\n"
            "Убедитесь, что:\n"
            "• Бот является администратором канала\n"
            "• Username канала указан правильно\n"
            "• Канал существует и доступен"
        )
        return AdminButtonStates.WAITING_SUBSCRIPTION_CHANNEL
    
    return ConversationHandler.END


async def admin_channel_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show channel settings."""
    query = update.callback_query
    await query.answer()
    
    telegram_id = query.from_user.id
    
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    try:
        current_channel = await get_subscription_channel()
        message = f"""
⚙️ **НАСТРОЙКИ КАНАЛА**

**Текущий канал для проверки подписки:** {current_channel}

Используйте команду `/set_channel` для изменения канала.
"""
    except Exception as e:
        logger.error(f"Error getting channel settings: {e}")
        message = """
⚙️ **НАСТРОЙКИ КАНАЛА**

Используйте команду `/set_channel` для настройки канала.
"""
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data="admin:back")]
        ])
    )


async def cancel_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel channel setting."""
    await update.message.reply_text("❌ Настройка канала отменена.")
    return ConversationHandler.END


# ==================== WELCOME MESSAGE SETTINGS ====================

async def set_welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_welcome command - настройка приветственного сообщения."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    # Показываем инструкцию (без вывода «сырых» текущих текстов, чтобы избежать экранирования)
    try:
        await get_welcome_settings()  # просто проверяем, что всё работает
    except Exception as e:
        logger.error(f"Error getting welcome settings: {e}")
    
    message = (
        "💬 **НАСТРОЙКА ПРИВЕТСТВЕННОГО СООБЩЕНИЯ**\n\n"
        "Шаг 1. Отправьте **текст приветствия**, который будет показываться при входе в бота.\n\n"
        "Шаг 2. Затем бот попросит **текст кнопки**.\n"
        "Шаг 3. После этого бот попросит **ссылку на лид-магнит**.\n\n"
        "_Используйте /cancel для отмены._"
    )
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    return AdminButtonStates.WAITING_WELCOME_TEXT


async def set_welcome_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняем текст приветствия и спрашиваем текст кнопки."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("❌ Текст приветствия не может быть пустым. Отправьте текст еще раз.")
        return AdminButtonStates.WAITING_WELCOME_TEXT
    
    context.user_data["welcome_text"] = text
    
    await update.message.reply_text(
        "✅ Текст приветствия сохранен!\n\n"
        "Теперь отправьте **текст кнопки**.\n\n"
        "Например: \"📋 Получить чек-лист отдела продаж\"",
        parse_mode=ParseMode.MARKDOWN,
    )
    return AdminButtonStates.WAITING_WELCOME_BUTTON_TEXT


async def set_welcome_button_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняем текст кнопки и спрашиваем ссылку."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    button_text = update.message.text.strip()
    if not button_text:
        await update.message.reply_text("❌ Текст кнопки не может быть пустым. Отправьте текст еще раз.")
        return AdminButtonStates.WAITING_WELCOME_BUTTON_TEXT
    
    context.user_data["welcome_button_text"] = button_text
    
    await update.message.reply_text(
        "✅ Текст кнопки сохранен!\n\n"
        "Теперь отправьте **ссылку на чек-лист** или другой лид-магнит.\n\n"
        "Ссылка должна начинаться с http:// или https://",
        parse_mode=ParseMode.MARKDOWN,
    )
    return AdminButtonStates.WAITING_WELCOME_LINK


async def set_welcome_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняем ссылку и записываем все настройки в БД."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    link = update.message.text.strip()
    if not (link.startswith("http://") or link.startswith("https://")):
        await update.message.reply_text(
            "❌ Неверный формат ссылки. Отправьте полную ссылку, начинающуюся с http:// или https://"
        )
        return AdminButtonStates.WAITING_WELCOME_LINK
    
    text = context.user_data.get("welcome_text")
    button_text = context.user_data.get("welcome_button_text")
    
    if not text or not button_text:
        await update.message.reply_text("❌ Ошибка: данные приветствия потеряны. Попробуйте еще раз с /set_welcome.")
        return ConversationHandler.END
    
    # Сохраняем в БД
    await set_welcome_settings(text=text, button_text=button_text, link=link, updated_by=telegram_id)
    
    # Очищаем временные данные
    context.user_data.pop("welcome_text", None)
    context.user_data.pop("welcome_button_text", None)
    
    await update.message.reply_text(
        "✅ **Приветственное сообщение обновлено!**\n\n"
        "Теперь при входе в бота пользователи будут видеть новый текст и кнопку.",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# ==================== FOLLOW-UP SETTINGS ====================

async def set_followup_lost_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_followup_lost - текст для неподписавшихся."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    try:
        current_text = await get_followup_lost_text()
        message = (
            "♻️ **НАСТРОЙКА FOLLOW-UP ДЛЯ НЕПОДПИСАВШИХСЯ (lost)**\n\n"
            "**Текущий текст:**\n"
            f"{current_text}\n\n"
            "Отправьте **новый текст сообщения**, которое будет приходить на следующий день "
            "тем, кто нажал на лид-магнит, но так и не подписался на канал.\n\n"
            "_Используйте /cancel для отмены._"
        )
    except Exception as e:
        logger.error(f"Error getting followup_lost_text: {e}")
        message = (
            "♻️ **НАСТРОЙКА FOLLOW-UP ДЛЯ НЕПОДПИСАВШИХСЯ (lost)**\n\n"
            "Отправьте **текст сообщения**, которое будет приходить на следующий день тем, "
            "кто нажал на лид-магнит, но так и не подписался на канал.\n\n"
            "_Используйте /cancel для отмены._"
        )
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    return AdminButtonStates.WAITING_FOLLOWUP_LOST_TEXT


async def set_followup_lost_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняет текст follow-up для неподписанных."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("❌ Текст не может быть пустым. Отправьте текст еще раз.")
        return AdminButtonStates.WAITING_FOLLOWUP_LOST_TEXT
    
    await set_followup_lost_text(text, updated_by=telegram_id)
    await update.message.reply_text(
        "✅ **Текст follow-up для неподписавшихся обновлён!**",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def set_followup_lead_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /set_followup_lead - текст и кнопки для подписавшихся."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    try:
        current = await get_followup_lead_settings()
        btn_lines = "\n".join(
            [f"- {btn['text']}: {btn['url']}" for btn in current["buttons"]]
        ) or "кнопки не настроены"
        message = (
            "💰 **НАСТРОЙКА FOLLOW-UP ДЛЯ ПОДПИСАВШИХСЯ (lead)**\n\n"
            "**Текущий текст:**\n"
            f"{current['text']}\n\n"
            "**Текущие кнопки:**\n"
            f"{btn_lines}\n\n"
            "Сначала отправьте **новый продающий текст** сообщения.\n\n"
            "_После этого бот по очереди попросит тексты и ссылки для до 3 кнопок._\n\n"
            "_Используйте /cancel для отмены._"
        )
    except Exception as e:
        logger.error(f"Error getting followup_lead_settings: {e}")
        message = (
            "💰 **НАСТРОЙКА FOLLOW-UP ДЛЯ ПОДПИСАВШИХСЯ (lead)**\n\n"
            "Сначала отправьте **продающий текст** сообщения.\n\n"
            "_После этого бот по очереди попросит тексты и ссылки для до 3 кнопок._\n\n"
            "_Используйте /cancel для отмены._"
        )
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    return AdminButtonStates.WAITING_FOLLOWUP_LEAD_TEXT


async def set_followup_lead_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохраняет текст follow-up lead и запрашивает кнопку 1."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("❌ Текст не может быть пустым. Отправьте текст еще раз.")
        return AdminButtonStates.WAITING_FOLLOWUP_LEAD_TEXT
    
    context.user_data["followup_lead_text"] = text
    
    await update.message.reply_text(
        "✅ Текст сохранен!\n\n"
        "Теперь отправьте **текст первой кнопки** (например, название тарифа).\n\n"
        "Если вы хотите пропустить эту кнопку, отправьте один дефис: `-`",
        parse_mode=ParseMode.MARKDOWN,
    )
    return AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN1_TEXT


async def _process_button_text(
    update: Update,
    state_text: str,
    next_state_url: AdminButtonStates,
    storage_key: str,
):
    text = update.message.text.strip()
    if text == "-":
        update.message.text = ""  # для последующей логики
        text = ""
    context = update._bot._application.context_types.context  # not used, avoid


async def set_followup_lead_btn1_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Текст кнопки 1."""
    text = update.message.text.strip()
    if text == "-":
        text = ""
    context.user_data["followup_lead_btn1_text"] = text
    await update.message.reply_text(
        "Теперь отправьте **ссылку для первой кнопки** "
        "(или `-`, чтобы пропустить эту кнопку).",
        parse_mode=ParseMode.MARKDOWN,
    )
    return AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN1_URL


async def set_followup_lead_btn1_url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """URL кнопки 1."""
    url = update.message.text.strip()
    if url == "-":
        url = ""
    elif url and not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text(
            "❌ Неверный формат ссылки. Отправьте полную ссылку (http:// или https://) "
            "или `-`, чтобы пропустить кнопку."
        )
        return AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN1_URL
    context.user_data["followup_lead_btn1_url"] = url
    
    await update.message.reply_text(
        "Теперь отправьте **текст второй кнопки** (или `-`, чтобы пропустить).",
        parse_mode=ParseMode.MARKDOWN,
    )
    return AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN2_TEXT


async def set_followup_lead_btn2_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "-":
        text = ""
    context.user_data["followup_lead_btn2_text"] = text
    await update.message.reply_text(
        "Теперь отправьте **ссылку для второй кнопки** "
        "(или `-`, чтобы пропустить эту кнопку).",
        parse_mode=ParseMode.MARKDOWN,
    )
    return AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN2_URL


async def set_followup_lead_btn2_url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if url == "-":
        url = ""
    elif url and not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text(
            "❌ Неверный формат ссылки. Отправьте полную ссылку (http:// или https://) "
            "или `-`, чтобы пропустить кнопку."
        )
        return AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN2_URL
    context.user_data["followup_lead_btn2_url"] = url
    
    await update.message.reply_text(
        "Теперь отправьте **текст третьей кнопки** (или `-`, чтобы пропустить).",
        parse_mode=ParseMode.MARKDOWN,
    )
    return AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN3_TEXT


async def set_followup_lead_btn3_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "-":
        text = ""
    context.user_data["followup_lead_btn3_text"] = text
    await update.message.reply_text(
        "Теперь отправьте **ссылку для третьей кнопки** "
        "(или `-`, чтобы пропустить эту кнопку).",
        parse_mode=ParseMode.MARKDOWN,
    )
    return AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN3_URL


async def set_followup_lead_btn3_url_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финальный шаг — URL третьей кнопки и сохранение всех настроек."""
    telegram_id = update.effective_user.id
    
    if not is_admin(telegram_id):
        await update.message.reply_text("❌ У вас нет прав доступа.")
        return ConversationHandler.END
    
    url = update.message.text.strip()
    if url == "-":
        url = ""
    elif url and not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text(
            "❌ Неверный формат ссылки. Отправьте полную ссылку (http:// или https://) "
            "или `-`, чтобы пропустить кнопку."
        )
        return AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN3_URL
    context.user_data["followup_lead_btn3_url"] = url
    
    text = context.user_data.get("followup_lead_text", "")
    btn1_text = context.user_data.get("followup_lead_btn1_text", "")
    btn1_url = context.user_data.get("followup_lead_btn1_url", "")
    btn2_text = context.user_data.get("followup_lead_btn2_text", "")
    btn2_url = context.user_data.get("followup_lead_btn2_url", "")
    btn3_text = context.user_data.get("followup_lead_btn3_text", "")
    btn3_url = context.user_data.get("followup_lead_btn3_url", "")
    
    if not text:
        await update.message.reply_text(
            "❌ Ошибка: текст сообщения потерян. Попробуйте еще раз с /set_followup_lead."
        )
        return ConversationHandler.END
    
    await set_followup_lead_settings(
        text=text,
        btn1_text=btn1_text,
        btn1_url=btn1_url,
        btn2_text=btn2_text,
        btn2_url=btn2_url,
        btn3_text=btn3_text,
        btn3_url=btn3_url,
        updated_by=telegram_id,
    )
    
    # Чистим временные данные
    for key in [
        "followup_lead_text",
        "followup_lead_btn1_text",
        "followup_lead_btn1_url",
        "followup_lead_btn2_text",
        "followup_lead_btn2_url",
        "followup_lead_btn3_text",
        "followup_lead_btn3_url",
    ]:
        context.user_data.pop(key, None)
    
    await update.message.reply_text(
        "✅ **Follow-up для подписавшихся обновлён!**",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_welcome_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает краткую сводку и кнопку «Изменить», которая запускает тот же поток, что и /set_welcome."""
    query = update.callback_query
    await query.answer()
    
    telegram_id = query.from_user.id
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    
    try:
        current = await get_welcome_settings()
        link_status = "задана" if current.get("link") else "не задана"
        message = (
            "💬 **НАСТРОЙКИ ПРИВЕТСТВИЯ**\n\n"
            f"**Текст кнопки:** {current['button_text']}\n"
            f"**Ссылка:** {link_status}\n\n"
            "Нажмите кнопку ниже, чтобы изменить текст приветствия, кнопку и ссылку."
        )
    except Exception as e:
        logger.error(f"Error loading welcome settings: {e}")
        message = (
            "💬 **НАСТРОЙКИ ПРИВЕТСТВИЯ**\n\n"
            "Нажмите кнопку ниже, чтобы задать приветствие и кнопку."
        )
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Изменить приветствие", callback_data="admin:start_set_welcome")],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin:back")],
        ]),
    )


async def start_set_welcome_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point из админ-меню: тот же поток, что и /set_welcome."""
    query = update.callback_query
    await query.answer()
    
    telegram_id = query.from_user.id
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return ConversationHandler.END
    
    message = (
        "💬 **НАСТРОЙКА ПРИВЕТСТВЕННОГО СООБЩЕНИЯ**\n\n"
        "Шаг 1. Отправьте **текст приветствия**, который будет показываться при входе в бота.\n\n"
        "Шаг 2. Затем бот попросит **текст кнопки**.\n"
        "Шаг 3. После этого бот попросит **ссылку на лид-магнит**.\n\n"
        "_Используйте /cancel для отмены._"
    )
    
    await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN)
    return AdminButtonStates.WAITING_WELCOME_TEXT


async def admin_followup_lost_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран настроек follow-up для неподписавшихся: краткая сводка и кнопка «Изменить»."""
    query = update.callback_query
    await query.answer()
    telegram_id = query.from_user.id
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    try:
        current_text = await get_followup_lost_text()
        status = "задан" if (current_text and current_text.strip()) else "не задан"
        message = (
            "♻️ **FOLLOW-UP ДЛЯ НЕПОДПИСАВШИХСЯ**\n\n"
            f"Текст сообщения: **{status}**\n\n"
            "Нажмите кнопку ниже, чтобы изменить текст."
        )
    except Exception as e:
        logger.error(f"Error loading followup_lost: {e}")
        message = (
            "♻️ **FOLLOW-UP ДЛЯ НЕПОДПИСАВШИХСЯ**\n\n"
            "Нажмите кнопку ниже, чтобы задать текст сообщения на следующий день."
        )
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Изменить текст", callback_data="admin:start_set_followup_lost")],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin:back")],
        ]),
    )


async def admin_followup_lead_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экран настроек follow-up для подписавшихся: краткая сводка и кнопка «Изменить»."""
    query = update.callback_query
    await query.answer()
    telegram_id = query.from_user.id
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return
    try:
        current = await get_followup_lead_settings()
        text_ok = bool(current.get("text") and current["text"].strip())
        buttons_count = len([b for b in current.get("buttons", []) if b.get("text") or b.get("url")])
        message = (
            "💰 **FOLLOW-UP ДЛЯ ПОДПИСАВШИХСЯ**\n\n"
            f"Текст: **{'задан' if text_ok else 'не задан'}**\n"
            f"Кнопок: **{buttons_count}**\n\n"
            "Нажмите кнопку ниже, чтобы изменить текст и кнопки."
        )
    except Exception as e:
        logger.error(f"Error loading followup_lead: {e}")
        message = (
            "💰 **FOLLOW-UP ДЛЯ ПОДПИСАВШИХСЯ**\n\n"
            "Нажмите кнопку ниже, чтобы задать текст и до 3 кнопок."
        )
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Изменить настройки", callback_data="admin:start_set_followup_lead")],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin:back")],
        ]),
    )


async def start_set_followup_lost_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point из админ-меню: тот же поток, что и /set_followup_lost."""
    query = update.callback_query
    await query.answer()
    telegram_id = query.from_user.id
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return ConversationHandler.END
    message = (
        "♻️ **НАСТРОЙКА FOLLOW-UP ДЛЯ НЕПОДПИСАВШИХСЯ**\n\n"
        "Отправьте **текст сообщения**, которое будет приходить на следующий день тем, "
        "кто нажал на лид-магнит, но так и не подписался на канал.\n\n"
        "_Используйте /cancel для отмены._"
    )
    await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN)
    return AdminButtonStates.WAITING_FOLLOWUP_LOST_TEXT


async def start_set_followup_lead_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point из админ-меню: тот же поток, что и /set_followup_lead."""
    query = update.callback_query
    await query.answer()
    telegram_id = query.from_user.id
    if not is_admin(telegram_id):
        await query.edit_message_text("❌ Нет прав доступа.")
        return ConversationHandler.END
    message = (
        "💰 **НАСТРОЙКА FOLLOW-UP ДЛЯ ПОДПИСАВШИХСЯ**\n\n"
        "Сначала отправьте **продающий текст** сообщения.\n\n"
        "После этого бот по очереди попросит тексты и ссылки для до 3 кнопок.\n\n"
        "_Используйте /cancel для отмены._"
    )
    await query.edit_message_text(message, parse_mode=ParseMode.MARKDOWN)
    return AdminButtonStates.WAITING_FOLLOWUP_LEAD_TEXT


# ==================== REGISTER ADMIN HANDLERS ====================

def register_admin_handlers(application):
    """
    Register admin handlers.

    Args:
        application: Telegram Application instance
    """
    # Admin command
    application.add_handler(CommandHandler("admin", admin_command))
    
    # Admin callbacks
    application.add_handler(CallbackQueryHandler(admin_back_callback, pattern="^admin:back$"))
    application.add_handler(CallbackQueryHandler(admin_commands_callback, pattern="^admin:commands$"))
    application.add_handler(CallbackQueryHandler(admin_button_stats_callback, pattern="^admin:button_stats$"))
    application.add_handler(CallbackQueryHandler(admin_back_callback, pattern="^admin:add_button$"))
    application.add_handler(CallbackQueryHandler(admin_channel_settings_callback, pattern="^admin:channel_settings$"))
    application.add_handler(CallbackQueryHandler(admin_welcome_settings_callback, pattern="^admin:welcome_settings$"))
    application.add_handler(CallbackQueryHandler(admin_followup_lost_settings_callback, pattern="^admin:followup_lost_settings$"))
    application.add_handler(CallbackQueryHandler(admin_followup_lead_settings_callback, pattern="^admin:followup_lead_settings$"))
    application.add_handler(CallbackQueryHandler(admin_toggle_followup_callback, pattern="^admin:toggle_followup$"))
    
    # Channel button management command
    button_management_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("add_button", add_button_command)
        ],
        states={
            AdminButtonStates.WAITING_BUTTON_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_button_text_handler)
            ],
            AdminButtonStates.WAITING_LEAD_MAGNET_TYPE: [
                CallbackQueryHandler(add_button_type_callback, pattern="^button:type:")
            ],
            AdminButtonStates.WAITING_EXTERNAL_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_button_link_handler)
            ],
            AdminButtonStates.WAITING_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_button_channel_handler)
            ],
            AdminButtonStates.WAITING_POST_CONTENT: [
                MessageHandler(filters.TEXT | filters.PHOTO, add_button_post_handler)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_button_command)
        ]
    )
    
    application.add_handler(button_management_conversation)
    
    # Channel settings command
    channel_settings_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("set_channel", set_channel_command)
        ],
        states={
            AdminButtonStates.WAITING_SUBSCRIPTION_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_channel_handler)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_channel_command)
        ]
    )
    
    application.add_handler(channel_settings_conversation)
    
    # Follow-up lost (команда и кнопка в админ-меню)
    followup_lost_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("set_followup_lost", set_followup_lost_command),
            CallbackQueryHandler(start_set_followup_lost_callback, pattern="^admin:start_set_followup_lost$"),
        ],
        states={
            AdminButtonStates.WAITING_FOLLOWUP_LOST_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_followup_lost_text_handler)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_channel_command)
        ],
    )
    application.add_handler(followup_lost_conversation)

    # Follow-up lead (команда и кнопка в админ-меню)
    followup_lead_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("set_followup_lead", set_followup_lead_command),
            CallbackQueryHandler(start_set_followup_lead_callback, pattern="^admin:start_set_followup_lead$"),
        ],
        states={
            AdminButtonStates.WAITING_FOLLOWUP_LEAD_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_followup_lead_text_handler)
            ],
            AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN1_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_followup_lead_btn1_text_handler)
            ],
            AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN1_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_followup_lead_btn1_url_handler)
            ],
            AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN2_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_followup_lead_btn2_text_handler)
            ],
            AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN2_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_followup_lead_btn2_url_handler)
            ],
            AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN3_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_followup_lead_btn3_text_handler)
            ],
            AdminButtonStates.WAITING_FOLLOWUP_LEAD_BTN3_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_followup_lead_btn3_url_handler)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_channel_command)
        ],
    )
    application.add_handler(followup_lead_conversation)

    # Welcome settings command (и кнопка «Изменить приветствие» в админ-меню)
    welcome_settings_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("set_welcome", set_welcome_command),
            CallbackQueryHandler(start_set_welcome_callback, pattern="^admin:start_set_welcome$"),
        ],
        states={
            AdminButtonStates.WAITING_WELCOME_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_welcome_text_handler)
            ],
            AdminButtonStates.WAITING_WELCOME_BUTTON_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_welcome_button_text_handler)
            ],
            AdminButtonStates.WAITING_WELCOME_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_welcome_link_handler)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_channel_command)
        ],
    )
    
    application.add_handler(welcome_settings_conversation)
    
    logger.info("✅ Admin handlers registered")
