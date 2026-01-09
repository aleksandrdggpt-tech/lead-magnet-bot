"""
Конфигурация бота для лид-магнита.
"""

import os
from typing import List
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()


class Config:
    """Класс конфигурации приложения."""

    # Секретные ключи из .env
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
    
    # Список админов (идентификаторы Telegram), через запятую в .env: ADMIN_USER_IDS=123,456
    _ADMIN_IDS_RAW: str = os.getenv('ADMIN_USER_IDS', '')
    ADMIN_USER_IDS: List[int] = []
    if _ADMIN_IDS_RAW:
        try:
            ADMIN_USER_IDS = [int(x.strip()) for x in _ADMIN_IDS_RAW.split(',') if x.strip().isdigit()]
        except Exception:
            ADMIN_USER_IDS = []

    # Канал для проверки подписки
    CHANNEL_USERNAME: str = os.getenv('CHANNEL_USERNAME', '@TaktikaKutuzova')

    @classmethod
    def validate(cls) -> None:
        """Проверяет критичные параметры конфигурации."""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не установлен")
