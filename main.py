"""
MTProto Proxy Scraper & Checker
Скрапит прокси из Telegram каналов и проверяет их работоспособность.

Usage:
    python main.py --scrape    # Скрапить прокси из канала
    python main.py --check     # Проверить прокси из файла
    python main.py --all       # Скрапить и проверить
    python main.py --notify    # Отправить уведомление в ЛС
"""

import asyncio
import re
import os
import sys
import argparse
import requests
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from output_manager import OutputManager, ProxyRecord

load_dotenv()

from telethon import TelegramClient
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate

# ==================== КОНФИГУРАЦИЯ ====================
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
YOUR_CHAT_ID = os.getenv("YOUR_CHAT_ID", "")

# Каналы для скрапинга (MTProto прокси)
CHANNELS = [
    "@ProxyMTProto",
    "@MTProto_Proxies_Free",
    "@MTP_roxy",
    "@Proxy_Telegram_MTProto",
    "@V2Ray_MTProto",
    "@TeleProxy_New",
    "@MTProto_Proxy_List",
    "@Telegram_Proxy_Server",
    "@Proxy_MTProto_Telegram",
    "@MTProto_List",
]

# GitHub Raw ссылки для скрапинга (списки прокси)
GITHUB_SOURCES = [
    "https://raw.githubusercontent.com/SoliSpirit/mtproto/master/all_proxies.txt",
    "https://raw.githubusercontent.com/mtprotox/ProxyList/main/README.md",
    "https://raw.githubusercontent.com/Free-Mtproto-Proxies/mtproto-proxy/main/README.md",
]

# Настройки
MESSAGES_LIMIT = int(os.getenv("MESSAGES_LIMIT", 20))
CHECK_TIMEOUT = int(os.getenv("CHECK_TIMEOUT", 30))  # 30с — для ре-чека (точность)
CHECK_TIMEOUT_FAST = 5  # 5с — для массовой проверки из очереди
CHECK_SAVE_INTERVAL = 30  # Сохранять промежуточные результаты каждые N прокси
BACKUP_PING_THRESHOLD = 15000  # мс — прокси с пингом выше = "запасной"
MAX_CONNECT_RETRIES = 3  # Попытки подключения с экспоненциальной задержкой

# Файлы
WORKING_FILE = "working_mtproto.txt"
BACKUP_FILE = "backup_proxies.txt"  # Медленные, но рабочие
SCRAPED_FILE = "scraped_proxies.txt"
BEST_PROXY_FILE = "best_proxy.txt"
LOG_FILE = "logs/checker.log"
QUEUE_FILE = "queue.txt"

# Прокси для подключения (если нужен)
DEFAULT_PROXY_HOST = os.getenv("DEFAULT_PROXY_HOST", "")
DEFAULT_PROXY_PORT = os.getenv("DEFAULT_PROXY_PORT", "")
DEFAULT_PROXY_SECRET = os.getenv("DEFAULT_PROXY_SECRET", "")

# Менеджер вывода (data/)
output = OutputManager()

# Убедиться что logs/ существует
Path("logs").mkdir(exist_ok=True)
# ======================================================


