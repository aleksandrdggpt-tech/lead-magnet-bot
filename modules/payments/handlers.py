"""
Handlers for Lead Magnet Bot.
Handles subscription checks, link distribution, welcome flow and follow-ups.
"""

import logging
from datetime import datetime, time as dtime, timedelta, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from database.database import get_session
from database import ChannelButtonClick
from .subscription import (
    check_channel_subscription,
    get_or_create_user,
    get_subscription_channel,
)
from .messages import get_free_access_message
from .keyboards import get_free_access_keyboard
from .settings import get_welcome_settings
from config import Config

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
            # Создаем/обновляем пользователя и логируем нажатие кнопки проверки подписки
            user = await get_or_create_user(
                telegram_id,
                session,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name,
            )
            click = ChannelButtonClick(
                user_id=user.id,
                telegram_id=telegram_id,
                button_id=None,
                source="payment_check_subscription",
                post_id=None,
            )
            session.add(click)
            await session.commit()
            
            # Получаем канал для проверки
            channel_username = await get_subscription_channel()
            
            # Проверяем подписку
            try:
                is_subscribed = await check_channel_subscription(context.bot, telegram_id, channel_username)
            except Exception as e:
                logger.error(f"Error checking channel subscription: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                await query.edit_message_text(
                    "❌ Ошибка при проверке подписки. Попробуйте позже.",
                    reply_markup=get_free_access_keyboard(channel_username)
                )
                return

            # Если пользователь не подписан - просим подписаться
            if not is_subscribed:
                message = f"""
❌ **ПОДПИСКА НЕ НАЙДЕНА**

Пожалуйста:
1. 📢 Подпишитесь на канал {channel_username}
2. ✅ Нажмите "Я подписался" еще раз для проверки
"""
                try:
                    await query.edit_message_text(message, reply_markup=get_free_access_keyboard(channel_username))
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
        # Получаем канал для fallback
        try:
            channel_username = await get_subscription_channel()
            await query.edit_message_text(
                "❌ Произошла ошибка при проверке подписки. Попробуйте позже.",
                reply_markup=get_free_access_keyboard(channel_username)
            )
        except Exception as e2:
            if "not modified" not in str(e2).lower():
                logger.error(f"Error sending error message: {e2}")


def register_subscription_handlers(application):
    """Register subscription handlers."""
    application.add_handler(
        CallbackQueryHandler(
            check_subscription_callback,
            pattern="^payment:check_subscription$",
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            welcome_get_checklist_callback,
            pattern="^welcome:get_checklist$",
        )
    )
    logger.info("✅ Subscription handlers registered")


