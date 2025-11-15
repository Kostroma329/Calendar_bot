# bot.py
import logging
import sqlite3
import os
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes,
    ConversationHandler, CallbackQueryHandler, filters
)

from config import BOT_TOKEN
from database import init_db, add_event, get_upcoming_events, delete_event, get_today_events, get_all_events
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

# Временное хранилище
user_data = {}


def get_main_menu():
    """Возвращает главное меню с кнопками"""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить событие", callback_data="add_event")],
        [InlineKeyboardButton("📅 Мои мероприятия", callback_data="show_events")],
        [InlineKeyboardButton("🗑️ Удалить событие", callback_data="delete_event")],
        [InlineKeyboardButton("🎯 Сегодня есть мероприятие?", callback_data="today")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Приветственное сообщение с учетом прав
    if is_admin(user_id):
        welcome_text = "Привет, Администратор! 👑\n\n"
    else:
        welcome_text = "Привет! Я твой танцевальный календарь 🕺💃\n\n"

    welcome_text += "Выбери действие или отправь описание мероприятия:"

    await update.message.reply_text(welcome_text, reply_markup=get_main_menu())


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if query.data == "add_event":
        await query.edit_message_text("Отправь описание мероприятия:\n\n"
                                      "Пример: *«Завтра в 19:00 в Троицком танцуем вальс»*", parse_mode="Markdown")
        return ConversationHandler.END

    elif query.data == "show_events":
        events = get_upcoming_events(user_id)

        if not events:
            msg = "У тебя пока нет запланированных мероприятий."
        else:
            msg = "📌 Твои ближайшие мероприятия:\n\n"
            for ev in events:
                dt = datetime.fromisoformat(ev[1])
                loc = ev[2] or "не указано"
                dances = ev[3] or "не указаны"
                msg += f"• {dt.strftime('%d.%m %H:%M')} — {loc} | {dances}\n"
        await query.edit_message_text(msg, reply_markup=get_main_menu())
        return ConversationHandler.END

    elif query.data == "delete_event":
        events = get_upcoming_events(user_id)
        if not events:
            msg = "У тебя нет мероприятий для удаления."
            await query.edit_message_text(msg, reply_markup=get_main_menu())
            return ConversationHandler.END

        msg = "📌 Выбери событие для удаления:\n\n"
        for i, ev in enumerate(events, 1):
            dt = datetime.fromisoformat(ev[1])
            loc = ev[2] or "не указано"
            dances = ev[3] or "не указаны"
            msg += f"{i}. {dt.strftime('%d.%m %H:%M')} — {loc} | {dances}\n"

        msg += "\n\nОтправь команду /delete N, где N — номер события."

        await query.edit_message_text(msg, reply_markup=get_main_menu())
        return ConversationHandler.END

    elif query.data == "today":
        events = get_today_events(user_id)
        if not events:
            msg = "Сегодня у тебя нет мероприятий 😊"
        else:
            msg = "🎉 Сегодня у тебя:\n\n"
            for ev in events:
                dt = datetime.fromisoformat(ev[1])
                loc = ev[2] or "не указано"
                dances = ev[3] or "не указаны"
                msg += f"• {dt.strftime('%H:%M')} — {loc} | {dances}\n"

        await query.edit_message_text(msg, reply_markup=get_main_menu())
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

    # Сохраняем во временное хранилище
    user_data[user_id] = {
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

    if user_id not in user_data:
        await query.edit_message_text("❌ Ошибка. Начни сначала.", reply_markup=get_main_menu())
        return ConversationHandler.END

    data = user_data[user_id]

    if query.data == "confirm":
        success = add_event(user_id, data["datetime"], data["location"], data["dances"], data["raw_text"])
        if success:
            await query.edit_message_text("✅ Отлично! Событие сохранено в календаре.", reply_markup=get_main_menu())
        else:
            await query.edit_message_text("❌ Ошибка при сохранении события.", reply_markup=get_main_menu())
        del user_data[user_id]
        return ConversationHandler.END

    elif query.data == "edit_location":
        await query.edit_message_text("Напиши правильное место проведения:")
        return AWAITING_LOCATION

    elif query.data == "edit_dances":
        await query.edit_message_text("Напиши правильные танцы через запятую:")
        return AWAITING_DANCES


async def receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data:
        await update.message.reply_text("❌ Ошибка. Начни с команды /start.", reply_markup=get_main_menu())
        return ConversationHandler.END

    new_location = update.message.text.strip()

    # Обновляем данные
    user_data[user_id]["location"] = new_location

    # Показываем обновленные данные для подтверждения
    data = user_data[user_id]

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
    if user_id not in user_data:
        await update.message.reply_text("❌ Ошибка. Начни с команды /start.", reply_markup=get_main_menu())
        return ConversationHandler.END

    dances_input = update.message.text.strip()
    dances = [d.strip() for d in dances_input.split(",") if d.strip()]

    # Обновляем данные
    user_data[user_id]["dances"] = dances

    # Показываем обновленные данные для подтверждения
    data = user_data[user_id]

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
    # Проверяем, что это сообщение, а не что-то другое
    if update.message is None:
        return  # или логируем ошибку

    user_id = update.effective_user.id
    args = context.args

    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "❌ Неверный формат.\nИспользуй: /delete N, где N — номер события.\n"
            "Сначала посмотри список через /events или кнопку «Мои мероприятия».",
            reply_markup=get_main_menu()
        )
        return

    event_num = int(args[0])
    events = get_upcoming_events(user_id)

    if event_num < 1 or event_num > len(events):
        await update.message.reply_text(
            f"❌ Нет события с номером {event_num}.",
            reply_markup=get_main_menu()
        )
        return

    event_id = events[event_num - 1][0]  # id события
    delete_event(event_id)

    await update.message.reply_text(
        f"✅ Событие №{event_num} удалено!",
        reply_markup=get_main_menu()
    )

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для отладки - показывает все события (только для админов)"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    events = get_all_events(user_id)

    if not events:
        await update.message.reply_text("В базе данных нет событий.")
    else:
        msg = "🔧 Все события в БД:\n\n"
        for ev in events:
            dt = datetime.fromisoformat(ev[1])
            loc = ev[2] or "не указано"
            dances = ev[3] or "не указаны"
            is_past = "⏰" if dt < datetime.now() else "✅"
            msg += f"{is_past} {dt.strftime('%d.%m %H:%M')} — {loc} | {dances}\n"

        await update.message.reply_text(msg)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика бота (только для админов)"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        conn = sqlite3.connect("events.db")
        cursor = conn.cursor()

        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM events")
        total_events = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM events")
        total_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM events WHERE event_datetime >= ?",
                       (datetime.now().isoformat(),))
        upcoming_events = cursor.fetchone()[0]

        conn.close()

        stats_msg = (
            "📊 Статистика бота:\n\n"
            f"• Всего событий: {total_events}\n"
            f"• Предстоящих событий: {upcoming_events}\n"
            f"• Уникальных пользователей: {total_users}\n"
            f"• Админов: {len(ADMIN_IDS)}\n"
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

    await update.message.reply_text(help_text, reply_markup=get_main_menu())


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)


def main():
    # Инициализация базы данных
    init_db()

    # Создаем Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Обработчик диалога
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
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
        fallbacks=[CommandHandler("start", start)],
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
    application.add_handler(CallbackQueryHandler(button_handler))

    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)

    # Запускаем бота
    print("✅ Бот запущен с системой прав!")
    print(f"👑 Админы: {ADMIN_IDS}")

    application.run_polling()


if __name__ == "__main__":
    main()