# ==================== ЛОГИРОВАНИЕ ====================
def log(message: str, level: str = "INFO"):
    """Логирует сообщение в консоль и файл."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] [{level}] {message}"
    print(log_msg)
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except:
        pass


def log_error(message: str):
    log(message, "ERROR")


def log_success(message: str):
    log(message, "OK")


def log_warning(message: str):
    log(message, "WARN")
# ======================================================


# ==================== ПАРСИНГ ====================
# Паттерн для текста вида: Server: `...`, Port: `...`, Secret: `...`
PROXY_TEXT_PATTERN = re.compile(
    r'Server:\s*`?([^`\n\r]+)`?\s*\n?\s*Port:\s*`?(\d+)`?\s*\n?\s*Secret:\s*`?([a-fA-F0-9]+)`?',
    re.IGNORECASE
)

# Паттерн для ссылок t.me/proxy и tg://proxy
PROXY_LINK_PATTERN = re.compile(
    r'(?:https?://)?(?:t\.me/proxy\?|tg://proxy\?)server=([^&\s]+)&port=(\d+)&secret=([a-fA-F0-9]+)',
    re.IGNORECASE
)


def extract_proxy(text: str) -> list[str]:
    """Извлекает ссылки на прокси из текста."""
    proxies = []
    
    # Ищем ссылки t.me/proxy
    for match in PROXY_LINK_PATTERN.finditer(text):
        host, port, secret = match.groups()
        proxy_url = f"https://t.me/proxy?server={host}&port={port}&secret={secret}"
        if proxy_url not in proxies:
            proxies.append(proxy_url)
    
    # Ищем текст с параметрами
    for match in PROXY_TEXT_PATTERN.finditer(text):
        host, port, secret = match.groups()
        host = host.strip()
        proxy_url = f"https://t.me/proxy?server={host}&port={port}&secret={secret}"
        if proxy_url not in proxies:
            proxies.append(proxy_url)
    
    return proxies


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
    
    # Декодируем
    try:
        secret_bytes = bytes.fromhex(secret)
    except ValueError:
        # Пытаемся base64
        import base64
        secret = secret + '=' * (-len(secret) % 4)
        secret_bytes = base64.b64decode(secret.encode())
    
    return secret_bytes[:16]


def parse_proxy(proxy_url: str) -> tuple:
    """Парсит ссылку в (host, port, secret_bytes)."""
    pattern = r"server=([^&]+)&port=(\d+)&secret=([^&]+)"
    match = re.search(pattern, proxy_url, re.IGNORECASE)
    
    if not match:
        raise ValueError(f"Неверный формат прокси: {proxy_url}")
    
    host = match.group(1)
    port = int(match.group(2))
    secret = normalize_secret(match.group(3))
    
    return host, port, secret.hex()
# ======================================================


# ==================== СКРАПИНГ ====================
def proxy_key(proxy_url: str) -> str:
    """
    Нормализует прокси в ключ host:port:secret для дедупликации.
    Удаляет лишние пробелы, приводит к нижнему регистру.
    """
    pattern = r"server=([^&]+)&port=(\d+)&secret=([^&]+)"
    match = re.search(pattern, proxy_url, re.IGNORECASE)
    if not match:
        return proxy_url.strip().lower()
    host, port, secret = match.groups()
    return f"{host.strip().lower()}:{port.strip()}:{secret.strip().lower()}"


def load_known_proxies() -> set[str]:
    """
    Загружает все известные прокси из всех источников и возвращает set их ключей.
    Используется для дедупликации.
    """
    known = set()
    for source in [WORKING_FILE, str(output.working_list_file), QUEUE_FILE, SCRAPED_FILE]:
        proxies = load_proxies(source)
        for p in proxies:
            known.add(proxy_key(p))
    return known


def fetch_github_proxies() -> list[str]:
    """
    Скачивает текст по всем GITHUB_SOURCES и извлекает прокси.
    """
    all_proxies = []

    for url in GITHUB_SOURCES:
        log(f"  📥 GitHub: {url}")
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            proxies = extract_proxy(resp.text)
            all_proxies.extend(proxies)
            log(f"     Найдено: {len(proxies)} прокси")
        except Exception as e:
            log_warning(f"  Ошибка загрузки {url}: {type(e).__name__}: {e}")

    return all_proxies


async def scrape_proxies(client: TelegramClient) -> list[str]:
    """
    Скрапит прокси из ВСЕХ источников (Telegram каналы + GitHub).
    Дедуплицирует по host:port:secret против существующих файлов.
    Возвращает ТОЛЬКО новые уникальные прокси.
    """
    log("\n[SCRAPER] Сбор прокси из всех источников...")

    # 1. Скрапинг из Telegram каналов
    tg_proxies = []
    for i, channel in enumerate(CHANNELS, 1):
        log(f"\n[{i}/{len(CHANNELS)}] Скрапинг канала: {channel}")
        log("-" * 50)

        try:
            messages = await client.get_messages(channel, limit=MESSAGES_LIMIT)
            log(f"  Получено сообщений: {len(messages)}")

            channel_proxies = []
            for msg in messages:
                if msg.text:
                    proxies = extract_proxy(msg.text)
                    for proxy in proxies:
                        if proxy not in channel_proxies:
                            channel_proxies.append(proxy)

            if channel_proxies:
                log_success(f"  Найдено прокси в этом канале: {len(channel_proxies)}")
                tg_proxies.extend(channel_proxies)
            else:
                log_warning(f"  Прокси не найдены в {channel}")

        except Exception as e:
            log_error(f"  Ошибка скрапинга {channel}: {type(e).__name__}: {e}")

    log(f"\n[SCRAPER] Из Telegram каналов: {len(tg_proxies)} прокси")

    # 2. Скрапинг из GitHub
    gh_proxies = fetch_github_proxies()
    log(f"[SCRAPER] Из GitHub: {len(gh_proxies)} прокси")

    # 3. Объединяем все найденные прокси
    all_found = tg_proxies + gh_proxies

    # 4. Нормализация и дедупликация
    # Удаляем дубликаты внутри самих новых данных
    seen_in_session = set()
    unique_new = []
    for proxy in all_found:
        key = proxy_key(proxy)
        if key not in seen_in_session:
            seen_in_session.add(key)
            unique_new.append(proxy)

    # 5. Исключаем уже известные прокси (из всех файлов)
    known = load_known_proxies()
    truly_new = []
    duplicates_count = 0

    for proxy in unique_new:
        key = proxy_key(proxy)
        if key in known:
            duplicates_count += 1
        else:
            truly_new.append(proxy)
            known.add(key)  # Чтобы не добавлять дубликаты внутри truly_new

    log("\n" + "=" * 50)
    log(f"[SCRAPER] НАЙДЕНО ВСЕГО: {len(all_found)}")
    log(f"[SCRAPER] Уникальных (внутри сессии): {len(unique_new)}")
    log(f"[SCRAPER] Новых уникальных прокси: {len(truly_new)}")
    log(f"[SCRAPER] Дубликатов пропущено: {duplicates_count}")
    log("=" * 50)

    return truly_new
# ======================================================


# ==================== ПРОВЕРКА ====================
async def check_proxy(proxy_url: str, timeout: int = CHECK_TIMEOUT) -> tuple[bool, float, str]:
    """
    Проверяет прокси подключением с retry и экспоненциальной задержкой.
    timeout — можно переопределить (для массовой проверки = 10с).
    """
    try:
        host, port, secret_hex = parse_proxy(proxy_url)
    except Exception as e:
        return False, 0, f"Ошибка парсинга: {e}"

    start_time = time.perf_counter()
    client = None

    # Для быстрой проверки — меньше попыток
    max_attempts = 1 if timeout <= 15 else MAX_CONNECT_RETRIES

    for attempt in range(max_attempts):
        try:
            client = TelegramClient(
                session=f"temp_{host}_{port}",
                api_id=API_ID,
                api_hash=API_HASH,
                proxy=(host, port, secret_hex),
                connection=ConnectionTcpMTProxyRandomizedIntermediate,
            )

            await asyncio.wait_for(client.connect(), timeout=timeout)
            is_auth = await client.is_user_authorized()

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            await client.disconnect()
            cleanup_session(f"temp_{host}_{port}")

            return True, elapsed_ms, "OK" if is_auth else "OK (no auth)"

        except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as e:
            # Retryable errors — пробуем снова
            if attempt < max_attempts - 1:
                delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                await asyncio.sleep(delay)
                cleanup_session(f"temp_{host}_{port}")
                continue
            # Все попытки исчерпаны
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            error_type = "Таймаут" if isinstance(e, asyncio.TimeoutError) else type(e).__name__
            try:
                if client and client.is_connected():
                    await client.disconnect()
            except:
                pass
            cleanup_session(f"temp_{host}_{port}")
            return False, elapsed_ms, f"{error_type} ({max_attempts}/{max_attempts})"

        except Exception as e:
            # Non-retryable error — сразу возвращаем
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            try:
                if client and client.is_connected():
                    await client.disconnect()
            except:
                pass
            cleanup_session(f"temp_{host}_{port}")
            return False, elapsed_ms, f"{type(e).__name__}: {str(e)[:40]}"

    # Fallback (если цикл закончился без return)
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    try:
        if client and client.is_connected():
            await client.disconnect()
    except:
        pass
    cleanup_session(f"temp_{host}_{port}")
    return False, elapsed_ms, "Неизвестная ошибка"


def cleanup_session(session_name: str):
    """Удаляет файлы сессии."""
    for ext in [".session", ".session-journal"]:
        try:
            path = session_name + ext
            if os.path.exists(path):
                os.remove(path)
        except:
            pass
# ======================================================


# ==================== УВЕДОМЛЕНИЯ (ЧЕРЕЗ БОТА) ====================

def build_proxy_message(working_proxies: list[str], scraped_count: int = 0) -> str:
    """Формирует сообщение для отправки в Telegram."""
    working_count = len(working_proxies)

    if working_count > 0:
        dead_count = max(0, scraped_count - working_count) if scraped_count > 0 else "?"

        message = f"""
