"""
Конфигурация проекта MTPROTO HUNTER V2
Загрузка переменных окружения и настроек
"""
import os
from dotenv import load_dotenv

# Загружаем .env с перезаписью существующих переменных
load_dotenv(override=True)

# Telegram API
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")

# Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ChatID для уведомлений (целое число!)
YOUR_CHAT_ID = int(os.getenv("YOUR_CHAT_ID", "0"))

# Админы
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip()]

# Прокси по умолчанию (опционально)
DEFAULT_PROXY_HOST = os.getenv("DEFAULT_PROXY_HOST", "")
DEFAULT_PROXY_PORT = os.getenv("DEFAULT_PROXY_PORT", "")
DEFAULT_PROXY_SECRET = os.getenv("DEFAULT_PROXY_SECRET", "")

# Настройки
MESSAGES_LIMIT = int(os.getenv("MESSAGES_LIMIT", "20"))
CHECK_TIMEOUT = int(os.getenv("CHECK_TIMEOUT", "10"))
PING_THRESHOLD = int(os.getenv("PING_THRESHOLD", "250"))

# Список каналов для мониторинга
CHANNELS = [
    "@ProxyMTProto",
    "@MTProto_Proxies_Free",
    "@Proxy_Telegram_MTProto",
    "@MTProto_Proxy_List",
    "@Proxy_MTProto_Telegram",
    "@TeleProxy_New",
]

# Файлы хранения
BEST_PROXY_FILE = "best_proxy.txt"
GOOD_PROXIES_FILE = "good_proxies.txt"
QUEUE_FILE = "queue.txt"

# Таймауты подключения
CONNECT_TIMEOUT = 30
PING_TIMEOUT = 10


def get_default_proxy() -> tuple | None:
    """Возвращает прокси по умолчанию из .env если задан."""
    if DEFAULT_PROXY_HOST and DEFAULT_PROXY_PORT and DEFAULT_PROXY_SECRET:
        return (DEFAULT_PROXY_HOST, int(DEFAULT_PROXY_PORT), DEFAULT_PROXY_SECRET)
    return None


def is_configured() -> bool:
    """Проверяет, заполнены ли обязательные настройки."""
    return bool(API_ID and API_HASH and PHONE and BOT_TOKEN and YOUR_CHAT_ID)
