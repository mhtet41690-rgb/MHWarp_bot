import os
import time
import uuid
import shutil
import subprocess
import requests
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
PAYMENT_CHANNEL_ID = int(os.getenv("PAYMENT_CHANNEL_ID", "0"))

WGCF_URL = "https://github.com/ViRb3/wgcf/releases/latest/download/wgcf_2.2.30_linux_amd64"
WGCF_BIN = "./wgcf"

ENDPOINT_IP = "162.159.192.1"
ENDPOINT_PORT = 500

VIP_PRICE = (
    "🥰 VIP Lifetime 🥰\n\n"
    "💎 Unlimited Server Access\n"
    "💵 Price: 5000 Ks\n"
    "📆 VIP → တစ်ရက်တစ်ခါ Generate"
)

BANKING_TEXT = (
    "💳 Payment Methods\n\n"
    "🏦 KPay – 09982383696\n"
    "🏦 WavePay – 09972752831\n\n"
    "📸 Screenshot ကို ဒီ bot ထဲမှာပို့ပါ"
)

VIP_TUTORIAL_VIDEO = "PUT_YOUR_VIDEO_FILE_ID"

VIP_TUTORIAL_TEXT = (
    "📘 VIP Tutorial\n\n"
    "1️⃣ WireGuard App ကို Install လုပ်ပါ\n"
    "2️⃣ Generate WARP ကိုနှိပ်ပါ\n"
    "3️⃣ QR Code ကို Scan လုပ်ပါ\n"
    "4️⃣ Connect နှိပ်ပြီး အသုံးပြုပါ\n\n"
    "⚠️ VIP User များသည် နေ့စဉ် ၁ ကြိမ် Generate လုပ်နိုင်ပါသည်"
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

pending_payments = set()

# ================= HELPERS =================
def now_ts():
    return int(time.time())

def remaining(sec):
    d = sec // 86400
    h = (sec % 86400) // 3600
    m = (sec % 3600) // 60
    return f"{d}ရက် {h}နာရီ {m}မိနစ်"

# ================= DB =================
def get_user(uid):
    cur.execute("SELECT vip,last FROM users WHERE user_id=?", (str(uid),))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO users VALUES (?,?,?)", (str(uid),0,0))
        conn.commit()
        return {"vip": False, "last": 0}
    return {"vip": bool(r[0]), "last": r[1]}

def set_vip(uid, v=True):
    cur.execute("UPDATE users SET vip=? WHERE user_id=?", (1 if v else 0, str(uid)))
    if cur.rowcount == 0:
        cur.execute("INSERT INTO users VALUES (?,?,?)", (str(uid),1 if v else 0,0))
    conn.commit()

def set_last(uid):
    cur.execute("UPDATE users SET last=? WHERE user_id=?", (now_ts(), str(uid)))
    conn.commit()

# ================= VIP STATS =================
def vip_stats_text(uid):
    user = get_user(uid)
    status = "💎 VIP" if user["vip"] else "❌ Free"
    gen = "နေ့စဉ် ၁ ကြိမ် Generate" if user["vip"] else "၇ ရက်တစ်ကြိမ် Generate"

    return (
        "📊 VIP Stats\n\n"
        f"👤 Your Status : {status}\n"
        f"⚡ Generate Limit : {gen}\n"
    )

# ================= TELEGRAM =================
async def is_joined(bot, uid):
    try:
        m = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", uid)
        return m.status in ("member","administrator","creator")
    except:
        return False

# ================= WGCF =================
def setup_wgcf():
    if not os.path.exists(WGCF_BIN):
        r = requests.get(WGCF_URL)
        open("wgcf","wb").write(r.content)
        os.chmod("wgcf",0o755)

def reset_wgcf():
    for f in ["wgcf-account.toml","wgcf-profile.conf"]:
        if os.path.exists(f):
            os.remove(f)

def patch_endpoint(conf):
    out=[]
    for l in open(conf):
        if l.startswith("Endpoint"):
            l=f"Endpoint = {ENDPOINT_IP}:{ENDPOINT_PORT}\n"
        out.append(l)
    open(conf,"w").writelines(out)

def make_qr(conf,png):
    img=qrcode.make(open(conf).read())
    img.save(png)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 မင်္ဂလာပါ\nMenu ရွေးပါ 👇", reply_markup=MAIN_KB)

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
            await context.bot.send_video(uid, VIP_TUTORIAL_VIDEO, caption="🎬 VIP Tutorial")
            await context.bot.send_message(uid, VIP_TUTORIAL_TEXT)
        else:
            await update.message.reply_text(
                vip_stats_text(uid) + "\n" + VIP_PRICE,
                reply_markup=VIP_FREE_KB
            )

    elif text == "💰 Buy VIP":
        pending_payments.add(uid)
        await update.message.reply_text(BANKING_TEXT, reply_markup=VIP_BACK_KB)

    elif text == "🔙 Back":
        await update.message.reply_text("🏠 Main Menu", reply_markup=MAIN_KB)

    elif text == "⚡ Generate WARP":
        if not await is_joined(context.bot, uid):
            await update.message.reply_text("⛔ Channel join လုပ်ပါ")
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
            setup_wgcf()
            reset_wgcf()
            subprocess.run([WGCF_BIN,"register","--accept-tos"],check=True)
            subprocess.run([WGCF_BIN,"generate"],check=True)

            patch_endpoint("wgcf-profile.conf")

            conf=f"WARP_{uuid.uuid4().hex[:8]}.conf"
            png=conf.replace(".conf",".png")
            shutil.move("wgcf-profile.conf",conf)
            make_qr(conf,png)

            await update.message.reply_document(open(conf,"rb"))
            await update.message.reply_photo(open(png,"rb"), caption="📱 QR Code (WireGuard App)")

            if uid != ADMIN_ID:
                set_last(uid)

            os.remove(conf)
            os.remove(png)

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

# ================= PAYMENT PHOTO =================
async def payment_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid not in pending_payments:
        return

    p = update.message.photo[-1]
    uname = update.message.from_user.username or "No username"

    await context.bot.send_photo(
        PAYMENT_CHANNEL_ID,
        p.file_id,
        caption=f"💰 VIP Payment\n👤 {uid}\n@{uname}"
    )

    pending_payments.remove(uid)
    await update.message.reply_text("✅ Screenshot ပို့ပြီးပါပြီ")

# ================= ADMIN =================
async def approvevip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    uid = int(context.args[0])
    set_vip(uid, True)

    await update.message.reply_text(f"✅ VIP Approved {uid}")

    await context.bot.send_message(uid, "🎉 VIP Activated!")
    await context.bot.send_message(uid, vip_stats_text(uid))
    await context.bot.send_video(uid, VIP_TUTORIAL_VIDEO, caption="🎬 VIP Tutorial")
    await context.bot.send_message(uid, VIP_TUTORIAL_TEXT)

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approvevip", approvevip))
    app.add_handler(MessageHandler(filters.PHOTO, payment_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu))

    print("🤖 BOT RUNNING")
    app.run_polling()
