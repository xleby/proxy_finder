"""
Bot — обработчик входящих сообщений от пользователей
Автоматически добавляет подписчиков которые написали /start или любое сообщение
"""
import asyncio
import logging
from typing import Optional

from telethon import TelegramClient, events
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate
from telethon.tl.types import User

import config
from modules.subscribers import get_manager

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Стандартные API ключи для ботов
BOT_API_ID = 6
BOT_API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"


class SubscriberBot:
    """
    Бот для автоматического добавления подписчиков.
    
    Команды:
    - /start — начать диалог, добавиться в подписчики
    - /help — справка
    - /status — статус подписки
    """
    
    def __init__(self):
        self.client: TelegramClient = None
        self.subscribers = get_manager()
        self.proxy = self._load_best_proxy()
    
    def _load_best_proxy(self) -> Optional[tuple]:
        """Загружает лучший прокси."""
        try:
            with open(config.BEST_PROXY_FILE, "r", encoding="utf-8") as f:
                line = f.read().strip()
                if line and "|" in line:
                    parts = line.split("|")
                    return (parts[0], int(parts[1]), parts[2])
        except:
            pass
        return config.get_default_proxy()
    
    async def start(self):
        """Запускает бота."""
        logger.info("🤖 Запуск бота подписчиков...")
        
        self.client = TelegramClient(
            "subscriber_bot",
            BOT_API_ID,
            BOT_API_HASH,
            proxy=self.proxy,
            connection=ConnectionTcpMTProxyRandomizedIntermediate if self.proxy else None,
            timeout=config.CONNECT_TIMEOUT
        )
        
        # Регистрируем обработчики
        self.client.add_event_handler(self.handle_new_message, events.NewMessage(pattern='/start'))
        self.client.add_event_handler(self.handle_any_message, events.NewMessage())
        
        await self.client.start(bot_token=config.BOT_TOKEN)
        
        me = await self.client.get_me()
        logger.info(f"✅ Бот запущен: @{me.username}")
        logger.info(f"📬 Ссылка для подписки: https://t.me/{me.username}")
        
        # Отправляем приветственное сообщение владельцу
        await self.send_welcome_to_owner(me.username)
        
        await self.client.run_until_disconnected()
    
    async def send_welcome_to_owner(self, bot_username: str):
        """Отправляет приветственное сообщение владельцу."""
        try:
            message = (
                f"✅ <b>Бот подписчиков запущен!</b>\n\n"
                f"🤖 Бот: @{bot_username}\n"
                f"🔗 Ссылка: https://t.me/{bot_username}\n\n"
                f"Отправьте эту ссылку знакомым чтобы они подписались на уведомления!"
            )
            await self.client.send_message(config.YOUR_CHAT_ID, message, parse_mode='html')
            logger.info("Приветственное сообщение отправлено владельцу")
        except Exception as e:
            logger.error(f"Ошибка отправки приветствия: {e}")
    
    async def handle_new_message(self, event):
        """Обработчик команды /start."""
        user = event.sender
        user_id = user.id
        
        # Добавляем подписчика
        is_new = self.subscribers.add_subscriber(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name
        )
        
        if is_new:
            response = (
                f"🎉 <b>Добро пожаловать!</b>\n\n"
                f"Вы подписались на уведомления о новых MTProto прокси!\n\n"
                f"📬 Когда система найдёт хороший прокси, вы получите уведомление.\n"
                f"⚡ Пинг будет указан в сообщении.\n\n"
                f"<i>Владелец: @{(await self.client.get_entity(config.YOUR_CHAT_ID)).username}</i>"
            )
        else:
            response = (
                f"✅ <b>Вы уже подписаны!</b>\n\n"
                f"Следующее уведомление придёт когда система найдёт новые прокси."
            )
        
        await event.respond(response, parse_mode='html')
        logger.info(f"Пользователь {user.first_name} (@{user.username}) добавился в подписчики")
    
    async def handle_any_message(self, event):
        """Обработчик любых сообщений (для добавления подписчиков)."""
        user = event.sender
        user_id = user.id
        
        # Добавляем подписчика если ещё не добавлен
        is_new = self.subscribers.add_subscriber(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name
        )
        
        if is_new:
            logger.info(f"Новый подписчик из сообщения: {user.first_name} (@{user.username})")
        
        # Если это не команда /start, отвечаем
        if not event.message.text or not event.message.text.startswith('/start'):
            response = (
                f"👋 Привет, {user.first_name}!\n\n"
                f"Вы подписаны на уведомления о прокси.\n\n"
                f"Используйте /start чтобы подтвердить подписку."
            )
            await event.respond(response, parse_mode='html')


async def main():
    if not config.is_configured():
        logger.error("Не заполнен .env файл!")
        return
    
    bot = SubscriberBot()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
