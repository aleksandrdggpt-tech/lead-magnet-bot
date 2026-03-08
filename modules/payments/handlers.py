"""
Handlers for Lead Magnet Bot.
Handles subscription checks, link distribution, welcome flow and follow-ups.
"""

import asyncio
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
from .settings import (
    get_welcome_settings,
    get_followup_enabled,
    get_followup_lost_text,
    get_followup_lead_settings,
    get_followup_texts,
    get_diag_selection_settings,
)
from config import Config

logger = logging.getLogger(__name__)


async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик кнопки "✅ Я подписался".
    Если подписка не найдена (или ошибка): удаляем сообщение, пауза 1 сек, отправляем результат новым сообщением.
    Если подписан: сообщение не трогаем, сразу отправляем результат новым сообщением ниже.
    """
    query = update.callback_query
    telegram_id = update.effective_user.id
    chat_id = query.message.chat_id

    try:
        await query.answer("Проверяем подписку...")
    except Exception as e:
        logger.error(f"Error answering callback query: {e}")

    try:
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
                source="payment_check_subscription",
                post_id=None,
            )
            session.add(click)
            await session.commit()

            channel_username = await get_subscription_channel()

            try:
                is_subscribed = await check_channel_subscription(context.bot, telegram_id, channel_username)
            except Exception as e:
                logger.error(f"Error checking channel subscription: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                try:
                    await query.message.delete()
                except Exception:
                    pass
                await asyncio.sleep(1)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Ошибка при проверке подписки. Попробуйте позже.",
                    reply_markup=get_free_access_keyboard(channel_username),
                )
                return

            if not is_subscribed:
                not_found_text = f"""
❌ **ПОДПИСКА НЕ НАЙДЕНА**

Пожалуйста:
1. 📢 Подпишитесь на канал {channel_username}
2. ✅ Нажмите "Я подписался" еще раз для проверки
"""
                try:
                    await query.message.delete()
                except Exception:
                    pass
                await asyncio.sleep(1)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=not_found_text,
                    reply_markup=get_free_access_keyboard(channel_username),
                    parse_mode="Markdown",
                )
                return

            channel_button_link = context.user_data.get('channel_button_link')
            channel_button_type = context.user_data.get('channel_button_type')

            # Подписан — сценарий другой: не удаляем сообщение, сразу отправляем результат ниже
            if channel_button_link:
                if channel_button_type == "external":
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔗 Получить доступ", url=channel_button_link)]
                    ])
                    success_message = """
✅ **ПОДПИСКА ПОДТВЕРЖДЕНА!**

Ваша ссылка готова! Нажмите на кнопку ниже, чтобы получить доступ.
"""
                else:
                    keyboard = InlineKeyboardMarkup([])
                    success_message = """
✅ **ПОДПИСКА ПОДТВЕРЖДЕНА!**

Доступ к боту предоставлен!
"""
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=success_message,
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )
                context.user_data.pop('channel_button_link', None)
                context.user_data.pop('channel_button_type', None)
                context.user_data.pop('channel_button_id', None)
                logger.info(f"✅ Link issued to user {telegram_id}: {channel_button_link}, type: {channel_button_type}")
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="✅ **ПОДПИСКА ПОДТВЕРЖДЕНА!**\n\nСпасибо за подписку!",
                    parse_mode="Markdown",
                )
                welcome = await get_welcome_settings()
                if welcome.get("link"):
                    keyboard = InlineKeyboardMarkup(
                        [[InlineKeyboardButton(welcome["button_text"], url=welcome["link"])]]
                    )
                    follow_message = """
✅ **ПОДПИСКА ПОДТВЕРЖДЕНА!**

