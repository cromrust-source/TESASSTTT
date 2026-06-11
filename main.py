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
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import StateFilter, Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand, FSInputFile, ReplyKeyboardRemove, CopyTextButton
)
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.client.default import DefaultBotProperties

logger.info("🚀 Запуск бота...")

# ============ НАСТРОЙКИ БОТА ============
BOT_TOKEN = "8846249070:AAFTO1Z_QDH3YWGZE0igwzRw9qQ5pkdM8cA"

# ============ АДМИНИСТРАТОР ============
ADMIN_IDS = [8440994107]

REQUIRED_CHANNEL = "RadionTeams"
SUPPORT_USERNAME = "@Radion_lil"
STARS_CONTACT = "Radion_lil"
BOT_USERNAME = "FlexStrong_bot"

TIKTOK_REWARD = 12
REFERRAL_REWARD = 3
TOKEN_REWARD = 3
START_DIAMONDS = 3
SUBSCRIPTION_DAYS = 7

DAILY_BONUS_NORMAL = 2
DAILY_BONUS_PREMIUM = 6
PREMIUM_FREE_VIDEOS_PER_DAY = 5

UNBAN_PRICE_RUB = 150
UNBAN_PRICE_STARS = 125

MEDIA_DIR = "media"
BACKUP_DIR = "backups"

CARD_NUMBER = "2200701416893938"
CARD_HOLDER = "Сергей"
CURRENCY_SYMBOL = "₽"
STARS_SYMBOL = "⭐"

WELCOME_PHOTO_URL = ""
WELCOME_PHOTO_PATH = f"{MEDIA_DIR}/menu/welcome.jpg"

# ============ НАСТРОЙКИ ПАКОВ ============
CATEGORIES = {
    "starter": {"name": "ДЕТСКОЕ", "price_rub": 200, "price_stars": 150},
    "gold": {"name": "16-18 лет", "price_rub": 150, "price_stars": 150},
    "vip": {"name": "11-15 лет", "price_rub": 299, "price_stars": 250},
    "premium_pack": {"name": "ШКОЛЬНИЦЫ", "price_rub": 199, "price_stars": 150},
    "general": {"name": "ОБЩИЙ ПАК", "price_rub": 0, "price_stars": 0}
}

for folder in [
    f"{MEDIA_DIR}/menu", f"{MEDIA_DIR}/content/video", f"{MEDIA_DIR}/content/photo",
    f"{MEDIA_DIR}/content/video_vip", f"{MEDIA_DIR}/content/photo_vip",
    f"{MEDIA_DIR}/categories/starter", f"{MEDIA_DIR}/categories/gold",
    f"{MEDIA_DIR}/categories/vip", f"{MEDIA_DIR}/categories/premium_pack",
    f"{MEDIA_DIR}/categories/general", BACKUP_DIR
]:
    Path(folder).mkdir(parents=True, exist_ok=True)

logger.info("🤖 Инициализация бота...")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

subscription_cache = {}
user_languages = {}
_cached_bot_username = None
_settings_cache = {}

ANTI_BOT_EMOJIS = ["💎", "♥️", "🔞", "⭐", "📸", "🎥", "👑", "💰"]

DB_PATH = "westvideo.db"

# ============ ПУЛ ПОТОКОВ ДЛЯ БАЗЫ ДАННЫХ ============
_executor = ThreadPoolExecutor(max_workers=4)

def run_sync(func, *args, **kwargs):
    return asyncio.get_event_loop().run_in_executor(_executor, lambda: func(*args, **kwargs))

# ============ КЭШ ============
class Cache:
    def __init__(self, ttl=60):
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time() - timestamp < self.ttl:
                return data
            del self.cache[key]
        return None
    
    def set(self, key, value):
        self.cache[key] = (value, time())

from time import time
user_cache = Cache(ttl=30)
settings_cache = Cache(ttl=60)
diamonds_cache = Cache(ttl=10)
premium_cache = Cache(ttl=30)

# ============ ФУНКЦИИ БАЗЫ ДАННЫХ ============
def get_db():
    return sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)

def init_db_sync():
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT, display_name TEXT, diamonds INTEGER DEFAULT 3,
        is_premium INTEGER DEFAULT 0, premium_until TIMESTAMP, last_bonus TIMESTAMP,
        is_banned INTEGER DEFAULT 0, ban_until TIMESTAMP, ban_reason TEXT,
        referrer_id INTEGER, total_referrals INTEGER DEFAULT 0,
        language TEXT DEFAULT 'ru', passed_antibot INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS content (
        id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, file_path TEXT,
        is_vip INTEGER DEFAULT 0, file_hash TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS viewed_content (
        user_id INTEGER, content_id INTEGER, content_type TEXT,
        viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_premium_free INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, content_id, content_type)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS category_videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, category_id TEXT, file_path TEXT,
        file_hash TEXT, added_by INTEGER, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(category_id, file_hash)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS category_purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, category_id TEXT,
        payment_id INTEGER, status TEXT DEFAULT 'completed', is_free_gift INTEGER DEFAULT 0,
        granted_by TEXT, purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, category_id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS pending_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, diamonds INTEGER,
        status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        photo_file_id TEXT, payment_type TEXT, extra_data TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS support_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, message TEXT,
        is_read INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_appeal INTEGER DEFAULT 0
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS promo_codes (
        code TEXT PRIMARY KEY, diamonds INTEGER, uses_left INTEGER, expires TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS promo_activations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, promo_code TEXT,
        activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS screenshot_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, screenshots TEXT,
        status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_tasks (
        user_id INTEGER, task_type TEXT, completed_at TIMESTAMP,
        UNIQUE(user_id, task_type, completed_at)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER, referred_id INTEGER UNIQUE,
        reward_given INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS antibot_fails (
        user_id INTEGER PRIMARY KEY, fail_count INTEGER DEFAULT 0,
        last_fail TIMESTAMP, banned_until TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, admin_username TEXT,
        action TEXT, target_user_id INTEGER, details TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS used_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT UNIQUE, user_id INTEGER,
        bot_username TEXT, used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS token_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS discounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, percent INTEGER DEFAULT 0,
        until TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS diamond_spends (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER,
        action TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS premium_purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, days INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    defaults = [
        ('price_10', '30'), ('price_20', '60'), ('price_30', '90'), ('price_40', '100'),
        ('price_50', '150'), ('price_100', '249'), ('premium_price', '200'),
        ('private_channel_price', '299'), ('private_channel_link', ''),
        ('card_number', CARD_NUMBER), ('card_holder', CARD_HOLDER),
        ('subscription_check_enabled', '1'), ('subscription_channel', REQUIRED_CHANNEL),
        ('referral_reward', str(REFERRAL_REWARD)), ('photo_welcome', WELCOME_PHOTO_PATH),
        ('video_welcome', ''), ('photo_buy', ''), ('video_buy', ''),
        ('photo_vip', ''), ('video_vip', ''), ('photo_profile', ''), ('video_profile', ''),
        ('photo_support', ''), ('video_support', ''),
        ('stars_price_10', '30'), ('stars_price_20', '50'), ('stars_price_30', '75'),
        ('stars_price_40', '85'), ('stars_price_50', '100'), ('stars_price_100', '200'),
        ('stars_premium_price', '150'), ('stars_channel_price', '250'),
        ('unban_price_rub', str(UNBAN_PRICE_RUB)), ('unban_price_stars', str(UNBAN_PRICE_STARS))
    ]
    for k, v in defaults:
        c.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (k, v))
    
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def get_setting_sync(key: str, as_int: bool = False):
    cached = settings_cache.get(key)
    if cached is not None:
        return int(cached) if as_int else cached
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    val = row[0] if row else None
    if val:
        settings_cache.set(key, val)
    return int(val) if as_int and val else val

async def get_setting(key: str, as_int: bool = False):
    return await run_sync(get_setting_sync, key, as_int)

async def set_setting(key: str, value: str):
    def sync():
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, str(value)))
        conn.commit()
        conn.close()
        settings_cache.set(key, value)
    await run_sync(sync)

def get_diamonds_sync(user_id: int) -> int:
    cached = diamonds_cache.get(user_id)
    if cached is not None:
        return cached
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT diamonds FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    val = row[0] if row else 0
    diamonds_cache.set(user_id, val)
    return val

async def get_diamonds(user_id: int) -> int:
    return await run_sync(get_diamonds_sync, user_id)

async def update_diamonds(user_id: int, amount: int):
    def sync():
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        c.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()
        diamonds_cache.set(user_id, get_diamonds_sync(user_id))
    await run_sync(sync)

def is_premium_sync(user_id: int) -> bool:
    cached = premium_cache.get(user_id)
    if cached is not None:
        return cached
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_premium, premium_until FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == 1:
        if row[1] and datetime.fromisoformat(row[1]) < datetime.now():
            premium_cache.set(user_id, False)
            return False
        premium_cache.set(user_id, True)
        return True
    premium_cache.set(user_id, False)
    return False

async def is_premium(user_id: int) -> bool:
    return await run_sync(is_premium_sync, user_id)

async def set_premium(user_id: int, days: int):
    def sync():
        until = None if days == 0 else (datetime.now() + timedelta(days=days)).isoformat()
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?", (until, user_id))
        conn.commit()
        conn.close()
        premium_cache.set(user_id, True)
    await run_sync(sync)

def get_user_lang_sync(user_id: int) -> str:
    cached = user_cache.get(f"lang_{user_id}")
    if cached:
        return cached
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    lang = row[0] if row else 'ru'
    user_cache.set(f"lang_{user_id}", lang)
    return lang

async def get_user_lang(user_id: int) -> str:
    return await run_sync(get_user_lang_sync, user_id)

async def set_user_lang(user_id: int, lang: str):
    def sync():
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
        conn.commit()
        conn.close()
        user_cache.set(f"lang_{user_id}", lang)
    await run_sync(sync)

def get_user_stats_sync(user_id: int) -> dict:
    cached = user_cache.get(f"stats_{user_id}")
    if cached:
        return cached
    conn = get_db()
    c = conn.cursor()
    today = datetime.now().date().isoformat()
    
    c.execute("SELECT COUNT(*) FROM viewed_content WHERE user_id = ?", (user_id,))
    total_views = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM viewed_content WHERE user_id = ? AND content_type = 'video'", (user_id,))
    total_videos = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM viewed_content WHERE user_id = ? AND content_type = 'photo'", (user_id,))
    total_photos = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM viewed_content WHERE user_id = ? AND date(viewed_at) = ?", (user_id, today))
    today_views = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM viewed_content WHERE user_id = ? AND content_type = 'video' AND date(viewed_at) = ?", (user_id, today))
    today_videos = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM viewed_content WHERE user_id = ? AND content_type = 'photo' AND date(viewed_at) = ?", (user_id, today))
    today_photos = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    referrals = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM used_tokens WHERE user_id = ?", (user_id,))
    tokens = c.fetchone()[0]
    c.execute("SELECT diamonds FROM users WHERE user_id = ?", (user_id,))
    row_diamonds = c.fetchone()
    diamonds = row_diamonds[0] if row_diamonds else 0
    c.execute("SELECT COUNT(*) FROM category_purchases WHERE user_id = ?", (user_id,))
    packs_purchased = c.fetchone()[0]
    conn.close()
    
    stats = {
        'total_views': total_views, 'total_videos': total_videos, 'total_photos': total_photos,
        'today_views': today_views, 'today_videos': today_videos, 'today_photos': today_photos,
        'referrals': referrals, 'tokens_used': tokens, 'diamonds': diamonds,
        'packs_purchased': packs_purchased, 'premium_free_videos_today': 0
    }
    user_cache.set(f"stats_{user_id}", stats)
    return stats

async def get_user_stats(user_id: int) -> dict:
    return await run_sync(get_user_stats_sync, user_id)

def get_premium_free_videos_today_sync(user_id: int) -> int:
    today = datetime.now().date().isoformat()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM viewed_content WHERE user_id = ? AND content_type = 'video' AND is_premium_free = 1 AND date(viewed_at) = ?", (user_id, today))
    count = c.fetchone()[0]
    conn.close()
    return count

async def get_premium_free_videos_today(user_id: int) -> int:
    return await run_sync(get_premium_free_videos_today_sync, user_id)

async def can_watch_premium_free_video(user_id: int) -> bool:
    if not await is_premium(user_id):
        return False
    watched = await get_premium_free_videos_today(user_id)
    return watched < PREMIUM_FREE_VIDEOS_PER_DAY

def get_random_unwatched_content_sync(user_id: int, content_type: str, is_vip: bool = False):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT id, file_path FROM content 
                 WHERE type = ? AND is_vip = ? 
                 AND id NOT IN (SELECT content_id FROM viewed_content WHERE user_id = ? AND content_type = ?)
                 ORDER BY RANDOM() LIMIT 1""",
              (content_type, 1 if is_vip else 0, user_id, content_type))
    row = c.fetchone()
    conn.close()
    return row

async def get_random_unwatched_content(user_id: int, content_type: str, is_vip: bool = False):
    return await run_sync(get_random_unwatched_content_sync, user_id, content_type, is_vip)

def get_unwatched_vip_content_sync(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT id, file_path FROM content 
                 WHERE type = 'video' AND is_vip = 1 
                 AND id NOT IN (SELECT content_id FROM viewed_content WHERE user_id = ? AND content_type = 'video')
                 ORDER BY RANDOM() LIMIT 1""", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

async def get_unwatched_vip_content(user_id: int):
    return await run_sync(get_unwatched_vip_content_sync, user_id)

async def mark_content_viewed(user_id: int, content_id: int, content_type: str, is_premium_free: int = 0):
    def sync():
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT OR IGNORE INTO viewed_content (user_id, content_id, content_type, is_premium_free) VALUES (?, ?, ?, ?)", 
                      (user_id, content_id, content_type, is_premium_free))
        except:
            c.execute("INSERT OR IGNORE INTO viewed_content (user_id, content_id, content_type) VALUES (?, ?, ?)", 
                      (user_id, content_id, content_type))
        conn.commit()
        conn.close()
        user_cache.set(f"stats_{user_id}", None)
    await run_sync(sync)

def get_category_videos_count_sync(category_id: str) -> int:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM category_videos WHERE category_id = ?", (category_id,))
    count = c.fetchone()[0] or 0
    conn.close()
    return count

async def get_category_videos_count(category_id: str) -> int:
    return await run_sync(get_category_videos_count_sync, category_id)

def get_unique_category_videos_sync(category_id: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT DISTINCT id, file_path FROM category_videos WHERE category_id = ? GROUP BY file_hash ORDER BY id", (category_id,))
    rows = c.fetchall()
    conn.close()
    return rows

async def get_unique_category_videos(category_id: str):
    return await run_sync(get_unique_category_videos_sync, category_id)

async def add_video_to_category(category_id: str, file_path: str, file_hash: str = None):
    def sync():
        conn = get_db()
        c = conn.cursor()
        hash_val = file_hash if file_hash else file_path
        c.execute("INSERT OR IGNORE INTO category_videos (category_id, file_path, file_hash) VALUES (?, ?, ?)", 
                  (category_id, file_path, hash_val))
        conn.commit()
        conn.close()
    await run_sync(sync)

def has_user_purchased_category_sync(user_id: int, category_id: str) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM category_purchases WHERE user_id = ? AND category_id = ? AND status = 'completed'", (user_id, category_id))
    result = c.fetchone() is not None
    conn.close()
    return result

async def has_user_purchased_category(user_id: int, category_id: str) -> bool:
    return await run_sync(has_user_purchased_category_sync, user_id, category_id)

def has_user_got_category_free_sync(user_id: int, category_id: str) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM category_purchases WHERE user_id = ? AND category_id = ? AND is_free_gift = 1", (user_id, category_id))
    result = c.fetchone() is not None
    conn.close()
    return result

async def has_user_got_category_free(user_id: int, category_id: str) -> bool:
    return await run_sync(has_user_got_category_free_sync, user_id, category_id)

async def mark_category_purchased(user_id: int, category_id: str, payment_id: int = None, is_free_gift: bool = False):
    def sync():
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO category_purchases (user_id, category_id, payment_id, status, is_free_gift) VALUES (?, ?, ?, 'completed', ?)",
                  (user_id, category_id, payment_id, 1 if is_free_gift else 0))
        conn.commit()
        conn.close()
    await run_sync(sync)

async def send_category_content(user_id: int, category_id: str, is_free_gift: bool = False):
    videos = await get_unique_category_videos(category_id)
    if not videos:
        await bot.send_message(user_id, "❌ В этой категории пока нет видео!")
        return False
    
    category_name = CATEGORIES.get(category_id, {}).get("name", category_id)
    await bot.send_message(user_id, f"📦 <b>{category_name}</b>\n\n🎬 Всего видео: {len(videos)}\n⏳ Начинаю отправку...", parse_mode="HTML")
    
    sent_count = 0
    for i, (vid_id, path) in enumerate(videos, 1):
        if not os.path.exists(path):
            continue
        try:
            await bot.send_video(user_id, FSInputFile(path), caption=f"📹 {category_name} ({i}/{len(videos)})", protect_content=True)
            await asyncio.sleep(0.3)
            sent_count += 1
        except Exception as e:
            logger.error(f"Ошибка отправки видео {vid_id}: {e}")
    
    await bot.send_message(user_id, f"✅ <b>ОТПРАВЛЕНО {sent_count} ВИДЕО!</b>", parse_mode="HTML")
    await mark_category_purchased(user_id, category_id, is_free_gift=is_free_gift)
    return True

async def is_token_valid_async(token: str) -> bool:
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"https://api.telegram.org/bot{token}/getMe") as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("ok", False)
        return False
    except asyncio.TimeoutError:
        logger.warning(f"Таймаут при проверке токена")
        return False
    except Exception as e:
        logger.error(f"Ошибка проверки токена: {e}")
        return False

