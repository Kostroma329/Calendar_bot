# admin.py
# Список ID администраторов
ADMIN_IDS = {
    481825464,  # Замените на ваш Telegram ID
    # Можно добавить другие ID через запятую
}

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

def get_admin_commands() -> list:
    """Возвращает список команд для администраторов"""
    return ['start', 'delete', 'debug', 'stats']

def get_user_commands() -> list:
    """Возвращает список команд для обычных пользователей"""
    return ['start', 'delete']