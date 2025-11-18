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
            print("✅ Подключение к PostgreSQL установлено")
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
        
        # Автоматический бэкап (для SQLite)
        if not is_postgresql:
            backup_events()
            
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении события: {e}")
        return False

def get_upcoming_events(user_id):
    """Получение предстоящих событий пользователя"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if is_postgresql:
            # PostgreSQL
            cursor.execute('''
                SELECT id, event_datetime, location, dances 
                FROM events 
                WHERE user_id = %s AND event_datetime >= %s
                ORDER BY event_datetime
            ''', (user_id, datetime.now()))
            
            events = cursor.fetchall()
            # Конвертируем datetime в строку для совместимости
            events = [(ev[0], ev[1].isoformat(), ev[2], ev[3]) for ev in events]
        else:
            # SQLite
            cursor.execute('''
                SELECT id, event_datetime, location, dances 
                FROM events 
                WHERE user_id = ? AND event_datetime >= ?
                ORDER BY event_datetime
            ''', (user_id, datetime.now().isoformat()))
            
            events = cursor.fetchall()
        
        conn.close()
        return events
    except Exception as e:
        logger.error(f"❌ Ошибка при получении событий: {e}")
        return []

def get_today_events(user_id):
    """Получение событий на сегодня"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().date()
        tomorrow = datetime(today.year, today.month, today.day + 1).date()
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if is_postgresql:
            # PostgreSQL
            cursor.execute('''
                SELECT id, event_datetime, location, dances 
                FROM events 
                WHERE user_id = %s AND event_datetime >= %s AND event_datetime < %s
                ORDER BY event_datetime
            ''', (user_id, today, tomorrow))
            
            events = cursor.fetchall()
            events = [(ev[0], ev[1].isoformat(), ev[2], ev[3]) for ev in events]
        else:
            # SQLite
            cursor.execute('''
                SELECT id, event_datetime, location, dances 
                FROM events 
                WHERE user_id = ? AND event_datetime >= ? AND event_datetime < ?
                ORDER BY event_datetime
            ''', (user_id, today.isoformat(), tomorrow.isoformat()))
            
            events = cursor.fetchall()
        
        conn.close()
        return events
    except Exception as e:
        logger.error(f"❌ Ошибка при получении сегодняшних событий: {e}")
        return []

def get_all_events(user_id):
    """Получение всех событий пользователя"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if is_postgresql:
            # PostgreSQL
            cursor.execute('''
                SELECT id, event_datetime, location, dances 
                FROM events 
                WHERE user_id = %s
                ORDER BY event_datetime
            ''', (user_id,))
            
            events = cursor.fetchall()
            events = [(ev[0], ev[1].isoformat(), ev[2], ev[3]) for ev in events]
        else:
            # SQLite
            cursor.execute('''
                SELECT id, event_datetime, location, dances 
                FROM events 
                WHERE user_id = ?
                ORDER BY event_datetime
            ''', (user_id,))
            
            events = cursor.fetchall()
        
        conn.close()
        return events
    except Exception as e:
        logger.error(f"❌ Ошибка при получении всех событий: {e}")
        return []

def delete_event(event_id):
    """Удаление события по ID"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        is_postgresql = os.getenv('RENDER') and PSYCOPG2_AVAILABLE
        
        if is_postgresql:
            # PostgreSQL
            cursor.execute('DELETE FROM events WHERE id = %s', (event_id,))
        else:
            # SQLite
            cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
        
        conn.commit()
        conn.close()
        
        # Автоматический бэкап (для SQLite)
        if not is_postgresql:
            backup_events()
            
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
            # PostgreSQL
            cursor.execute('''
                SELECT COUNT(*) FROM events 
                WHERE user_id = %s 
                AND event_datetime = %s 
                AND location = %s
                AND dances = %s
            ''', (user_id, event_datetime, location, dances_str))
        else:
            # SQLite
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

# Функции резервного копирования (только для SQLite)
import json

def backup_events():
    """Резервное копирование событий в JSON файл (только для SQLite)"""
    if os.getenv('RENDER') and PSYCOPG2_AVAILABLE:
        print("ℹ️  Резервное копирование не требуется для PostgreSQL")
        return True
        
    try:
        conn = sqlite3.connect("events.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events")
        events = cursor.fetchall()
        
        cursor.execute("PRAGMA table_info(events)")
        columns = [column[1] for column in cursor.fetchall()]
        
        conn.close()
        
        events_dict = []
        for event in events:
            event_dict = dict(zip(columns, event))
            events_dict.append(event_dict)
        
        backup_data = {
            "backup_time": datetime.now().isoformat(),
            "events_count": len(events_dict),
            "events": events_dict
        }
        
        with open("backup_events.json", "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
        print(f"✅ Резервная копия SQLite создана: {len(events_dict)} событий")
        return True
    except Exception as e:
        print(f"❌ Ошибка резервного копирования SQLite: {e}")
        return False

def restore_events():
    """Восстановление событий из JSON файла (только для SQLite)"""
    if os.getenv('RENDER') and PSYCOPG2_AVAILABLE:
        print("ℹ️  Восстановление не требуется для PostgreSQL")
        return True
        
    try:
        if not os.path.exists("backup_events.json"):
            print("ℹ️  Файл резервной копии SQLite не найден")
            return False
            
        with open("backup_events.json", "r", encoding="utf-8") as f:
            backup_data = json.load(f)
        
        conn = sqlite3.connect("events.db", check_same_thread=False)
        cursor = conn.cursor()
        
        restored_count = 0
        for event_dict in backup_data["events"]:
            try:
                event_values = (
                    event_dict.get('id'),
                    event_dict.get('user_id'),
                    event_dict.get('event_datetime'),
                    event_dict.get('location'),
                    event_dict.get('dances'),
                    event_dict.get('raw_text'),
                    event_dict.get('created_at')
                )
                
                cursor.execute('''
                    INSERT OR IGNORE INTO events 
                    (id, user_id, event_datetime, location, dances, raw_text, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', event_values)
                restored_count += 1
            except Exception as e:
                print(f"❌ Ошибка при восстановлении события {event_dict.get('id')}: {e}")
        
        conn.commit()
        conn.close()
        print(f"✅ Восстановлено {restored_count} событий в SQLite")
        return True
    except Exception as e:
        print(f"❌ Ошибка восстановления SQLite: {e}")
        return False

def get_backup_info():
    """Информация о резервной копии (только для SQLite)"""
    if os.getenv('RENDER') and PSYCOPG2_AVAILABLE:
        return "🔄 Используется PostgreSQL - резервное копирование не требуется"
        
    try:
        if not os.path.exists("backup_events.json"):
            return "Резервная копия SQLite не найдена"
            
        with open("backup_events.json", "r", encoding="utf-8") as f:
            backup_data = json.load(f)
            
        return f"Резервная копия SQLite от {backup_data['backup_time']} ({backup_data['events_count']} событий)"
    except Exception as e:
        return f"Ошибка чтения резервной копии SQLite: {e}"
