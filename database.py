# database.py
import sqlite3
import json
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
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
def backup_events():
    """Резервное копирование событий в JSON файл"""
    try:
        conn = sqlite3.connect("events.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events")
        events = cursor.fetchall()
        
        # Получаем названия колонок
        cursor.execute("PRAGMA table_info(events)")
        columns = [column[1] for column in cursor.fetchall()]
        
        conn.close()
        
        # Преобразуем в список словарей для лучшей читаемости
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
            
        print(f"✅ Резервная копия создана: {len(events_dict)} событий")
        return True
    except Exception as e:
        print(f"❌ Ошибка резервного копирования: {e}")
        return False

def restore_events():
    """Восстановление событий из JSON файла"""
    try:
        if not os.path.exists("backup_events.json"):
            print("ℹ️  Файл резервной копии не найден")
            return False
            
        with open("backup_events.json", "r", encoding="utf-8") as f:
            backup_data = json.load(f)
        
        conn = sqlite3.connect("events.db", check_same_thread=False)
        cursor = conn.cursor()
        
        restored_count = 0
        for event_dict in backup_data["events"]:
            try:
                # Создаем кортеж значений в правильном порядке
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
        print(f"✅ Восстановлено {restored_count} событий из резервной копии от {backup_data.get('backup_time', 'неизвестно')}")
        return True
    except Exception as e:
        print(f"❌ Ошибка восстановления: {e}")
        return False

def get_backup_info():
    """Информация о резервной копии"""
    try:
        if not os.path.exists("backup_events.json"):
            return "Резервная копия не найдена"
            
        with open("backup_events.json", "r", encoding="utf-8") as f:
            backup_data = json.load(f)
            
        return f"Резервная копия от {backup_data['backup_time']} ({backup_data['events_count']} событий)"
    except Exception as e:
        return f"Ошибка чтения резервной копии: {e}"

def add_event(user_id, event_datetime, location, dances, raw_text):
    """Добавление события в базу данных с автоматическим бэкапом"""
    try:
        conn = sqlite3.connect("events.db", check_same_thread=False)
        cursor = conn.cursor()
        
        dances_str = ", ".join(dances) if dances else None
        
        cursor.execute('''
            INSERT INTO events (user_id, event_datetime, location, dances, raw_text)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, event_datetime.isoformat(), location, dances_str, raw_text))
        
        conn.commit()
        conn.close()
        
        # АВТОМАТИЧЕСКИЙ БЭКАП ПОСЛЕ ДОБАВЛЕНИЯ СОБЫТИЯ
        print("💾 Автоматический бэкап после добавления события...")
        backup_events()
        
        return True
    except Exception as e:
        print(f"❌ Ошибка при добавлении события: {e}")
        return False

def delete_event(event_id):
    """Удаление события по ID с автоматическим бэкапом"""
    try:
        conn = sqlite3.connect("events.db", check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM events WHERE id = ?', (event_id,))
        
        conn.commit()
        conn.close()
        
        # АВТОМАТИЧЕСКИЙ БЭКАП ПОСЛЕ УДАЛЕНИЯ СОБЫТИЯ
        print("💾 Автоматический бэкап после удаления события...")
        backup_events()
        
        return True
    except Exception as e:
        print(f"❌ Ошибка при удалении события: {e}")
        return False

