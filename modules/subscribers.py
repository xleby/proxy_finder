"""
Subscribers — управление подписчиками бота
Сохраняет ID пользователей которые написали боту
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

SUBSCRIBERS_FILE = "subscribers.json"


class SubscribersManager:
    """
    Менеджер подписчиков бота.
    
    Хранит:
    - ID пользователей
    - Дату подписки
    - Имя пользователя (если доступно)
    """
    
    def __init__(self, subscribers_file: str = SUBSCRIBERS_FILE):
        self.file_path = Path(subscribers_file)
        self.subscribers: Dict[int, Dict] = {}
        self.load()
    
    def load(self):
        """Загружает подписчиков из файла."""
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Конвертируем ключи из строк в int
                    self.subscribers = {int(k): v for k, v in data.items()}
                logger.info(f"Загружено {len(self.subscribers)} подписчиков")
            except Exception as e:
                logger.error(f"Ошибка загрузки подписчиков: {e}")
                self.subscribers = {}
        else:
            self.subscribers = {}
            logger.info("Файл подписчиков не найден, создаём новый")
    
    def save(self):
        """Сохраняет подписчиков в файл."""
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.subscribers, f, indent=2, ensure_ascii=False)
            logger.debug(f"Сохранено {len(self.subscribers)} подписчиков")
        except Exception as e:
            logger.error(f"Ошибка сохранения подписчиков: {e}")
    
    def add_subscriber(self, user_id: int, username: str = None, first_name: str = None):
        """
        Добавляет подписчика.
        
        Args:
            user_id: Telegram ID пользователя
            username: Username пользователя (@username)
            first_name: Имя пользователя
        """
        if user_id not in self.subscribers:
            self.subscribers[user_id] = {
                "subscribed_at": datetime.now().isoformat(),
                "username": username,
                "first_name": first_name,
                "messages_sent": 0
            }
            logger.info(f"Новый подписчик: {first_name or user_id} (@{username or 'no username'})")
            self.save()
            return True
        
        # Обновляем информацию если изменилась
        sub = self.subscribers[user_id]
        if username and sub.get("username") != username:
            sub["username"] = username
        if first_name and sub.get("first_name") != first_name:
            sub["first_name"] = first_name
        self.save()
        return False
    
    def remove_subscriber(self, user_id: int) -> bool:
        """Удаляет подписчика."""
        if user_id in self.subscribers:
            del self.subscribers[user_id]
            self.save()
            logger.info(f"Подписчик {user_id} удалён")
            return True
        return False
    
    def get_all_ids(self) -> List[int]:
        """Возвращает список всех ID подписчиков."""
        return list(self.subscribers.keys())
    
    def get_subscriber(self, user_id: int) -> Dict:
        """Возвращает информацию о подписчике."""
        return self.subscribers.get(user_id, {})
    
    def increment_messages(self, user_id: int):
        """Увеличивает счётчик отправленных сообщений."""
        if user_id in self.subscribers:
            self.subscribers[user_id]["messages_sent"] = \
                self.subscribers[user_id].get("messages_sent", 0) + 1
            self.save()
    
    def __len__(self) -> int:
        """Возвращает количество подписчиков."""
        return len(self.subscribers)


# Глобальный экземпляр
_manager: SubscribersManager = None


def get_manager() -> SubscribersManager:
    """Возвращает глобальный менеджер подписчиков."""
    global _manager
    if _manager is None:
        _manager = SubscribersManager()
    return _manager


if __name__ == "__main__":
    # Тест
    manager = get_manager()
    print(f"Подписчиков: {len(manager)}")
    print(f"ID: {manager.get_all_ids()}")
