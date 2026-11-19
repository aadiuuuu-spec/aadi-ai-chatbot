import os, sqlite3, random, time, logging
from datetime import date
from pathlib import Path
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN=os.getenv("BOT_TOKEN","").strip()
KEY=os.getenv("GROQ_API_KEY","").strip()
MODEL=os.getenv("GROQ_MODEL","llama-3.3-70b-versatile")
DB=os.getenv("DB_PATH","data/aadi.sqlite3")
Path(DB).parent.mkdir(parents=True,exist_ok=True)
logging.basicConfig(level=logging.INFO)
log=logging.getLogger("aadi")
PUZZLES=[("What has keys but cannot open locks?","keyboard"),("What gets wetter as it dries?","towel"),("What has a face and two hands but no arms or legs?","clock"),("What goes up but never comes down?","age")]
SYSTEM=("You are Aadi, a friendly AI Telegram chatbot. Be concise and natural; use light Hinglish when appropriate. Never pretend to be human. Keep content age-appropriate; no sexual content, romantic roleplay, violent instructions, or wrongdoing.")

def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init():
 with conn() as c:c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT,coins INTEGER DEFAULT 500,xp INTEGER DEFAULT 0,level INTEGER DEFAULT 1,daily TEXT DEFAULT '',work REAL DEFAULT 0)")
def user(t):
 with conn() as c:
  c.execute("INSERT OR IGNORE INTO users(id,name) VALUES(?,?)",(t.id,t.first_name or "User"))
  c.execute("UPDATE users SET name=? WHERE id=?",(t.first_name or "User",t.id))
  return c.execute("SELECT * FROM users WHERE id=?",(t.id,)).fetchone()
def xp(uid,n=5):
 with conn() as c:
  r=c.execute("SELECT xp,level FROM users WHERE id=?",(uid,)).fetchone(); x,l=r["xp"]+n,r["level"]
  while x>=500+(l-1)*250:x-=500+(l-1)*250;l+=1
  c.execute("UPDATE users SET xp=?,level=? WHERE id=?",(x,l,uid))
async def ai(prompt):
 if not KEY:return "AI configure nahi hai. Owner ko GROQ_API_KEY set karna hoga."
 async with httpx.AsyncClient(timeout=35) as c:
  r=await c.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization":f"Bearer {KEY}"},json={"model":MODEL,"messages":[{"role":"system","content":SYSTEM},{"role":"user","content":prompt[:4000]}],"max_tokens":450})
  r.raise_for_status();return r.json()["choices"][0]["message"]["content"].strip()
async def start(u,c):
 user(u.effective_user);xp(u.effective_user.id,10);await u.message.reply_text(f"Hey {u.effective_user.first_name}! Main Aadi AI bot hoon. /help use karo.")
async def help_(u,c):
 await u.message.reply_text("/start /help /profile /daily /work /leaderboard /puzzle /waifu\nPrivate chat mein normal message bhejo for AI chat.")
async def profile(u,c):
 r=user(u.effective_user);await u.message.reply_text(f"{r['name']}\nCoins: {r['coins']}\nLevel: {r['level']} | XP: {r['xp']}")
async def daily(u,c):
 r=user(u.effective_user);d=date.today().isoformat()
 if r["daily"]==d:return await u.message.reply_text("Aaj ka reward le chuke ho. Kal aana!")
 with conn() as x:x.execute("UPDATE users SET coins=coins+250,daily=? WHERE id=?",(d,r["id"]))
 await u.message.reply_text("+250 daily coins 🎁")
async def work(u,c):
 r=user(u.effective_user);now=time.time()
 if now-r["work"]<3600:return await u.message.reply_text(f"{int((3600-now+r['work'])/60)} min baad try karo.")
 n=random.randint(40,120)
 with conn() as x:x.execute("UPDATE users SET coins=coins+?,work=? WHERE id=?",(n,now,r["id"]))
 await u.message.reply_text(f"+{n} coins 💼")
async def board(u,c):
 with conn() as x:rows=x.execute("SELECT name,coins,level FROM users ORDER BY coins DESC LIMIT 10").fetchall()
 await u.message.reply_text("🏆 LEADERBOARD\n"+"\n".join(f"{i}. {r['name']} — {r['coins']} coins (Lv.{r['level']})" for i,r in enumerate(rows,1)))
async def puzzle(u,c):
 q,a=random.choice(PUZZLES);c.user_data["answer"]=a;await u.message.reply_text("🧩 "+q+"\nAnswer bhejo.")
async def waifu(u,c):
 m=u.message;s=m if m.photo else (m.reply_to_message if m.reply_to_message and m.reply_to_message.photo else None)
 if not s:return await m.reply_text("Image bhejo ya image par reply karke /waifu likho.")
 if not KEY:return await m.reply_text("GROQ_API_KEY configure nahi hai.")
 try:
  f=await c.bot.get_file(s.photo[-1].file_id);raw=await f.download_as_bytearray()
  import base64
  async with httpx.AsyncClient(timeout=45) as h:
   r=await h.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization":f"Bearer {KEY}"},json={"model":os.getenv("VISION_MODEL","llama-4-scout-17b-16e-instruct"),"messages":[{"role":"user","content":[{"type":"text","text":"Describe this image. Discuss fictional anime/game characters if visible. Do not identify real people."},{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+base64.b64encode(bytes(raw)).decode()}}]}],"max_tokens":450})
   r.raise_for_status();await m.reply_text(r.json()["choices"][0]["message"]["content"][:4000])
 except Exception:log.exception("image request failed");await m.reply_text("Image analysis abhi fail hua.")
async def chat(u,c):
 m=u.message
 if not m or not m.text:return
 r=user(u.effective_user);xp(r["id"])
 a=c.user_data.pop("answer",None)
 if a:
  if m.text.strip().lower()==a:
   with conn() as x:x.execute("UPDATE users SET coins=coins+50 WHERE id=?",(r["id"],))
   return await m.reply_text("Correct! +50 coins 🎉")
  return await m.reply_text("Not quite. /puzzle try karo.")
 if u.effective_chat.type!="private":
  name=c.bot.username
  if not name or "@"+name.lower() not in m.text.lower():return
 try:await m.reply_text((await ai(m.text))[:4000])
 except httpx.HTTPError:log.exception("Groq error");await m.reply_text("AI service unavailable.")
def main():
 if not TOKEN:raise SystemExit("BOT_TOKEN missing. Set environment variables.")
 init();app=Application.builder().token(TOKEN).build()
 for n,f in [("start",start),("help",help_),("profile",profile),("daily",daily),("work",work),("leaderboard",board),("puzzle",puzzle),("waifu",waifu)]:app.add_handler(CommandHandler(n,f))
 app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,chat));app.run_polling()
if __name__=="__main__":main()
