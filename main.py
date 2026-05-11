#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import sqlite3
import json
import os
import shutil
import logging
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
logger.info("🚀 Запуск бота...")

import requests
import urllib.request
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand, FSInputFile, ReplyKeyboardRemove
)
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.client.default import DefaultBotProperties

BOT_TOKEN = "8712709852:AAHhze9Qnrg27pVb8wlJU8V1Dx-_h66xRDg"
ADMIN_IDS = [7437870400, 8693921243]
REQUIRED_CHANNEL = "SHINA_SELL"
SUPPORT_USERNAME = "@Shima_lil"

TIKTOK_REWARD = 20
REFERRAL_REWARD = 3
TOKEN_REWARD = 3
MAX_VIP_VIDEOS_PER_DAY = 5
DAILY_PREMIUM_BONUS = 5
START_DIAMONDS = 8

MEDIA_DIR = "media"
BACKUP_DIR = "backups"

ADMIN_PASSWORD = "WELLCOME"
CARD_NUMBER = "2200700538676841"
CARD_HOLDER = "Сергей"
CURRENCY_SYMBOL = "₽"

WELCOME_PHOTO_URL = "https://gspics.org/images/2026/05/05/IApR0n.png"
WELCOME_PHOTO_PATH = f"{MEDIA_DIR}/menu/welcome.jpg"

for folder in [
    f"{MEDIA_DIR}/menu",
    f"{MEDIA_DIR}/content/video",
    f"{MEDIA_DIR}/content/photo",
    f"{MEDIA_DIR}/content/video_vip",
    f"{MEDIA_DIR}/content/photo_vip",
    BACKUP_DIR
]:
    Path(folder).mkdir(parents=True, exist_ok=True)
    logger.debug(f"Папка готова: {folder}")

if not os.path.exists(WELCOME_PHOTO_PATH):
    try:
        logger.info("📥 Скачивание приветственного фото...")
        urllib.request.urlretrieve(WELCOME_PHOTO_URL, WELCOME_PHOTO_PATH)
        logger.info(f"✅ Приветственное фото сохранено: {WELCOME_PHOTO_PATH}")
    except Exception as e:
        logger.error(f"❌ Не удалось загрузить приветственное фото: {e}")
else:
    logger.info("✅ Приветственное фото уже существует")

logger.info("🤖 Инициализация бота...")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

subscription_cache = {}
user_languages = {}
_cached_bot_username = None

ANTI_BOT_EMOJIS = ["💎", "♥️", "🔞", "⭐", "📸", "🎥", "👑", "💰"]

DB_PATH = "westvideo.db"

