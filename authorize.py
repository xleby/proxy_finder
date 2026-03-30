"""
Первичная авторизация пользователя для скрапера
Бот не требует авторизации — используется токен
"""
import asyncio
from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

import config


async def main():
    print("🔐 Авторизация для MTPROTO HUNTER V2")
    
    # Загружаем прокси
    proxy = config.get_default_proxy()
    
    if not proxy:
        print("⚠️ Нет прокси в .env, пробуем прямое подключение")
    
    client = TelegramClient(
        "scraper_session",
        config.API_ID,
        config.API_HASH,
        proxy=proxy,
        connection=ConnectionTcpMTProxyRandomizedIntermediate if proxy else None,
        timeout=config.CONNECT_TIMEOUT
    )
    
    await client.connect()
    
    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"✅ Уже авторизован: {me.first_name} (@{me.username or 'no username'})")
    else:
        print("📲 Отправляю код на ваш номер Telegram...")
        await client.send_code_request(config.PHONE)
        print(f"Введите код из Telegram для {config.PHONE}:")
        code = input("> ")
        
        try:
            await client.sign_in(config.PHONE, code)
            print("✅ Авторизация успешна!")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    await client.disconnect()


if __name__ == "__main__":
    if not config.is_configured():
        print("❌ Заполните .env файл!")
        exit(1)
    
    asyncio.run(main())
