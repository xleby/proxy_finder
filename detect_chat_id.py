"""
Определяет твой Chat ID через Telethon.
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")

PROXY_HOST = os.getenv("DEFAULT_PROXY_HOST", "")
PROXY_PORT = os.getenv("DEFAULT_PROXY_PORT", "")
PROXY_SECRET = os.getenv("DEFAULT_PROXY_SECRET", "")

async def main():
    print("=" * 70)
    print("Chat ID Detector")
    print("=" * 70)
    
    client = TelegramClient(
        session='detect_session',
        api_id=API_ID,
        api_hash=API_HASH,
        proxy=(PROXY_HOST, int(PROXY_PORT), PROXY_SECRET),
        connection=ConnectionTcpMTProxyRandomizedIntermediate,
    )
    
    try:
        print("Подключаюсь...")
        await client.start(phone=PHONE)
        
        me = await client.get_me()
        print(f"\n✅ Твой аккаунт: {me.first_name} @{me.username or 'no username'}")
        print(f"\n📱 Твой Chat ID: {me.id}")
        print(f"\n💾 Сохраняю в .env...")
        
        # Читаем .env
        with open(".env", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Заменяем Chat ID
        import re
        content = re.sub(
            r'YOUR_CHAT_ID=\d+',
            f'YOUR_CHAT_ID={me.id}',
            content
        )
        
        # Сохраняем
        with open(".env", "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"✅ Готово! YOUR_CHAT_ID={me.id} записан в .env")
        print("\nТеперь запусти: python main.py --all --notify")
        
        # Чистим сессию
        await client.disconnect()
        for f in ['detect_session.session', 'detect_session.session-journal']:
            try:
                os.remove(f)
            except:
                pass
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")

asyncio.run(main())
