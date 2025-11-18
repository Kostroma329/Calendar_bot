# database.py
import os
import sqlite3
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Пытаемся импортировать psycopg2 для PostgreSQL
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("⚠️  psycopg2 не установлен. Используется SQLite.")

def get_connection():
    """Получение подключения к базе данных"""
    # Если на Render и есть PostgreSQL
    if os.getenv('RENDER') and PSYCOPG2_AVAILABLE:
        try:
            DATABASE_URL = os.getenv('DATABASE_URL')
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            return conn
        except Exception as e:
            print(f"❌ Ошибка подключения к PostgreSQL: {e}")
            print("🔄 Используется SQLite")
    
    # Локально или fallback на SQLite
    return sqlite3.connect("events.db", check_same_thread=False)

def init_db():
    """Инициализация базы данных"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Проверяем, используем ли мы PostgreSQL
    is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
    
    if is_postgresql:
        # PostgreSQL
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                event_datetime TIMESTAMP NOT NULL,
                location TEXT,
                dances TEXT,
                raw_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Таблица events создана в PostgreSQL")
    else:
        # SQLite
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_datetime TEXT NOT NULL,
                location TEXT,
                dances TEXT,
                raw_text TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Таблица events создана в SQLite")
    
    conn.commit()
    conn.close()

def add_event(user_id, event_datetime, location, dances, raw_text):
    """Добавление события в базу данных"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        dances_str = ", ".join(dances) if dances else None
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if is_postgresql:
            # PostgreSQL
            cursor.execute('''
                INSERT INTO events (user_id, event_datetime, location, dances, raw_text)
                VALUES (%s, %s, %s, %s, %s)
            ''', (user_id, event_datetime, location, dances_str, raw_text))
        else:
            # SQLite
            cursor.execute('''
                INSERT INTO events (user_id, event_datetime, location, dances, raw_text)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, event_datetime.isoformat(), location, dances_str, raw_text))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении события: {e}")
        return False

def get_upcoming_events_all():
    """Получение ВСЕХ предстоящих событий (для всех пользователей)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if is_postgresql:
            # PostgreSQL - все события
            cursor.execute('''
                SELECT id, event_datetime, location, dances, user_id
                FROM events 
                WHERE event_datetime >= %s
                ORDER BY event_datetime
            ''', (datetime.now(),))
        else:
            # SQLite - все события
            cursor.execute('''
                SELECT id, event_datetime, location, dances, user_id
                FROM events 
                WHERE event_datetime >= ?
                ORDER BY event_datetime
            ''', (datetime.now().isoformat(),))
        
        events = cursor.fetchall()
        conn.close()
        
        # Конвертируем даты для PostgreSQL
        if is_postgresql:
            events = [(ev[0], ev[1].isoformat(), ev[2], ev[3], ev[4]) for ev in events]
        
        return events
    except Exception as e:
        logger.error(f"❌ Ошибка при получении всех событий: {e}")
        return []

def get_today_events_all():
    """Получение ВСЕХ событий на сегодня (для всех пользователей)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().date()
        tomorrow = datetime(today.year, today.month, today.day + 1).date()
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if is_postgresql:
            # PostgreSQL - все события
            cursor.execute('''
                SELECT id, event_datetime, location, dances, user_id
                FROM events 
                WHERE event_datetime >= %s AND event_datetime < %s
                ORDER BY event_datetime
            ''', (today, tomorrow))
        else:
            # SQLite - все события
            cursor.execute('''
                SELECT id, event_datetime, location, dances, user_id
                FROM events 
                WHERE event_datetime >= ? AND event_datetime < ?
                ORDER BY event_datetime
            ''', (today.isoformat(), tomorrow.isoformat()))
        
        events = cursor.fetchall()
        conn.close()
        
        if is_postgresql:
            events = [(ev[0], ev[1].isoformat(), ev[2], ev[3], ev[4]) for ev in events]
        
        return events
    except Exception as e:
        logger.error(f"❌ Ошибка при получении сегодняшних событий: {e}")
        return []

def get_all_events(user_id=None):
    """Получение всех событий (для админов) или событий пользователя"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if user_id:
            # События конкретного пользователя
            if is_postgresql:
                cursor.execute('''
                    SELECT id, event_datetime, location, dances, user_id
                    FROM events 
                    WHERE user_id = %s
                    ORDER BY event_datetime
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT id, event_datetime, location, dances, user_id
                    FROM events 
                    WHERE user_id = ?
                    ORDER BY event_datetime
                ''', (user_id,))
        else:
            # Все события (для админов)
            if is_postgresql:
                cursor.execute('''
                    SELECT id, event_datetime, location, dances, user_id
                    FROM events 
                    ORDER BY event_datetime
                ''')
            else:
                cursor.execute('''
                    SELECT id, event_datetime, location, dances, user_id
                    FROM events 
                    ORDER BY event_datetime
                ''')
        
        events = cursor.fetchall()
        conn.close()
        
        if is_postgresql:
            events = [(ev[0], ev[1].isoformat(), ev[2], ev[3], ev[4]) for ev in events]
        
        return events
    except Exception as e:
        logger.error(f"❌ Ошибка при получении событий: {e}")
        return []
def get_all_users():
    """Получение списка всех уникальных пользователей"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if is_postgresql:
            cursor.execute('SELECT DISTINCT user_id FROM events')
        else:
            cursor.execute('SELECT DISTINCT user_id FROM events')
        
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        return users
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении списка пользователей: {e}")
        return []


def get_event_by_id(event_id):
    """Получение события по ID"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if is_postgresql:
            cursor.execute('''
                SELECT id, event_datetime, location, dances, user_id 
                FROM events WHERE id = %s
            ''', (event_id,))
        else:
            cursor.execute('''
                SELECT id, event_datetime, location, dances, user_id 
                FROM events WHERE id = ?
            ''', (event_id,))
        
        event = cursor.fetchone()
        conn.close()
        
        if event and is_postgresql:
            event = (event[0], event[1].isoformat(), event[2], event[3], event[4])
        
        return event
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении события по ID: {e}")
        return None
        
def delete_event(event_id):
    """Удаление события по ID"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if is_postgresql:
            cursor.execute('DELETE FROM events WHERE id = %s', (event_id,))
        else:
            cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении события: {e}")
        return False

def event_exists(user_id, event_datetime, location, dances):
    """Проверяет, существует ли уже такое событие"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        dances_str = ", ".join(dances) if dances else None
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if is_postgresql:
            cursor.execute('''
                SELECT COUNT(*) FROM events 
                WHERE user_id = %s 
                AND event_datetime = %s 
                AND location = %s
                AND dances = %s
            ''', (user_id, event_datetime, location, dances_str))
        else:
            cursor.execute('''
                SELECT COUNT(*) FROM events 
                WHERE user_id = ? 
                AND event_datetime = ? 
                AND location = ?
                AND dances = ?
            ''', (user_id, event_datetime.isoformat(), location, dances_str))
        
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке события: {e}")
        return False

def event_exists_for_any_user(datetime, location, dances):
    """Проверяет, существует ли такое событие у любого пользователя"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        dances_str = ", ".join(dances) if dances else None
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if is_postgresql:
            # PostgreSQL
            cursor.execute('''
                SELECT COUNT(*) FROM events 
                WHERE event_datetime = %s AND location = %s AND dances = %s
            ''', (datetime, location, dances_str))
        else:
            # SQLite
            cursor.execute('''
                SELECT COUNT(*) FROM events 
                WHERE event_datetime = ? AND location = ? AND dances = ?
            ''', (datetime.isoformat(), location, dances_str))
        
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке существования события: {e}")
        return False

def init_db():
    """Инициализация базы данных"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Проверяем, используем ли мы PostgreSQL
    is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
    
    if is_postgresql:
        # PostgreSQL
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                event_datetime TIMESTAMP NOT NULL,
                location TEXT,
                dances TEXT,
                raw_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Таблицы events и bot_users созданы в PostgreSQL")
    else:
        # SQLite
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_datetime TEXT NOT NULL,
                location TEXT,
                dances TEXT,
                raw_text TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_activity TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Таблицы events и bot_users созданы в SQLite")
    
    conn.commit()
    conn.close()

def add_bot_user(user_id, username=None, first_name=None, last_name=None):
    """Добавление/обновление пользователя бота"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if is_postgresql:
            cursor.execute('''
                INSERT INTO bot_users (user_id, username, first_name, last_name, last_activity)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_activity = CURRENT_TIMESTAMP
            ''', (user_id, username, first_name, last_name))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO bot_users 
                (user_id, username, first_name, last_name, last_activity)
                VALUES (?, ?, ?, ?, datetime('now'))
            ''', (user_id, username, first_name, last_name))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении пользователя бота: {e}")
        return False

def get_all_bot_users():
    """Получение списка всех пользователей бота"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM bot_users')
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        return users
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении списка пользователей бота: {e}")
        return []

def get_bot_users_stats():
    """Статистика пользователей бота"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if is_postgresql:
            cursor.execute('SELECT COUNT(*) FROM bot_users')
            total_users = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM bot_users 
                WHERE last_activity >= CURRENT_TIMESTAMP - INTERVAL '30 days'
            ''')
            active_users = cursor.fetchone()[0]
        else:
            cursor.execute('SELECT COUNT(*) FROM bot_users')
            total_users = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM bot_users 
                WHERE last_activity >= datetime('now', '-30 days')
            ''')
            active_users = cursor.fetchone()[0]
        
        conn.close()
        return total_users, active_users
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении статистики пользователей: {e}")
        return 0, 0
