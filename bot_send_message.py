"""
Отправка сообщения от бота через MTProto прокси.
Использует Telethon для подключения через прокси.
"""

import asyncio
import os
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

# ==================== НАСТРОЙКИ ====================
# Все настройки читаются из .env
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PROXY_HOST = os.getenv("DEFAULT_PROXY_HOST", "")
PROXY_PORT = os.getenv("DEFAULT_PROXY_PORT", "")
PROXY_SECRET = os.getenv("DEFAULT_PROXY_SECRET", "")

# Chat ID — можно использовать @username или числовой ID
YOUR_CHAT_ID = os.getenv("YOUR_CHAT_ID", "")

# Сессия бота
SESSION_NAME = "bot_sender"
# ================================================


def normalize_secret_for_proxy(secret: str) -> str:
    """Нормализует secret до 32 hex-символов (как в main.py)."""
    if secret[:2] in ("ee", "dd"):
        secret = secret[2:]
    hex_part = ""
    for char in secret:
        if char in "0123456789abcdefABCDEF":
            hex_part += char
        else:
            break
    return hex_part[:32]


async def main():
    if not BOT_TOKEN:
        print("❗ ОШИБКА: BOT_TOKEN не настроен!")
        return
    
    print("=" * 70)
    print("Telegram Bot Sender (через MTProto прокси)")
    print("=" * 70)
    print(f"Бот: {BOT_TOKEN.split(':')[0]}:...")
    print(f"Прокси: {PROXY_HOST}:{PROXY_PORT}")
    print(f"Chat ID: {YOUR_CHAT_ID}")
    print("=" * 70)
    print()
    
    # Создаём клиент с прокси
    # Для бота используем bot_token вместо api_id/api_hash
    normalized_secret = normalize_secret_for_proxy(PROXY_SECRET)
    client = TelegramClient(
        session=SESSION_NAME,
        api_id=6,  # Стандартный API ID для ботов
        api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e",
        proxy=(PROXY_HOST, int(PROXY_PORT), normalized_secret),
        connection=ConnectionTcpMTProxyRandomizedIntermediate,
    )
    
    try:
        print("🔌 Подключаюсь к Telegram...")
        await client.start(bot_token=BOT_TOKEN)
        print("✅ Бот подключён!")
        
        # Получаем информацию о боте
        me = await client.get_me()
        print(f"🤖 Бот: @{me.username} ({me.first_name})")
        print()
        
        print("-" * 70)
        
        # Формируем сообщение
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"""
🤖 <b>Сообщение от бота</b>

⏰ Время: {timestamp}
📡 Статус: <b>Работает через MTProto прокси</b>
🔗 Прокси: {PROXY_HOST}:{PROXY_PORT}

Это тестовое сообщение подтверждает что бот работает! ✅
        """.strip()
        
        print(f"📤 Отправляю сообщение в чат {YOUR_CHAT_ID}...")
        
        # Отправляем сообщение
        await client.send_message(YOUR_CHAT_ID, message, parse_mode='html')
        
        print("✅ Сообщение отправлено успешно!")
        print()
        print("Проверь Telegram — должно прийти сообщение от бота.")
        
    except Exception as e:
        print(f"❌ ОШИБКА: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.disconnect()
        # НЕ удаляем сессию
        print()
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
