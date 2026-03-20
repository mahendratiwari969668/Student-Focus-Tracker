from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import random
import smtplib
import os
import requests
from dotenv import load_dotenv
from email.mime.text import MIMEText
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta

# ============================================
# LOAD ENV
# ============================================
load_dotenv()

# ============================================
# FLASK APP CONFIG
# ============================================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "focusflow_super_secret_key_change_this")

# ============================================
# CONFIG
# ============================================
DB_NAME = "focusflow.db"

# Email config (Forgot Password OTP)
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

# SambaNova AI config
SAMBANOVA_API_KEY = os.getenv("SAMBANOVA_API_KEY")
SAMBANOVA_API_URL = os.getenv("SAMBANOVA_API_URL", "https://api.sambanova.ai/v1/chat/completions")
SAMBANOVA_MODEL = os.getenv("SAMBANOVA_MODEL", "Meta-Llama-3.1-8B-Instruct")


# ============================================
# DB HELPERS
# ============================================
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # USERS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # STUDY SESSIONS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            duration INTEGER NOT NULL,
            distractions INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # DAILY GOALS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            goal_seconds INTEGER NOT NULL DEFAULT 3600,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # SMART REMINDERS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            subject TEXT,
            remind_at TEXT NOT NULL,
            repeat_type TEXT DEFAULT 'once',
            is_done INTEGER DEFAULT 0,
            last_triggered_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.commit()
    conn.close()


# ============================================
# FORMAT HELPERS
# ============================================
def format_seconds(total_seconds):
    total_seconds = int(total_seconds or 0)
    hrs = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hrs > 0:
        return f"{hrs}h {mins}m {secs}s"
    elif mins > 0:
        return f"{mins}m {secs}s"
    else:
        return f"{secs}s"


def safe_int(value, default=0):
    try:
        return int(value)
    except:
        return default


