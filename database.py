# database.py
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional
import logging
from contextlib import contextmanager

# Настройка логирования
logger = logging.getLogger(__name__)

DB_PATH = "events.db"


@contextmanager
def get_db_connection():
    """Контекстный менеджер для работы с БД"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def init_db():
    """Инициализация базы данных"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_datetime TEXT NOT NULL,
                location TEXT,
                dances TEXT,
                raw_text TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON events(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_datetime ON events(event_datetime)")

        conn.commit()
        logger.info("Database initialized successfully")


def add_event(user_id: int, event_datetime: datetime, location: Optional[str],
              dances: List[str], raw_text: str) -> bool:
    """Добавляет событие в базу данных"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events (user_id, event_datetime, location, dances, raw_text)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                event_datetime.isoformat(),
                location or "",
                ",".join(dances) if dances else "",
                raw_text
            ))
            conn.commit()
            logger.info(f"Event added for user {user_id} at {event_datetime}")
            return True
    except Exception as e:
        logger.error(f"Error adding event for user {user_id}: {e}")
        return False


def get_upcoming_events(user_id: int, limit: int = 50) -> List:
    """Получает предстоящие события пользователя"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, event_datetime, location, dances, raw_text
                FROM events 
                WHERE user_id = ? AND event_datetime >= ?
                ORDER BY event_datetime ASC
                LIMIT ?
            """, (user_id, datetime.now().isoformat(), limit))
            rows = cursor.fetchall()

            result = []
            for row in rows:
                result.append((
                    row['id'],
                    row['event_datetime'],
                    row['location'],
                    row['dances'],
                    row['raw_text']
                ))
            return result
    except Exception as e:
        logger.error(f"Error getting events for user {user_id}: {e}")
        return []


def get_events_for_notification(user_id: int, target_date: datetime) -> List:
    """Получает события пользователя на указанную дату (для уведомлений)"""
    try:
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, event_datetime, location, dances, raw_text
                FROM events 
                WHERE user_id = ? AND event_datetime BETWEEN ? AND ?
                ORDER BY event_datetime ASC
            """, (user_id, start_of_day.isoformat(), end_of_day.isoformat()))
            rows = cursor.fetchall()

            result = []
            for row in rows:
                result.append((
                    row['id'],
                    row['event_datetime'],
                    row['location'],
                    row['dances'],
                    row['raw_text']
                ))
            return result
    except Exception as e:
        logger.error(f"Error getting events for notification for user {user_id}: {e}")
        return []


def get_all_events(user_id: int) -> List:
    """Получает ВСЕ события пользователя (для отладки)"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, event_datetime, location, dances, raw_text
                FROM events 
                WHERE user_id = ?
                ORDER BY event_datetime ASC
            """, (user_id,))
            rows = cursor.fetchall()

            result = []
            for row in rows:
                result.append((
                    row['id'],
                    row['event_datetime'],
                    row['location'],
                    row['dances'],
                    row['raw_text']
                ))
            return result
    except Exception as e:
        logger.error(f"Error getting all events for user {user_id}: {e}")
        return []


def get_events_by_date_range(user_id: int, start_date: datetime, end_date: datetime) -> List:
    """Получает события пользователя за указанный период"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, event_datetime, location, dances, raw_text
                FROM events 
                WHERE user_id = ? 
                AND event_datetime BETWEEN ? AND ?
                ORDER BY event_datetime ASC
            """, (user_id, start_date.isoformat(), end_date.isoformat()))
            rows = cursor.fetchall()

            result = []
            for row in rows:
                result.append((
                    row['id'],
                    row['event_datetime'],
                    row['location'],
                    row['dances'],
                    row['raw_text']
                ))
            return result
    except Exception as e:
        logger.error(f"Error getting events for date range: {e}")
        return []


def delete_event(event_id: int) -> bool:
    """Удаляет событие"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
            conn.commit()
            logger.info(f"Event {event_id} deleted")
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error deleting event {event_id}: {e}")
        return False


def get_today_events(user_id: int) -> List:
    """Получает события на сегодня"""
    try:
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        return get_events_by_date_range(user_id, today_start, today_end)
    except Exception as e:
        logger.error(f"Error getting today's events: {e}")
        return []