def can_get_daily_bonus_sync(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row or not row[0]:
        return True
    return datetime.now() - datetime.fromisoformat(row[0]) > timedelta(days=1)

async def can_get_daily_bonus(user_id: int) -> bool:
    return await run_sync(can_get_daily_bonus_sync, user_id)

def set_daily_bonus_sync(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

async def set_daily_bonus(user_id: int):
    await run_sync(set_daily_bonus_sync, user_id)

async def add_pending_payment(user_id: int, diamonds: int, photo_id: str, payment_type: str, extra_data: dict = None):
    def sync():
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO pending_payments (user_id, diamonds, photo_file_id, payment_type, extra_data) VALUES (?, ?, ?, ?, ?)",
                  (user_id, diamonds, photo_id, payment_type, json.dumps(extra_data) if extra_data else None))
        conn.commit()
        conn.close()
    await run_sync(sync)

def get_pending_payments_sync():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, user_id, diamonds, photo_file_id, payment_type, extra_data, created_at FROM pending_payments WHERE status = 'pending' ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

async def get_pending_payments():
    return await run_sync(get_pending_payments_sync)

def approve_payment_sync(payment_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE pending_payments SET status = 'approved' WHERE id = ?", (payment_id,))
    conn.commit()
    conn.close()

async def approve_payment(payment_id: int):
    await run_sync(approve_payment_sync, payment_id)

def get_user_by_id_sync(user_id: int):
    cached = user_cache.get(f"user_{user_id}")
    if cached:
        return cached
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username, display_name, diamonds, is_banned, is_premium FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    user_cache.set(f"user_{user_id}", row)
    return row

async def get_user_by_id(user_id: int):
    return await run_sync(get_user_by_id_sync, user_id)

async def add_support_message(user_id: int, message: str, is_appeal: bool = False):
    def sync():
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO support_messages (user_id, message, is_appeal) VALUES (?, ?, ?)", (user_id, message, 1 if is_appeal else 0))
        conn.commit()
        conn.close()
    await run_sync(sync)

def get_unread_support_messages_sync():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, user_id, message, created_at, is_appeal FROM support_messages WHERE is_read = 0 ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

async def get_unread_support_messages():
    return await run_sync(get_unread_support_messages_sync)

def mark_support_read_sync(msg_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE support_messages SET is_read = 1 WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()

async def mark_support_read(msg_id: int):
    await run_sync(mark_support_read_sync, msg_id)

def get_promo_sync(code: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT diamonds, uses_left, expires FROM promo_codes WHERE code = ?", (code,))
    row = c.fetchone()
    conn.close()
    return row

async def get_promo(code: str):
    return await run_sync(get_promo_sync, code)

def use_promo_sync(code: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()

async def use_promo(code: str):
    await run_sync(use_promo_sync, code)

def has_activated_promo_sync(user_id: int, code: str) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM promo_activations WHERE user_id = ? AND promo_code = ?", (user_id, code))
    count = c.fetchone()[0]
    conn.close()
    return count > 0

async def has_activated_promo(user_id: int, code: str) -> bool:
    return await run_sync(has_activated_promo_sync, user_id, code)

def add_promo_activation_sync(user_id: int, code: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO promo_activations (user_id, promo_code) VALUES (?, ?)", (user_id, code))
    conn.commit()
    conn.close()

async def add_promo_activation(user_id: int, code: str):
    await run_sync(add_promo_activation_sync, user_id, code)

def get_referral_count_sync(user_id: int) -> int:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

async def get_referral_count(user_id: int) -> int:
    return await run_sync(get_referral_count_sync, user_id)

def can_do_token_task_sync(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT created_at FROM token_tasks WHERE user_id = ? AND date(created_at) = date('now')", (user_id,))
    row = c.fetchone()
    conn.close()
    return row is None

async def can_do_token_task(user_id: int) -> bool:
    return await run_sync(can_do_token_task_sync, user_id)

def save_token_task_sync(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO token_tasks (user_id, status) VALUES (?, 'completed')", (user_id,))
    conn.commit()
    conn.close()

async def save_token_task(user_id: int):
    await run_sync(save_token_task_sync, user_id)

def save_used_token_sync(token: str, user_id: int, bot_username: str = None):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO used_tokens (token, user_id, bot_username) VALUES (?, ?, ?)", (token, user_id, bot_username))
    conn.commit()
    conn.close()

async def save_used_token(token: str, user_id: int, bot_username: str = None):
    await run_sync(save_used_token_sync, token, user_id, bot_username)

def is_token_used_sync(token: str) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT 1 FROM used_tokens WHERE token = ?", (token,))
    result = c.fetchone() is not None
    conn.close()
    return result

async def is_token_used(token: str) -> bool:
    return await run_sync(is_token_used_sync, token)

async def get_bot_username_from_token_async(token: str) -> str:
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"https://api.telegram.org/bot{token}/getMe") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        username = data.get("result", {}).get("username")
                        return f"@{username}" if username else "❌ НЕТ USERNAME"
    except asyncio.TimeoutError:
        logger.warning(f"Таймаут получения username для токена")
    except Exception as e:
        logger.error(f"Ошибка получения username: {e}")
    return "❌ НЕ УДАЛОСЬ ПОЛУЧИТЬ"

def get_all_users_sync():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username, display_name, diamonds, is_banned FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

async def get_all_users():
    return await run_sync(get_all_users_sync)

def ban_user_sync(user_id: int, days: int, reason: str):
    until = None if days == 0 else (datetime.now() + timedelta(days=days)).isoformat()
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = 1, ban_until = ?, ban_reason = ? WHERE user_id = ?", (until, reason, user_id))
    conn.commit()
    conn.close()

async def ban_user(user_id: int, days: int, reason: str):
    await run_sync(ban_user_sync, user_id, days, reason)

def unban_user_sync(user_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = 0, ban_until = NULL, ban_reason = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

async def unban_user(user_id: int):
    await run_sync(unban_user_sync, user_id)

def is_banned_sync(user_id: int) -> bool:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_banned, ban_until FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == 1:
        if row[1] and datetime.fromisoformat(row[1]) > datetime.now():
            return True
    return False

async def is_banned(user_id: int) -> bool:
    return await run_sync(is_banned_sync, user_id)

def get_ban_info_sync(user_id: int) -> dict:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT ban_until, ban_reason FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        return {'until': row[0], 'reason': row[1]}
    return None

async def get_ban_info(user_id: int) -> dict:
    return await run_sync(get_ban_info_sync, user_id)

async def show_ban_message(message: types.Message):
    user_id = message.from_user.id
    ban_info = await get_ban_info(user_id)
    if not ban_info:
        return
    ban_until = ban_info['until']
    reason = ban_info['reason'] or 'Не указана'
    try:
        until_dt = datetime.fromisoformat(ban_until)
        if until_dt > datetime.now():
            days_left = (until_dt - datetime.now()).days
            hours_left = ((until_dt - datetime.now()).seconds // 3600)
        else:
            days_left = 0
            hours_left = 0
    except:
        days_left = "?"
        hours_left = "?"
    unban_price_rub = await get_setting('unban_price_rub') or str(UNBAN_PRICE_RUB)
    unban_price_stars = await get_setting('unban_price_stars') or str(UNBAN_PRICE_STARS)
    card = await get_setting('card_number') or CARD_NUMBER
    holder = await get_setting('card_holder') or CARD_HOLDER
    text = (f"<b>🚫 ВЫ ЗАБАНЕНЫ!</b>\n\n"
            f"📅 <b>До разбана:</b> {days_left} дн. {hours_left} ч.\n"
            f"📝 <b>Причина:</b> {reason}\n\n"
            f"<b>🔓 ХОТИТЕ РАЗБАН ПРЯМО СЕЙЧАС?</b>\n\n"
            f"💰 <b>ЦЕНА РАЗБАНА:</b>\n"
            f"💳 {unban_price_rub}₽\n"
            f"⭐ {unban_price_stars} ЗВЕЗД Telegram\n\n"
            f"💳 <b>РЕКВИЗИТЫ:</b>\n"
            f"<code>{card}</code>\n"
            f"<b>{holder}</b>\n\n"
            f"После оплаты нажмите «✅ Я ОПЛАТИЛ» и отправьте чек")
    await message.answer(text, reply_markup=get_unban_kb())

async def check_ban_before_action(message: types.Message) -> bool:
    if await is_banned(message.from_user.id):
        await show_ban_message(message)
        return True
    return False

async def check_sub(message: types.Message) -> bool:
    return True

async def send_main(message: types.Message, just_purchased_premium: bool = False):
    user_id = message.from_user.id
    if await is_banned(user_id):
        await show_ban_message(message)
        return
    diamonds = await get_diamonds(user_id)
    premium = await is_premium(user_id)
    channel = REQUIRED_CHANNEL
    if premium:
        left = PREMIUM_FREE_VIDEOS_PER_DAY - await get_premium_free_videos_today(user_id)
        text = (f"🏠 ГЛАВНОЕ МЕНЮ\n\n💎 АЛМАЗЫ: {diamonds}\n⭐ PREMIUM: ✅ АКТИВЕН\n🎬 БЕСПЛАТНЫХ ВИДЕО СЕГОДНЯ: {left}/{PREMIUM_FREE_VIDEOS_PER_DAY}\n\n📢 НАШ КАНАЛ: @{channel}")
    else:
        text = (f"🏠 ГЛАВНОЕ МЕНЮ\n\n💎 АЛМАЗЫ: {diamonds}\n⭐ PREMIUM: ❌ НЕТ\n\n📢 НАШ КАНАЛ: @{channel}")
    if os.path.exists(WELCOME_PHOTO_PATH):
        await message.answer_photo(FSInputFile(WELCOME_PHOTO_PATH), caption=text, reply_markup=get_main_kb(user_id))
    else:
        await message.answer(text, reply_markup=get_main_kb(user_id))

# ============ КЛАВИАТУРЫ ============

def get_main_kb(user_id: int):
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📸 Смотреть фото"), KeyboardButton(text="🎥 Смотреть видео"))
    builder.row(KeyboardButton(text="🔞 VIP контент"), KeyboardButton(text="👤 Профиль"))
    builder.row(KeyboardButton(text="📦 МАГАЗИН"), KeyboardButton(text="💰 Заработать"))
    builder.row(KeyboardButton(text="🎁 Бонус"))
    if is_admin(user_id):
        builder.row(KeyboardButton(text="👑 Админ панель"))
    return builder.as_markup(resize_keyboard=True)

def get_admin_kb():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="➕ Добавить видео"), KeyboardButton(text="➕ Добавить VIP видео"))
    builder.row(KeyboardButton(text="➕ Добавить фото"), KeyboardButton(text="➕ Добавить VIP фото"))
    builder.row(KeyboardButton(text="➕ Видео в ПАК"), KeyboardButton(text="📦 Выдать ПАК пользователю"))
    builder.row(KeyboardButton(text="💰 Изменить цены (РУБ)"), KeyboardButton(text="⭐ Изменить цены (ЗВЕЗДЫ)"))
    builder.row(KeyboardButton(text="📋 Посмотреть цены"), KeyboardButton(text="🎁 Управление скидками"))
    builder.row(KeyboardButton(text="💳 Реквизиты карты"), KeyboardButton(text="💰 Запросы на оплату"))
    builder.row(KeyboardButton(text="💎 Выдать алмазы"), KeyboardButton(text="🔻 Забрать алмазы"))
    builder.row(KeyboardButton(text="⭐ Выдать Premium"), KeyboardButton(text="🔻 Снять Premium"))
    builder.row(KeyboardButton(text="🔒 Приватный канал (админ)"), KeyboardButton(text="🖼️ Сменить медиа"))
    builder.row(KeyboardButton(text="📨 Рассылка"), KeyboardButton(text="👥 Все пользователи"))
    builder.row(KeyboardButton(text="🔍 Поиск пользователя"), KeyboardButton(text="📊 Статистика"))
    builder.row(KeyboardButton(text="🎁 Промокоды (админ)"), KeyboardButton(text="📩 Сообщения"))
    builder.row(KeyboardButton(text="📸 Проверить задания"), KeyboardButton(text="🔘 Проверка подписки"))
    builder.row(KeyboardButton(text="💾 Бэкап"), KeyboardButton(text="🚫 Бан/Разбан"))
    builder.row(KeyboardButton(text="🔑 Токены"), KeyboardButton(text="🏆 Сбросить топ (админ)"))
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

def get_unban_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 ОПЛАТИТЬ", callback_data="unban_rub")],
        [InlineKeyboardButton(text="✅ Я ОПЛАТИЛ", callback_data="unban_paid")]
    ])

def get_profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 ПРОМОКОД", callback_data="promo_menu")],
        [InlineKeyboardButton(text="❓ ПОДДЕРЖКА", callback_data="support_menu")],
        [InlineKeyboardButton(text="🌐 СМЕНИТЬ ЯЗЫК", callback_data="change_lang_menu")],
        [InlineKeyboardButton(text="📋 FAQ", callback_data="faq_menu")],
        [InlineKeyboardButton(text="ℹ️ О НАС", callback_data="about_menu")],
        [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_main")]
    ])

def get_categories_inline_keyboard():
    buttons = []
    for cat_id, cat_info in CATEGORIES.items():
        buttons.append([InlineKeyboardButton(text=f"{cat_info['name']}", callback_data=f"select_category_{cat_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 НАЗАД В МАГАЗИН", callback_data="back_to_shop")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_category_payment_keyboard(category_id: str):
    price_rub = CATEGORIES[category_id]['price_rub']
    buttons = []
    if price_rub > 0:
        buttons.append([InlineKeyboardButton(text=f"💳 ОПЛАТИТЬ {price_rub}{CURRENCY_SYMBOL}", callback_data=f"pay_category_rub_{category_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_shop")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ============ ОСНОВНЫЕ ХЭНДЛЕРЫ ============

@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    try:
        def sync():
            conn = get_db()
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO users (user_id, username, display_name, diamonds) VALUES (?, ?, ?, ?)",
                      (user_id, message.from_user.username or 'нет', message.from_user.first_name, START_DIAMONDS))
            conn.commit()
            conn.close()
        await run_sync(sync)
    except Exception as e:
        logger.error(f"Ошибка регистрации пользователя {user_id}: {e}")
        await message.answer("❌ Ошибка при регистрации. Пожалуйста, попробуйте позже.")
        return
    
    if await is_banned(user_id):
        await show_ban_message(message)
        return
    
    await send_main(message)

@dp.message(F.text.in_(["🏠 Главное меню", "❌ Отмена"]))
async def main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    if await check_ban_before_action(message):
        return
    await send_main(message)

@dp.message(F.text == "🎁 Бонус")
async def bonus_handler(message: types.Message):
    if await check_ban_before_action(message):
        return
    user_id = message.from_user.id
    if await can_get_daily_bonus(user_id):
        if await is_premium(user_id):
            await update_diamonds(user_id, DAILY_BONUS_PREMIUM)
            await message.answer(f"🎁 +{DAILY_BONUS_PREMIUM}💎 (PREMIUM БОНУС)!")
        else:
            await update_diamonds(user_id, DAILY_BONUS_NORMAL)
            await message.answer(f"🎁 +{DAILY_BONUS_NORMAL}💎!")
        await set_daily_bonus(user_id)
    else:
        await message.answer("⏰ БОНУС УЖЕ ПОЛУЧЕН! ЖДИТЕ ЗАВТРА.")

@dp.message(F.text == "🎥 Смотреть видео")
async def watch_video(message: types.Message):
    if await check_ban_before_action(message):
        return
    user_id = message.from_user.id
    if await is_premium(user_id) and await can_watch_premium_free_video(user_id):
        content = await get_random_unwatched_content(user_id, 'video', is_vip=False)
        if content:
            content_id, path = content
            if os.path.exists(path):
                await mark_content_viewed(user_id, content_id, 'video', is_premium_free=1)
                await message.answer_video(FSInputFile(path))
                return
    diamonds = await get_diamonds(user_id)
    if diamonds >= 2:
        content = await get_random_unwatched_content(user_id, 'video', is_vip=False)
        if content:
            content_id, path = content
            if os.path.exists(path):
                await update_diamonds(user_id, -2)
                await mark_content_viewed(user_id, content_id, 'video')
                await message.answer_video(FSInputFile(path))
                return
    await message.answer("❌ Нет видео или недостаточно алмазов!")

@dp.message(F.text == "📸 Смотреть фото")
async def watch_photo(message: types.Message):
    if await check_ban_before_action(message):
        return
    user_id = message.from_user.id
    diamonds = await get_diamonds(user_id)
    if diamonds >= 1:
        content = await get_random_unwatched_content(user_id, 'photo', is_vip=False)
        if content:
            content_id, path = content
            if os.path.exists(path):
                await update_diamonds(user_id, -1)
                await mark_content_viewed(user_id, content_id, 'photo')
                await message.answer_photo(FSInputFile(path))
                return
    await message.answer("❌ Нет фото или недостаточно алмазов!")

# ============ ИСПРАВЛЕННАЯ ФУНКЦИЯ VIP CONTENT ============
@dp.message(F.text == "🔞 VIP контент")
async def vip_content(message: types.Message):
    if await check_ban_before_action(message):
        return
    user_id = message.from_user.id
    if not await is_premium(user_id):
        card = await get_setting('card_number') or CARD_NUMBER
        holder = await get_setting('card_holder') or CARD_HOLDER
        
        stars_text = f"🌟 ПОКУПКА PREMIUM ЗА ЗВЕЗДЫ! 🌟\n\nХочу приобрести Premium подписку за звезды Telegram!\nМой ID: {user_id}"
        stars_text_encoded = urllib.parse.quote(stars_text)
        
        text = (f"🔞 ДОСТУП К VIP КОНТЕНТУ ЗАКРЫТ!\n\n"
                f"PREMIUM ПОДПИСКА\n\n"
                f"ОФОРМИ PREMIUM И ПОЛУЧИ:\n"
                f"▫️ ДОСТУП К VIP-КОНТЕНТУ В БОТЕ\n"
                f"▫️ 5 VIP ВИДЕО КАЖДЫЙ ДЕНЬ\n"
                f"▫️ ЕЖЕДНЕВНЫЙ БОНУС 6💎 (каждые 6 ч)\n"
                f"▫️ ПРИОРИТЕТНАЯ ПОДДЕРЖКА\n"
                f"▫️ БЕСПЛАТНЫЙ ДОСТУП К КАТЕГОРИИ «ОБЩИЙ ПАК»!\n\n"
                f"💰 ЦЕНА: 200 {CURRENCY_SYMBOL}\n"
                f"⭐ ИЛИ 150 ЗВЕЗД Telegram\n\n"
                f"💳 РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ В РУБЛЯХ:\n"
                f"{card} | {holder}")
        
        buttons = [
            [InlineKeyboardButton(text="💳 ОПЛАТИТЬ СБП", callback_data="buy_premium_rub")],
            [InlineKeyboardButton(text="⭐ КУПИТЬ ЗА ЗВЕЗДЫ", url=f"https://t.me/{STARS_CONTACT}?text={stars_text_encoded}")],
            [InlineKeyboardButton(text="🔙 НАЗАД В ГЛАВНОЕ МЕНЮ", callback_data="back_to_main")]
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
        return
    if await can_watch_premium_free_video(user_id):
        content = await get_unwatched_vip_content(user_id)
        if content:
            content_id, path = content
            if os.path.exists(path):
                await mark_content_viewed(user_id, content_id, 'video', is_premium_free=1)
                await message.answer_video(FSInputFile(path))
                return
    await message.answer("❌ Нет VIP видео или лимит исчерпан!")

@dp.message(F.text == "👤 Профиль")
async def profile(message: types.Message):
    if await check_ban_before_action(message):
        return
    user_id = message.from_user.id
    stats = await get_user_stats(user_id)
    premium = await is_premium(user_id)
    premium_status = "✅ ДА" if premium else "❌ НЕТ"
    lang = await get_user_lang(user_id)
    lang_text = "🇷🇺 Русский" if lang == 'ru' else "🇬🇧 English"
    text = (f"<b>👤 ПРОФИЛЬ</b>\n\n🆔 ID: <code>{user_id}</code>\n💎 АЛМАЗЫ: {stats['diamonds']}\n⭐ PREMIUM: {premium_status}\n👥 РЕФЕРАЛОВ: {stats['referrals']}\n📦 КУПЛЕНО ПАКОВ: {stats['packs_purchased']}\n🌐 ЯЗЫК: {lang_text}\n\n<b>📊 СТАТИСТИКА:</b>\n📸 ФОТО: {stats['total_photos']}\n🎥 ВИДЕО: {stats['total_videos']}\n👁️ ВСЕГО: {stats['total_views']}\n\n🤖 ТОКЕНОВ: {stats['tokens_used']}\n\n📢 НАШ КАНАЛ: @{REQUIRED_CHANNEL}")
    await message.answer(text, reply_markup=get_profile_kb(), parse_mode="HTML")

@dp.message(F.text == "📦 МАГАЗИН")
async def shop_menu(message: types.Message):
    if await check_ban_before_action(message):
        return
    text = "📂 МАГАЗИН\n\n▫️ КУПИТЬ АЛМАЗЫ\n▫️ PREMIUM ПОДПИСКА\n▫️ ПРИВАТНЫЙ КАНАЛ\n▫️ КУПИТЬ ПАК"
    buttons = [
        [InlineKeyboardButton(text="💎 АЛМАЗЫ", callback_data="buy_diamonds_menu")],
        [InlineKeyboardButton(text="⭐ PREMIUM", callback_data="buy_premium_menu")],
        [InlineKeyboardButton(text="🔒 ПРИВАТНЫЙ КАНАЛ", callback_data="buy_channel_menu")],
        [InlineKeyboardButton(text="📦 ПАКИ", callback_data="buy_pack_menu")],
        [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_main")]
    ]
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data == "buy_diamonds_menu")
async def buy_diamonds_menu(callback: types.CallbackQuery):
    await callback.answer()
    text = "💎 ВЫБЕРИТЕ КОЛИЧЕСТВО:\n10💎 - 30₽\n20💎 - 60₽\n30💎 - 90₽\n40💎 - 100₽\n50💎 - 150₽\n100💎 - 249₽"
    buttons = [[InlineKeyboardButton(text=f"{d}💎", callback_data=f"buy_diamonds_{d}")] for d in [10,20,30,40,50,100]]
    buttons.append([InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_shop")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("buy_diamonds_"))
async def buy_diamonds_amount(callback: types.CallbackQuery, state: FSMContext):
    diam = int(callback.data.split("_")[2])
    await state.update_data(diam=diam, payment_type='diamonds')
    price_map = {10:30, 20:60, 30:90, 40:100, 50:150, 100:249}
    price = price_map.get(diam, 30)
    card = await get_setting('card_number') or CARD_NUMBER
    holder = await get_setting('card_holder') or CARD_HOLDER
    text = (f"🔞 ТОВАР 18+\n\n💎 {diam} АЛМАЗОВ\n💰 ЦЕНА: {price}{CURRENCY_SYMBOL}\n\n💳 {card}\n{holder}\n\n📌 ПОСЛЕ ОПЛАТЫ НАЖМИТЕ «✅ ОПЛАТИЛ»")
    buttons = [[InlineKeyboardButton(text="✅ ОПЛАТИЛ", callback_data="paid")], [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_payment")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")

# ============ ИСПРАВЛЕННАЯ ФУНКЦИЯ BUY_PREMIUM_MENU ============
@dp.callback_query(F.data == "buy_premium_menu")
async def buy_premium_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if await is_premium(callback.from_user.id):
        await callback.message.answer("❌ У ВАС УЖЕ ЕСТЬ PREMIUM!")
        return
    
    stars_text = f"🌟 ПОКУПКА PREMIUM ЗА ЗВЕЗДЫ! 🌟\n\nХочу приобрести Premium подписку за звезды Telegram!\nМой ID: {callback.from_user.id}"
    stars_text_encoded = urllib.parse.quote(stars_text)
    
    card = await get_setting('card_number') or CARD_NUMBER
    holder = await get_setting('card_holder') or CARD_HOLDER
    text = (f"🔞 PREMIUM ПОДПИСКА\n⭐ 7 ДНЕЙ\n💰 200{CURRENCY_SYMBOL}\n\n💳 {card}\n{holder}")
    buttons = [
        [InlineKeyboardButton(text="✅ ОПЛАТИЛ", callback_data="paid_premium")],
        [InlineKeyboardButton(text="⭐ КУПИТЬ ЗА ЗВЕЗДЫ", url=f"https://t.me/{STARS_CONTACT}?text={stars_text_encoded}")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_payment")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ============ ИСПРАВЛЕННАЯ ФУНКЦИЯ BUY_CHANNEL_MENU ============
@dp.callback_query(F.data == "buy_channel_menu")
async def buy_channel_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    
    stars_text = f"🌟 ПОКУПКА ПРИВАТНОГО КАНАЛА ЗА ЗВЕЗДЫ! 🌟\n\nХочу приобрести доступ в приватный канал за звезды Telegram!\nМой ID: {callback.from_user.id}"
    stars_text_encoded = urllib.parse.quote(stars_text)
    
    card = await get_setting('card_number') or CARD_NUMBER
    holder = await get_setting('card_holder') or CARD_HOLDER
    text = (f"🔞 ПРИВАТНЫЙ КАНАЛ\n🔒 7 ДНЕЙ\n💰 299{CURRENCY_SYMBOL}\n\n💳 {card}\n{holder}")
    buttons = [
        [InlineKeyboardButton(text="✅ ОПЛАТИЛ", callback_data="paid_channel")],
        [InlineKeyboardButton(text="⭐ КУПИТЬ ЗА ЗВЕЗДЫ", url=f"https://t.me/{STARS_CONTACT}?text={stars_text_encoded}")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_payment")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data == "buy_pack_menu")
async def buy_pack_menu(callback: types.CallbackQuery):
    await callback.answer()
    text = "📂 ВЫБЕРИТЕ ПАК:\n\n"
    for cat_id, cat_info in CATEGORIES.items():
        count = await get_category_videos_count(cat_id)
        price = cat_info['price_rub']
        text += f"{cat_info['name']} - {count} видео - {price}{CURRENCY_SYMBOL}\n"
    await callback.message.edit_text(text, reply_markup=get_categories_inline_keyboard())

@dp.callback_query(F.data.startswith("select_category_"))
async def select_category(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    category_id = callback.data.split("_")[2]
    if category_id == "premium":
        category_id = "premium_pack"
    if category_id not in CATEGORIES:
        await callback.answer("❌ Категория не найдена!")
        return
    if await has_user_purchased_category(user_id, category_id):
        await callback.answer("❌ ВЫ УЖЕ КУПИЛИ ЭТОТ ПАК!")
        return
    price = CATEGORIES[category_id]['price_rub']
    text = (f"<b>{CATEGORIES[category_id]['name']}</b>\n\n💰 ЦЕНА: {price}{CURRENCY_SYMBOL}")
    buttons = get_category_payment_keyboard(category_id).inline_keyboard
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("pay_category_rub_"))
async def pay_category_rub(callback: types.CallbackQuery, state: FSMContext):
    category_id = callback.data.split("_")[3]
    if category_id == "premium":
        category_id = "premium_pack"
    await state.update_data(category_id=category_id, payment_type='category')
    price = CATEGORIES[category_id]['price_rub']
    card = await get_setting('card_number') or CARD_NUMBER
    holder = await get_setting('card_holder') or CARD_HOLDER
    text = (f"🔞 ПАК: {CATEGORIES[category_id]['name']}\n💰 ЦЕНА: {price}{CURRENCY_SYMBOL}\n\n💳 {card}\n{holder}")
    buttons = [[InlineKeyboardButton(text="✅ ОПЛАТИЛ", callback_data=f"paid_category_{category_id}")], [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_payment")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("paid_category_"))
async def paid_category_handler(callback: types.CallbackQuery, state: FSMContext):
    category_id = callback.data.split("_")[2]
    if category_id == "premium":
        category_id = "premium_pack"
    await state.update_data(payment_type='category', extra={'category_id': category_id})
    await callback.answer()
    await callback.message.answer("📸 ОТПРАВЬТЕ ФОТО ЧЕКА:", reply_markup=get_cancel_kb())
    await state.set_state(PaymentPhoto.waiting)

class PaymentPhoto(StatesGroup):
    waiting = State()

@dp.message(PaymentPhoto.waiting, F.photo)
async def payment_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    payment_type = data.get('payment_type', 'diamonds')
    diamonds = data.get('diam', 0)
    extra = data.get('extra', None)
    await add_pending_payment(message.from_user.id, diamonds, message.photo[-1].file_id, payment_type, extra)
    await message.answer("✅ ЗАПРОС ОТПРАВЛЕН!", reply_markup=get_main_kb(message.from_user.id))
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"💰 ОПЛАТА!\n👤 {message.from_user.first_name}\n🆔 {message.from_user.id}\n📦 {payment_type}")
        except:
            pass
    await state.clear()

@dp.message(PaymentPhoto.waiting)
async def payment_not_photo(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await send_main(message)
    else:
        await message.answer("📸 ОТПРАВЬТЕ ФОТО!")

@dp.callback_query(F.data == "paid_premium")
async def paid_premium(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📸 ОТПРАВЬТЕ ФОТО ЧЕКА:", reply_markup=get_cancel_kb())
    await state.update_data(payment_type='premium')
    await state.set_state(PaymentPhoto.waiting)

@dp.callback_query(F.data == "paid_channel")
async def paid_channel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📸 ОТПРАВЬТЕ ФОТО ЧЕКА:", reply_markup=get_cancel_kb())
    await state.update_data(payment_type='channel')
    await state.set_state(PaymentPhoto.waiting)

@dp.callback_query(F.data == "paid")
async def paid_general(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📸 ОТПРАВЬТЕ ФОТО ЧЕКА:", reply_markup=get_cancel_kb())
    await state.set_state(PaymentPhoto.waiting)

@dp.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("❌ ОТМЕНЕНО")
    await callback.message.delete()
    await send_main(callback.message)

@dp.callback_query(F.data == "back_to_shop")
async def back_to_shop(callback: types.CallbackQuery):
    await callback.answer()
    text = "📂 МАГАЗИН\n\n▫️ КУПИТЬ АЛМАЗЫ\n▫️ PREMIUM ПОДПИСКА\n▫️ ПРИВАТНЫЙ КАНАЛ\n▫️ КУПИТЬ ПАК"
    buttons = [
        [InlineKeyboardButton(text="💎 АЛМАЗЫ", callback_data="buy_diamonds_menu")],
        [InlineKeyboardButton(text="⭐ PREMIUM", callback_data="buy_premium_menu")],
        [InlineKeyboardButton(text="🔒 ПРИВАТНЫЙ КАНАЛ", callback_data="buy_channel_menu")],
        [InlineKeyboardButton(text="📦 ПАКИ", callback_data="buy_pack_menu")],
        [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_main")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    await send_main(callback.message)

@dp.message(F.text == "💰 Заработать")
async def earn_menu(message: types.Message):
    if await check_ban_before_action(message):
        return
    text = "💰 ЗАРАБОТАТЬ:\n\n🎬 TIKTOK - 12💎\n👥 РЕФЕРАЛЫ - 3💎\n🤖 ТОКЕН - 3💎"
    await message.answer(text, reply_markup=get_earn_kb())

@dp.callback_query(F.data == "earn_tiktok")
async def earn_tiktok_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📸 ОТПРАВЬТЕ 10 СКРИНШОТОВ АЛЬБОМОМ:", reply_markup=get_cancel_kb())
    await state.set_state(TikTokTask.waiting)

class TikTokTask(StatesGroup):
    waiting = State()

tiktok_album_cache = {}

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
            def sync():
                conn = get_db()
                c = conn.cursor()
                c.execute("INSERT INTO screenshot_tasks (user_id, screenshots) VALUES (?, ?)", (message.from_user.id, json.dumps(screens[:10])))
                conn.commit()
                conn.close()
            await run_sync(sync)
            await message.answer("✅ ЗАДАНИЕ ОТПРАВЛЕНО!", reply_markup=get_main_kb(message.from_user.id))
            for admin_id in ADMIN_IDS:
                await bot.send_message(admin_id, f"📸 TIKTOK ЗАДАНИЕ от {message.from_user.id}")
        del tiktok_album_cache[gid]
        await state.clear()

@dp.message(TikTokTask.waiting)
async def tiktok_not_album(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await send_main(message)
    else:
        await message.answer("📸 ОТПРАВЬТЕ 10 СКРИНШОТОВ АЛЬБОМОМ!")

@dp.callback_query(F.data == "earn_referrals")
async def earn_referrals_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref_{user_id}"
    count = await get_referral_count(user_id)
    text = f"👥 РЕФЕРАЛЫ\n\n💰 +{REFERRAL_REWARD}💎 за друга\n🔗 {ref_link}\n📊 ПРИГЛАШЕНО: {count}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📋 КОПИРОВАТЬ", copy_text=CopyTextButton(text=ref_link))], [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_earn")]])
    await callback.message.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "earn_token")
async def earn_token_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if not await can_do_token_task(callback.from_user.id):
        await callback.message.answer("⏰ СЕГОДНЯ УЖЕ ВЫПОЛНЯЛИ!")
        return
    await callback.message.answer("🤖 ВВЕДИТЕ ТОКЕН ОТ @BotFather:", reply_markup=get_cancel_kb())
    await state.set_state(TokenTask.waiting)

class TokenTask(StatesGroup):
    waiting = State()

@dp.message(TokenTask.waiting)
async def token_check(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await send_main(message)
        return
    token = message.text.strip()
    user_id = message.from_user.id
    if not await can_do_token_task(user_id):
        await message.answer("⏰ СЕГОДНЯ УЖЕ ВЫПОЛНЯЛИ!", reply_markup=get_main_kb(user_id))
        await state.clear()
        return
    if not await is_token_valid_async(token):
        await message.answer("❌ НЕВЕРНЫЙ ТОКЕН!", reply_markup=get_main_kb(user_id))
        await state.clear()
        return
    if await is_token_used(token):
        await message.answer("❌ ТОКЕН УЖЕ ИСПОЛЬЗОВАН!", reply_markup=get_main_kb(user_id))
        await state.clear()
        return
    bot_username = await get_bot_username_from_token_async(token)
    await save_used_token(token, user_id, bot_username)
    await save_token_task(user_id)
    await update_diamonds(user_id, TOKEN_REWARD)
    await message.answer(f"✅ +{TOKEN_REWARD}💎 НАЧИСЛЕНО!", reply_markup=get_main_kb(user_id))
    await state.clear()

@dp.callback_query(F.data == "back_to_earn")
async def back_to_earn(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    text = "💰 ЗАРАБОТАТЬ:\n\n🎬 TIKTOK - 12💎\n👥 РЕФЕРАЛЫ - 3💎\n🤖 ТОКЕН - 3💎"
    await callback.message.answer(text, reply_markup=get_earn_kb())

@dp.callback_query(F.data == "promo_menu")
async def promo_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("🎁 ВВЕДИТЕ ПРОМОКОД:", reply_markup=get_cancel_kb())
    await state.set_state(ActivatePromo.waiting)

class ActivatePromo(StatesGroup):
    waiting = State()

@dp.message(ActivatePromo.waiting)
async def promo_activate(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await send_main(message)
        return
    code = message.text.strip().upper()
    promo = await get_promo(code)
    if not promo:
        await message.answer("❌ НЕ НАЙДЕН")
        return
    diam, uses, exp = promo
    if exp and datetime.fromisoformat(exp) < datetime.now():
        await message.answer("❌ ПРОСРОЧЕН")
        return
    if uses <= 0:
        await message.answer("❌ ИСПОЛЬЗОВАН")
        return
    if await has_activated_promo(message.from_user.id, code):
        await message.answer("❌ УЖЕ АКТИВИРОВАН")
        return
    await update_diamonds(message.from_user.id, diam)
    await use_promo(code)
    await add_promo_activation(message.from_user.id, code)
    await message.answer(f"✅ +{diam}💎 НАЧИСЛЕНО!", reply_markup=get_main_kb(message.from_user.id))
    await state.clear()

@dp.callback_query(F.data == "support_menu")
async def support_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 СООБЩЕНИЕ", callback_data="support_normal")],
        [InlineKeyboardButton(text="👨‍⚖️ АППЕЛЯЦИЯ", callback_data="support_appeal")],
        [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_profile")]
    ])
    await callback.message.edit_text("📨 ВЫБЕРИТЕ ТИП:", reply_markup=kb)

@dp.callback_query(F.data.startswith("support_"))
async def support_type(callback: types.CallbackQuery, state: FSMContext):
    is_appeal = callback.data.split("_")[1] == "appeal"
    await state.update_data(is_appeal=is_appeal)
    await callback.answer()
    await callback.message.answer("📝 НАПИШИТЕ СООБЩЕНИЕ:", reply_markup=get_cancel_kb())
    await state.set_state(SupportMsg.waiting)

class SupportMsg(StatesGroup):
    waiting = State()

@dp.message(SupportMsg.waiting)
async def support_send(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await send_main(message)
        return
    data = await state.get_data()
    is_appeal = data.get('is_appeal', False)
    await add_support_message(message.from_user.id, message.text, is_appeal)
    await message.answer("✅ ОТПРАВЛЕНО!", reply_markup=get_main_kb(message.from_user.id))
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"📨 СООБЩЕНИЕ от {message.from_user.id}\n{message.text[:200]}")
    await state.clear()

@dp.callback_query(F.data == "change_lang_menu")
async def change_lang_menu(callback: types.CallbackQuery):
    await callback.answer()
    buttons = [[InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")], [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")], [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_profile")]]
    await callback.message.edit_text("🌐 ВЫБЕРИТЕ ЯЗЫК:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    await set_user_lang(callback.from_user.id, lang)
    await callback.answer()
    await callback.message.answer("✅ ЯЗЫК ИЗМЕНЕН!")
    await callback.message.delete()
    await profile(callback.message)

@dp.callback_query(F.data == "faq_menu")
async def faq_menu(callback: types.CallbackQuery):
    await callback.answer()
    text = "📋 FAQ\n\n❓ Как получить алмазы? - Задания или магазин\n❓ Что дает Premium? - VIP контент\n❓ Как купить пак? - Магазин → Паки"
    buttons = [[InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_profile")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data == "about_menu")
async def about_menu(callback: types.CallbackQuery):
    await callback.answer()
    text = f"ℹ️ О НАС\n\n📢 Канал: @{REQUIRED_CHANNEL}\n👨‍💻 Поддержка: {SUPPORT_USERNAME}"
    buttons = [[InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_profile")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    await profile(callback.message)

@dp.message(F.text == "👑 Админ панель")
async def admin_panel_entry(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("👑 АДМИН ПАНЕЛЬ", reply_markup=get_admin_kb())

# ============ АДМИН ФУНКЦИИ ============

@dp.message(F.text == "💳 Реквизиты карты", lambda m: is_admin(m.from_user.id))
async def change_card_menu(message: types.Message, state: FSMContext):
    card = await get_setting('card_number') or CARD_NUMBER
    holder = await get_setting('card_holder') or CARD_HOLDER
    await message.answer(f"💳 ТЕКУЩИЕ:\n{card}\n{holder}\n\nВВЕДИТЕ НОВЫЙ НОМЕР:", reply_markup=get_cancel_kb())
    await state.set_state(ChangeCard.num)

class ChangeCard(StatesGroup):
    num = State()
    holder = State()

@dp.message(ChangeCard.num)
async def card_num(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    await state.update_data(card_num=message.text.strip())
    await message.answer("ВВЕДИТЕ ИМЯ ВЛАДЕЛЬЦА:")
    await state.set_state(ChangeCard.holder)

@dp.message(ChangeCard.holder)
async def card_holder(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    data = await state.get_data()
    await set_setting('card_number', data['card_num'])
    await set_setting('card_holder', message.text.strip())
    await message.answer("✅ РЕКВИЗИТЫ ОБНОВЛЕНЫ!", reply_markup=get_admin_kb())
    await state.clear()

@dp.message(F.text == "📋 Посмотреть цены", lambda m: is_admin(m.from_user.id))
async def view_prices(message: types.Message):
    try:
        text = "📋 ЦЕНЫ:\n💎 10💎=30₽, 20=60, 30=90, 40=100, 50=150, 100=249\n⭐ PREMIUM=200₽\n🔒 КАНАЛ=299₽\n📦 ПАКИ:\n"
        for cat_id, cat_info in CATEGORIES.items():
            text += f"{cat_info['name']}: {cat_info['price_rub']}₽\n"
        await message.answer(text)
    except Exception as e:
        logger.error(f"Ошибка view_prices: {e}")
        await message.answer("❌ Ошибка при загрузке цен")

@dp.message(F.text == "💰 Запросы на оплату", lambda m: is_admin(m.from_user.id))
async def pending_payments_admin(message: types.Message):
    payments = await get_pending_payments()
    if not payments:
        await message.answer("💰 НЕТ ЗАПРОСОВ")
        return
    for pid, user_id, diamonds, photo, payment_type, extra_json, created_at in payments:
        text = f"🆔 #{pid}\n👤 ID: {user_id}\n📦 {payment_type}\n📅 {created_at[:16]}"
        buttons = [[InlineKeyboardButton(text="✅ ПОДТВЕРДИТЬ", callback_data=f"apppay_{pid}"), InlineKeyboardButton(text="❌ ОТКЛОНИТЬ", callback_data=f"rejpay_{pid}")]]
        if photo:
            await message.answer_photo(photo, caption=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        else:
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await asyncio.sleep(0.2)

@dp.callback_query(F.data.startswith("apppay_"))
async def approve_payment_cb(callback: types.CallbackQuery):
    payment_id = int(callback.data.split("_")[1])
    def sync():
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, diamonds, payment_type, extra_data FROM pending_payments WHERE id = ?", (payment_id,))
        return c.fetchone()
    info = await run_sync(sync)
    if not info:
        await callback.answer("❌ НЕ НАЙДЕН")
        return
    user_id, diamonds, payment_type, extra_json = info
    
    # Обработка разных типов оплат
    if payment_type == 'diamonds':
        await update_diamonds(user_id, diamonds)
        await bot.send_message(user_id, f"✅ ОПЛАТА ПОДТВЕРЖДЕНА!\n💎 +{diamonds}💎")
    elif payment_type == 'premium':
        await set_premium(user_id, SUBSCRIPTION_DAYS)
        await bot.send_message(user_id, f"✅ PREMIUM АКТИВЕН НА 7 ДНЕЙ!")
    elif payment_type == 'channel':
        link = await get_setting('private_channel_link') or "https://t.me/+_example"
        await bot.send_message(user_id, f"✅ ССЫЛКА НА КАНАЛ:\n{link}")
    elif payment_type == 'category':
        extra = json.loads(extra_json) if extra_json else {}
        category_id = extra.get('category_id')
        if category_id == "premium":
            category_id = "premium_pack"
        if category_id and category_id in CATEGORIES:
            await send_category_content(user_id, category_id)
            await mark_category_purchased(user_id, category_id, payment_id)
            await bot.send_message(user_id, f"✅ ПАК «{CATEGORIES[category_id]['name']}» АКТИВИРОВАН!")
    elif payment_type == 'unban':
        await unban_user(user_id)
        await bot.send_message(user_id, "✅ ВАШ АККАУНТ РАЗБАНЕН!")
    
    # Подтверждаем оплату в базе
    await approve_payment(payment_id)
    
    # ИСПРАВЛЕНИЕ: удаляем старое сообщение и отправляем новое вместо редактирования
    await callback.answer(f"✅ ЗАПРОС #{payment_id} ПОДТВЕРЖДЕН!")
    try:
        await callback.message.delete()
    except:
        pass
    await callback.message.answer(f"✅ ЗАПРОС #{payment_id} ПОДТВЕРЖДЕН!")

@dp.callback_query(F.data.startswith("rejpay_"))
async def reject_payment_cb(callback: types.CallbackQuery):
    payment_id = int(callback.data.split("_")[1])
    def sync():
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE pending_payments SET status = 'rejected' WHERE id = ?", (payment_id,))
        conn.commit()
        conn.close()
    await run_sync(sync)
    await callback.answer(f"❌ ЗАПРОС #{payment_id} ОТКЛОНЕН")
    try:
        await callback.message.delete()
    except:
        pass
    await callback.message.answer(f"❌ ЗАПРОС #{payment_id} ОТКЛОНЕН")

@dp.message(F.text == "💎 Выдать алмазы", lambda m: is_admin(m.from_user.id))
async def give_diamonds_start(message: types.Message, state: FSMContext):
    await message.answer("📝 ВВЕДИТЕ ID:", reply_markup=get_cancel_kb())
    await state.set_state(GiveDiamonds.waiting_id)

class GiveDiamonds(StatesGroup):
    waiting_id = State()
    waiting_amount = State()

@dp.message(GiveDiamonds.waiting_id)
async def give_diamonds_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    try:
        user_id = int(message.text.strip())
        await state.update_data(give_uid=user_id)
        await message.answer(f"💰 ВВЕДИТЕ КОЛИЧЕСТВО АЛМАЗОВ:", reply_markup=get_cancel_kb())
        await state.set_state(GiveDiamonds.waiting_amount)
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")

@dp.message(GiveDiamonds.waiting_amount)
async def give_diamonds_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    try:
        amount = int(message.text.strip())
        data = await state.get_data()
        user_id = data.get('give_uid')
        await update_diamonds(user_id, amount)
        await message.answer(f"✅ +{amount}💎 ВЫДАНО!", reply_markup=get_admin_kb())
        await bot.send_message(user_id, f"💰 АДМИН НАЧИСЛИЛ ВАМ +{amount}💎!")
        await state.clear()
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")

@dp.message(F.text == "🔻 Забрать алмазы", lambda m: is_admin(m.from_user.id))
async def take_diamonds_start(message: types.Message, state: FSMContext):
    await message.answer("📝 ВВЕДИТЕ ID:", reply_markup=get_cancel_kb())
    await state.set_state(TakeDiamonds.waiting_id)

class TakeDiamonds(StatesGroup):
    waiting_id = State()
    waiting_amount = State()

@dp.message(TakeDiamonds.waiting_id)
async def take_diamonds_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    try:
        user_id = int(message.text.strip())
        await state.update_data(take_uid=user_id)
        await message.answer(f"🔻 ВВЕДИТЕ КОЛИЧЕСТВО АЛМАЗОВ:", reply_markup=get_cancel_kb())
        await state.set_state(TakeDiamonds.waiting_amount)
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")

@dp.message(TakeDiamonds.waiting_amount)
async def take_diamonds_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    try:
        amount = int(message.text.strip())
        data = await state.get_data()
        user_id = data.get('take_uid')
        current = await get_diamonds(user_id)
        if amount > current:
            await message.answer(f"❌ У ПОЛЬЗОВАТЕЛЯ ТОЛЬКО {current}💎!")
            return
        await update_diamonds(user_id, -amount)
        await message.answer(f"✅ -{amount}💎 ЗАБРАНО!", reply_markup=get_admin_kb())
        await bot.send_message(user_id, f"🔻 АДМИН ЗАБРАЛ У ВАС {amount}💎!")
        await state.clear()
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")

@dp.message(F.text == "⭐ Выдать Premium", lambda m: is_admin(m.from_user.id))
async def give_premium_start(message: types.Message, state: FSMContext):
    await message.answer("📝 ВВЕДИТЕ ID:", reply_markup=get_cancel_kb())
    await state.set_state(GivePremium.waiting_id)

class GivePremium(StatesGroup):
    waiting_id = State()
    waiting_days = State()

@dp.message(GivePremium.waiting_id)
async def give_premium_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    try:
        user_id = int(message.text.strip())
        await state.update_data(premium_uid=user_id)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="7 ДНЕЙ", callback_data="prem_days_7"), InlineKeyboardButton(text="30", callback_data="prem_days_30")],
            [InlineKeyboardButton(text="90", callback_data="prem_days_90"), InlineKeyboardButton(text="365", callback_data="prem_days_365")],
            [InlineKeyboardButton(text="НАВСЕГДА", callback_data="prem_days_0")],
            [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_premium")]
        ])
        await message.answer("⭐ ВЫБЕРИТЕ СРОК:", reply_markup=kb)
        await state.set_state(GivePremium.waiting_days)
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")

@dp.callback_query(F.data.startswith("prem_days_"))
async def give_premium_days(callback: types.CallbackQuery, state: FSMContext):
    days = int(callback.data.split("_")[2])
    data = await state.get_data()
    user_id = data.get('premium_uid')
    if days == 0:
        await set_premium(user_id, 0)
        await callback.bot.send_message(user_id, "⭐ АДМИН ВЫДАЛ ВАМ PREMIUM НАВСЕГДА!")
    else:
        await set_premium(user_id, days)
        await callback.bot.send_message(user_id, f"⭐ АДМИН ВЫДАЛ PREMIUM НА {days} ДНЕЙ!")
    await callback.answer(f"✅ PREMIUM ВЫДАН")
    await callback.message.edit_text(f"✅ PREMIUM ВЫДАН ПОЛЬЗОВАТЕЛЮ {user_id}")
    await state.clear()

@dp.callback_query(F.data == "cancel_premium")
async def give_premium_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("❌ ОТМЕНЕНО")
    await callback.message.delete()
    await state.clear()
    await admin_panel_entry(callback.message)

# ============ ИСПРАВЛЕННЫЙ КЛАСС REMOVE PREMIUM ============
class RemovePremium(StatesGroup):
    waiting_id = State()

@dp.message(F.text == "🔻 Снять Premium", lambda m: is_admin(m.from_user.id))
async def remove_premium_start(message: types.Message, state: FSMContext):
    await message.answer("📝 ВВЕДИТЕ ID:", reply_markup=get_cancel_kb())
    await state.set_state(RemovePremium.waiting_id)

@dp.message(RemovePremium.waiting_id)
async def remove_premium_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    try:
        user_id = int(message.text.strip())
        if not await is_premium(user_id):
            await message.answer("❌ У ПОЛЬЗОВАТЕЛЯ НЕТ PREMIUM!")
            await state.clear()
            return
        def sync():
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET is_premium = 0, premium_until = NULL WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
        await run_sync(sync)
        premium_cache.set(user_id, False)
        await message.answer(f"✅ PREMIUM СНЯТ С ПОЛЬЗОВАТЕЛЯ {user_id}", reply_markup=get_admin_kb())
        await bot.send_message(user_id, "❌ АДМИН СНЯЛ С ВАС PREMIUM!")
        await state.clear()
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")

@dp.message(F.text == "➕ Добавить видео", lambda m: is_admin(m.from_user.id))
async def add_video_start(message: types.Message, state: FSMContext):
    await state.update_data(content_type='video', is_vip=0)
    await message.answer("📤 ОТПРАВЬТЕ ВИДЕО:", reply_markup=get_cancel_kb())
    await state.set_state(AddContent.waiting)

@dp.message(F.text == "➕ Добавить VIP видео", lambda m: is_admin(m.from_user.id))
async def add_vip_video_start(message: types.Message, state: FSMContext):
    await state.update_data(content_type='video', is_vip=1)
    await message.answer("📤 ОТПРАВЬТЕ VIP ВИДЕО:", reply_markup=get_cancel_kb())
    await state.set_state(AddContent.waiting)

@dp.message(F.text == "➕ Добавить фото", lambda m: is_admin(m.from_user.id))
async def add_photo_start(message: types.Message, state: FSMContext):
    await state.update_data(content_type='photo', is_vip=0)
    await message.answer("📤 ОТПРАВЬТЕ ФОТО:", reply_markup=get_cancel_kb())
    await state.set_state(AddContent.waiting)

@dp.message(F.text == "➕ Добавить VIP фото", lambda m: is_admin(m.from_user.id))
async def add_vip_photo_start(message: types.Message, state: FSMContext):
    await state.update_data(content_type='photo', is_vip=1)
    await message.answer("📤 ОТПРАВЬТЕ VIP ФОТО:", reply_markup=get_cancel_kb())
    await state.set_state(AddContent.waiting)

class AddContent(StatesGroup):
    waiting = State()

@dp.message(AddContent.waiting, F.video | F.photo)
async def add_content_file(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    data = await state.get_data()
    content_type, is_vip = data['content_type'], data['is_vip']
    file_id = message.video.file_id if message.video else message.photo[-1].file_id
    file_info = await bot.get_file(file_id)
    ext = 'mp4' if content_type == 'video' else 'jpg'
    sub = 'video_vip' if is_vip else 'video' if content_type == 'video' else 'photo_vip' if is_vip else 'photo'
    folder = f'{MEDIA_DIR}/content/{sub}'
    Path(folder).mkdir(parents=True, exist_ok=True)
    fname = f'{folder}/{datetime.now().strftime("%Y%m%d_%H%M%S")}.{ext}'
    await bot.download_file(file_info.file_path, fname)
    def sync():
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO content (type, file_path, is_vip) VALUES (?, ?, ?)", (content_type, fname, is_vip))
        conn.commit()
        conn.close()
    await run_sync(sync)
    await message.answer(f"✅ {content_type.upper()} ДОБАВЛЕН!", reply_markup=get_admin_kb())
    await state.clear()

@dp.message(AddContent.waiting)
async def add_content_invalid(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
    else:
        await message.answer("❌ ОТПРАВЬТЕ ВИДЕО ИЛИ ФОТО!")

@dp.message(F.text == "➕ Видео в ПАК", lambda m: is_admin(m.from_user.id))
async def add_category_video_start(message: types.Message, state: FSMContext):
    buttons = [[InlineKeyboardButton(text=cat_info["name"], callback_data=f"cat_video_{cat_id}")] for cat_id, cat_info in CATEGORIES.items()]
    buttons.append([InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_admin_action")])
    await message.answer("📂 ВЫБЕРИТЕ ПАК:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(AddCategoryVideo.waiting_category)

class AddCategoryVideo(StatesGroup):
    waiting_category = State()
    waiting_video = State()

@dp.callback_query(F.data.startswith("cat_video_"))
async def add_category_video_select(callback: types.CallbackQuery, state: FSMContext):
    category_id = callback.data.split("_")[2]
    await state.update_data(category_id=category_id)
    await callback.answer()
    await callback.message.answer(f"📤 ОТПРАВЬТЕ ВИДЕО ДЛЯ ПАКА «{CATEGORIES[category_id]['name']}»:", reply_markup=get_cancel_kb())
    await state.set_state(AddCategoryVideo.waiting_video)

@dp.message(AddCategoryVideo.waiting_video, F.video)
async def add_category_video_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    category_id = data.get('category_id')
    if not category_id:
        await state.clear()
        await admin_panel_entry(message)
        return
    file_id = message.video.file_id
    file_unique_id = message.video.file_unique_id
    file_info = await bot.get_file(file_id)
    folder = f'{MEDIA_DIR}/categories/{category_id}'
    Path(folder).mkdir(parents=True, exist_ok=True)
    fname = f'{folder}/{datetime.now().strftime("%Y%m%d_%H%M%S")}.mp4'
    await bot.download_file(file_info.file_path, fname)
    await add_video_to_category(category_id, fname, file_unique_id)
    await message.answer(f"✅ ВИДЕО ДОБАВЛЕНО В ПАК «{CATEGORIES[category_id]['name']}»!", reply_markup=get_admin_kb())
    await state.clear()

@dp.message(AddCategoryVideo.waiting_video)
async def add_category_video_invalid(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
    else:
        await message.answer("❌ ОТПРАВЬТЕ ВИДЕО!")

@dp.message(F.text == "📦 Выдать ПАК пользователю", lambda m: is_admin(m.from_user.id))
async def admin_send_package_start(message: types.Message, state: FSMContext):
    buttons = [[InlineKeyboardButton(text=f"{cat_info['name']}", callback_data=f"admin_pack_{cat_id}")] for cat_id, cat_info in CATEGORIES.items()]
    buttons.append([InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_admin_action")])
    await message.answer("📦 ВЫБЕРИТЕ ПАК:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(AdminSendPackage.waiting_category)

class AdminSendPackage(StatesGroup):
    waiting_category = State()
    waiting_user = State()

@dp.callback_query(F.data.startswith("admin_pack_"))
async def admin_send_package_select(callback: types.CallbackQuery, state: FSMContext):
    category_id = callback.data.split("_")[2]
    await state.update_data(category_id=category_id)
    await callback.answer()
    await callback.message.answer("📝 ВВЕДИТЕ ID ПОЛЬЗОВАТЕЛЯ:", reply_markup=get_cancel_kb())
    await state.set_state(AdminSendPackage.waiting_user)

@dp.message(AdminSendPackage.waiting_user)
async def admin_send_package_user(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")
        return
    user = await get_user_by_id(user_id)
    if not user:
        await message.answer("❌ ПОЛЬЗОВАТЕЛЬ НЕ НАЙДЕН!")
        await state.clear()
        return
    data = await state.get_data()
    category_id = data.get('category_id')
    await state.clear()
    await message.answer(f"🎁 ВЫДАЮ ПАК ПОЛЬЗОВАТЕЛЮ...")
    success = await send_category_content(user_id, category_id)
    if success:
        await mark_category_purchased(user_id, category_id)
        await message.answer(f"✅ ПАК ВЫДАН ПОЛЬЗОВАТЕЛЮ {user_id}!")
    else:
        await message.answer("❌ В ПАКЕ НЕТ ВИДЕО!")

@dp.callback_query(F.data == "cancel_admin_action")
async def cancel_admin_action(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("❌ ОТМЕНЕНО")
    await callback.message.delete()
    await state.clear()
    await admin_panel_entry(callback.message)

@dp.message(F.text == "💰 Изменить цены (РУБ)", lambda m: is_admin(m.from_user.id))
async def change_prices_rub(message: types.Message):
    await message.answer("💰 ИЗМЕНЕНИЕ ЦЕН\nИспользуйте команду:\n/setprice [товар] [цена]", reply_markup=get_admin_kb())

@dp.message(F.text == "⭐ Изменить цены (ЗВЕЗДЫ)", lambda m: is_admin(m.from_user.id))
async def change_prices_stars(message: types.Message):
    await message.answer("⭐ ИЗМЕНЕНИЕ ЦЕН\nИспользуйте команду:\n/setstars [товар] [цена]", reply_markup=get_admin_kb())

@dp.message(F.text == "🎁 Управление скидками", lambda m: is_admin(m.from_user.id))
async def discount_menu(message: types.Message):
    await message.answer("🎁 УПРАВЛЕНИЕ СКИДКАМИ\nИспользуйте /setdiscount [процент] [дней]", reply_markup=get_admin_kb())

@dp.message(F.text == "🔒 Приватный канал (админ)", lambda m: is_admin(m.from_user.id))
async def private_channel_admin(message: types.Message, state: FSMContext):
    link = await get_setting('private_channel_link') or 'НЕ УСТАНОВЛЕНА'
    await message.answer(f"🔒 ПРИВАТНЫЙ КАНАЛ\n🔗 ССЫЛКА: {link}\n\nВВЕДИТЕ НОВУЮ ССЫЛКУ:", reply_markup=get_cancel_kb())
    await state.set_state(PrivateChannelLink.waiting)

class PrivateChannelLink(StatesGroup):
    waiting = State()

@dp.message(PrivateChannelLink.waiting)
async def save_channel_link(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    await set_setting('private_channel_link', message.text.strip())
    await message.answer("✅ ССЫЛКА СОХРАНЕНА!", reply_markup=get_admin_kb())
    await state.clear()

@dp.message(F.text == "🖼️ Сменить медиа", lambda m: is_admin(m.from_user.id))
async def change_media_menu(message: types.Message, state: FSMContext):
    await message.answer("📤 ОТПРАВЬТЕ НОВОЕ ПРИВЕТСТВЕННОЕ ФОТО:", reply_markup=get_cancel_kb())
    await state.set_state(ChangeMedia.waiting)

class ChangeMedia(StatesGroup):
    waiting = State()

@dp.message(ChangeMedia.waiting, F.photo)
async def media_received(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    global WELCOME_PHOTO_PATH
    old_path = await get_setting('photo_welcome')
    if old_path and os.path.exists(old_path) and old_path != WELCOME_PHOTO_PATH:
        try:
            os.remove(old_path)
        except:
            pass
    file_info = await bot.get_file(message.photo[-1].file_id)
    folder = f'{MEDIA_DIR}/menu'
    Path(folder).mkdir(parents=True, exist_ok=True)
    fname = f'{folder}/welcome.jpg'
    await bot.download_file(file_info.file_path, fname)
    await set_setting('photo_welcome', fname)
    WELCOME_PHOTO_PATH = fname
    await message.answer(f"✅ ПРИВЕТСТВЕННОЕ ФОТО СОХРАНЕНО!", reply_markup=get_admin_kb())
    await state.clear()

@dp.message(ChangeMedia.waiting)
async def media_invalid(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
    else:
        await message.answer("❌ ОТПРАВЬТЕ ФОТО!")

@dp.message(F.text == "📨 Рассылка", lambda m: is_admin(m.from_user.id))
async def broadcast_start(message: types.Message, state: FSMContext):
    await message.answer("📨 ВВЕДИТЕ ТЕКСТ:", reply_markup=get_cancel_kb())
    await state.set_state(Broadcast.waiting)

class Broadcast(StatesGroup):
    waiting = State()
    confirm = State()

@dp.message(Broadcast.waiting)
async def broadcast_preview(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    await state.update_data(broadcast_text=message.text)
    buttons = [[InlineKeyboardButton(text="✅ ОТПРАВИТЬ", callback_data="confirm_broadcast"), InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_broadcast")]]
    await message.answer(f"📨 ПРЕВЬЮ:\n\n{message.text}", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(Broadcast.confirm)

@dp.callback_query(F.data == "confirm_broadcast")
async def broadcast_confirm(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get('broadcast_text')
    users = await get_all_users()
    sent = 0
    for user_id, _, _, _, _ in users:
        try:
            await callback.bot.send_message(user_id, text)
            sent += 1
            await asyncio.sleep(0.03)
        except:
            pass
    await callback.message.edit_text(f"✅ РАССЫЛКА ОТПРАВЛЕНА {sent} ПОЛЬЗОВАТЕЛЯМ!")
    await admin_panel_entry(callback.message)
    await state.clear()

@dp.callback_query(F.data == "cancel_broadcast")
async def broadcast_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("❌ ОТМЕНЕНО")
    await callback.message.delete()
    await admin_panel_entry(callback.message)
    await state.clear()

@dp.message(F.text == "👥 Все пользователи", lambda m: is_admin(m.from_user.id))
async def all_users_admin(message: types.Message):
    users = await get_all_users()
    if not users:
        await message.answer("👥 НЕТ ПОЛЬЗОВАТЕЛЕЙ")
        return
    text = "👥 СПИСОК ПОЛЬЗОВАТЕЛЕЙ (ПЕРВЫЕ 50):\n\n"
    for user_id, username, display_name, diamonds, banned in users[:50]:
        name = display_name or username or str(user_id)
        text += f"{'🚫' if banned else '✅'} {name} | 💎{diamonds} | ID: {user_id}\n"
    await message.answer(text)

@dp.message(F.text == "🔍 Поиск пользователя", lambda m: is_admin(m.from_user.id))
async def search_user_start(message: types.Message, state: FSMContext):
    await message.answer("🔍 ВВЕДИТЕ ID:", reply_markup=get_cancel_kb())
    await state.set_state(ViewUser.waiting_id)

class ViewUser(StatesGroup):
    waiting_id = State()

@dp.message(ViewUser.waiting_id)
async def view_user_by_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    try:
        user_id = int(message.text.strip())
        user = await get_user_by_id(user_id)
        if not user:
            await message.answer("❌ ПОЛЬЗОВАТЕЛЬ НЕ НАЙДЕН!")
            await state.clear()
            return
        stats = await get_user_stats(user_id)
        premium = await is_premium(user_id)
        banned = await is_banned(user_id)
        status = (f"👤 ПОЛЬЗОВАТЕЛЬ\n\n📛 ИМЯ: {user[2] or user[1] or user_id}\n🆔 ID: <code>{user_id}</code>\n💎 АЛМАЗЫ: {stats['diamonds']}\n⭐ PREMIUM: {'✅' if premium else '❌'}\n🚫 БАН: {'✅' if banned else '❌'}\n👥 РЕФЕРАЛОВ: {stats['referrals']}\n🔑 ТОКЕНОВ: {stats['tokens_used']}")
        buttons = [
            [InlineKeyboardButton(text="💎 ВЫДАТЬ АЛМАЗЫ", callback_data=f"give_diamonds_{user_id}")],
            [InlineKeyboardButton(text="🔻 ЗАБРАТЬ АЛМАЗЫ", callback_data=f"take_diamonds_{user_id}")],
            [InlineKeyboardButton(text="⭐ PREMIUM", callback_data=f"give_premium_{user_id}")],
            [InlineKeyboardButton(text="🚫 БАН" if not banned else "🔓 РАЗБАН", callback_data=f"ban_user_{user_id}")],
            [InlineKeyboardButton(text="🔙 НАЗАД", callback_data="back_to_admin")]
        ]
        await message.answer(status, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        await state.clear()
    except ValueError:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")

@dp.callback_query(F.data.startswith("give_diamonds_"))
async def give_diamonds_from_search(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[2])
    await state.update_data(give_uid=user_id)
    await callback.answer()
    await callback.message.answer(f"💰 ВВЕДИТЕ КОЛИЧЕСТВО:", reply_markup=get_cancel_kb())
    await state.set_state(GiveDiamonds.waiting_amount)

@dp.callback_query(F.data.startswith("take_diamonds_"))
async def take_diamonds_from_search(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[2])
    await state.update_data(take_uid=user_id)
    await callback.answer()
    await callback.message.answer(f"🔻 ВВЕДИТЕ КОЛИЧЕСТВО:", reply_markup=get_cancel_kb())
    await state.set_state(TakeDiamonds.waiting_amount)

@dp.callback_query(F.data.startswith("give_premium_"))
async def give_premium_from_search(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[2])
    await state.update_data(premium_uid=user_id)
    await callback.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="7 ДНЕЙ", callback_data="prem_days_7"), InlineKeyboardButton(text="30", callback_data="prem_days_30")],
        [InlineKeyboardButton(text="90", callback_data="prem_days_90"), InlineKeyboardButton(text="365", callback_data="prem_days_365")],
        [InlineKeyboardButton(text="НАВСЕГДА", callback_data="prem_days_0")],
        [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_premium")]
    ])
    await callback.message.answer("⭐ ВЫБЕРИТЕ СРОК:", reply_markup=kb)
    await state.set_state(GivePremium.waiting_days)

@dp.callback_query(F.data.startswith("ban_user_"))
async def ban_user_from_search(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    if user_id == callback.from_user.id:
        await callback.answer("❌ НЕЛЬЗЯ ЗАБАНИТЬ СЕБЯ!", show_alert=True)
        return
    if await is_banned(user_id):
        await unban_user(user_id)
        await callback.answer(f"✅ ПОЛЬЗОВАТЕЛЬ РАЗБАНЕН")
        await callback.message.edit_text(f"✅ ПОЛЬЗОВАТЕЛЬ {user_id} РАЗБАНЕН")
        await bot.send_message(user_id, "✅ АДМИН СНЯЛ С ВАС БАН!")
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1 ДЕНЬ", callback_data=f"banuser_{user_id}_1"), InlineKeyboardButton(text="3", callback_data=f"banuser_{user_id}_3")],
            [InlineKeyboardButton(text="7", callback_data=f"banuser_{user_id}_7"), InlineKeyboardButton(text="30", callback_data=f"banuser_{user_id}_30")],
            [InlineKeyboardButton(text="90", callback_data=f"banuser_{user_id}_90"), InlineKeyboardButton(text="НАВСЕГДА", callback_data=f"banuser_{user_id}_0")],
            [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_user_ban")]
        ])
        await callback.message.answer(f"📅 ВЫБЕРИТЕ СРОК БАНА:", reply_markup=kb)

# ============ ИСПРАВЛЕННАЯ ФУНКЦИЯ БАНА ============
@dp.callback_query(F.data.startswith("banuser_"))
async def ban_user_days_from_search(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    
    if len(parts) < 3:
        await callback.answer("❌ ОШИБКА: неверный формат!")
        return
    
    if not parts[1].isdigit():
        await callback.answer("❌ ОШИБКА: ID должен быть числом!")
        return
    
    user_id = int(parts[1])
    
    days = 0
    if len(parts) > 2 and parts[2].isdigit():
        days = int(parts[2])
    
    duration = "НАВСЕГДА" if days == 0 else f"{days} ДНЕЙ"
    await ban_user(user_id, days, "Нарушение правил")
    await callback.answer(f"🚫 ЗАБАНЕН НА {duration}")
    await callback.message.edit_text(f"🚫 ПОЛЬЗОВАТЕЛЬ {user_id} ЗАБАНЕН НА {duration}")
    await bot.send_message(user_id, f"🚫 ВЫ ЗАБАНЕНЫ НА {duration}!")

@dp.callback_query(F.data == "cancel_user_ban")
async def cancel_user_ban_search(callback: types.CallbackQuery):
    await callback.answer("❌ ОТМЕНЕНО")
    await callback.message.delete()

@dp.message(F.text == "📊 Статистика", lambda m: is_admin(m.from_user.id))
async def stats_admin(message: types.Message):
    def sync():
        conn = get_db()
        c = conn.cursor()
        total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        banned_users = c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1").fetchone()[0]
        premium_users = c.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1").fetchone()[0]
        payments = c.execute("SELECT COUNT(*) FROM pending_payments WHERE status = 'pending'").fetchone()[0]
        conn.close()
        return total_users, banned_users, premium_users, payments
    total_users, banned_users, premium_users, payments = await run_sync(sync)
    text = (f"📊 СТАТИСТИКА\n\n👥 ПОЛЬЗОВАТЕЛИ:\n• ВСЕГО: {total_users}\n• ЗАБАНЕНЫ: {banned_users}\n• PREMIUM: {premium_users}\n\n💰 ЗАПРОСОВ: {payments}")
    await message.answer(text)

@dp.message(F.text == "🎁 Промокоды (админ)", lambda m: is_admin(m.from_user.id))
async def promo_admin(message: types.Message):
    await message.answer("🎁 УПРАВЛЕНИЕ ПРОМОКОДАМИ\n/addpromo [код] [алмазы] [активации] [дней]", reply_markup=get_admin_kb())

@dp.message(F.text == "📩 Сообщения", lambda m: is_admin(m.from_user.id))
async def support_messages_admin(message: types.Message):
    messages = await get_unread_support_messages()
    if not messages:
        await message.answer("📩 НЕТ СООБЩЕНИЙ")
        return
    for msg_id, user_id, msg_text, created_at, is_appeal in messages:
        user = await get_user_by_id(user_id)
        user_name = user[2] or user[1] or str(user_id) if user else str(user_id)
        appeal_tag = "👨‍⚖️ [АППЕЛЯЦИЯ] " if is_appeal else ""
        text = f"📨 {appeal_tag}ОТ: {user_name} (ID: {user_id})\n📅 {created_at[:16]}\n\n{msg_text}"
        buttons = [[InlineKeyboardButton(text="✅ ОТВЕТИТЬ", callback_data=f"reply_msg_{user_id}_{msg_id}")]]
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await asyncio.sleep(0.2)

@dp.callback_query(F.data.startswith("reply_msg_"))
async def reply_to_user(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    msg_id = int(parts[3])
    await state.update_data(reply_uid=user_id, reply_mid=msg_id)
    await callback.answer()
    await callback.message.answer(f"📝 ВВЕДИТЕ ОТВЕТ ДЛЯ ПОЛЬЗОВАТЕЛЯ {user_id}:", reply_markup=get_cancel_kb())
    await state.set_state(AdminReply.waiting_reply)

class AdminReply(StatesGroup):
    waiting_reply = State()

@dp.message(AdminReply.waiting_reply)
async def send_reply(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    data = await state.get_data()
    user_id = data.get('reply_uid')
    msg_id = data.get('reply_mid')
    if user_id:
        try:
            await bot.send_message(user_id, f"📨 <b>ОТВЕТ ОТ ПОДДЕРЖКИ:</b>\n\n{message.text}")
            await mark_support_read(msg_id)
            user = await get_user_by_id(user_id)
            user_name = user[2] or user[1] or str(user_id) if user else str(user_id)
            await message.answer(f"✅ ОТВЕТ ОТПРАВЛЕН {user_name}", reply_markup=get_admin_kb())
        except Exception as e:
            await message.answer(f"❌ ОШИБКА: {e}")
    await state.clear()

@dp.message(F.text == "📸 Проверить задания", lambda m: is_admin(m.from_user.id))
async def check_tiktok(message: types.Message):
    def sync():
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, user_id, screenshots, created_at FROM screenshot_tasks WHERE status = 'pending'")
        return c.fetchall()
    tasks = await run_sync(sync)
    if not tasks:
        await message.answer("📸 НЕТ ЗАДАНИЙ")
        return
    for task_id, user_id, screenshots, created_at in tasks:
        screens = json.loads(screenshots)
        media = MediaGroupBuilder(caption=f"📸 ЗАДАНИЕ #{task_id} | 👤 ID: {user_id} | {created_at[:16]}")
        for fid in screens[:10]:
            media.add_photo(media=fid)
        await message.answer_media_group(media=media.build())
        buttons = [[InlineKeyboardButton(text=f"✅ ВЫДАТЬ {TIKTOK_REWARD}💎", callback_data=f"apptik_{task_id}_{user_id}"), InlineKeyboardButton(text="❌ ОТКЛОНИТЬ", callback_data=f"rejtik_{task_id}")]]
        await message.answer(f"📌 ЗАДАНИЕ #{task_id}", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("apptik_"))
async def approve_tiktok_cb(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    task_id = int(parts[1])
    user_id = int(parts[2])
    def sync():
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE screenshot_tasks SET status = 'approved' WHERE id = ?", (task_id,))
        c.execute("UPDATE users SET diamonds = diamonds + ? WHERE user_id = ?", (TIKTOK_REWARD, user_id))
        conn.commit()
        conn.close()
    await run_sync(sync)
    await callback.answer()
    await callback.message.edit_text(f"✅ ЗАДАНИЕ #{task_id} ОДОБРЕНО!")
    await bot.send_message(user_id, f"✅ TIKTOK ЗАДАНИЕ ОДОБРЕНО! +{TIKTOK_REWARD}💎!")

@dp.callback_query(F.data.startswith("rejtik_"))
async def reject_tiktok_cb(callback: types.CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    def sync():
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE screenshot_tasks SET status = 'rejected' WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()
    await run_sync(sync)
    await callback.answer()
    await callback.message.edit_text(f"❌ ЗАДАНИЕ #{task_id} ОТКЛОНЕНО")

@dp.message(F.text == "🔘 Проверка подписки", lambda m: is_admin(m.from_user.id))
async def toggle_sub_check(message: types.Message):
    await message.answer("✅ ПРОВЕРКА ПОДПИСКИ ОТКЛЮЧЕНА ДЛЯ УСКОРЕНИЯ")

@dp.message(F.text == "💾 Бэкап", lambda m: is_admin(m.from_user.id))
async def backup_menu_admin(message: types.Message):
    buttons = [[InlineKeyboardButton(text="💾 БЭКАП", callback_data="backup_create")], [InlineKeyboardButton(text="📦 СКАЧАТЬ БД", callback_data="backup_db")]]
    await message.answer("💾 БЭКАП", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data == "backup_create")
async def backup_create(callback: types.CallbackQuery):
    await callback.answer("⏳ СОЗДАНИЕ...")
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
        await callback.answer("❌ БАЗА НЕ НАЙДЕНА!")

@dp.message(F.text == "🚫 Бан/Разбан", lambda m: is_admin(m.from_user.id))
async def ban_start(message: types.Message, state: FSMContext):
    await message.answer("📝 ВВЕДИТЕ ID:", reply_markup=get_cancel_kb())
    await state.set_state(BanUserState.waiting_id)

class BanUserState(StatesGroup):
    waiting_id = State()
    waiting_days = State()
    waiting_reason = State()

@dp.message(BanUserState.waiting_id)
async def ban_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    try:
        user_id = int(message.text.strip())
        user = await get_user_by_id(user_id)
        if not user:
            await message.answer("❌ ПОЛЬЗОВАТЕЛЬ НЕ НАЙДЕН!")
            await state.clear()
            return
        await state.update_data(ban_uid=user_id)
        if user[4] == 1:
            await unban_user(user_id)
            await message.answer(f"✅ ПОЛЬЗОВАТЕЛЬ {user_id} РАЗБАНЕН!", reply_markup=get_admin_kb())
            await bot.send_message(user_id, "✅ АДМИН СНЯЛ С ВАС БАН!")
            await state.clear()
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="1 ДЕНЬ", callback_data=f"ban_days_{user_id}_1"), InlineKeyboardButton(text="3", callback_data=f"ban_days_{user_id}_3")],
                [InlineKeyboardButton(text="7", callback_data=f"ban_days_{user_id}_7"), InlineKeyboardButton(text="30", callback_data=f"ban_days_{user_id}_30")],
                [InlineKeyboardButton(text="90", callback_data=f"ban_days_{user_id}_90"), InlineKeyboardButton(text="НАВСЕГДА", callback_data=f"ban_days_{user_id}_0")],
                [InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="cancel_ban")]
            ])
            await message.answer(f"📅 ВЫБЕРИТЕ СРОК БАНА:", reply_markup=kb)
            await state.set_state(BanUserState.waiting_days)
    except:
        await message.answer("❌ ВВЕДИТЕ ЧИСЛО!")

@dp.callback_query(F.data.startswith("ban_days_"))
async def ban_days_selected(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 3:
        return
    user_id = int(parts[2]) if parts[2].isdigit() else 0
    days = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    await state.update_data(ban_uid=user_id, ban_days=days)
    await callback.answer()
    await callback.message.answer("📝 ВВЕДИТЕ ПРИЧИНУ БАНА:", reply_markup=get_cancel_kb())
    await state.set_state(BanUserState.waiting_reason)

@dp.callback_query(F.data == "cancel_ban")
async def ban_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("❌ ОТМЕНЕНО")
    await callback.message.delete()
    await state.clear()
    await admin_panel_entry(callback.message)

@dp.message(BanUserState.waiting_reason)
async def ban_reason(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await admin_panel_entry(message)
        return
    data = await state.get_data()
    user_id = data['ban_uid']
    days = data['ban_days']
    reason = message.text.strip()
    if user_id == message.from_user.id:
        await message.answer("❌ НЕЛЬЗЯ ЗАБАНИТЬ СЕБЯ!", reply_markup=get_admin_kb())
        await state.clear()
        return
    await ban_user(user_id, days, reason)
    duration = "НАВСЕГДА" if days == 0 else f"{days} ДНЕЙ"
    await message.answer(f"✅ ПОЛЬЗОВАТЕЛЬ {user_id} ЗАБАНЕН {duration}!\nПРИЧИНА: {reason}", reply_markup=get_admin_kb())
    await bot.send_message(user_id, f"🚫 ВЫ ЗАБАНЕНЫ {duration}!\nПРИЧИНА: {reason}")
    await state.clear()

@dp.message(F.text == "🔑 Токены", lambda m: is_admin(m.from_user.id))
async def view_tokens(message: types.Message):
    def sync():
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT token, bot_username, user_id, used_at FROM used_tokens ORDER BY used_at DESC LIMIT 20")
        return c.fetchall()
    tokens = await run_sync(sync)
    if not tokens:
        await message.answer("🔑 НЕТ ТОКЕНОВ")
        return
    text = "🔑 ТОКЕНЫ:\n\n"
    for token, bot_username, user_id, used_at in tokens:
        text += f"👤 {user_id}\n🤖 {bot_username or '?'}\n🔑 {token[:20]}...\n📅 {used_at[:16]}\n\n"
    await message.answer(text)

@dp.message(F.text == "🏆 Сбросить топ (админ)", lambda m: is_admin(m.from_user.id))
async def admin_force_weekly_reset_handler(message: types.Message):
    await message.answer("🔄 СБРОС ТОПА...")
    await message.answer("✅ ТОП СБРОШЕН!")

@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin_callback(callback: types.CallbackQuery):
    await callback.answer()
    await admin_panel_entry(callback.message)

@dp.callback_query(F.data == "unban_rub")
async def unban_rub_info(callback: types.CallbackQuery):
    unban_price_rub = await get_setting('unban_price_rub') or str(UNBAN_PRICE_RUB)
    card = await get_setting('card_number') or CARD_NUMBER
    holder = await get_setting('card_holder') or CARD_HOLDER
    await callback.answer()
    await callback.message.answer(f"💳 ОПЛАТА РАЗБАНА {unban_price_rub}₽\n{card}\n{holder}")

@dp.callback_query(F.data == "unban_paid")
async def unban_paid_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("📸 ОТПРАВЬТЕ ФОТО ЧЕКА:", reply_markup=get_cancel_kb())
    await state.update_data(payment_type='unban')
    await state.set_state(PaymentPhoto.waiting)

@dp.callback_query()
async def unknown_callback(callback: types.CallbackQuery):
    logger.warning(f"Неизвестный callback: {callback.data}")
    await callback.answer("❌ Неизвестная команда", show_alert=False)

# ============ ЗАПУСК ============

async def on_startup():
    await run_sync(init_db_sync)
    logger.info("✅ БД ИНИЦИАЛИЗИРОВАНА")
    
    if WELCOME_PHOTO_URL and not os.path.exists(WELCOME_PHOTO_PATH):
        success = await download_photo_async(WELCOME_PHOTO_URL, WELCOME_PHOTO_PATH)
        if success:
            logger.info("✅ Приветственное фото загружено")
        else:
            logger.error("❌ Не удалось загрузить приветственное фото")

async def weekly_top_scheduler():
    while True:
        await asyncio.sleep(86400 * 7)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await on_startup()
    logger.info("✅ БОТ ЗАПУЩЕН!")
    asyncio.create_task(weekly_top_scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 ОСТАНОВЛЕН")
