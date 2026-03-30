"""
StabilityChecker — модуль проверки прокси на стабильность
Проверяет работает ли прокси стабильно в течение нескольких попыток
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

import config

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class StabilityResult:
    """Результат проверки стабильности."""
    host: str
    port: int
    secret: str
    url: str
    is_stable: bool
    success_rate: float  # Процент успешных подключений (0-100)
    avg_latency_ms: float  # Средний пинг
    attempts: int  # Количество попыток
    successful: int  # Успешных попыток


class StabilityChecker:
    """
    Модуль проверки прокси на стабильность.
    
    Атрибуты:
        attempts: Количество попыток подключения (по умолчанию 3)
        delay: Задержка между попытками в секундах (по умолчанию 2)
        timeout: Таймаут одного подключения (по умолчанию 10)
        min_success_rate: Минимальный процент успеха для стабильности (по умолчанию 66%)
    """
    
    def __init__(
        self,
        attempts: int = 3,
        delay: float = 2.0,
        timeout: int = 10,
        min_success_rate: float = 66.0
    ):
        self.attempts = attempts
        self.delay = delay
        self.timeout = timeout
        self.min_success_rate = min_success_rate
    
    async def check_proxy_stability(
        self,
        host: str,
        port: int,
        secret: str,
        url: str = ""
    ) -> StabilityResult:
        """
        Проверяет прокси на стабильность.
        
        Args:
            host: Хост прокси
            port: Порт прокси
            secret: Secret прокси
            url: Исходная ссылка
        
        Returns:
            StabilityResult с результатом проверки
        """
        successful = 0
        latencies = []
        
        logger.debug(f"Проверка стабильности {host}:{port} ({self.attempts} попыток)...")
        
        for i in range(self.attempts):
            try:
                client = TelegramClient(
                    f"stability_check_{i}",
                    config.API_ID,
                    config.API_HASH,
                    proxy=(host, port, secret),
                    connection=ConnectionTcpMTProxyRandomizedIntermediate,
                    timeout=self.timeout
                )
                
                start_time = time.perf_counter()
                
                await asyncio.wait_for(client.connect(), timeout=self.timeout)
                
                if client.is_connected():
                    await asyncio.wait_for(client.get_me(), timeout=self.timeout)
                    
                    end_time = time.perf_counter()
                    latency = (end_time - start_time) * 1000
                    latencies.append(latency)
                    successful += 1
                    logger.debug(f"  Попытка {i+1}: ✅ {latency:.0f} мс")
                else:
                    logger.debug(f"  Попытка {i+1}: ❌ Не подключился")
                    
            except Exception as e:
                logger.debug(f"  Попытка {i+1}: ❌ {type(e).__name__}")
            
            finally:
                try:
                    await client.disconnect()
                except:
                    pass
            
            # Задержка между попытками (кроме последней)
            if i < self.attempts - 1:
                await asyncio.sleep(self.delay)
        
        # Вычисляем процент успеха
        success_rate = (successful / self.attempts) * 100
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        # Определяем стабильность
        is_stable = success_rate >= self.min_success_rate
        
        result = StabilityResult(
            host=host,
            port=port,
            secret=secret,
            url=url,
            is_stable=is_stable,
            success_rate=success_rate,
            avg_latency_ms=avg_latency,
            attempts=self.attempts,
            successful=successful
        )
        
        status = "✅ СТАБИЛЬНЫЙ" if is_stable else "❌ НЕСТАБИЛЬНЫЙ"
        logger.info(f"{status} {host}:{port} | {success_rate:.0f}% | {avg_latency:.0f} мс")
        
        return result
    
    async def check_batch(
        self,
        proxies: List[dict],
        max_concurrent: int = 3
    ) -> List[StabilityResult]:
        """
        Проверяет пачку прокси на стабильность.
        
        Args:
            proxies: Список прокси для проверки
            max_concurrent: Максимум одновременных проверок
        
        Returns:
            Список результатов
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def check_with_semaphore(proxy: dict) -> StabilityResult:
            async with semaphore:
                return await self.check_proxy_stability(
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
                processed.append(StabilityResult(
                    host=proxy["host"],
                    port=proxy["port"],
                    secret=proxy["secret"],
                    url=proxy.get("url", ""),
                    is_stable=False,
                    success_rate=0,
                    avg_latency_ms=0,
                    attempts=self.attempts,
                    successful=0
                ))
            else:
                processed.append(result)
        
        return processed


async def filter_stable_proxies(
    proxies: List[dict],
    checker: Optional[StabilityChecker] = None
) -> Tuple[List[dict], List[dict]]:
    """
    Фильтрует прокси оставляя только стабильные.
    
    Args:
        proxies: Список прокси для проверки
        checker: Экземпляр StabilityChecker (или создастся новый)
    
    Returns:
        (stable_proxies, unstable_proxies) — кортеж из двух списков
    """
    if not checker:
        checker = StabilityChecker()
    
    logger.info(f"Проверка {len(proxies)} прокси на стабильность...")
    
    results = await checker.check_batch(proxies)
    
    stable = []
    unstable = []
    
    for result in results:
        proxy = {
            "host": result.host,
            "port": result.port,
            "secret": result.secret,
            "url": result.url
        }
        
        if result.is_stable:
            stable.append(proxy)
        else:
            unstable.append(proxy)
    
    logger.info(f"Стабильных: {len(stable)}, Нестабильных: {len(unstable)}")
    
    return stable, unstable


# Для автономного запуска
if __name__ == "__main__":
    if not config.is_configured():
        logger.error("Не заполнен .env файл!")
        exit(1)
    
    # Тест
    async def main():
        checker = StabilityChecker(attempts=3, delay=2)
        
        # Пример проверки
        result = await checker.check_proxy_stability(
            "65.109.215.115",
            8443,
            "104462821249bd7ac519130220c25d09"
        )
        
        print(f"\nРезультат: {result}")
    
    asyncio.run(main())
