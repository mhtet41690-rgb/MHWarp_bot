import os
import time
import uuid
import shutil
import subprocess
import qrcode
import sqlite3
from datetime import datetime, timedelta

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
PAYMENT_CHANNEL_ID = int(os.getenv("PAYMENT_CHANNEL_ID"))

WGCF_BIN = "./wgcf"

VIP_PRICE = (
    "🥰 VIP Lifetime 🥰\n\n"
    "💎 တစ်ခါဝယ်ထားယုံဖြင့် တစ်သက်စာ အသုံးပြုလို့ရပါသည်\n"
    "💵 Price: 3000 Ks\n"
    "📆 VIP → တစ်ရက်တစ်ခါ Generate"
)

VIP_TUTORIAL_VIDEO = "BAACAgUAAxkBAAIB9WmS1Mwvr42_VTJgDBs_nD8DN5-lAAL0GAACIkeZVPJRAAF0x4zJMzoE"

VIP_TUTORIAL_TEXT = (
    "📘 VIP Tutorial\n\n"
    "1️⃣ V2ray / V2Box App install\n"
    "2️⃣ https://mhwarp.netlify.app/mh.txt\n"
    "3️⃣ Link ကို copy ယူပြီး video အတိုင်းလုပ်ပါ"
)

# ================= KEYBOARD =================
MAIN_KB = ReplyKeyboardMarkup(
    [["⚡ Generate WARP", "💎 VIP Info"], ["📢 Join Channel"]],
    resize_keyboard=True
)

VIP_FREE_KB = ReplyKeyboardMarkup(
    [["💰 Buy VIP"], ["🔙 Back"]],
    resize_keyboard=True
)

VIP_BACK_KB = ReplyKeyboardMarkup(
    [["🔙 Back"]],
    resize_keyboard=True
)

# ================= SQLITE =================
DB_PATH = "/data/users.db"
os.makedirs("/data", exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    vip INTEGER DEFAULT 0,
    last INTEGER DEFAULT 0
)
""")
conn.commit()

# ================= HELPERS =================
def now_ts():
    return int(time.time())

def remaining(sec):
    d = sec // 86400
    h = (sec % 86400) // 3600
    m = (sec % 3600) // 60
    return f"{d}ရက် {h}နာရီ {m}မိနစ်"

# ================= CHANNEL CHECK =================
async def is_joined_channel(bot, user_id):
    try:
        member = await bot.get_chat_member(
            chat_id=f"@{CHANNEL_USERNAME}",
            user_id=user_id
        )
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ================= DB =================
def get_user(uid):
    cur.execute("SELECT vip,last FROM users WHERE user_id=?", (str(uid),))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO users VALUES (?,?,?)", (str(uid), 0, 0))
        conn.commit()
        return {"vip": False, "last": 0}
    return {"vip": bool(r[0]), "last": r[1]}

def set_vip(uid, v=True):
    cur.execute("UPDATE users SET vip=? WHERE user_id=?", (1 if v else 0, str(uid)))
    if cur.rowcount == 0:
        cur.execute("INSERT INTO users VALUES (?,?,?)", (str(uid), 1 if v else 0, 0))
    conn.commit()

def set_last(uid):
    cur.execute("UPDATE users SET last=? WHERE user_id=?", (now_ts(), str(uid)))
    conn.commit()

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 မင်္ဂလာပါ\nMenu ရွေးပါ 👇",
        reply_markup=MAIN_KB
    )

# ================= MENU =================
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.message.from_user.id
    user = get_user(uid)
    now = datetime.now()

    if text == "📢 Join Channel":
        await update.message.reply_text(f"https://t.me/{CHANNEL_USERNAME}")

    elif text == "💎 VIP Info":
        if user["vip"]:
            await context.bot.send_video(uid, VIP_TUTORIAL_VIDEO)
            await context.bot.send_message(uid, VIP_TUTORIAL_TEXT)
        else:
            await update.message.reply_text(
                VIP_PRICE,
                reply_markup=VIP_FREE_KB
            )

    elif text == "💰 Buy VIP":
        await update.message.reply_text(
            "💳 Payment Screenshot ကို ပို့ပါ",
            reply_markup=VIP_BACK_KB
        )

    elif text == "🔙 Back":
        await update.message.reply_text("🏠 Main Menu", reply_markup=MAIN_KB)

    elif text == "⚡ Generate WARP":

        joined = await is_joined_channel(context.bot, uid)
        if not joined:
            await update.message.reply_text(
                f"🚫 Channel Join လုပ်ပါ\nhttps://t.me/{CHANNEL_USERNAME}"
            )
            return

        if uid != ADMIN_ID and user["last"]:
            limit = 1 if user["vip"] else 7
            nt = datetime.fromtimestamp(user["last"]) + timedelta(days=limit)
            if now < nt:
                await update.message.reply_text(
                    f"⏳ ကျန်ချိန်: {remaining(int((nt-now).total_seconds()))}"
                )
                return

        await update.message.reply_text("⚙️ Generating...")

        try:
            subprocess.run([WGCF_BIN, "register", "--accept-tos"], check=True)
            subprocess.run([WGCF_BIN, "generate"], check=True)

            conf = f"WARP_{uuid.uuid4().hex[:8]}.conf"
            png = conf.replace(".conf", ".png")
            shutil.move("wgcf-profile.conf", conf)

            img = qrcode.make(open(conf).read())
            img.save(png)

            await update.message.reply_document(open(conf, "rb"))
            await update.message.reply_photo(open(png, "rb"))

            if uid != ADMIN_ID:
                set_last(uid)

            os.remove(conf)
            os.remove(png)

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

# ================= PAYMENT PHOTO =================
async def payment_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    caption = (
        "💰 VIP Payment Screenshot\n\n"
        f"👤 User ID: {user.id}\n"
        f"👤 Name: {user.full_name}\n"
        f"👤 Username: @{user.username if user.username else 'None'}"
    )

    await context.bot.send_photo(
        chat_id=PAYMENT_CHANNEL_ID,
        photo=update.message.photo[-1].file_id,
        caption=caption
    )

    await update.message.reply_text("✅ Screenshot ပို့ပြီးပါပြီ")

# ================= VIDEO ID HANDLER =================
async def get_video_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video
    if not video:
        return

    text = (
        "🎥 Video Info\n\n"
        f"🆔 File ID:\n{video.file_id}\n\n"
        f"🔑 Unique ID:\n{video.file_unique_id}\n\n"
        f"⏱ Duration: {video.duration} sec"
    )
    await update.message.reply_text(text)

# ================= ADMIN =================
async def approvevip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    set_vip(uid, True)
    await update.message.reply_text(f"✅ VIP Approved {uid}")
    await context.bot.send_message(uid, "🎉 VIP Activated!")

async def rejectvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    set_vip(uid, False)
    await update.message.reply_text(f"❌ VIP Rejected {uid}")

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approvevip", approvevip))
    app.add_handler(CommandHandler("rejectvip", rejectvip))

    app.add_handler(MessageHandler(filters.PHOTO, payment_photo))
    app.add_handler(MessageHandler(filters.VIDEO, get_video_id))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu))

    print("🤖 BOT RUNNING")
    app.run_polling()