🔍 <b>Проверка прокси завершена</b>

📊 <b>Результаты:</b>
   • Найдено: {scraped_count if scraped_count else "?"}
   • Рабочих: {working_count} ✅
   • Мёртвых: {dead_count} ❌

🔗 <b>Рабочие прокси (нажми для подключения):</b>
"""
        for i, proxy in enumerate(working_proxies[:20], 1):
            try:
                pattern = r"server=([^&]+)&port=(\d+)"
                match = re.search(pattern, proxy)
                if match:
                    host, port = match.groups()
                    message += f"\n{i}. <a href='{proxy}'>{host}:{port}</a>"
                else:
                    message += f"\n{i}. <a href='{proxy}'>Прокси #{i}</a>"
            except:
                message += f"\n{i}. <a href='{proxy}'>Прокси #{i}</a>"

        if working_count > 20:
            message += f"\n\n... и ещё {working_count - 20} в файле {WORKING_FILE}"

        message += f"""

📁 <b>Файлы:</b>
   • Все: {SCRAPED_FILE}
   • Рабочие: {WORKING_FILE}
   • Отчёт: data/report.md

⏰ {datetime.now().strftime("%d.%m.%Y %H:%M")}
        """.strip()
    else:
        message = f"""
🔍 <b>Проверка завершена</b>

📊 Рабочих прокси: 0
⏰ {datetime.now().strftime("%d.%m.%Y %H:%M")}

