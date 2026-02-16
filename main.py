import os
import time
import uuid
import shutil
import subprocess
import qrcode
import sqlite3
import requests
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
WGCF_URL = "https://github.com/ViRb3/wgcf/releases/latest/download/wgcf_2.2.30_linux_amd64"

VIP_PRICE = (
    "🥰 VIP Lifetime 🥰\n\n"
    "💎 တစ်ခါဝယ်ထားယုံဖြင့် တစ်သက်စာ အသုံးပြုလို့ရသွားမှာပါ။\n"
    "💵 Price: 3000 Ks\n"
    "📆 VIP → တစ်ရက်တစ်ခါ Generate"
)

VIP_TUTORIAL_VIDEO = "BAACAgUAAxkBAAIB9WmS1Mwvr42_VTJgDBs_nD8DN5-lAAL0GAACIkeZVPJRAAF0x4zJMzoE"

VIP_TUTORIAL_TEXT = (
    "📘 VIP Tutorial\n\n"
    "1️⃣ V2box App Install\n"
    "2️⃣ https://mhwarp.netlify.app/mh.txt\n"
    "3️⃣ Video အတိုင်းလုပ်ပါ"
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

# ================= WGCF =================
def setup_wgcf():
    if not os.path.exists(WGCF_BIN):
        r = requests.get(WGCF_URL)
        with open("wgcf", "wb") as f:
            f.write(r.content)
        os.chmod("wgcf", 0o755)

def reset_wgcf():
    for f in ["wgcf-account.toml", "wgcf-profile.conf"]:
        if os.path.exists(f):
            os.remove(f)

# ================= HELPERS =================
def now_ts():
    return int(time.time())

def remaining(sec):
    d = sec // 86400
    h = (sec % 86400) // 3600
    m = (sec % 3600) // 60
    return f"{d}ရက် {h}နာရီ {m}မိနစ်"

# ================= CHANNEL CHECK =================
async def is_joined_channel(bot, uid):
    try:
        m = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", uid)
        return m.status in ("member", "administrator", "creator")
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

def vip_stats_text(uid):
    u = get_user(uid)
    return (
        "📊 VIP Stats\n\n"
        f"👤 Status : {'💎 VIP' if u['vip'] else '❌ Free'}\n"
        f"⚡ Limit : {'နေ့စဉ် ၁ ကြိမ်' if u['vip'] else '၇ ရက်တစ်ကြိမ်'}"
    )

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 မင်္ဂလာပါ", reply_markup=MAIN_KB)

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
            await update.message.reply_text(vip_stats_text(uid))
            await context.bot.send_video(uid, VIP_TUTORIAL_VIDEO)
            await context.bot.send_message(uid, VIP_TUTORIAL_TEXT)
        else:
            await update.message.reply_text(vip_stats_text(uid) + "\n\n" + VIP_PRICE, reply_markup=VIP_FREE_KB)

    elif text == "💰 Buy VIP":
        await update.message.reply_text("💳 Screenshot ကို ဒီ bot ထဲပို့ပါ", reply_markup=VIP_BACK_KB)

    elif text == "🔙 Back":
        await update.message.reply_text("🏠 Main Menu", reply_markup=MAIN_KB)

    elif text == "⚡ Generate WARP":

        if not await is_joined_channel(context.bot, uid):
            await update.message.reply_text(f"🚫 Channel Join လုပ်ပါ\nhttps://t.me/{CHANNEL_USERNAME}")
            return

        if uid != ADMIN_ID and user["last"]:
            limit = 1 if user["vip"] else 7
            nt = datetime.fromtimestamp(user["last"]) + timedelta(days=limit)
            if now < nt:
                await update.message.reply_text(f"⏳ ကျန်ချိန်: {remaining(int((nt-now).total_seconds()))}")
                return

        await update.message.reply_text("⚙️ Generating...")

        try:
            setup_wgcf()
            reset_wgcf()

            subprocess.run([WGCF_BIN, "register", "--accept-tos"], check=True, timeout=30)
            subprocess.run([WGCF_BIN, "generate"], check=True, timeout=30)

            conf = f"WARP_{uuid.uuid4().hex[:8]}.conf"
            png = conf.replace(".conf", ".png")

            shutil.move("wgcf-profile.conf", conf)

            with open(conf, "r") as f:
                img = qrcode.make(f.read())
                img.save(png)

            await update.message.reply_document(open(conf, "rb"))
            await update.message.reply_photo(open(png, "rb"))

            if uid != ADMIN_ID:
                set_last(uid)

            os.remove(conf)
            os.remove(png)

        except Exception as e:
            await update.message.reply_text(f"❌ Error:\n{e}")

# ================= PAYMENT PHOTO =================
async def payment_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.message.from_user
        uid = user.id
        username = f"@{user.username}" if user.username else "No username"

        caption = (
            "💰 VIP Payment Screenshot\n\n"
            f"👤 User ID: {uid}\n"
            f"👤 Name: {user.full_name}\n"
            f"👤 Username: {username}\n"
            f"🔗 Profile: {profile_link}"
        )

        await context.bot.send_photo(
            chat_id=PAYMENT_CHANNEL_ID,
            photo=update.message.photo[-1].file_id,
            caption=caption
        )

        await update.message.reply_text(
            "✅ Screenshot ပို့ပြီးပါပြီ\n"
            "⏳admin စစ်ဆေးနေပါသည်\n"
            "🙏 ခဏစောင့်ပါ"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ================= ADMIN =================
async def approvevip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    set_vip(uid, True)
    await update.message.reply_text(f"✅ VIP Approved {uid}")
    await context.bot.send_message(uid, "🎉 VIP Activated")

async def rejectvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    uid = int(context.args[0])
    set_vip(uid, False)
    await update.message.reply_text(f"❌ VIP Rejected {uid}")

# ================= MAIN =================
if __name__ == "__main__":
    setup_wgcf()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approvevip", approvevip))
    app.add_handler(CommandHandler("rejectvip", rejectvip))
    app.add_handler(MessageHandler(filters.PHOTO, payment_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu))

    print("🤖 BOT RUNNING (GENERATE FIXED)")
    app.run_polling()
