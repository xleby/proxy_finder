"""
Validator — модуль комплексной проверки прокси на стабильность
Включает 3 этапа:
1. Jitter Check (серийный пинг)
2. Keep-Alive (удержание сессии)
3. Heavy Load (загрузка тяжёлого объекта)
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from statistics import mean, stdev
from typing import List, Optional, Tuple

from telethon import TelegramClient
from telethon.errors import ConnectionResetError, IncompleteReadError
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate
from telethon.tl.functions.channels import GetMessagesRequest
from telethon.tl.types import InputChannel

import config

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Результат комплексной проверки прокси."""
    host: str
    port: int
    secret: str
    url: str
    
    # Общие результаты
    is_valid: bool
    total_score: float  # 0-100
    
    # Этап 1: Jitter Check
    jitter_passed: bool
    avg_latency_ms: float
    jitter_percent: float
    ping_attempts: int
    
    # Этап 2: Keep-Alive
    keepalive_passed: bool
    session_duration_sec: float
    
    # Этап 3: Heavy Load
    heavy_load_passed: bool
    download_speed_kbps: float
    
    # Детали ошибок
    errors: List[str]


class ProxyValidator:
    """
    Модуль комплексной валидации прокси.
    
    Атрибуты:
        ping_attempts: Количество замеров пинга (по умолчанию 5)
        ping_delay: Задержка между замерами в секундах (по умолчанию 1)
        keepalive_wait: Время ожидания для Keep-Alive теста (по умолчанию 15)
        jitter_threshold: Максимальный допустимый jitter в % (по умолчанию 30)
        min_download_speed: Мин. скорость загрузки в Кбит/с (по умолчанию 50)
    """
    
    def __init__(
        self,
        ping_attempts: int = 5,
        ping_delay: float = 1.0,
        keepalive_wait: float = 15.0,
        jitter_threshold: float = 30.0,
        min_download_speed: float = 50.0
    ):
        self.ping_attempts = ping_attempts
        self.ping_delay = ping_delay
        self.keepalive_wait = keepalive_wait
        self.jitter_threshold = jitter_threshold
        self.min_download_speed = min_download_speed
    
    async def _create_client(self, proxy: tuple) -> TelegramClient:
        """Создаёт клиента для проверки прокси."""
        return TelegramClient(
            f"validator_{int(time.time())}",
            config.API_ID,
            config.API_HASH,
            proxy=proxy,
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            timeout=30
        )
    
    async def _jitter_check(
        self,
        client: TelegramClient,
        host: str,
        port: int
    ) -> Tuple[bool, float, float, int]:
        """
        Этап 1: Серийный пинг (Jitter Check).
        
        Делает 5-10 запросов get_me() с интервалом 1 секунда.
        Считает среднее отклонение (jitter).
        
        Returns:
            (passed, avg_latency, jitter_percent, attempts)
        """
        latencies = []
        logger.info(f"  📍 Этап 1: Jitter Check ({self.ping_attempts} замеров)...")
        
        for i in range(self.ping_attempts):
            try:
                start = time.perf_counter()
                await client.get_me()
                end = time.perf_counter()
                
                latency = (end - start) * 1000
                latencies.append(latency)
                logger.debug(f"    Замер {i+1}: {latency:.0f} мс")
                
            except Exception as e:
                logger.debug(f"    Замер {i+1}: ❌ {type(e).__name__}")
            
            # Задержка между замерами (кроме последнего)
            if i < self.ping_attempts - 1:
                await asyncio.sleep(self.ping_delay)
        
        if len(latencies) < 3:
            logger.warning(f"  ❌ Jitter Check провален: мало успешных замеров ({len(latencies)}/{self.ping_attempts})")
            return False, 0, 100, len(latencies)
        
        # Считаем статистику
        avg_latency = mean(latencies)
        jitter = stdev(latencies) if len(latencies) > 1 else 0
        jitter_percent = (jitter / avg_latency) * 100 if avg_latency > 0 else 0
        
        passed = jitter_percent <= self.jitter_threshold
        
        logger.info(f"    Средний пинг: {avg_latency:.0f} мс, Jitter: {jitter_percent:.1f}%")
        
        if passed:
            logger.info(f"  ✅ Jitter Check пройден")
        else:
            logger.info(f"  ❌ Jitter Check провален (jitter > {self.jitter_threshold}%)")
        
        return passed, avg_latency, jitter_percent, len(latencies)
    
    async def _keepalive_check(
        self,
        client: TelegramClient,
        host: str,
        port: int
    ) -> Tuple[bool, float]:
        """
        Этап 2: Проверка удержания сессии (Keep-Alive).
        
        Подключается, ждёт 15 секунд, затем пробует сделать запрос.
        
        Returns:
            (passed, session_duration)
        """
        logger.info(f"  🔗 Этап 2: Keep-Alive ({self.keepalive_wait} сек ожидания)...")
        
        start_time = time.time()
        
        try:
            # Ждём указанное время
            await asyncio.sleep(self.keepalive_wait)
            
            # Пробуем сделать запрос
            await client.get_me()
            
            session_duration = time.time() - start_time
            
            logger.info(f"  ✅ Keep-Alive пройден (сессия {session_duration:.1f} сек)")
            return True, session_duration
            
        except (ConnectionResetError, IncompleteReadError, asyncio.TimeoutError) as e:
            session_duration = time.time() - start_time
            logger.info(f"  ❌ Keep-Alive провален: {type(e).__name__} через {session_duration:.1f} сек")
            return False, session_duration
            
        except Exception as e:
            session_duration = time.time() - start_time
            logger.info(f"  ❌ Keep-Alive провален: {e}")
            return False, session_duration
    
    async def _heavy_load_check(
        self,
        client: TelegramClient,
        host: str,
        port: int
    ) -> Tuple[bool, float]:
        """
        Этап 3: Загрузка тяжёлого объекта.
        
        Пробует получить информацию о канале и последние сообщения.
        Это создаёт нагрузку на соединение.
        
        Returns:
            (passed, download_speed_kbps)
        """
        logger.info(f"  📦 Этап 3: Heavy Load (загрузка данных)...")
        
        try:
            # Получаем информацию о канале (создаёт нагрузку)
            start_time = time.time()
            
            # Пробуем получить популярный канал для теста
            entity = await client.get_entity("@telegram")
            
            # Получаем последние сообщения с медиа
            messages = await client.get_messages(entity, limit=10)
            
            # Считаем объём данных (примерно)
            total_size = 0
            for msg in messages:
                if msg.media:
                    # Приблизительный размер медиа
                    if hasattr(msg.media, 'photo'):
                        total_size += 50 * 1024  # 50KB для фото
                    if hasattr(msg.media, 'document'):
                        total_size += 100 * 1024  # 100KB для документов
            
            elapsed = time.time() - start_time
            
            # Скорость в Кбит/с
            download_speed = (total_size * 8) / (elapsed * 1000) if elapsed > 0 else 0
            
            passed = download_speed >= self.min_download_speed
            
            logger.info(f"    Загружено {total_size / 1024:.1f} KB за {elapsed:.2f} сек")
            logger.info(f"    Скорость: {download_speed:.1f} Кбит/с")
            
            if passed:
                logger.info(f"  ✅ Heavy Load пройден")
            else:
                logger.info(f"  ❌ Heavy Load провален (скорость < {self.min_download_speed} Кбит/с)")
            
            return passed, download_speed
            
        except Exception as e:
            logger.info(f"  ❌ Heavy Load провален: {e}")
            return False, 0
    
    async def validate_proxy(
        self,
        host: str,
        port: int,
        secret: str,
        url: str = ""
    ) -> ValidationResult:
        """
        Комплексная проверка прокси.
        
        Args:
            host: Хост прокси
            port: Порт прокси
            secret: Secret прокси
            url: Исходная ссылка
        
        Returns:
            ValidationResult с результатами всех этапов
        """
        proxy = (host, port, secret)
        errors = []
        
        logger.info(f"\n🔍 Валидация прокси {host}:{port}")
        logger.info("=" * 50)
        
        client = None
        
        try:
            # Создаём клиента
            client = await self._create_client(proxy)
            await client.connect()
            
            if not client.is_connected():
                return ValidationResult(
                    host=host, port=port, secret=secret, url=url,
                    is_valid=False, total_score=0,
                    jitter_passed=False, avg_latency_ms=0, jitter_percent=0, ping_attempts=0,
                    keepalive_passed=False, session_duration_sec=0,
                    heavy_load_passed=False, download_speed_kbps=0,
                    errors=["Не удалось подключиться"]
                )
            
            # Этап 1: Jitter Check
            jitter_passed, avg_latency, jitter_percent, ping_attempts = \
                await self._jitter_check(client, host, port)
            
            if not jitter_passed:
                errors.append(f"Jitter {jitter_percent:.1f}% > {self.jitter_threshold}%")
            
            # Этап 2: Keep-Alive
            keepalive_passed, session_duration = \
                await self._keepalive_check(client, host, port)
            
            if not keepalive_passed:
                errors.append("Сессия оборвалась")
            
            # Этап 3: Heavy Load
            heavy_load_passed, download_speed = \
                await self._heavy_load_check(client, host, port)
            
            if not heavy_load_passed:
                errors.append(f"Скорость {download_speed:.1f} < {self.min_download_speed} Кбит/с")
            
            # Подсчёт общего scores
            total_score = 0
            if jitter_passed:
                total_score += 40
            if keepalive_passed:
                total_score += 30
            if heavy_load_passed:
                total_score += 30
            
            is_valid = total_score >= 70  # Минимум 70 баллов для валидности
            
            logger.info("=" * 50)
            logger.info(f"📊 Результат: {total_score}/100 | {'✅ ВАЛИДЕН' if is_valid else '❌ НЕ ВАЛИДЕН'}")
            
            return ValidationResult(
                host=host,
                port=port,
                secret=secret,
                url=url,
                is_valid=is_valid,
                total_score=total_score,
                jitter_passed=jitter_passed,
                avg_latency_ms=avg_latency,
                jitter_percent=jitter_percent,
                ping_attempts=ping_attempts,
                keepalive_passed=keepalive_passed,
                session_duration_sec=session_duration,
                heavy_load_passed=heavy_load_passed,
                download_speed_kbps=download_speed,
                errors=errors
            )
            
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass
    
    async def validate_batch(
        self,
        proxies: List[dict],
        max_concurrent: int = 2
    ) -> List[ValidationResult]:
        """
        Проверяет пачку прокси.
        
        Args:
            proxies: Список прокси для проверки
            max_concurrent: Максимум одновременных проверок
        
        Returns:
            Список результатов
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def validate_with_semaphore(proxy: dict) -> ValidationResult:
            async with semaphore:
                return await self.validate_proxy(
                    proxy["host"],
                    proxy["port"],
                    proxy["secret"],
                    proxy.get("url", "")
                )
        
        tasks = [validate_with_semaphore(p) for p in proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Обрабатываем исключения
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                proxy = proxies[i]
                processed.append(ValidationResult(
                    host=proxy["host"],
                    port=proxy["port"],
                    secret=proxy["secret"],
                    url=proxy.get("url", ""),
                    is_valid=False,
                    total_score=0,
                    jitter_passed=False,
                    avg_latency_ms=0,
                    jitter_percent=0,
                    ping_attempts=0,
                    keepalive_passed=False,
                    session_duration_sec=0,
                    heavy_load_passed=False,
                    download_speed_kbps=0,
                    errors=[str(result)]
                ))
            else:
                processed.append(result)
        
        return processed


async def filter_valid_proxies(
    proxies: List[dict],
    validator: Optional[ProxyValidator] = None,
    min_score: float = 70.0
) -> Tuple[List[dict], List[dict]]:
    """
    Фильтрует прокси оставляя только валидные.
    
    Args:
        proxies: Список прокси для проверки
        validator: Экземпляр ProxyValidator
        min_score: Минимальный score для валидности
    
    Returns:
        (valid_proxies, invalid_proxies)
    """
    if not validator:
        validator = ProxyValidator()
    
    logger.info(f"🔍 Валидация {len(proxies)} прокси...")
    
    results = await validator.validate_batch(proxies)
    
    valid = []
    invalid = []
    
    for result in results:
        proxy = {
            "host": result.host,
            "port": result.port,
            "secret": result.secret,
            "url": result.url
        }
        
        if result.is_valid and result.total_score >= min_score:
            valid.append(proxy)
            logger.info(f"✅ {result.host}:{result.port} | Score: {result.total_score}")
        else:
            invalid.append(proxy)
            logger.info(f"❌ {result.host}:{result.port} | Score: {result.total_score}")
    
    logger.info(f"\nИтого: Валидных: {len(valid)}, Невалидных: {len(invalid)}")
    
    return valid, invalid


# Для автономного запуска
if __name__ == "__main__":
    if not config.is_configured():
        logger.error("Не заполнен .env файл!")
        exit(1)
    
    async def main():
        validator = ProxyValidator(
            ping_attempts=5,
            keepalive_wait=15,
            jitter_threshold=30
        )
        
        # Пример проверки
        result = await validator.validate_proxy(
            "65.109.215.115",
            8443,
            "104462821249bd7ac519130220c25d09"
        )
        
        print(f"\n📊 Результат валидации:")
        print(f"  Score: {result.total_score}/100")
        print(f"  Jitter: {result.jitter_percent:.1f}%")
        print(f"  Keep-Alive: {result.session_duration_sec:.1f} сек")
        print(f"  Download: {result.download_speed_kbps:.1f} Кбит/с")
        print(f"  Ошибки: {result.errors}")
    
    asyncio.run(main())
