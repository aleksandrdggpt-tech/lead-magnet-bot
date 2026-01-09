"""
Channel Button Service - управление кнопками в постах канала.

Сервис для добавления кнопок к постам в Telegram каналах.
Генерирует ссылки на бота с отслеживанием нажатий.
"""

import logging
from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class ChannelButtonService:
    """Сервис для работы с кнопками в постах канала."""

    @staticmethod
    def generate_bot_link(bot_username: str, post_id: int = None) -> str:
        """
        Генерирует ссылку на бота с параметром для отслеживания нажатий.
        
        Args:
            bot_username: Имя бота (без @)
            post_id: ID поста (опционально, для аналитики)
        
        Returns:
            Ссылка на бота вида: https://t.me/bot_username?start=channel_button_123
        """
        # Убираем @ если есть
        if bot_username.startswith('@'):
            bot_username = bot_username[1:]
        
        # Формируем параметр
        if post_id:
            param = f"channel_button_{post_id}"
        else:
            param = "channel_button"
        
        return f"https://t.me/{bot_username}?start={param}"

    @staticmethod
    def create_button_keyboard(link: str, button_text: str) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру с одной кнопкой.
        
        Args:
            link: Ссылка (на бота, файл, опрос и т.д.)
            button_text: Текст кнопки
        
        Returns:
            InlineKeyboardMarkup с кнопкой
        """
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(button_text, url=link)]
        ])
        return keyboard

    @staticmethod
    async def publish_post_with_button(
        bot,
        channel_id: str,
        post_content: str,
        button_text: str,
        link: str,
        photo_file_id: Optional[str] = None,
        lead_magnet_type: str = "bot"
    ) -> Optional[int]:
        """
        Публикует новый пост в канале с кнопкой.
        
        Args:
            bot: Экземпляр Telegram бота
            channel_id: ID канала (username или числовой ID)
            post_content: Текст поста
            button_text: Текст кнопки
            link: Ссылка для кнопки
            photo_file_id: File ID изображения (опционально)
            lead_magnet_type: Тип лид-магнита ("bot" или "external")
        
        Returns:
            message_id опубликованного поста или None если ошибка
        """
        try:
            # Создаем клавиатуру с кнопкой
            keyboard = ChannelButtonService.create_button_keyboard(link, button_text)
            
            # Публикуем пост
            if photo_file_id:
                # Используем file_id если есть
                sent_message = await bot.send_photo(
                    chat_id=channel_id,
                    photo=photo_file_id,
                    caption=post_content,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                # Только текст
                sent_message = await bot.send_message(
                    chat_id=channel_id,
                    text=post_content,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            
            logger.info(f"Post published in channel {channel_id} with button, message_id: {sent_message.message_id}, type: {lead_magnet_type}")
            return sent_message.message_id
            
        except TelegramError as e:
            logger.error(f"Telegram error publishing post: {e}")
            return None
        except Exception as e:
            logger.error(f"Error publishing post: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
