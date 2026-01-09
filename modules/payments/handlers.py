"""
Handlers for Lead Magnet Bot.
Handles subscription checks and link distribution.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from database.database import get_session
from .subscription import check_channel_subscription, get_or_create_user
from .messages import FREE_ACCESS_CHANNEL
from .keyboards import get_free_access_keyboard

logger = logging.getLogger(__name__)


async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки "✅ Я подписался".
    
    Проверяет подписку пользователя на канал и выдает ссылку если подписан.
    """
    query = update.callback_query
    telegram_id = update.effective_user.id

    try:
        await query.answer("Проверяем подписку...")
    except Exception as e:
        logger.error(f"Error answering callback query: {e}")

    try:
        async with get_session() as session:
            # Проверяем подписку
            try:
                is_subscribed = await check_channel_subscription(context.bot, telegram_id)
            except Exception as e:
                logger.error(f"Error checking channel subscription: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                await query.edit_message_text(
                    "❌ Ошибка при проверке подписки. Попробуйте позже.",
                    reply_markup=get_free_access_keyboard()
                )
                return

            # Если пользователь не подписан - просим подписаться
            if not is_subscribed:
                message = """
❌ **ПОДПИСКА НЕ НАЙДЕНА**

Пожалуйста:
1. 📢 Подпишитесь на канал @TaktikaKutuzova
2. ✅ Нажмите "Я подписался" еще раз для проверки
"""
                try:
                    await query.edit_message_text(message, reply_markup=get_free_access_keyboard())
                except Exception as edit_error:
                    if "not modified" not in str(edit_error).lower():
                        logger.error(f"Error editing message: {edit_error}")
                return

            # Пользователь подписан - проверяем, пришел ли через кнопку канала
            channel_button_link = context.user_data.get('channel_button_link')
            channel_button_type = context.user_data.get('channel_button_type')
            
            if channel_button_link:
                # Пользователь пришел через кнопку канала - выдаем ссылку
                if channel_button_type == "external":
                    # Внешняя ссылка - показываем кнопку со ссылкой
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔗 Получить доступ", url=channel_button_link)]
                    ])
                    success_message = """
✅ **ПОДПИСКА ПОДТВЕРЖДЕНА!**

Ваша ссылка готова! Нажмите на кнопку ниже, чтобы получить доступ.
"""
                else:
                    # Доступ к боту - просто подтверждаем
                    keyboard = InlineKeyboardMarkup([])
                    success_message = """
✅ **ПОДПИСКА ПОДТВЕРЖДЕНА!**

Доступ к боту предоставлен!
"""
                
                try:
                    await query.edit_message_text(
                        success_message,
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
                    # Очищаем данные о кнопке после выдачи ссылки
                    context.user_data.pop('channel_button_link', None)
                    context.user_data.pop('channel_button_type', None)
                    context.user_data.pop('channel_button_id', None)
                    logger.info(f"✅ Link issued to user {telegram_id}: {channel_button_link}, type: {channel_button_type}")
                except Exception as e:
                    logger.error(f"Error sending success message: {e}")
            else:
                # Обычная проверка подписки (не через кнопку канала)
                await query.edit_message_text(
                    "✅ **ПОДПИСКА ПОДТВЕРЖДЕНА!**\n\n"
                    "Спасибо за подписку!",
                    parse_mode="Markdown"
                )

    except Exception as e:
        logger.error(f"Unexpected error in check_subscription_callback: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        try:
            await query.edit_message_text(
                "❌ Произошла ошибка при проверке подписки. Попробуйте позже.",
                reply_markup=get_free_access_keyboard()
            )
        except Exception as e2:
            if "not modified" not in str(e2).lower():
                logger.error(f"Error sending error message: {e2}")


def register_subscription_handlers(application):
    """Register subscription handlers."""
    application.add_handler(CallbackQueryHandler(
        check_subscription_callback,
        pattern="^payment:check_subscription$"
    ))
    logger.info("✅ Subscription handlers registered")
