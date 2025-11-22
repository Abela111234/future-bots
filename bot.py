# Install dependencies on FPS.ms:
# pip install python-telegram-bot pandas

import sqlite3
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# -----------------------------
# Config
# -----------------------------
BOT_TOKEN = "8266067770:AAE0b1sXQdcfY44E7D6r4hTzg8afKH2xt5E"   # Replace with your token
ADMIN_PASSWORD = "mathematicsisthebest"   # Replace with your password
CSV_COLUMNS = ['Student Name', 'Grade', 'Section', 'Roll Number', 
               'Math', 'English', 'Physics', 'Chemistry', 'Biology', 'IT', 
               'Economics', 'History', 'Geography', 'Citizenship', 'Amharic', 
               'Kembatissa', 'Com.m', 'Web.dev', 'Art', 'Sport', 'CTE', 
               'Social Studies', 'General Science', 'Marketing', 'Accounting']

# Conversation states
ADMIN_PASSWORD_INPUT, ADMIN_MENU, CSV_UPLOAD, ANNOUNCE_TEXT, DELETE_ANNOUNCE, STUDENT_GRADE, STUDENT_SECTION, STUDENT_ROLL, STUDENT_NAME = range(9)

# -----------------------------
# Database Setup
# -----------------------------
conn = sqlite3.connect("school_bot.db", check_same_thread=False)
c = conn.cursor()

# Students table
c.execute("""
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    name TEXT,
    grade INT,
    section TEXT,
    roll_number INT,
    chat_id INT
)
""")

# Results table
c.execute("""
CREATE TABLE IF NOT EXISTS results (
    student_id TEXT,
    subject TEXT,
    score REAL,
    PRIMARY KEY(student_id, subject),
    FOREIGN KEY(student_id) REFERENCES students(student_id)
)
""")

# Announcements table
c.execute("""
CREATE TABLE IF NOT EXISTS announcements (
    announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT
)
""")
conn.commit()

# -----------------------------
# Helper Functions
# -----------------------------
def generate_student_id(grade, section, roll_number):
    return f"G{grade}S{section}R{roll_number}"

def insert_student(student_id, name, grade, section, roll_number):
    c.execute("""
    INSERT OR IGNORE INTO students(student_id, name, grade, section, roll_number)
    VALUES (?, ?, ?, ?, ?)
    """, (student_id, name, grade, section, roll_number))
    conn.commit()

def insert_result(student_id, subject, score):
    if pd.notna(score):
        c.execute("""
        INSERT OR REPLACE INTO results(student_id, subject, score)
        VALUES (?, ?, ?)
        """, (student_id, subject, float(score)))
        conn.commit()

def verify_student(student_id, name):
    c.execute("SELECT * FROM students WHERE student_id=? AND LOWER(name)=?", (student_id, name.lower()))
    return c.fetchone()

def fetch_student_scores(student_id):
    c.execute("SELECT subject, score FROM results WHERE student_id=?", (student_id,))
    rows = c.fetchall()
    subject_scores = {sub: score for sub, score in rows if score is not None}
    total = sum(subject_scores.values())
    average = total / len(subject_scores) if subject_scores else 0
    return subject_scores, total, average

def calculate_rank(student_id):
    c.execute("SELECT grade, section FROM students WHERE student_id=?", (student_id,))
    res = c.fetchone()
    if not res:
        return None
    grade, section = res
    c.execute("SELECT student_id FROM students WHERE grade=? AND section=?", (grade, section))
    students = [r[0] for r in c.fetchall()]
    totals = []
    for sid in students:
        _, total, _ = fetch_student_scores(sid)
        totals.append((sid, total))
    totals.sort(key=lambda x: x[1], reverse=True)
    rank = 1
    prev_total = None
    skip = 0
    for sid, t in totals:
        if prev_total is None:
            prev_total = t
        elif t < prev_total:
            rank += skip + 1
            skip = 0
            prev_total = t
        else:
            skip += 1
        if sid == student_id:
            return rank

# -----------------------------
# Student Handlers
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Please enter your Grade (number):")
    return STUDENT_GRADE

async def student_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['grade'] = update.message.text
    await update.message.reply_text("Enter your Section (letter):")
    return STUDENT_SECTION

async def student_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['section'] = update.message.text
    await update.message.reply_text("Enter your Roll Number:")
    return STUDENT_ROLL

async def student_roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['roll_number'] = update.message.text
    await update.message.reply_text("Enter your full name:")
    return STUDENT_NAME

