# 📚 Telegram Proxy: Проблемы и Решения

Полное руководство по работе с MTProto и HTTP/HTTPS прокси в Python для Telegram.

---

## 📋 Содержание

1. [Telethon и MTProto прокси](#telethon-и-mtproto-прокси)
2. [Формат Secret ключа](#формат-secret-ключа)
3. [Классы подключения](#классы-подключения)
4. [Версии Telethon](#версии-telethon)
5. [Bot API vs User API](#bot-api-vs-user-api)
6. [HTTP/HTTPS прокси](#httphttps-прокси)
7. [Сессии и авторизация](#сессии-и-авторизация)
8. [Таймауты и ошибки](#таймауты-и-ошибки)
9. [Лучшие практики](#лучшие-практики)

---

## 🔧 Telethon и MTProto прокси

### ❌ Проблема 1: Неправильный формат proxy параметра

**Ошибка:**
```python
TypeError: TelegramBaseClient.__init__() got an unexpected keyword argument 'proxy_secret'
```

**Причина:** В Telethon 1.34+ параметр `proxy_secret` удалён.

**Решение:**
```python
# ❌ НЕПРАВИЛЬНО (работало в старых версиях)
client = TelegramClient(
    session='session',
    api_id=API_ID,
    api_hash=API_HASH,
    proxy=(host, port),
    proxy_secret=secret,  # ❌ Удалено!
    connection=ConnectionTcpMTProxyRandomizedIntermediate,
)

# ✅ ПРАВИЛЬНО
client = TelegramClient(
    session='session',
    api_id=API_ID,
    api_hash=API_HASH,
    proxy=(host, port, secret),  # Secret в кортеже!
    connection=ConnectionTcpMTProxyRandomizedIntermediate,
)
```

---

### ❌ Проблема 2: ValueError: MTProxy secret must be a hex-string representing 16 bytes

**Ошибка:**
```
ValueError: MTProxy secret must be a hex-string representing 16 bytes
```

**Причина:** Secret должен быть ровно 32 hex-символа (16 байт).

**Решение:**
```python
def normalize_secret(secret: str) -> str:
    """Нормализует secret до 32 hex-символов."""
    if not secret:
        return '0' * 32
    
    # Удаляем префиксы ee/dd
    if secret[:2] in ("ee", "dd"):
        secret = secret[2:]
    
    # Извлекаем только hex часть (до домена)
    hex_part = ""
    for char in secret:
        if char in "0123456789abcdefABCDEF":
            hex_part += char
        else:
            break  # Нашли не-hex символ (начало домена)
    
    # Обрезаем до 32 символов
    return hex_part[:32]

# Пример использования
secret = "eecac7f588b01164afc6a337125ecdd96173626172732e7275"  # 50 символов с доменом
normalized = normalize_secret(secret)  # "eecac7f588b01164afc6a337125ecdd9" (32 символа)
```

---

### ❌ Проблема 3: ValueError: readexactly size can not be less than zero

**Ошибка:**
```
ValueError: readexactly size can not be less than zero
```

**Причина:** Неправильный класс подключения для типа secret.

**Решение:**
```python
# Для dd-secret (начинается с dd) - ТОЛЬКО RandomizedIntermediate
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

client = TelegramClient(
    session='session',
    api_id=API_ID,
    api_hash=API_HASH,
    proxy=(host, port, secret),
    connection=ConnectionTcpMTProxyRandomizedIntermediate,  # ✅ Обязательно!
)

# Для ee-secret - можно любой, но лучше RandomizedIntermediate
# Для secret без префикса - любой класс
```

---

## 🔑 Формат Secret ключа

### Поддерживаемые форматы:

| Формат | Пример | Обработка |
|--------|--------|-----------|
| **Hex с ee** | `ee1234567890abcdef1234567890abcdef` | Удалить `ee`, взять 32 символа |
| **Hex с dd** | `dd1234567890abcdef1234567890abcdef` | Удалить `dd`, взять 32 символа |
| **Hex без префикса** | `1234567890abcdef1234567890abcdef` | Взять первые 32 символа |
| **С доменом** | `ee1234567890abcdef1234567890abcdefasbars.ru` | Обрезать до 32 hex |
| **Base64** | `SGVsbG9Xb3JsZCE=` | Декодировать, взять 16 байт |

### Функция нормализации:

```python
import base64

def normalize_secret(secret: str) -> bytes:
    """
    Нормализует secret по алгоритму Telethon tcpmtproxy.py.
    Возвращает 16 байт.
    """
    if not secret:
        return b'\x00' * 16
    
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
    
    secret = hex_part
    
    # Обрезаем до 32 символов (16 байт)
    if len(secret) > 32:
        secret = secret[:32]
    
    # Декодируем из hex
    try:
        secret_bytes = bytes.fromhex(secret)
    except ValueError:
        # Пытаемся base64
        secret = secret + '=' * (-len(secret) % 4)
        secret_bytes = base64.b64decode(secret.encode())
    
    return secret_bytes[:16]
```

---

## 🔌 Классы подключения

### Доступные классы для MTProxy:

```python
from telethon.network import (
    ConnectionTcpMTProxyAbridged,           # Минимальный оверхед
    ConnectionTcpMTProxyIntermediate,       # Всегда 4 байта длины
    ConnectionTcpMTProxyRandomizedIntermediate,  # ✅ Рекомендуется
)
```

### Какой класс использовать:

| Secret | Класс | Примечание |
|--------|-------|------------|
| `dd...` | `ConnectionTcpMTProxyRandomizedIntermediate` | **Обязательно!** |
| `ee...` | Любой, лучше `RandomizedIntermediate` | Совместимость |
| Без префикса | Любой | Стандартный MTProxy |

### Пример:

```python
from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

# ✅ Универсальный вариант (работает со всеми типами secret)
client = TelegramClient(
    session='session',
    api_id=API_ID,
    api_hash=API_HASH,
    proxy=(host, port, secret),
    connection=ConnectionTcpMTProxyRandomizedIntermediate,
)
```

---

## 📦 Версии Telethon

### Сравнение версий:

| Версия | Python | proxy_secret | Примечание |
|--------|--------|--------------|------------|
| 1.28.x | ≤3.11 | ✅ Есть | Устарела, нет поддержки Python 3.12+ |
| 1.34.x | ≤3.13 | ❌ Нет | Стабильная, рекомендуется |
| 1.42.x | ≥3.10 | ❌ Нет | Новая, баги с MTProxy на Python 3.14 |

### Проблема с Python 3.14:

**Ошибка:**
```
ModuleNotFoundError: No module named 'imghdr'
```

**Причина:** Модуль `imghdr` удалён в Python 3.13+.

**Решение:** Использовать Telethon 1.34+ или Python 3.11.

### Рекомендуемая конфигурация:

```bash
# Для стабильной работы
Python 3.11 + Telethon 1.34.0

# Или
Python 3.12 + Telethon 1.42.0
```

### Установка:

```bash
# Стабильная версия
pip install telethon==1.34.0

# Или последняя
pip install telethon>=1.42.0

# Зависимости
pip install python-dotenv requests
```

---

## 🤖 Bot API vs User API

### В чём разница:

| Характеристика | Bot API | User API (Telethon) |
|----------------|---------|---------------------|
| Библиотека | `requests` | `telethon` |
| Авторизация | Токен бота | Номер телефона |
| Прокси | HTTP/HTTPS/SOCKS5 | MTProto/HTTP/SOCKS5 |
| Ограничения | Боты не читают историю | Полный доступ |
| Сессия | Не нужна | Сохраняется в .session |

### Отправка сообщений:

#### Через Bot API (requests):

```python
import requests

BOT_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
CHAT_ID = "123456789"

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
response = requests.post(
    url,
    json={
        "chat_id": CHAT_ID,
        "text": "Hello!",
        "parse_mode": "HTML"
    },
    timeout=10
)
```

**Проблема:** Telegram API заблокирован у многих провайдеров без прокси.

**Решение с HTTP прокси:**
```python
proxies = {
    "http": "http://user:pass@ip:port",
    "https": "http://user:pass@ip:port"
}

response = requests.post(
    url,
    json={"chat_id": CHAT_ID, "text": "Hello!"},
    proxies=proxies,
    timeout=30
)
```

**Проблема:** HTTP прокси часто не работают с Telegram API.

#### Через User API (Telethon):

```python
from telethon import TelegramClient

client = TelegramClient('session', API_ID, API_HASH)
await client.start(phone=PHONE)

# Отправка через тот же прокси что и подключение
await client.send_message(CHAT_ID, "Hello!", parse_mode='html')
```

**Преимущество:** Работает через MTProto прокси, не нужен отдельный HTTP прокси.

### Вывод:

✅ **Для уведомлений используйте Telethon** — работает через тот же прокси что и основное подключение.

❌ **Bot API через requests** — требует отдельный HTTP прокси который может не работать.

---

## 🌐 HTTP/HTTPS прокси

### Форматы прокси для requests:

```python
# Без авторизации
proxies = {
    "http": "http://123.45.67.89:8080",
    "https": "http://123.45.67.89:8080"
}

# С авторизацией
proxies = {
    "http": "http://user:pass@123.45.67.89:8080",
    "https": "http://user:pass@123.45.67.89:8080"
}

# SOCKS5 (требуется pysocks)
proxies = {
    "http": "socks5://user:pass@123.45.67.89:1080",
    "https": "socks5://user:pass@123.45.67.89:1080"
}
```

### Проблема: Telegram API заблокирован

**Симптомы:**
```
requests.exceptions.ReadTimeout: HTTPSConnectionPool(host='api.telegram.org', port=443): Read timed out.
```

**Решения:**

1. **Использовать MTProto прокси через Telethon** (рекомендуется)
2. **Найти рабочий HTTP прокси** (сложно)
3. **Использовать VPN** (альтернатива)

### Проверка HTTP прокси:

```python
import requests

def check_http_proxy(proxy_url: str, timeout: int = 5) -> bool:
    """Проверяет HTTP прокси через запрос к Telegram Bot API."""
    proxies = {
        "http": f"http://{proxy_url}",
        "https": f"http://{proxy_url}"
    }
    
    try:
        response = requests.get(
            "https://api.telegram.org/bot{TOKEN}/getMe",
            proxies=proxies,
            timeout=timeout
        )
        return response.status_code == 200
    except:
        return False
```

---

## 💾 Сессии и авторизация

### Файлы сессий:

```
session_name.session           # Данные сессии
session_name.session-journal   # Журнал (SQLite)
```

### Что делать с сессиями:

| Действие | Что делать |
|----------|------------|
| **Первый запуск** | Ввести код из Telegram |
| **Повторный запуск** | Использовать сохранённую сессию |
| **Смена аккаунта** | Удалить .session файл |
| **GitHub** | НЕ коммитить .session файлы |

### .gitignore для сессий:

```gitignore
# Telethon sessions
*.session
*.session-journal

# Environment
.env
```

### Код подтверждения:

**Где получить:**
1. Откройте Telegram на телефоне/ПК
2. Найдите сообщение от **Telegram** (официальный аккаунт с галочкой)
3. Скопируйте код из сообщения

**Не SMS!** Код приходит в приложение Telegram.

---

## ⏱️ Таймауты и ошибки

### Частые ошибки и решения:

#### 1. TimeoutError

```python
# Увеличьте таймаут
await asyncio.wait_for(client.connect(), timeout=30)  # Было 10
```

#### 2. ConnectionRefusedError

```python
# Прокси недоступен, пробуем следующий
try:
    await client.connect()
except ConnectionRefusedError:
    # Переключиться на другой прокси
    pass
```

#### 3. OSError: [WinError 121] Превышен таймаут семафора

**Причина:** Прокси слишком медленный или заблокирован.

**Решение:** Использовать другой прокси или увеличить таймаут.

#### 4. IncompleteReadError

```
IncompleteReadError: 323 bytes read on a total of X expected bytes
```

**Причина:** Прокси закрывает соединение досрочно.

**Решение:** Прокси мёртвый, использовать другой.

#### 5. gaierror: [Errno 11001] getaddrinfo failed

**Причина:** Не удалось разрешить имя хоста.

**Решение:** Проверить DNS или использовать IP вместо домена.

---

## ✅ Лучшие практики

### 1. Умный выбор прокси

```python
# Сохраняем лучший прокси
def save_best_proxy(proxy_url: str, latency: float):
    with open("best_proxy.txt", "w") as f:
        f.write(f"{proxy_url}|{latency}")

# Загружаем и используем
def load_best_proxy() -> tuple:
    with open("best_proxy.txt", "r") as f:
        data = f.read().split("|")
        return data[0], float(data[1])
```

### 2. Fallback цепочка

```python
# Порядок подключения:
# 1. Лучший прокси из best_proxy.txt
# 2. Прокси из .env
# 3. Рабочие прокси из working_mtproto.txt
# 4. Прямое подключение (если доступно)
```

### 3. Логирование

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("checker.log"),
        logging.StreamHandler()
    ]
)
```

### 4. Обработка ошибок

```python
async def safe_connect(client, max_retries=3):
    for attempt in range(max_retries):
        try:
            await client.connect()
            return True
        except Exception as e:
            log.warning(f"Попытка {attempt+1} не удалась: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
    return False
```

### 5. Конфигурация через .env

```env
# .env
API_ID=12345678
API_HASH=abcdef0123456789
PHONE=+79991234567
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
YOUR_CHAT_ID=123456789

# Прокси (опционально)
DEFAULT_PROXY_HOST=65.21.58.190
DEFAULT_PROXY_PORT=8080
DEFAULT_PROXY_SECRET=dd104462821249bd7ac519130220c25d09

# Настройки
MESSAGES_LIMIT=20
CHECK_TIMEOUT=15
```

---

## 📝 Чеклист перед запуском

- [ ] API_ID и API_HASH получены с https://my.telegram.org/apps
- [ ] PHONE указан в формате +79991234567
- [ ] .env файл создан и заполнен
- [ ] .env добавлен в .gitignore
- [ ] Зависимости установлены: `pip install -r requirements.txt`
- [ ] Есть рабочий MTProto прокси для подключения
- [ ] YOUR_CHAT_ID получен от @userinfobot

---

## 🔗 Полезные ссылки

- [Telethon документация](https://docs.telethon.dev/)
- [Telegram API](https://my.telegram.org/apps)
- [MTProto прокси каналы](https://t.me/ProxyMTProto)
- [PySocks документация](https://github.com/Anorov/PySocks)

---

## 📚 История версий документа

| Дата | Изменения |
|------|-----------|
| 2026-03-30 | Initial version |

---

<div align="center">

**Сохраните этот файл чтобы не решать те же проблемы снова!**

</div>
