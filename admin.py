# admin.py
# Список ID администраторов
ADMIN_IDS = {
    481825464,  # Ваш ID
    # Можно добавить другие ID через запятую
}

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

def get_admin_commands():
    """Возвращает список команд для администраторов"""
    return [
        "start", "help", "add", "delete", "cancel",
        "debug", "stats"
    ]

def get_user_commands():
    """Возвращает список команд для обычных пользователей"""
    return ["start", "help", "add", "cancel"]

def add_admin(user_id: int):
    """Добавляет администратора"""
    ADMIN_IDS.add(user_id)

def remove_admin(user_id: int):
    """Удаляет администратора"""
    ADMIN_IDS.discard(user_id)

def get_admin_ids() -> set:
    """Возвращает список ID администраторов"""
    return ADMIN_IDS.copy()