Все прокси оказались мёртвыми.
        """.strip()

    return message


async def send_report_via_bot(working_proxies: list[str], scraped_count: int = 0):
    """
    Отправляет отчёт через БОТА (не user).
    Пробует несколько прокси до успешной отправки.
    """
    if not BOT_TOKEN:
        log_error("BOT_TOKEN не настроен — не могу отправить через бота")
        return False

    if not YOUR_CHAT_ID:
        log_error("YOUR_CHAT_ID не настроен")
        return False

    message = build_proxy_message(working_proxies, scraped_count)

    # Собираем список прокси для попытки подключения
    proxy_candidates = []

    # 1. Лучший прокси
    best = load_best_proxy()
    if best:
        try:
            host, port, secret = parse_proxy(best[0])
            proxy_candidates.append((host, int(port), secret, "best_proxy.txt"))
        except:
            pass

    # 2. Быстрые из working_mtproto.txt
    for p in load_proxies(WORKING_FILE):
        try:
            host, port, secret = parse_proxy(p)
            proxy_candidates.append((host, int(port), secret, WORKING_FILE))
        except:
            pass

    # 3. Из data/working_list.txt
    if output.working_list_file.exists():
        for p in output.load_working_list():
            try:
                host, port, secret = parse_proxy(p)
                proxy_candidates.append((host, int(port), secret, "data/working_list.txt"))
            except:
                pass

    # 4. Без прокси (напрямую)
    proxy_candidates.append((None, None, None, "напрямую"))

    chat_id = YOUR_CHAT_ID
    if chat_id.lstrip('-').isdigit():
        chat_id = int(chat_id)

    # Пробуем каждый прокси
    for host, port, secret, source in proxy_candidates:
        try:
            if host and port and secret:
                proxy_kwargs = {
                    "proxy": (host, port, secret),
                    "connection": ConnectionTcpMTProxyRandomizedIntermediate,
                }
                log(f"[BOT] Пробую бота через {host}:{port} ({source})...")
            else:
                proxy_kwargs = {}
                log(f"[BOT] Пробую бота {source}...")

            client = TelegramClient(
                session="bot_notify_session",
                api_id=6,
                api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e",
                **proxy_kwargs
            )

            await asyncio.wait_for(client.start(bot_token=BOT_TOKEN), timeout=30)
            me = await client.get_me()
            log(f"[BOT] Бот @{me.username} подключён")
            log(f"[BOT] Длина сообщения: {len(message)} символов")

            # Telegram лимит: 4096 символов на сообщение
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await asyncio.wait_for(client.send_message(chat_id, chunk, parse_mode='html'), timeout=30)
            else:
                await asyncio.wait_for(
                    client.send_message(chat_id, message, parse_mode='html'),
                    timeout=30
                )

            log_success(f"✅ Отчёт отправлен через бота @{me.username}!")
            await client.disconnect()
            return True

        except Exception as e:
            log_warning(f"[BOT] Не удалось через {source}: {type(e).__name__}")
            try:
                await client.disconnect()
            except:
                pass
            cleanup_session("bot_notify_session")
            continue

    log_error("[BOT] Не удалось отправить через бота ни одним способом")
    return False


# Старая функция — оставлена для совместимости
async def send_notification_via_telethon(client: TelegramClient, scraped_count: int, working_proxies: list[str] = []):
    """
    Устарело: отправляет через user-клиент (в Избранное).
    Используйте send_report_via_bot() для отправки через бота.
    """
    if not YOUR_CHAT_ID:
        log_warning("Chat ID не настроен, пропускаю уведомление")
        return False

    try:
        chat_id = YOUR_CHAT_ID
        # Если числовая строка — конвертируем в int, иначе оставляем @username
        if chat_id.lstrip('-').isdigit():
            chat_id = int(chat_id)
        working_count = len(working_proxies)

        # Формируем сообщение
        if working_count > 0:
            message = f"""
🔍 <b>Проверка прокси завершена</b>

📊 <b>Результаты:</b>
   • Найдено: {scraped_count}
   • Рабочих: {working_count} ✅
   • Мёртвых: {scraped_count - working_count} ❌

🔗 <b>Рабочие прокси (нажми для подключения):</b>
"""
            # Добавляем первые 10 рабочих прокси ссылками
            for i, proxy in enumerate(working_proxies[:10], 1):
                # Извлекаем host и port для отображения
                try:
                    pattern = r"server=([^&]+)&port=(\d+)"
                    match = re.search(pattern, proxy)
                    if match:
                        host, port = match.groups()
                        message += f"\n{i}. <a href='{proxy}'>{host}:{port}</a>"
                    else:
                        message += f"\n{i}. <a href='{proxy}'>Прокси #{i}</a>"
                except:
                    message += f"\n{i}. <a href='{proxy}'>Прокси #{i}</a>"
            
            if working_count > 10:
                message += f"\n\n... и ещё {working_count - 10} в файле {WORKING_FILE}"
            
            message += f"""

📁 <b>Файлы:</b>
   • Все: {SCRAPED_FILE}
   • Рабочие: {WORKING_FILE}

⏰ {datetime.now().strftime("%d.%m.%Y %H:%M")}
            """.strip()
            
        else:
            # Уведомление только о скрапинге (без рабочих прокси)
            message = f"""
📥 <b>Скрапинг прокси завершён</b>

📊 Найдено прокси: {scraped_count}
📁 Файл: {SCRAPED_FILE}

⏰ {datetime.now().strftime("%d.%m.%Y %H:%M")}

Запусти с --check для проверки!
            """.strip()
        
        # Отправляем через Telethon
        log(f"[NOTIFY] Отправляю сообщение в chat_id={chat_id}...")
        log(f"[NOTIFY] Длина сообщения: {len(message)} символов")
        try:
            await asyncio.wait_for(
                client.send_message(chat_id, message, parse_mode='html'),
                timeout=30
            )
            log_success(f"✅ Уведомление отправлено! (рабочих прокси: {working_count})")
            return True
        except asyncio.TimeoutError:
            log_error("Таймаут отправки уведомления (30с)")
            return False
        
    except Exception as e:
        log_error(f"Не удалось отправить уведомление: {type(e).__name__}: {e}")
        return False
# ======================================================


# ==================== СОХРАНЕНИЕ ====================
def save_proxies(proxies: list[str], filename: str):
    """Сохраняет прокси в файл."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(proxies))
    log(f"Сохранено в {filename}")


def load_proxies(filename: str) -> list[str]:
    """Загружает прокси из файла."""
    if not os.path.exists(filename):
        return []

    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def save_best_proxy(proxy_url: str, latency: float):
    """Сохраняет лучший прокси (делегат к OutputManager + legacy файл)."""
    # Legacy файл (для обратной совместимости)
    with open(BEST_PROXY_FILE, "w", encoding="utf-8") as f:
        f.write(f"{proxy_url}|{latency}")
    # Новый формат в data/
    output.save_best(proxy_url, latency)
    log(f"Лучший прокси сохранён: {proxy_url[:50]}... ({latency:.2f} мс)")