# ============================================
# USER HELPERS
# ============================================
def get_user_by_email(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def create_user(name, email, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    hashed_password = generate_password_hash(password)

    try:
        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, hashed_password)
        )
        conn.commit()
        user_id = cursor.lastrowid

        cursor.execute(
            "INSERT OR IGNORE INTO daily_goals (user_id, goal_seconds) VALUES (?, ?)",
            (user_id, 3600)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print("Create User Error:", e)
        return False
    finally:
        conn.close()


def update_password(email, new_password):
    conn = get_db_connection()
    cursor = conn.cursor()
    hashed_password = generate_password_hash(new_password)

    try:
        cursor.execute(
            "UPDATE users SET password = ? WHERE email = ?",
            (hashed_password, email)
        )
        conn.commit()
        return True
    except Exception as e:
        print("Update Password Error:", e)
        return False
    finally:
        conn.close()


# ============================================
# EMAIL OTP
# ============================================
def send_otp_email(receiver_email, otp):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("\n" + "=" * 50)
        print("DEMO MODE: EMAIL NOT CONFIGURED")
        print(f"OTP for {receiver_email} is: {otp}")
        print("=" * 50 + "\n")
        return True

    try:
        subject = "FocusFlow Password Reset OTP"
        body = f"""
Hello,

Your FocusFlow password reset OTP is: {otp}

If you did not request this, ignore this email.

- FocusFlow
        """

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = receiver_email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()

        print("OTP Email Sent Successfully")
        return True

    except Exception as e:
        print("Email Error:", e)
        return False


# ============================================
# AUTH HELPERS
# ============================================
def login_required():
    return "user_id" in session


def current_user():
    if "user_id" not in session:
        return None
    return get_user_by_id(session["user_id"])


# ============================================
# SESSION HELPERS
# ============================================
def add_study_session(user_id, subject, duration, distractions=0, custom_datetime=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if custom_datetime:
            cursor.execute("""
                INSERT INTO study_sessions (user_id, subject, duration, distractions, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, subject, duration, distractions, custom_datetime))
        else:
            cursor.execute("""
                INSERT INTO study_sessions (user_id, subject, duration, distractions)
                VALUES (?, ?, ?, ?)
            """, (user_id, subject, duration, distractions))

        conn.commit()
        return True
    except Exception as e:
        print("Add Study Session Error:", e)
        return False
    finally:
        conn.close()


def get_total_study_seconds(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(SUM(duration), 0) AS total
        FROM study_sessions
        WHERE user_id = ?
    """, (user_id,))
    total = cursor.fetchone()["total"]
    conn.close()
    return total or 0


def get_today_study_seconds(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    today_str = date.today().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT COALESCE(SUM(duration), 0) AS total
        FROM study_sessions
        WHERE user_id = ? AND date(created_at) = ?
    """, (user_id, today_str))

    total = cursor.fetchone()["total"]
    conn.close()
    return total or 0


def get_total_sessions(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) AS cnt
        FROM study_sessions
        WHERE user_id = ?
    """, (user_id,))
    count = cursor.fetchone()["cnt"]
    conn.close()
    return count or 0


def get_total_distractions(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(SUM(distractions), 0) AS total
        FROM study_sessions
        WHERE user_id = ?
    """, (user_id,))
    total = cursor.fetchone()["total"]
    conn.close()
    return total or 0


def get_recent_sessions(user_id, limit=10):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT *
        FROM study_sessions
        WHERE user_id = ?
        ORDER BY datetime(created_at) DESC
        LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()

    sessions = []
    for row in rows:
        item = dict(row)
        item["duration_formatted"] = format_seconds(item["duration"])
        sessions.append(item)
    return sessions


def delete_study_session(user_id, session_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            DELETE FROM study_sessions
            WHERE id = ? AND user_id = ?
        """, (session_id, user_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print("Delete Session Error:", e)
        return False
    finally:
        conn.close()


def get_longest_single_session(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(MAX(duration), 0) AS max_duration
        FROM study_sessions
        WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row["max_duration"] if row else 0


def has_zero_distraction_session(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) AS cnt
        FROM study_sessions
        WHERE user_id = ? AND distractions = 0
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    return (row["cnt"] if row else 0) > 0


# ============================================
# GOAL HELPERS
# ============================================
def get_daily_goal_seconds(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT goal_seconds
        FROM daily_goals
        WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return row["goal_seconds"]
    return 3600


def set_daily_goal(user_id, goal_seconds):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO daily_goals (user_id, goal_seconds, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id)
            DO UPDATE SET goal_seconds = excluded.goal_seconds,
                          updated_at = CURRENT_TIMESTAMP
        """, (user_id, goal_seconds))
        conn.commit()
        return True
    except Exception as e:
        print("Set Goal Error:", e)
        return False
    finally:
        conn.close()


# ============================================
# ANALYTICS HELPERS
# ============================================
def get_subject_stats(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            subject,
            COUNT(*) AS session_count,
            COALESCE(SUM(duration), 0) AS total_duration,
            COALESCE(SUM(distractions), 0) AS total_distractions
        FROM study_sessions
        WHERE user_id = ?
        GROUP BY subject
        ORDER BY total_duration DESC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    stats = []
    max_duration = rows[0]["total_duration"] if rows else 0

    for row in rows:
        item = dict(row)
        item["total_duration_formatted"] = format_seconds(item["total_duration"])
        item["bar_percent"] = int((item["total_duration"] / max_duration) * 100) if max_duration > 0 else 0
        stats.append(item)

    return stats


def get_top_subject(user_id):
    stats = get_subject_stats(user_id)
    if stats:
        return stats[0]
    return None


def get_last_7_days_data(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    end_date = date.today()
    start_date = end_date - timedelta(days=6)

    cursor.execute("""
        SELECT
            date(created_at) AS session_date,
            COALESCE(SUM(duration), 0) AS total_duration
        FROM study_sessions
        WHERE user_id = ?
          AND date(created_at) BETWEEN ? AND ?
        GROUP BY date(created_at)
    """, (user_id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))

    rows = cursor.fetchall()
    conn.close()

    db_map = {row["session_date"]: row["total_duration"] for row in rows}

    data = []
    max_val = 0

    for i in range(7):
        day = start_date + timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        total = db_map.get(day_str, 0)

        data.append({
            "date": day_str,
            "label": day.strftime("%a"),
            "seconds": total,
            "formatted": format_seconds(total)
        })

        if total > max_val:
            max_val = total

    for item in data:
        item["bar_percent"] = int((item["seconds"] / max_val) * 100) if max_val > 0 else 0

    return data


def get_weekly_total(user_id):
    data = get_last_7_days_data(user_id)
    return sum(item["seconds"] for item in data)


def get_best_day(user_id):
    data = get_last_7_days_data(user_id)
    non_zero = [d for d in data if d["seconds"] > 0]
    if not non_zero:
        return None
    best = max(non_zero, key=lambda x: x["seconds"])
    return best


def get_current_streak(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT date(created_at) AS day
        FROM study_sessions
        WHERE user_id = ?
        ORDER BY day DESC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return 0

    days = [datetime.strptime(row["day"], "%Y-%m-%d").date() for row in rows]
    day_set = set(days)

    today = date.today()
    yesterday = today - timedelta(days=1)

    if today in day_set:
        current = today
    elif yesterday in day_set:
        current = yesterday
    else:
        return 0

    streak = 0
    while current in day_set:
        streak += 1
        current -= timedelta(days=1)

    return streak


def get_longest_streak(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT date(created_at) AS day
        FROM study_sessions
        WHERE user_id = ?
        ORDER BY day ASC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return 0

    days = [datetime.strptime(row["day"], "%Y-%m-%d").date() for row in rows]

    longest = 1
    current = 1

    for i in range(1, len(days)):
        if days[i] == days[i - 1] + timedelta(days=1):
            current += 1
            longest = max(longest, current)
        else:
            current = 1

    return longest


# ============================================
# ACHIEVEMENT HELPERS
# ============================================
def get_achievements(user_id):
    total_sessions = get_total_sessions(user_id)
    total_study = get_total_study_seconds(user_id)
    today_study = get_today_study_seconds(user_id)
    current_streak = get_current_streak(user_id)
    longest_streak = get_longest_streak(user_id)
    longest_session = get_longest_single_session(user_id)
    zero_distraction = has_zero_distraction_session(user_id)
    daily_goal = get_daily_goal_seconds(user_id)

    achievements = [
        {
            "title": "First Focus",
            "icon": "🎯",
            "desc": "Complete your first study session",
            "unlocked": total_sessions >= 1
        },
        {
            "title": "Consistency Starter",
            "icon": "📘",
            "desc": "Complete 3 study sessions",
            "unlocked": total_sessions >= 3
        },
        {
            "title": "Focus Warrior",
            "icon": "⚔️",
            "desc": "Complete 10 study sessions",
            "unlocked": total_sessions >= 10
        },
        {
            "title": "1 Hour Club",
            "icon": "⏱️",
            "desc": "Study for a total of 1 hour",
            "unlocked": total_study >= 3600
        },
        {
            "title": "5 Hour Beast",
            "icon": "🔥",
            "desc": "Study for a total of 5 hours",
            "unlocked": total_study >= 18000
        },
        {
            "title": "Streak Rookie",
            "icon": "📅",
            "desc": "Reach a 3-day streak",
            "unlocked": longest_streak >= 3
        },
        {
            "title": "Streak Master",
            "icon": "👑",
            "desc": "Reach a 7-day streak",
            "unlocked": longest_streak >= 7
        },
        {
            "title": "Deep Focus",
            "icon": "🧠",
            "desc": "Complete a single session of 1 hour or more",
            "unlocked": longest_session >= 3600
        },
        {
            "title": "Distraction Free",
            "icon": "🧘",
            "desc": "Complete at least 1 session with zero distractions",
            "unlocked": zero_distraction
        },
        {
            "title": "Goal Crusher",
            "icon": "🚀",
            "desc": "Complete today's full daily goal",
            "unlocked": today_study >= daily_goal and daily_goal > 0
        }
    ]

    unlocked_count = sum(1 for a in achievements if a["unlocked"])
    total_count = len(achievements)
    progress_percent = int((unlocked_count / total_count) * 100) if total_count > 0 else 0

    return achievements, unlocked_count, total_count, progress_percent


# ============================================
# REMINDER HELPERS
# ============================================
def add_reminder(user_id, title, message, subject, remind_at, repeat_type="once"):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO reminders (user_id, title, message, subject, remind_at, repeat_type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, title, message, subject, remind_at, repeat_type))
        conn.commit()
        return True
    except Exception as e:
        print("Add Reminder Error:", e)
        return False
    finally:
        conn.close()


def get_all_reminders(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM reminders
        WHERE user_id = ?
        ORDER BY datetime(remind_at) ASC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    reminders = []
    for row in rows:
        reminders.append(dict(row))
    return reminders


def get_due_reminders(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        SELECT *
        FROM reminders
        WHERE user_id = ?
          AND is_done = 0
          AND datetime(remind_at) <= datetime(?)
        ORDER BY datetime(remind_at) ASC
    """, (user_id, now_str))

    rows = cursor.fetchall()
    conn.close()

    reminders = []
    for row in rows:
        reminders.append(dict(row))
    return reminders


def mark_reminder_done(user_id, reminder_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE reminders
            SET is_done = 1
            WHERE id = ? AND user_id = ?
        """, (reminder_id, user_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print("Mark Reminder Done Error:", e)
        return False
    finally:
        conn.close()


def delete_reminder(user_id, reminder_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            DELETE FROM reminders
            WHERE id = ? AND user_id = ?
        """, (reminder_id, user_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print("Delete Reminder Error:", e)
        return False
    finally:
        conn.close()


def snooze_reminder(user_id, reminder_id, minutes=10):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT * FROM reminders
            WHERE id = ? AND user_id = ?
        """, (reminder_id, user_id))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False

        new_time = datetime.now() + timedelta(minutes=minutes)

        cursor.execute("""
            UPDATE reminders
            SET remind_at = ?, last_triggered_at = ?
            WHERE id = ? AND user_id = ?
        """, (
            new_time.strftime("%Y-%m-%d %H:%M:%S"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            reminder_id,
            user_id
        ))

        conn.commit()
        return True

    except Exception as e:
        print("Snooze Reminder Error:", e)
        return False
    finally:
        conn.close()


def process_recurring_reminders(user_id):
    due = get_due_reminders(user_id)
    if not due:
        return []

    now = datetime.now()
    processed_due = []

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        for reminder in due:
            processed_due.append(reminder)

            repeat_type = reminder["repeat_type"]
            remind_at_dt = datetime.strptime(reminder["remind_at"], "%Y-%m-%d %H:%M:%S")

            if repeat_type == "once":
                continue

            last_triggered = reminder["last_triggered_at"]
            if last_triggered:
                try:
                    last_triggered_dt = datetime.strptime(last_triggered, "%Y-%m-%d %H:%M:%S")
                    if (now - last_triggered_dt).total_seconds() < 30:
                        continue
                except:
                    pass

            next_time = remind_at_dt
            if repeat_type == "daily":
                while next_time <= now:
                    next_time += timedelta(days=1)
            elif repeat_type == "weekly":
                while next_time <= now:
                    next_time += timedelta(days=7)

            cursor.execute("""
                UPDATE reminders
                SET remind_at = ?, last_triggered_at = ?
                WHERE id = ? AND user_id = ?
            """, (
                next_time.strftime("%Y-%m-%d %H:%M:%S"),
                now.strftime("%Y-%m-%d %H:%M:%S"),
                reminder["id"],
                user_id
            ))

        conn.commit()

    except Exception as e:
        print("Process Recurring Reminders Error:", e)
    finally:
        conn.close()

    return processed_due


# ============================================
# AI HELPERS
# ============================================
def build_focusflow_context(user_id):
    user = get_user_by_id(user_id)
    total_seconds = get_total_study_seconds(user_id)
    today_seconds = get_today_study_seconds(user_id)
    total_sessions = get_total_sessions(user_id)
    total_distractions = get_total_distractions(user_id)
    current_streak = get_current_streak(user_id)
    longest_streak = get_longest_streak(user_id)
    daily_goal = get_daily_goal_seconds(user_id)
    subject_stats = get_subject_stats(user_id)
    top_subject = get_top_subject(user_id)
    weekly_total = get_weekly_total(user_id)
    best_day = get_best_day(user_id)
    achievements, unlocked_count, total_count, _ = get_achievements(user_id)

    subject_lines = []
    for s in subject_stats[:6]:
        subject_lines.append(
            f"- {s['subject']}: {s['total_duration_formatted']} | Sessions: {s['session_count']} | Distractions: {s['total_distractions']}"
        )

    if not subject_lines:
        subject_lines.append("- No study data yet")

    best_day_line = f"{best_day['label']} ({best_day['formatted']})" if best_day else "No best day yet"

    context = f"""
FocusFlow Student Data:
User Name: {user['name'] if user else 'Student'}
Total Study Time: {format_seconds(total_seconds)}
Today's Study Time: {format_seconds(today_seconds)}
Total Sessions: {total_sessions}
Total Distractions: {total_distractions}
Current Streak: {current_streak} days
Longest Streak: {longest_streak} days
Daily Goal: {format_seconds(daily_goal)}
Weekly Total (Last 7 Days): {format_seconds(weekly_total)}
Top Subject: {top_subject['subject'] if top_subject else 'None'}
Best Day This Week: {best_day_line}
Achievements Unlocked: {unlocked_count}/{total_count}

Subject-wise Analytics:
{chr(10).join(subject_lines)}
"""
    return context.strip()


def ask_sambanova_ai(user_id, user_question):
    if not SAMBANOVA_API_KEY:
        return "SambaNova API key is missing. Put the REAL secret key in your .env file as SAMBANOVA_API_KEY=your_actual_key"

    tracker_context = build_focusflow_context(user_id)

    system_prompt = f"""
You are FLOWBOT, a cute but highly practical AI study assistant inside the FocusFlow website.

Your role:
1. Help the student understand difficult paragraphs in simple language.
2. Give short hints if useful.
3. Help solve coding errors step by step.
4. Analyze the student's study tracker data and tell them what subject needs more focus.
5. Give specific, practical focus tips.
6. If the student asks what to study next, use the tracker data.
7. Be concise, useful, and easy to understand.
8. Keep answers clean and not too long unless asked.

IMPORTANT:
- Use the student's actual FocusFlow tracker data below.
- If the user asks something unrelated to study/productivity/coding, gently steer it back.
- Give direct and practical answers.
- If explaining a paragraph, use simple words first, then a short hint.
- If debugging code, mention likely cause + fix.

Student Tracker Context:
{tracker_context}
"""

    headers = {
        "Authorization": f"Bearer {SAMBANOVA_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": SAMBANOVA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question}
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }

    try:
        response = requests.post(
            SAMBANOVA_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        print("AI Status Code:", response.status_code)
        print("AI Raw Response:", response.text[:800])

        if response.status_code == 401:
            return "AI authentication failed (401). Your SambaNova API key is invalid or not the real secret key."

        if response.status_code == 400:
            return f"AI request failed (400). Most likely model name is wrong. Current model: {SAMBANOVA_MODEL}"

        if response.status_code >= 500:
            return f"AI server error ({response.status_code}). Try again later."

        response.raise_for_status()

        data = response.json()

        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                return choice["message"]["content"].strip()

        return "AI responded, but reply format was unexpected."

    except requests.exceptions.Timeout:
        return "AI request timed out."
    except requests.exceptions.RequestException as e:
        print("AI Request Error:", e)
        return f"AI request failed: {str(e)}"
    except Exception as e:
        print("AI Unexpected Error:", e)
        return f"Unexpected AI error: {str(e)}"


# ============================================
# ROUTES
# ============================================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not name or not email or not password:
            flash("All fields are required!", "error")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters!", "error")
            return redirect(url_for("register"))

        if get_user_by_email(email):
            flash("Email already registered!", "error")
            return redirect(url_for("register"))

        if create_user(name, email, password):
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))
        else:
            flash("Registration failed!", "error")
            return redirect(url_for("register"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("Email and password are required!", "error")
            return redirect(url_for("login"))

        user = get_user_by_email(email)

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password!", "error")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if not login_required():
        flash("Please login first!", "error")
        return redirect(url_for("login"))

    user = current_user()
    user_id = user["id"]

    total_seconds = get_total_study_seconds(user_id)
    today_seconds = get_today_study_seconds(user_id)
    total_sessions = get_total_sessions(user_id)
    total_distractions = get_total_distractions(user_id)
    sessions = get_recent_sessions(user_id, limit=10)

    daily_goal = get_daily_goal_seconds(user_id)
    goal_progress = int((today_seconds / daily_goal) * 100) if daily_goal > 0 else 0
    if goal_progress > 100:
        goal_progress = 100

    subject_stats = get_subject_stats(user_id)
    top_subject = get_top_subject(user_id)
    current_streak = get_current_streak(user_id)
    longest_streak = get_longest_streak(user_id)
    last_7_days = get_last_7_days_data(user_id)
    weekly_total = get_weekly_total(user_id)
    best_day = get_best_day(user_id)

    due_reminders = process_recurring_reminders(user_id)
    all_reminders = get_all_reminders(user_id)

    achievements, unlocked_count, total_badges, achievement_progress = get_achievements(user_id)

    return render_template(
        "dashboard.html",
        user_name=user["name"],
        total_seconds=total_seconds,
        total_seconds_formatted=format_seconds(total_seconds),
        today_seconds=today_seconds,
        today_seconds_formatted=format_seconds(today_seconds),
        total_sessions=total_sessions,
        total_distractions=total_distractions,
        sessions=sessions,
        daily_goal_seconds=daily_goal,
        daily_goal_formatted=format_seconds(daily_goal),
        goal_progress=goal_progress,
        subject_stats=subject_stats,
        top_subject=top_subject,
        current_streak=current_streak,
        longest_streak=longest_streak,
        last_7_days=last_7_days,
        weekly_total=weekly_total,
        weekly_total_formatted=format_seconds(weekly_total),
        best_day=best_day,
        due_reminders=due_reminders,
        all_reminders=all_reminders,
        achievements=achievements,
        unlocked_count=unlocked_count,
        total_badges=total_badges,
        achievement_progress=achievement_progress
    )


@app.route("/add-session", methods=["POST"])
def add_session():
    if not login_required():
        flash("Please login first!", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    subject = request.form.get("subject", "").strip()
    duration = request.form.get("duration", "").strip()
    distractions = request.form.get("distractions", "0").strip()

    if not subject:
        flash("Subject is required!", "error")
        return redirect(url_for("dashboard"))

    duration = safe_int(duration, 0)
    distractions = safe_int(distractions, 0)

    if duration <= 0:
        flash("Session duration must be greater than 0!", "error")
        return redirect(url_for("dashboard"))

    success = add_study_session(user_id, subject, duration, distractions)

    if success:
        flash("Live timer session saved successfully!", "success")
    else:
        flash("Failed to save live timer session!", "error")

    return redirect(url_for("dashboard"))


@app.route("/add-manual-session", methods=["POST"])
def add_manual_session():
    if not login_required():
        flash("Please login first!", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    subject = request.form.get("manual_subject", "").strip()
    manual_hours = request.form.get("manual_hours", "0").strip()
    manual_minutes = request.form.get("manual_minutes", "0").strip()
    manual_seconds = request.form.get("manual_seconds", "0").strip()
    manual_distractions = request.form.get("manual_distractions", "0").strip()
    manual_date = request.form.get("manual_date", "").strip()
    manual_time = request.form.get("manual_time", "").strip()

    if not subject or not manual_date or not manual_time:
        flash("Manual session needs subject, date and time!", "error")
        return redirect(url_for("dashboard"))

    h = safe_int(manual_hours, 0)
    m = safe_int(manual_minutes, 0)
    s = safe_int(manual_seconds, 0)
    distractions = safe_int(manual_distractions, 0)

    total_duration = h * 3600 + m * 60 + s

    if total_duration <= 0:
        flash("Manual session duration must be greater than 0!", "error")
        return redirect(url_for("dashboard"))

    custom_datetime = f"{manual_date} {manual_time}:00"

    success = add_study_session(user_id, subject, total_duration, distractions, custom_datetime)

    if success:
        flash("Manual session saved successfully!", "success")
    else:
        flash("Failed to save manual session!", "error")

    return redirect(url_for("dashboard"))


@app.route("/delete-session/<int:session_id>", methods=["POST"])
def delete_session(session_id):
    if not login_required():
        flash("Please login first!", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    success = delete_study_session(user_id, session_id)

    if success:
        flash("Session deleted successfully!", "success")
    else:
        flash("Failed to delete session or session not found!", "error")

    return redirect(url_for("dashboard"))


@app.route("/set-goal", methods=["POST"])
def set_goal():
    if not login_required():
        flash("Please login first!", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    goal_hours = request.form.get("goal_hours", "0").strip()
    goal_minutes = request.form.get("goal_minutes", "0").strip()
    goal_seconds = request.form.get("goal_seconds", "0").strip()

    h = safe_int(goal_hours, 0)
    m = safe_int(goal_minutes, 0)
    s = safe_int(goal_seconds, 0)

    total_goal_seconds = h * 3600 + m * 60 + s

    if total_goal_seconds <= 0:
        flash("Daily goal must be greater than 0!", "error")
        return redirect(url_for("dashboard"))

    success = set_daily_goal(user_id, total_goal_seconds)

    if success:
        flash("Daily goal updated successfully!", "success")
    else:
        flash("Failed to update daily goal!", "error")

    return redirect(url_for("dashboard"))


@app.route("/add-reminder", methods=["POST"])
def add_reminder_route():
    if not login_required():
        flash("Please login first!", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    title = request.form.get("reminder_title", "").strip()
    message = request.form.get("reminder_message", "").strip()
    subject = request.form.get("reminder_subject", "").strip()
    reminder_date = request.form.get("reminder_date", "").strip()
    reminder_time = request.form.get("reminder_time", "").strip()
    repeat_type = request.form.get("repeat_type", "once").strip().lower()

    if not title or not message or not reminder_date or not reminder_time:
        flash("Reminder title, message, date and time are required!", "error")
        return redirect(url_for("dashboard"))

    if repeat_type not in ["once", "daily", "weekly"]:
        repeat_type = "once"

    remind_at = f"{reminder_date} {reminder_time}:00"

    success = add_reminder(
        user_id=user_id,
        title=title,
        message=message,
        subject=subject if subject else None,
        remind_at=remind_at,
        repeat_type=repeat_type
    )

    if success:
        flash("Smart reminder created successfully!", "success")
    else:
        flash("Failed to create reminder!", "error")

    return redirect(url_for("dashboard"))


@app.route("/complete-reminder/<int:reminder_id>", methods=["POST"])
def complete_reminder(reminder_id):
    if not login_required():
        flash("Please login first!", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    success = mark_reminder_done(user_id, reminder_id)

    if success:
        flash("Reminder marked as done!", "success")
    else:
        flash("Failed to update reminder!", "error")

    return redirect(url_for("dashboard"))


@app.route("/delete-reminder/<int:reminder_id>", methods=["POST"])
def delete_reminder_route(reminder_id):
    if not login_required():
        flash("Please login first!", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    success = delete_reminder(user_id, reminder_id)

    if success:
        flash("Reminder deleted successfully!", "success")
    else:
        flash("Failed to delete reminder!", "error")

    return redirect(url_for("dashboard"))


@app.route("/snooze-reminder/<int:reminder_id>", methods=["POST"])
def snooze_reminder_route(reminder_id):
    if not login_required():
        flash("Please login first!", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    success = snooze_reminder(user_id, reminder_id, minutes=10)

    if success:
        flash("Reminder snoozed for 10 minutes!", "success")
    else:
        flash("Failed to snooze reminder!", "error")

    return redirect(url_for("dashboard"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not email:
            flash("Please enter your email!", "error")
            return redirect(url_for("forgot_password"))

        user = get_user_by_email(email)
        if not user:
            flash("Email not found!", "error")
            return redirect(url_for("forgot_password"))

        otp = str(random.randint(100000, 999999))

        session["reset_email"] = email
        session["reset_otp"] = otp

        if send_otp_email(email, otp):
            if not SENDER_EMAIL or not SENDER_PASSWORD:
                flash("OTP generated in terminal (demo mode). Check terminal.", "success")
            else:
                flash("OTP sent to your email!", "success")
            return redirect(url_for("verify_otp"))
        else:
            flash("Failed to send OTP. Check Gmail app password/settings.", "error")
            return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if "reset_email" not in session:
        flash("Please request OTP first!", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        entered_otp = request.form.get("otp", "").strip()
        saved_otp = session.get("reset_otp")

        if not entered_otp:
            flash("Please enter OTP!", "error")
            return redirect(url_for("verify_otp"))

        if entered_otp == saved_otp:
            session["otp_verified"] = True
            flash("OTP verified successfully!", "success")
            return redirect(url_for("reset_password"))
        else:
            flash("Invalid OTP!", "error")
            return redirect(url_for("verify_otp"))

    return render_template("verify_otp.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if "reset_email" not in session or not session.get("otp_verified"):
        flash("Please verify OTP first!", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("password", "").strip()
        email = session["reset_email"]

        if not new_password:
            flash("Please enter new password!", "error")
            return redirect(url_for("reset_password"))

        if len(new_password) < 6:
            flash("Password must be at least 6 characters!", "error")
            return redirect(url_for("reset_password"))

        success = update_password(email, new_password)

        if not success:
            flash("Failed to reset password!", "error")
            return redirect(url_for("reset_password"))

        user = get_user_by_email(email)

        session["user_id"] = user["id"]
        session["user_email"] = user["email"]

        session.pop("reset_email", None)
        session.pop("reset_otp", None)
        session.pop("otp_verified", None)

        flash("Password reset successful! You are now logged in.", "success")
        return redirect(url_for("dashboard"))

    return render_template("reset_password.html")


@app.route("/ai-assistant", methods=["POST"])
def ai_assistant():
    if not login_required():
        return jsonify({"error": "Please login first."}), 401

    try:
        data = request.get_json()
        question = data.get("question", "").strip() if data else ""

        if not question:
            return jsonify({"error": "Question is required."}), 400

        user_id = session["user_id"]
        reply = ask_sambanova_ai(user_id, question)

        return jsonify({"reply": reply})

    except Exception as e:
        print("AI Assistant Route Error:", e)
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# ============================================
# RUN APP
# ============================================
if __name__ == "__main__":
    init_db()
    app.run(debug=True)