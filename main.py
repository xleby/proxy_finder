"""
MTPROTO HUNTER V2 — точка входа
Координирует работу Scraper, Checker и Notifier
"""
import asyncio
import logging
import signal
import sys
from typing import Optional

import config
from modules.scraper import Scraper
from modules.checker import Checker
from modules.notifier import Notifier

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("hunter.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MTPProtoHunter:
    """
    Основной класс системы поиска прокси.
    
    Координирует работу:
    1. Scraper — сбор прокси из каналов
    2. Checker — проверка прокси с замером пинга
    3. Notifier — отправка уведомлений
    """
    
    def __init__(self):
        self.scraper: Optional[Scraper] = None
        self.checker: Optional[Checker] = None
        self.notifier: Optional[Notifier] = None
        self._shutdown = False
    
    def setup_signal_handlers(self):
        """Настраивает обработчики сигналов для корректного завершения."""
        def handler(sig, frame):
            logger.info("Получен сигнал завершения, останавливаемся...")
            self._shutdown = True
        
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
    
    async def run_cycle(self, notify: bool = True):
        """
        Выполняет один цикл работы: скрапинг → проверка → уведомление.
        
        Args:
            notify: Отправлять ли уведомления
        """
        logger.info("=" * 50)
        logger.info("НОВЫЙ ЦИКЛ РАБОТЫ")
        logger.info("=" * 50)
        
        # 1. Скрапинг
        logger.info("Этап 1: Скрапинг прокси из каналов...")
        self.scraper = Scraper()
        proxies = await self.scraper.run()
        
        if self._shutdown:
            return
        
        if not proxies:
            logger.warning("Прокси не найдены, переходим к следующему циклу")
            return
        
        # 2. Проверка
        logger.info("Этап 2: Проверка прокси...")
        self.checker = Checker()
        new_best, good_proxies = await self.checker.run()
        
        if self._shutdown:
            return
        
        # 3. Уведомление
        if notify and good_proxies:
            logger.info("Этап 3: Отправка уведомлений...")
            self.notifier = Notifier()
            await self.notifier.run(new_best=new_best, good_proxies=good_proxies)
        
        logger.info("=" * 50)
        logger.info(f"ЦИКЛ ЗАВЕРШЁН. Найдено хороших прокси: {len(good_proxies)}")
        logger.info("=" * 50)
    
    async def run_continuous(self, interval_minutes: int = 30):
        """
        Запускает непрерывную работу с указанным интервалом.
        
        Args:
            interval_minutes: Интервал между циклами в минутах
        """
        self.setup_signal_handlers()
        
        logger.info("🚀 ЗАПУСК MTPROTO HUNTER V2")
        logger.info(f"Интервал: {interval_minutes} мин")
        logger.info(f"Каналов для мониторинга: {len(config.CHANNELS)}")
        
        while not self._shutdown:
            try:
                await self.run_cycle(notify=True)
            except Exception as e:
                logger.error(f"Ошибка в цикле: {e}", exc_info=True)
            
            if self._shutdown:
                break
            
            # Ждём следующий цикл
            interval_seconds = interval_minutes * 60
            logger.info(f"Следующий цикл через {interval_minutes} мин...")
            
            # Разбиваем ожидание на интервалы по 1 секунде для быстрого реагирования на сигнал
            for _ in range(interval_seconds):
                if self._shutdown:
                    break
                await asyncio.sleep(1)
        
        logger.info("MTPROTO HUNTER V2 остановлен")
    
    async def run_once(self, notify: bool = True):
        """
        Запускает один цикл работы и завершается.
        
        Args:
            notify: Отправлять ли уведомления
        """
        logger.info("🚀 ЗАПУСК MTPROTO HUNTER V2 (однократный режим)")
        await self.run_cycle(notify=notify)
        logger.info("Работа завершена")


async def main():
    """Точка входа."""
    # Проверка конфигурации
    if not config.is_configured():
        logger.error("❌ Не заполнен .env файл!")
        logger.error("Пожалуйста, укажите API_ID, API_HASH, PHONE, BOT_TOKEN, YOUR_CHAT_ID")
        sys.exit(1)
    
    hunter = MTPProtoHunter()
    
    # Режим работы: однократный или непрерывный
    # Для непрерывного раскомментируйте:
    # await hunter.run_continuous(interval_minutes=30)
    
    # notify=False отключает уведомления (если Bot API недоступен)
    await hunter.run_once(notify=True)


if __name__ == "__main__":
    asyncio.run(main())
