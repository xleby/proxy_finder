"""
Checker — независимый модуль проверки MTProto прокси с замером Latency
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

import config

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Результат проверки прокси."""
    host: str
    port: int
    secret: str
    url: str
    is_working: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class Checker:
    """
    Модуль проверки прокси.
    
    Атрибуты:
        timeout: Таймаут проверки в секундах
        ping_threshold: Максимальный пинг для "хорошего" прокси
    """
    
    def __init__(
        self,
        timeout: Optional[int] = None,
        ping_threshold: Optional[int] = None
    ):
        self.timeout = timeout or config.CHECK_TIMEOUT
        self.ping_threshold = ping_threshold or config.PING_THRESHOLD
        self._client: Optional[TelegramClient] = None
    
    async def _create_client(self, proxy: tuple) -> TelegramClient:
        """Создаёт клиента для проверки конкретного прокси."""
        return TelegramClient(
            "checker_session",
            config.API_ID,
            config.API_HASH,
            proxy=proxy,
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            timeout=self.timeout
        )
    
    async def check_proxy(
        self,
        host: str,
        port: int,
        secret: str,
        url: str = ""
    ) -> CheckResult:
        """
        Проверяет один прокси с замером пинга.
        
        Args:
            host: Хост прокси
            port: Порт прокси
            secret: Secret прокси (нормализованный)
            url: Исходная ссылка (для отчёта)
        
        Returns:
            CheckResult с результатом проверки
        """
        proxy = (host, port, secret)
        
        client = None
        start_time = 0
        latency_ms = None
        error = None
        is_working = False
        
        try:
            client = await self._create_client(proxy)
            
            # Замер времени подключения с таймаутом
            start_time = time.perf_counter()
            
            await asyncio.wait_for(
                client.connect(),
                timeout=self.timeout
            )
            
            # Проверяем что клиент подключён
            if not client.is_connected():
                error = "Not connected"
                return CheckResult(
                    host=host, port=port, secret=secret, url=url,
                    is_working=False, latency_ms=None, error=error
                )
            
            # Замер пинга через get_me
            await asyncio.wait_for(
                client.get_me(),
                timeout=self.timeout
            )
            
            end_time = time.perf_counter()
            latency_ms = round((end_time - start_time) * 1000, 2)
            
            is_working = True
            logger.info(f"✓ {host}:{port} | Пинг: {latency_ms} мс")
            
        except asyncio.TimeoutError:
            error = f"Timeout ({self.timeout}s)"
            logger.debug(f"✗ {host}:{port} | {error}")
            
        except FloodWaitError as e:
            error = f"FloodWait: {e.seconds}s"
            logger.warning(f"✗ {host}:{port} | {error}")
            
        except ConnectionRefusedError:
            error = "Connection refused"
            logger.debug(f"✗ {host}:{port} | {error}")
            
        except OSError as e:
            error = f"OS Error: {e}"
            logger.debug(f"✗ {host}:{port} | {error}")
            
        except Exception as e:
            error = str(e) or type(e).__name__
            logger.debug(f"✗ {host}:{port} | {error}")
            
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass
        
        return CheckResult(
            host=host, port=port, secret=secret, url=url,
            is_working=is_working, latency_ms=latency_ms, error=error
        )
    
    async def check_batch(
        self,
        proxies: list[dict],
        max_concurrent: int = 5
    ) -> list[CheckResult]:
        """
        Проверяет пачку прокси параллельно.
        
        Args:
            proxies: Список прокси для проверки
            max_concurrent: Максимум одновременных проверок
        
        Returns:
            Список результатов проверки
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def check_with_semaphore(proxy: dict) -> CheckResult:
            async with semaphore:
                return await self.check_proxy(
                    proxy["host"],
                    proxy["port"],
                    proxy["secret"],
                    proxy.get("url", "")
                )
        
        tasks = [check_with_semaphore(p) for p in proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем исключения
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                proxy = proxies[i]
                processed.append(CheckResult(
                    host=proxy["host"],
                    port=proxy["port"],
                    secret=proxy["secret"],
                    url=proxy.get("url", ""),
                    is_working=False,
                    error=str(result)
                ))
            else:
                processed.append(result)
        
        return processed
    
    def _load_best_proxy(self) -> Optional[tuple]:
        """Загружает лучший прокси из файла."""
        try:
            with open(config.BEST_PROXY_FILE, "r", encoding="utf-8") as f:
                line = f.read().strip()
                if line and "|" in line:
                    parts = line.split("|")
                    return (parts[0], int(parts[1]), parts[2])
        except:
            pass
        return None
    
    def _save_best_proxy(self, result: CheckResult):
        """Сохраняет новый лучший прокси."""
        with open(config.BEST_PROXY_FILE, "w", encoding="utf-8") as f:
            f.write(f"{result.host}|{result.port}|{result.secret}\n")
        logger.info(f"💾 Сохранён новый лучший прокси: {result.host}:{result.port}")
    
    def _save_good_proxy(self, result: CheckResult):
        """Добавляет прокси в список хороших."""
        # Проверяем есть ли уже такой
        existing = set()
        try:
            with open(config.GOOD_PROXIES_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if "|" in line:
                        parts = line.strip().split("|")
                        if len(parts) >= 2:
                            existing.add((parts[0], int(parts[1])))
        except FileNotFoundError:
            pass
        
        if (result.host, result.port) not in existing:
            with open(config.GOOD_PROXIES_FILE, "a", encoding="utf-8") as f:
                f.write(f"{result.host}|{result.port}|{result.secret}|{result.latency_ms}\n")
            logger.info(f"✅ Добавлен в good_proxies: {result.host}:{result.port}")
    
    async def process_queue(self) -> tuple[Optional[CheckResult], list[CheckResult]]:
        """
        Обрабатывает queue.txt: проверяет прокси и обновляет файлы.
        
        Returns:
            (best_proxy_result, good_proxies_results)
            best_proxy_result — новый лучший прокси или None
            good_proxies_results — список хороших прокси
        """
        # Загружаем очередь
        proxies = []
        try:
            with open(config.QUEUE_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and "|" in line:
                        parts = line.split("|")
                        if len(parts) >= 3:
                            proxies.append({
                                "host": parts[0],
                                "port": int(parts[1]),
                                "secret": parts[2],
                                "url": parts[3] if len(parts) > 3 else ""
                            })
        except FileNotFoundError:
            logger.warning(f"{config.QUEUE_FILE} не найден")
            return None, []
        
        if not proxies:
            logger.info("Очередь пуста")
            return None, []
        
        logger.info(f"Проверка {len(proxies)} прокси из очереди...")
        
        # Получаем текущий лучший прокси
        best_current = self._load_best_proxy()
        best_latency = None
        if best_current:
            # Проверяем его актуальный пинг
            result = await self.check_proxy(*best_current)
            if result.is_working:
                best_latency = result.latency_ms
                logger.info(f"Текущий лучший прокси: {best_current[0]}:{best_current[1]} ({best_latency} мс)")
            else:
                logger.warning("Текущий лучший прокси больше не работает")
                best_latency = float('inf')
        else:
            best_latency = float('inf')
        
        # Проверяем все прокси
        results = await self.check_batch(proxies)
        
        new_best = None
        good_results = []
        
        for result in results:
            if not result.is_working:
                continue
            
            # Проверяем если это новый лучший
            if result.latency_ms and result.latency_ms < best_latency:
                logger.info(f"🌟 НОВЫЙ ЛУЧШИЙ! Пинг: {result.latency_ms} мс")
                self._save_best_proxy(result)
                new_best = result
                best_latency = result.latency_ms
                good_results.append(result)
            elif result.latency_ms and result.latency_ms <= self.ping_threshold:
                logger.info(f"✅ Хороший прокси | Пинг: {result.latency_ms} мс")
                self._save_good_proxy(result)
                good_results.append(result)
        
        # Очищаем очередь после проверки
        open(config.QUEUE_FILE, "w").close()
        
        return new_best, good_results
    
    async def run(self):
        """Запускает проверку очереди прокси."""
        logger.info("=== ЗАПУСК CHECKER ===")
        new_best, good_proxies = await self.process_queue()
        
        if new_best:
            logger.info(f"Найден новый лучший прокси: {new_best.host}:{new_best.port} ({new_best.latency_ms} мс)")
        
        logger.info(f"Хороших прокси найдено: {len(good_proxies)}")
        
        return new_best, good_proxies


# Для автономного запуска
if __name__ == "__main__":
    if not config.is_configured():
        logger.error("Не заполнен .env файл!")
        exit(1)
    
    checker = Checker()
    asyncio.run(checker.run())
