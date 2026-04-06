"""
Нормализация MTProto секретов и парсинг ссылок
Согласно PROXY_TROUBLESHOOTING.md
"""
import base64
import re
from typing import Optional


def normalize_secret(secret: str) -> str:
    """
    Нормализует secret до 32 hex-символов (16 байт).
    
    Алгоритм:
    1. Удаляем префиксы ee/dd
    2. Извлекаем только hex часть (до домена или не-hex символов)
    3. Обрезаем до 32 символов
    4. Возвращаем как hex-строку
    
    Args:
        secret: Исходный secret (может содержать ee/dd, домен, base64)
    
    Returns:
        Нормализованный hex-секрет (32 символа)
    """
    if not secret:
        return "0" * 32
    
    secret = secret.strip()
    
    # Удаляем префиксы ee/dd (регистронезависимо)
    if len(secret) >= 2 and secret[:2].lower() in ("ee", "dd"):
        secret = secret[2:]
    
    # Извлекаем только hex часть (до домена или других символов)
    hex_part = ""
    for char in secret:
        if char in "0123456789abcdefABCDEF":
            hex_part += char
        else:
            break  # Нашли не-hex символ (начало домена)
    
    # Если hex часть пустая, пробуем base64
    if not hex_part:
        try:
            # Добавляем padding для base64
            padded = secret + "=" * (-len(secret) % 4)
            decoded = base64.b64decode(padded)
            hex_part = decoded.hex()
        except Exception:
            return "0" * 32
    
    # Обрезаем до 32 символов (16 байт)
    return hex_part[:32].lower()


def parse_proxy_url(url: str) -> Optional[dict]:
    """
    Парсит MTProto ссылку в формат прокси.
    
    Поддерживаемые форматы:
    - tg://proxy?server=host&port=1234&secret=xxx
    - tg://proxy?server=host&port=1234&secret=ee...
    - https://t.me/proxy?server=host&port=1234&secret=xxx
    
    Args:
        url: Ссылка на прокси
    
    Returns:
        Dict с ключами: host, port, secret, url (исходная ссылка)
        или None если не удалось распарсить
    """
    if not url:
        return None
    
    url = url.strip()
    
    # Извлекаем часть после tg://proxy? или https://t.me/proxy?
    pattern = r"(?:tg://proxy|https://t\.me/proxy)\?(.+)"
    match = re.match(pattern, url, re.IGNORECASE)
    
    if not match:
        # Пробуем найти ссылку в тексте
        url_match = re.search(
            r"(tg://proxy\?[^\s]+|https://t\.me/proxy\?[^\s]+)",
            url,
            re.IGNORECASE
        )
        if url_match:
            url = url_match.group(1)
            match = re.match(pattern, url, re.IGNORECASE)
        if not match:
            return None
    
    # Парсим параметры
    params = {}
    query = match.group(1)
    
    # Разбираем query string
    for pair in query.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            key = key.strip().lower()
            value = value.strip()
            
            # URL decode для value
            value = value.replace("%3D", "=")
            
            params[key] = value
    
    # Извлекаем обязательные поля
    host = params.get("server") or params.get("host")
    port_str = params.get("port")
    secret = params.get("secret", "")
    
    if not host or not port_str:
        return None
    
    try:
        port = int(port_str)
    except ValueError:
        return None
    
    # Нормализуем secret
    normalized_secret = normalize_secret(secret)
    
    return {
        "host": host,
        "port": port,
        "secret": normalized_secret,
        "raw_secret": secret,
        "url": url
    }


def extract_proxy_links(text: str) -> list[dict]:
    """
    Извлекает все MTProto ссылки из текста.
    
    Args:
        text: Текст сообщения
    
    Returns:
        Список словарей с информацией о прокси
    """
    if not text:
        return []
    
    proxies = []
    seen = set()
    
    # Паттерн для tg://proxy и https://t.me/proxy
    pattern = r"(tg://proxy\?[^\s\"<>]+|https://t\.me/proxy\?[^\s\"<>]+)"
    
    for match in re.finditer(pattern, text, re.IGNORECASE):
        url = match.group(1)
        # Убираем возможные хвосты
        url = url.rstrip(".,;:!?)")
        
        if url in seen:
            continue
        seen.add(url)
        
        proxy_data = parse_proxy_url(url)
        if proxy_data:
            proxies.append(proxy_data)
    
    return proxies


def proxy_to_url(host: str, port: int, secret: str) -> str:
    """
    Создаёт MTProto ссылку из параметров прокси.
    
    Args:
        host: Хост прокси
        port: Порт прокси
        secret: Secret прокси
    
    Returns:
        Ссылка tg://proxy
    """
    return f"tg://proxy?server={host}&port={port}&secret=ee{secret}"
