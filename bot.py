import os, sqlite3, random, time, logging, asyncio
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN", "").strip()
KEY = os.getenv("GROQ_API_KEY", "").strip()
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
DB_PATH = os.getenv("DB_PATH", "data/aadi.sqlite3")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("disha")

PUZZLES = [
    ("What has keys but cannot open locks?", "keyboard"),
    ("What gets wetter as it dries?", "towel"),
    ("What has a face and two hands but no arms or legs?", "clock"),
    ("What goes up but never comes down?", "age"),
]
DEVELOPER = "Aditya Kumar"
BOT_NAME = "Disha"

SYSTEM = (
    "You are Disha, a friendly AI Telegram chatbot. Be concise and natural; "
    "use light Hinglish when appropriate. Never pretend to be human. Keep "
    "content age-appropriate; no sexual content, romantic roleplay, violent "
    "instructions, or wrongdoing."
)


class PostgresCompat:
    """Small adapter so the same SQL works with local SQLite and hosted Postgres."""
    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row
        self.raw = psycopg.connect(url, row_factory=dict_row, connect_timeout=10)

    def __enter__(self):
        self.raw.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        return self.raw.__exit__(exc_type, exc, tb)

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
        c.execute(
            """CREATE TABLE IF NOT EXISTS users(
                id BIGINT PRIMARY KEY,
                name TEXT,
                coins INTEGER DEFAULT 500,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                daily TEXT DEFAULT '',
                work DOUBLE PRECISION DEFAULT 0
            )"""
        )


def user(t):
    with conn() as c:
        c.execute("INSERT INTO users(id,name) VALUES(?,?) ON CONFLICT(id) DO NOTHING",
                  (t.id, t.first_name or "User"))
        c.execute("UPDATE users SET name=? WHERE id=?", (t.first_name or "User", t.id))
        return c.execute("SELECT * FROM users WHERE id=?", (t.id,)).fetchone()


def xp(uid, n=5):
    with conn() as c:
        r = c.execute("SELECT xp,level FROM users WHERE id=?", (uid,)).fetchone()
        if not r:
            return
        x, level = r["xp"] + n, r["level"]
        while x >= 500 + (level - 1) * 250:
            x -= 500 + (level - 1) * 250
            level += 1
        c.execute("UPDATE users SET xp=?,level=? WHERE id=?", (x, level, uid))


async def ai(prompt):
    if not KEY:
        return "AI configure nahi hai. Owner ko GROQ_API_KEY set karna hoga."
    async with httpx.AsyncClient(timeout=35) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {KEY}"},
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt[:4000]},
                ],
                "max_tokens": 450,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


def main_menu():
    # Telegram primary button style gives the interface its blue accent.
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 PROFILE", callback_data="profile", style="primary"),
            InlineKeyboardButton("📜 COMMANDS", callback_data="help", style="primary"),
        ],
        [
            InlineKeyboardButton("💰 ECONOMY", callback_data="economy", style="primary"),
            InlineKeyboardButton("🎮 GAMES", callback_data="games", style="primary"),
        ],
        [
            InlineKeyboardButton("🎁 DAILY REWARD", callback_data="daily", style="primary"),
            InlineKeyboardButton("💼 WORK", callback_data="work", style="primary"),
        ],
        [InlineKeyboardButton("🏆 LEADERBOARD", callback_data="leaderboard", style="primary")],
    ])


def back_menu():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("‹  BACK TO MENU", callback_data="back", style="primary")
    ]])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = user(update.effective_user)
    xp(update.effective_user.id, 10)
    r = user(update.effective_user)
    name = update.effective_user.first_name or "there"
    await update.message.reply_text(
        f"✦  <b>D I S H A  /  AI COMPANION</b>\n"
        f"Your personal chat, games and rewards space.\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👋 Welcome, <b>{name}</b>\n"
        f"💰 <b>{r['coins']}</b> coins   ·   ⭐ <b>LV {r['level']}</b>   ·   ✨ <b>{r['xp']}</b> XP\n\n"
        f"<i>Choose a section to explore.</i>",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q:
        return
    await q.answer()
    section = q.data
    if section == "back":
        r = user(q.from_user)
        await q.edit_message_text(
            f"✦  <b>A A D I  /  AI COMPANION</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>{r['coins']}</b> coins   ·   ⭐ <b>LV {r['level']}</b>   ·   ✨ <b>{r['xp']}</b> XP\n\n"
            f"<i>Choose a section to explore.</i>",
            parse_mode="HTML", reply_markup=main_menu(),
        )
        return

    r = user(q.from_user)
    pages = {
        "profile": (
            "👤  <b>YOUR PROFILE</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"Name: <b>{r['name']}</b>\nCoins: <b>{r['coins']}</b>\n"
            f"Level: <b>{r['level']}</b>\nXP: <b>{r['xp']}</b>"
        ),
        "help": (
            "📜  <b>COMMAND CENTER</b>\n━━━━━━━━━━━━━━━━━━\n"
            "/start — Open main menu\n/profile — Your profile\n/daily — Claim daily coins\n"
            "/work — Earn coins\n/leaderboard — Top users\n/puzzle — Solve a puzzle\n"
            "/waifu — Describe an anime/game character from an image\n\n"
            "Private chat mein normal message bhejo to Disha se AI chat kar sakte ho."
        ),
        "economy": (
            "💰  <b>ECONOMY</b>\n━━━━━━━━━━━━━━━━━━\n"
            "/daily — Daily reward\n/work — Earn coins\n/leaderboard — Top users\n"
            "Rewards aur progress tumhare profile mein update hote hain."
        ),
        "games": (
            "🎮  <b>GAMES & DISCOVERY</b>\n━━━━━━━━━━━━━━━━━━\n"
            "/puzzle — Try a quick puzzle\n/waifu — Image-based anime/game character finder"
        ),
        "daily": "🎁  <b>DAILY REWARD</b>\n\nDaily reward claim karne ke liye /daily bhejo.",
        "work": "💼  <b>WORK</b>\n\nCoins earn karne ke liye /work bhejo.",
        "leaderboard": "🏆  <b>LEADERBOARD</b>\n\nTop users dekhne ke liye /leaderboard bhejo.",
    }
    await q.edit_message_text(
        pages.get(section, "Disha AI"),
        parse_mode="HTML",
        reply_markup=back_menu(),
    )


async def help_(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start /help /profile /daily /work /leaderboard /puzzle /waifu /about\n"
        "Private chat mein normal message bhejo for AI chat."
    )


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"✦ <b>Disha AI</b>\nYour AI chat companion.\n\nDeveloper: <b>{DEVELOPER}</b>",
        parse_mode="HTML",
    )


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = user(update.effective_user)
    await update.message.reply_text(
        f"{r['name']}\nCoins: {r['coins']}\nLevel: {r['level']} | XP: {r['xp']}"
    )


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = user(update.effective_user)
    today = date.today().isoformat() if not DATABASE_URL else date.today().isoformat()
    # Use India-local calendar date for the daily reward.
    today = __import__("datetime").datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
    if r["daily"] == today:
        return await update.message.reply_text("Aaj ka reward le chuke ho. Kal aana!")
    with conn() as c:
        c.execute("UPDATE users SET coins=coins+250,daily=? WHERE id=?", (today, r["id"]))
    await update.message.reply_text("+250 daily coins 🎁")


