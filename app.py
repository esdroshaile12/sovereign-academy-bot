import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DB_PATH = os.getenv('DB_PATH', 'sovereign_academy.db')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_TELEGRAM_ID = int(os.getenv('ADMIN_TELEGRAM_ID', '0'))

LANGUAGE, NAME, TRACK, MENU, SUBMIT_WARRIOR, SUBMIT_LOVER, SUBMIT_MAGICIAN, SUBMIT_KING, WEEKLY_Q1, WEEKLY_Q2, WEEKLY_Q3, OUTREACH_BIZ, OUTREACH_METHOD, OUTREACH_RESULT = range(14)

TRACKS = [
    'Video Editing',
    'Social Media Management',
    'Promotional Content Creation',
    'Graphic Design',
]

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton('My Day'), KeyboardButton('Submit Proof')],
        [KeyboardButton('My Progress'), KeyboardButton('My Track')],
        [KeyboardButton('Outreach Log'), KeyboardButton('Weekly Audit')],
        [KeyboardButton('Help')],
    ],
    resize_keyboard=True
)

LANG_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton('English')], [KeyboardButton('Amharic')]],
    resize_keyboard=True,
    one_time_keyboard=True
)

TRACK_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton(track)] for track in TRACKS],
    resize_keyboard=True,
    one_time_keyboard=True
)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            language TEXT,
            track TEXT,
            joined_at TEXT,
            streak INTEGER DEFAULT 0,
            current_day INTEGER DEFAULT 1,
            is_admin INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            day_number INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            theme TEXT,
            video_script TEXT,
            warrior_task TEXT,
            lover_task TEXT,
            magician_task TEXT,
            king_task TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            academy_day INTEGER NOT NULL,
            warrior_proof TEXT,
            lover_proof TEXT,
            magician_proof TEXT,
            king_proof TEXT,
            submitted_at TEXT,
            UNIQUE(telegram_id, academy_day)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS weekly_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            week_number INTEGER NOT NULL,
            q1 TEXT,
            q2 TEXT,
            q3 TEXT,
            submitted_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS outreach_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            business_name TEXT,
            contact_method TEXT,
            result TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    seed_lessons(conn)
    conn.close()


def seed_lessons(conn):
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) as count FROM lessons')
    count = cur.fetchone()['count']
    if count > 0:
        return

    day_1_video = (
        'Day 1 — The End of Drifting\n\n'
        '0–2: Right now there are two kinds of men: men who drift through life and men who direct their lives. '
        'Most people drift through scrolling, consuming, and watching others succeed.\n\n'
        '2–5: If your life is not where you want it to be, either you lack skill or discipline. '
        'Information without execution is entertainment. Execution changes life.\n\n'
        '5–8: A sovereign man rules himself. He asks not what he feels like doing, but what must be done.\n\n'
        '8–11: Every academy day has four pillars: Warrior, Lover, Magician, King.\n\n'
        '11–14: Today you complete four missions. They are simple, but not optional.\n\n'
        '14–15: Today is the day you stop drifting and begin executing.'
    )

    cur.execute("""
        INSERT OR REPLACE INTO lessons
        (day_number, title, theme, video_script, warrior_task, lover_task, magician_task, king_task)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        1,
        'Stop Drifting',
        'You stop consuming life and start producing value.',
        day_1_video,
        '50 pushups, 50 squats, 1 minute plank, then cold water on face or cold shower. No phone before completing this.',
        'Read Atomic Habits: Introduction and Chapter 1. Submit one insight from the reading.',
        'Observe 3 businesses today. Write one sentence for each: how could I help this business?',
        'Identify one money leak in your life and write how you will stop it.'
    ))

    cur.execute("""
        INSERT OR REPLACE INTO lessons
        (day_number, title, theme, video_script, warrior_task, lover_task, magician_task, king_task)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        2,
        'Control Your Morning',
        'Disciplined men direct the first hour.',
        'Day 2 lesson placeholder from academy structure.',
        '50 pushups, 50 squats, 20 lunges, 2 minute plank, cold water face wash or shower.',
        'Read Atomic Habits Chapter 2. Answer: What kind of man am I becoming through my habits?',
        'Observe 5 businesses and note how they attract customers.',
        'Write your basic daily schedule and follow the first-hour rule.'
    ))

    conn.commit()


