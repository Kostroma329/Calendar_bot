# database.py
import sqlite3
import os
from datetime import datetime

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect("events.db", check_same_thread=False)
    cursor = conn.cursor()
    
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
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

def event_exists(user_id, event_datetime, location, dances):
    """Проверяет, существует ли уже такое событие"""
    try:
        conn = sqlite3.connect("events.db", check_same_thread=False)
        cursor = conn.cursor()
        
        # Преобразуем список танцев в строку для сравнения
        dances_str = ", ".join(dances) if dances else None
        
        # Ищем события с тем же пользователем, временем и местом
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
        print(f"❌ Ошибка при проверке события: {e}")
        return False

def add_event(user_id, event_datetime, location, dances, raw_text):
    """Добавление события в базу данных"""
    try:
        conn = sqlite3.connect("events.db", check_same_thread=False)
        cursor = conn.cursor()
        
        # Преобразуем список танцев в строку
        dances_str = ", ".join(dances) if dances else None
        
        cursor.execute('''
            INSERT INTO events (user_id, event_datetime, location, dances, raw_text)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, event_datetime.isoformat(), location, dances_str, raw_text))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Ошибка при добавлении события: {e}")
        return False

def get_upcoming_events(user_id):
    """Получение предстоящих событий пользователя"""
    try:
        conn = sqlite3.connect("events.db", check_same_thread=False)
        cursor = conn.cursor()
        
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
        print(f"❌ Ошибка при получении событий: {e}")
        return []

def get_today_events(user_id):
    """Получение событий на сегодня"""
    try:
        conn = sqlite3.connect("events.db", check_same_thread=False)
        cursor = conn.cursor()
        
        today = datetime.now().date()
        tomorrow = datetime(today.year, today.month, today.day + 1).date()
        
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
        print(f"❌ Ошибка при получении сегодняшних событий: {e}")
        return []

def get_all_events(user_id):
    """Получение всех событий пользователя"""
    try:
        conn = sqlite3.connect("events.db", check_same_thread=False)
        cursor = conn.cursor()
        
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
        print(f"❌ Ошибка при получении всех событий: {e}")
        return []

def delete_event(event_id):
    """Удаление события по ID"""
    try:
        conn = sqlite3.connect("events.db", check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Ошибка при удалении события: {e}")
        return False
