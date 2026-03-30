# 🤖 Как заставить бота работать через MTProto прокси

Полное руководство по подключению Telegram бота через MTProto прокси.

---

## 📋 Проблема

Обычно боты используют **Bot API** через `requests`:

```python
import requests

BOT_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

response = requests.post(
    url,
    json={"chat_id": CHAT_ID, "text": "Hello!"}
)
```

**Проблема:** `api.telegram.org` заблокирован у многих провайдеров. Нужен HTTP прокси, но они часто не работают.

---

## ✅ Решение: Telethon + Bot Token

Используем **Telethon** (User API) с **бот-токеном** для подключения через MTProto прокси.

### Почему это работает:

| Характеристика | Bot API (requests) | Telethon + Bot Token |
|----------------|-------------------|---------------------|
| Подключение | HTTPS к api.telegram.org | MTProto к серверам Telegram |
| Прокси | HTTP/HTTPS (часто не работает) | MTProto (работает!) |
| Блокировки | Затрагивает api.telegram.org | Обходит блокировки |

---

## 🔧 Реализация

### 1. Импорт библиотек

```python
import asyncio
from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate
```

### 2. Настройки

```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# MTProto прокси
PROXY_HOST = "65.21.58.190"
PROXY_PORT = 8080
PROXY_SECRET = "dd104462821249bd7ac519130220c25d09"

# Кому отправлять
YOUR_CHAT_ID = 123456789  # Или @username
```

### 3. Создание клиента

```python
client = TelegramClient(
    session='bot_session',
    api_id=6,  # Стандартный API ID для ботов
    api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e",  # Стандартный hash
    proxy=(PROXY_HOST, PROXY_PORT, PROXY_SECRET),
    connection=ConnectionTcpMTProxyRandomizedIntermediate,
)
```

**Важно:** 
- `api_id=6` и `api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e"` — это стандартные значения для ботов
- Не нужно получать свои API ключи для бота!

### 4. Подключение и отправка

```python
async def main():
    # Подключаемся как бот
    await client.start(bot_token=BOT_TOKEN)
    
    # Получаем информацию о боте
    me = await client.get_me()
    print(f"Бот: @{me.username}")
    
    # Формируем сообщение
    message = """
🤖 <b>Сообщение от бота</b>

⏰ Время: 2026-03-30 04:40:33
📡 Статус: <b>Работает через MTProto прокси</b>
🔗 Прокси: 65.21.58.190:8080

Это тестовое сообщение подтверждает что бот работает! ✅
    """.strip()
    
    # Отправляем
    await client.send_message(YOUR_CHAT_ID, message, parse_mode='html')
    
    print("✅ Сообщение отправлено!")
    
    await client.disconnect()

asyncio.run(main())
```

---

## 📝 Полный рабочий скрипт

```python
"""
Отправка сообщения от бота через MTProto прокси.
"""

import asyncio
from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

# Настройки
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
PROXY_HOST = "65.21.58.190"
PROXY_PORT = 8080
PROXY_SECRET = "dd104462821249bd7ac519130220c25d09"
YOUR_CHAT_ID = 123456789

async def main():
    client = TelegramClient(
        session='bot_session',
        api_id=6,
        api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e",
        proxy=(PROXY_HOST, PROXY_PORT, PROXY_SECRET),
        connection=ConnectionTcpMTProxyRandomizedIntermediate,
    )
    
    try:
        await client.start(bot_token=BOT_TOKEN)
        me = await client.get_me()
        print(f"🤖 Бот: @{me.username}")
        
        message = f"""
🤖 <b>Сообщение от бота</b>

⏰ Время: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
📡 Статус: <b>Работает через MTProto прокси</b>
🔗 Прокси: {PROXY_HOST}:{PROXY_PORT}

Это тестовое сообщение подтверждает что бот работает! ✅
        """.strip()
        
        await client.send_message(YOUR_CHAT_ID, message, parse_mode='html')
        print("✅ Сообщение отправлено!")
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
    finally:
        await client.disconnect()

asyncio.run(main())
```

---

## 🔑 Ключевые моменты

### 1. Telethon вместо requests

```python
# ❌ НЕ РАБОТАЕТ (если api.telegram.org заблокирован)
requests.post("https://api.telegram.org/bot{TOKEN}/sendMessage", ...)

# ✅ РАБОТАЕТ (через MTProto)
client = TelegramClient(..., proxy=(host, port, secret))
await client.start(bot_token=TOKEN)
await client.send_message(...)
```

### 2. Стандартные API ключи для ботов

```python
# Не нужно получать свои ключи!
api_id=6
api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e"
```

Эти ключи используются по умолчанию для ботов.

### 3. Класс подключения

```python
# Для dd-secret (начинается с dd)
ConnectionTcpMTProxyRandomizedIntermediate

# Для ee-secret
ConnectionTcpMTProxyRandomizedIntermediate  # Универсальный
```

### 4. Формат secret

```python
# Secret должен быть 32 hex-символа (16 байт)
# Если длиннее (с доменом) - обрезать

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

# Пример
secret = "dd104462821249bd7ac519130220c25d09"  # 34 символа
normalized = normalize_secret(secret)  # "104462821249bd7ac519130220c25d09" (32 символа)
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
- Или использовать @username вместо ID

```python
# ✅ Работает если пользователь начал диалог
YOUR_CHAT_ID = 123456789

# ✅ Или использовать username
YOUR_CHAT_ID = "@username"
```

### 2. UsernameInvalidError

**Ошибка:**
```
UsernameInvalidError: Nobody is using this username
```

**Причина:** Username не существует или неверный формат.

**Решение:**
- Проверить что username существует
- Формат: `[a-zA-Z][\w\d]{3,30}[a-zA-Z\d]`

```python
# ✅ Правильно
YOUR_CHAT_ID = "@durov"

# ❌ Неправильно
YOUR_CHAT_ID = "@ddd"  # Слишком короткий
YOUR_CHAT_ID = "@123user"  # Начинается с цифры
```

### 3. ConnectionRefusedError

**Ошибка:**
```
ConnectionRefusedError: [WinError 1225] Удаленный компьютер отклонил подключение
```

**Причина:** Прокси не работает.

**Решение:** Использовать другой прокси.

---

## 📊 Сравнение подходов

| Подход | Плюсы | Минусы |
|--------|-------|--------|
| **Bot API + requests** | Простой | Не работает без HTTP прокси |
| **Bot API + HTTP прокси** | Работает | HTTP прокси часто мертвые |
| **Telethon + MTProto** | ✅ Работает через MTProto | Нужно знать API ключи |

---

## ✅ Итог

Для работы бота через MTProto прокси:

1. **Используй Telethon** вместо requests
2. **Подключайся как бот** через `client.start(bot_token=...)`
3. **Используй стандартные API ключи** (api_id=6, api_hash=...)
4. **Настрой MTProto прокси** в параметре proxy
5. **Отправляй сообщения** через `client.send_message()`

---

## 📁 Пример файла: bot_send_message.py

См. файл `bot_send_message.py` в проекте для полного рабочего примера.

---

<div align="center">

**Теперь бот работает через MTProto прокси! 🎉**

</div>
