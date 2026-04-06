# MTProto Proxy Scraper & Checker

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Telethon 1.42+](https://img.shields.io/badge/telethon-1.42+-blue.svg)](https://github.com/LonamiWebs/Telethon)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Автоматический инструмент для поиска, проверки и мониторинга MTProto прокси в Telegram.

---

## 📖 Возможности

| Функция | Описание |
|---------|----------|
| 🔍 **Скрапинг** | Поиск прокси из 10 Telegram каналов + 3 GitHub источников |
| ✅ **Проверка** | Тестирование каждого прокси подключением с retry |
| 🐌 **Классификация** | Разделение на быстрые и запасные (backup) прокси |
| 📢 **Уведомления** | Отчёт через Telegram бота |
| 📝 **Отчёты** | Markdown таблица в `data/report.md` |
| 🔄 **Ре-чек** | Автоматическая проверка старых прокси при каждом запуске |
| 🗑️ **Дедупликация** | Пропуск уже известных прокси (host:port:secret) |
| 📋 **Очередь** | Новые прокси → `queue.txt` → проверка → очистка |

---

## 🚀 Быстрый старт

```bash
# 1. Установка зависимостей
pip install -r requirements.txt

# 2. Настройка
cp .env.example .env
# Отредактируй .env — вставь API ключи и телефон

# 3. Первая авторизация (код из Telegram)
python auth_user.py

# 4. Запуск
python main.py --all --notify
```

---

## ⚙️ Настройка (.env)

| Переменная | Обязательна | Описание |
|------------|-------------|----------|
| `API_ID` | ✅ | API ID от my.telegram.org |
| `API_HASH` | ✅ | API Hash от my.telegram.org |
| `PHONE` | ✅ | Номер телефона (+7...) |
| `BOT_TOKEN` | ❌ | Токен бота (для уведомлений) |
| `YOUR_CHAT_ID` | ❌ | ID или @username для уведомлений |
| `DEFAULT_PROXY_HOST` | ❌ | Прокси для подключения (если Telegram заблокирован) |
| `DEFAULT_PROXY_PORT` | ❌ | Порт прокси |
| `DEFAULT_PROXY_SECRET` | ❌ | Secret прокси |
| `MESSAGES_LIMIT` | ❌ | Сообщений на канал (по умолчанию: 20) |
| `CHECK_TIMEOUT` | ❌ | Таймаут ре-чека в секундах (по умолчанию: 30) |

### Получение API ключей

1. https://my.telegram.org/apps
2. Войти по номеру телефона
3. Создать приложение → скопировать `api_id` и `api_hash`

### Узнавание Chat ID

1. Написать боту [@userinfobot](https://t.me/userinfobot)
2. Вставить полученный ID в `YOUR_CHAT_ID`

---

## 💻 Команды

```bash
# Полный цикл: ре-чек старых + скрапинг + проверка новых + сохранение
python main.py --all

# Полный цикл + отчёт в Telegram бота
python main.py --all --notify

# Только скрапинг (добавить новые в очередь)
python main.py --scrape

# Только проверка очереди
python main.py --check

# Отправить рабочие прокси через бота (без проверки)
python main.py --report

# Определить свой Chat ID
python detect_chat_id.py

# Тестовое сообщение от бота
python bot_send_message.py
```

---

## 📁 Структура проекта

```
telegram-proxy-checker/
├── main.py                     # 🟢 Основной скрипт
├── auth_user.py                # Однократная авторизация (ввести код)
├── detect_chat_id.py           # Узнать свой Chat ID
├── bot_send_message.py         # Тестовая отправка от бота
├── output_manager.py           # Модуль экспорта (data/)
│
├── .env.example                # Шаблон настроек
├── .env                        # 🔴 Секреты (НЕ КОММИТЬ!)
├── .gitignore
├── requirements.txt
├── README.md
│
├── data/                       # 📤 Выходные данные OutputManager
│   ├── working_list.txt        # Рабочие прокси (новый формат)
│   ├── best_proxy.txt          # Лучший прокси
│   └── report.md               # Красивый отчёт в Markdown
│
├── logs/                       # 📋 Логи
│   └── checker.log
│
├── legacy/                     # 📦 Архив старых скриптов
├── tests/                      # 🧪 Тесты
├── telethon_lib/               # 📚 Vendored Telethon
│
├── sessions/                   # 🔐 Сессии (НЕ КОММИТЬ!)
├── output/                     # 📤 Legacy output
│
└── [генерируемые файлы]        # 🔴 НЕ КОММИТЬ!
    ├── working_mtproto.txt     # Быстрые рабочие прокси
    ├── backup_proxies.txt      # Медленные, но рабочие
    ├── scraped_proxies.txt     # Все найденные
    ├── best_proxy.txt          # Лучший (legacy)
    ├── queue.txt               # Очередь проверки
    └── *.session               # Сессии Telegram
```

---

## 📊 Форматы вывода

| Файл | Содержимое |
|------|-----------|
| `working_mtproto.txt` | Быстрые прокси (пинг ≤ 15 сек) |
| `backup_proxies.txt` | Медленные, но рабочие (пинг > 15 сек) |
| `data/working_list.txt` | Копия быстрых (новый формат) |
| `best_proxy.txt` | Самый быстрый прокси + latency |
| `data/report.md` | Таблица: Статус, Ссылка, Пинг, Jitter, Время |

---

## 🔄 Логика работы

```
1. ПОДКЛЮЧЕНИЕ
   User через прокси → если нет сессии → ввести код (1 раз)
   ↓
2. РЕ-ЧЕК СТАРЫХ
   Проверить working_mtproto.txt + backup_proxies.txt
   Мёртвые → удалить, рабочие → оставить
   ↓
3. СКРАПИНГ
   10 каналов + 3 GitHub → дедупликация → queue.txt
   ↓
4. ПРОВЕРКА НОВЫХ
   queue.txt → check each → быстрые / запасные
   queue.txt → очистить
   ↓
5. СОХРАНЕНИЕ
   working_mtproto.txt + backup_proxies.txt + data/ + report.md
   ↓
6. УВЕДОМЛЕНИЕ (если --notify)
   Отчёт через бота в Telegram
```

---

## ⚠️ Отказ от ответственности

Проект предоставляется "как есть". Автор не несёт ответственности за последствия использования.

---

<div align="center">

**Сделано с ❤️ для сообщества Telegram**

</div>