async def welcome_get_checklist_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """
    Обработчик кнопки приветственного сообщения "Получить чек-лист".

    Проверяет подписку и выдает ссылку на чек-лист, если пользователь подписан.
    """
    query = update.callback_query
    telegram_id = update.effective_user.id

    try:
        await query.answer("Проверяем подписку...")
    except Exception as e:
        logger.error(f"Error answering callback query (welcome): {e}")

    try:
        # Получаем канал и настройки приветствия
        channel_username = await get_subscription_channel()
        welcome = await get_welcome_settings()

        # Без ссылки на чек-лист нет смысла продолжать
        if not welcome["link"]:
            await query.edit_message_text(
                "❌ Ссылка на чек-лист не настроена. Обратитесь к администратору."
            )
            return

        # Логируем пользователя и нажатие кнопки, а также планируем follow-up
        async with get_session() as session:
            user = await get_or_create_user(
                telegram_id,
                session,
                username=update.effective_user.username,
                first_name=update.effective_user.first_name,
            )
            click = ChannelButtonClick(
                user_id=user.id,
                telegram_id=telegram_id,
                button_id=None,
                source="welcome_get_checklist",
                post_id=None,
            )
            session.add(click)
            await session.commit()

        schedule_lead_followup(context, telegram_id)

        # Проверяем подписку
        try:
            is_subscribed = await check_channel_subscription(
                context.bot, telegram_id, channel_username
            )
        except Exception as e:
            logger.error(f"Error checking channel subscription (welcome): {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            await query.edit_message_text(
                "❌ Ошибка при проверке подписки. Попробуйте позже.",
                reply_markup=get_free_access_keyboard(channel_username),
            )
            return

        if not is_subscribed:
            # Пользователь не подписан - просим подписаться
            message = f"""
❌ **ПОДПИСКА НЕ НАЙДЕНА**

Пожалуйста:
1. 📢 Подпишитесь на канал {channel_username}
2. ✅ Нажмите "Я подписался" еще раз для проверки
"""
            try:
                await query.edit_message_text(
                    message,
                    reply_markup=get_free_access_keyboard(channel_username),
                )
            except Exception as edit_error:
                if "not modified" not in str(edit_error).lower():
                    logger.error(
                        f"Error editing message (welcome not subscribed): {edit_error}"
                    )
            return

        # Пользователь подписан - выдаем ссылку на чек-лист
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔗 Получить чек-лист", url=welcome["link"])]]
        )
        success_message = """
✅ **ПОДПИСКА ПОДТВЕРЖДЕНА!**

Ваш чек-лист готов. Нажмите на кнопку ниже, чтобы получить доступ.
"""
        try:
            await query.edit_message_text(
                success_message,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            logger.info(
                f"✅ Welcome checklist link issued to user {telegram_id}: {welcome['link']}"
            )
        except Exception as e:
            logger.error(f"Error sending welcome success message: {e}")

    except Exception as e:
        logger.error(f"Unexpected error in welcome_get_checklist_callback: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        try:
            channel_username = await get_subscription_channel()
            await query.edit_message_text(
                "❌ Произошла ошибка при проверке подписки. Попробуйте позже.",
                reply_markup=get_free_access_keyboard(channel_username),
            )
        except Exception as e2:
            if "not modified" not in str(e2).lower():
                logger.error(f"Error sending error message (welcome): {e2}")


def schedule_lead_followup(context: ContextTypes.DEFAULT_TYPE, telegram_id: int) -> None:
    """
    Планирует follow-up сообщение на следующий день в заданный час.
    """
    try:
        job_queue = context.application.job_queue

        now = datetime.now(timezone.utc)
        target_time = dtime(hour=Config.FOLLOWUP_HOUR, minute=0, second=0)
        target = now.replace(
            hour=target_time.hour,
            minute=target_time.minute,
            second=target_time.second,
            microsecond=0,
        )
        if target <= now:
            target += timedelta(days=1)

        job_queue.run_once(
            send_lead_followup_job,
            when=target,
            chat_id=telegram_id,
            name=f"lead_followup_{telegram_id}_{int(now.timestamp())}",
        )
        logger.info(f"Lead follow-up scheduled for user {telegram_id} at {target.isoformat()}")
    except Exception as e:
        logger.error(f"Error scheduling lead follow-up for user {telegram_id}: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")


async def send_lead_followup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Follow-up сообщение через день после нажатия на кнопку лид-магнита.

    Два сценария:
    1) Пользователь подписан на канал — отправляем продающий текст + 3 кнопки оплаты.
    2) Не подписан — повторно предлагаем получить лид-магнит с кнопкой, как в приветствии.
    """
    telegram_id = context.job.chat_id

    try:
        channel_username = await get_subscription_channel()
        welcome = await get_welcome_settings()

        # Проверяем подписку
        try:
            is_subscribed = await check_channel_subscription(
                context.bot, telegram_id, channel_username
            )
        except Exception as e:
            logger.error(f"Error checking subscription in follow-up for {telegram_id}: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return

        if is_subscribed:
            # Сценарий 1: подписан — продающее сообщение + 3 кнопки оплаты
            payment_buttons = []
            if Config.PAYMENT_URL_1:
                payment_buttons.append(
                    [InlineKeyboardButton("💳 Тариф 1", url=Config.PAYMENT_URL_1)]
                )
            if Config.PAYMENT_URL_2:
                payment_buttons.append(
                    [InlineKeyboardButton("💳 Тариф 2", url=Config.PAYMENT_URL_2)]
                )
            if Config.PAYMENT_URL_3:
                payment_buttons.append(
                    [InlineKeyboardButton("💳 Тариф 3", url=Config.PAYMENT_URL_3)]
                )

            if not payment_buttons:
                logger.warning(
                    "No PAYMENT_URL_* configured, skipping follow-up payment message"
                )
                return

            keyboard = InlineKeyboardMarkup(payment_buttons)
            text = (
                "🔥 **Как использовать чек-лист, чтобы выжать максимум из отдела продаж**\n\n"
                "За последний день ты уже получил чек-лист. Следующий логичный шаг — "
                "внедрить его с нашей помощью и получить результат быстрее:\n\n"
                "1️⃣ Индивидуальный разбор и план внедрения\n"
                "2️⃣ Сопровождение по шагам\n"
                "3️⃣ Ответы на вопросы и разбор кейсов\n\n"
                "Выбери удобный формат работы ниже 👇"
            )

            await context.bot.send_message(
                chat_id=telegram_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            logger.info(f"Sent subscribed follow-up to user {telegram_id}")
        else:
            # Сценарий 2: не подписан — повторное предложение получить лид-магнит
            reminder_text = (
                "👋 Привет! Вчера ты начинал получать чек-лист отдела продаж, но не завершил шаг "
                "с подпиской на канал.\n\n"
                "Подпишись на канал, чтобы открыть доступ к материалу, и нажми кнопку ниже, "
                "чтобы получить чек-лист."
            )
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            welcome["button_text"],
                            callback_data="welcome:get_checklist",
                        )
                    ]
                ]
            )

            await context.bot.send_message(
                chat_id=telegram_id,
                text=reminder_text,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            logger.info(f"Sent unsubscribed follow-up to user {telegram_id}")
    except Exception as e:
        logger.error(f"Unexpected error in send_lead_followup_job for {telegram_id}: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
