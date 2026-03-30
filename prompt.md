🚀 FINAL ARCHITECT PROMPT: MTPROTO HUNTER V2 (MODULAR)
Контекст: Разработка модульной системы на Python (Telethon 1.42+), учитывающей все ошибки из docs/PROXY_TROUBLESHOOTING.md.
1. Архитектура проекта (Раздельные файлы):

    .env — ключи API, токен бота и ID админов.
    config.py — загрузка .env, список каналов (см. ниже) и настройки таймаутов.
    utils/normalizer.py — функция нормализации секретов (ee, dd, base64) и выбор класса ConnectionTcpMTProxyRandomizedIntermediate.
    modules/scraper.py — мониторинг каналов и сбор сырых ссылок в queue.txt.
    modules/checker.py — независимый модуль проверки прокси с замером Latency.
    modules/notifier.py — отправка уведомлений через Bot API.
    main.py — точка входа, координирующая работу модулей.

2. Список актуальных каналов (CHANNELS):
['@ProxyMTProto', '@MTProto_Proxies_Free', '@MTP_roxy', '@Proxy_Telegram_MTProto', '@MTProto_Proxy_List', '@Telegram_Proxy_Server', '@V2Ray_MTProto', '@Proxy_MTProto_Telegram', '@MTProto_List', '@TeleProxy_New']
3. Логика «Лучшего прокси» и хранения:

    best_proxy.txt: Хранит только ОДИН прокси с минимальным пингом. Если при проверке новой пачки найден прокси быстрее текущего — файл перезаписывается.
    good_proxies.txt: Список всех рабочих прокси с пингом до 250мс.
    Уведомления в боте:
        Если найден прокси быстрее, чем в best_proxy.txt, бот шлет: 🌟 НОВЫЙ ЛУЧШИЙ ПРОКСИ! ⚡ Пинг: X мс | 🔗 Ссылка....
        Если прокси просто рабочий, но не побил рекорд: ✅ Хороший прокси | ⚡ Пинг: X мс | 🔗 Ссылка....

4. Технические требования (согласно TROUBLESHOOTING.md):

    Connection: Только RandomizedIntermediate для обхода блокировок.
    Secrets: Реализовать обработку всех форматов (с ee, dd, доменами).
    Timeouts: asyncio.wait_for на 10 сек для каждой проверки, чтобы избежать IncompleteReadError и TimeoutError.
    Flood Control: Автоматическая пауза при FloodWaitError.
    Тестируемость: Каждый класс должен иметь метод run(), чтобы его можно было запустить отдельно от других.

5. Задание:
Напиши код для каждого файла отдельно. Используй python-dotenv для конфигов. Убедись, что Скрапер использует best_proxy.txt для своего подключения, а если тот умрет — переключается на следующий из good_proxies.txt (Fallback цепочка).