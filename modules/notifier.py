"""
Notifier — отправка уведомлений от БОТА через MTProto прокси (Telethon)
Использует стандартные API ключи для ботов (api_id=6)
Поддерживает рассылку всем подписчикам
"""
import asyncio
import logging
from typing import Optional, List

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

import config
from modules.checker import CheckResult
from modules.subscribers import get_manager

logger = logging.getLogger(__name__)

# Стандартные API ключи для ботов
BOT_API_ID = 6
BOT_API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"


class Notifier:
    """
    Модуль отправки уведомлений от БОТА через MTProto прокси.
    
    Атрибуты:
        client: TelegramClient для отправки
        chat_id: ID чата для уведомлений (владелец)
        bot_token: Токен бота
        subscribers: Менеджер подписчиков
    """
    
    def __init__(self, chat_id: Optional[int] = None, bot_token: Optional[str] = None):
        self.owner_chat_id = chat_id or config.YOUR_CHAT_ID
        self.bot_token = bot_token or config.BOT_TOKEN
        self.client: Optional[TelegramClient] = None
        self._client_owned = False
        self.subscribers = get_manager()
    
    def _load_best_proxy(self) -> Optional[tuple]:
        """Загружает лучший прокси для подключения."""
        try:
            with open(config.BEST_PROXY_FILE, "r", encoding="utf-8") as f:
                line = f.read().strip()
                if line and "|" in line:
                    parts = line.split("|")
                    return (parts[0], int(parts[1]), parts[2])
        except:
            pass
        return config.get_default_proxy()
    
    async def _create_client(self) -> TelegramClient:
        """Создаёт клиента бота с использованием лучшего прокси."""
        proxy = self._load_best_proxy()
        
        if proxy:
            logger.info(f"Бот подключается через прокси: {proxy[0]}:{proxy[1]}")
            return TelegramClient(
                "bot_session",
                BOT_API_ID,
                BOT_API_HASH,
                proxy=proxy,
                connection=ConnectionTcpMTProxyRandomizedIntermediate,
                timeout=config.CONNECT_TIMEOUT
            )
        else:
            logger.warning("Нет прокси, прямое подключение")
            return TelegramClient(
                "bot_session",
                BOT_API_ID,
                BOT_API_HASH
            )
    
    async def connect(self):
        """Подключает бота к Telegram."""
        if self.client is None:
            self.client = await self._create_client()
            self._client_owned = True
        
        if not self.client.is_connected():
            await self.client.connect()
        
        # Авторизуемся как бот
        if not await self.client.is_user_authorized():
            await self.client.start(bot_token=self.bot_token)
            logger.info(f"Бот авторизован: @{(await self.client.get_me()).username}")
    
    async def disconnect(self):
        """Отключает бота."""
        if self.client and self._client_owned:
            await self.client.disconnect()
            self.client = None
            self._client_owned = False
    
    async def send_message(self, text: str, parse_mode: str = "html", chat_id: Optional[int] = None):
        """
        Отправляет сообщение в чат.
        
        Args:
            text: Текст сообщения
            parse_mode: Режим парсинга (html, markdown)
            chat_id: ID получателя (по умолчанию владелец)
        """
        await self.connect()
        
        target_chat_id = chat_id or self.owner_chat_id
        
        try:
            await self.client.send_message(
                target_chat_id,
                text,
                parse_mode=parse_mode
            )
            logger.info(f"Сообщение отправлено в {target_chat_id}")
            self.subscribers.increment_messages(target_chat_id)
        except FloodWaitError as e:
            logger.warning(f"FloodWait: ждём {e.seconds} секунд")
            await asyncio.sleep(e.seconds)
            await self.send_message(text, parse_mode, chat_id)
        except Exception as e:
            logger.error(f"Ошибка отправки в {target_chat_id}: {e}")
    
    async def broadcast_message(self, text: str, parse_mode: str = "html") -> int:
        """
        Рассылает сообщение всем подписчикам.
        
        Args:
            text: Текст сообщения
            parse_mode: Режим парсинга
        
        Returns:
            Количество успешных отправок
        """
        subscriber_ids = self.subscribers.get_all_ids()
        success_count = 0
        
        logger.info(f"Рассылка {len(subscriber_ids)} подписчикам...")
        
        for user_id in subscriber_ids:
            try:
                await self.send_message(text, parse_mode, chat_id=user_id)
                success_count += 1
                await asyncio.sleep(0.5)  # Пауза для избежания flood
            except Exception as e:
                logger.error(f"Не удалось отправить {user_id}: {e}")
        
        return success_count
    
    async def notify_new_best(self, result: CheckResult, broadcast: bool = False):
        """
        Уведомление о новом лучшем прокси.
        
        Args:
            result: Результат проверки прокси
            broadcast: Если True, отправлять всем подписчикам (используется в broadcast_to_subscribers)
        """
        if broadcast:
            return  # Не отправляем, это делает broadcast_to_subscribers
        
        # Создаём MTProto ссылку
        proxy_url = f"tg://proxy?server={result.host}&port={result.port}&secret=ee{result.secret}"
        
        text = (
            f"🌟 <b>НОВЫЙ ЛУЧШИЙ ПРОКСИ!</b>\n\n"
            f"⚡ <b>Пинг:</b> {result.latency_ms} мс\n"
            f"🔗 <b>Ссылка:</b> <a href='{proxy_url}'>Подключиться</a>\n\n"
            f"<code>{result.host}:{result.port}</code>"
        )
        await self.send_message(text)
    
    async def notify_good_proxy(self, result: CheckResult, broadcast: bool = False):
        """
        Уведомление о хорошем прокси.
        
        Args:
            result: Результат проверки прокси
            broadcast: Если True, отправлять всем подписчикам (используется в broadcast_to_subscribers)
        """
        if broadcast:
            return  # Не отправляем, это делает broadcast_to_subscribers
        
        proxy_url = f"tg://proxy?server={result.host}&port={result.port}&secret=ee{result.secret}"
        
        text = (
            f"✅ <b>Хороший прокси</b>\n\n"
            f"⚡ <b>Пинг:</b> {result.latency_ms} мс\n"
            f"🔗 <a href='{proxy_url}'>Подключиться</a>\n\n"
            f"<code>{result.host}:{result.port}</code>"
        )
        await self.send_message(text)
    
    async def notify_scrape_result(self, count: int):
        """Уведомление о результатах скрапинга."""
        if count == 0:
            text = "⚠️ <b>Скрапинг завершён</b>\n\nПрокси не найдены."
        else:
            text = (
                f"📥 <b>Скрапинг завершён</b>\n\n"
                f"Найдено прокси: <b>{count}</b>\n"
                "Отправляем на проверку..."
            )
        await self.send_message(text)
    
    async def notify_check_result(
        self,
        new_best: Optional[CheckResult],
        good_proxies: list[CheckResult]
    ):
        """
        Уведомление о результатах проверки.
        Отправляет владельцу и всем подписчикам.
        """
        # Сначала отправляем владельцу
        if new_best:
            await self.notify_new_best(new_best, broadcast=False)
        
        # Отправляем первые 5 хороших прокси владельцу
        for result in good_proxies[:5]:
            if result != new_best:
                await self.notify_good_proxy(result, broadcast=False)
        
        # Теперь рассылаем всем подписчикам
        await self.broadcast_to_subscribers(new_best, good_proxies)
    
    async def broadcast_to_subscribers(
        self,
        new_best: Optional[CheckResult],
        good_proxies: list[CheckResult]
    ):
        """
        Рассылает уведомления всем подписчикам.
        """
        subscriber_ids = self.subscribers.get_all_ids()
        
        if not subscriber_ids:
            logger.info("Нет подписчиков для рассылки")
            return
        
        logger.info(f"Рассылка подписчикам ({len(subscriber_ids)} чел)...")
        
        # Формируем сообщения
        messages = []
        
        if new_best:
            proxy_url = f"tg://proxy?server={new_best.host}&port={new_best.port}&secret=ee{new_best.secret}"
            text = (
                f"🌟 <b>НОВЫЙ ЛУЧШИЙ ПРОКСИ!</b>\n\n"
                f"⚡ <b>Пинг:</b> {new_best.latency_ms} мс\n"
                f"🔗 <a href='{proxy_url}'>Подключиться</a>\n\n"
                f"<code>{new_best.host}:{new_best.port}</code>"
            )
            messages.append(text)
        
        # Хорошие прокси (до 5)
        for result in good_proxies[:5]:
            if result != new_best:
                proxy_url = f"tg://proxy?server={result.host}&port={result.port}&secret=ee{result.secret}"
                text = (
                    f"✅ <b>Хороший прокси</b>\n\n"
                    f"⚡ <b>Пинг:</b> {result.latency_ms} мс\n"
                    f"🔗 <a href='{proxy_url}'>Подключиться</a>\n\n"
                    f"<code>{result.host}:{result.port}</code>"
                )
                messages.append(text)
        
        # Отправляем каждое сообщение всем подписчикам
        for text in messages:
            await self.broadcast_message(text)
        
        logger.info(f"Рассылка завершена. Охват: {len(subscriber_ids)} подписчиков")
    
    async def notify_error(self, error: str):
        """Уведомление об ошибке."""
        text = f"❌ <b>Ошибка</b>\n\n{error}"
        await self.send_message(text)
    
    async def run(self, new_best: Optional[CheckResult] = None, good_proxies: list[CheckResult] = None):
        """
        Запускает отправку уведомлений.
        
        Args:
            new_best: Новый лучший прокси (или None)
            good_proxies: Список хороших прокси
        """
        logger.info("=== ЗАПУСК NOTIFIER (BOT) ===")
        
        if good_proxies is None:
            good_proxies = []
        
        await self.connect()
        
        try:
            await self.notify_check_result(new_best, good_proxies)
        finally:
            await self.disconnect()
        
        logger.info("Notifier завершил работу")


# Для автономного запуска (тест)
if __name__ == "__main__":
    if not config.is_configured():
        logger.error("Не заполнен .env файл!")
        exit(1)
    
    # Тестовое уведомление
    notifier = Notifier()
    
    test_result = CheckResult(
        host="test.example.com",
        port=8080,
        secret="test1234567890abcdef",
        url="tg://proxy?server=test.example.com&port=8080&secret=ee...",
        is_working=True,
        latency_ms=123.45
    )
    
    asyncio.run(notifier.run(new_best=test_result, good_proxies=[test_result]))