async def work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = user(update.effective_user)
    now = time.time()
    if now - r["work"] < 3600:
        return await update.message.reply_text(
            f"{int((3600 - now + r['work']) / 60)} min baad try karo."
        )
    amount = random.randint(40, 120)
    with conn() as c:
        c.execute("UPDATE users SET coins=coins+?,work=? WHERE id=?",
                  (amount, now, r["id"]))
    await update.message.reply_text(f"+{amount} coins 💼")


async def board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with conn() as c:
        rows = c.execute(
            "SELECT name,coins,level FROM users ORDER BY coins DESC LIMIT 10"
        ).fetchall()
    if not rows:
        return await update.message.reply_text("Abhi leaderboard khaali hai.")
    await update.message.reply_text(
        "🏆 LEADERBOARD\n" +
        "\n".join(
            f"{i}. {r['name']} — {r['coins']} coins (Lv.{r['level']})"
            for i, r in enumerate(rows, 1)
        )
    )


async def puzzle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question, answer = random.choice(PUZZLES)
    context.user_data["answer"] = answer
    await update.message.reply_text("🧩 " + question + "\nAnswer bhejo.")


async def waifu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    source = message if message.photo else (
        message.reply_to_message
        if message.reply_to_message and message.reply_to_message.photo else None
    )
    if not source:
        return await message.reply_text("Image bhejo ya image par reply karke /waifu likho.")
    if not KEY:
        return await message.reply_text("GROQ_API_KEY configure nahi hai.")
    try:
        file = await context.bot.get_file(source.photo[-1].file_id)
        raw = await file.download_as_bytearray()
        import base64
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {KEY}"},
                json={
                    "model": os.getenv("VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"),
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Describe this image. Discuss fictional anime/game characters if visible. Do not identify real people.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/jpeg;base64," +
                                    base64.b64encode(bytes(raw)).decode()
                                },
                            },
                        ],
                    }],
                    "max_tokens": 450,
                },
            )
            response.raise_for_status()
            await message.reply_text(
                response.json()["choices"][0]["message"]["content"][:4000]
            )
    except Exception:
        log.exception("Image request failed")
        await message.reply_text("Image analysis abhi fail hua.")


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    r = user(update.effective_user)
    xp(r["id"])
    answer = context.user_data.pop("answer", None)
    if answer:
        if message.text.strip().lower() == answer:
            with conn() as c:
                c.execute("UPDATE users SET coins=coins+50 WHERE id=?", (r["id"],))
            return await message.reply_text("Correct! +50 coins 🎉")
        return await message.reply_text("Not quite. /puzzle try karo.")
    if update.effective_chat.type != "private":
        username = context.bot.username
        if not username or "@" + username.lower() not in message.text.lower():
            return
    try:
        await message.reply_text((await ai(message.text))[:4000])
    except httpx.HTTPError:
        log.exception("Groq error")
        await message.reply_text("AI service unavailable.")


def build_application():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN missing. Set environment variables.")
    init()
    application = Application.builder().token(TOKEN).build()
    for name, handler in [
        ("start", start), ("help", help_), ("about", about), ("profile", profile),
        ("daily", daily), ("work", work), ("leaderboard", board),
        ("puzzle", puzzle), ("waifu", waifu),
    ]:
        application.add_handler(CommandHandler(name, handler))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^(profile|help|economy|games|daily|work|leaderboard|back)$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    return application


def main():
    application = build_application()
    application.run_polling()


if __name__ == "__main__":
    main()
