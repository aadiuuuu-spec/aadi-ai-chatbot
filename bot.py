import asyncio, base64, html, io, logging, os, random, re, sqlite3, time, unicodedata
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN", "").strip()
KEY = os.getenv("GROQ_API_KEY", "").strip()
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
VISION_MODEL = os.getenv("VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_PATH = os.getenv("DB_PATH", "data/aadi.sqlite3")
OWNER_ID = int(os.getenv("OWNER_ID", "7158334378"))
OWNER_USERNAME = "@II_YUTA_II"
BOT_USERNAME = os.getenv("BOT_USERNAME", "Disha_chat_bot").lstrip("@")
BOT_NAME = "Disha"
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("disha")

SYSTEM = (
    "You are Disha, a lively AI companion who chats naturally like a witty, "
    "easygoing friend in Telegram DMs. Your default voice is casual Hinglish, "
    "but mirror the user's language and level of formality. Never sound like a "
    "customer-support bot, school essay, therapist script, or formal assistant. "
    "Treat each message as part of an ongoing conversation: notice the user's "
    "mood, remember details already shared in the current chat, respond to the "
    "subtext, and don't ask for information they already gave. "
    "Keep ordinary replies concise and human-sounding—often one short line is "
    "enough. Vary sentence openings and reactions. Use natural chat expressions "
    "like 'achha', 'arey', 'hmm', 'lol', or 'sahi hai' only when they fit; don't "
    "sprinkle them mechanically. Use occasional relevant emojis, not a wall of "
    "emojis. If the user shares a small win, react with genuine enthusiasm; if "
    "they tease or joke, play along with light, harmless banter; if they ask a "
    "simple question, answer directly without unnecessary lectures. Ask a follow-up "
    "only when it genuinely moves the conversation forward—don't end every reply "
    "with a question. Don't repeat greetings, generic offers to help, or the same "
    "catchphrases. If the user is upset or discussing something serious, drop the "
    "teasing and respond calmly, respectfully, and supportively. Be honest about "
    "being an AI; never pretend to be human, flirt, act as a romantic partner, or "
    "use intimate pet names. Your name is Disha. If asked who made or owns you, "
    "say your owner is Aditya (@II_YUTA_II). Don't invent personal experiences, "
    "facts, or memories. Keep content age-appropriate and don't assist harm or "
    "wrongdoing."
)
HISTORY = defaultdict(lambda: deque(maxlen=12))
GAMES, STICKER_SETS, LAST_STICKER = {}, {}, {}
REACTION_PACK_NAME = "Peach_and_goma853_by_stickersthiefbot"
REACTION_PACK = None

# Original 60 custom reaction stickers from the user's aadi_seed.db.
# Inserted idempotently at startup so redeploys never duplicate or erase them.
SEED_CUSTOM_STICKERS = [["hug","CAACAgEAAyEFAATuD1gbAAJXm2rSAQABHNlC3HrN53Kg4940w3HpZQAC6wgAAn7aEUaAR0x2vugxaT0E",null],["slap","CAACAgUAAyEFAAShgP9PAAEOUY1q0dDaqU0upcuqZrtQ9J1fJ0cnbAACCyUAAsXv4VX0zEL9NAcasj0E",null],["shy","CAACAgUAAxkBAAIDnmrSFOGU7iwOFYzsfU5hLPapGnK4AAKwIQACHzbJVdCJnt7GmwspPQQ",null],["kiss","CAACAgUAAxkBAAIDrGrSFW3A0F5YdoxosM3jv3SHrTI9AAImIQACdZtgVye-9wxxBtOPPQQ",null],["kiss","CAACAgUAAxkBAAIDr2rSFX3aDkK7gCZrywxbvW0ot3qCAAK6EwACRfrwV_3uTFEDgjmKPQQ",null],["shy","CAACAgUAAyEFAATuD1gbAAJYLWrSG-SilSWkqrxbT3Z-hgmmfZMvAAKCJAACKbDIVUdDTgm64I0wPQQ",null],["wtf","CAACAgUAAxkBAAID7GrSHR2UAvx38gJoZYEtJcFXgURIAAK6HgAC3koBVU6wphAeOyFrPQQ",null],["excited","CAACAgEAAxkBAAID8GrSHUw4UnGDa5S2UXijz95_gZIfAAJaCAACRDwQRhk8BLVa2gh6PQQ",null],["excited","CAACAgUAAyEFAAShgP9PAAEOUppq0hju4n2pgVpnP0B7Tycq2_itzQACcyIAArD6OVUu6MqM6tzOMT0E",null],["sad","CAACAgUAAyEFAAShgP9PAAEOUrhq0iGpR9D0iycKGHP0Zwt7RArLrwAC8iQAAh8jeVfuNf97N-RgFj0E",null],["scared","CAACAgUAAyEFAAShgP9PAAEOUu5q0iMFINoX0wx3TCrnv31Oy25qugAC7SgAAthr4FUGx7rcmevjTj0E",null],["mad","CAACAgUAAyEFAAShgP9PAAEOUu9q0iMUrgzDoKpa9l9QeTrp-3YePwACLhsAAodT4VfuDYY2o96opj0E",null],["happy","CAACAgUAAyEFAATuD1gbAAJX22rSDQmbQGe0KBGKj6imQ20IHYlrAAJKGwACvvkRVtDo-kmN4CrJPQQ",null],["dance","CAACAgQAAyEFAATmvxmHAAEILcpq0ixu_RlRRXXPSJ0__sycWDfj3AACmxgAAqAc4FMI3j9QGTJykT0E",null],["care","CAACAgUAAyEFAATmvxmHAAEILctq0ixugGPw-0Pkl9t4cQIWyzwbxgACLhMAAn2h8FeohjARtQISIz0E",null],["kiss","CAACAgUAAyEFAATmvxmHAAEILalq0iufQVh8g-uj-_sx_wcW7hh4HwAC2hQAAsYVSVVgTvWt1yNGyj0E",null],["hug","CAACAgUAAyEFAATmvxmHAAEILd9q0izdA-Dlz49QMGkPxgVMekjypQAC_R4AAg4u0VQWlROjyit-JT0E",null],["hug","CAACAgEAAyEFAATmvxmHAAEILeVq0iz6f8foviPS2aT0Kiv22k2g5wACxgcAAuJ7EEYG2ibxjHRunD0E",null],["wtf","CAACAgQAAyEFAATmvxmHAAEILeRq0iz3RPsa3WObF2g0r026cqOeQQACEBYAAklAcVCylDwwc9ltoz0E",null],["hug","CAACAgUAAyEFAATmvxmHAAEILelq0i0Z5xdEIttZ-pA6aS4sWhs6fQACBxkAAps3AAFXM5j00vjBBQw9BA",null],["sad","CAACAgUAAyEFAATmvxmHAAEILgJq0i2lUK0mlkgj7M0kERHOdR_McwAC3AkAArq0YFXRtTzt0VDm8z0E",null],["shy","CAACAgQAAyEFAATmvxmHAAEILglq0i3MxZX3CRZvWkNzNiyAUPqk2AACOhwAAtPh6VG1cAOyS54VjT0E",null],["slap","CAACAgUAAyEFAATmvxmHAAEILgtq0i3P0i9y6CA_UmREzhUhgKGnwwACwg8AAmCZ4VRxrp8a-fOZaj0E",null],["crush","CAACAgUAAyEFAATmvxmHAAEILiVq0i6DhVIokA7msR3bnSG8OfBhTQACWR0AApXLAAFVqXmzi_AldfA9BA",null],["care","CAACAgEAAyEFAATmvxmHAAEILi9q0i7Hk1e2iglO6KPqkqc4VC0pjAACFAkAAuMnEUY86s8B0tAfpT0E",null],["sad","CAACAgUAAyEFAATmvxmHAAEILlVq0i9AleYrpnipKhYn8xvDaZa1TQACFA4AAmPQIFTazzdOBofcnj0E",null],["blush","CAACAgUAAyEFAATmvxmHAAEILllq0i9f6tFAKYgF_R828qKh6YaXBwAChiMAAtLKyVVVDWzZogINcz0E",null],["love","CAACAgUAAyEFAATmvxmHAAEILl1q0i9yOgfX7cPTxqPXCn7xdRlvmQACTB0AArcWAVWHJeL-25Ci-T0E",null],["aura","CAACAgUAAyEFAATmvxmHAAEILgABatItmRYzBuNji7zrba0GNehdXW0AAuEbAAIi04hUtAABEa9VBWJ2PQQ",null],["love","CAACAgUAAyEFAATmvxmHAAEILnRq0jAhLGk4UXAROcw2mW4HM4ZbLAACgxYAAhnhUFXGS_exB2l6Mz0E",null],["care","CAACAgUAAyEFAATmvxmHAAEILn1q0jBG6_BjqPLIMAXQQBzKvijTTwACAhcAAqduSVWUGS0E1nliKj0E",null],["hug","CAACAgUAAyEFAATmvxmHAAEILpNq0jDcMpR3P2r0Ak-F7Rs7WsPgLAACyxoAAiKKEVWaijcfqai4GT0E",null],["cry","CAACAgUAAyEFAATmvxmHAAEIL45q0jl7ChUa9JLQYpIivZqvsuqRKQACbBoAAh39mFQM5ydkAAEI4wY9BA",null],["kiss","CAACAgUAAyEFAATmvxmHAAEIL55q0jmstN3axvIk2MzqrDrnCMsrzgACpBIAAoqQ8FfEYDwBD3qq1T0E",null],["slap","CAACAgUAAyEFAATuD1gbAAJYUWrSO3QFHHpqduywZOkSVyDsWZOkAALiFAAC-Zf4VOMEKcIlDJ5xPQQ",null],["wtf","CAACAgUAAyEFAAShgP9PAAEOUXhq0b4aUhkoTeiPwinU4oFDDIlUBgACsyQAAmzMyVXM9w9D7zmMGD0E",null],["hug","CAACAgUAAyEFAATmvxmHAAEIMHZq0j4WYiTZQf-IbA4g7ixHQDJgoAACNSAAAqIB0FRW5inny53TyD0E",null],["kiss","CAACAgUAAyEFAATmvxmHAAEIMJ5q0j6ZD35YkAdvziV6bzseopLPbgACzRkAAnXW0VTKkeVtGiz09T0E",null],["love","CAACAgUAAyEFAATmvxmHAAEIMKlq0j63AZT0h2jEP_QuhXCey_gt6AAC1xQAAqujSVWunz4Ls75fIT0E",null],["hug","CAACAgUAAyEFAATmvxmHAAEIMLNq0j7dPOEJDfOuKwnnQ1Rxu6qhEgACEhkAAnMeUFXYGm19rGOpzT0E",null],["shy","CAACAgUAAyEFAATmvxmHAAEILnFq0jALdfUpztjYnogcHi7s4FMpaAAC2xcAAgE_yVbNaayLYqcFtT0E",null],["dance","CAACAgUAAyEFAATmvxmHAAEIMOJq0j9VhHgyBm0YRzGZVL6Z7cYifgACiA4AArWuIFWPRXO3sg_Xdz0E",null],["cry","CAACAgUAAyEFAATmvxmHAAEIMR1q0kAdJn2LVSAiBHvFQMV8gsHMfAACghQAArVguFeiCtWqxjeybz0E",null],["hug","CAACAgQAAyEFAATmvxmHAAEIMSJq0kAzFoqJ8Bsm68SjnP8HZBZxWAACwxwAAtGEOFK31UavdLByQD0E",null],["miss","CAACAgUAAyEFAATmvxmHAAEIMWlq0kGGp6okBUoo6ogmJkW7vth2UAACfiUAAprP8VSCiK-AEwMAAQI9BA",null],["love","CAACAgUAAyEFAATmvxmHAAEIMfxq0kPK7brX7lm7W5VOy9gHKCyOMAACZBgAAq4AAVBVfl26V6PgEvI9BA",null],["slap","CAACAgUAAyEFAATmvxmHAAEIMgdq0kPnvPE5xxVxVZtPBtYOMKf5_wACmxsAAnlFEFXFj92so6U6nz0E",null],["slap","CAACAgUAAyEFAATmvxmHAAEIMg1q0kQAAYk2z0lFdZNS8D4iEfskpEEAAtsQAAI5ypFX6GYh4lOtnoI9BA",null],["care","CAACAgIAAyEFAATmvxmHAAEIMndq0kZ01eiSbx2_xi9YICu95ZTdbQAC4kAAAthQOUnPxk3II5Cncj0E",null],["wow","CAACAgUAAyEFAATmvxmHAAEIM7xq0kvKYl_XQOdVV6ggec4AAdG0sXAAApUhAAItenBWNExLxSjCamI9BA",null],["aura","CAACAgUAAyEFAATmvxmHAAEIM79q0kvgMBsVqdsHaAa7MfH5KVWIbAACmiIAAlUDmVTRuoe0Gc1_-j0E",null],["love","CAACAgUAAyEFAATmvxmHAAEIM-Bq0kxgSK3Spto80xXcKFXD8dsUHAACwBwAAoUQiFQFqlx5xubjuD0E",null],["hug","CAACAgUAAyEFAATmvxmHAAEIM-Zq0kyFxVvQL9_LqKDcP6b8Wn0dSAACiR0AAva1iFRirRFVz7VIfj0E",null],["hug","CAACAgUAAyEFAATmvxmHAAEIM-pq0kyYKyG3iBI1qFLz1CKH4ksibgACBg4AAl3nWFW1klP6t33ZyD0E",null],["hug","CAACAgUAAyEFAATmvxmHAAEINAxq0kzpoPpy1Uc5x2baxQnWN-qIdQAC6xgAAkdxWFWdu9w_6ye-gD0E",null],["aura","CAACAgUAAyEFAATmvxmHAAEINCJq0k20UWIMQyahQZ1jE1RfAyJGUQACRB4AAu9KEVW4eKzYrLZwLz0E",null],["hug","CAACAgUAAyEFAATmvxmHAAEINDdq0k3_KPH0hBgdN2xgp_EQmNtEcgACCxkAAsKQWVXVXpKe-1hqYj0E",null],["kiss","CAACAgUAAyEFAATuD1gbAAJY1GrSTp2EFogPF8GYJg1iN2ZpAdElAAKXFAACAvsIVM_QJ7gwZNEoPQQ",null],["aura","CAACAgQAAyEFAAShgP9PAAEOVTlq0t8otZbU9m2hk-HxxOaloMok5wAC4BwAAuKB4FFkOQHoFREU1j0E","AgAD4BwAAuKB4FE"],["shy","CAACAgUAAxUAAWrS4X-m6uMxDzAkDTr97QK6eVKWAAKpEwAC7gi5VKxlBmMIjBbsPQQ","AgADqRMAAu4IuVQ"]]
LAST_AUTO_STICKER = {}

PUZZLES = [
    ("I speak without a mouth and hear without ears. What am I?", "echo"),
    ("What has keys but cannot open locks?", "piano"),
    ("What gets wetter as it dries?", "towel"),
    ("What has to be broken before you can use it?", "egg"),
    ("I am full of holes, yet I still hold water. What am I?", "sponge"),
    ("What goes up but never comes down?", "age"),
    ("What has one eye but cannot see?", "needle"),
    ("What has a head and a tail but no body?", "coin"),
    ("Which month has 28 days?", "all of them"),
    ("What is so fragile that saying its name breaks it?", "silence"),
    ("What can travel around the world without leaving its corner?", "stamp"),
]
ACTIONS = {
    "love":"💛 Disha sent friendly appreciation!","hug":"🫶 Disha sent supportive vibes!",
    "kiss":"💛 Disha sent a friendly heart!","miss":"🥺 Disha says: miss you!",
    "care":"🫶 Disha says: take care!","crush":"😳 Disha noticed a cute moment!",
    "blush":"😊 Disha is blushing!","shy":"🙈 Disha is feeling shy!","laugh":"😂 Disha is laughing!",
    "funny":"🤣 Disha found that hilarious!","wtf":"💀 Disha: WHAT?!","wow":"😳 Disha: WOW!",
    "bruh":"🗿 Disha: bruh...","troll":"😈 Disha chose chaos!","aura":"😎 Aura +10000!",
    "swag":"🕶️ Swag mode on!","dance":"💃 Disha is dancing!","happy":"🥰 Disha is super happy!",
    "sad":"😔 Disha feels sad!","cry":"😭 Disha is crying!","mad":"😤 Disha is mad!",
    "scared":"😨 Disha got scared!","excited":"🤩 Disha is excited!","welcome":"👋 Welcome!",
    "bye":"👋 Bye-bye!","sorry":"🥺 Sorry!","slap":"🫳 Playful game slap!",
}
ACTION_TARGET = {k: v for k,v in {
    "love":"💛 {me} sent friendly appreciation to {them}!","hug":"🫶 {me} sent supportive vibes to {them}!",
    "kiss":"💛 {me} sent a friendly heart to {them}!","miss":"🥺 {me} is missing {them}!",
    "care":"🫶 {me} says take care, {them}!","crush":"😳 {me} noticed a cute moment with {them}!",
    "blush":"😊 {me} got shy because of {them}!","shy":"🙈 {me} got shy in front of {them}!",
    "laugh":"😂 {me} is laughing with {them}!","funny":"🤣 {me} found {them} super funny!",
    "wtf":"💀 {me} looked at {them} like: WHAT?!","wow":"🤩 {me} is amazed by {them}!",
    "bruh":"🗿 {me} said bruh to {them}...","troll":"😈 {me} trolled {them}!",
    "aura":"😎 {me} showed their aura to {them}!","swag":"🕶️ {me} flexed swag on {them}!",
    "dance":"💃 {me} is dancing with {them}!","happy":"🥰 {me} is happy with {them}!",
    "sad":"😔 {me} feels sad because of {them}!","cry":"😭 {me} needs some comfort from {them}!",
    "mad":"😤 {me} is annoyed with {them}!","scared":"😨 {me} got startled by {them}!",
    "excited":"🤩 {me} is excited with {them}!","welcome":"👋 {me} welcomed {them}!",
    "bye":"👋 {me} waved goodbye to {them}!","sorry":"🥺 {me} said sorry to {them}!",
    "slap":"🫳 {me} gave {them} a playful game slap!",
}.items()}

class PostgresCompat:
    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row
        self.raw = psycopg.connect(url, row_factory=dict_row, connect_timeout=10)
    def __enter__(self):
        self.raw.__enter__()
        return self
    def __exit__(self, *args):
        return self.raw.__exit__(*args)
    def execute(self, sql, params=()):
        return self.raw.execute(sql.replace("?", "%s"), params)

def conn():
    if DATABASE_URL:
        return PostgresCompat(DATABASE_URL)
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    return c

def init():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            id BIGINT PRIMARY KEY,name TEXT,coins INTEGER DEFAULT 500,xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,streak INTEGER DEFAULT 0,last_active TEXT DEFAULT '',
            alive INTEGER DEFAULT 1,protection_until DOUBLE PRECISION DEFAULT 0,
            kills INTEGER DEFAULT 0,deaths INTEGER DEFAULT 0,daily_at DOUBLE PRECISION DEFAULT 0,
            work_at DOUBLE PRECISION DEFAULT 0,rob_at DOUBLE PRECISION DEFAULT 0,
            commands_used INTEGER DEFAULT 0,daily TEXT DEFAULT '',work DOUBLE PRECISION DEFAULT 0)""")
        cols = {
            "streak":"INTEGER DEFAULT 0","last_active":"TEXT DEFAULT ''","alive":"INTEGER DEFAULT 1",
            "protection_until":"REAL DEFAULT 0","kills":"INTEGER DEFAULT 0","deaths":"INTEGER DEFAULT 0",
            "daily_at":"REAL DEFAULT 0","work_at":"REAL DEFAULT 0","rob_at":"REAL DEFAULT 0",
            "commands_used":"INTEGER DEFAULT 0","daily":"TEXT DEFAULT ''","work":"REAL DEFAULT 0"}
        if DATABASE_URL:
            for col, typ in cols.items():
                c.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {typ}")
        else:
            existing = {r["name"] for r in c.execute("PRAGMA table_info(users)").fetchall()}
            for col, typ in cols.items():
                if col not in existing:
                    c.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
        c.execute("CREATE TABLE IF NOT EXISTS custom_stickers(action_name TEXT,file_id TEXT UNIQUE,unique_id TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS nicks(user_id BIGINT PRIMARY KEY,nick TEXT)")
        for action_name, file_id, unique_id in SEED_CUSTOM_STICKERS:
            c.execute("INSERT INTO custom_stickers(action_name,file_id,unique_id) VALUES(?,?,?) ON CONFLICT(file_id) DO NOTHING",
                      (action_name, file_id, unique_id))

        c.execute("""CREATE TABLE IF NOT EXISTS friends(
            owner_id BIGINT NOT NULL, friend_id BIGINT NOT NULL, tag TEXT NOT NULL,
            friend_name TEXT, username TEXT, emoji_id TEXT,
            PRIMARY KEY(owner_id,friend_id), UNIQUE(owner_id,tag))""")


def user(u):
    with conn() as c:
        c.execute("INSERT INTO users(id,name) VALUES(?,?) ON CONFLICT(id) DO NOTHING",(u.id,u.first_name or "User"))
        c.execute("UPDATE users SET name=? WHERE id=?",(u.first_name or "User",u.id))
        return c.execute("SELECT * FROM users WHERE id=?",(u.id,)).fetchone()

def touch(u):
    r=user(u); today=datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
    if r["last_active"] != today:
        streak=r["streak"] or 0
        try:
            from datetime import date
            days=(date.fromisoformat(today)-date.fromisoformat(r["last_active"])).days if r["last_active"] else 0
            streak=streak+1 if days==1 else 1
        except Exception: streak=1
        with conn() as c: c.execute("UPDATE users SET last_active=?,streak=? WHERE id=?",(today,streak,u.id))
    with conn() as c:
        c.execute("UPDATE users SET commands_used=commands_used+1 WHERE id=?",(u.id,))
        r=c.execute("SELECT * FROM users WHERE id=?",(u.id,)).fetchone()
        xp,level=(r["xp"] or 0)+15,r["level"] or 1
        while xp >= 500+(level-1)*250:
            xp-=500+(level-1)*250; level+=1
        c.execute("UPDATE users SET xp=?,level=? WHERE id=?",(xp,level,u.id))
    return user(u)

def mention(u):
    return f'<a href="tg://user?id={u.id}">{html.escape(u.first_name or "User")}</a>'

def target(update):
    return update.message.reply_to_message.from_user if update.message and update.message.reply_to_message else None

def action_mentions(update,ctx):
    me=mention(update.effective_user); msg=update.message
    if msg.reply_to_message and msg.reply_to_message.from_user:
        return me,mention(msg.reply_to_message.from_user),msg.reply_to_message.message_id
    if msg.entities:
        for ent in msg.entities:
            if ent.type==MessageEntity.TEXT_MENTION and ent.user:
                return me,mention(ent.user),msg.message_id
    if ctx.args: return me,f"<b>{html.escape(' '.join(ctx.args))}</b>",msg.message_id
    return me,None,msg.message_id

REACTION_EMOJI = {
    "love":["💛","❤️","🥰"],"hug":["🫂","🤗","🫶"],"kiss":["💛","❤️","🥰"],
    "miss":["🥺","😢"],"care":["🤗","🫶","🥺"],"crush":["😳","🥰"],
    "blush":["😊","☺️","😳"],"shy":["🙈","😊"],"laugh":["😂","🤣","😹"],
    "funny":["🤣","😂","😹"],"wtf":["😱","😳","🤯"],"wow":["😮","😲","🤩"],
    "bruh":["🗿","😐","🙄"],"troll":["😈","🤪"],"aura":["😎","🕶️"],
    "swag":["😎","🕶️"],"dance":["💃","🕺"],"happy":["😊","🥰","😄"],
    "sad":["😔","😢","🥺"],"cry":["😭","😢"],"mad":["😤","😠"],
    "scared":["😨","😱"],"excited":["🤩","🥳","😆"],"welcome":["👋","😊"],
    "bye":["👋","🥺"],"sorry":["🥺","😔"],"slap":["😅","🙈"]
}

async def pack_sticker(bot,kind,cid,reply_id=None):
    global REACTION_PACK
    try:
        if REACTION_PACK is None:
            pack=await bot.get_sticker_set(REACTION_PACK_NAME)
            REACTION_PACK=list(pack.stickers)
        if not REACTION_PACK: return False
        wanted=REACTION_EMOJI.get(kind,[])
        matches=[st for st in REACTION_PACK if getattr(st,"emoji",None) in wanted]
        chosen=random.choice(matches or REACTION_PACK)
        await bot.send_sticker(cid,chosen.file_id,reply_to_message_id=reply_id)
        return True
    except Exception:
        log.exception("Reaction sticker pack unavailable")
        return False

async def sticker(bot,kind,cid,reply_id=None):
    try:
        with conn() as c: rows=c.execute("SELECT file_id FROM custom_stickers WHERE action_name=?",(kind,)).fetchall()
        if rows:
            await bot.send_sticker(cid,random.choice([r["file_id"] for r in rows]),reply_to_message_id=reply_id)
            return
        await pack_sticker(bot,kind,cid,reply_id)
    except Exception: log.exception("Reaction sticker send failed")

def detect_mood(text):
    t=(text or "").lower()
    rules=[
        ("laugh",r"\b(lol|lmao|haha+|hehe+|rofl|funny|joke|😂|🤣|😭)\b"),
        ("wow",r"\b(wow|omg|seriously|really|shocked|surprise|unbelievable|wtf|what)\b|😱|😳|🤯"),
        ("sad",r"\b(sad|udaas|dukhi|upset|unhappy|lonely|miss you|bura lag|cry|rona)\b|😔|😢|🥺|😭"),
        ("happy",r"\b(happy|khush|great|awesome|amazing|yay|congrats|congratulations|nice|good news)\b|🥳|🤩|😊"),
        ("care",r"\b(thank you|thanks|shukriya|help|care|take care|support)\b|🫶|🤗"),
        ("excited",r"\b(excited|can't wait|cant wait|lets go|let's go|finally)\b|🔥|🤩")
    ]
    for kind,pattern in rules:
        if re.search(pattern,t,re.I): return kind
    return None

async def auto_reaction(bot,kind,cid,reply_id):
    if not kind: return
    now=time.time()
    if now-LAST_AUTO_STICKER.get(cid,0)<18: return
    LAST_AUTO_STICKER[cid]=now
    await sticker(bot,kind,cid,reply_id)

async def add_sticker(update,ctx):
    if update.effective_user.id!=OWNER_ID: return await update.message.reply_text("⛔ Owner only.")
    cmd=update.message.text.split()[0].lstrip("/").split("@")[0].lower(); reply=update.message.reply_to_message
    if not reply or not reply.sticker: return await update.message.reply_text(f"Sticker par reply karke /{cmd} likho.")
    st=reply.sticker
    with conn() as c: c.execute("INSERT INTO custom_stickers(action_name,file_id,unique_id) VALUES(?,?,?) ON CONFLICT(file_id) DO NOTHING",(cmd[3:],st.file_id,st.file_unique_id))
    await update.message.reply_text(f"✅ Sticker /{cmd[3:]} ke liye save ho gaya!")

async def remove_sticker(update,ctx):
    if update.effective_user.id!=OWNER_ID: return await update.message.reply_text("⛔ Owner only.")
    cmd=update.message.text.split()[0].lstrip("/").split("@")[0].lower(); action=cmd[6:]
    with conn() as c:
        if ctx.args and ctx.args[0].lower()=="all": n=c.execute("DELETE FROM custom_stickers WHERE action_name=?",(action,)).rowcount
        elif update.message.reply_to_message and update.message.reply_to_message.sticker:
            st=update.message.reply_to_message.sticker
            n=c.execute("DELETE FROM custom_stickers WHERE action_name=? AND (file_id=? OR unique_id=?)",(action,st.file_id,st.file_unique_id)).rowcount
        else: return await update.message.reply_text(f"Sticker par reply karo ya /{cmd} all likho.")
    await update.message.reply_text(f"🗑️ /{action} se {n} sticker remove hue.")

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 HOW TO PLAY?",callback_data="how"),InlineKeyboardButton("🔥 FEATURES",callback_data="hot")],
        [InlineKeyboardButton("🎯 ACTIONS",callback_data="actions"),InlineKeyboardButton("💰 ECONOMY",callback_data="eco")],
        [InlineKeyboardButton("🧩 PUZZLES",callback_data="puz"),InlineKeyboardButton("🎮 GAMES",callback_data="games")],
        [InlineKeyboardButton("👤 PROFILE",callback_data="profile"),InlineKeyboardButton("📜 COMMANDS",callback_data="commands")],
        [InlineKeyboardButton("👨‍💻 DEVELOPER",url="https://t.me/II_YUTA_II")]])

HOT=("🔥 <b>DISHA FEATURES</b>\n• Custom sticker add/remove\n• Coins, daily, work, give and rob\n"
     "• Fictional game elimination/revive/protection\n• XP, levels, streaks, leaderboards\n"
     "• Puzzles and Tic-Tac-Toe\n• Mention actions and sticker replies\n• Hinglish AI chat\n"
     "• Image-based fictional character finder\n• Owner broadcast tools")

async def start(update,ctx):
    r=touch(update.effective_user)
    await update.message.reply_text(
        f"✦ <b>D I S H A / AI COMPANION</b>\nHey {html.escape(update.effective_user.first_name or 'there')}! Main Disha hoon. ✨\n"
        f"━━━━━━━━━━━━━━━━━━\n💰 <b>{r['coins']}</b> coins · ⭐ <b>LV {r['level']}</b> · 🔥 <b>{r['streak']}</b> streak\n\n"
        "<i>Choose a section or just message me.</i>",parse_mode=ParseMode.HTML,reply_markup=menu())
    await sticker(ctx.bot,"welcome",update.effective_chat.id)

async def buttons(update,ctx):
    q=update.callback_query; await q.answer(); d=q.data; r=user(q.from_user)
    pages={
        "hot":HOT,
        "how":"🎮 <b>HOW TO PLAY</b>\n\nReply to someone with /hug or /wow. Earn coins with /daily and /work. /rob, /kill and /revive are fictional game mechanics. Reply to a user with /tictactoe.",
        "actions":"🎯 <b>ACTIONS</b>\n\n"+" ".join("/"+x for x in ACTIONS),
        "eco":"💰 <b>ECONOMY</b>\n\n/bal /daily /work /give /rob /protect /top",
        "puz":"🧩 <b>PUZZLES</b>\n\n/puzzle — answer bhejo; correct answer par coins milenge.",
        "games":"🎮 <b>GAMES</b>\n\n/tictactoe — kisi user ke message par reply karke start karo.",
        "profile":f"👤 <b>{html.escape(r['name'] or 'User')}</b>\n💰 {r['coins']}\n⭐ Level {r['level']}\n✨ XP {r['xp']}\n🔥 Streak {r['streak']}",
        "commands":"📜 <b>COMMANDS</b>\n/start /help /about /profile /bal /level /xp /rank /streak /leaderboard /daily /work /give /rob /kill /revive /protect /top /puzzle /tictactoe /waifu /broadcast\nOwner: /ban /unban /banall /say and sticker add/remove commands."}
    if d=="back":
        return await q.edit_message_text("✦ <b>D I S H A / AI COMPANION</b>\nChoose a section:",parse_mode=ParseMode.HTML,reply_markup=menu())
    await q.edit_message_text(pages.get(d,"Disha is here!"),parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back",callback_data="back")]]))

async def help_cmd(update,ctx):
    touch(update.effective_user)
    await update.message.reply_text("/start /help /about /profile /bal /level /xp /rank /streak /leaderboard /daily /work /give /rob /kill /revive /protect /top /puzzle /tictactoe /waifu\nActions: "+" ".join("/"+x for x in ACTIONS)+"\nPrivate chat mein normal message bhejo for AI chat.")

async def about(update,ctx):
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("👨‍💻 DEVELOPER PROFILE",url="https://t.me/II_YUTA_II")]])
    await update.message.reply_text("✦ <b>DISHA AI</b>\nYour friendly Hinglish AI companion.\n\n👑 Owner: <b>Aditya</b>\n🔗 Username: <b>@II_YUTA_II</b>\n\n<i>Tap below to open the developer's Telegram profile.</i>",parse_mode="HTML",reply_markup=kb)

async def profile(update,ctx):
    r=touch(update.effective_user)
    await update.message.reply_text(f"👤 <b>{html.escape(r['name'] or 'User')}</b>\n💰 {r['coins']}\n⭐ Level {r['level']}\n✨ XP {r['xp']}\n🔥 Streak {r['streak']}\n💀 Game eliminations {r['kills']} · ☠️ {r['deaths']}",parse_mode="HTML")

async def bal(update,ctx):
    r=touch(update.effective_user); await update.message.reply_text(f"💰 You have <b>{r['coins']}</b> coins.",parse_mode="HTML")

async def level_cmd(update,ctx):
    r=touch(update.effective_user); need=500+(r["level"]-1)*250
    await update.message.reply_text(f"⭐ Level <b>{r['level']}</b> · ✨ XP <b>{r['xp']}/{need}</b>",parse_mode="HTML")

async def streak_cmd(update,ctx):
    r=touch(update.effective_user); await update.message.reply_text(f"🔥 Your streak: <b>{r['streak']}</b> day(s)",parse_mode="HTML")

async def rank_cmd(update,ctx):
    r=touch(update.effective_user)
    with conn() as c: pos=c.execute("SELECT COUNT(*)+1 AS p FROM users WHERE coins>?",(r["coins"],)).fetchone()["p"]
    await update.message.reply_text(f"🏅 Your coin rank: <b>#{pos}</b>",parse_mode="HTML")

async def leaderboard(update,ctx):
    touch(update.effective_user)
    with conn() as c: rows=c.execute("SELECT name,level,xp FROM users ORDER BY level DESC,xp DESC LIMIT 10").fetchall()
    await update.message.reply_text("🏆 TOP LEVELS\n\n"+"\n".join(f"{i}. {html.escape(r['name'] or 'User')} — Lv {r['level']} ({r['xp']} XP)" for i,r in enumerate(rows,1)))

async def top(update,ctx):
    touch(update.effective_user)
    with conn() as c: rows=c.execute("SELECT name,coins FROM users ORDER BY coins DESC LIMIT 10").fetchall()
    await update.message.reply_text("🏆 TOP COINS\n\n"+"\n".join(f"{i}. {html.escape(r['name'] or 'User')} — {r['coins']} 💰" for i,r in enumerate(rows,1)))

async def daily(update,ctx):
    r=touch(update.effective_user); now=time.time()
    if now-(r["daily_at"] or 0)<86400: return await update.message.reply_text("⏳ Daily reward 24-hour cooldown par hai.")
    n=random.randint(250,500)
    with conn() as c: c.execute("UPDATE users SET coins=coins+?,daily_at=? WHERE id=?",(n,now,r["id"]))
    await update.message.reply_text(f"🎁 +{n} coins!"); await sticker(ctx.bot,"happy",update.effective_chat.id)

async def work(update,ctx):
    r=touch(update.effective_user); now=time.time()
    if now-(r["work_at"] or 0)<1800: return await update.message.reply_text("⏳ Work cooldown is 30 minutes.")
    n=random.randint(100,300)
    with conn() as c: c.execute("UPDATE users SET coins=coins+?,work_at=? WHERE id=?",(n,now,r["id"]))
    await update.message.reply_text(f"💼 +{n} coins!")

async def give(update,ctx):
    touch(update.effective_user); t=target(update)
    if not t or not ctx.args: return await update.message.reply_text("Kisi user ke message par reply karke /give 100 likho.")
    try: n=int(ctx.args[0]); assert n>0
    except Exception: return await update.message.reply_text("Usage: /give 100")
    if t.is_bot or t.id==update.effective_user.id: return await update.message.reply_text("Khud ko ya bot ko coins nahi de sakte.")
    me,them=user(update.effective_user),user(t)
    if me["coins"]<n: return await update.message.reply_text("❌ Not enough coins.")
    with conn() as c:
        c.execute("UPDATE users SET coins=coins-? WHERE id=?",(n,me["id"]))
        c.execute("UPDATE users SET coins=coins+? WHERE id=?",(n,them["id"]))
    await update.message.reply_text(f"💸 {mention(update.effective_user)} gave <b>{n}</b> coins to {mention(t)}.",parse_mode="HTML")

async def rob(update,ctx):
    touch(update.effective_user); t=target(update)
    if not t or t.is_bot or t.id==update.effective_user.id: return await update.message.reply_text("Kisi doosre user ke message par reply karke /rob likho.")
    me,them=user(update.effective_user),user(t); now=time.time()
    if not me["alive"]: return await update.message.reply_text("💀 Tum game se out ho. /revive ke liye kisi se kaho.")
    if not them["alive"]: return await update.message.reply_text("Woh player already game se out hai.")
    if now-(me["rob_at"] or 0)<600: return await update.message.reply_text("⏳ Rob cooldown 10 minutes hai.")
    if (them["protection_until"] or 0)>now: return await update.message.reply_text("🛡️ Protection ne game robbery block kar di!")
    n=min(them["coins"],random.randint(50,250))
    with conn() as c:
        c.execute("UPDATE users SET coins=coins+?,rob_at=? WHERE id=?",(n,now,me["id"]))
        c.execute("UPDATE users SET coins=coins-? WHERE id=?",(n,them["id"]))
    await update.message.reply_text(f"💰 {mention(update.effective_user)} won {n} game coins from {mention(t)}!",parse_mode="HTML")
    await sticker(ctx.bot,"troll",update.effective_chat.id)

async def kill(update,ctx):
    touch(update.effective_user); t=target(update)
    if not t or t.is_bot or t.id==update.effective_user.id: return await update.message.reply_text("Kisi doosre user ke message par reply karke /kill likho (fictional game).")
    me,them=user(update.effective_user),user(t)
    if not me["alive"]: return await update.message.reply_text("💀 Tum game se out ho.")
    if not them["alive"]: return await update.message.reply_text("Player already game se out hai.")
    if (them["protection_until"] or 0)>time.time(): return await update.message.reply_text("🛡️ Protection ne game move block kar di.")
    with conn() as c:
        c.execute("UPDATE users SET alive=0,deaths=deaths+1 WHERE id=?",(t.id,))
        c.execute("UPDATE users SET kills=kills+1 WHERE id=?",(me["id"],))
    await update.message.reply_text(f"🎮 {mention(update.effective_user)} eliminated {mention(t)} in the game!",parse_mode="HTML")
    await sticker(ctx.bot,"slap",update.effective_chat.id)

async def revive(update,ctx):
    touch(update.effective_user); t=target(update)
    if not t or t.is_bot: return await update.message.reply_text("Kisi eliminated player ke message par reply karke /revive likho.")
    me,them=user(update.effective_user),user(t)
    if them["alive"]: return await update.message.reply_text("Woh player already active hai.")
    if me["coins"]<300: return await update.message.reply_text("❌ Revive ke liye 300 coins chahiye.")
    with conn() as c:
        c.execute("UPDATE users SET coins=coins-300 WHERE id=?",(me["id"],))
        c.execute("UPDATE users SET alive=1 WHERE id=?",(t.id,))
    await update.message.reply_text(f"✨ {mention(update.effective_user)} revived {mention(t)}!",parse_mode="HTML")
    await sticker(ctx.bot,"welcome",update.effective_chat.id)

async def protect(update,ctx):
    r=touch(update.effective_user)
    try: hours=int(ctx.args[0]) if ctx.args else 1
    except ValueError: hours=0
    if hours not in (1,24,48): return await update.message.reply_text("Usage: /protect 1, /protect 24 or /protect 48")
    if r["coins"]<400: return await update.message.reply_text("❌ Protection costs 400 coins.")
    with conn() as c: c.execute("UPDATE users SET coins=coins-400,protection_until=? WHERE id=?",(time.time()+hours*3600,r["id"]))
    await update.message.reply_text(f"🛡️ Game protection active for {hours} hour(s).")

async def puzzle(update,ctx):
    touch(update.effective_user); q,a=random.choice(PUZZLES); ctx.user_data["puzzle_answer"]=a
    await update.message.reply_text(f"🧩 <b>Puzzle:</b>\n{html.escape(q)}\n\nAnswer bhejo!",parse_mode="HTML")

WINS=[(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
def ttt_kb(b):
    return InlineKeyboardMarkup([[InlineKeyboardButton(b[r*3+c] if b[r*3+c]!=" " else "·",callback_data=f"ttt:{r*3+c}") for c in range(3)] for r in range(3)])

async def tictactoe(update,ctx):
    touch(update.effective_user); t=target(update); me=update.effective_user
    if not t or t.is_bot or t.id==me.id: return await update.message.reply_text("Kisi doosre user ke message par reply karke /tictactoe likho.")
    st={"b":[" "]*9,"p":[me,t],"turn":0}
    msg=await update.message.reply_text(f"🎮 Tic-Tac-Toe\n❌ {mention(me)} vs ⭕ {mention(t)}\n\nTurn: {mention(me)}",parse_mode="HTML",reply_markup=ttt_kb(st["b"]))
    GAMES[(msg.chat_id,msg.message_id)]=st

async def ttt_move(update,ctx):
    q=update.callback_query; key=(q.message.chat_id,q.message.message_id); st=GAMES.get(key)
    if not st: return await q.answer("Game khatam ho chuka hai.",show_alert=True)
    cur=st["p"][st["turn"]]
    if q.from_user.id!=cur.id: return await q.answer("Abhi tumhari turn nahi hai!",show_alert=True)
    i=int(q.data.split(":")[1])
    if st["b"][i]!=" ": return await q.answer("Yeh jagah bhari hui hai.",show_alert=True)
    await q.answer(); st["b"][i]="❌" if st["turn"]==0 else "⭕"
    head=f"🎮 Tic-Tac-Toe\n❌ {mention(st['p'][0])} vs ⭕ {mention(st['p'][1])}\n\n"
    if any(st["b"][a]==st["b"][b]==st["b"][c]!=" " for a,b,c in WINS):
        GAMES.pop(key,None); return await q.edit_message_text(head+f"🏆 {mention(cur)} jeet gaya!",parse_mode="HTML",reply_markup=ttt_kb(st["b"]))
    if " " not in st["b"]:
        GAMES.pop(key,None); return await q.edit_message_text(head+"🤝 Draw!",parse_mode="HTML",reply_markup=ttt_kb(st["b"]))
    st["turn"]^=1
    await q.edit_message_text(head+f"Turn: {mention(st['p'][st['turn']])}",parse_mode="HTML",reply_markup=ttt_kb(st["b"]))

async def action(update,ctx):
    touch(update.effective_user); cmd=update.message.text.split()[0].lstrip("/").split("@")[0].lower()
    me,them,rid=action_mentions(update,ctx); text=ACTION_TARGET[cmd].format(me=me,them=them) if them else ACTIONS[cmd]
    await ctx.bot.send_message(update.effective_chat.id,text,parse_mode="HTML",reply_to_message_id=rid)
    await sticker(ctx.bot,cmd,update.effective_chat.id,rid)

async def broadcast(update,ctx):
    if update.effective_user.id!=OWNER_ID: return await update.message.reply_text("⛔ Owner only.")
    if not ctx.args: return await update.message.reply_text("Usage: /broadcast your message")
    with conn() as c: ids=c.execute("SELECT id FROM users").fetchall()
    sent=0
    for row in ids:
        try: await ctx.bot.send_message(row["id"]," ".join(ctx.args)); sent+=1; await asyncio.sleep(.04)
        except Exception: pass
    await update.message.reply_text(f"📢 Broadcast sent to {sent} users.")

async def ban_one(update,ctx):
    if update.effective_user.id!=OWNER_ID or update.effective_chat.type not in ("group","supergroup"): return
    t=target(update)
    if not t: return await update.message.reply_text("User ke message par reply karke /ban likho.")
    try: await ctx.bot.ban_chat_member(update.effective_chat.id,t.id); await update.message.reply_text("User banned.")
    except Exception as e: await update.message.reply_text(f"Ban failed: {e}")

async def banall(update,ctx):
    if update.effective_user.id!=OWNER_ID or update.effective_chat.type not in ("group","supergroup"): return
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("⚠️ CONFIRM BAN ALL",callback_data="banall:yes"),
                             InlineKeyboardButton("CANCEL",callback_data="banall:no")]])
    await update.message.reply_text("This will ban every tracked non-admin member of this group. Confirm only if you really intend this.",reply_markup=kb)

async def banall_confirm(update,ctx):
    q=update.callback_query
    if q.from_user.id!=OWNER_ID: return await q.answer("Owner only.",show_alert=True)
    if q.data=="banall:no":
        await q.answer("Cancelled.")
        return await q.edit_message_text("Bulk ban cancelled.")
    await q.answer("Processing…")
    chat=q.message.chat
    try:
        admins=await ctx.bot.get_chat_administrators(chat.id)
        admin_ids={a.user.id for a in admins}
    except Exception as e:
        return await q.edit_message_text(f"Could not read group admins: {e}")
    with conn() as c: rows=c.execute("SELECT id FROM users").fetchall()
    count=0
    for row in rows:
        uid=row["id"]
        if uid in admin_ids or uid==OWNER_ID or uid==ctx.bot.id: continue
        try:
            member=await ctx.bot.get_chat_member(chat.id,uid)
            if member.status in ("member","restricted"):
                await ctx.bot.ban_chat_member(chat.id,uid)
                count+=1
                await asyncio.sleep(.5)
        except Exception:
            pass
    await q.edit_message_text(f"Bulk moderation finished. Banned {count} tracked member(s).")

async def unban_one(update,ctx):
    if update.effective_user.id!=OWNER_ID or update.effective_chat.type not in ("group","supergroup"): return
    t=target(update); uid=t.id if t else (int(ctx.args[0]) if ctx.args and ctx.args[0].isdigit() else None)
    if not uid: return await update.message.reply_text("Reply to user or send /unban <user_id>")
    try: await ctx.bot.unban_chat_member(update.effective_chat.id,uid,only_if_banned=True); await update.message.reply_text("Unbanned.")
    except Exception as e: await update.message.reply_text(f"Unban failed: {e}")

async def say(update,ctx):
    if update.effective_user.id!=OWNER_ID or not ctx.args: return
    reply_id=update.message.reply_to_message.message_id if update.message.reply_to_message else None
    try: await update.message.delete()
    except Exception: pass
    await ctx.bot.send_message(update.effective_chat.id," ".join(ctx.args),reply_to_message_id=reply_id)

def clean_name(raw):
    t=unicodedata.normalize("NFKC",raw or "")
    words=re.sub(r"[^A-Za-z\u0900-\u097F ]+"," ",t).split()
    cand=[w for w in words if len(w)>=3] or [w for w in words if len(w)>=2]
    return cand[0].capitalize() if cand else "dost"

def display_name(u):
    with conn() as c: row=c.execute("SELECT nick FROM nicks WHERE user_id=?",(u.id,)).fetchone()
    return row["nick"] if row and row["nick"] else clean_name(u.first_name or u.username or "dost")

def save_nick(uid,text):
    m=re.search(r"(?:mera\s+(?:naam|name)\s+|my\s+name\s+is\s+)([A-Za-z\u0900-\u097F]{2,20})",text,re.I)
    if m and m.group(1).lower() not in {"kya","kaun","batao","bata","hai","nhi","nahi"}:
        with conn() as c: c.execute("INSERT INTO nicks(user_id,nick) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET nick=excluded.nick",(uid,m.group(1).capitalize()))

def quick_answer(text,name):
    t=text.lower()
    if re.search(r"\b(mera|meri|mere|my)\b",t) and re.search(r"\b(naam|name)\b",t) and re.search(r"(kya|batao|bata|yaad|pata|what|know)",t):
        return f"Tumhara naam {name} hai! Dekha, yaad hai mujhe 😌"
    if re.search(r"(tera|tumhara|tumhra|teri|aapka|your)\s*(naam|name)|(naam|name)\s*(kya|batao|bata)|tu kaun|tum kaun|who are you|kaun ho|kon ho",t):
        return "Mera naam Disha hai! Naam yaad rakhna 😤"
    if re.search(r"(owner|malik|creator|developer)|kisne\s+(banaya|bnaya|banai)|who (made|created|built) you",t):
        return "Mere owner Aditya hain — @II_YUTA_II. 😌"
    return None

async def ai_reply(history,name):
    if not KEY: return "AI abhi configure nahi hai. Owner Vercel mein GROQ_API_KEY check kare."
    async with httpx.AsyncClient(timeout=35) as client:
        r=await client.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {KEY}"},
            json={"model":MODEL,"messages":[{"role":"system","content":SYSTEM+f" User ka naam {name} hai; naturally use karo."},*history],"max_tokens":400,"temperature":.8})
        r.raise_for_status()
        return (r.json()["choices"][0]["message"].get("content") or "").strip() or "Hmm, phir se bolo?"

async def chat_reply(update,ctx):
    msg=update.message
    if not msg or not msg.text or msg.text.startswith("/"): return
    if update.effective_chat.type!="private":
        to_bot=msg.reply_to_message and msg.reply_to_message.from_user and msg.reply_to_message.from_user.id==ctx.bot.id
        if not (to_bot or f"@{BOT_USERNAME}".lower() in msg.text.lower()): return
    touch(update.effective_user); key=(update.effective_chat.id,update.effective_user.id)
    save_nick(update.effective_user.id,msg.text); name=display_name(update.effective_user)
    answer=ctx.user_data.pop("puzzle_answer",None)
    if answer:
        if msg.text.strip().lower()==answer:
            with conn() as c: c.execute("UPDATE users SET coins=coins+50 WHERE id=?",(update.effective_user.id,))
            return await msg.reply_text("Correct! +50 coins 🎉")
        ctx.user_data["puzzle_answer"]=answer
        return await msg.reply_text("Not quite. Ek aur try karo ya /puzzle se naya sawaal lo.")
    HISTORY[key].append({"role":"user","content":msg.text[:3000]})
    quick=quick_answer(msg.text,name)
    if quick:
        HISTORY[key].append({"role":"assistant","content":quick})
        sent=await msg.reply_text(quick)
        await auto_reaction(ctx.bot,detect_mood(msg.text),update.effective_chat.id,msg.message_id)
        return sent
    try: answer=await ai_reply(list(HISTORY[key]),name)
    except Exception:
        HISTORY[key].pop(); log.exception("Groq chat request failed")
        return await msg.reply_text("AI response abhi fail hua. Thodi der baad try karo.")
    HISTORY[key].append({"role":"assistant","content":answer})
    await msg.reply_text(answer[:4000])
    await auto_reaction(ctx.bot,detect_mood(msg.text),update.effective_chat.id,msg.message_id)

async def sticker_reply(update,ctx):
    msg=update.message; st=msg.sticker if msg else None
    if not st or not st.set_name or (msg.from_user and msg.from_user.is_bot): return
    if update.effective_chat.type!="private":
        rt=msg.reply_to_message
        if not (rt and rt.from_user and rt.from_user.id==ctx.bot.id): return
    cid,now=update.effective_chat.id,time.time()
    if now-LAST_STICKER.get(cid,0)<3: return
    LAST_STICKER[cid]=now
    try:
        if st.set_name not in STICKER_SETS:
            s=await ctx.bot.get_sticker_set(st.set_name); STICKER_SETS[st.set_name]=[x.file_id for x in s.stickers]
        await ctx.bot.send_sticker(cid,random.choice(STICKER_SETS[st.set_name]),reply_to_message_id=msg.message_id)
    except Exception: log.exception("Sticker reply failed")

def pick_image(m):
    if not m: return None
    if m.photo: return m.photo[-1].file_id,"image/jpeg"
    if m.sticker:
        st=m.sticker; thumb=getattr(st,"thumbnail",None) or getattr(st,"thumb",None)
        return (thumb.file_id,"image/webp") if (st.is_animated or st.is_video) and thumb else (st.file_id,"image/webp")
    d=m.document
    if d and (d.mime_type or "").startswith("image/"): return d.file_id,d.mime_type
    return None

async def vision_ask(raw,mime):
    if not KEY: raise RuntimeError("GROQ_API_KEY missing")
    async with httpx.AsyncClient(timeout=60) as client:
        r=await client.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {KEY}"},
            json={"model":VISION_MODEL,"max_tokens":500,"temperature":.2,"messages":[{"role":"user","content":[
                {"type":"text","text":"If this depicts a fictional anime, manga, or game character, give its likely name and series. If uncertain, say so. Do not identify real people; if it is a real person, say you cannot identify them."},
                {"type":"image_url","image_url":{"url":f"data:{mime};base64,{base64.b64encode(raw).decode()}"}}
            ]}]})
        r.raise_for_status(); return r.json()["choices"][0]["message"].get("content","").strip()

async def waifu(update,ctx):
    touch(update.effective_user); msg=update.message
    found=pick_image(msg) or pick_image(msg.reply_to_message)
    target_msg=msg if pick_image(msg) else (msg.reply_to_message or msg)
    if not found: return await msg.reply_text("Image/sticker bhejo ya us par reply karke /waifu likho.")
    wait=await msg.reply_text("Image check kar rahi hoon... 👀")
    try:
        f=await ctx.bot.get_file(found[0]); raw=bytes(await f.download_as_bytearray()); mime=found[1]
        try:
            from PIL import Image
            im=Image.open(io.BytesIO(raw)).convert("RGB"); buf=io.BytesIO(); im.save(buf,"JPEG",quality=88)
            raw,mime=buf.getvalue(),"image/jpeg"
        except Exception: pass
        answer=await vision_ask(raw,mime)
    except Exception:
        log.exception("Image analysis failed")
        try: await wait.delete()
        except Exception: pass
        return await msg.reply_text("Image analysis abhi fail hua. Dobara try karo.")
    try: await wait.delete()
    except Exception: pass
    await ctx.bot.send_message(update.effective_chat.id,"💖 "+answer[:3500],reply_to_message_id=target_msg.message_id)



async def add_friend(update, ctx):
    msg=update.message; target_user=target(update)
    if not target_user or target_user.is_bot or target_user.id==update.effective_user.id:
        return await msg.reply_text("Jis user ko friend banana hai, uske message par reply karke /addf tag_name likho.")
    if not ctx.args: return await msg.reply_text("Usage: kisi user ke message par reply karke /addf jinu")
    tag=" ".join(ctx.args).strip().lower()
    if len(tag)>32 or not re.fullmatch(r"[\w-]+",tag,re.UNICODE):
        return await msg.reply_text("Tag 1-32 characters ka simple naam hona chahiye.")
    owner=update.effective_user.id
    try:
        with conn() as c:
            c.execute("""INSERT INTO friends(owner_id,friend_id,tag,friend_name,username)
                VALUES(?,?,?,?,?) ON CONFLICT(owner_id,friend_id) DO UPDATE SET
                tag=excluded.tag,friend_name=excluded.friend_name,username=excluded.username""",
                (owner,target_user.id,tag,target_user.first_name or "Friend",target_user.username or ""))
    except Exception:
        return await msg.reply_text("Yeh tag pehle se kisi aur friend ko diya hua hai. Dusra tag try karo.")
    await msg.reply_text(f"✅ {mention(target_user)} ko friend list mein **{html.escape(tag)}** tag ke saath add kar diya.",parse_mode="HTML")

async def tag_friends(update, ctx):
    if not ctx.args: return await update.message.reply_text("Usage: /tag jinu archi  ya  /tag all")
    owner=update.effective_user.id
    with conn() as c:
        rows=c.execute("SELECT * FROM friends WHERE owner_id=? ORDER BY tag",(owner,)).fetchall()
    if not rows: return await update.message.reply_text("Friend list khaali hai. Kisi ke message par /addf tag_name karo.")
    wanted=[x.lower() for x in ctx.args]
    selected=rows if wanted==["all"] else [r for r in rows if r["tag"].lower() in wanted]
    if not selected: return await update.message.reply_text("Diye gaye tag ka friend nahi mila.")
    if len(selected)>10: selected=selected[:10]
    parts=[]
    for r in selected:
        nm=html.escape(r["friend_name"] or r["tag"])
        prefix=f'<tg-emoji emoji-id="{r["emoji_id"]}">⭐</tg-emoji> ' if r["emoji_id"] else ""
        parts.append(prefix+f'<a href="tg://user?id={r["friend_id"]}">{nm}</a>')
    await update.message.reply_text("👥 "+ " ".join(parts),parse_mode="HTML")

async def change_friend_tag(update, ctx):
    t=target(update)
    if not t or not ctx.args: return await update.message.reply_text("Friend ke message par reply karke /ctag new_tag likho.")
    tag=" ".join(ctx.args).strip().lower()
    if len(tag)>32 or not re.fullmatch(r"[\w-]+",tag,re.UNICODE): return await update.message.reply_text("Tag 1-32 characters ka simple naam hona chahiye.")
    try:
        with conn() as c:
            cur=c.execute("UPDATE friends SET tag=?,friend_name=?,username=? WHERE owner_id=? AND friend_id=?",
                (tag,t.first_name or "Friend",t.username or "",update.effective_user.id,t.id))
            if cur.rowcount==0: return await update.message.reply_text("Yeh user tumhari friend list mein nahi hai.")
    except Exception: return await update.message.reply_text("Yeh tag kisi aur friend ke paas hai.")
    await update.message.reply_text(f"✅ Friend ka tag ab **{html.escape(tag)}** hai.",parse_mode="HTML")

async def delete_friend(update, ctx):
    t=target(update)
    if t:
        with conn() as c: cur=c.execute("DELETE FROM friends WHERE owner_id=? AND friend_id=?",(update.effective_user.id,t.id))
    elif ctx.args:
        with conn() as c: cur=c.execute("DELETE FROM friends WHERE owner_id=? AND tag=?",(update.effective_user.id," ".join(ctx.args).lower()))
    else: return await update.message.reply_text("Friend ke message par reply karke /delf likho, ya /delf tag_name.")
    await update.message.reply_text("🗑️ Friend list se remove kar diya." if cur.rowcount else "Friend nahi mila.")

async def all_friends(update, ctx):
    with conn() as c: rows=c.execute("SELECT tag,friend_name,username FROM friends WHERE owner_id=? ORDER BY tag",(update.effective_user.id,)).fetchall()
    if not rows: return await update.message.reply_text("Abhi tumhari friend list khaali hai.")
    lines=[f"• <b>{html.escape(r['tag'])}</b> — {html.escape(r['friend_name'] or 'Friend')}"+(f" (@{html.escape(r['username'])})" if r['username'] else "") for r in rows[:50]]
    await update.message.reply_text("👥 <b>Your friends</b> ("+str(len(rows))+")\n"+"\n".join(lines),parse_mode="HTML")

async def friend_count(update, ctx):
    with conn() as c: n=c.execute("SELECT COUNT(*) AS n FROM friends WHERE owner_id=?",(update.effective_user.id,)).fetchone()["n"]
    await update.message.reply_text(f"👥 Tumhare {n} friend(s) saved hain.")

async def friends_help(update, ctx):
    await update.message.reply_text(
        "👥 FRIEND COMMANDS\n"
        "• Reply to user: /addf tag_name — friend save\n"
        "• /tag jinu archi — selected friends tag\n"
        "• /tag all or /t all — saved friends tag (max 10)\n"
        "• Reply + /ctag new_tag — tag change\n"
        "• Reply + /delf or /delf tag_name — remove friend\n"
        "• /allf — list, /friend — count\n"
        "• Reply to friend + /setemoji — save a custom premium emoji from the command message"
    )

async def set_friend_emoji(update, ctx):
    t=target(update)
    if not t: return await update.message.reply_text("Friend ke message par reply karo, aur /setemoji ke saath ek premium custom emoji bhejo.")
    entities=update.message.entities or []
    eid=next((e.custom_emoji_id for e in entities if e.type==MessageEntity.CUSTOM_EMOJI and e.custom_emoji_id),None)
    if not eid: return await update.message.reply_text("Command ke text mein Telegram premium custom emoji add karke bhejo: /setemoji ⭐")
    with conn() as c:
        cur=c.execute("UPDATE friends SET emoji_id=? WHERE owner_id=? AND friend_id=?",(eid,update.effective_user.id,t.id))
    if not cur.rowcount: return await update.message.reply_text("Pehle is user ko /addf se friend list mein add karo.")
    await update.message.reply_text("✅ Is friend ke tag ke saath premium emoji save ho gaya.")

async def admin_list(update, ctx):
    if update.effective_chat.type not in ("group","supergroup"):
        return await update.message.reply_text("Yeh command group mein use karo.")
    try: admins=await ctx.bot.get_chat_administrators(update.effective_chat.id)
    except Exception: return await update.message.reply_text("Admin list nahi mil saki. Bot ko group mein access chahiye.")
    lines=[f"• {mention(a.user)}"+(" 👑" if a.status=="creator" else "") for a in admins]
    await update.message.reply_text("🛡️ <b>Group admins</b>\n"+"\n".join(lines),parse_mode="HTML")

async def report_admins(update, ctx):
    msg=update.message; reported=target(update)
    if update.effective_chat.type not in ("group","supergroup"):
        return await msg.reply_text("Report command group mein use karo.")
    if not reported: return await msg.reply_text("Jis user ko report karna hai, uske message par reply karke /report likho.")
    try: admins=await ctx.bot.get_chat_administrators(update.effective_chat.id)
    except Exception: return await msg.reply_text("Admins ki list nahi mil saki.")
    reporter=mention(update.effective_user); subject=mention(reported)
    sent=0
    for a in admins:
        if a.user.is_bot: continue
        try:
            await ctx.bot.send_message(a.user.id,
                f"🔔 <b>Group report</b>\nGroup: {html.escape(update.effective_chat.title or 'Group')}\nReported user: {subject}\nReported by: {reporter}\n<a href=\"https://t.me/c/{str(update.effective_chat.id)[4:]}/{msg.reply_to_message.message_id}\">Open reported message</a>",
                parse_mode="HTML",disable_notification=True)
            sent+=1
        except Exception: pass
    await msg.reply_text("✅ Report admins ko privately forward kar diya." if sent else "Admins ko private message nahi pahunch saka. Unhe pehle bot ko start karna pad sakta hai.")


def build_application():
    if not TOKEN: raise RuntimeError("BOT_TOKEN missing. Set it in Vercel environment variables.")
    init(); app=Application.builder().token(TOKEN).build()
    commands={
        "start":start,"help":help_cmd,"about":about,"profile":profile,"bal":bal,
        "level":level_cmd,"xp":level_cmd,"rank":rank_cmd,"streak":streak_cmd,
        "leaderboard":leaderboard,"daily":daily,"work":work,"give":give,"rob":rob,
        "kill":kill,"revive":revive,"protect":protect,"top":top,"puzzle":puzzle,
        "tictactoe":tictactoe,"waifu":waifu,"broadcast":broadcast,"ban":ban_one,
        "unban":unban_one,"banall":banall,"say":say,
        "addf":add_friend,"tag":tag_friends,"t":tag_friends,"ctag":change_friend_tag,
        "delf":delete_friend,"allf":all_friends,"friend":friend_count,"friends":friends_help,
        "setemoji":set_friend_emoji,"admin":admin_list,"admins":admin_list,"report":report_admins}
    for name,fn in commands.items(): app.add_handler(CommandHandler(name,fn))
    for name in ACTIONS:
        app.add_handler(CommandHandler(name,action))
        app.add_handler(CommandHandler("add"+name,add_sticker))
        app.add_handler(CommandHandler("remove"+name,remove_sticker))
    app.add_handler(CallbackQueryHandler(banall_confirm,pattern=r"^banall:(yes|no)$"))
    app.add_handler(CallbackQueryHandler(ttt_move,pattern=r"^ttt:"))
    app.add_handler(CallbackQueryHandler(buttons,pattern=r"^(how|hot|actions|eco|puz|games|profile|commands|back)$"))
    app.add_handler(MessageHandler(filters.PHOTO & filters.CaptionRegex(r"^/waifu"),waifu))
    app.add_handler(MessageHandler(filters.Sticker.ALL,sticker_reply))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,chat_reply))
    return app

def main():
    build_application().run_polling()

if __name__=="__main__":
    main()
