import os
import time
import uuid
import shutil
import subprocess
import requests
import qrcode
import sqlite3
from datetime import datetime, timedelta

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
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
    "💎 Lifetime Unlimited Access\n"
    "💵 5000 Ks\n"
    "📆 VIP – တစ်ရက်တစ်ခါ generate"
)

BANKING_TEXT = (
    "💳 Payment Methods\n\n"
    "🏦 Kpay – 09982383696\n"
    "🏦 WavePay – 09972752831\n\n"
    "📸 Screenshot ကို ဒီ bot ထဲမှာပို့ပါ"
)

# ================= KEYBOARDS =================
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["⚡ Generate WARP", "💎 VIP Info"],
        ["📢 Join Channel"]
    ],
    resize_keyboard=True
)

VIP_KEYBOARD_FREE = ReplyKeyboardMarkup(
    [
        ["💰 Buy VIP"],
        ["🔙 Back"]
    ],
    resize_keyboard=True
)

VIP_KEYBOARD_ACTIVE = ReplyKeyboardMarkup(
    [
        ["✅ VIP Activated"],
        ["🔙 Back"]
    ],
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

def remaining_time(sec):
    d = sec // 86400
    h = (sec % 86400) // 3600
    m = (sec % 3600) // 60
    return f"{d}ရက် {h}နာရီ {m}မိနစ်"

# ================= DB =================
def get_user(uid):
    cur.execute("SELECT vip, last FROM users WHERE user_id=?", (str(uid),))
    r = cur.fetchone()
    if not r:
        cur.execute(
            "INSERT INTO users (user_id,vip,last) VALUES (?,0,0)",
            (str(uid),)
        )
        conn.commit()
        return {"vip": False, "last": 0}
    return {"vip": bool(r[0]), "last": r[1]}

def set_vip(uid, vip=True):
    cur.execute(
        "UPDATE users SET vip=? WHERE user_id=?",
        (1 if vip else 0, str(uid))
    )
    conn.commit()

def set_last(uid):
    cur.execute(
        "UPDATE users SET last=? WHERE user_id=?",
        (now_ts(), str(uid))
    )
    conn.commit()

# ================= TELEGRAM =================
async def is_user_joined(bot, user_id):
    try:
        m = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return m.status in ("member", "administrator", "creator")
    except:
        return False

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

def patch_endpoint(conf):
    out = []
    with open(conf) as f:
        for line in f:
            if line.startswith("Endpoint"):
                line = f"Endpoint = {ENDPOINT_IP}:{ENDPOINT_PORT}\n"
            out.append(line)
    with open(conf, "w") as f:
        f.writelines(out)

def make_qr(conf, png):
    with open(conf) as f:
        img = qrcode.make(f.read())
    img.save(png)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 မင်္ဂလာပါ\nMenu ကိုရွေးပါ 👇",
        reply_markup=MAIN_KEYBOARD
    )

# ================= MENU HANDLER =================
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.message.from_user.id
    user = get_user(uid)
    now = datetime.now()

    # ===== JOIN CHANNEL =====
    if text == "📢 Join Channel":
        await update.message.reply_text(f"https://t.me/{CHANNEL_USERNAME}")

    # ===== VIP INFO =====
    elif text == "💎 VIP Info":
        if user["vip"]:
            await update.message.reply_text(
                "🎉 သင်သည် VIP ဖြစ်ပြီးသားပါ 💎",
                reply_markup=VIP_KEYBOARD_ACTIVE
            )
        else:
            await update.message.reply_text(
                VIP_PRICE,
                reply_markup=VIP_KEYBOARD_FREE
            )

    # ===== BUY VIP =====
    elif text == "💰 Buy VIP":
        pending_payments.add(uid)
        await update.message.reply_text(BANKING_TEXT)

    # ===== BACK =====
    elif text == "🔙 Back":
        await update.message.reply_text(
            "🏠 Main Menu",
            reply_markup=MAIN_KEYBOARD
        )

    # ===== GENERATE =====
    elif text == "⚡ Generate WARP":
        if not await is_user_joined(context.bot, uid):
            await update.message.reply_text("⛔ Channel join လုပ်ပါ")
            return

        if uid != ADMIN_ID:
            last = user["last"]

            if not user["vip"] and last:
                nt = datetime.fromtimestamp(last) + timedelta(days=7)
                if now < nt:
                    await update.message.reply_text(
                        f"⛔ Free user\n⏳ {remaining_time(int((nt-now).total_seconds()))}"
                    )
                    return

            if user["vip"] and last:
                nt = datetime.fromtimestamp(last) + timedelta(days=1)
                if now < nt:
                    await update.message.reply_text(
                        f"⛔ VIP user\n⏳ {remaining_time(int((nt-now).total_seconds()))}"
                    )
                    return

        await update.message.reply_text("⚙️ Generating...")

        try:
            setup_wgcf()
            reset_wgcf()
            subprocess.run([WGCF_BIN, "register", "--accept-tos"], check=True)
            subprocess.run([WGCF_BIN, "generate"], check=True)

            patch_endpoint("wgcf-profile.conf")

            conf = f"MHWARP_{uuid.uuid4().hex[:8]}.conf"
            png = conf.replace(".conf", ".png")

            shutil.move("wgcf-profile.conf", conf)
            make_qr(conf, png)

            await update.message.reply_document(open(conf, "rb"))
            await update.message.reply_photo(
                open(png, "rb"),
                caption="📱 QR Code (WireGuard app မှာ Scan လုပ်ပါ)"
            )

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

    photo = update.message.photo[-1]
    uname = update.message.from_user.username or "No username"

    await context.bot.send_photo(
        PAYMENT_CHANNEL_ID,
        photo.file_id,
        caption=f"💰 VIP Payment\n👤 {uid}\n@{uname}"
    )

    pending_payments.remove(uid)
    await update.message.reply_text("✅ Screenshot ပို့ပြီးပါပြီ")

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, payment_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler))

    print("🤖 Bot running (VIP Keyboard Dynamic)")
    app.run_polling()
