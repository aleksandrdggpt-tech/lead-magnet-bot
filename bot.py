"""
Lead Magnet Bot - бот для раздачи лид-магнитов через кнопки в канале.

Функционал:
- Создание постов с кнопками в канале (только для админов)
- Проверка подписки на канал перед выдачей ссылки
- Раздача ссылок пользователям, перешедшим по кнопке
- Статистика нажатий на кнопки
"""

import logging
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)
from telegram.constants import ParseMode

from config import Config
from database.database import init_db, close_db, get_session
from database import ChannelButton, ChannelButtonClick
from modules.payments.subscription import (
    get_or_create_user,
    check_channel_subscription,
    get_subscription_channel
)
from modules.payments.messages import get_free_access_message
from modules.payments.keyboards import get_free_access_keyboard
from modules.payments.handlers import register_subscription_handlers
from modules.payments.admin_handlers import register_admin_handlers

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start - проверяет подписку и выдает ссылку."""
    t0 = time.perf_counter()
    telegram_id = update.effective_user.id
    
    # Обработка deep link параметров (для отслеживания нажатий на кнопку в канале)
    start_param = None
    if context.args and len(context.args) > 0:
        start_param = context.args[0]
        logger.info(f"🚀 Команда /start вызвана пользователем {telegram_id} с параметром: {start_param}")
        
        # Если параметр начинается с "channel_" - это нажатие на кнопку в канале
        if start_param.startswith("channel_"):
            try:
                async with get_session() as session:
                    # Получаем или создаем пользователя
                    user = await get_or_create_user(
                        telegram_id,
                        session,
                        username=update.effective_user.username,
                        first_name=update.effective_user.first_name
                    )
                    
                    # Пытаемся найти button_id из параметра (формат: channel_button_123)
                    button_id = None
                    post_id = None
                    button_link = None
                    button_lead_magnet_type = None
                    if start_param.startswith("channel_button_"):
                        try:
                            post_id = int(start_param.replace("channel_button_", ""))
                            # Ищем кнопку по message_id
                            from sqlalchemy import select
                            button_result = await session.execute(
                                select(ChannelButton).where(ChannelButton.message_id == post_id)
                            )
                            found_button = button_result.scalar_one_or_none()
                            if found_button:
                                button_id = found_button.id
                                button_link = found_button.link
                                button_lead_magnet_type = found_button.lead_magnet_type
                                # Сохраняем информацию о кнопке в context для последующей выдачи ссылки
                                context.user_data['channel_button_id'] = button_id
                                context.user_data['channel_button_link'] = button_link
                                context.user_data['channel_button_type'] = button_lead_magnet_type
                                logger.info(f"✅ Сохранена информация о кнопке: button_id={button_id}, link={button_link}, type={button_lead_magnet_type}")
                        except (ValueError, Exception) as e:
                            logger.debug(f"Could not extract button_id from param: {e}")
                    
                    # Сохраняем нажатие на кнопку
                    click = ChannelButtonClick(
                        user_id=user.id,
                        telegram_id=telegram_id,
                        button_id=button_id,
                        source=start_param,
                        post_id=post_id if 'post_id' in locals() else None
                    )
                    session.add(click)
                    await session.commit()
                    logger.info(f"✅ Зафиксировано нажатие на кнопку канала: {start_param} от пользователя {telegram_id}, button_id: {button_id}")
                    
                    # ВАЖНО: Сразу обрабатываем кнопку канала и выходим
                    if button_link:
                        # Получаем канал для проверки
                        channel_username = await get_subscription_channel()
                        
                        # Проверяем подписку сразу
                        try:
                            is_subscribed = await check_channel_subscription(context.bot, telegram_id, channel_username)
                            logger.info(f"🔵 User {telegram_id} subscription status: {is_subscribed}")
                            
                            if is_subscribed:
                                # Пользователь подписан - сразу выдаем ссылку
                                if button_lead_magnet_type == "external":
                                    # Внешняя ссылка - показываем кнопку со ссылкой
                                    keyboard = InlineKeyboardMarkup([
                                        [InlineKeyboardButton("🔗 Получить доступ", url=button_link)]
                                    ])
                                    message = """
✅ **ПОДПИСКА ПОДТВЕРЖДЕНА!**

