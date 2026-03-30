# 🤖 Отправка сообщений от бота через MTProto прокси

**Полное руководство с примерами кода для использования в будущих проектах**

---

## 📋 Проблема

Обычно боты Telegram используют **Bot API** через HTTPS запросы:

```python
# ❌ Стандартный подход (не работает без HTTP прокси)
import requests

BOT_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

response = requests.post(
    url,
    json={"chat_id": 123456789, "text": "Hello!"}
)
```

**Проблема:** `api.telegram.org` заблокирован у многих провайдеров в России. Нужен HTTP прокси, но они часто не работают.

---

## ✅ Решение: Telethon + Bot Token

Используем **Telethon** (User API библиотека) с **бот-токеном** для подключения через **MTProto прокси**.

### Почему это работает:

| Характеристика | Bot API (requests) | Telethon + Bot Token |
|----------------|-------------------|---------------------|
| Подключение | HTTPS к api.telegram.org | MTProto к серверам Telegram |
| Прокси | HTTP/HTTPS (часто не работает) | MTProto (работает!) |
| Блокировки | Затрагивает api.telegram.org | Обходит блокировки |

---

## 🔧 Реализация

### Шаг 1: Установка зависимостей

```bash
pip install telethon>=1.42.0
```

### Шаг 2: Импорт библиотек

```python
import asyncio
from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate
```

### Шаг 3: Настройки

```python
# Токен бота (получить от @BotFather)
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# MTProto прокси (из best_proxy.txt или .env)
PROXY_HOST = "65.109.215.115"
PROXY_PORT = 8443
PROXY_SECRET = "104462821249bd7ac519130220c25d09"

# Кому отправлять (целое число, не строка!)
YOUR_CHAT_ID = 123456789
```

### Шаг 4: Создание клиента

```python
# Стандартные API ключи для ботов!
# Не нужно получать свои API ключи для бота!
BOT_API_ID = 6
BOT_API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"

client = TelegramClient(
    session='bot_session',
    api_id=BOT_API_ID,
    api_hash=BOT_API_HASH,
    proxy=(PROXY_HOST, PROXY_PORT, PROXY_SECRET),
    connection=ConnectionTcpMTProxyRandomizedIntermediate,
)
```

**Важно:**
- `api_id=6` и `api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e"` — стандартные значения для ботов
- Не нужно получать свои API ключи!

### Шаг 5: Подключение и отправка

```python
async def main():
    # Подключаемся как бот (используем токен!)
    await client.start(bot_token=BOT_TOKEN)

    # Получаем информацию о боте
    me = await client.get_me()
    print(f"Бот: @{me.username}")

    # Формируем сообщение с HTML разметкой
    message = """
🤖 <b>Сообщение от бота</b>

⏰ Время: 2026-03-30 04:40:33
📡 Статус: <b>Работает через MTProto прокси</b>
🔗 Прокси: 65.109.215.115:8443

Это тестовое сообщение подтверждает что бот работает! ✅
    """.strip()

    # Отправляем сообщение
    await client.send_message(YOUR_CHAT_ID, message, parse_mode='html')

    print("✅ Сообщение отправлено!")

    await client.disconnect()

asyncio.run(main())
```

---

## 📝 Полный рабочий пример

