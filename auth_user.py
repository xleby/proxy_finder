"""Однократная интерактивная авторизация user-аккаунта через MTProto прокси.
Прокси для авторизации читается из .env (DEFAULT_PROXY_HOST/PORT/SECRET).
"""
import asyncio, os
from dotenv import load_dotenv
load_dotenv()
from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

def normalize_secret(secret: str) -> str:
    if secret[:2] in ("ee", "dd"):
        secret = secret[2:]
    hex_part = ""
    for char in secret:
        if char in "0123456789abcdefABCDEF":
            hex_part += char
        else:
            break
    return hex_part[:32]

async def auth():
    proxy_host = os.getenv("DEFAULT_PROXY_HOST")
    proxy_port = os.getenv("DEFAULT_PROXY_PORT")
    proxy_secret = os.getenv("DEFAULT_PROXY_SECRET")

    if not proxy_host or not proxy_port or not proxy_secret:
        print("❌ Настрой DEFAULT_PROXY_HOST, DEFAULT_PROXY_PORT, DEFAULT_PROXY_SECRET в .env")
        return

    proxy_secret = normalize_secret(proxy_secret)

    client = TelegramClient(
        'main_session',
        int(os.getenv('API_ID')),
        os.getenv('API_HASH'),
        proxy=(proxy_host, int(proxy_port), proxy_secret),
        connection=ConnectionTcpMTProxyRandomizedIntermediate,
    )
    await client.start(phone=os.getenv('PHONE'))
    me = await client.get_me()
    print(f'✅ Авторизован: {me.first_name} (@{me.username or "no username"})')
    await client.disconnect()

asyncio.run(auth())
