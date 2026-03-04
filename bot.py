import logging
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ─── НАСТРОЙКИ ────────────────────────────────────────────────────────────────
BOT_TOKEN = "8664115456:AAF8ttjaw_jTj7vuvtx7pa_ksVbr5jjZht4"          # токен от @BotFather
ADMIN_CHAT_ID = 598192209              # ваш личный Chat ID

TRAINER_NAME = "Александр Селезнев"
PHONE = "+7 (916) 413-05-22"
CITY = "г. Мытищи"

SERVICES = [
    ("🎯 Послушание (ОКД)", 1500, "60 мин"),
    ("🧠 Коррекция поведения", 2500, "90 мин"),
    ("🐶 Щенячья группа", 1000, "45 мин"),
    ("🏃 Аджилити / спорт", 1800, "60 мин"),
    ("⭐ Индивидуальное занятие", 2000, "60 мин"),
]

PROBLEMS = [
    "Тянет поводок", "Прыгает на людей", "Агрессия",
    "Страхи/тревога", "Не слушается команд", "Другое"
]

WORK_HOURS = list(range(9, 20))  # 9:00 — 19:00

# ─── СОСТОЯНИЯ ДИАЛОГА ────────────────────────────────────────────────────────
(OWNER_NAME, DOG_NAME, BREED, AGE, PROBLEMS_STEP,
 PHONE_STEP, SERVICE, DATE, TIME_STEP) = range(9)

bookings = {}  # хранилище записей в памяти

logging.basicConfig(level=logging.INFO)

# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ──────────────────────────────────────────────────
def get_days():
    days = []
    today = datetime.now()
    day_names = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]
    month_names = ["янв","фев","мар","апр","май","июн",
                   "июл","авг","сен","окт","ноя","дек"]
    for i in range(1, 8):
        d = today + timedelta(days=i)
        label = f"{day_names[d.weekday()]} {d.day} {month_names[d.month-1]}"
        key = d.strftime("%Y-%m-%d")
        days.append((label, key))
    return days

def get_free_slots(date_key):
    booked = bookings.get(date_key, [])
    return [f"{h:02d}:00" for h in WORK_HOURS if f"{h:02d}:00" not in booked]