Ваша ссылка готова! Нажмите на кнопку ниже, чтобы получить доступ.
"""
                                else:
                                    # Доступ к боту - просто подтверждаем
                                    keyboard = InlineKeyboardMarkup([])
                                    message = """
✅ **ПОДПИСКА ПОДТВЕРЖДЕНА!**

Доступ к боту предоставлен!
"""
                                
                                await update.message.reply_text(
                                    message,
                                    reply_markup=keyboard,
                                    parse_mode=ParseMode.MARKDOWN
                                )
                                # Очищаем данные о кнопке после выдачи ссылки
                                context.user_data.pop('channel_button_link', None)
                                context.user_data.pop('channel_button_type', None)
                                context.user_data.pop('channel_button_id', None)
                                logger.info(f"✅ Link issued immediately to subscribed user {telegram_id}: {button_link}, type: {button_lead_magnet_type}")
                                elapsed = int((time.perf_counter() - t0) * 1000)
                                logger.info(f"⏱ /start handled in {elapsed} ms (channel button - subscribed)")
                                return
                            else:
                                # Пользователь не подписан - показываем диалог проверки подписки
                                await update.message.reply_text(
                                    get_free_access_message(channel_username),
                                    reply_markup=get_free_access_keyboard(channel_username),
                                    parse_mode=ParseMode.MARKDOWN
                                )
                                logger.info(f"🔵 User came via channel button but not subscribed, showing subscription check. Link: {button_link}, Type: {button_lead_magnet_type}")
                                elapsed = int((time.perf_counter() - t0) * 1000)
                                logger.info(f"⏱ /start handled in {elapsed} ms (channel button - not subscribed)")
                                return
                        except Exception as e:
                            logger.error(f"❌ Error checking subscription for channel button: {e}")
                            import traceback
                            logger.error(f"Traceback: {traceback.format_exc()}")
                            # В случае ошибки показываем диалог проверки подписки
                            channel_username = await get_subscription_channel()
                            await update.message.reply_text(
                                get_free_access_message(channel_username),
                                reply_markup=get_free_access_keyboard(channel_username),
                                parse_mode=ParseMode.MARKDOWN
                            )
                            elapsed = int((time.perf_counter() - t0) * 1000)
                            logger.info(f"⏱ /start handled in {elapsed} ms (channel button - error)")
                            return
            except Exception as e:
                logger.error(f"❌ Ошибка при сохранении нажатия на кнопку: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
    else:
        logger.info(f"🚀 Команда /start вызвана пользователем {telegram_id}")
    
    # Обычный /start без параметров - просто приветствие
    await update.message.reply_text(
        "👋 Добро пожаловать!\n\n"
        "Этот бот раздает лид-магниты через кнопки в канале.\n\n"
        "Перейдите по кнопке в канале, чтобы получить доступ к материалам.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    elapsed = int((time.perf_counter() - t0) * 1000)
    logger.info(f"⏱ /start handled in {elapsed} ms")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок для предотвращения падения бота."""
    error = context.error
    logger.error(f"Exception while handling an update: {error}", exc_info=error)


def main():
    """Главная функция приложения."""
    logger.info("=" * 80)
    logger.info("🚀 LEAD MAGNET BOT STARTING")
    logger.info("=" * 80)
    
    # Валидация конфигурации
    try:
        Config.validate()
    except ValueError as e:
        logger.critical(f"Configuration error: {e}")
        return
    
    # Инициализация базы данных
    logger.info("🔄 Initializing database...")
    try:
        import asyncio
        asyncio.run(init_db())
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}")
        return
    
    # Создание приложения
    logger.info("🔄 Creating Telegram Application...")
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Регистрация обработчиков
    logger.info("🔄 Registering handlers...")
    
    # Команда /start
    application.add_handler(CommandHandler("start", start_command))
    logger.info("✅ Handler /start registered")
    
    # Обработчики подписки
    register_subscription_handlers(application)
    
    # Админ-панель
    register_admin_handlers(application)
    
    # Глобальный обработчик ошибок
    application.add_error_handler(error_handler)
    
    logger.info("✅ All handlers registered")
    
    # Запуск бота
    logger.info("🚀 Starting bot...")
    logger.info("🔄 Starting polling...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
