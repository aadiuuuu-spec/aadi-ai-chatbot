# Aadi AI Telegram Bot

A Telegram bot with Groq-powered AI chat, user profiles, coins, daily rewards, work cooldowns, a leaderboard, puzzles, and image Q&A.

## Requirements
- Python 3.10+
- Telegram bot token from [@BotFather](https://t.me/BotFather)
- Groq API key from [Groq Console](https://console.groq.com/)

## Setup
1. Clone this repository.
2. Create a virtual environment: `python -m venv .venv`
3. Activate it (Windows: `.venv\\Scripts\\activate`; macOS/Linux: `source .venv/bin/activate`).
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and fill in your secrets. Export those variables in your terminal (or use a local dotenv loader).
6. Run: `python bot.py`

The SQLite database is created automatically in `data/`, which is excluded from Git.

## Commands
- `/start`, `/help`
- `/profile`
- `/daily` — 250 coins once per day
- `/work` — 40–120 coins, one-hour cooldown
- `/leaderboard`
- `/puzzle` — correct answer earns 50 coins
- `/waifu` — image Q&A for anime/game images (send with an image or reply to one)

In private chats, ordinary text messages go to the AI. In groups, mention the bot.

## Environment
See `.env.example`. Never commit `.env`, API keys, bot tokens, database files, or personal user data.

This starter intentionally omits destructive moderation commands and romantic roleplay. The bot identifies itself as an AI chatbot and keeps interactions age-appropriate.
