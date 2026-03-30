# 🚀 MTPROTO HUNTER V2

Модульная система поиска и проверки MTProto прокси для Telegram с поддержкой подписчиков.

## 📋 Возможности

- ✅ **Автоматический сбор** прокси из Telegram каналов
- ✅ **Проверка пинга** каждого прокси
- ✅ **Проверка на стабильность** (3 попытки подключения)
- ✅ **Уведомления в Telegram** о найденных прокси
- ✅ **Подписчики** — друзья могут подписаться на уведомления через бота
- ✅ **Работа через MTProto прокси** — обходит блокировки
- ✅ **Сохранение лучших прокси** в файлы

---

## 📁 Структура проекта

```
proxy_finderv2/
├── .env                    # Конфигурация (API ключи, токены)
├── .env.example            # Пример конфигурации
├── config.py               # Настройки и список каналов
├── main.py                 # Точка входа (поиск + уведомления)
├── bot.py                  # Бот для подписчиков
├── authorize.py            # Авторизация пользователя
├── requirements.txt        # Зависимости Python
├── utils/
│   └── normalizer.py       # Нормализация MTProto секретов
└── modules/
    ├── scraper.py          # Сбор прокси из каналов
    ├── checker.py          # Проверка прокси с замером пинга
    ├── stability_checker.py # Проверка на стабильность
    ├── notifier.py         # Уведомления через бота
    └── subscribers.py      # Управление подписчиками
```

---

## ⚙️ Установка

### 1. Установите зависимости

```bash
pip install -r requirements.txt
```

### 2. Заполните `.env`

Скопируйте `.env.example` в `.env` и заполните:

```env
# Telegram API (получить на https://my.telegram.org/apps)
API_ID=your_api_id_here
API_HASH=your_api_hash_here
PHONE=+79991234567

# Bot Token (получить от @BotFather)
BOT_TOKEN=your_bot_token_here

# Ваш ChatID (целое число! получить от @userinfobot)
YOUR_CHAT_ID=your_chat_id_here

# Прокси по умолчанию (опционально)
DEFAULT_PROXY_HOST=proxy_host
DEFAULT_PROXY_PORT=8080
DEFAULT_PROXY_SECRET=proxy_secret

# Настройки
MESSAGES_LIMIT=20
CHECK_TIMEOUT=10
PING_THRESHOLD=250
```

### 3. Пройдите авторизацию (один раз)

```bash
python authorize.py
```

Введите код из Telegram (от официального аккаунта с галочкой).

---

## 🚀 Запуск

### Основной режим (поиск + уведомления)

```bash
python main.py
```

**Что происходит:**
1. Скрапинг 6 каналов → ~190 прокси
2. Проверка пинга каждого прокси
3. Сохранение лучших в `best_proxy.txt` и `good_proxies.txt`
4. Отправка уведомлений вам в Telegram
5. Рассылка всем подписчикам (если есть)

### Непрерывный режим

В `main.py` раскомментируйте строку:

```python
await hunter.run_continuous(interval_minutes=30)
```

Запустите:
```bash
python main.py
```

### Бот для подписчиков

Запустите в **отдельном окне/терминале**:

```bash
python bot.py
```

**Что делает:**
- Отвечает на `/start`
- Автоматически добавляет пользователей в подписчики
- Присылает ссылку для подписки

---

## 👥 Система подписчиков

### Как добавить подписчика

1. **Запустите бота:**
   ```bash
   python bot.py
   ```

2. **Отправьте ссылку знакомым:**
   ```
   https://t.me/My_proxycheckerbot
   ```

3. **Они нажимают `/start`** в боте

4. **Готово!** При следующем запуске `python main.py` уведомления придут всем подписчикам

### Управление подписчиками

```bash
# Просмотр количества подписчиков
python -c "from modules.subscribers import get_manager; m = get_manager(); print(f'Подписчиков: {len(m)}')"

# Просмотр всех ID
python -c "from modules.subscribers import get_manager; m = get_manager(); print(m.get_all_ids())"

# Файл subscribers.json — полная база
```

---

## 📊 Файлы хранения

| Файл | Описание |
|------|----------|
| `best_proxy.txt` | Лучший прокси (минимальный пинг) |
| `good_proxies.txt` | Все рабочие прокси (пинг ≤ 250мс) |
| `queue.txt` | Очередь на проверку (временный) |
| `subscribers.json` | База подписчиков |
| `hunter.log` | Лог работы системы |

---

## 📝 Настройки

В `.env`:

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `MESSAGES_LIMIT` | 20 | Сообщений проверять в канале |
| `CHECK_TIMEOUT` | 10 | Таймаут проверки прокси (сек) |
| `PING_THRESHOLD` | 250 | Макс. пинг для "хорошего" прокси (мс) |

---

## 🔧 Отдельные модули

```bash
# Только сбор прокси
python -m modules.scraper

# Только проверка queue.txt
python -m modules.checker

# Только уведомления (тест)
python -m modules.notifier
```

---

## 📡 Каналы для мониторинга

По умолчанию:
- `@ProxyMTProto`
- `@MTProto_Proxies_Free`
- `@Proxy_Telegram_MTProto`
- `@MTProto_Proxy_List`
- `@Proxy_MTProto_Telegram`
- `@TeleProxy_New`

Изменить можно в `config.py`.

---

## ⚠️ Важно

1. **Не коммитьте `.env` и `.session` файлы!** Они в `.gitignore`.
2. **Пользователь должен начать диалог с ботом** (нажать `/start`) перед получением уведомлений.
3. **Бот работает через MTProto прокси** — не требует HTTP прокси.
4. **Первый запуск** требует ввода кода авторизации.

---

## 🛠️ Требования

- Python 3.10+
- Telethon 1.42+
- Рабочий MTProto прокси для подключения

---

## 📄 Лицензия

MIT

---

## 🆘 Troubleshooting

### Ошибка: "Не заполнен .env файл"
Заполните `.env` по примеру из `.env.example`

### Ошибка: "Требуется авторизация"
Запустите `python authorize.py` и введите код из Telegram

### Бот не отправляет уведомления
- Проверьте что нажали `/start` в боте
- Убедитесь что `YOUR_CHAT_ID` правильный (целое число!)
- Проверьте лог: `hunter.log`

### Прокси не находятся
- Некоторые каналы могут быть недоступны
- Увеличьте `MESSAGES_LIMIT` в `.env`

---

<div align="center">

**MTPROTO HUNTER V2** — Найдёт лучшие прокси автоматически! 🔍

</div>