# ─── ХЕНДЛЕРЫ ─────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("📅 Записаться на занятие", callback_data="book")],
        [InlineKeyboardButton("💰 Услуги и цены", callback_data="services")],
        [InlineKeyboardButton("📲 Контакты", callback_data="contacts")],
    ]
    await update.message.reply_text(
        f"🐾 Привет! Я бот-помощник кинолога *{TRAINER_NAME}*.\n\n"
        "Помогу записать вашу собаку на занятие — это займёт пару минут!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "services":
        text = f"*Услуги кинолога {TRAINER_NAME}:*\n\n"
        text += "\n".join(f"{s[0]} — {s[1]} ₽ / {s[2]}" for s in SERVICES)
        kb = [[InlineKeyboardButton("📅 Записаться", callback_data="book")]]
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data == "contacts":
        text = (f"📲 *Контакты {TRAINER_NAME}:*\n\n"
                f"✈️ Telegram: @Professional_dog_trainer_bot\n"
                f"📞 Телефон: {PHONE}\n"
                f"📍 Адрес: {CITY}")
        kb = [[InlineKeyboardButton("📅 Записаться", callback_data="book")]]
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data == "book":
        await q.edit_message_text("Отлично! Как вас зовут?")
        return OWNER_NAME

    elif data.startswith("svc_"):
        idx = int(data.split("_")[1])
        ctx.user_data["service"] = SERVICES[idx]
        days = get_days()
        kb = [[InlineKeyboardButton(label, callback_data=f"date_{key}")] for label, key in days]
        await q.edit_message_text("📅 Выберите удобный день:", reply_markup=InlineKeyboardMarkup(kb))
        return DATE

    elif data.startswith("date_"):
        date_key = data.split("_", 1)[1]
        ctx.user_data["date_key"] = date_key
        ctx.user_data["date_label"] = next(l for l, k in get_days() if k == date_key)
        slots = get_free_slots(date_key)
        if not slots:
            await q.edit_message_text("На этот день нет свободных слотов. Выберите другой.")
            days = get_days()
            kb = [[InlineKeyboardButton(l, callback_data=f"date_{k}")] for l, k in days]
            await q.edit_message_text("📅 Выберите другой день:", reply_markup=InlineKeyboardMarkup(kb))
            return DATE
        kb = [[InlineKeyboardButton(t, callback_data=f"time_{t}")] for t in slots]
        await q.edit_message_text("🕐 Выберите время:", reply_markup=InlineKeyboardMarkup(kb))
        return TIME_STEP

    elif data.startswith("time_"):
        time = data.split("_")[1]
        ctx.user_data["time"] = time
        await confirm_booking(q, ctx)
        return ConversationHandler.END

    elif data == "confirm":
        await finalize_booking(q, ctx)
        return ConversationHandler.END

async def get_owner_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["owner_name"] = update.message.text
    await update.message.reply_text(f"Приятно познакомиться, {update.message.text}! 😊\nКак зовут вашего питомца?")
    return DOG_NAME

async def get_dog_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["dog_name"] = update.message.text
    await update.message.reply_text(f"{update.message.text} — отличное имя! 🐕\nКакая порода?")
    return BREED

async def get_breed(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["breed"] = update.message.text
    await update.message.reply_text("Сколько лет/месяцев питомцу?")
    return AGE

async def get_age(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["age"] = update.message.text
    kb = []
    for p in PROBLEMS:
        kb.append([InlineKeyboardButton(p, callback_data=f"prob_{p}")])
    kb.append([InlineKeyboardButton("✅ Продолжить", callback_data="prob_done")])
    await update.message.reply_text(
        "Есть ли особенности поведения?\n(выберите несколько или сразу нажмите «Продолжить»)",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    ctx.user_data["problems"] = []
    return PROBLEMS_STEP

async def handle_problem(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "prob_done":
        await q.edit_message_text("Укажите ваш номер телефона:")
        return PHONE_STEP
    problem = q.data.replace("prob_", "")
    probs = ctx.user_data.get("problems", [])
    if problem not in probs:
        probs.append(problem)
    ctx.user_data["problems"] = probs
    await q.answer(f"✓ {problem}", show_alert=False)
    return PROBLEMS_STEP

async def get_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["phone"] = update.message.text
    kb = [[InlineKeyboardButton(s[0], callback_data=f"svc_{i}")] for i, s in enumerate(SERVICES)]
    await update.message.reply_text("Выберите тип занятия:", reply_markup=InlineKeyboardMarkup(kb))
    return SERVICE

async def confirm_booking(q, ctx):
    d = ctx.user_data
    svc = d["service"]
    probs = ", ".join(d.get("problems", [])) or "Не указано"
    text = (f"📋 *Проверьте данные:*\n\n"
            f"👤 {d['owner_name']} · 📞 {d['phone']}\n"
            f"🐕 {d['dog_name']} ({d['breed']}, {d['age']})\n"
            f"{svc[0]} — {svc[1]} ₽\n"
            f"📅 {d['date_label']} в {d['time']}\n"
            f"⚡ {probs}")
    kb = [[InlineKeyboardButton("✅ Подтвердить запись", callback_data="confirm")]]
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def finalize_booking(q, ctx):
    d = ctx.user_data
    svc = d["service"]
    probs = ", ".join(d.get("problems", [])) or "Не указано"

    # Сохраняем слот
    date_key = d["date_key"]
    if date_key not in bookings:
        bookings[date_key] = []
    bookings[date_key].append(d["time"])

    # Клиенту
    await q.edit_message_text(
        f"🎉 *Запись подтверждена!*\n\n"
        f"👤 {d['owner_name']} · 📞 {d['phone']}\n"
        f"🐕 {d['dog_name']} ({d['breed']}, {d['age']})\n"
        f"{svc[0]} — {svc[1]} ₽\n"
        f"📅 {d['date_label']} в {d['time']}\n\n"
        f"Кинолог *{TRAINER_NAME}* свяжется с вами для подтверждения. До встречи! 🐾",
        parse_mode="Markdown"
    )

    # Уведомление вам
    await q.get_bot().send_message(
        chat_id=ADMIN_CHAT_ID,
        text=(f"🔔 *Новая запись!*\n\n"
              f"👤 {d['owner_name']} · 📞 {d['phone']}\n"
              f"🐕 {d['dog_name']} ({d['breed']}, {d['age']})\n"
              f"{svc[0]} — {svc[1]} ₽\n"
              f"📅 {d['date_label']} в {d['time']}\n"
              f"⚡ {probs}"),
        parse_mode="Markdown"
    )

# ─── ЗАПУСК ───────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button, pattern="^book$")],
        states={
            OWNER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_owner_name)],
            DOG_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, get_dog_name)],
            BREED:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_breed)],
            AGE:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            PROBLEMS_STEP: [CallbackQueryHandler(handle_problem, pattern="^prob_")],
            PHONE_STEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            SERVICE:    [CallbackQueryHandler(button, pattern="^svc_")],
            DATE:       [CallbackQueryHandler(button, pattern="^date_")],
            TIME_STEP:  [CallbackQueryHandler(button, pattern="^time_")],
        },
        fallbacks=[CommandHandler("start", start)],
        per_message=False,
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(conv)
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
```

И файл **`requirements.txt`**:
```
python-telegram-bot==20.7