def upsert_user(telegram_id: int, username: str, full_name: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (telegram_id, username, full_name, joined_at, is_admin)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username=excluded.username,
            full_name=excluded.full_name
    """, (
        telegram_id,
        username,
        full_name,
        datetime.utcnow().isoformat(),
        1 if telegram_id == ADMIN_TELEGRAM_ID else 0
    ))
    conn.commit()
    conn.close()


def update_user_field(telegram_id: int, field: str, value: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f'UPDATE users SET {field} = ? WHERE telegram_id = ?', (value, telegram_id))
    conn.commit()
    conn.close()


def get_user(telegram_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cur.fetchone()
    conn.close()
    return user


def get_lesson(day_number: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM lessons WHERE day_number = ?', (day_number,))
    lesson = cur.fetchone()
    conn.close()
    return lesson


def save_submission_field(telegram_id: int, academy_day: int, field: str, value: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('INSERT OR IGNORE INTO submissions (telegram_id, academy_day, submitted_at) VALUES (?, ?, ?)',
                (telegram_id, academy_day, datetime.utcnow().isoformat()))
    cur.execute(f'UPDATE submissions SET {field} = ?, submitted_at = ? WHERE telegram_id = ? AND academy_day = ?',
                (value, datetime.utcnow().isoformat(), telegram_id, academy_day))
    conn.commit()
    conn.close()


def get_submission(telegram_id: int, academy_day: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM submissions WHERE telegram_id = ? AND academy_day = ?', (telegram_id, academy_day))
    row = cur.fetchone()
    conn.close()
    return row


def get_progress_summary(telegram_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT current_day, streak, track FROM users WHERE telegram_id = ?', (telegram_id,))
    user = cur.fetchone()
    cur.execute('SELECT COUNT(*) as count FROM submissions WHERE telegram_id = ?', (telegram_id,))
    completed = cur.fetchone()['count']
    cur.execute('SELECT COUNT(*) as count FROM outreach_logs WHERE telegram_id = ?', (telegram_id,))
    outreach = cur.fetchone()['count']
    conn.close()
    return user, completed, outreach


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_user(user.id, user.username or '', user.full_name)
    await update.message.reply_text(
        'Welcome to Sovereign Academy. Choose your language.',
        reply_markup=LANG_MENU
    )
    return LANGUAGE


async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = update.message.text.strip()
    update_user_field(update.effective_user.id, 'language', language)
    await update.message.reply_text('Good. Now send the name you want the academy to call you.')
    return NAME


async def save_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    update_user_field(update.effective_user.id, 'full_name', name)
    await update.message.reply_text('Choose your skill track.', reply_markup=TRACK_MENU)
    return TRACK


async def choose_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track = update.message.text.strip()
    update_user_field(update.effective_user.id, 'track', track)
    await update.message.reply_text(
        'You are in. Sovereign Academy begins now. Use the menu below.',
        reply_markup=MAIN_MENU
    )
    return MENU


async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text('Send /start first.')
        return ConversationHandler.END

    if text == 'My Day':
        lesson = get_lesson(user['current_day'])
        if not lesson:
            await update.message.reply_text('No lesson found for your current day yet.')
            return MENU
        message = (
            f"Day {lesson['day_number']} — {lesson['title']}\n\n"
            f"Theme: {lesson['theme']}\n\n"
            f"Warrior: {lesson['warrior_task']}\n\n"
            f"Lover: {lesson['lover_task']}\n\n"
            f"Magician: {lesson['magician_task']}\n\n"
            f"King: {lesson['king_task']}"
        )
        await update.message.reply_text(message)
        return MENU

    if text == 'Submit Proof':
        await update.message.reply_text('Send your Warrior proof first. Example: workout complete + short note.')
        return SUBMIT_WARRIOR

    if text == 'My Progress':
        info, completed, outreach = get_progress_summary(update.effective_user.id)
        progress_text = (
            f"Current Day: {info['current_day']}\n"
            f"Track: {info['track'] or 'Not chosen'}\n"
            f"Streak: {info['streak']}\n"
            f"Completed day submissions: {completed}\n"
            f"Outreach logs: {outreach}"
        )
        await update.message.reply_text(progress_text)
        return MENU

    if text == 'My Track':
        await update.message.reply_text(f"Your current track is: {user['track']}")
        return MENU

    if text == 'Outreach Log':
        await update.message.reply_text('Send the business name you contacted.')
        return OUTREACH_BIZ

    if text == 'Weekly Audit':
        await update.message.reply_text('Weekly Audit Q1: How many days did you fully complete this week?')
        return WEEKLY_Q1

    if text == 'Help':
        await update.message.reply_text(
            "Use My Day to see today's tasks. Use Submit Proof to submit the 4 pillars. "
            'Use Outreach Log to record businesses contacted. Use Weekly Audit once every 7 days.'
        )
        return MENU

    if text == '/admin':
        if update.effective_user.id != ADMIN_TELEGRAM_ID:
            await update.message.reply_text('You are not an admin.')
            return MENU
        await update.message.reply_text('Admin mode is basic in MVP. Available command: /broadcast Your message here')
        return MENU

    await update.message.reply_text('Choose an option from the menu.')
    return MENU


async def submit_warrior(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    save_submission_field(update.effective_user.id, user['current_day'], 'warrior_proof', update.message.text)
    await update.message.reply_text('Warrior proof saved. Now send your Lover proof.')
    return SUBMIT_LOVER


async def submit_lover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    save_submission_field(update.effective_user.id, user['current_day'], 'lover_proof', update.message.text)
    await update.message.reply_text('Lover proof saved. Now send your Magician proof.')
    return SUBMIT_MAGICIAN


async def submit_magician(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    save_submission_field(update.effective_user.id, user['current_day'], 'magician_proof', update.message.text)
    await update.message.reply_text('Magician proof saved. Now send your King proof.')
    return SUBMIT_KING


async def submit_king(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    save_submission_field(update.effective_user.id, user['current_day'], 'king_proof', update.message.text)

    submission = get_submission(update.effective_user.id, user['current_day'])
    if submission and all([submission['warrior_proof'], submission['lover_proof'], submission['magician_proof'], submission['king_proof']]):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('UPDATE users SET streak = streak + 1, current_day = current_day + 1 WHERE telegram_id = ?', (update.effective_user.id,))
        conn.commit()
        conn.close()
        await update.message.reply_text('All 4 proofs saved. Day complete. You advanced to the next day.', reply_markup=MAIN_MENU)
    else:
        await update.message.reply_text('King proof saved.', reply_markup=MAIN_MENU)
    return MENU


async def weekly_q1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['weekly_q1'] = update.message.text.strip()
    await update.message.reply_text('Weekly Audit Q2: What did you learn this week?')
    return WEEKLY_Q2


async def weekly_q2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['weekly_q2'] = update.message.text.strip()
    await update.message.reply_text('Weekly Audit Q3: What is your main weakness next week?')
    return WEEKLY_Q3


async def weekly_q3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q3 = update.message.text.strip()
    user = get_user(update.effective_user.id)
    week_number = max(1, ((user['current_day'] - 1) // 7) + 1)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO weekly_audits (telegram_id, week_number, q1, q2, q3, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        update.effective_user.id,
        week_number,
        context.user_data.get('weekly_q1', ''),
        context.user_data.get('weekly_q2', ''),
        q3,
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()

    await update.message.reply_text('Weekly audit submitted.', reply_markup=MAIN_MENU)
    return MENU


async def outreach_biz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['business_name'] = update.message.text.strip()
    await update.message.reply_text('What contact method did you use? Example: Telegram, phone, Instagram, in person.')
    return OUTREACH_METHOD


async def outreach_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['contact_method'] = update.message.text.strip()
    await update.message.reply_text('What was the result? Example: no reply, replied, meeting, paid task.')
    return OUTREACH_RESULT


async def outreach_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.message.text.strip()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO outreach_logs (telegram_id, business_name, contact_method, result, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        update.effective_user.id,
        context.user_data.get('business_name', ''),
        context.user_data.get('contact_method', ''),
        result,
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()
    await update.message.reply_text('Outreach log saved.', reply_markup=MAIN_MENU)
    return MENU


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        await update.message.reply_text('You are not authorized.')
        return

    message = update.message.text.replace('/broadcast', '', 1).strip()
    if not message:
        await update.message.reply_text('Usage: /broadcast Your message here')
        return

    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT telegram_id FROM users')
    users = cur.fetchall()
    conn.close()

    sent = 0
    for row in users:
        try:
            await context.bot.send_message(chat_id=row['telegram_id'], text=message)
            sent += 1
        except Exception as exc:
            logger.warning(f'Failed to send to {row["telegram_id"]}: {exc}')

    await update.message.reply_text(f'Broadcast sent to {sent} users.')


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Cancelled.', reply_markup=MAIN_MENU)
    return MENU


def main():
    if not BOT_TOKEN:
        raise ValueError('BOT_TOKEN environment variable is missing.')

    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LANGUAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_language)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_name)],
            TRACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_track)],
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu_router)],
            SUBMIT_WARRIOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_warrior)],
            SUBMIT_LOVER: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_lover)],
            SUBMIT_MAGICIAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_magician)],
            SUBMIT_KING: [MessageHandler(filters.TEXT & ~filters.COMMAND, submit_king)],
            WEEKLY_Q1: [MessageHandler(filters.TEXT & ~filters.COMMAND, weekly_q1)],
            WEEKLY_Q2: [MessageHandler(filters.TEXT & ~filters.COMMAND, weekly_q2)],
            WEEKLY_Q3: [MessageHandler(filters.TEXT & ~filters.COMMAND, weekly_q3)],
            OUTREACH_BIZ: [MessageHandler(filters.TEXT & ~filters.COMMAND, outreach_biz)],
            OUTREACH_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, outreach_method)],
            OUTREACH_RESULT: [MessageHandler(filters.TEXT & ~filters.COMMAND, outreach_result)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler('broadcast', broadcast))

    logger.info('Bot is starting...')
    app.run_polling()


if __name__ == '__main__':
    main()
