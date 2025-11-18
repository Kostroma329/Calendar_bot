# bot.py
import logging
import sqlite3
import os
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, CallbackQueryHandler, filters
)

from config import BOT_TOKEN
from database import init_db, add_event, delete_event, event_exists
from database import get_upcoming_events_all, get_today_events_all, get_all_events
from parser import extract_with_spacy
from admin import is_admin, get_admin_commands, get_user_commands, ADMIN_IDS

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния
AWAITING_CONFIRMATION, AWAITING_LOCATION, AWAITING_DANCES = 1, 2, 3


def get_moscow_time():
    """Получение текущего времени в Московском часовом поясе (UTC+3)"""
    return datetime.now() + timedelta(hours=3)


def convert_to_moscow_time(dt):
    """Конвертирует время в Московский часовой пояс"""
    return dt + timedelta(hours=3)


def convert_to_utc(dt):
    """Конвертирует время в UTC"""
    return dt - timedelta(hours=3)


async def send_daily_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Отправка напоминаний за 1 день до события (только создателю события)"""
    try:
        from database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        
        # Текущее время в Московском часовом поясе
        moscow_now = get_moscow_time()
        
        # Время через 24 часа в Московском времени
        reminder_start = moscow_now + timedelta(hours=24)
        reminder_end = reminder_start + timedelta(minutes=30)
        
        # Конвертируем в UTC для запроса к базе данных
        reminder_start_utc = convert_to_utc(reminder_start)
        reminder_end_utc = convert_to_utc(reminder_end)
        
        is_postgresql = os.getenv('RENDER')
        
        if is_postgresql:
            # PostgreSQL - выбираем ВСЕ события в диапазоне
            cursor.execute('''
                SELECT user_id, event_datetime, location, dances 
                FROM events 
                WHERE event_datetime BETWEEN %s AND %s
            ''', (reminder_start_utc, reminder_end_utc))
        else:
            # SQLite - выбираем ВСЕ события в диапазоне
            cursor.execute('''
                SELECT user_id, event_datetime, location, dances 
                FROM events 
                WHERE event_datetime BETWEEN ? AND ?
            ''', (reminder_start_utc.isoformat(), reminder_end_utc.isoformat()))
        
        events = cursor.fetchall()
        conn.close()
        
        # Конвертируем даты для PostgreSQL
        if is_postgresql:
            events = [(ev[0], ev[1].isoformat(), ev[2], ev[3]) for ev in events]
        
        sent_reminders = 0
        for event in events:
            user_id, event_datetime, location, dances = event
            
            # Конвертируем время события в Московский часовой пояс
            event_dt_utc = datetime.fromisoformat(event_datetime.replace('Z', '+00:00'))
            event_dt_moscow = convert_to_moscow_time(event_dt_utc)
            
            message = (
                "🔔 Напоминание за 1 день!\n\n"
                f"📅 Завтра {event_dt_moscow.strftime('%d.%m в %H:%M')}\n"
                f"📍 {location or 'Место не указано'}\n"
                f"💃 {dances or 'Танцы не указаны'}\n\n"
                f"Не забудь подготовиться! 🕺💃"
            )
            
            try:
                await context.bot.send_message(chat_id=user_id, text=message)
                sent_reminders += 1
                logger.info(f"Отправлено напоминание создателю {user_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить напоминание пользователю {user_id}: {e}")
        
        logger.info(f"Всего отправлено напоминаний: {sent_reminders}")
        
    except Exception as e:
        # Не логируем как ошибку, если таблица еще не создана
        if "no such table" not in str(e) and "relation" not in str(e):
            logger.error(f"Ошибка в send_daily_reminders: {e}")


def get_main_menu(user_id=None):
    """Возвращает главное меню с кнопками"""
    # Одинаковое меню для всех пользователей
    keyboard = [
        [InlineKeyboardButton("➕ Добавить событие", callback_data="add_event")],
        [InlineKeyboardButton("📅 Все мероприятия", callback_data="show_events")],
        [InlineKeyboardButton("🎯 Сегодня есть мероприятие?", callback_data="today")]
    ]
    
    # Только админы видят дополнительные кнопки
    if user_id and is_admin(user_id):
        keyboard.extend([
            [InlineKeyboardButton("🗑️ Удалить событие", callback_data="delete_event")]
        ])
    
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Приветственное сообщение с учетом прав
    if is_admin(user_id):
        welcome_text = "Привет, Администратор! 👑\n\n"
    else:
        welcome_text = "Привет! Я твой танцевальный календарь 🕺💃\n\n"

    welcome_text += "Выбери действие или отправь описание мероприятия:"

    await update.message.reply_text(welcome_text, reply_markup=get_main_menu(user_id))


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    try:
        if query.data == "add_event":
            await query.edit_message_text("Отправь описание мероприятия:\n\n"
                                          "Пример: *«Завтра в 19:00 в Троицком танцуем вальс»*", 
                                          parse_mode="Markdown")
            return ConversationHandler.END

        elif query.data == "show_events":
            # Показываем ВСЕ события всем пользователям
            events = get_upcoming_events_all()

            if not events:
                msg = "Пока нет запланированных мероприятий."
            else:
                msg = "📅 Все ближайшие мероприятия:\n\n"
                for ev in events:
                    dt = datetime.fromisoformat(ev[1])
                    dt_moscow = convert_to_moscow_time(dt)  # Конвертируем в Московское время
                    loc = ev[2] or "не указано"
                    dances = ev[3] or "не указаны"
                    # Для админов показываем ID пользователя, для обычных - просто событие
                    if is_admin(user_id):
                        user_info = f"(👤 {ev[4]})"
                    else:
                        user_info = ""
                    msg += f"• {dt_moscow.strftime('%d.%m %H:%M')} — {loc} | {dances} {user_info}\n"
            
            await query.edit_message_text(msg, reply_markup=get_main_menu(user_id))
            return ConversationHandler.END

        elif query.data == "delete_event":
            # Только для админов
            if not is_admin(user_id):
                await query.edit_message_text("❌ У вас нет прав для удаления событий.", 
                                              reply_markup=get_main_menu(user_id))
                return ConversationHandler.END
            
            events = get_upcoming_events_all()  # Все события

            if not events:
                msg = "Нет мероприятий для удаления."
                await query.edit_message_text(msg, reply_markup=get_main_menu(user_id))
                return ConversationHandler.END

            msg = "🗑️ Выбери событие для удаления:\n\n"
            for i, ev in enumerate(events, 1):
                dt = datetime.fromisoformat(ev[1])
                dt_moscow = convert_to_moscow_time(dt)  # Конвертируем в Московское время
                loc = ev[2] or "не указано"
                dances = ev[3] or "не указаны"
                user_info = f"(👤 {ev[4]})"
                msg += f"{i}. {dt_moscow.strftime('%d.%m %H:%M')} — {loc} | {dances} {user_info}\n"

            msg += "\n\nОтправь команду /delete N, где N — номер события."

            await query.edit_message_text(msg, reply_markup=get_main_menu(user_id))
            return ConversationHandler.END

        elif query.data == "today":
            events = get_today_events_all()  # Все события на сегодня

            if not events:
                msg = "Сегодня нет мероприятий 😊"
            else:
                msg = "🎉 Сегодня:\n\n"
                for ev in events:
                    dt = datetime.fromisoformat(ev[1])
                    dt_moscow = convert_to_moscow_time(dt)  # Конвертируем в Московское время
                    loc = ev[2] or "не указано"
                    dances = ev[3] or "не указаны"
                    # Для админов показываем ID пользователя
                    if is_admin(user_id):
                        user_info = f"(👤 {ev[4]})"
                    else:
                        user_info = ""
                    msg += f"• {dt_moscow.strftime('%H:%M')} — {loc} | {dances} {user_info}\n"

            await query.edit_message_text(msg, reply_markup=get_main_menu(user_id))
            return ConversationHandler.END

        elif query.data == "debug":
            # Проверяем права доступа
            if not is_admin(user_id):
                await query.edit_message_text("❌ У вас нет прав для выполнения этой команды.", 
                                              reply_markup=get_main_menu(user_id))
                return ConversationHandler.END
                
            events = get_all_events()  # Все события

            if not events:
                await query.edit_message_text("В базе данных нет событий.", 
                                              reply_markup=get_main_menu(user_id))
            else:
                msg = "🔧 Все события в БД:\n\n"
                for ev in events:
                    dt = datetime.fromisoformat(ev[1])
                    dt_moscow = convert_to_moscow_time(dt)  # Конвертируем в Московское время
                    loc = ev[2] or "не указано"
                    dances = ev[3] or "не указаны"
                    is_past = "⏰" if dt_moscow < get_moscow_time() else "✅"
                    msg += f"{is_past} {dt_moscow.strftime('%d.%m %H:%M')} — {loc} | {dances} (👤 {ev[4]})\n"

                await query.edit_message_text(msg, reply_markup=get_main_menu(user_id))
            return ConversationHandler.END

        elif query.data == "stats":
            # Проверяем права доступа
            if not is_admin(user_id):
                await query.edit_message_text("❌ У вас нет прав для выполнения этой команды.", 
                                              reply_markup=get_main_menu(user_id))
                return ConversationHandler.END
                
            try:
                from database import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                # Общая статистика
                if os.getenv('RENDER'):
                    # PostgreSQL
                    cursor.execute("SELECT COUNT(*) FROM events")
                    total_events = cursor.fetchone()[0]

                    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM events")
                    total_users = cursor.fetchone()[0]

                    cursor.execute("SELECT COUNT(*) FROM events WHERE event_datetime >= %s", 
                                   (datetime.now(),))
                    upcoming_events = cursor.fetchone()[0]
                else:
                    # SQLite
                    cursor.execute("SELECT COUNT(*) FROM events")
                    total_events = cursor.fetchone()[0]

                    cursor.execute("SELECT COUNT(DISTINCT user_id) FROM events")
                    total_users = cursor.fetchone()[0]

                    cursor.execute("SELECT COUNT(*) FROM events WHERE event_datetime >= ?",
                                   (datetime.now().isoformat(),))
                    upcoming_events = cursor.fetchone()[0]

                conn.close()

                db_type = "PostgreSQL" if os.getenv('RENDER') else "SQLite"
                stats_msg = (
                    "📊 Статистика бота:\n\n"
                    f"• Всего событий: {total_events}\n"
                    f"• Предстоящих событий: {upcoming_events}\n"
                    f"• Уникальных пользователей: {total_users}\n"
                    f"• Админов: {len(ADMIN_IDS)}\n"
                    f"• База данных: {db_type}\n"
                    f"• Часовой пояс: Москва (UTC+3)\n"
                )

                await query.edit_message_text(stats_msg, reply_markup=get_main_menu(user_id))

            except Exception as e:
                await query.edit_message_text(f"❌ Ошибка при получении статистики: {e}", 
                                              reply_markup=get_main_menu(user_id))
            return ConversationHandler.END

    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.error(f"Ошибка в button_handler: {e}")
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте снова.", 
                                          reply_markup=get_main_menu(user_id))
        return ConversationHandler.END


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Используем парсер
    extracted = extract_with_spacy(text)
    dt = extracted["datetime"]
    location = extracted["location"]
    dances = extracted["dances"]

    if not dt:
        await update.message.reply_text("❌ Не удалось определить дату. Попробуй: *«завтра в 19:00»*",
                                        parse_mode="Markdown")
        return ConversationHandler.END

    # Проверяем, нет ли уже такого события
    if event_exists(user_id, dt, location, dances):
        dances_str = ", ".join(dances) if dances else "не указаны"
        existing_event_msg = (
            "❌ Такое событие уже существует!\n\n"
            f"📅 {dt.strftime('%d.%m.%Y %H:%M')}\n"
            f"📍 {location or 'не указано'}\n"
            f"💃 {dances_str}\n\n"
            "Измени дату, место или танцы и попробуй снова."
        )
        await update.message.reply_text(existing_event_msg, reply_markup=get_main_menu(user_id))
        return ConversationHandler.END

    # Сохраняем в context.user_data
    context.user_data["event_data"] = {
        "datetime": dt,
        "location": location,
        "dances": dances,
        "raw_text": text
    }

    # Кнопки подтверждения
    keyboard = [
        [
            InlineKeyboardButton("✅ Всё верно", callback_data="confirm"),
        ],
        [
            InlineKeyboardButton("✏️ Место", callback_data="edit_location"),
            InlineKeyboardButton("💃 Танцы", callback_data="edit_dances")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    dances_str = ", ".join(dances) if dances else "не распознаны"
    await update.message.reply_text(
        f"Проверь данные:\n\n"
        f"📅 {dt.strftime('%d.%m.%Y %H:%M')}\n"
        f"📍 {location or 'не указано'}\n"
        f"💃 {dances_str}\n\n"
        f"Всё правильно?",
        reply_markup=reply_markup
    )
    return AWAITING_CONFIRMATION


async def confirm_or_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if "event_data" not in context.user_data:
        await query.edit_message_text("❌ Ошибка. Начни сначала.", reply_markup=get_main_menu(user_id))
        return ConversationHandler.END

    data = context.user_data["event_data"]

    if query.data == "confirm":
        # Двойная проверка перед сохранением
        if event_exists(user_id, data["datetime"], data["location"], data["dances"]):
            dances_str = ", ".join(data["dances"]) if data["dances"] else "не указаны"
            existing_event_msg = (
                "❌ Пока ты подтверждал, такое событие уже было создано!\n\n"
                f"📅 {data['datetime'].strftime('%d.%m.%Y %H:%M')}\n"
                f"📍 {data['location'] or 'не указано'}\n"
                f"💃 {dances_str}\n\n"
                "Проверь свои события или измени данные."
            )
            await query.edit_message_text(existing_event_msg, reply_markup=get_main_menu(user_id))
            context.user_data.pop("event_data", None)
            return ConversationHandler.END

        success = add_event(user_id, data["datetime"], data["location"], data["dances"], data["raw_text"])
        if success:
            db_type = "PostgreSQL" if os.getenv('RENDER') else "SQLite"
            message = f"✅ Отлично! Событие сохранено в календаре ({db_type})."
            await query.edit_message_text(message, reply_markup=get_main_menu(user_id))
        else:
            await query.edit_message_text("❌ Ошибка при сохранении события.", reply_markup=get_main_menu(user_id))
        # Очищаем временные данные
        context.user_data.pop("event_data", None)
        return ConversationHandler.END

    elif query.data == "edit_location":
        await query.edit_message_text("Напиши правильное место проведения:")
        return AWAITING_LOCATION

    elif query.data == "edit_dances":
        await query.edit_message_text("Напиши правильные танцы через запятую:")
        return AWAITING_DANCES


async def receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if "event_data" not in context.user_data:
        await update.message.reply_text("❌ Ошибка. Начни с команды /start.", reply_markup=get_main_menu(user_id))
        return ConversationHandler.END

    new_location = update.message.text.strip()

    # Обновляем данные в context.user_data
    context.user_data["event_data"]["location"] = new_location

    # Показываем обновленные данные для подтверждения
    data = context.user_data["event_data"]

    keyboard = [
        [
            InlineKeyboardButton("✅ Всё верно", callback_data="confirm"),
        ],
        [
            InlineKeyboardButton("✏️ Место", callback_data="edit_location"),
            InlineKeyboardButton("💃 Танцы", callback_data="edit_dances")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    dances_str = ", ".join(data["dances"]) if data["dances"] else "не указаны"
    await update.message.reply_text(
        f"✅ Место обновлено!\n\n"
        f"Обновленные данные:\n"
        f"📅 {data['datetime'].strftime('%d.%m.%Y %H:%M')}\n"
        f"📍 {new_location or 'не указано'}\n"
        f"💃 {dances_str}\n\n"
        f"Всё правильно?",
        reply_markup=reply_markup
    )
    return AWAITING_CONFIRMATION


async def receive_dances(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if "event_data" not in context.user_data:
        await update.message.reply_text("❌ Ошибка. Начни с команды /start.", reply_markup=get_main_menu(user_id))
        return ConversationHandler.END

    dances_input = update.message.text.strip()
    dances = [d.strip() for d in dances_input.split(",") if d.strip()]

    # Обновляем данные в context.user_data
    context.user_data["event_data"]["dances"] = dances

    # Показываем обновленные данные для подтверждения
    data = context.user_data["event_data"]

    keyboard = [
        [
            InlineKeyboardButton("✅ Всё верно", callback_data="confirm"),
        ],
        [
            InlineKeyboardButton("✏️ Место", callback_data="edit_location"),
            InlineKeyboardButton("💃 Танцы", callback_data="edit_dances")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    dances_str = ", ".join(dances) if dances else "не указаны"
    await update.message.reply_text(
        f"✅ Танцы обновлены!\n\n"
        f"Обновленные данные:\n"
        f"📅 {data['datetime'].strftime('%d.%m.%Y %H:%M')}\n"
        f"📍 {data['location'] or 'не указано'}\n"
        f"💃 {dances_str}\n\n"
        f"Всё правильно?",
        reply_markup=reply_markup
    )
    return AWAITING_CONFIRMATION


async def delete_event_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return

    user_id = update.effective_user.id
    args = context.args

    # Проверяем права - только админы могут удалять
    if not is_admin(user_id):
        await update.message.reply_text(
            "❌ У вас нет прав для удаления событий.",
            reply_markup=get_main_menu(user_id)
        )
        return

    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "❌ Неверный формат.\nИспользуй: /delete N, где N — номер события.\n"
            "Сначала посмотри список через кнопку «Удалить событие».",
            reply_markup=get_main_menu(user_id)
        )
        return

    event_num = int(args[0])
    events = get_upcoming_events_all()  # Все события

    if event_num < 1 or event_num > len(events):
        await update.message.reply_text(
            f"❌ Нет события с номером {event_num}.",
            reply_markup=get_main_menu(user_id)
        )
        return

    event_id = events[event_num - 1][0]  # id события
    delete_event(event_id)

    await update.message.reply_text(
        f"✅ Событие №{event_num} удалено!",
        reply_markup=get_main_menu(user_id)
    )


async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для отладки - показывает все события (только для админов)"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    events = get_all_events()  # Все события

    if not events:
        await update.message.reply_text("В базе данных нет событий.")
    else:
        msg = "🔧 Все события в БД:\n\n"
        for ev in events:
            dt = datetime.fromisoformat(ev[1])
            dt_moscow = convert_to_moscow_time(dt)  # Конвертируем в Московское время
            loc = ev[2] or "не указано"
            dances = ev[3] or "не указаны"
            is_past = "⏰" if dt_moscow < get_moscow_time() else "✅"
            msg += f"{is_past} {dt_moscow.strftime('%d.%m %H:%M')} — {loc} | {dances} (👤 {ev[4]})\n"

        await update.message.reply_text(msg)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика бота (только для админов)"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        from database import get_connection
        conn = get_connection()
        cursor = conn.cursor()

        # Общая статистика
        if os.getenv('RENDER'):
            # PostgreSQL
            cursor.execute("SELECT COUNT(*) FROM events")
            total_events = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT user_id) FROM events")
            total_users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM events WHERE event_datetime >= %s",
                           (datetime.now(),))
            upcoming_events = cursor.fetchone()[0]
        else:
            # SQLite
            cursor.execute("SELECT COUNT(*) FROM events")
            total_events = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT user_id) FROM events")
            total_users = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM events WHERE event_datetime >= ?",
                           (datetime.now().isoformat(),))
            upcoming_events = cursor.fetchone()[0]

        conn.close()

        db_type = "PostgreSQL" if os.getenv('RENDER') else "SQLite"
        stats_msg = (
            "📊 Статистика бота:\n\n"
            f"• Всего событий: {total_events}\n"
            f"• Предстоящих событий: {upcoming_events}\n"
            f"• Уникальных пользователей: {total_users}\n"
            f"• Админов: {len(ADMIN_IDS)}\n"
            f"• База данных: {db_type}\n"
            f"• Часовой пояс: Москва (UTC+3)\n"
        )

        await update.message.reply_text(stats_msg)

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при получении статистики: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает доступные команды"""
    user_id = update.effective_user.id

    if is_admin(user_id):
        commands = get_admin_commands()
        role = "👑 Администратор"
    else:
        commands = get_user_commands()
        role = "👤 Пользователь"

    commands_text = "\n".join([f"/{cmd}" for cmd in commands])

    help_text = (
        f"{role}\n\n"
        "Доступные команды:\n"
        f"{commands_text}\n\n"
        "Или используй кнопки меню ниже 👇"
    )

    await update.message.reply_text(help_text, reply_markup=get_main_menu(user_id))


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущей операции"""
    user_id = update.effective_user.id
    
    # Очищаем временные данные
    context.user_data.pop("event_data", None)
    
    await update.message.reply_text(
        "❌ Операция отменена.",
        reply_markup=get_main_menu(user_id)
    )
    return ConversationHandler.END


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    error = context.error
    
    # Игнорируем ошибку "Message is not modified"
    if hasattr(error, 'message') and "Message is not modified" in str(error):
        return
    
    # Логируем все остальные ошибки
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)


def main():
    # Инициализация базы данных с задержкой
    print("🔄 Инициализация базы данных...")
    init_db()
    
    # Даем время на создание таблиц в PostgreSQL
    time.sleep(3)
    
    print("✅ База данных готова")
    print("🌍 Часовой пояс: Москва (UTC+3)")

    # Создаем Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Добавляем job для напоминаний с задержкой
    job_queue = application.job_queue
    
    # Проверяем, что JobQueue доступен
    if job_queue:
        # Запускаем первую проверку через 10 секунд после старта
        job_queue.run_repeating(send_daily_reminders, interval=1800, first=10)
        print("🔔 Система напоминаний активирована (с задержкой)")
    else:
        print("⚠️  JobQueue недоступен. Напоминания отключены.")

    # Обработчик диалога
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            CommandHandler("add", handle_message)
        ],
        states={
            AWAITING_CONFIRMATION: [
                CallbackQueryHandler(confirm_or_edit, pattern="^(confirm|edit_location|edit_dances)$")
            ],
            AWAITING_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_location)
            ],
            AWAITING_DANCES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_dances)
            ]
        },
        fallbacks=[
            CommandHandler("start", start),
            CommandHandler("cancel", cancel_command),
            CommandHandler("help", help_command)
        ],
        name="conversation",
        persistent=False
    )

    # Добавляем обработчики команд
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("delete", delete_event_command))
    application.add_handler(CommandHandler("debug", debug_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(button_handler))

    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)

    # Запускаем бота
    print("✅ Бот запущен!")
    print(f"👑 Админы: {ADMIN_IDS}")
    print("🛡️  Защита от дубликатов включена")
    print("💾 Общая база данных активна")

    # Для Render - используем webhook
    if os.getenv('RENDER'):
        webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{BOT_TOKEN}"
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv('PORT', 8443)),
            url_path=BOT_TOKEN,
            webhook_url=webhook_url
        )
    else:
        # Для локальной разработки - polling
        application.run_polling()


if __name__ == "__main__":
    main()
