"""
Output Manager — модуль сохранения результатов проверки прокси.

Экспортирует проверенные прокси в три формата внутри папки data/:
  - data/best_proxy.txt     — один лучший прокси (перезаписывается только при новом рекорде)
  - data/working_list.txt   — все рабочие прокси (полный список)
  - data/report.md          — человекочитаемая таблица в Markdown

Использует pathlib для кроссплатформенной работы с путями.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional


# Базовый путь — папка data/ в корне проекта (рядом с этим файлом)
DATA_DIR = Path(__file__).parent / "data"


class ProxyRecord:
    """Запись о проверенном прокси."""

    __slots__ = ("url", "host", "port", "latency_ms", "status", "sponsor", "checked_at", "error")

    def __init__(
        self,
        url: str,
        host: str = "",
        port: int = 0,
        latency_ms: float = 0.0,
        status: str = "FAIL",
        sponsor: str = "",
        checked_at: Optional[str] = None,
        error: str = "",
    ):
        self.url = url
        self.host = host
        self.port = port
        self.latency_ms = latency_ms
        self.status = status  # "OK" или "FAIL"
        self.sponsor = sponsor
        self.checked_at = checked_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.error = error

    @property
    def display_name(self) -> str:
        """Короткое имя для отображения (host:port или обрезанный URL)."""
        if self.host and self.port:
            return f"{self.host}:{self.port}"
        # Извлекаем host:port из URL если есть
        import re
        match = re.search(r"server=([^&]+)&port=(\d+)", self.url)
        if match:
            return f"{match.group(1)}:{match.group(2)}"
        return self.url[:40] + "..." if len(self.url) > 40 else self.url


class OutputManager:
    """
    Управляет записью результатов проверки прокси в три формата.

    Автоматически создаёт папку data/ при инициализации.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.best_proxy_file = self.data_dir / "best_proxy.txt"
        self.working_list_file = self.data_dir / "working_list.txt"
        self.report_file = self.data_dir / "report.md"

    # ==================== BEST PROXY ====================

    def save_best(self, proxy_url: str, latency: float) -> bool:
        """
        Сохраняет прокси как лучший ТОЛЬКО если его пинг меньше
        текущего рекорда в файле. Если файла нет или он пуст — записывает.

        Returns:
            True если запись произошла, False если новый прокси не лучше.
        """
        current_best_latency = self._load_best_latency()

        if current_best_latency is None or latency < current_best_latency:
            self.best_proxy_file.write_text(f"{proxy_url}|{latency}", encoding="utf-8")
            print(f"[OK] Новый лучший прокси: {proxy_url[:50]}... ({latency:.2f} мс)")
            return True

        print(f"[INFO] Прокси {proxy_url[:40]}... ({latency:.2f} мс) не лучше текущего ({current_best_latency:.2f} мс)")
        return False

    def load_best(self) -> Optional[tuple[str, float]]:
        """Загружает лучший прокси и его задержку."""
        if not self.best_proxy_file.exists():
            return None

        try:
            data = self.best_proxy_file.read_text(encoding="utf-8").strip()
            if "|" in data:
                proxy, latency_str = data.split("|", 1)
                return proxy, float(latency_str)
        except Exception:
            pass
        return None

    def _load_best_latency(self) -> Optional[float]:
        """Возвращает задержку текущего лучшего прокси или None."""
        best = self.load_best()
        return best[1] if best else None

    # ==================== WORKING LIST ====================

    def update_txt_list(self, proxy_urls: list[str]) -> None:
        """
        Полностью перезаписывает файл рабочих прокси.
        Каждый прокси — одна строка (ссылка t.me/proxy?...).
        """
        content = "\n".join(proxy_urls)
        self.working_list_file.write_text(content, encoding="utf-8")
        print(f"[OK] Обновлён рабочий список: {len(proxy_urls)} прокси → {self.working_list_file}")

    def load_working_list(self) -> list[str]:
        """Загружает список рабочих прокси из файла."""
        if not self.working_list_file.exists():
            return []

        lines = self.working_list_file.read_text(encoding="utf-8").splitlines()
        return [line.strip() for line in lines if line.strip()]

    # ==================== MARKDOWN REPORT ====================

    def generate_markdown_report(
        self,
        proxies: list[ProxyRecord],
        total_scraped: int = 0,
    ) -> None:
        """
        Генерирует человекочитаемый отчёт в Markdown.

        Колонки: Статус | Ссылка | Пинг (мс) | Стабильность (Jitter) | Спонсор | Время проверки
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        working_count = sum(1 for p in proxies if p.status == "OK")
        failed_count = len(proxies) - working_count

        # Вычисляем jitter (разброс задержек среди рабочих)
        latencies = [p.latency_ms for p in proxies if p.status == "OK"]
        if len(latencies) >= 2:
            avg_latency = sum(latencies) / len(latencies)
            jitter = max(latencies) - min(latencies)
            jitter_label = f"{jitter:.0f} мс"
        elif len(latencies) == 1:
            avg_latency = latencies[0]
            jitter_label = "— (1 прокси)"
        else:
            avg_latency = 0
            jitter_label = "— (нет рабочих)"

        # Заголовок
        lines = [
            "# 📊 Отчёт проверки MTProto прокси\n",
            f"**Дата:** {now}  ",
            f"**Всего проверено:** {len(proxies)}  ",
            f"**Рабочих:** {working_count} ✅  ",
            f"**Мёртвых:** {failed_count} ❌  ",
            f"**Средний пинг:** {avg_latency:.0f} мс  ",
            f"**Стабильность (Jitter):** {jitter_label}\n",
            "---\n",
        ]

        # Таблица
        lines.append(
            "| # | Статус | Ссылка | Пинг (мс) | Стабильность | Спонсор | Время проверки |"
        )
        lines.append(
            "|---|--------|--------|-----------|--------------|---------|----------------|"
        )

        for i, proxy in enumerate(proxies, 1):
            status_emoji = "✅" if proxy.status == "OK" else "❌"
            status_badge = f"{status_emoji} {proxy.status}"

            # Кликабельная ссылка
            display = proxy.display_name
            link = f"[{display}]({proxy.url})"

            # Пинг
            ping_str = f"{proxy.latency_ms:.0f}" if proxy.status == "OK" else "—"

            # Стабильность (jitter относительно среднего)
            if proxy.status == "OK" and len(latencies) >= 2:
                deviation = abs(proxy.latency_ms - avg_latency)
                if deviation < avg_latency * 0.2:
                    stability = "⚡ Высокая"
                elif deviation < avg_latency * 0.5:
                    stability = "🟡 Средняя"
                else:
                    stability = "🔴 Низкая"
            elif proxy.status == "FAIL":
                stability = "—"
            else:
                stability = "— (1 прокси)"

            sponsor = proxy.sponsor if proxy.sponsor else "—"
            time_str = proxy.checked_at

            lines.append(
                f"| {i} | {status_badge} | {link} | {ping_str} | {stability} | {sponsor} | {time_str} |"
            )

        # Подвал
        lines.extend([
            "\n---\n",
            f"*Сгенерировано автоматически • {now}*\n",
        ])

        content = "\n".join(lines)
        self.report_file.write_text(content, encoding="utf-8")
        print(f"[OK] Отчёт сохранён: {self.report_file}")

    # ==================== LOAD ALL REPORTS ====================

    @staticmethod
    def parse_proxy_record(proxy_url: str, latency: float = 0.0, status: str = "OK", sponsor: str = "") -> ProxyRecord:
        """
        Создаёт ProxyRecord из URL и метрик.
        Автоматически извлекает host/port из ссылки.
        """
        import re
        host, port = "", 0
        match = re.search(r"server=([^&]+)&port=(\d+)", proxy_url)
        if match:
            host = match.group(1)
            port = int(match.group(2))

        return ProxyRecord(
            url=proxy_url,
            host=host,
            port=port,
            latency_ms=latency,
            status=status,
            sponsor=sponsor,
        )