def save_intermediate_results(working_with_latency: list[tuple], proxy_records: list):
    """
    Промежуточное сохранение — обновляет файлы во время массовой проверки.
    Разделяет на быстрые и запасные.
    """
    fast = [(u, l) for u, l in working_with_latency if classify_proxy(u, l) == "fast"]
    backup = [(u, l) for u, l in working_with_latency if classify_proxy(u, l) == "backup"]

    fast_urls = [p[0] for p in fast]
    backup_urls = [p[0] for p in backup]

    if fast_urls:
        save_proxies(fast_urls, WORKING_FILE)
        output.update_txt_list(fast_urls)

        # Обновляем лучший
        fast.sort(key=lambda x: x[1])
        best_proxy, best_latency = fast[0]
        save_best_proxy(best_proxy, best_latency)
    else:
        save_proxies([], WORKING_FILE)
        output.update_txt_list([])

    if backup_urls:
        save_proxies(backup_urls, BACKUP_FILE)

    # Генерируем отчёт с текущими данными
    if proxy_records:
        output.generate_markdown_report(proxy_records)


def classify_proxy(proxy_url: str, latency: float) -> str:
    """
    Классифицирует прокси по скорости.
    Returns: 'fast', 'backup', или 'dead'
    """
    if latency <= BACKUP_PING_THRESHOLD:
        return "fast"
    return "backup"