```python
"""
Отправка сообщения от бота через MTProto прокси.
Копируйте и используйте в своих проектах!
"""

import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

# === КОНФИГУРАЦИЯ ===
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
PROXY_HOST = "65.109.215.115"
PROXY_PORT = 8443
PROXY_SECRET = "104462821249bd7ac519130220c25d09"
YOUR_CHAT_ID = 123456789  # Целое число!

# Стандартные API ключи для ботов
BOT_API_ID = 6
BOT_API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"


async def send_notification(message_text: str):
    """
    Отправляет уведомление от имени бота через MTProto прокси.
    
    Args:
        message_text: Текст сообщения (поддерживает HTML)
    """
    client = TelegramClient(
        'bot_session',
        BOT_API_ID,
        BOT_API_HASH,
        proxy=(PROXY_HOST, PROXY_PORT, PROXY_SECRET),
        connection=ConnectionTcpMTProxyRandomizedIntermediate,
    )
    
    try:
        await client.start(bot_token=BOT_TOKEN)
        await client.send_message(YOUR_CHAT_ID, message_text, parse_mode='html')
        print(f"✅ Сообщение отправлено в {YOUR_CHAT_ID}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        raise
    finally:
        await client.disconnect()


async def main():
    # Формируем сообщение
    message = f"""
🤖 <b>Уведомление от бота</b>

⏰ Время: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
📡 Статус: <b>Работает через MTProto прокси</b>
🔗 Прокси: {PROXY_HOST}:{PROXY_PORT}

Это тестовое сообщение подтверждает что бот работает! ✅
    """.strip()
    
    await send_notification(message)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🔑 Ключевые моменты

### 1. Telethon вместо requests

```python
# ❌ НЕ РАБОТАЕТ (если api.telegram.org заблокирован)
requests.post("https://api.telegram.org/bot{TOKEN}/sendMessage", ...)

# ✅ РАБОТАЕТ (через MTProto прокси)
client = TelegramClient(..., proxy=(host, port, secret))
await client.start(bot_token=TOKEN)
await client.send_message(...)
```

### 2. Стандартные API ключи для ботов

```python
# Не нужно получать свои ключи!
BOT_API_ID = 6
BOT_API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"
```

Эти ключи используются по умолчанию для всех ботов Telegram.

### 3. Класс подключения

```python
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

# Для dd-secret (начинается с dd)
# Для ee-secret
# Для secret без префикса
# Универсальный класс - работает со всеми типами!
connection=ConnectionTcpMTProxyRandomizedIntermediate
```

### 4. Формат secret

```python
def normalize_secret(secret: str) -> str:
    """
    Нормализует secret до 32 hex-символов (16 байт).
    """
    # Удаляем префиксы ee/dd
    if secret[:2] in ("ee", "dd"):
        secret = secret[2:]
    
    # Извлекаем только hex часть (до домена)
    hex_part = ""
    for char in secret:
        if char in "0123456789abcdefABCDEF":
            hex_part += char
        else:
            break
    
    # Обрезаем до 32 символов
    return hex_part[:32]

# Пример
secret = "dd104462821249bd7ac519130220c25d09"  # 34 символа
normalized = normalize_secret(secret)  # "104462821249bd7ac519130220c25d09"
```

### 5. ChatID должен быть целым числом

```python
# ✅ Правильно
YOUR_CHAT_ID = 123456789

# ❌ Неправильно (бот не сможет найти пользователя)
YOUR_CHAT_ID = "123456789"
YOUR_CHAT_ID = "+79991234567"
```

---

## 🚨 Частые ошибки

### 1. ValueError: Could not find the input entity

**Ошибка:**
```
ValueError: Could not find the input entity for PeerUser(user_id=123456789)
```

**Причина:** Бот не может найти пользователя по ID.

**Решение:**
- Пользователь должен начать диалог с ботом (нажать /start)
- Использовать целый тип int для ID

```python
# ✅ Правильно
YOUR_CHAT_ID = 123456789  # int, не str!

# Пользователь нажал /start в боте
```

### 2. UsernameInvalidError

**Ошибка:**
```
UsernameInvalidError: Nobody is using this username
```

**Причина:** Username не существует.

**Решение:** Проверить что username существует:

```python
# ✅ Правильно
YOUR_CHAT_ID = "@durov"  # Если username существует

# ❌ Неправильно
YOUR_CHAT_ID = "@nonexistent123"
```

### 3. ConnectionRefusedError

**Ошибка:**
```
ConnectionRefusedError: [WinError 1225] Удаленный компьютер отклонил подключение
```

**Причина:** Прокси не работает.

**Решение:** Использовать другой прокси или проверить текущий:

```python
# Проверка прокси перед использованием
async def check_proxy(host, port, secret):
    client = TelegramClient(
        'test', 6, 'eb06d4abfb49dc3eeb1aeb98ae0f581e',
        proxy=(host, port, secret),
        connection=ConnectionTcpMTProxyRandomizedIntermediate
    )
    try:
        await client.connect()
        print("✅ Прокси работает")
        return True
    except:
        print("❌ Прокси не работает")
        return False
    finally:
        await client.disconnect()
