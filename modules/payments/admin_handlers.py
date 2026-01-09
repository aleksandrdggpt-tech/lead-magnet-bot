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
    
    await update.message.reply_text(
        message,
        reply_markup=get_admin_panel_keyboard(),
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
    
    await query.edit_message_text(
        message,
        reply_markup=get_admin_panel_keyboard(),
        parse_mode=ParseMode.MARKDOWN
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
`/add_button` - Создать пост с кнопкой
`/set_channel` - Настроить канал для проверки подписки

**Действия через меню:**
• ➕ Создать пост с кнопкой
• 📊 Статистика по кнопкам
• ⚙️ Настройки канала
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
        ],
        per_message=False
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
        ],
        per_message=False
    )
    
    application.add_handler(channel_settings_conversation)
    
    logger.info("✅ Admin handlers registered")