def load_best_proxy() -> tuple[str, float] | None:
    """Загружает лучший прокси (сначала из data/, потом из legacy)."""
    # Сначала пробуем новый формат
    best = output.load_best()
    if best:
        return best

    # Fallback на legacy файл
    if not os.path.exists(BEST_PROXY_FILE):
        return None

    try:
        with open(BEST_PROXY_FILE, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if "|" in data:
                proxy, latency = data.split("|", 1)
                return proxy, float(latency)
    except:
        pass
    return None


def get_proxy_latency(proxy_url: str, working_proxies: list[tuple]) -> float:
    """Получает задержку прокси из списка проверенных."""
    for proxy, latency in working_proxies:
        if proxy == proxy_url:
            return latency
    return float('inf')


# ==================== СБОР И РЕ-ПРОВЕРКА ПРОКСИ ИЗ ФАЙЛОВ ====================
def collect_all_proxies() -> list[str]:
    """
    Собирает все уникальные прокси из ВСЕХ источников (КРОМЕ queue.txt).
    queue.txt — это новые ещё не проверенные, их не нужно ре-чекать.
    Источники:
      - scraped_proxies.txt (новые из каналов)
      - working_mtproto.txt (проверенные ранее)
      - data/working_list.txt (новый формат)
    Возвращает дедуплицированный список.
    """
    all_proxies = []
    seen = set()

    for source in [WORKING_FILE, BACKUP_FILE, str(output.working_list_file)]:
        proxies = load_proxies(source)
        for p in proxies:
            if p not in seen:
                seen.add(p)
                all_proxies.append(p)

    log(f"📦 Собрано старых прокси для ре-проверки: {len(all_proxies)}")
    return all_proxies


async def recheck_working_proxies() -> tuple[list[str], list[tuple], list[str]]:
    """
    Проверяет все старые прокси из файлов.
    Нерабочие удаляет, рабочие возвращает с обновлёнными задержками.

    Returns:
        (working_urls, working_with_latency, failed_urls)
    """
    old_proxies = collect_all_proxies()

    if not old_proxies:
        log("Нет старых прокси для ре-проверки")
        return [], []

    log(f"\n🔄 Ре-проверка {len(old_proxies)} старых прокси...")
    log("-" * 85)
    log(f"{'Время':<20} | {'Статус':<6} | {'Прокси':<35} | {'Задержка':<12}")
    log("-" * 85)

    working_with_latency = []
    failed_urls = []
    removed_count = 0

    for proxy in old_proxies:
        success, latency, message = await check_proxy(proxy)

        timestamp = datetime.now().strftime("%H:%M:%S")
        status = "OK" if success else "FAIL"

        try:
            host, port, _ = parse_proxy(proxy)
            proxy_display = f"{host}:{port}"
        except:
            proxy_display = proxy[:35]

        if len(proxy_display) > 35:
            proxy_display = proxy_display[:32] + "..."

        log(f"{timestamp:<20} | {status:<6} | {proxy_display:<35} | {latency:>8.2f} мс")

        if success:
            working_with_latency.append((proxy, latency))
        else:
            failed_urls.append(proxy)
            removed_count += 1

    log("-" * 85)
    log(f"Ре-проверка: ✅ {len(working_with_latency)} | ❌ Удалено: {removed_count}")

    # Обновляем все файлы с рабочими прокси
    working_urls = [p[0] for p in working_with_latency]

    if working_urls:
        # Legacy
        save_proxies(working_urls, WORKING_FILE)
        # Новый формат
        output.update_txt_list(working_urls)

        # Обновляем лучший
        working_with_latency.sort(key=lambda x: x[1])
        best_proxy, best_latency = working_with_latency[0]
        save_best_proxy(best_proxy, best_latency)
    else:
        # Очищаем файлы если все прокси умерли
        save_proxies([], WORKING_FILE)
        output.update_txt_list([])
        log_warning("Все старые прокси умерли, файлы очищены")

    return working_urls, working_with_latency, failed_urls
# ======================================================


# ==================== MAIN ====================
async def main():
    parser = argparse.ArgumentParser(description="MTProto Proxy Scraper & Checker")
    parser.add_argument("--scrape", action="store_true", help="Скрапить прокси из каналов")
    parser.add_argument("--check", action="store_true", help="Проверить прокси из файла")
    parser.add_argument("--all", action="store_true", help="Скрапить и проверить")
    parser.add_argument("--notify", action="store_true", help="Отправить отчёт через бота (добавляется к любому флагу)")
    parser.add_argument("--report", action="store_true", help="Только отправить рабочие прокси из файла через бота (без проверки)")
    args = parser.parse_args()

    # Если нет аргументов, показываем помощь
    if not any([args.scrape, args.check, args.all, args.notify, args.report]):
        parser.print_help()
        return

    # --report standalone: просто отправить прокси из файла через бота
    if args.report and not any([args.scrape, args.check, args.all]):
        log("=" * 60)
        log("ОТПРАВКА РАБОЧИХ ПРОКСИ ЧЕРЕЗ БОТА")
        log("=" * 60)

        working = load_proxies(WORKING_FILE)
        backup = load_proxies(BACKUP_FILE)

        if not working and not backup:
            # Пробуем data/working_list.txt
            working = output.load_working_list()

        if not working and not backup:
            log_warning("Нет рабочих прокси в файлах!")
            return

        log(f"Быстрых: {len(working)}, Запасных: {len(backup)}")

        # Отправляем быстрые
        if working:
            await send_report_via_bot(working, len(working) + len(backup))

        # Если есть запасные — добавляем
        if backup:
            backup_msg = f"\n\n🐌 <b>Запасные прокси ({len(backup)} шт.):</b>\n"
            for i, proxy in enumerate(backup[:10], 1):
                try:
                    pattern = r"server=([^&]+)&port=(\d+)"
                    match = re.search(pattern, proxy)
                    if match:
                        host, port = match.groups()
                        backup_msg += f"\n{i}. <a href='{proxy}'>{host}:{port}</a>"
                    else:
                        backup_msg += f"\n{i}. <a href='{proxy}'>Запасной #{i}</a>"
                except:
                    backup_msg += f"\n{i}. <a href='{proxy}'>Запасной #{i}</a>"

            if len(backup) > 10:
                backup_msg += f"\n\n... и ещё {len(backup) - 10} в файле {BACKUP_FILE}"

            # Отправляем как второе сообщение
            client = TelegramClient(
                session="bot_notify_session",
                api_id=6,
                api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e",
            )
            try:
                await client.start(bot_token=BOT_TOKEN)
                chat_id = YOUR_CHAT_ID
                if chat_id.lstrip('-').isdigit():
                    chat_id = int(chat_id)
                await client.send_message(chat_id, backup_msg.strip(), parse_mode='html')
                log_success(f"✅ Запасные прокси отправлены ({len(backup)} шт.)")
            except Exception as e:
                log_error(f"Ошибка отправки запасных: {e}")
            finally:
                await client.disconnect()
                for ext in [".session", ".session-journal"]:
                    try:
                        os.remove(f"bot_notify_session{ext}")
                    except:
                        pass

        return
    
    # Проверка настроек
    if API_ID == 0 or not API_HASH:
        log_error("Настрой API_ID и API_HASH в .env!")
        log_error("Получи на https://my.telegram.org/apps")
        return

    if not PHONE:
        log_error("Настрой PHONE в .env!")
        return

    # Подключение
    log("=" * 60)
    log("MTProto Proxy Scraper & Checker")
    log("=" * 60)

    # Загружаем лучший прокси для использования в fallback логике
    best_proxy_data = load_best_proxy()
    connected = False
    is_bot_mode = False  # Если True — пропустить скрапинг (бот не читает каналы)

    client = TelegramClient(
        session="main_session",
        api_id=API_ID,
        api_hash=API_HASH,
    )

    # === ПОДКЛЮЧЕНИЕ ===
    # Приоритет: 1) User через прокси (нужен для скрапинга) → 2) Бот через прокси (fallback)
    proxy_list = []

    # Собираем все прокси в порядке приоритета
    if best_proxy_data:
        bp_url, bp_lat = best_proxy_data
        proxy_list.append((bp_url, "best_proxy.txt"))

    for source_file, label in [(str(output.working_list_file), "data/working_list.txt"), (WORKING_FILE, "working_mtproto.txt")]:
        if os.path.exists(source_file):
            for p in load_proxies(source_file):
                proxy_list.append((p, label))

    # Добавляем .env прокси
    if DEFAULT_PROXY_HOST and DEFAULT_PROXY_PORT and DEFAULT_PROXY_SECRET:
        env_proxy_url = f"https://t.me/proxy?server={DEFAULT_PROXY_HOST}&port={DEFAULT_PROXY_PORT}&secret={DEFAULT_PROXY_SECRET}"
        proxy_list.append((env_proxy_url, ".env"))

    # 1. Сначала пробуем user-подключение через каждый прокси
    tried = set()
    for proxy_url, source_label in proxy_list:
        if connected:
            break
        key = proxy_key(proxy_url)
        if key in tried:
            continue
        tried.add(key)

        try:
            host, port, secret_hex = parse_proxy(proxy_url)

            client = TelegramClient(
                session="main_session",
                api_id=API_ID,
                api_hash=API_HASH,
                proxy=(host, int(port), secret_hex),
                connection=ConnectionTcpMTProxyRandomizedIntermediate,
            )

            log(f"📡 User через {host}:{port} (из {source_label})...")
            await client.connect()
            if await client.is_user_authorized():
                me = await client.get_me()
                log_success(f"✅ Подключено как USER через {host}:{port}! {me.first_name} (@{me.username or 'no username'})")
                connected = True
                save_best_proxy(proxy_url, 0)
            else:
                log_warning(f"  Сессия не авторизована, нужен ввод кода — пропускаю")
                await client.disconnect()
        except Exception as e2:
            log_warning(f"  Не подошёл {host}:{port}: {type(e2).__name__}")
            try:
                await client.disconnect()
            except:
                pass
            continue

    # 2. Если user не подключился — пробуем бот
    if not connected and BOT_TOKEN:
        for proxy_url, source_label in proxy_list:
            if connected:
                break
            key = proxy_key(proxy_url)
            if key in tried:
                continue
            tried.add(key)

            try:
                host, port, secret_hex = parse_proxy(proxy_url)

                client = TelegramClient(
                    session="main_session",
                    api_id=6,
                    api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e",
                    proxy=(host, int(port), secret_hex),
                    connection=ConnectionTcpMTProxyRandomizedIntermediate,
                )

                log(f"📡 Бот через {host}:{port} (из {source_label})...")
                await client.connect()
                await client.start(bot_token=BOT_TOKEN)
                me = await client.get_me()
                log_success(f"✅ Бот подключён через {host}:{port}! @{me.username}")
                connected = True
                is_bot_mode = True
                save_best_proxy(proxy_url, 0)
            except Exception as e2:
                log_warning(f"  Не подошёл {host}:{port}: {type(e2).__name__}")
                try:
                    await client.disconnect()
                except:
                    pass
                continue

    if not connected:
        log_error("❌ Не удалось подключиться ни через один прокси!")
        log_error("   Подсказка: для скрапинга нужно user-подключение (введи код один раз)")
        return
    # === КОНЕЦ ПОДКЛЮЧЕНИЯ ===

    try:
        scraped_count = 0
        all_working_with_latency = []  # Список кортежей (proxy_url, latency)
        all_proxy_records = []  # Для отчёта: ProxyRecord

        # === РЕ-ПРОВЕРКА СТАРЫХ ПРОКСИ ===
        # При --all всегда проверяем старые прокси из файлов, удаляем мёртвые
        if args.all:
            log("\n" + "=" * 60)
            log("РЕ-ПРОВЕРКА СТАРЫХ ПРОКСИ ИЗ ФАЙЛОВ")
            log("=" * 60)

            old_working, old_working_with_latency, old_failed = await recheck_working_proxies()

            if old_working_with_latency:
                all_working_with_latency.extend(old_working_with_latency)
                for url, latency in old_working_with_latency:
                    all_proxy_records.append(OutputManager.parse_proxy_record(url, latency, status="OK"))
                log_success(f"Старых рабочих прокси: {len(old_working_with_latency)}")

            # Добавляем FAIL записи для отчёта
            for url in old_failed:
                all_proxy_records.append(OutputManager.parse_proxy_record(url, 0.0, status="FAIL"))

            if not old_working_with_latency:
                log_warning("Старых рабочих прокси не осталось")
        # === КОНЕЦ РЕ-ПРОВЕРКИ ===

        # Скрапинг
        if args.scrape or args.all:
            if is_bot_mode:
                log_warning("Бот не может читать каналы, пропускаю скрапинг")
            else:
                log("\n" + "=" * 60)
                log("СКРАПИНГ НОВЫХ ПРОКСИ")
                log("=" * 60)

                scraped = await scrape_proxies(client)
                scraped_count = len(scraped)

                if scraped:
                    save_proxies(scraped, SCRAPED_FILE)
                    # Сохраняем в очередь для проверки
                    save_proxies(scraped, QUEUE_FILE)
                    log_success(f"Сохранено {scraped_count} новых прокси в {SCRAPED_FILE}")
                    log_success(f"Добавлено {scraped_count} прокси в очередь {QUEUE_FILE}")
                else:
                    log_warning("Новые прокси не найдены")

        # Проверка новых прокси из очереди (или standalone --check)
        if args.check or args.all:
            # Загружаем прокси из очереди (новые, ещё не проверенные)
            queue_proxies = load_proxies(QUEUE_FILE)

            # Если очередь пуста — берём из scraped_proxies (обратная совместимость)
            # При standalone --check без --scrape — очередь может быть пуста, берём scraped
            if not queue_proxies and (args.check and not args.scrape):
                new_proxies = load_proxies(SCRAPED_FILE)
            elif queue_proxies:
                new_proxies = queue_proxies
            else:
                new_proxies = []

            # Исключаем те что уже проверены при ре-чеке
            already_checked = set(p[0] for p in all_working_with_latency)
            proxies_to_check = [p for p in new_proxies if p not in already_checked]

            if not proxies_to_check:
                if args.scrape or args.all:
                    log_warning("Нет новых прокси для проверки (все уже проверены при ре-чеке)")
                else:
                    log_warning("Нет прокси для проверки! Запусти --scrape или положи прокси в queue.txt")
            else:
                log("\n" + "=" * 60)
                log(f"ПРОВЕРКА {len(proxies_to_check)} НОВЫХ ПРОКСИ ИЗ ОЧЕРЕДИ")
                log("=" * 60)

                log(f"{'Время':<20} | {'Статус':<6} | {'Прокси':<35} | {'Задержка':<12}")
                log("-" * 85)

                for idx, proxy in enumerate(proxies_to_check, 1):
                    success, latency, message = await check_proxy(proxy, timeout=CHECK_TIMEOUT_FAST)

                    timestamp = datetime.now().strftime("%H:%M:%S")
                    status = "OK" if success else "FAIL"

                    try:
                        host, port, _ = parse_proxy(proxy)
                        proxy_display = f"{host}:{port}"
                    except:
                        proxy_display = proxy[:35]

                    if len(proxy_display) > 35:
                        proxy_display = proxy_display[:32] + "..."

                    log(f"{timestamp:<20} | {status:<6} | {proxy_display:<35} | {latency:>8.2f} мс")

                    if success:
                        all_working_with_latency.append((proxy, latency))
                        all_proxy_records.append(OutputManager.parse_proxy_record(proxy, latency, status="OK"))
                    else:
                        all_proxy_records.append(OutputManager.parse_proxy_record(proxy, latency, status="FAIL"))

                    # Промежуточное сохранение
                    if idx % CHECK_SAVE_INTERVAL == 0:
                        ok_so_far = len([p for p in all_working_with_latency])
                        fast_so_far = len([p for p in all_working_with_latency if classify_proxy(p[0], p[1]) == "fast"])
                        backup_so_far = ok_so_far - fast_so_far
                        log(f"\n  ⏳ Промежуточное сохранение ({idx}/{len(proxies_to_check)}): быстрых {fast_so_far}, запасных {backup_so_far}")
                        save_intermediate_results(all_working_with_latency, all_proxy_records)

                log("-" * 85)
                ok_count = len([p for p in all_proxy_records if p.status == 'OK' and p.url in proxies_to_check])
                fail_count = len([p for p in all_proxy_records if p.status == 'FAIL' and p.url in proxies_to_check])
                log(f"Итог: OK = {ok_count}, FAIL = {fail_count}")

                # Очищаем очередь после проверки
                save_proxies([], QUEUE_FILE)
                log(f"[QUEUE] Очередь очищена ({QUEUE_FILE})")

        # === СОХРАНЕНИЕ ВСЕХ РАБОЧИХ (старые + новые) ===
        # Выполняется всегда если есть результаты ре-чека или проверки

        # Разделяем на быстрые и запасные
        fast_proxies = []       # (url, latency) — быстрые
        backup_proxies = []     # (url, latency) — медленные, но живые

        for url, latency in all_working_with_latency:
            if classify_proxy(url, latency) == "fast":
                fast_proxies.append((url, latency))
            else:
                backup_proxies.append((url, latency))

        all_working_urls = [p[0] for p in fast_proxies]
        backup_urls = [p[0] for p in backup_proxies]

        if all_working_urls or backup_urls:
            # Быстрые прокси — в основной файл
            if all_working_urls:
                save_proxies(all_working_urls, WORKING_FILE)
                output.update_txt_list(all_working_urls)

                # === СОХРАНЯЕМ ЛУЧШИЙ ПРОКСИ ===
                fast_proxies.sort(key=lambda x: x[1])
                best_proxy, best_latency = fast_proxies[0]
                save_best_proxy(best_proxy, best_latency)
                log_success(f"🏆 Лучший прокси: {best_proxy[:50]}... ({best_latency:.2f} мс)")
                # === КОНЕЦ СОХРАНЕНИЯ ЛУЧШЕГО ===
            else:
                save_proxies([], WORKING_FILE)
                output.update_txt_list([])

            # Запасные прокси — в отдельный файл
            if backup_urls:
                save_proxies(backup_urls, BACKUP_FILE)
                log_success(f"🐌 Запасные прокси: {len(backup_urls)} → {BACKUP_FILE}")
            else:
                save_proxies([], BACKUP_FILE)

            log_success(f"📊 Рабочих (быстрых): {len(all_working_urls)}, Запасных: {len(backup_urls)}")

            # === TRIPLE EXPORT — ПОЛНЫЙ ОТЧЁТ ===
            output.generate_markdown_report(all_proxy_records, total_scraped=scraped_count)
            # === КОНЕЦ TRIPLE EXPORT ===
        else:
            # Все прокси умерли — очищаем файлы
            save_proxies([], WORKING_FILE)
            save_proxies([], BACKUP_FILE)
            output.update_txt_list([])
            log_warning("Все прокси мертвы, файлы очищены")
        # === КОНЕЦ СОХРАНЕНИЯ ===

        # Уведомление через бота
        if args.notify:
            log("\n" + "=" * 60)
            log("ОТПРАВКА ОТЧЁТА ЧЕРЕЗ БОТА")
            log("=" * 60)

            all_working = [p[0] for p in all_working_with_latency]
            total_checked = len(set(p.url for p in all_proxy_records) | set(p[0] for p in all_working_with_latency))

            if all_working:
                await send_report_via_bot(all_working, total_checked)
            else:
                log_warning("Нет рабочих прокси для отправки")

        log("\n" + "=" * 60)
        log("ГОТОВО")
        log("=" * 60)
        
    except Exception as e:
        log_error(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