async def student_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    grade = context.user_data['grade']
    section = context.user_data['section']
    roll = context.user_data['roll_number']
    student_id = generate_student_id(grade, section, roll)
    context.user_data['chat_id'] = update.message.chat_id
    student_row = verify_student(student_id, name)
    if student_row:
        c.execute("UPDATE students SET chat_id=? WHERE student_id=?", (update.message.chat_id, student_id))
        conn.commit()
        subjects, total, average = fetch_student_scores(student_id)
        rank = calculate_rank(student_id)
        msg = ""
        for sub, score in subjects.items():  # Only show subjects with scores
            msg += f"{sub}: {score}\n"
        msg += f"Total: {total}\nAverage: {average:.2f}\nRank: {rank}"
        await update.message.reply_text(msg)
        return ConversationHandler.END
    else:
        await update.message.reply_text("Student not found. Please check your details or contact admin.")
        return ConversationHandler.END

# -----------------------------
# Admin Handlers
# -----------------------------
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter admin password:")
    return ADMIN_PASSWORD_INPUT

async def admin_password_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == ADMIN_PASSWORD:
        keyboard = [['Upload CSV', 'Post Announcement', 'Delete Announcement']]
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Admin menu:", reply_markup=markup)
        return ADMIN_MENU
    else:
        await update.message.reply_text("Wrong password. Access denied.")
        return ConversationHandler.END

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice == "Upload CSV":
        await update.message.reply_text("Please send the CSV file.")
        return CSV_UPLOAD
    elif choice == "Post Announcement":
        await update.message.reply_text("Send announcement text:")
        return ANNOUNCE_TEXT
    elif choice == "Delete Announcement":
        c.execute("SELECT announcement_id, text FROM announcements")
        rows = c.fetchall()
        if not rows:
            await update.message.reply_text("No announcements to delete.")
            return ADMIN_MENU
        msg = "Announcements:\n"
        for r in rows:
            msg += f"{r[0]}: {r[1]}\n"
        await update.message.reply_text(msg + "\nSend the ID of the announcement to delete:")
        return DELETE_ANNOUNCE
    else:
        await update.message.reply_text("Invalid option. Use the buttons.")
        return ADMIN_MENU

async def csv_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document:
        file = await update.message.document.get_file()
        file_path = "uploaded.csv"
        await file.download_to_drive(file_path)
        try:
            df = pd.read_csv(file_path)
            missing_cols = [col for col in CSV_COLUMNS if col not in df.columns]
            if missing_cols:
                await update.message.reply_text(f"CSV missing columns: {missing_cols}")
                return ADMIN_MENU
            for _, row in df.iterrows():
                student_id = generate_student_id(row['Grade'], row['Section'], row['Roll Number'])
                insert_student(student_id, row['Student Name'], row['Grade'], row['Section'], row['Roll Number'])
                for sub in CSV_COLUMNS[4:]:
                    insert_result(student_id, sub, row.get(sub))
            await update.message.reply_text("CSV uploaded and database updated successfully!")
        except Exception as e:
            await update.message.reply_text(f"Error processing CSV: {e}")
    else:
        await update.message.reply_text("Please send a valid CSV file.")
    return ADMIN_MENU

async def announce_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    c.execute("INSERT INTO announcements(text) VALUES (?)", (text,))
    conn.commit()
    c.execute("SELECT chat_id FROM students WHERE chat_id IS NOT NULL")
    chat_ids = [r[0] for r in c.fetchall()]
    for cid in chat_ids:
        try:
            await context.bot.send_message(cid, f"Announcement:\n{text}")
        except:
            pass
    await update.message.reply_text("Announcement posted and broadcasted!")
    return ADMIN_MENU

async def delete_announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        a_id = int(update.message.text)
        c.execute("DELETE FROM announcements WHERE announcement_id=?", (a_id,))
        conn.commit()
        await update.message.reply_text("Announcement deleted!")
    except:
        await update.message.reply_text("Invalid ID.")
    return ADMIN_MENU

async def show_announcements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c.execute("SELECT text FROM announcements")
    rows = c.fetchall()
    if not rows:
        await update.message.reply_text("No announcements at the moment.")
        return
    msg = "Announcements:\n"
    for r in rows:
        msg += f"{r[0]}\n"
    await update.message.reply_text(msg)

# -----------------------------
# Main
# -----------------------------
app = ApplicationBuilder().token(BOT_TOKEN).build()

student_conv = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        STUDENT_GRADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, student_grade)],
        STUDENT_SECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, student_section)],
        STUDENT_ROLL: [MessageHandler(filters.TEXT & ~filters.COMMAND, student_roll)],
        STUDENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, student_name)],
    },
    fallbacks=[]
)

admin_conv = ConversationHandler(
    entry_points=[CommandHandler('admin', admin)],
    states={
        ADMIN_PASSWORD_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_password_input)],
        ADMIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_menu)],
        CSV_UPLOAD: [MessageHandler(filters.Document.ALL, csv_upload)],
        ANNOUNCE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, announce_text)],
        DELETE_ANNOUNCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_announce)],
    },
    fallbacks=[]
)

app.add_handler(student_conv)
app.add_handler(admin_conv)
app.add_handler(CommandHandler('announcements', show_announcements))

app.run_polling()