def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    logger.info("📦 Инициализация базы данных...")
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        display_name TEXT,
        diamonds INTEGER DEFAULT 8,
        is_premium INTEGER DEFAULT 0,
        premium_until TIMESTAMP,
        last_bonus TIMESTAMP,
        is_banned INTEGER DEFAULT 0,
        ban_until TIMESTAMP,
        ban_reason TEXT,
        referrer_id INTEGER,
        total_referrals INTEGER DEFAULT 0,
        language TEXT DEFAULT 'ru',
        passed_antibot INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        file_path TEXT,
        is_vip INTEGER DEFAULT 0,
        file_hash TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS viewed_content (
        user_id INTEGER,
        content_id INTEGER,
        content_type TEXT,
        viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, content_id, content_type)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS pending_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        diamonds INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        photo_file_id TEXT,
        payment_type TEXT,
        extra_data TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS support_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_appeal INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes (
        code TEXT PRIMARY KEY,
        diamonds INTEGER,
        uses_left INTEGER,
        expires TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS promo_activations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        promo_code TEXT,
        activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS screenshot_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        screenshots TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_tasks (
        user_id INTEGER,
        task_type TEXT,
        completed_at TIMESTAMP,
        UNIQUE(user_id, task_type, completed_at)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS channel_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER UNIQUE,
        reward_given INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS localization (
        key TEXT PRIMARY KEY,
        ru TEXT,
        en TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS antibot_fails (
        user_id INTEGER PRIMARY KEY,
        fail_count INTEGER DEFAULT 0,
        last_fail TIMESTAMP,
        banned_until TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        admin_username TEXT,
        action TEXT,
        target_user_id INTEGER,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_payment_id (
        user_id INTEGER PRIMARY KEY,
        payment_id TEXT UNIQUE
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS used_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE,
        user_id INTEGER,
        bot_username TEXT,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS token_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    defaults = [
        ('price_10', '50'), ('price_20', '90'), ('price_30', '130'), ('price_40', '170'),
        ('price_50', '200'), ('price_100', '350'), ('premium_price', '499'),
        ('private_channel_price', '299'), ('private_channel_link', ''),
        ('admin_password', ADMIN_PASSWORD), ('card_number', CARD_NUMBER),
        ('card_holder', CARD_HOLDER), ('subscription_check_enabled', '1'),
        ('subscription_channel', REQUIRED_CHANNEL), ('referral_reward', str(REFERRAL_REWARD)),
        ('photo_welcome', WELCOME_PHOTO_PATH), ('video_welcome', ''), 
        ('photo_buy', ''), ('video_buy', ''),
        ('photo_vip', ''), ('video_vip', ''), ('photo_profile', ''), ('video_profile', ''),
        ('photo_support', ''), ('video_support', '')
    ]
    for k, v in defaults:
        c.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (k, v))
    
    loc_defaults = [
        ('main_menu', '🏠 ГЛАВНОЕ МЕНЮ', '🏠 MAIN MENU'),
        ('watch_photo', '📸 Смотреть фото', '📸 Watch photo'),
        ('watch_video', '🎥 Смотреть видео', '🎥 Watch video'),
        ('vip_content', '👑 VIP контент', '👑 VIP content'),
        ('profile', '👤 Профиль', '👤 Profile'),
        ('buy_diamonds', '💎 Купить алмазы', '💎 Buy diamonds'),
        ('premium', '⭐ Premium подписка', '⭐ Premium'),
        ('private_channel', '🔒 Приватный канал', '🔒 Private channel'),
        ('promo', '🎁 Промокод', '🎁 Promo code'),
        ('earn', '💰 Заработать', '💰 Earn'),
        ('support', '❓ Поддержка', '❓ Support'),
        ('change_lang', '🌐 Сменить язык', '🌐 Change language'),
        ('tiktok', '🎬 TikTok задание', '🎬 TikTok task')
    ]
    for k, ru, en in loc_defaults:
        c.execute("INSERT OR IGNORE INTO localization VALUES (?, ?, ?)", (k, ru, en))
    
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

init_db()

def is_token_valid(token: str) -> bool:
    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("ok", False)
        return False
    except:
        return False

def get_bot_username_from_token(token: str) -> str:
    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                username = data.get("result", {}).get("username")
                return f"@{username}" if username else "❌ НЕТ USERNAME"
    except:
        pass
    return "❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ"

def is_token_used(token: str) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM used_tokens WHERE token = ?", (token,))
    result = c.fetchone() is not None
    conn.close()
    return result

def save_used_token(token: str, user_id: int, bot_username: str = None):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO used_tokens (token, user_id, bot_username) VALUES (?, ?, ?)", 
              (token, user_id, bot_username))
    conn.commit()
    conn.close()

def get_referral_count(user_id: int) -> int:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_referral_earned(user_id: int) -> int:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) * ? FROM referrals WHERE referrer_id = ?", (REFERRAL_REWARD, user_id))
    earned = c.fetchone()[0]
    conn.close()
    return earned

def can_do_token_task(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT created_at FROM token_tasks WHERE user_id = ? AND date(created_at) = date('now')", (user_id,))
    r = c.fetchone()
    conn.close()
    return r is None

def save_token_task(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO token_tasks (user_id, status) VALUES (?, 'completed')", (user_id,))
    conn.commit()
    conn.close()

def get_all_used_tokens():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT t.token, t.bot_username, t.user_id, t.used_at, u.username, u.display_name
        FROM used_tokens t
        LEFT JOIN users u ON t.user_id = u.user_id
        ORDER BY t.used_at DESC
    """)
    rows = c.fetchall()
    conn.close()
    return rows

async def get_bot_username():
    global _cached_bot_username
    if _cached_bot_username is None:
        me = await bot.get_me()
        _cached_bot_username = me.username
    return _cached_bot_username

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def get_setting(key: str, as_int: bool = False):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    r = c.fetchone()
    conn.close()
    if not r:
        return None
    return int(r[0]) if as_int else r[0]

def set_setting(key: str, value: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_diamonds(user_id: int) -> int:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT diamonds FROM users WHERE user_id = ?", (user_id,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else 0

def update_diamonds(user_id: int, amount: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    c.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def is_premium(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_premium, premium_until FROM users WHERE user_id = ?", (user_id,))
    r = c.fetchone()
    conn.close()
    if r and r[0] == 1:
        if r[1] and datetime.fromisoformat(r[1]) < datetime.now():
            return False
        return True
    return False

def set_premium(user_id: int, days: int):
    if days == 0:
        until = None
    else:
        until = (datetime.now() + timedelta(days=days)).isoformat()
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?", (until, user_id))
    conn.commit()
    conn.close()

def remove_premium(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_premium = 0, premium_until = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_banned(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_banned, ban_until FROM users WHERE user_id = ?", (user_id,))
    r = c.fetchone()
    conn.close()
    if r and r[0] == 1:
        if r[1] and datetime.fromisoformat(r[1]) > datetime.now():
            return True
    return False

def ban_user(user_id: int, days: int, reason: str):
    until = None if days == 0 else (datetime.now() + timedelta(days=days)).isoformat()
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = 1, ban_until = ?, ban_reason = ? WHERE user_id = ?", (until, reason, user_id))
    conn.commit()
    conn.close()

def unban_user(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = 0, ban_until = NULL, ban_reason = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def can_get_daily_bonus(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
    r = c.fetchone()
    conn.close()
    if not r or not r[0]:
        return True
    return datetime.now() - datetime.fromisoformat(r[0]) > timedelta(days=1)

def set_daily_bonus(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def get_vip_watch_count(user_id: int) -> int:
    today = datetime.now().date().isoformat()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM viewed_content WHERE user_id = ? AND content_type = 'video' AND date(viewed_at) = ?", (user_id, today))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_unwatched_vip_content(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT id, file_path FROM content 
                 WHERE type = 'video' AND is_vip = 1 
                 AND id NOT IN (SELECT content_id FROM viewed_content WHERE user_id = ? AND content_type = 'video')
                 ORDER BY RANDOM() LIMIT 1""", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def mark_content_viewed(user_id: int, content_id: int, content_type: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO viewed_content (user_id, content_id, content_type) VALUES (?, ?, ?)", 
              (user_id, content_id, content_type))
    conn.commit()
    conn.close()

def get_random_unwatched_content(user_id: int, content_type: str, is_vip: bool = False):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT id, file_path FROM content 
                 WHERE type = ? AND is_vip = ? 
                 AND id NOT IN (SELECT content_id FROM viewed_content WHERE user_id = ? AND content_type = ?)
                 ORDER BY RANDOM() LIMIT 1""",
              (content_type, 1 if is_vip else 0, user_id, content_type))
    rows = c.fetchall()
    conn.close()
    return rows

def add_pending_payment(user_id: int, diamonds: int, photo_id: str, payment_type: str, extra_data: dict = None):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO pending_payments 
                 (user_id, diamonds, photo_file_id, payment_type, extra_data) 
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, diamonds, photo_id, payment_type, json.dumps(extra_data) if extra_data else None))
    conn.commit()
    conn.close()

def get_pending_payments():
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT id, user_id, diamonds, photo_file_id, payment_type, extra_data, created_at 
                 FROM pending_payments WHERE status = 'pending' ORDER BY id DESC''')
    rows = c.fetchall()
    conn.close()
    return rows

def get_payment_info(payment_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, diamonds, payment_type, extra_data FROM pending_payments WHERE id = ?", (payment_id,))
    r = c.fetchone()
    conn.close()
    return r

def approve_payment(payment_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE pending_payments SET status = 'approved' WHERE id = ?", (payment_id,))
    conn.commit()
    conn.close()

def reject_payment(payment_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE pending_payments SET status = 'rejected' WHERE id = ?", (payment_id,))
    conn.commit()
    conn.close()

def add_support_message(user_id: int, message: str, is_appeal: bool = False):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO support_messages (user_id, message, is_appeal) VALUES (?, ?, ?)",
              (user_id, message, 1 if is_appeal else 0))
    conn.commit()
    conn.close()

def get_unread_support_messages():
    conn = get_db()
    c = conn.cursor()
    rows = c.execute("SELECT id, user_id, message, created_at, is_appeal FROM support_messages WHERE is_read = 0 ORDER BY id DESC").fetchall()
    conn.close()
    return rows

def mark_support_read(msg_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE support_messages SET is_read = 1 WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()

def has_pending_tiktok(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM screenshot_tasks WHERE user_id = ? AND status = 'pending'", (user_id,))
    r = c.fetchone()
    conn.close()
    return r is not None

def can_do_tiktok(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT completed_at FROM user_tasks WHERE user_id = ? AND task_type = 'tiktok' AND date(completed_at) = date('now')", (user_id,))
    r = c.fetchone()
    conn.close()
    return r is None

def save_tiktok_task(user_id: int, screenshots: list):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO screenshot_tasks (user_id, screenshots) VALUES (?, ?)",
              (user_id, json.dumps(screenshots)))
    conn.commit()
    conn.close()

def get_pending_tiktok():
    conn = get_db()
    c = conn.cursor()
    rows = c.execute("SELECT id, user_id, screenshots, created_at FROM screenshot_tasks WHERE status = 'pending'").fetchall()
    conn.close()
    return rows

def approve_tiktok(task_id: int, user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE screenshot_tasks SET status = 'approved' WHERE id = ?", (task_id,))
    c.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id = ?", (TIKTOK_REWARD, user_id))
    c.execute("INSERT INTO user_tasks (user_id, task_type, completed_at) VALUES (?, 'tiktok', ?)",
              (user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def reject_tiktok(task_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE screenshot_tasks SET status = 'rejected' WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

def add_promo(code: str, diamonds: int, uses: int, expires: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO promo_codes (code, diamonds, uses_left, expires) VALUES (?, ?, ?, ?)",
              (code, diamonds, uses, expires))
    conn.commit()
    conn.close()

def get_promo(code: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT diamonds, uses_left, expires FROM promo_codes WHERE code = ?", (code,))
    r = c.fetchone()
    conn.close()
    return r

def use_promo(code: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()

def has_activated_promo(user_id: int, code: str) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM promo_activations WHERE user_id = ? AND promo_code = ?", (user_id, code))
    r = c.fetchone()[0]
    conn.close()
    return r > 0

def add_promo_activation(user_id: int, code: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO promo_activations (user_id, promo_code) VALUES (?, ?)", (user_id, code))
    conn.commit()
    conn.close()

def add_channel_request(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO channel_requests (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_channel_requests():
    conn = get_db()
    c = conn.cursor()
    rows = c.execute("SELECT id, user_id, created_at FROM channel_requests WHERE status = 'pending'").fetchall()
    conn.close()
    return rows

def approve_channel_request(request_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE channel_requests SET status = 'approved' WHERE id = ?", (request_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_db()
    c = conn.cursor()
    rows = c.execute("SELECT user_id, username, display_name, diamonds, is_banned FROM users").fetchall()
    conn.close()
    return rows

def get_user_by_id(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username, display_name, diamonds, is_banned, is_premium FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def search_users(query: str):
    conn = get_db()
    c = conn.cursor()
    if query.isdigit():
        c.execute("SELECT user_id, username, display_name, diamonds, is_banned, is_premium FROM users WHERE user_id = ?", (int(query),))
    else:
        c.execute("SELECT user_id, username, display_name, diamonds, is_banned, is_premium FROM users WHERE username LIKE ? OR display_name LIKE ?",
                  (f"%{query.lstrip('@')}%", f"%{query.lstrip('@')}%"))
    rows = c.fetchmany(5)
    conn.close()
    return rows

def get_user_payment_id(user_id: int) -> str:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT payment_id FROM user_payment_id WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    payment_id = f"Shima_{user_id}"
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO user_payment_id (user_id, payment_id) VALUES (?, ?)", (user_id, payment_id))
    conn.commit()
    conn.close()
    return payment_id

def get_user_lang(user_id: int) -> str:
    if user_id in user_languages:
        return user_languages[user_id]
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    r = c.fetchone()
    conn.close()
    lang = r[0] if r else 'ru'
    user_languages[user_id] = lang
    return lang

def set_user_lang(user_id: int, lang: str):
    user_languages[user_id] = lang
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()

def loc(key: str, user_id: int) -> str:
    lang = get_user_lang(user_id)
    conn = get_db()
    c = conn.cursor()
    c.execute(f"SELECT {lang} FROM localization WHERE key = ?", (key,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else key

def has_passed_antibot(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT passed_antibot FROM users WHERE user_id = ?", (user_id,))
    r = c.fetchone()
    conn.close()
    return r and r[0] == 1

def set_passed_antibot(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET passed_antibot = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_antibot_banned(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT banned_until FROM antibot_fails WHERE user_id = ?", (user_id,))
    r = c.fetchone()
    conn.close()
    return r and r[0] and datetime.fromisoformat(r[0]) > datetime.now()

def increment_antibot_fail(user_id: int) -> int:
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO antibot_fails (user_id, fail_count, last_fail) VALUES (?, 1, ?) "
              "ON CONFLICT(user_id) DO UPDATE SET fail_count = fail_count + 1, last_fail = ?",
              (user_id, datetime.now().isoformat(), datetime.now().isoformat()))
    c.execute("SELECT fail_count FROM antibot_fails WHERE user_id = ?", (user_id,))
    fails = c.fetchone()[0]
    if fails >= 3:
        ban_until = (datetime.now() + timedelta(hours=1)).isoformat()
        c.execute("UPDATE antibot_fails SET banned_until = ? WHERE user_id = ?", (ban_until, user_id))
    conn.commit()
    conn.close()
    return fails

def reset_antibot_fails(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM antibot_fails WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def log_admin_action(admin_id: int, admin_username: str, action: str, target_user_id: int = None, details: str = None):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO admin_logs (admin_id, admin_username, action, target_user_id, details)
                 VALUES (?, ?, ?, ?, ?)''',
              (admin_id, admin_username, action, target_user_id, details))
    conn.commit()
    conn.close()

async def download_media(file_id: str, file_type: str, is_vip: bool = False, menu_key: str = None) -> str:
    file_info = await bot.get_file(file_id)
    ext = 'mp4' if file_type == 'video' else 'jpg'
    
    if menu_key:
        folder = f'{MEDIA_DIR}/menu'
        fname = f'{folder}/{menu_key}.{ext}'
    else:
        # ИСПРАВЛЕНО: правильное определение папки для VIP контента
        if file_type == 'video':
            sub = 'video_vip' if is_vip else 'video'
        else:
            sub = 'photo_vip' if is_vip else 'photo'
        folder = f'{MEDIA_DIR}/content/{sub}'
        fname = f'{folder}/{datetime.now().strftime("%Y%m%d_%H%M%S")}.{ext}'
    
    Path(folder).mkdir(parents=True, exist_ok=True)
    await bot.download_file(file_info.file_path, fname)
    return fname

def add_content_to_db(content_type: str, file_path: str, is_vip: int = 0):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO content (type, file_path, is_vip) VALUES (?, ?, ?)",
              (content_type, file_path, is_vip))
    conn.commit()
    conn.close()

def is_sub_check_enabled() -> bool:
    return get_setting('subscription_check_enabled', as_int=True) == 1

def get_sub_channel() -> str:
    return get_setting('subscription_channel') or REQUIRED_CHANNEL

async def is_subscribed(user_id: int, channel: str) -> bool:
    try:
        member = await bot.get_chat_member(f"@{channel}", user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

async def check_sub(message: types.Message) -> bool:
    if not is_sub_check_enabled():
        return True
    
    user_id = message.from_user.id
    if user_id in subscription_cache and subscription_cache[user_id]:
        return True
    
    if await is_subscribed(user_id, get_sub_channel()):
        subscription_cache[user_id] = True
        return True
    
    channel = get_sub_channel()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 ПОДПИСАТЬСЯ", url=f"https://t.me/{channel}")],
        [InlineKeyboardButton(text="✅ ПРОВЕРИТЬ", callback_data="check_sub")]
    ])
    await message.answer(f"🔒 ПОДПИШИТЕСЬ: @{channel}", reply_markup=kb)
    return False

@dp.callback_query(F.data == "check_sub")
async def sub_callback(callback: types.CallbackQuery):
    if await is_subscribed(callback.from_user.id, get_sub_channel()):
        subscription_cache[callback.from_user.id] = True
        await callback.answer("✅ Подписка подтверждена!")
        await callback.message.delete()
        await send_main(callback.message)
    else:
        await callback.answer("❌ Не подписаны!", show_alert=True)

def get_main_kb(user_id: int):
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text=loc('watch_photo', user_id)), KeyboardButton(text=loc('watch_video', user_id)))
    builder.row(KeyboardButton(text=loc('vip_content', user_id)), KeyboardButton(text=loc('premium', user_id)))
    builder.row(KeyboardButton(text=loc('buy_diamonds', user_id)), KeyboardButton(text=loc('promo', user_id)))
    builder.row(KeyboardButton(text=loc('private_channel', user_id)), KeyboardButton(text=loc('support', user_id)))
    builder.row(KeyboardButton(text=loc('profile', user_id)), KeyboardButton(text=loc('earn', user_id)))
    builder.row(KeyboardButton(text=loc('change_lang', user_id)),)  # TikTok кнопка удалена отсюда
    builder.row(KeyboardButton(text="👑 Админ панель"), KeyboardButton(text="🏠 Главное меню"))
    builder.row(KeyboardButton(text="🔄 Обновить"), KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)

def get_admin_kb():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="➕ Добавить видео"), KeyboardButton(text="➕ Добавить VIP видео"))
    builder.row(KeyboardButton(text="➕ Добавить фото"), KeyboardButton(text="➕ Добавить VIP фото"))
    builder.row(KeyboardButton(text="💰 Изменить цены"), KeyboardButton(text="💳 Реквизиты"))
    builder.row(KeyboardButton(text="💰 Запросы на оплату"), KeyboardButton(text="💎 Выдать алмазы"))
    builder.row(KeyboardButton(text="⭐ Выдать Premium"), KeyboardButton(text="🔒 Приватный канал (админ)"))
    builder.row(KeyboardButton(text="🖼️ Сменить медиа"), KeyboardButton(text="📨 Рассылка"))
    builder.row(KeyboardButton(text="👥 Все пользователи"), KeyboardButton(text="🔍 Поиск пользователя"))
    builder.row(KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🎁 Промокоды (админ)"))
    builder.row(KeyboardButton(text="📩 Сообщения"), KeyboardButton(text="📸 Проверить задания"))
    builder.row(KeyboardButton(text="🔘 Проверка подписки"), KeyboardButton(text="💾 Бэкап"))
    builder.row(KeyboardButton(text="🚫 Бан/Разбан"), KeyboardButton(text="🔑 Токены"))
    builder.row(KeyboardButton(text="🏠 Главное меню"), KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)

def get_cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

def get_antibot_kb(correct_emoji: str):
    builder = ReplyKeyboardBuilder()
    emojis = random.sample(ANTI_BOT_EMOJIS, 4)
    if correct_emoji not in emojis:
        emojis[random.randint(0, 3)] = correct_emoji
    random.shuffle(emojis)
    for e in emojis:
        builder.add(KeyboardButton(text=e))
    builder.row(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True), correct_emoji

def get_earn_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 ЗАДАНИЕ TIKTOK", callback_data="earn_tiktok")],
        [InlineKeyboardButton(text="👥 РЕФЕРАЛЫ (+3💎)", callback_data="earn_referrals")],
        [InlineKeyboardButton(text="🤖 ТОКЕН BOTFATHER (+3💎)", callback_data="earn_token")],
        [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_main")]
    ])

class AntiBot(StatesGroup): waiting = State()
class AddContent(StatesGroup): waiting = State()
class AdminAuth(StatesGroup): waiting = State()
class GiveDiamonds(StatesGroup): waiting_id = State(); waiting_amount = State()
class GivePremium(StatesGroup): waiting_id = State(); waiting_days = State()
class Broadcast(StatesGroup): waiting = State(); confirm = State()
class CreatePromo(StatesGroup): code = State(); diamonds = State(); uses = State(); days = State()
class ActivatePromo(StatesGroup): waiting = State()
class SupportMsg(StatesGroup): waiting = State()
class TikTokTask(StatesGroup): waiting = State()
class TokenTask(StatesGroup): waiting = State()
class SearchUser(StatesGroup): waiting = State()
class PaymentPhoto(StatesGroup): waiting = State()
class ChangePrice(StatesGroup): ptype = State(); val = State()
class ChangeCard(StatesGroup): num = State(); holder = State()
class ChangeMedia(StatesGroup): waiting = State()
class PrivateChannelPrice(StatesGroup): waiting = State()
class PrivateChannelLink(StatesGroup): waiting = State()
class BanUserState(StatesGroup): waiting_id = State(); waiting_days = State(); waiting_reason = State()
class AdminReply(StatesGroup): waiting_reply = State()

async def send_main(message: types.Message):
    user_id = message.from_user.id
    if is_banned(user_id):
        await message.answer("❌ ВЫ ЗАБАНЕНЫ!")
        return
    
    channel = get_sub_channel()
    text = (f"🏠 ГЛАВНОЕ МЕНЮ\n\n"
            f"💎 АЛМАЗЫ: {get_diamonds(user_id)}\n"
            f"⭐ PREMIUM: {'✅ ДА' if is_premium(user_id) else '❌ НЕТ'}\n\n"
            f"📢 НАШ КАНАЛ: @{channel}")
    
    if os.path.exists(WELCOME_PHOTO_PATH):
        await message.answer_photo(FSInputFile(WELCOME_PHOTO_PATH), caption=text, reply_markup=get_main_kb(user_id))
    else:
        await message.answer(text, reply_markup=get_main_kb(user_id))

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    args = message.text.split()
    if len(args) > 1 and args[1].startswith('ref_'):
        try:
            ref = int(args[1].replace('ref_', ''))
            if ref != user_id:
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
                if not c.fetchone():
                    c.execute("UPDATE users SET referrer_id = ? WHERE user_id = ?", (ref, user_id))
                    c.execute("INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?, ?)", (ref, user_id))
                    update_diamonds(ref, REFERRAL_REWARD)
                    c.execute("UPDATE users SET total_referrals = total_referrals + 1 WHERE user_id = ?", (ref,))
                    await bot.send_message(ref, f"🎉 +{REFERRAL_REWARD}💎 ЗА РЕФЕРАЛА!")
                conn.commit()
                conn.close()
        except:
            pass
    
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, display_name, diamonds) VALUES (?, ?, ?, ?)",
              (user_id, message.from_user.username or 'нет', message.from_user.first_name, START_DIAMONDS))
    conn.commit()
    conn.close()
    
    if is_banned(user_id):
        await message.answer("❌ ВЫ ЗАБАНЕНЫ!")
        return
    if is_antibot_banned(user_id):
        await message.answer("🚫 ВЫ ЗАБЛОКИРОВАНЫ НА 1 ЧАС ЗА ПОДОЗРИТЕЛЬНУЮ АКТИВНОСТЬ!")
        return
    if not has_passed_antibot(user_id):
        kb, correct = get_antibot_kb(random.choice(ANTI_BOT_EMOJIS))
        await state.update_data(target=correct)
        await state.set_state(AntiBot.waiting)
        await message.answer(f"🤖 ПРОВЕРКА НА БОТА\n\nНажми на кнопку: {correct}", reply_markup=kb)
        return
    if not await check_sub(message):
        return
    
    channel = get_sub_channel()
    
    msg = await message.answer(
        f"⚠️ ВАЖНО!\n\n"
        f"ПОСЛЕ БЛОКИРОВКИ БОТА ВЫ СМОЖЕТЕ НАЙТИ ЕГО ЗДЕСЬ:\n\n"
        f"📢 @{channel}\n"
        f"👨‍💻 {SUPPORT_USERNAME}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 ПЕРЕЙТИ В КАНАЛ", url=f"https://t.me/{channel}")],
            [InlineKeyboardButton(text="👨‍💻 СВЯЗАТЬСЯ С АДМИНОМ", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}")]
        ])
    )
    
    try:
        await msg.pin()
    except Exception as e:
        logger.error(f"Не удалось закрепить сообщение: {e}")
    
    await send_main(message)

@dp.message(AntiBot.waiting)
async def antibot_check(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    target = data.get('target')
    
    if message.text == "❌ Отмена":
        await state.clear()
        await send_main(message)
        return
    
    if message.text == target:
        set_passed_antibot(user_id)
        reset_antibot_fails(user_id)
        await state.clear()
        await message.answer("✅ Проверка пройдена!")
        if not await check_sub(message):
            return
        
        channel = get_sub_channel()
        
        msg = await message.answer(
            f"⚠️ ВАЖНО!\n\n"
            f"ПОСЛЕ БЛОКИРОВКИ БОТА ВЫ СМОЖЕТЕ НАЙТИ ЕГО ЗДЕСЬ:\n\n"
            f"📢 @{channel}\n"
            f"👨‍💻 {SUPPORT_USERNAME}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 ПЕРЕЙТИ В КАНАЛ", url=f"https://t.me/{channel}")],
                [InlineKeyboardButton(text="👨‍💻 СВЯЗАТЬСЯ С АДМИНОМ", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}")]
            ])
        )
        
        try:
            await msg.pin()
        except Exception as e:
            logger.error(f"Не удалось закрепить сообщение: {e}")
        
        await send_main(message)
    else:
        fails = increment_antibot_fail(user_id)
        remaining = 3 - fails
        if fails >= 3:
            await state.clear()
            await message.answer("🚫 ВЫ ЗАБЛОКИРОВАНЫ НА 1 ЧАС!", reply_markup=ReplyKeyboardRemove())
        else:
            kb, new_target = get_antibot_kb(random.choice(ANTI_BOT_EMOJIS))
            await state.update_data(target=new_target)
            await message.answer(f"❌ НЕВЕРНО! Осталось попыток: {remaining}\n\nНажми на кнопку: {new_target}", reply_markup=kb)

@dp.message(F.text.in_(["🏠 Главное меню", "❌ Отмена"]))
async def main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    if is_banned(message.from_user.id):
        await message.answer("❌ ВЫ ЗАБАНЕНЫ!")
        return
    if not await check_sub(message):
        return
    await send_main(message)

@dp.message(F.text == "🔄 Обновить")
async def refresh(message: types.Message):
    if is_banned(message.from_user.id):
        await message.answer("❌ ВЫ ЗАБАНЕНЫ!")
        return
    subscription_cache.pop(message.from_user.id, None)
    if not await check_sub(message):
        return
    await send_main(message)

@dp.message(F.text.in_(["📸 Смотреть фото", "📸 Watch photo"]))
async def watch_photo(message: types.Message):
    if is_banned(message.from_user.id):
        return
    if not await check_sub(message):
        return
    user_id = message.from_user.id
    if get_diamonds(user_id) < 1:
        return await message.answer("❌ Нужно 1💎")
    
    content = get_random_unwatched_content(user_id, 'photo', is_vip=False)
    if not content:
        await message.answer("❌ Нет новых фото. Возвращайтесь позже!")
        return
    
    content_id, path = content[0]
    if not os.path.exists(path):
        return await message.answer("❌ Файл не найден")
    update_diamonds(user_id, -1)
    mark_content_viewed(user_id, content_id, 'photo')
    await message.answer_photo(FSInputFile(path), caption=f"🖼️ -1💎 | 💎 {get_diamonds(user_id)}")

@dp.message(F.text.in_(["🎥 Смотреть видео", "🎥 Watch video"]))
async def watch_video(message: types.Message):
    if is_banned(message.from_user.id):
        return
    if not await check_sub(message):
        return
    user_id = message.from_user.id
    if get_diamonds(user_id) < 2:
        return await message.answer("❌ Нужно 2💎")
    
    content = get_random_unwatched_content(user_id, 'video', is_vip=False)
    if not content:
        await message.answer("❌ Нет новых видео. Возвращайтесь позже!")
        return
    
    content_id, path = content[0]
    if not os.path.exists(path):
        return await message.answer("❌ Файл не найден")
    update_diamonds(user_id, -2)
    mark_content_viewed(user_id, content_id, 'video')
    await message.answer_video(FSInputFile(path), caption=f"🎬 -2💎 | 💎 {get_diamonds(user_id)}")

@dp.message(F.text.in_(["👑 VIP контент", "👑 VIP content"]))
async def vip_content(message: types.Message):
    if is_banned(message.from_user.id):
        return
    if not await check_sub(message):
        return
    user_id = message.from_user.id
    if not is_premium(user_id):
        return await message.answer("❌ Только для Premium пользователей!")
    
    vip_media = get_setting('photo_vip') or get_setting('video_vip')
    if vip_media and os.path.exists(vip_media):
        if vip_media.endswith('.mp4'):
            await message.answer_video(FSInputFile(vip_media))
        else:
            await message.answer_photo(FSInputFile(vip_media))
    
    if can_get_daily_bonus(user_id):
        update_diamonds(user_id, DAILY_PREMIUM_BONUS)
        set_daily_bonus(user_id)
        await message.answer(f"🎁 ЕЖЕДНЕВНЫЙ VIP БОНУС: +{DAILY_PREMIUM_BONUS}💎 | 💎 {get_diamonds(user_id)}")
    
    watched_today = get_vip_watch_count(user_id)
    if watched_today >= MAX_VIP_VIDEOS_PER_DAY:
        return await message.answer(f"❌ Вы уже посмотрели {MAX_VIP_VIDEOS_PER_DAY} VIP видео сегодня! Лимит на сегодня исчерпан.")
    
    videos = get_unwatched_vip_content(user_id)
    if not videos:
        await message.answer("❌ Нет новых VIP видео. Возвращайтесь позже!")
        return
    
    vid, path = videos[0]
    if not os.path.exists(path):
        return await message.answer("❌ Файл не найден")
    mark_content_viewed(user_id, vid, 'video')
    await message.answer_video(FSInputFile(path), caption=f"👑 VIP ВИДЕО ({watched_today + 1}/{MAX_VIP_VIDEOS_PER_DAY})")

@dp.message(F.text.in_(["👤 Профиль", "👤 Profile"]))
async def profile(message: types.Message):
    if is_banned(message.from_user.id):
        return
    if not await check_sub(message):
        return
    user_id = message.from_user.id
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT total_referrals FROM users WHERE user_id = ?", (user_id,))
    refs = c.fetchone()
    conn.close()
    
    payment_id = get_user_payment_id(user_id)
    
    text = (f"👤 ПРОФИЛЬ\n\n"
            f"🆔 ID: {user_id}\n"
            f"💎 АЛМАЗЫ: {get_diamonds(user_id)}\n"
            f"⭐ PREMIUM: {'✅ ДА' if is_premium(user_id) else '❌ НЕТ'}\n"
            f"👥 РЕФЕРАЛОВ: {refs[0] if refs else 0}\n"
            f"🆔 ID ДЛЯ ОПЛАТЫ: <code>{payment_id}</code>\n\n"
            f"📢 НАШ КАНАЛ: @{get_sub_channel()}")
    
    profile_media = get_setting('photo_profile') or get_setting('video_profile')
    if profile_media and os.path.exists(profile_media):
        if profile_media.endswith('.mp4'):
            await message.answer_video(FSInputFile(profile_media), caption=text)
        else:
            await message.answer_photo(FSInputFile(profile_media), caption=text)
    else:
        await message.answer(text)

@dp.message(F.text.in_(["💎 Купить алмазы", "💎 Buy diamonds"]))
async def buy_diamonds(message: types.Message):
    if is_banned(message.from_user.id):
        return
    if not await check_sub(message):
        return
    
    buttons = [
        [InlineKeyboardButton(text=f"10💎 - {get_setting('price_10')}{CURRENCY_SYMBOL}", callback_data="diam_10")],
        [InlineKeyboardButton(text=f"20💎 - {get_setting('price_20')}{CURRENCY_SYMBOL}", callback_data="diam_20")],
        [InlineKeyboardButton(text=f"30💎 - {get_setting('price_30')}{CURRENCY_SYMBOL}", callback_data="diam_30")],
        [InlineKeyboardButton(text=f"40💎 - {get_setting('price_40')}{CURRENCY_SYMBOL}", callback_data="diam_40")],
        [InlineKeyboardButton(text=f"50💎 - {get_setting('price_50')}{CURRENCY_SYMBOL}", callback_data="diam_50")],
        [InlineKeyboardButton(text=f"100💎 - {get_setting('price_100')}{CURRENCY_SYMBOL}", callback_data="diam_100")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    buy_media = get_setting('photo_buy') or get_setting('video_buy')
    if buy_media and os.path.exists(buy_media):
        if buy_media.endswith('.mp4'):
            await message.answer_video(FSInputFile(buy_media), caption="💰 ВЫБЕРИТЕ КОЛИЧЕСТВО АЛМАЗОВ:", reply_markup=kb)
        else:
            await message.answer_photo(FSInputFile(buy_media), caption="💰 ВЫБЕРИТЕ КОЛИЧЕСТВО АЛМАЗОВ:", reply_markup=kb)
    else:
        await message.answer("💰 ВЫБЕРИТЕ КОЛИЧЕСТВО АЛМАЗОВ:", reply_markup=kb)

@dp.callback_query(F.data.startswith("diam_"))
async def diam_selected(callback: types.CallbackQuery, state: FSMContext):
    diam = int(callback.data.split("_")[1])
    await state.update_data(diam=diam, payment_type='diamonds')
    price = get_setting(f'price_{diam}')
    payment_id = get_user_payment_id(callback.from_user.id)
    
    text = (f"🔞 ВНИМАНИЕ! ТОВАР 18+ 🔞\n\n"
            f"💎 АЛМАЗЫ: {diam} шт\n"
            f"💰 ЦЕНА: {price} {CURRENCY_SYMBOL}\n\n"
            f"💳 РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ:\n"
            f"{CARD_NUMBER} | {CARD_HOLDER}\n\n"
            f"🆕 ВАШ ID ДЛЯ ОПЛАТЫ (ОБЯЗАТЕЛЬНО В КОММЕНТАРИИ):\n"
            f"<code>{payment_id}</code>\n\n"
            f"📌 ПОСЛЕ ОПЛАТЫ НАЖМИТЕ «✅ Я ОПЛАТИЛ» И ОТПРАВЬТЕ ЧЕК")
    buttons = [
        [InlineKeyboardButton(text="✅ Я ОПЛАТИЛ", callback_data="paid")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_payment")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.answer()
    await callback.message.answer(text, reply_markup=kb)

@dp.message(F.text.in_(["⭐ Premium подписка", "⭐ Premium"]))
async def premium_info(message: types.Message):
    if is_banned(message.from_user.id):
        return
    if not await check_sub(message):
        return
    price = get_setting('premium_price', as_int=True) or 499
    payment_id = get_user_payment_id(message.from_user.id)
    
    text = (f"🔞 ВНИМАНИЕ! ПОДПИСКА 18+ 🔞\n\n"
            f"⭐ VIP ПОДПИСКА (30 ДНЕЙ)\n\n"
            f"▫️ ДОСТУП К VIP-КОНТЕНТУ В БОТЕ\n"
            f"▫️ {MAX_VIP_VIDEOS_PER_DAY} VIP ВИДЕО КАЖДЫЙ ДЕНЬ\n"
            f"▫️ ЕЖЕДНЕВНЫЙ БОНУС {DAILY_PREMIUM_BONUS}💎\n"
            f"▫️ ПРИОРИТЕТНАЯ ПОДДЕРЖКА\n\n"
            f"💰 ЦЕНА: {price} {CURRENCY_SYMBOL}\n\n"
            f"💳 РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ:\n"
            f"{CARD_NUMBER} | {CARD_HOLDER}\n\n"
            f"🆕 ВАШ ID ДЛЯ ОПЛАТЫ (ОБЯЗАТЕЛЬНО В КОММЕНТАРИИ):\n"
            f"<code>{payment_id}</code>\n\n"
            f"📌 ПОСЛЕ ОПЛАТЫ НАЖМИТЕ «✅ Я ОПЛАТИЛ» И ОТПРАВЬТЕ ЧЕК")
    buttons = [
        [InlineKeyboardButton(text="✅ Я ОПЛАТИЛ", callback_data="paid_premium")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_payment")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=kb)

@dp.message(F.text.in_(["🔒 Приватный канал", "🔒 Private channel"]))
async def private_channel(message: types.Message):
    if is_banned(message.from_user.id):
        return
    if not await check_sub(message):
        return
    price = get_setting('private_channel_price', as_int=True) or 299
    payment_id = get_user_payment_id(message.from_user.id)
    
    text = (f"🔞 ВНИМАНИЕ! КОНТЕНТ 18+ 🔞\n\n"
            f"🔒 ПРИВАТНЫЙ КАНАЛ (30 ДНЕЙ)\n\n"
            f"▫️ 30+ ЭКСКЛЮЗИВНЫХ ВИДЕО КАЖДЫЙ ДЕНЬ\n"
            f"▫️ ДОСТУП В ЗАКРЫТЫЙ TELEGRAM КАНАЛ\n"
            f"▫️ НОВИНКИ СРАЗУ ПОСЛЕ ВЫХОДА\n"
            f"▫️ БЕЗ РЕКЛАМЫ\n\n"
            f"💰 ЦЕНА: {price} {CURRENCY_SYMBOL}\n\n"
            f"💳 РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ:\n"
            f"{CARD_NUMBER} | {CARD_HOLDER}\n\n"
            f"🆕 ВАШ ID ДЛЯ ОПЛАТЫ (ОБЯЗАТЕЛЬНО В КОММЕНТАРИИ):\n"
            f"<code>{payment_id}</code>\n\n"
            f"📌 ПОСЛЕ ОПЛАТЫ ВЫ ПОЛУЧИТЕ ССЫЛКУ НА КАНАЛ")
    buttons = [
        [InlineKeyboardButton(text="✅ Я ОПЛАТИЛ", callback_data="paid_channel")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_payment")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "paid_premium")
async def paid_premium(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📸 ОТПРАВЬТЕ ФОТО ЧЕКА ДЛЯ ПОДТВЕРЖДЕНИЯ:", reply_markup=get_cancel_kb())
    await state.update_data(payment_type='premium')
    await state.set_state(PaymentPhoto.waiting)

@dp.callback_query(F.data == "paid_channel")
async def paid_channel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📸 ОТПРАВЬТЕ ФОТО ЧЕКА ДЛЯ ПОДТВЕРЖДЕНИЯ:", reply_markup=get_cancel_kb())
    await state.update_data(payment_type='channel')
    await state.set_state(PaymentPhoto.waiting)

@dp.callback_query(F.data == "paid")
async def paid_general(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📸 ОТПРАВЬТЕ ФОТО ЧЕКА ДЛЯ ПОДТВЕРЖДЕНИЯ:", reply_markup=get_cancel_kb())
    await state.set_state(PaymentPhoto.waiting)

@dp.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("❌ ОПЛАТА ОТМЕНЕНА")
    await callback.message.delete()
    await send_main(callback.message)

@dp.message(PaymentPhoto.waiting, F.photo)
async def payment_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    payment_type = data.get('payment_type', 'diamonds')
    diamonds = data.get('diam', 0)
    extra = data.get('extra', None)
    
    add_pending_payment(message.from_user.id, diamonds, message.photo[-1].file_id, payment_type, extra)
    await message.answer("✅ ЗАПРОС ОТПРАВЛЕН! ОЖИДАЙТЕ ПОДТВЕРЖДЕНИЯ.", reply_markup=get_main_kb(message.from_user.id))
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"💰 НОВАЯ ОПЛАТА!\n👤 ID: {message.from_user.id}\n📦 ТИП: {payment_type}\n💎 АЛМАЗЫ: {diamonds if payment_type == 'diamonds' else 'N/A'}")
        except:
            pass
    
    await state.clear()

@dp.message(PaymentPhoto.waiting)
async def payment_not_photo(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await send_main(message)
    else:
        await message.answer("📸 ОТПРАВЬТЕ ФОТО ЧЕКА!")

@dp.message(F.text.in_(["🎁 Промокод", "🎁 Promo code"]))
async def promo_activate_start(message: types.Message, state: FSMContext):
    if is_banned(message.from_user.id):
        return
    if not await check_sub(message):
        return
    await message.answer("🎁 ВВЕДИТЕ ПРОМОКОД:", reply_markup=get_cancel_kb())
    await state.set_state(ActivatePromo.waiting)

@dp.message(ActivatePromo.waiting)
async def promo_activate(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await send_main(message)
        return
    code = message.text.strip().upper()
    promo = get_promo(code)
    if not promo:
        return await message.answer("❌ ПРОМОКОД НЕ НАЙДЕН")
    diam, uses, exp = promo
    if exp and datetime.fromisoformat(exp) < datetime.now():
        return await message.answer("❌ ПРОМОКОД ПРОСРОЧЕН")
    if uses <= 0:
        return await message.answer("❌ ПРОМОКОД УЖЕ ИСПОЛЬЗОВАН")
    if has_activated_promo(message.from_user.id, code):
        return await message.answer("❌ ВЫ УЖЕ АКТИВИРОВАЛИ ЭТОТ ПРОМОКОД")
    update_diamonds(message.from_user.id, diam)
    use_promo(code)
    add_promo_activation(message.from_user.id, code)
    await message.answer(f"✅ +{diam}💎 НАЧИСЛЕНЫ!", reply_markup=get_main_kb(message.from_user.id))
    await state.clear()

@dp.message(F.text.in_(["💰 Заработать", "💰 Earn"]))
async def earn_menu(message: types.Message):
    if is_banned(message.from_user.id):
        return
    if not await check_sub(message):
        return
    
    text = ("💰 ВЫБЕРИТЕ СПОСОБ ЗАРАБОТКА:\n\n"
            "🎬 ЗАДАНИЕ TIKTOK - 20💎\n"
            "👥 РЕФЕРАЛЬНАЯ СИСТЕМА - 3💎 за друга\n"
            "🤖 ТОКЕН BOTFATHER - 3💎 за токен")
    
    await message.answer(text, reply_markup=get_earn_kb())

tiktok_album_cache = {}

@dp.callback_query(F.data == "earn_tiktok")
async def earn_tiktok_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    
    if has_pending_tiktok(user_id):
        return await callback.message.answer("⏰ У ВАС УЖЕ ЕСТЬ ЗАДАНИЕ НА ПРОВЕРКЕ!")
    if not can_do_tiktok(user_id):
        return await callback.message.answer("⏰ ВЫ УЖЕ ВЫПОЛНЯЛИ ЗАДАНИЕ СЕГОДНЯ!")
    
    text = (f"🎬 ЗАДАНИЕ TIKTOK\n\n"
            f"1️⃣ В ПОИСКЕ TIKTOK: детское питание\n"
            f"2️⃣ ПОД 10 ВИДЕО КОММЕНТАРИЙ:\n"
            f"👉 @SHINA_SELL лучший ( топ 1 ) 👈\n"
            f"3️⃣ ЛАЙКНИТЕ СВОЙ КОММЕНТАРИЙ\n"
            f"4️⃣ ОТПРАВЬТЕ 10 СКРИНШОТОВ ОДНИМ СООБЩЕНИЕМ\n\n"
            f"💰 НАГРАДА: {TIKTOK_REWARD}💎")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 СКОПИРОВАТЬ ТЕКСТ", callback_data="copy_tiktok_text")]
    ])
    await callback.message.answer(text, reply_markup=kb)
    await callback.message.answer("📸 ОТПРАВЬТЕ 10 СКРИНШОТОВ ОДНИМ СООБЩЕНИЕМ:", reply_markup=get_cancel_kb())
    await state.set_state(TikTokTask.waiting)

@dp.callback_query(F.data == "copy_tiktok_text")
async def copy_tiktok_text(callback: types.CallbackQuery):
    text_to_copy = "@SHINA_SELL лучший ( топ 1 )"
    await callback.answer(text_to_copy, show_alert=True)

@dp.message(TikTokTask.waiting, F.media_group_id)
async def tiktok_album(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await send_main(message)
        return
    
    gid = message.media_group_id
    if gid not in tiktok_album_cache:
        tiktok_album_cache[gid] = []
    tiktok_album_cache[gid].append(message)
    
    if len(tiktok_album_cache[gid]) >= 10:
        screens = []
        for m in tiktok_album_cache[gid]:
            if m.photo:
                screens.append(m.photo[-1].file_id)
        if len(screens) >= 10:
            save_tiktok_task(message.from_user.id, screens[:10])
            await message.answer("✅ ЗАДАНИЕ ОТПРАВЛЕНО НА ПРОВЕРКУ!", reply_markup=get_main_kb(message.from_user.id))
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, f"📸 НОВОЕ TIKTOK ЗАДАНИЕ ОТ {message.from_user.id}")
                except:
                    pass
        del tiktok_album_cache[gid]
        await state.clear()

@dp.message(TikTokTask.waiting)
async def tiktok_not_album(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await send_main(message)
    else:
        await message.answer("📸 ОТПРАВЬТЕ 10 СКРИНШОТОВ ОДНИМ СООБЩЕНИЕМ!")

@dp.callback_query(F.data == "earn_referrals")
async def earn_referrals_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    me = await bot.get_me()
    bot_username = me.username
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    count = get_referral_count(user_id)
    earned = count * REFERRAL_REWARD
    
    text = (f"👥 РЕФЕРАЛЬНАЯ СИСТЕМА\n\n"
            f"💰 ЗА КАЖДОГО ПРИГЛАШЁННОГО ДРУГА: +{REFERRAL_REWARD}💎\n\n"
            f"🔗 ВАША ССЫЛКА:\n"
            f"<code>{ref_link}</code>\n\n"
            f"📊 ПРИГЛАШЕНО: {count} человек\n"
            f"💎 ЗАРАБОТАНО: {earned} алмазов\n\n"
            f"ПРИГЛАШАЙ ДРУЗЕЙ И ПОЛУЧАЙ АЛМАЗЫ!")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 СКОПИРОВАТЬ ССЫЛКУ", callback_data="copy_ref_link")],
        [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_earn")]
    ])
    
    await callback.message.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "copy_ref_link")
async def copy_ref_link(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref_{user_id}"
    await callback.answer(ref_link, show_alert=True)

@dp.callback_query(F.data == "back_to_earn")
async def back_to_earn(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    text = ("💰 ВЫБЕРИТЕ СПОСОБ ЗАРАБОТКА:\n\n"
            "🎬 ЗАДАНИЕ TIKTOK - 20💎\n"
            "👥 РЕФЕРАЛЬНАЯ СИСТЕМА - 3💎 за друга\n"
            "🤖 ТОКЕН BOTFATHER - 3💎 за токен")
    await callback.message.answer(text, reply_markup=get_earn_kb())

@dp.callback_query(F.data == "earn_token")
async def earn_token_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    
    if not can_do_token_task(user_id):
        return await callback.message.answer("⏰ ВЫ УЖЕ ВЫПОЛНЯЛИ ЗАДАНИЕ С ТОКЕНОМ СЕГОДНЯ!\nВозвращайтесь завтра!")
    
    text = ("🤖 КАК ПОЛУЧИТЬ ТОКЕН?\n\n"
            "1️⃣ Перейдите в бота @BotFather\n\n"
            "2️⃣ Отправьте команду /newbot\n\n"
            "3️⃣ Придумайте имя боту (любое)\n\n"
            "4️⃣ Придумайте username бота (должен заканчиваться на _bot)\n\n"
            "5️⃣ Скопируйте полученный ТОКЕН\n\n"
            "Пример токена:\n"
            "<code>1234567890:ABCdefGHIjklMNOpqrsTUVwxyz</code>\n\n"
            "🎁 НАГРАДА: +3💎 ЗА КАЖДЫЙ НОВЫЙ ТОКЕН\n\n"
            "👇 ВВЕДИТЕ ТОКЕН:")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 ПЕРЕЙТИ В BOTFATHER", url="https://t.me/BotFather")],
        [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_earn")]
    ])
    
    await callback.message.answer(text, reply_markup=kb)
    await callback.message.answer("📝 ВВЕДИТЕ ТОКЕН:", reply_markup=get_cancel_kb())
    await state.set_state(TokenTask.waiting)

@dp.message(TokenTask.waiting)
async def token_check(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await send_main(message)
        return
    
    token = message.text.strip()
    user_id = message.from_user.id
    
    if not can_do_token_task(user_id):
        await message.answer("⏰ ВЫ УЖЕ ВЫПОЛНЯЛИ ЗАДАНИЕ С ТОКЕНОМ СЕГОДНЯ!", reply_markup=get_main_kb(user_id))
        await state.clear()
        return
    
    if not is_token_valid(token):
        await message.answer("❌ НЕВЕРНЫЙ ТОКЕН!\n\nПолучите новый токен у @BotFather и попробуйте снова.", reply_markup=get_main_kb(user_id))
        await state.clear()
        return
    
    if is_token_used(token):
        await message.answer("❌ ЭТОТ ТОКЕН УЖЕ БЫЛ ИСПОЛЬЗОВАН!\n\nКаждый токен можно использовать только 1 раз.", reply_markup=get_main_kb(user_id))
        await state.clear()
        return
    
    bot_username = get_bot_username_from_token(token)
    save_used_token(token, user_id, bot_username)
    save_token_task(user_id)
    update_diamonds(user_id, TOKEN_REWARD)
    
    await message.answer(
        f"✅ ТОКЕН ПРИНЯТ!\n"
        f"🤖 ЮЗЕРНЕЙМ БОТА: {bot_username}\n"
        f"💎 +{TOKEN_REWARD}💎 НАЧИСЛЕНО!\n\n"
        f"💰 БАЛАНС: {get_diamonds(user_id)}💎",
        reply_markup=get_main_kb(user_id)
    )
    await state.clear()

@dp.message(F.text.in_(["❓ Поддержка", "❓ Support"]))
async def support_start(message: types.Message, state: FSMContext):
    if is_banned(message.from_user.id):
        return
    if not await check_sub(message):
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 ОБЫЧНОЕ СООБЩЕНИЕ", callback_data="support_normal")],
        [InlineKeyboardButton(text="👨‍⚖️ АППЕЛЯЦИЯ (ОБЖАЛОВАНИЕ БАНА)", callback_data="support_appeal")]
    ])
    await message.answer("📨 ВЫБЕРИТЕ ТИП ОБРАЩЕНИЯ:", reply_markup=kb)

@dp.callback_query(F.data.startswith("support_"))
async def support_type(callback: types.CallbackQuery, state: FSMContext):
    msg_type = callback.data.split("_")[1]
    is_appeal = (msg_type == "appeal")
    await state.update_data(is_appeal=is_appeal)
    await callback.answer()
    await callback.message.answer("📝 НАПИШИТЕ ВАШЕ СООБЩЕНИЕ:", reply_markup=get_cancel_kb())
    await state.set_state(SupportMsg.waiting)

@dp.message(SupportMsg.waiting)
async def support_send(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await send_main(message)
        return
    
    data = await state.get_data()
    is_appeal = data.get('is_appeal', False)
    
    add_support_message(message.from_user.id, message.text, is_appeal)
    await message.answer("✅ СООБЩЕНИЕ ОТПРАВЛЕНО! МЫ СВЯЖЕМСЯ С ВАМИ В БЛИЖАЙШЕЕ ВРЕМЯ.", reply_markup=get_main_kb(message.from_user.id))
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"📨 НОВОЕ СООБЩЕНИЕ ОТ {message.from_user.id}\n{'👨‍⚖️ АППЕЛЯЦИЯ' if is_appeal else ''}\n\n{message.text[:200]}")
        except:
            pass
    await state.clear()

@dp.message(F.text.in_(["🌐 Сменить язык", "🌐 Change language"]))
async def change_lang(message: types.Message):
    if is_banned(message.from_user.id):
        return
    buttons = [
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("ВЫБЕРИТЕ ЯЗЫК / CHOOSE LANGUAGE:", reply_markup=kb)

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    set_user_lang(callback.from_user.id, lang)
    await callback.answer()
    await callback.message.answer("✅ ЯЗЫК ИЗМЕНЕН!")
    await send_main(callback.message)

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    await send_main(callback.message)

@dp.message(F.text == "👑 Админ панель")
async def admin_panel_entry(message: types.Message, state: FSMContext):
    if is_admin(message.from_user.id):
        await message.answer("👑 АДМИН ПАНЕЛЬ", reply_markup=get_admin_kb())
    else:
        await message.answer("🔐 ВВЕДИТЕ ПАРОЛЬ ДЛЯ ДОСТУПА К АДМИН ПАНЕЛИ:", reply_markup=get_cancel_kb())
        await state.set_state(AdminAuth.waiting)

@dp.message(AdminAuth.waiting)
async def admin_auth(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await send_main(message)
        return
    if message.text == get_setting('admin_password'):
        await message.answer("✅ ДОСТУП К АДМИН ПАНЕЛИ ПОЛУЧЕН!", reply_markup=get_admin_kb())
        log_admin_action(message.from_user.id, message.from_user.username or '', 'admin_login')
    else:
        await message.answer("❌ НЕВЕРНЫЙ ПАРОЛЬ!")
    await state.clear()

@dp.message(F.text == "🔑 Токены", lambda m: is_admin(m.from_user.id))
async def view_tokens(message: types.Message):
    tokens = get_all_used_tokens()
    
    if not tokens:
        await message.answer("🔑 НЕТ ИСПОЛЬЗОВАННЫХ ТОКЕНОВ")
        return
    
    text = "🔑 ИСПОЛЬЗОВАННЫЕ ТОКЕНЫ:\n\n"
    for i, (token, bot_username, user_id, used_at, username, display_name) in enumerate(tokens[:20], 1):
        user_name = display_name or username or str(user_id)
        bot_name = bot_username or "❌ НЕ УКАЗАН"
        token_short = token[:20] + "..." if len(token) > 25 else token
        
        text += f"{i}. 👤 {user_name} (ID: {user_id})\n"
        text += f"   🤖 БОТ: {bot_name}\n"
        text += f"   🔑 ТОКЕН: <code>{token_short}</code>\n"
        text += f"   📅 {used_at[:16]}\n\n"
    
    if len(tokens) > 20:
        text += f"... И ЕЩЁ {len(tokens) - 20} ТОКЕНОВ"
    
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text.startswith("➕ Добавить"), lambda m: is_admin(m.from_user.id))
async def add_content_start(message: types.Message, state: FSMContext):
    text = message.text
    is_vip = 1 if "VIP" in text else 0
    content_type = 'video' if 'видео' in text.lower() else 'photo'
    await state.update_data(content_type=content_type, is_vip=is_vip)
    await message.answer(f"📤 ОТПРАВЬТЕ {content_type.upper()} (МОЖНО НЕСКОЛЬКО ПОДРЯД):", reply_markup=get_cancel_kb())
    await state.set_state(AddContent.waiting)

@dp.message(AddContent.waiting, F.video | F.photo)
async def add_content_file(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    data = await state.get_data()
    content_type, is_vip = data['content_type'], data['is_vip']
    file_id = message.video.file_id if message.video else message.photo[-1].file_id
    path = await download_media(file_id, content_type, is_vip=is_vip)
    add_content_to_db(content_type, path, is_vip)
    await message.answer(f"✅ {content_type.upper()} ДОБАВЛЕН! МОЖЕТЕ ОТПРАВИТЬ ЕЩЕ ИЛИ НАЖМИТЕ ❌ ОТМЕНА.", reply_markup=get_cancel_kb())

@dp.message(AddContent.waiting)
async def add_content_invalid(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, None)
    else:
        await message.answer("❌ ОТПРАВЬТЕ ВИДЕО ИЛИ ФОТО!")

@dp.message(F.text == "💰 Запросы на оплату", lambda m: is_admin(m.from_user.id))
async def pending_payments_admin(message: types.Message):
    payments = get_pending_payments()
    
    if not payments:
        await message.answer("💰 НЕТ ЗАПРОСОВ НА ОПЛАТУ")
        return
    
    for pid, user_id, diamonds, photo, payment_type, extra_json, created_at in payments:
        if payment_type == 'diamonds':
            text = f"🆔 #{pid}\n👤 ID: {user_id}\n💎 АЛМАЗЫ: {diamonds}\n📅 {created_at[:16]}"
        elif payment_type == 'premium':
            text = f"🆔 #{pid}\n👤 ID: {user_id}\n⭐ PREMIUM (30 ДНЕЙ)\n📅 {created_at[:16]}"
        elif payment_type == 'channel':
            text = f"🆔 #{pid}\n👤 ID: {user_id}\n🔒 ПРИВАТНЫЙ КАНАЛ\n📅 {created_at[:16]}"
        else:
            text = f"🆔 #{pid}\n👤 ID: {user_id}\n📦 ТИП: {payment_type}\n📅 {created_at[:16]}"
        
        buttons = [
            [InlineKeyboardButton(text="✅ ПОДТВЕРДИТЬ", callback_data=f"apppay_{pid}")],
            [InlineKeyboardButton(text="❌ ОТКЛОНИТЬ", callback_data=f"rejpay_{pid}")]
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        if photo:
            await message.answer_photo(photo, caption=text, reply_markup=kb)
        else:
            await message.answer(text, reply_markup=kb)
        
        await asyncio.sleep(0.3)

@dp.callback_query(F.data.startswith("apppay_"))
async def approve_payment_cb(callback: types.CallbackQuery):
    payment_id = int(callback.data.split("_")[1])
    info = get_payment_info(payment_id)
    if not info:
        await callback.answer("❌ ЗАПРОС НЕ НАЙДЕН")
        return
    
    user_id, diamonds, payment_type, extra_json = info
    
    if payment_type == 'diamonds':
        update_diamonds(user_id, diamonds)
        await callback.bot.send_message(user_id, f"✅✅✅ ОПЛАТА ПОДТВЕРЖДЕНА! ✅✅✅\n\n💎 ПОЛУЧЕНО: {diamonds}💎\n💰 ТЕКУЩИЙ БАЛАНС: {get_diamonds(user_id)}💎\n\n🎉 СПАСИБО ЗА ПОКУПКУ!")
        
    elif payment_type == 'premium':
        set_premium(user_id, 30)
        link = get_setting('private_channel_link') or "https://t.me/+_example"
        msg = f"✅✅✅ ОПЛАТА ПОДТВЕРЖДЕНА! ✅✅✅\n\n👑 VIP СТАТУС АКТИВИРОВАН НА 30 ДНЕЙ!\n🔒 ДОСТУП К ПРИВАТНОМУ КАНАЛУ: {link}\n\n🎉 СПАСИБО ЗА ПОКУПКУ!"
        await callback.bot.send_message(user_id, msg)
        
    elif payment_type == 'channel':
        link = get_setting('private_channel_link') or "https://t.me/+_example"
        await callback.bot.send_message(user_id, f"✅✅✅ ОПЛАТА ПОДТВЕРЖДЕНА! ✅✅✅\n\n🔒 ВАМ ОТКРЫТ ДОСТУП В ПРИВАТНЫЙ КАНАЛ:\n👉 {link}\n\n🎉 ПРИЯТНОГО ПРОСМОТРА!")
    
    approve_payment(payment_id)
    log_admin_action(callback.from_user.id, callback.from_user.username or '', 'payment_approve', user_id, f'Платеж #{payment_id}')
    await callback.answer()
    await callback.message.edit_text(f"✅ ЗАПРОС #{payment_id} ПОДТВЕРЖДЕН!")

@dp.callback_query(F.data.startswith("rejpay_"))
async def reject_payment_cb(callback: types.CallbackQuery):
    payment_id = int(callback.data.split("_")[1])
    info = get_payment_info(payment_id)
    if info:
        user_id = info[0]
        try:
            await callback.bot.send_message(user_id, "❌ ВАШ ПЛАТЕЖ ОТКЛОНЕН. ПРОВЕРЬТЕ ПРАВИЛЬНОСТЬ ЧЕКА И ОТПРАВЬТЕ СНОВА.")
        except:
            pass
    reject_payment(payment_id)
    await callback.answer()
    await callback.message.edit_text(f"❌ ЗАПРОС #{payment_id} ОТКЛОНЕН")

@dp.message(F.text == "💎 Выдать алмазы", lambda m: is_admin(m.from_user.id))
async def give_diamonds_start(message: types.Message, state: FSMContext):
    await message.answer("📝 ВВЕДИТЕ ID ПОЛЬЗОВАТЕЛЯ:", reply_markup=get_cancel_kb())
    await state.set_state(GiveDiamonds.waiting_id)

@dp.message(GiveDiamonds.waiting_id)
async def give_diamonds_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    try:
        user_id = int(message.text.strip())
        await state.update_data(give_uid=user_id)
        await message.answer(f"💰 ВВЕДИТЕ КОЛИЧЕСТВО АЛМАЗОВ ДЛЯ {user_id}:", reply_markup=get_cancel_kb())
        await state.set_state(GiveDiamonds.waiting_amount)
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО (ID ПОЛЬЗОВАТЕЛЯ)!")

@dp.message(GiveDiamonds.waiting_amount)
async def give_diamonds_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    try:
        amount = int(message.text.strip())
        data = await state.get_data()
        user_id = data.get('give_uid')
        update_diamonds(user_id, amount)
        log_admin_action(message.from_user.id, message.from_user.username or '', 'diamonds_grant', user_id, f'{amount} алмазов')
        await message.answer(f"✅ +{amount}💎 ПОЛЬЗОВАТЕЛЮ {user_id}", reply_markup=get_admin_kb())
        await message.bot.send_message(user_id, f"💰 АДМИНИСТРАТОР НАЧИСЛИЛ ВАМ +{amount}💎!")
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")
    await state.clear()

@dp.message(F.text == "⭐ Выдать Premium", lambda m: is_admin(m.from_user.id))
async def give_premium_start(message: types.Message, state: FSMContext):
    await message.answer("📝 ВВЕДИТЕ ID ПОЛЬЗОВАТЕЛЯ:", reply_markup=get_cancel_kb())
    await state.set_state(GivePremium.waiting_id)

@dp.message(GivePremium.waiting_id)
async def give_premium_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    try:
        user_id = int(message.text.strip())
        await state.update_data(premium_uid=user_id)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="7 ДНЕЙ", callback_data="prem_days_7"),
             InlineKeyboardButton(text="14 ДНЕЙ", callback_data="prem_days_14")],
            [InlineKeyboardButton(text="30 ДНЕЙ", callback_data="prem_days_30"),
             InlineKeyboardButton(text="90 ДНЕЙ", callback_data="prem_days_90")],
            [InlineKeyboardButton(text="365 ДНЕЙ", callback_data="prem_days_365"),
             InlineKeyboardButton(text="НАВСЕГДА", callback_data="prem_days_0")],
            [InlineKeyboardButton(text="❌ ЗАБРАТЬ PREMIUM", callback_data="prem_remove")],
            [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_premium")]
        ])
        await message.answer("⭐ ВЫБЕРИТЕ СРОК PREMIUM:", reply_markup=kb)
        await state.set_state(GivePremium.waiting_days)
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО (ID ПОЛЬЗОВАТЕЛЯ)!")

@dp.callback_query(F.data.startswith("prem_days_"))
async def give_premium_days(callback: types.CallbackQuery, state: FSMContext):
    days = int(callback.data.split("_")[2])
    data = await state.get_data()
    user_id = data.get('premium_uid')
    
    if days == 0:
        set_premium(user_id, 0)
        await callback.bot.send_message(user_id, "⭐ АДМИНИСТРАТОР ВЫДАЛ ВАМ PREMIUM НАВСЕГДА!")
        action = "premium_forever"
    else:
        set_premium(user_id, days)
        await callback.bot.send_message(user_id, f"⭐ АДМИНИСТРАТОР ВЫДАЛ ВАМ PREMIUM НА {days} ДНЕЙ!")
        action = f"premium_{days}_days"
    
    log_admin_action(callback.from_user.id, callback.from_user.username or '', action, user_id, f'Premium на {days} дней')
    await callback.answer(f"✅ PREMIUM ВЫДАН НА {days} ДНЕЙ")
    await callback.message.edit_text(f"✅ PREMIUM ВЫДАН ПОЛЬЗОВАТЕЛЮ {user_id} НА {days} ДНЕЙ")
    await state.clear()

@dp.callback_query(F.data == "prem_remove")
async def give_premium_remove(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('premium_uid')
    remove_premium(user_id)
    await callback.bot.send_message(user_id, "❌ АДМИНИСТРАТОР ЗАБРАЛ У ВАС PREMIUM!")
    log_admin_action(callback.from_user.id, callback.from_user.username or '', 'premium_remove', user_id, 'Premium удален')
    await callback.answer("✅ PREMIUM ЗАБРАН")
    await callback.message.edit_text(f"✅ PREMIUM ЗАБРАН У ПОЛЬЗОВАТЕЛЯ {user_id}")
    await state.clear()

@dp.callback_query(F.data == "cancel_premium")
async def give_premium_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("❌ ОТМЕНЕНО")
    await callback.message.delete()
    await state.clear()
    await admin_panel_entry(callback.message, state)

@dp.message(F.text == "🚫 Бан/Разбан", lambda m: is_admin(m.from_user.id))
async def ban_start(message: types.Message, state: FSMContext):
    await message.answer("📝 ВВЕДИТЕ ID ПОЛЬЗОВАТЕЛЯ:", reply_markup=get_cancel_kb())
    await state.set_state(BanUserState.waiting_id)

@dp.message(BanUserState.waiting_id)
async def ban_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    try:
        user_id = int(message.text.strip())
        user = get_user_by_id(user_id)
        if not user:
            await message.answer("❌ ПОЛЬЗОВАТЕЛЬ НЕ НАЙДЕН!")
            await state.clear()
            return
        await state.update_data(ban_uid=user_id)
        if user[4] == 1:
            unban_user(user_id)
            log_admin_action(message.from_user.id, message.from_user.username or '', 'unban', user_id, 'Разбанен')
            await message.answer(f"✅ ПОЛЬЗОВАТЕЛЬ {user_id} РАЗБАНЕН!", reply_markup=get_admin_kb())
            await message.bot.send_message(user_id, "✅ АДМИНИСТРАТОР СНЯЛ С ВАС БАН!")
            await state.clear()
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="1 ДЕНЬ", callback_data=f"ban_days_{user_id}_1"),
                 InlineKeyboardButton(text="3 ДНЯ", callback_data=f"ban_days_{user_id}_3")],
                [InlineKeyboardButton(text="7 ДНЕЙ", callback_data=f"ban_days_{user_id}_7"),
                 InlineKeyboardButton(text="30 ДНЕЙ", callback_data=f"ban_days_{user_id}_30")],
                [InlineKeyboardButton(text="90 ДНЕЙ", callback_data=f"ban_days_{user_id}_90"),
                 InlineKeyboardButton(text="НАВСЕГДА", callback_data=f"ban_days_{user_id}_0")],
                [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_ban")]
            ])
            await message.answer("📅 ВЫБЕРИТЕ СРОК БАНА:", reply_markup=kb)
            await state.set_state(BanUserState.waiting_days)
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО (ID ПОЛЬЗОВАТЕЛЯ)!")

@dp.callback_query(F.data.startswith("ban_days_"))
async def ban_days_selected(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    days = int(parts[3])
    await state.update_data(ban_uid=user_id, ban_days=days)
    await callback.answer()
    await callback.message.answer("📝 ВВЕДИТЕ ПРИЧИНУ БАНА:", reply_markup=get_cancel_kb())
    await state.set_state(BanUserState.waiting_reason)

@dp.callback_query(F.data == "cancel_ban")
async def ban_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("❌ ОТМЕНЕНО")
    await callback.message.delete()
    await state.clear()
    await admin_panel_entry(callback.message, state)

@dp.message(BanUserState.waiting_reason)
async def ban_reason(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    data = await state.get_data()
    user_id = data['ban_uid']
    days = data['ban_days']
    reason = message.text.strip()
    
    if user_id == message.from_user.id:
        await message.answer("❌ НЕЛЬЗЯ ЗАБАНИТЬ САМОГО СЕБЯ!", reply_markup=get_admin_kb())
        await state.clear()
        return
    
    ban_user(user_id, days, reason)
    duration = "НАВСЕГДА" if days == 0 else f"{days} ДНЕЙ"
    log_admin_action(message.from_user.id, message.from_user.username or '', 'ban', user_id, f'{duration}: {reason}')
    await message.answer(f"✅ ПОЛЬЗОВАТЕЛЬ {user_id} ЗАБАНЕН {duration}!\nПРИЧИНА: {reason}", reply_markup=get_admin_kb())
    await message.bot.send_message(user_id, f"🚫 ВЫ ЗАБАНЕНЫ {duration}!\nПРИЧИНА: {reason}")
    await state.clear()

@dp.message(F.text == "📸 Проверить задания", lambda m: is_admin(m.from_user.id))
async def check_tiktok(message: types.Message):
    tasks = get_pending_tiktok()
    if not tasks:
        return await message.answer("📸 НЕТ ЗАДАНИЙ НА ПРОВЕРКУ")
    
    for task_id, user_id, screenshots, created_at in tasks:
        screens = json.loads(screenshots)
        media = MediaGroupBuilder(caption=f"📸 ЗАДАНИЕ #{task_id} | 👤 {user_id} | {created_at[:16]}")
        for fid in screens[:10]:
            media.add_photo(media=fid)
        await message.answer_media_group(media=media.build())
        
        buttons = [
            [InlineKeyboardButton(text=f"✅ ВЫДАТЬ {TIKTOK_REWARD}💎", callback_data=f"apptik_{task_id}_{user_id}")],
            [InlineKeyboardButton(text="❌ ОТКЛОНИТЬ", callback_data=f"rejtik_{task_id}")]
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer(f"📌 ЗАДАНИЕ #{task_id}", reply_markup=kb)

@dp.callback_query(F.data.startswith("apptik_"))
async def approve_tiktok_cb(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    task_id = int(parts[1])
    user_id = int(parts[2])
    
    approve_tiktok(task_id, user_id)
    log_admin_action(callback.from_user.id, callback.from_user.username or '', 'tiktok_approve', user_id, f'Задание #{task_id}')
    await callback.answer()
    await callback.message.edit_text(f"✅ ЗАДАНИЕ #{task_id} ОДОБРЕНО! ПОЛЬЗОВАТЕЛЬ ПОЛУЧИЛ {TIKTOK_REWARD}💎")
    await callback.bot.send_message(user_id, f"✅ ВАШЕ TIKTOK ЗАДАНИЕ ОДОБРЕНО!\n💰 ВАМ НАЧИСЛЕНО +{TIKTOK_REWARD}💎!")

@dp.callback_query(F.data.startswith("rejtik_"))
async def reject_tiktok_cb(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    reject_tiktok(task_id)
    await callback.answer()
    await callback.message.edit_text(f"❌ ЗАДАНИЕ #{task_id} ОТКЛОНЕНО")

@dp.message(F.text == "🔒 Приватный канал (админ)", lambda m: is_admin(m.from_user.id))
async def private_channel_admin(message: types.Message):
    price = get_setting('private_channel_price', as_int=True) or 299
    link = get_setting('private_channel_link') or 'НЕ УСТАНОВЛЕНА'
    
    buttons = [
        [InlineKeyboardButton(text="💰 ИЗМЕНИТЬ ЦЕНУ", callback_data="ch_price")],
        [InlineKeyboardButton(text="🔗 ИЗМЕНИТЬ ССЫЛКУ", callback_data="ch_link")],
        [InlineKeyboardButton(text="📋 ЗАПРОСЫ НА ДОСТУП", callback_data="ch_requests")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(f"🔒 ПРИВАТНЫЙ КАНАЛ\n💰 ЦЕНА: {price}{CURRENCY_SYMBOL}\n🔗 ССЫЛКА: {link}", reply_markup=kb)

@dp.callback_query(F.data == "ch_price")
async def change_channel_price(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("💰 ВВЕДИТЕ НОВУЮ ЦЕНУ В РУБЛЯХ:", reply_markup=get_cancel_kb())
    await state.set_state(PrivateChannelPrice.waiting)

@dp.message(PrivateChannelPrice.waiting)
async def save_channel_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    try:
        price = int(message.text.strip())
        set_setting('private_channel_price', str(price))
        await message.answer(f"✅ ЦЕНА УСТАНОВЛЕНА: {price}{CURRENCY_SYMBOL}", reply_markup=get_admin_kb())
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")
    await state.clear()

@dp.callback_query(F.data == "ch_link")
async def change_channel_link(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("🔗 ВВЕДИТЕ НОВУЮ ССЫЛКУ НА КАНАЛ:", reply_markup=get_cancel_kb())
    await state.set_state(PrivateChannelLink.waiting)

@dp.message(PrivateChannelLink.waiting)
async def save_channel_link(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    set_setting('private_channel_link', message.text.strip())
    await message.answer("✅ ССЫЛКА СОХРАНЕНА!", reply_markup=get_admin_kb())
    await state.clear()

@dp.callback_query(F.data == "ch_requests")
async def channel_requests_list(callback: types.CallbackQuery):
    requests = get_channel_requests()
    if not requests:
        await callback.answer("НЕТ ЗАПРОСОВ НА ДОСТУП!")
        return
    
    for rid, user_id, created_at in requests:
        text = f"📨 ЗАПРОС #{rid}\n👤 ПОЛЬЗОВАТЕЛЬ: {user_id}\n📅 {created_at[:16]}"
        buttons = [[InlineKeyboardButton(text="✅ ВЫДАТЬ ДОСТУП", callback_data=f"appch_{rid}_{user_id}")]]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.answer(text, reply_markup=kb)
        await asyncio.sleep(0.3)

@dp.callback_query(F.data.startswith("appch_"))
async def approve_channel_request_cb(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    rid = int(parts[1])
    user_id = int(parts[2])
    
    approve_channel_request(rid)
    link = get_setting('private_channel_link')
    log_admin_action(callback.from_user.id, callback.from_user.username or '', 'channel_grant', user_id, f'Запрос #{rid}')
    await callback.answer()
    await callback.message.edit_text(f"✅ ЗАПРОС #{rid} ОДОБРЕН! ПОЛЬЗОВАТЕЛЬ ПОЛУЧИТ ССЫЛКУ.")
    await callback.bot.send_message(user_id, f"✅ ВАШ ЗАПРОС НА ДОСТУП В ПРИВАТНЫЙ КАНАЛ ОДОБРЕН!\n🔗 {link}")

@dp.message(F.text == "🔍 Поиск пользователя", lambda m: is_admin(m.from_user.id))
async def search_user_start(message: types.Message, state: FSMContext):
    await message.answer("🔍 ВВЕДИТЕ ID ИЛИ @USERNAME:", reply_markup=get_cancel_kb())
    await state.set_state(SearchUser.waiting)

@dp.message(SearchUser.waiting)
async def search_user_process(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    
    users = search_users(message.text.strip())
    if not users:
        return await message.answer("❌ ПОЛЬЗОВАТЕЛЬ НЕ НАЙДЕН")
    
    for user_id, username, display_name, diamonds, banned, premium in users:
        name = display_name or username or str(user_id)
        status = (f"👤 {name}\n"
                  f"🆔 ID: {user_id}\n"
                  f"💎 АЛМАЗЫ: {diamonds}\n"
                  f"⭐ PREMIUM: {'✅ ДА' if premium else '❌ НЕТ'}\n"
                  f"🚫 БАН: {'✅ ДА' if banned else '❌ НЕТ'}\n\n"
                  f"🆔 ID ДЛЯ ОПЛАТЫ: <code>{get_user_payment_id(user_id)}</code>")
        
        buttons = [
            [InlineKeyboardButton(text="🔒 ЗАБАНИТЬ" if not banned else "🔓 РАЗБАНИТЬ", callback_data=f"userban_{user_id}")],
            [InlineKeyboardButton(text="💎 ВЫДАТЬ АЛМАЗЫ", callback_data=f"userdiam_{user_id}")],
            [InlineKeyboardButton(text="⭐ PREMIUM" if not premium else "⭐ ЗАБРАТЬ PREMIUM", callback_data=f"userprem_{user_id}")]
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer(status, reply_markup=kb)
    
    await state.clear()

@dp.callback_query(F.data.startswith("userban_"))
async def user_ban_cb(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    
    if user_id == callback.from_user.id:
        await callback.answer("❌ НЕЛЬЗЯ ЗАБАНИТЬ САМОГО СЕБЯ!", show_alert=True)
        return
    
    if is_banned(user_id):
        unban_user(user_id)
        log_admin_action(callback.from_user.id, callback.from_user.username or '', 'unban', user_id, 'Разбанен')
        await callback.answer("✅ ПОЛЬЗОВАТЕЛЬ РАЗБАНЕН")
        await callback.message.edit_text(f"✅ ПОЛЬЗОВАТЕЛЬ {user_id} РАЗБАНЕН")
        await callback.bot.send_message(user_id, "✅ АДМИНИСТРАТОР СНЯЛ С ВАС БАН!")
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1 ДЕНЬ", callback_data=f"ban_{user_id}_1"),
             InlineKeyboardButton(text="3 ДНЯ", callback_data=f"ban_{user_id}_3")],
            [InlineKeyboardButton(text="7 ДНЕЙ", callback_data=f"ban_{user_id}_7"),
             InlineKeyboardButton(text="30 ДНЕЙ", callback_data=f"ban_{user_id}_30")],
            [InlineKeyboardButton(text="90 ДНЕЙ", callback_data=f"ban_{user_id}_90"),
             InlineKeyboardButton(text="НАВСЕГДА", callback_data=f"ban_{user_id}_0")],
            [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_user_ban")]
        ])
        await callback.message.answer(f"📅 ВЫБЕРИТЕ СРОК БАНА ДЛЯ {user_id}:", reply_markup=kb)

@dp.callback_query(F.data.startswith("ban_") and F.data.count("_") == 2)
async def user_ban_days(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[1])
    days = int(parts[2])
    
    ban_user(user_id, days, "Нарушение правил")
    duration = "НАВСЕГДА" if days == 0 else f"{days} ДНЕЙ"
    log_admin_action(callback.from_user.id, callback.from_user.username or '', 'ban', user_id, f'{duration}')
    await callback.answer(f"🚫 ПОЛЬЗОВАТЕЛЬ ЗАБАНЕН НА {duration}")
    await callback.message.edit_text(f"🚫 ПОЛЬЗОВАТЕЛЬ {user_id} ЗАБАНЕН НА {duration}")
    await callback.bot.send_message(user_id, f"🚫 АДМИНИСТРАТОР ЗАБАНИЛ ВАС НА {duration}!")

@dp.callback_query(F.data == "cancel_user_ban")
async def cancel_user_ban(callback: types.CallbackQuery):
    await callback.answer("❌ ОТМЕНЕНО")
    await callback.message.delete()

@dp.callback_query(F.data.startswith("userdiam_"))
async def user_diam_cb(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])
    await state.update_data(give_uid=user_id)
    await callback.answer()
    await callback.message.answer(f"💰 ВВЕДИТЕ КОЛИЧЕСТВО АЛМАЗОВ ДЛЯ ПОЛЬЗОВАТЕЛЯ {user_id}:", reply_markup=get_cancel_kb())
    await state.set_state(GiveDiamonds.waiting_amount)

@dp.callback_query(F.data.startswith("userprem_"))
async def user_prem_cb(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])
    await state.update_data(premium_uid=user_id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="7 ДНЕЙ", callback_data=f"prem_{user_id}_7"),
         InlineKeyboardButton(text="14 ДНЕЙ", callback_data=f"prem_{user_id}_14")],
        [InlineKeyboardButton(text="30 ДНЕЙ", callback_data=f"prem_{user_id}_30"),
         InlineKeyboardButton(text="90 ДНЕЙ", callback_data=f"prem_{user_id}_90")],
        [InlineKeyboardButton(text="365 ДНЕЙ", callback_data=f"prem_{user_id}_365"),
         InlineKeyboardButton(text="НАВСЕГДА", callback_data=f"prem_{user_id}_0")],
        [InlineKeyboardButton(text="❌ ЗАБРАТЬ PREMIUM", callback_data=f"prem_remove_{user_id}")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_user_prem")]
    ])
    await callback.message.answer(f"⭐ ВЫБЕРИТЕ СРОК PREMIUM ДЛЯ {user_id}:", reply_markup=kb)

@dp.callback_query(F.data.startswith("prem_") and F.data.count("_") == 2)
async def user_prem_days(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[1])
    days = int(parts[2])
    
    if days == 0:
        set_premium(user_id, 0)
        await callback.bot.send_message(user_id, "⭐ АДМИНИСТРАТОР ВЫДАЛ ВАМ PREMIUM НАВСЕГДА!")
    else:
        set_premium(user_id, days)
        await callback.bot.send_message(user_id, f"⭐ АДМИНИСТРАТОР ВЫДАЛ ВАМ PREMIUM НА {days} ДНЕЙ!")
    
    await callback.answer(f"✅ PREMIUM ВЫДАН НА {days} ДНЕЙ")
    await callback.message.edit_text(f"✅ PREMIUM ВЫДАН ПОЛЬЗОВАТЕЛЮ {user_id} НА {days} ДНЕЙ")

@dp.callback_query(F.data.startswith("prem_remove_"))
async def user_prem_remove(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    remove_premium(user_id)
    await callback.bot.send_message(user_id, "❌ АДМИНИСТРАТОР ЗАБРАЛ У ВАС PREMIUM!")
    await callback.answer("✅ PREMIUM ЗАБРАН")
    await callback.message.edit_text(f"✅ PREMIUM ЗАБРАН У ПОЛЬЗОВАТЕЛЯ {user_id}")

@dp.callback_query(F.data == "cancel_user_prem")
async def cancel_user_prem(callback: types.CallbackQuery):
    await callback.answer("❌ ОТМЕНЕНО")
    await callback.message.delete()

@dp.message(F.text == "👥 Все пользователи", lambda m: is_admin(m.from_user.id))
async def all_users_admin(message: types.Message):
    users = get_all_users()
    if not users:
        return await message.answer("👥 НЕТ ПОЛЬЗОВАТЕЛЕЙ")
    
    text = "👥 СПИСОК ПОЛЬЗОВАТЕЛЕЙ (ПЕРВЫЕ 50):\n\n"
    for user_id, username, display_name, diamonds, banned in users[:50]:
        name = display_name or username or str(user_id)
        text += f"{'🚫' if banned else '✅'} {name} | 💎{diamonds} | ID: {user_id}\n"
    
    if len(users) > 50:
        text += f"\n... И ЕЩЁ {len(users) - 50} ПОЛЬЗОВАТЕЛЕЙ"
    
    await message.answer(text)

@dp.message(F.text == "📩 Сообщения", lambda m: is_admin(m.from_user.id))
async def support_messages_admin(message: types.Message):
    messages = get_unread_support_messages()
    if not messages:
        return await message.answer("📩 НЕТ НОВЫХ СООБЩЕНИЙ")
    
    for msg_id, user_id, msg_text, created_at, is_appeal in messages:
        appeal_tag = "👨‍⚖️ [АППЕЛЯЦИЯ] " if is_appeal else ""
        text = f"📨 {appeal_tag}ОТ ПОЛЬЗОВАТЕЛЯ: {user_id}\n📅 {created_at[:16]}\n\n{msg_text}"
        buttons = [[InlineKeyboardButton(text="✅ ОТВЕТИТЬ", callback_data=f"reply_msg_{user_id}_{msg_id}")]]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer(text, reply_markup=kb)
        await asyncio.sleep(0.3)

@dp.callback_query(F.data.startswith("reply_msg_"))
async def reply_to_user(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    msg_id = int(parts[3])
    await state.update_data(reply_uid=user_id, reply_mid=msg_id)
    await callback.answer()
    await callback.message.answer(f"📝 ВВЕДИТЕ ОТВЕТ ДЛЯ ПОЛЬЗОВАТЕЛЯ {user_id}:", reply_markup=get_cancel_kb())
    await state.set_state(AdminReply.waiting_reply)

@dp.message(AdminReply.waiting_reply)
async def send_reply(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    
    data = await state.get_data()
    user_id = data.get('reply_uid')
    msg_id = data.get('reply_mid')
    
    if user_id:
        try:
            await message.bot.send_message(user_id, f"📨 *ОТВЕТ ОТ ПОДДЕРЖКИ:*\n\n{message.text}", parse_mode="Markdown")
            mark_support_read(msg_id)
            log_admin_action(message.from_user.id, message.from_user.username or '', 'support_reply', user_id, message.text[:100])
            await message.answer(f"✅ ОТВЕТ ОТПРАВЛЕН ПОЛЬЗОВАТЕЛЮ {user_id}", reply_markup=get_admin_kb())
        except Exception as e:
            await message.answer(f"❌ ОШИБКА: {e}")
    
    await state.clear()

@dp.message(F.text == "📊 Статистика", lambda m: is_admin(m.from_user.id))
async def stats_admin(message: types.Message):
    conn = get_db()
    c = conn.cursor()
    
    total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    banned_users = c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1").fetchone()[0]
    premium_users = c.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1").fetchone()[0]
    videos = c.execute("SELECT COUNT(*) FROM content WHERE type = 'video' AND is_vip = 0").fetchone()[0]
    vip_videos = c.execute("SELECT COUNT(*) FROM content WHERE type = 'video' AND is_vip = 1").fetchone()[0]
    photos = c.execute("SELECT COUNT(*) FROM content WHERE type = 'photo' AND is_vip = 0").fetchone()[0]
    vip_photos = c.execute("SELECT COUNT(*) FROM content WHERE type = 'photo' AND is_vip = 1").fetchone()[0]
    payments = c.execute("SELECT COUNT(*) FROM pending_payments WHERE status = 'pending'").fetchone()[0]
    tasks = c.execute("SELECT COUNT(*) FROM screenshot_tasks WHERE status = 'pending'").fetchone()[0]
    support = c.execute("SELECT COUNT(*) FROM support_messages WHERE is_read = 0").fetchone()[0]
    token_tasks = c.execute("SELECT COUNT(*) FROM used_tokens").fetchone()[0]
    conn.close()
    
    text = (f"📊 СТАТИСТИКА БОТА @{await get_bot_username()}\n\n"
            f"👥 ПОЛЬЗОВАТЕЛИ:\n"
            f"• ВСЕГО: {total_users}\n"
            f"• ЗАБАНЕНЫ: {banned_users}\n"
            f"• PREMIUM: {premium_users}\n\n"
            f"📹 КОНТЕНТ:\n"
            f"• ВИДЕО: {videos}\n"
            f"• VIP ВИДЕО: {vip_videos}\n"
            f"• ФОТО: {photos}\n"
            f"• VIP ФОТО: {vip_photos}\n\n"
            f"💰 ЗАПРОСОВ НА ОПЛАТУ: {payments}\n"
            f"📸 ЗАДАНИЙ TIKTOK: {tasks}\n"
            f"📨 СООБЩЕНИЙ В ПОДДЕРЖКУ: {support}\n"
            f"🔑 ИСПОЛЬЗОВАНО ТОКЕНОВ: {token_tasks}")
    
    await message.answer(text)

@dp.message(F.text == "🎁 Промокоды (админ)", lambda m: is_admin(m.from_user.id))
async def promo_admin(message: types.Message):
    buttons = [[InlineKeyboardButton(text="➕ СОЗДАТЬ НОВЫЙ ПРОМОКОД", callback_data="create_promo")]]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("🎁 УПРАВЛЕНИЕ ПРОМОКОДАМИ", reply_markup=kb)

@dp.callback_query(F.data == "create_promo")
async def create_promo_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📝 ВВЕДИТЕ КОД ПРОМОКОДА:", reply_markup=get_cancel_kb())
    await state.set_state(CreatePromo.code)

@dp.message(CreatePromo.code)
async def promo_code(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    await state.update_data(code=message.text.strip().upper())
    await message.answer("💰 ВВЕДИТЕ КОЛИЧЕСТВО АЛМАЗОВ:")
    await state.set_state(CreatePromo.diamonds)

@dp.message(CreatePromo.diamonds)
async def promo_diamonds(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    try:
        await state.update_data(diamonds=int(message.text.strip()))
        await message.answer("📊 ВВЕДИТЕ КОЛИЧЕСТВО АКТИВАЦИЙ:")
        await state.set_state(CreatePromo.uses)
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")

@dp.message(CreatePromo.uses)
async def promo_uses(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    try:
        await state.update_data(uses=int(message.text.strip()))
        await message.answer("📅 ВВЕДИТЕ СРОК ДЕЙСТВИЯ (ДНЕЙ, 0 = БЕССРОЧНО):")
        await state.set_state(CreatePromo.days)
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")

@dp.message(CreatePromo.days)
async def promo_days(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    try:
        days = int(message.text.strip())
        data = await state.get_data()
        expires = (datetime.now() + timedelta(days=days)).isoformat() if days > 0 else None
        add_promo(data['code'], data['diamonds'], data['uses'], expires)
        log_admin_action(message.from_user.id, message.from_user.username or '', 'promo_create', None, f'Код {data["code"]}')
        await message.answer(f"✅ ПРОМОКОД {data['code']} СОЗДАН!\n💎 {data['diamonds']} АЛМАЗОВ\n📊 {data['uses']} АКТИВАЦИЙ", reply_markup=get_admin_kb())
        await state.clear()
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")

@dp.message(F.text == "🖼️ Сменить медиа", lambda m: is_admin(m.from_user.id))
async def change_media_menu(message: types.Message):
    buttons = []
    for section in ['welcome', 'buy', 'vip', 'profile', 'support']:
        photo_path = get_setting(f'photo_{section}')
        video_path = get_setting(f'video_{section}')
        photo_status = "✅" if photo_path and os.path.exists(photo_path) else "❌"
        video_status = "✅" if video_path and os.path.exists(video_path) else "❌"
        buttons.append([InlineKeyboardButton(text=f"📸 ФОТО {section} {photo_status}", callback_data=f"media_change_photo_{section}")])
        buttons.append([InlineKeyboardButton(text=f"🎥 ВИДЕО {section} {video_status}", callback_data=f"media_change_video_{section}")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("🖼️ СМЕНА МЕДИА\n✅ - УСТАНОВЛЕНО, ❌ - НЕТ", reply_markup=kb)

@dp.callback_query(F.data.startswith("media_change_"))
async def media_type_selected(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    media_type = parts[2]
    section = parts[3]
    await state.update_data(media_type=media_type, section=section)
    await callback.answer()
    await callback.message.answer(f"📤 ОТПРАВЬТЕ {media_type.upper()} ДЛЯ РАЗДЕЛА '{section}':", reply_markup=get_cancel_kb())
    await state.set_state(ChangeMedia.waiting)

@dp.message(ChangeMedia.waiting, F.video | F.photo)
async def media_received(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    
    data = await state.get_data()
    media_type = data['media_type']
    section = data['section']
    
    old_key = f'{media_type}_{section}'
    old_path = get_setting(old_key)
    if old_path and os.path.exists(old_path) and old_path != WELCOME_PHOTO_PATH:
        os.remove(old_path)
    
    file_id = message.video.file_id if message.video else message.photo[-1].file_id
    path = await download_media(file_id, media_type, menu_key=f"{media_type}_{section}")
    set_setting(old_key, path)
    
    log_admin_action(message.from_user.id, message.from_user.username or '', 'media_change', None, f'{media_type}_{section}')
    await message.answer(f"✅ МЕДИА ДЛЯ РАЗДЕЛА '{section}' СОХРАНЕНО!", reply_markup=get_admin_kb())
    await state.clear()

@dp.message(ChangeMedia.waiting)
async def media_invalid(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
    else:
        await message.answer("❌ ОТПРАВЬТЕ ФОТО ИЛИ ВИДЕО!")

@dp.message(F.text == "💰 Изменить цены", lambda m: is_admin(m.from_user.id))
async def change_prices_menu(message: types.Message, state: FSMContext):
    buttons = [
        [InlineKeyboardButton(text=f"10💎 - {get_setting('price_10')}{CURRENCY_SYMBOL}", callback_data="price_10")],
        [InlineKeyboardButton(text=f"20💎 - {get_setting('price_20')}{CURRENCY_SYMBOL}", callback_data="price_20")],
        [InlineKeyboardButton(text=f"30💎 - {get_setting('price_30')}{CURRENCY_SYMBOL}", callback_data="price_30")],
        [InlineKeyboardButton(text=f"40💎 - {get_setting('price_40')}{CURRENCY_SYMBOL}", callback_data="price_40")],
        [InlineKeyboardButton(text=f"50💎 - {get_setting('price_50')}{CURRENCY_SYMBOL}", callback_data="price_50")],
        [InlineKeyboardButton(text=f"100💎 - {get_setting('price_100')}{CURRENCY_SYMBOL}", callback_data="price_100")],
        [InlineKeyboardButton(text=f"⭐ PREMIUM - {get_setting('premium_price')}{CURRENCY_SYMBOL}", callback_data="price_premium")],
        [InlineKeyboardButton(text=f"🔒 ПРИВАТНЫЙ КАНАЛ - {get_setting('private_channel_price')}{CURRENCY_SYMBOL}", callback_data="price_channel")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("💰 ВЫБЕРИТЕ ПОЗИЦИЮ ДЛЯ ИЗМЕНЕНИЯ ЦЕНЫ:", reply_markup=kb)
    await state.set_state(ChangePrice.ptype)

@dp.callback_query(ChangePrice.ptype, F.data.startswith("price_"))
async def price_type_selected(callback: types.CallbackQuery, state: FSMContext):
    setting_key = callback.data
    await state.update_data(price_type=setting_key)
    await callback.answer()
    
    display_name = {
        'price_10': '10💎',
        'price_20': '20💎', 
        'price_30': '30💎',
        'price_40': '40💎',
        'price_50': '50💎',
        'price_100': '100💎',
        'price_premium': '⭐ PREMIUM',
        'price_channel': '🔒 ПРИВАТНЫЙ КАНАЛ'
    }.get(setting_key, setting_key)
    
    await callback.message.answer(f"📝 ВВЕДИТЕ НОВУЮ ЦЕНУ ДЛЯ {display_name} (В РУБЛЯХ):", reply_markup=get_cancel_kb())
    await state.set_state(ChangePrice.val)

@dp.message(ChangePrice.val)
async def price_value_save(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    try:
        value = int(message.text.strip())
        data = await state.get_data()
        set_setting(data['price_type'], str(value))
        log_admin_action(message.from_user.id, message.from_user.username or '', 'price_change', None, f'{data["price_type"]}={value}')
        await message.answer(f"✅ ЦЕНА ОБНОВЛЕНА: {value}{CURRENCY_SYMBOL}", reply_markup=get_admin_kb())
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")
    await state.clear()

@dp.message(F.text == "💳 Реквизиты", lambda m: is_admin(m.from_user.id))
async def card_menu(message: types.Message, state: FSMContext):
    await message.answer(f"💳 ТЕКУЩИЕ РЕКВИЗИТЫ:\n\nКАРТА: {get_setting('card_number')}\nВЛАДЕЛЕЦ: {get_setting('card_holder')}\n\nВВЕДИТЕ НОВЫЙ НОМЕР КАРТЫ:", reply_markup=get_cancel_kb())
    await state.set_state(ChangeCard.num)

@dp.message(ChangeCard.num)
async def card_num(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    await state.update_data(card_num=message.text.strip())
    await message.answer("ВВЕДИТЕ ИМЯ ВЛАДЕЛЬЦА КАРТЫ:")
    await state.set_state(ChangeCard.holder)

@dp.message(ChangeCard.holder)
async def card_holder(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    data = await state.get_data()
    set_setting('card_number', data['card_num'])
    set_setting('card_holder', message.text.strip())
    log_admin_action(message.from_user.id, message.from_user.username or '', 'card_change')
    await message.answer("✅ РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ ОБНОВЛЕНЫ!", reply_markup=get_admin_kb())
    await state.clear()

@dp.message(F.text == "💾 Бэкап", lambda m: is_admin(m.from_user.id))
async def backup_menu_admin(message: types.Message):
    buttons = [
        [InlineKeyboardButton(text="💾 БЭКАП ТОЛЬКО БД", callback_data="backup_create")],
        [InlineKeyboardButton(text="📦 СКАЧАТЬ БД", callback_data="backup_db")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("💾 БЭКАП СИСТЕМЫ", reply_markup=kb)

@dp.callback_query(F.data == "backup_create")
async def backup_create(callback: types.CallbackQuery):
    await callback.answer("⏳ СОЗДАНИЕ БЭКАПА...")
    
    name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    path = f"{BACKUP_DIR}/{name}"
    
    try:
        shutil.copy2(DB_PATH, path)
        await callback.message.answer_document(FSInputFile(path), caption=f"📦 {name}")
        os.remove(path)
    except Exception as e:
        await callback.answer(f"❌ ОШИБКА: {e}")

@dp.callback_query(F.data == "backup_db")
async def backup_db(callback: types.CallbackQuery):
    if os.path.exists(DB_PATH):
        await callback.message.answer_document(FSInputFile(DB_PATH), caption="📁 westvideo.db")
    else:
        await callback.answer("❌ БАЗА ДАННЫХ НЕ НАЙДЕНА!")

@dp.message(F.text == "📨 Рассылка", lambda m: is_admin(m.from_user.id))
async def broadcast_start(message: types.Message, state: FSMContext):
    await message.answer("📨 ВВЕДИТЕ ТЕКСТ ДЛЯ РАССЫЛКИ (МОЖНО С ФОТО):", reply_markup=get_cancel_kb())
    await state.set_state(Broadcast.waiting)

@dp.message(Broadcast.waiting)
async def broadcast_preview(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message, state)
        return
    
    await state.update_data(broadcast_text=message.text or message.caption,
                           broadcast_photo=message.photo[-1].file_id if message.photo else None)
    
    buttons = [
        [InlineKeyboardButton(text="✅ ОТПРАВИТЬ", callback_data="confirm_broadcast")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_broadcast")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    if message.photo:
        await message.answer_photo(message.photo[-1].file_id, caption=f"📨 ПРЕВЬЮ:\n\n{message.caption}", reply_markup=kb)
    else:
        await message.answer(f"📨 ПРЕВЬЮ:\n\n{message.text}", reply_markup=kb)
    
    await state.set_state(Broadcast.confirm)

@dp.callback_query(F.data == "confirm_broadcast")
async def broadcast_confirm(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get('broadcast_text')
    photo = data.get('broadcast_photo')
    
    users = get_all_users()
    sent = 0
    for user_id, _, _, _, _ in users:
        try:
            if photo:
                await callback.bot.send_photo(user_id, photo, caption=text or "")
            else:
                await callback.bot.send_message(user_id, text)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    
    log_admin_action(callback.from_user.id, callback.from_user.username or '', 'broadcast', None, f'Отправлено {sent} пользователям')
    await callback.message.edit_text(f"✅ РАССЫЛКА ОТПРАВЛЕНА {sent} ПОЛЬЗОВАТЕЛЯМ!")
    await admin_panel_entry(callback.message, state)
    await state.clear()

@dp.callback_query(F.data == "cancel_broadcast")
async def broadcast_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("❌ ОТМЕНЕНО")
    await callback.message.delete()
    await admin_panel_entry(callback.message, state)
    await state.clear()

@dp.message(F.text == "🔘 Проверка подписки", lambda m: is_admin(m.from_user.id))
async def toggle_sub_check(message: types.Message):
    current = is_sub_check_enabled()
    new_status = not current
    set_setting('subscription_check_enabled', '1' if new_status else '0')
    status_text = "ВКЛЮЧЕНА" if new_status else "ОТКЛЮЧЕНА"
    await message.answer(f"✅ ПРОВЕРКА ПОДПИСКИ {status_text}!")

async def set_commands():
    await bot.set_my_commands([BotCommand(command="start", description="🚀 ЗАПУСТИТЬ")])

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ БОТ ЗАПУЩЕН!")
    await set_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 ОСТАНОВЛЕН")
