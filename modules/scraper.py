"""
Scraper — мониторинг Telegram каналов и сбор MTProto прокси
Использует best_proxy.txt / good_proxies.txt для подключения
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import Message

import config
from utils.normalizer import extract_proxy_links, proxy_to_url

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class Scraper:
    """
    Модуль сбора прокси из Telegram каналов.
    
    Атрибуты:
        client: TelegramClient для подключения
        channels: Список каналов для мониторинга
        messages_limit: Количество сообщений для проверки в каждом канале
    """
    
    def __init__(
        self,
        client: Optional[TelegramClient] = None,
        channels: Optional[list[str]] = None,
        messages_limit: Optional[int] = None
    ):
        self.client = client
        self.channels = channels or config.CHANNELS
        self.messages_limit = messages_limit or config.MESSAGES_LIMIT
        self._client_owned = False
    
    def _load_proxy_chain(self) -> list[tuple]:
        """
        Загружает цепочку прокси для подключения.
        Порядок: best_proxy.txt -> good_proxies.txt -> config default
        """
        proxies = []
        
        # 1. Лучший прокси
        try:
            with open(config.BEST_PROXY_FILE, "r", encoding="utf-8") as f:
                line = f.read().strip()
                if line and "|" in line:
                    parts = line.split("|")
                    host, port, secret = parts[0], int(parts[1]), parts[2]
                    proxies.append((host, port, secret))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Ошибка чтения best_proxy.txt: {e}")
        
        # 2. Хорошие прокси
        try:
            with open(config.GOOD_PROXIES_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and "|" in line:
                        parts = line.split("|")
                        if len(parts) >= 3:
                            host, port, secret = parts[0], int(parts[1]), parts[2]
                            if (host, port, secret) not in proxies:
                                proxies.append((host, port, secret))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Ошибка чтения good_proxies.txt: {e}")
        
        # 3. Прокси из конфига
        default_proxy = config.get_default_proxy()
        if default_proxy and default_proxy not in proxies:
            proxies.append(default_proxy)
        
        return proxies
    
    async def _create_client(self) -> TelegramClient:
        """
        Создаёт клиента с использованием цепочки прокси.
        """
        from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate
        
        proxies = self._load_proxy_chain()
        
        if not proxies:
            logger.warning("Нет доступных прокси, используем прямое подключение")
            client = TelegramClient(
                "scraper_session",
                config.API_ID,
                config.API_HASH,
                timeout=config.CONNECT_TIMEOUT
            )
            await asyncio.wait_for(client.connect(), timeout=15)
            return client
        
        # Пробуем прокси по очереди (максимум 3 попытки)
        max_attempts = min(3, len(proxies))
        for i in range(max_attempts):
            proxy = proxies[i]
            client = None
            try:
                logger.info(f"Попытка подключения через прокси {i+1}/{max_attempts}: {proxy[0]}:{proxy[1]}")
                client = TelegramClient(
                    "scraper_session",
                    config.API_ID,
                    config.API_HASH,
                    proxy=proxy,
                    connection=ConnectionTcpMTProxyRandomizedIntermediate,
                    timeout=10  # Короткий таймаут для быстрой проверки
                )
                await asyncio.wait_for(client.connect(), timeout=15)
                if await client.is_user_authorized():
                    logger.info(f"Успешное подключение через {proxy[0]}:{proxy[1]}")
                    return client
                else:
                    logger.warning(f"Не авторизован, пробуем другой прокси")
            except asyncio.TimeoutError:
                logger.warning(f"Таймаут подключения к {proxy[0]}:{proxy[1]}")
            except Exception as e:
                logger.warning(f"Прокси {proxy[0]}:{proxy[1]} не работает: {e}")
            
            # Отключаем только если не вернули клиента
            if client:
                try:
                    await client.disconnect()
                except:
                    pass
        
        # Если все прокси не работали
        raise ConnectionError("Не удалось подключиться через доступные прокси")
    
    async def connect(self):
        """Подключает клиента к Telegram."""
        if self.client is not None and self.client.is_connected():
            return
        
        try:
            self.client = await self._create_client()
            self._client_owned = True
        except ConnectionError as e:
            logger.error(f"Ошибка подключения: {e}")
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка подключения: {e}")
            raise
        
        if not await self.client.is_user_authorized():
            logger.warning("Требуется авторизация! Введите код из Telegram.")
            await self.client.send_code_request(config.PHONE)
            code = input("Введите код из Telegram: ")
            await self.client.sign_in(config.PHONE, code)
    
    async def disconnect(self):
        """Отключает клиента."""
        if self.client and self._client_owned:
            await self.client.disconnect()
            self.client = None
            self._client_owned = False
    
    async def scrape_channel(self, channel: str) -> list[dict]:
        """
        Собирает прокси из одного канала.
        
        Args:
            channel: Имя канала (@channel)
        
        Returns:
            Список найденных прокси
        """
        proxies = []
        
        try:
            entity = await self.client.get_entity(channel)
            logger.info(f"Сканирование канала {channel}...")
            
            messages = await self.client.get_messages(
                entity,
                limit=self.messages_limit
            )
            
            for msg in messages:
                if not msg.text:
                    continue
                
                # Извлекаем прокси из текста
                found = extract_proxy_links(msg.text)
                proxies.extend(found)
                
                # Если есть медиа с текстом
                if msg.message:
                    found = extract_proxy_links(msg.message)
                    proxies.extend(found)
            
            logger.info(f"Найдено {len(proxies)} прокси в {channel}")
            
        except FloodWaitError as e:
            logger.warning(f"FloodWait: ждём {e.seconds} секунд")
            await asyncio.sleep(e.seconds)
            return await self.scrape_channel(channel)
        except Exception as e:
            logger.error(f"Ошибка сканирования {channel}: {e}")
        
        return proxies
    
    async def scrape_all(self) -> list[dict]:
        """
        Собирает прокси из всех каналов.
        
        Returns:
            Список всех найденных прокси (без дубликатов)
        """
        all_proxies = []
        seen_urls = set()
        
        await self.connect()
        
        for channel in self.channels:
            proxies = await self.scrape_channel(channel)
            
            for proxy in proxies:
                if proxy["url"] not in seen_urls:
                    seen_urls.add(proxy["url"])
                    all_proxies.append(proxy)
            
            # Пауза между каналами для избежания flood
            await asyncio.sleep(1)
        
        await self.disconnect()
        
        logger.info(f"Всего найдено уникальных прокси: {len(all_proxies)}")
        return all_proxies
    
    def save_to_queue(self, proxies: list[dict]):
        """
        Сохраняет прокси в queue.txt для проверки.
        
        Args:
            proxies: Список прокси для сохранения
        """
        # Загружаем существующие
        existing_urls = set()
        try:
            with open(config.QUEUE_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if "|" in line:
                        parts = line.strip().split("|")
                        if len(parts) >= 4:
                            existing_urls.add(parts[3])  # url
        except FileNotFoundError:
            pass
        
        # Добавляем новые
        new_count = 0
        with open(config.QUEUE_FILE, "a", encoding="utf-8") as f:
            for proxy in proxies:
                if proxy["url"] not in existing_urls:
                    f.write(
                        f"{proxy['host']}|{proxy['port']}|{proxy['secret']}|{proxy['url']}\n"
                    )
                    new_count += 1
        
        logger.info(f"Добавлено {new_count} новых прокси в {config.QUEUE_FILE}")
    
    async def run(self):
        """
        Запускает скрапер: собирает прокси и сохраняет в queue.txt
        """
        logger.info("=== ЗАПУСК SCRAPER ===")
        proxies = await self.scrape_all()
        
        if proxies:
            self.save_to_queue(proxies)
            logger.info(f"Скрапер завершил работу. Найдено {len(proxies)} прокси.")
        else:
            logger.warning("Прокси не найдены.")
        
        return proxies


# Для автономного запуска
if __name__ == "__main__":
    if not config.is_configured():
        logger.error("Не заполнен .env файл!")
        exit(1)
    
    scraper = Scraper()
    asyncio.run(scraper.run())