```

### 4. AuthKeyUnregisteredError

**Ошибка:**
```
AuthKeyUnregisteredError: Auth key was registered with a different user
```

**Причина:** Сессия принадлежит другому пользователю.

**Решение:** Удалить файл сессии и создать новый:

```python
# Удалить bot_session.session и bot_session.session-journal
# Затем запустить заново
```

---

## 📊 Сравнение подходов

| Подход | Плюсы | Минусы | Когда использовать |
|--------|-------|--------|-------------------|
| **Bot API + requests** | Простой код | Не работает без HTTP прокси | Для серверов за рубежом |
| **Bot API + HTTP прокси** | Работает | HTTP прокси часто мертвые | Если есть рабочий HTTP прокси |
| **Telethon + MTProto** | ✅ Работает через MTProto | Нужно знать API ключи | **Для РФ и блокировок** |

---

## 🎯 Примеры использования

### 1. Уведомление о событии

```python
async def notify_event(event_name: str):
    message = f"""
🔔 <b>Событие: {event_name}</b>

⏰ Время: {datetime.now().strftime("%H:%M:%S")}
📍 Место: Сервер №1

Статус: <b>✅ Успешно</b>
    """
    await send_notification(message)
```

### 2. Уведомление с кнопкой

```python
from telethon import types

async def notify_with_button():
    message = "🔔 Новое уведомление!"
    
    buttons = types.KeyboardButton.inline(
        "Подробнее",
        data=b"show_details"
    )
    
    await client.send_message(
        YOUR_CHAT_ID,
        message,
        buttons=buttons
    )
```

### 3. Массовая рассылка

```python
async def broadcast_to_subscribers(subscriber_ids: list, message: str):
    """Отправляет сообщение всем подписчикам."""
    
    for user_id in subscriber_ids:
        try:
            await client.send_message(user_id, message)
            await asyncio.sleep(0.5)  # Пауза от flood
        except Exception as e:
            print(f"Не удалось отправить {user_id}: {e}")
```

### 4. Уведомление с фото

```python
async def notify_with_photo(message: str, photo_path: str):
    await client.send_file(
        YOUR_CHAT_ID,
        photo_path,
        caption=message,
        parse_mode='html'
    )
```

---

## 📁 Готовый модуль для проектов

Создайте файл `bot_notifier.py`:

```python
"""
Модуль уведомлений через бота Telethon + MTProto
"""
import asyncio
from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

class BotNotifier:
    def __init__(self, bot_token: str, chat_id: int, proxy: tuple):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.proxy = proxy
        self.client = None
    
    async def connect(self):
        self.client = TelegramClient(
            'bot_session',
            6,  # BOT_API_ID
            'eb06d4abfb49dc3eeb1aeb98ae0f581e',  # BOT_API_HASH
            proxy=self.proxy,
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
        )
        await self.client.start(bot_token=self.bot_token)
    
    async def send(self, text: str, parse_mode: str = 'html'):
        if not self.client:
            await self.connect()
        await self.client.send_message(self.chat_id, text, parse_mode=parse_mode)
    
    async def disconnect(self):
        if self.client:
            await self.client.disconnect()
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


# Использование
async def main():
    async with BotNotifier(
        bot_token="YOUR_TOKEN",
        chat_id=123456789,
        proxy=("host", port, "secret")
    ) as notifier:
        await notifier.send("🔔 Уведомление!")

asyncio.run(main())
```

---

## ✅ Итог

Для работы бота через MTProto прокси:

1. **Используй Telethon** вместо requests
2. **Подключайся как бот** через `client.start(bot_token=TOKEN)`
3. **Используй стандартные API ключи** (`api_id=6`, `api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e"`)
4. **Настрой MTProto прокси** в параметре proxy
5. **Отправляй сообщения** через `client.send_message()`
6. **ChatID должен быть целым числом** (int)

---

<div align="center">

**Теперь ваш бот работает через MTProto прокси! 🎉**

Копируйте эти примеры в свои проекты!

</div>
