"""Aadi Telegram bot: AI chat, profile/economy, puzzles and image Q&A.

Configuration is read from environment variables. Never commit real tokens or database files.
"""
from __future__ import annotations

import base64
import logging
import os
import random
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0") or "0")
BOT_NAME = os.getenv("BOT_NAME", "Aadi")
DB_PATH = os.getenv("DB_PATH", "data/aadi.sqlite3")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
VISION_MODEL = os.getenv("VISION_MODEL", "llama-4-scout-17b-16e-instruct")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("aadi-bot")
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = (
    "You are Aadi, a friendly Telegram chatbot. Be concise, helpful, and natural. "
    "You may use light Hinglish when the user does. You are an AI chatbot; "
    "never pretend to be a human or claim real-world experiences. "
    "Keep interactions age-appropriate. Do not produce sexual content, "
    "romantic roleplay, instructions for violence, or help with wrongdoing."
)
PUZZLES = [
    ("What has keys but cannot open locks?", "keyboard"),
    ("What gets wetter as it dries?", "towel"),
    ("What has a face and two hands but no arms or legs?", "clock"),
    ("What goes up but never comes down?", "age"),
]


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                coins INTEGER NOT NULL DEFAULT 500,
                xp INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 1,
                streak INTEGER NOT NULL DEFAULT 0,
                last_active TEXT NOT NULL DEFAULT '',
                daily_at TEXT NOT NULL DEFAULT '',
                work_at REAL NOT NULL DEFAULT 0
            )
        """)


def ensure_user(tg_user) -> sqlite3.Row:
    with connect() as con:
        con.execute(
            "INSERT OR IGNORE INTO users(user_id,name) VALUES(?,?)",
            (tg_user.id, tg_user.first_name or "User"),
        )
        con.execute(
            "UPDATE users SET name=? WHERE user_id=?",
            (tg_user.first_name or "User", tg_user.id),
        )
        return con.execute(
            "SELECT * FROM users WHERE user_id=?", (tg_user.id,)
        ).fetchone()


def add_xp(user_id: int, amount: int = 10) -> None:
    with connect() as con:
        row = con.execute(
            "SELECT xp,level FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
        xp, level = row["xp"] + amount, row["level"]
        while xp >= 500 + (level - 1) * 250:
            xp -= 500 + (level - 1) * 250
            level += 1
        con.execute(
            "UPDATE users SET xp=?,level=? WHERE user_id=?",
            (xp, level, user_id),
        )


async def groq_chat(prompt: str) -> str:
    if not GROQ_API_KEY:
        return "AI chat abhi configure nahi hua. Owner ko GROQ_API_KEY set karna hoga."
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt[:4000]},
        ],
        "temperature": 0.7,
        "max_tokens": 450,
    }
    async with httpx.AsyncClient(timeout=35) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers, json=payload,
        )
        response.raise_for_status()
        data = response.json()
    return data["choices"][0]["message"]["content"].strip()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = ensure_user(update.effective_user)
    add_xp(u["user_id"], 10)
    await update.message.reply_text(
        f"Hey {update.effective_user.first_name}! Main {BOT_NAME} hoon.\n"
        "AI chat, games aur coins ke liye /help use karo."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 AADI BOT COMMANDS\n"
        "/start - start bot\n/help - command list\n"
        "/profile - your stats\n/daily - claim daily coins\n"
        "/work - earn coins\n/leaderboard - top players\n"
        "/puzzle - get a puzzle\n/waifu - ask about an anime/game image\n\n"
        "Normal message bhejkar AI se chat kar sakte ho. "
        "Image ke saath /waifu caption ya reply use karo."
    )


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = ensure_user(update.effective_user)
    await update.message.reply_text(
        f"👤 {u['name']}\n🪙 Coins: {u['coins']}\n"
        f"⭐ Level: {u['level']}\n✨ XP: {u['xp']}\n"
        f"🔥 Streak: {u['streak']}"
    )


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = ensure_user(update.effective_user)
    today = date.today().isoformat()
    if u["daily_at"] == today:
        return await update.message.reply_text("Aaj ka daily reward le chuke ho. Kal aana!")
    with connect() as con:
        con.execute(
            "UPDATE users SET coins=coins+250,daily_at=? WHERE user_id=?",
            (today, u["user_id"]),
        )
    await update.message.reply_text("🎁 Daily reward: +250 coins!")


async def work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    u = ensure_user(update.effective_user)
    now = time.time()
    if now - u["work_at"] < 3600:
        remaining = int(3600 - (now - u["work_at"]))
        return await update.message.reply_text(f"Work cooldown: {remaining // 60} min baad try karo.")
    reward = random.randint(40, 120)
    with connect() as con:
        con.execute(
            "UPDATE users SET coins=coins+?,work_at=? WHERE user_id=?",
            (reward, now, u["user_id"]),
        )
    await update.message.reply_text(f"💼 Kaam complete! +{reward} coins.")


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with connect() as con:
        rows = con.execute(
            "SELECT name,coins,level FROM users ORDER BY coins DESC LIMIT 10"
        ).fetchall()
    if not rows:
        return await update.message.reply_text("Leaderboard abhi empty hai.")
    lines = ["🏆 TOP PLAYERS"]
    lines.extend(
        f"{i}. {r['name']} — {r['coins']} coins | Lv.{r['level']}"
        for i, r in enumerate(rows, 1)
    )
    await update.message.reply_text("\n".join(lines))


async def puzzle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question, answer = random.choice(PUZZLES)
    context.user_data["puzzle_answer"] = answer
    await update.message.reply_text(
        f"🧩 Puzzle: {question}\nAnswer dene ke liye normal message bhejo."
    )


async def image_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not GROQ_API_KEY:
        return await update.message.reply_text("Image AI configure nahi hai; owner ko GROQ_API_KEY set karna hoga.")
    message = update.message
    photo = message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = await file.download_as_bytearray()
    caption = " ".join(context.args).strip() or (message.caption or "").replace("/waifu", "").strip()
    prompt = caption or "Describe this image. If it appears to show a fictional anime or game character, discuss visible details without guessing beyond the image."
    encoded = base64.b64encode(bytes(image_bytes)).decode("ascii")
    payload = {
        "model": VISION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt + " Do not identify a real person."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
            ],
        }],
        "max_tokens": 450,
    }
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json=payload,
            )
            response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"].strip()
        await message.reply_text(answer[:4000])
    except (httpx.HTTPError, KeyError, ValueError):
        log.exception("Image analysis failed")
        await message.reply_text("Image analysis abhi fail ho gaya. Thodi der baad try karo.")


async def waifu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.photo:
        return await image_question(update, context)
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        context.args = context.args or []
        # The reply photo is handled using the same message flow.
        fake_update = update
        fake_update.message = update.message.reply_to_message
        await image_question(fake_update, context)
        return
    await update.message.reply_text("Kisi image par reply karke /waifu likho, ya image ke caption mein /waifu likho.")


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    u = ensure_user(update.effective_user)
    add_xp(u["user_id"], 5)
    guess = context.user_data.pop("puzzle_answer", None)
    if guess:
        if update.message.text.strip().lower() == guess:
            with connect() as con:
                con.execute("UPDATE users SET coins=coins+50 WHERE user_id=?", (u["user_id"],))
            await update.message.reply_text("Sahi jawab! 🎉 +50 coins.")
            return
        await update.message.reply_text("Not quite. /puzzle se naya puzzle try karo.")
        return
    text = update.message.text.strip()
    if update.effective_chat.type != "private" and not (
        context.bot.username and f"@{context.bot.username.lower()}" in text.lower()
    ):
        return
    try:
        answer = await groq_chat(text)
        await update.message.reply_text(answer[:4000])
    except httpx.HTTPError:
        log.exception("Groq request failed")
        await update.message.reply_text("AI service abhi unavailable hai. Baad mein try karo.")


async def post_init(app: Application) -> None:
    await app.bot.set_my_commands([
        ("start", "Start the bot"), ("help", "Show commands"),
        ("profile", "Show your stats"), ("daily", "Claim daily coins"),
        ("work", "Earn coins"), ("leaderboard", "Top players"),
        ("puzzle", "Get a puzzle"), ("waifu", "Analyze an anime/game image"),
    ])


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN missing. Copy .env.example to .env and configure it.")
    init_db()
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("work", work))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("puzzle", puzzle))
    app.add_handler(CommandHandler("waifu", waifu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    log.info("Starting %s", BOT_NAME)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