Ваш чек-лист готов. Нажмите на кнопку ниже, чтобы получить доступ.
"""
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=follow_message,
                        reply_markup=keyboard,
                        parse_mode="Markdown",
                    )
                    logger.info(f"Lead magnet message sent to user {telegram_id} after subscription check")

    except Exception as e:
        logger.error(f"Unexpected error in check_subscription_callback: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        try:
            await query.message.delete()
        except Exception:
            pass
        await asyncio.sleep(1)
        try:
            channel_username = await get_subscription_channel()
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Произошла ошибка при проверке подписки. Попробуйте позже.",
                reply_markup=get_free_access_keyboard(channel_username),
            )
        except Exception as e2:
            if "not modified" not in str(e2).lower():
                logger.error(f"Error sending error message: {e2}")


async def followup_choose_diagnostic_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Обработчик кнопки «Выбрать тип диагностики».
    Отправляет сообщение с текстом выбора диагностики и тремя кнопками (текст + url из настроек).
    """
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        logger.error(f"Error answering callback (choose_diagnostic): {e}")

    try:
        settings = await get_diag_selection_settings()
        text = (settings.get("text") or "").strip()
        if not text:
            text = "Выберите тип диагностики:"

        buttons = []
        for key in ("diag1", "diag2", "diag3"):
            diag = settings.get(key) or {}
            btn_text = (diag.get("btn_text") or "").strip()
            url = (diag.get("url") or "").strip()
            if url and btn_text:
                buttons.append([InlineKeyboardButton(btn_text, url=url)])
        keyboard = InlineKeyboardMarkup(buttons) if buttons else None

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        logger.info(f"Sent diag selection to user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error in followup_choose_diagnostic_callback: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Произошла ошибка. Попробуйте позже.",
            )
        except Exception:
            pass


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
    application.add_handler(
        CallbackQueryHandler(
            followup_choose_diagnostic_callback,
            pattern="^followup:choose_diagnostic$",
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

        # Логируем пользователя и нажатие кнопки; планируем follow-up только если включён
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
            if await get_followup_enabled(session):
                schedule_lead_followup_chain(context, telegram_id)

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

        # Пользователь подписан — выдаём ссылку на чек-лист (текст и кнопка из настроек)
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(welcome["button_text"], url=welcome["link"])]]
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


def schedule_lead_followup_chain(
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: int,
) -> None:
    """
    Планирует цепочку из трёх follow-up сообщений: день+1 (fup1), день+2 (fup2), день+3 (fup3).
    """
    try:
        job_queue = context.application.job_queue
        if not job_queue:
            logger.warning("Job queue not available, skip scheduling follow-up chain")
            return

        now = datetime.now(timezone.utc)
        base_time = dtime(hour=Config.FOLLOWUP_HOUR, minute=0, second=0)
        ts = int(now.timestamp())

        for day_offset in (1, 2, 3):
            target = now.replace(
                hour=base_time.hour,
                minute=base_time.minute,
                second=base_time.second,
                microsecond=0,
            ) + timedelta(days=day_offset)
            if target <= now:
                target += timedelta(days=1)

            job_queue.run_once(
                send_lead_followup_job,
                when=target,
                chat_id=telegram_id,
                name=f"lead_followup_{telegram_id}_{day_offset}_{ts}",
                data={"step": day_offset},
            )
            logger.info(
                f"Lead follow-up step {day_offset} scheduled for user {telegram_id} at {target.isoformat()}"
            )
    except Exception as e:
        logger.error(f"Error scheduling follow-up chain for user {telegram_id}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


async def send_lead_followup_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Одно из follow-up сообщений цепочки (шаг 1, 2 или 3).

    Сначала проверяет followup_enabled; затем подписку.
    Подписан: отправляет текст fup1/fup2/fup3 из настроек + кнопку «Выбрать тип диагностики».
    Не подписан: текст fup_lost + кнопка приветствия.
    """
    telegram_id = context.job.chat_id
    job_data = context.job.data or {}
    step = job_data.get("step", 1)

    try:
        async with get_session() as session:
            if not await get_followup_enabled(session):
                logger.info(f"Follow-up disabled, skip job for user {telegram_id}")
                return

        channel_username = await get_subscription_channel()
        welcome = await get_welcome_settings()

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
            texts = await get_followup_texts()
            key = f"fup{step}_text"
            text = (texts.get(key) or "").strip()
            if not text:
                logger.warning(f"No {key} configured, skipping follow-up step {step} for {telegram_id}")
                return

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Выбрать тип диагностики", callback_data="followup:choose_diagnostic")]
            ])
            await context.bot.send_message(
                chat_id=telegram_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            logger.info(f"Sent follow-up step {step} to user {telegram_id}")
        else:
            reminder_text = await get_followup_lost_text()
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        welcome["button_text"],
                        callback_data="welcome:get_checklist",
                    )
                ]
            ])
            await context.bot.send_message(
                chat_id=telegram_id,
                text=reminder_text,
                reply_markup=keyboard,
                parse_mode="Markdown",
            )
            logger.info(f"Sent unsubscribed follow-up step {step} to user {telegram_id}")
    except Exception as e:
        logger.error(f"Unexpected error in send_lead_followup_job for {telegram_id}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
