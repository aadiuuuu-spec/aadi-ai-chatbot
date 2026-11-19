import asyncio
import hmac
import logging
import os

from fastapi import FastAPI, Header, HTTPException, Request
from telegram import Update

from bot import build_application

log = logging.getLogger("aadi.webhook")
app = FastAPI(title="Aadi Telegram Bot")
telegram_app = None
init_lock = asyncio.Lock()


async def get_telegram_app():
    global telegram_app
    if telegram_app is None:
        async with init_lock:
            if telegram_app is None:
                telegram_app = build_application()
                await telegram_app.initialize()
                await telegram_app.start()
    return telegram_app


@app.get("/")
@app.get("/api")
async def health():
    return {"ok": True, "service": "Aadi Telegram webhook"}


@app.post("/")
@app.post("/api")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(default=""),
):
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    if not expected or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, expected
    ):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    try:
        payload = await request.json()
        tg_app = await get_telegram_app()
        update = Update.de_json(payload, tg_app.bot)
        await tg_app.process_update(update)
    except HTTPException:
        raise
    except Exception:
        log.exception("Telegram update processing failed")
        raise HTTPException(status_code=500, detail="Update processing failed")

    return {"ok": True}


@app.post("/setup")
@app.post("/api/setup")
async def setup_webhook(
    x_setup_secret: str = Header(default=""),
):
    setup_secret = os.getenv("SETUP_SECRET", "")
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    deployment_host = os.getenv("VERCEL_URL", "")
    if not setup_secret or not hmac.compare_digest(x_setup_secret, setup_secret):
        raise HTTPException(status_code=403, detail="Invalid setup secret")
    if not webhook_secret or not deployment_host:
        raise HTTPException(
            status_code=500,
            detail="TELEGRAM_WEBHOOK_SECRET or VERCEL_URL is missing",
        )

    tg_app = await get_telegram_app()
    webhook_url = f"https://{deployment_host}/api"
    await tg_app.bot.set_webhook(
        url=webhook_url,
        secret_token=webhook_secret,
        allowed_updates=Update.ALL_TYPES,
    )
    return {"ok": True, "webhook": webhook_url}
