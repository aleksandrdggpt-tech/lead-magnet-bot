"""
Subscription logic for Lead Magnet Bot.
Handles channel subscription checks.
"""

import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram.error import BadRequest
from telegram.constants import ChatMemberStatus

from database import User
from database.database import get_session
from config import Config

logger = logging.getLogger(__name__)


async def get_or_create_user(
    telegram_id: int,
    session: AsyncSession,
    username: Optional[str] = None,
    first_name: Optional[str] = None
) -> User:
    """Get existing user or create new one."""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info(f"Created new user: {telegram_id}")

    return user


async def check_channel_subscription(bot, telegram_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на канал.

    Args:
        bot: Экземпляр Telegram бота
        telegram_id: Telegram ID пользователя

    Returns:
        bool: True если пользователь подписан, False иначе
    """
    try:
        # Используем getChatMember для проверки статуса пользователя в канале
        member = await bot.get_chat_member(
            chat_id=Config.CHANNEL_USERNAME,
            user_id=telegram_id
        )

        # Проверяем статус участника
        status = member.status
        
        # Пользователь подписан если статус MEMBER, ADMINISTRATOR или CREATOR
        is_subscribed = status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        ]
        
        logger.info(f"User {telegram_id} subscription status: {status} -> {is_subscribed}")
        return is_subscribed
        
    except BadRequest as e:
        # Если канал недоступен или бот не является администратором
        error_message = str(e).lower()
        if "member list is inaccessible" in error_message:
            logger.warning(f"Channel member list is inaccessible for user {telegram_id}. Bot may not be admin.")
            return False
        logger.error(f"BadRequest checking subscription: {e}")
        return False
    except Exception as e:
        logger.error(f"Error checking channel subscription: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False
