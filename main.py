import os
import time
import uuid
import shutil
import subprocess
import requests
import qrcode
import sqlite3
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
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
    "🥰 Vip Lifetime 🥰\n"
    "💎 Server များစွာကို lifetime သုံးနိုင်\n\n"
    "💵 တသက်စာဝင်ကြေး 5000 ကျပ်\n"
    "📆 VIP user – တစ်ရက်တစ်ခါ file ထုတ်နိုင်"
)

BANKING_TEXT = (
    "💳 Payment Methods\n\n"
    "🏦 Kpay\nName: Win Htut Kyaw\nAcc: 09982383696\n\n"
    "🏦 WavePay\nName: Kyaw Kyaw Naing\nPhone: 09972752831\n\n"
    "📸 ငွေလွှဲပြီး Screenshot ကို ဒီ bot ထဲမှာပဲ ပို့ပါ ❗"
)

pending_payments = set()

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

def remaining_time(seconds):
    d = seconds // 86400
    h = (seconds % 86400) // 3600
    m = (seconds % 3600) // 60
    return f"{d}ရက် {h}နာရီ {m}မိနစ်"

# ================= DB =================
def get_user(user_id):
    cur.execute("SELECT vip, last FROM users WHERE user_id=?", (str(user_id),))
    row = cur.fetchone()
    if not row:
        cur.execute(
            "INSERT INTO users (user_id, vip, last) VALUES (?,0,0)",
            (str(user_id),)
        )
        conn.commit()
        return {"vip": False, "last": 0}
    return {"vip": bool(row[0]), "last": row[1]}

def set_vip(user_id, vip=True):
    cur.execute("UPDATE users SET vip=? WHERE user_id=?", (1 if vip else 0, str(user_id)))
    if cur.rowcount == 0:
        cur.execute(
            "INSERT INTO users (user_id, vip, last) VALUES (?, ?, 0)",
            (str(user_id), 1 if vip else 0)
        )
    conn.commit()

def set_last(user_id, ts):
    cur.execute("UPDATE users SET last=? WHERE user_id=?", (ts, str(user_id)))
    conn.commit()

def get_vip_users():
    cur.execute("SELECT user_id FROM users WHERE vip=1")
    return [r[0] for r in cur.fetchall()]

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
    lines = []
    with open(conf) as f:
        for line in f:
            if line.strip().startswith("Endpoint"):
                line = f"Endpoint = {ENDPOINT_IP}:{ENDPOINT_PORT}\n"
            lines.append(line)
    with open(conf, "w") as f:
        f.writelines(lines)

def generate_qr(conf, png):
    with open(conf) as f:
        img = qrcode.make(f.read())
    img.save(png)

# ================= KEYBOARDS =================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton("⚡ Generate WARP Config", callback_data="generate")],
        [InlineKeyboardButton("💎 VIP User", callback_data="vip_info")]
    ])

def vip_keyboard(is_vip=False):
    if is_vip:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Buy Now", callback_data="buy_now")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ])

def payment_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 ငွေလွှဲပြီး ပုံပို့ရန်", callback_data="send_payment")],
        [InlineKeyboardButton("🔙 Back", callback_data="vip_info")]
    ])

# ================= COMMAND =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 မင်္ဂလာပါ\n\n📌 Channel join လုပ်ပြီးမှ WARP config ထုတ်နိုင်ပါတယ်",
        reply_markup=main_keyboard()
    )

# ================= BUTTONS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user = get_user(user_id)
    now = datetime.now()

    if query.data == "back_main":
        await query.edit_message_text("🏠 Main Menu", reply_markup=main_keyboard())
        return

    if query.data == "vip_info":
        status = "💎 VIP" if user["vip"] else "❌ Free"
        text = f"💎 VIP Status\n\nStatus: {status}"
        text += "\n\n✅ You are already VIP" if user["vip"] else f"\n\n{VIP_PRICE}"
        await query.edit_message_text(text, reply_markup=vip_keyboard(user["vip"]))
        return

    if query.data == "buy_now":
        await query.edit_message_text(BANKING_TEXT, reply_markup=payment_keyboard())
        return

    if query.data == "send_payment":
        pending_payments.add(user_id)
        await query.edit_message_text("📸 Screenshot ကို ဒီမှာပို့ပါ")
        return

    if query.data == "generate":
        if not await is_user_joined(context.bot, user_id):
            await query.edit_message_text("⛔ Channel join လုပ်ပါ", reply_markup=main_keyboard())
            return

        last_ts = user["last"]

        if not user["vip"] and last_ts:
            next_time = datetime.fromtimestamp(last_ts) + timedelta(days=7)
            if now < next_time:
                remain = int((next_time - now).total_seconds())
                await query.edit_message_text(
                    f"⛔ Free user အပတ်တစ်ခါပဲရပါတယ်\n\n⏳ ကျန်ရှိချိန် : {remaining_time(remain)}",
                    reply_markup=main_keyboard()
                )
                return

        if user["vip"] and last_ts:
            next_time = datetime.fromtimestamp(last_ts) + timedelta(days=1)
            if now < next_time:
                remain = int((next_time - now).total_seconds())
                await query.edit_message_text(
                    f"⛔ VIP user တစ်ရက်တစ်ခါပဲရပါတယ်\n\n⏳ ကျန်ရှိချိန် : {remaining_time(remain)}",
                    reply_markup=main_keyboard()
                )
                return

        msg = await query.message.reply_text("⚙️ Generating...")

        try:
            setup_wgcf()
            reset_wgcf()
            subprocess.run([WGCF_BIN, "register", "--accept-tos"], check=True)
            subprocess.run([WGCF_BIN, "generate"], check=True)

            patch_endpoint("wgcf-profile.conf")

            conf = f"MHWARP_{uuid.uuid4().hex[:8]}.conf"
            png = conf.replace(".conf", ".png")

            shutil.move("wgcf-profile.conf", conf)
            generate_qr(conf, png)

            await query.message.reply_document(open(conf, "rb"))
            await query.message.reply_photo(
                photo=open(png, "rb"),
                caption="📱 QR Code (WireGuard app မှာ Scan လုပ်ပါ)"
            )

            set_last(user_id, now_ts())

            os.remove(conf)
            os.remove(png)
            await msg.delete()

            await query.message.reply_text("Menu ကိုပြန်ရွေးနိုင်ပါတယ် 👇", reply_markup=main_keyboard())

        except Exception as e:
            await msg.delete()
            await query.message.reply_text(f"❌ Error: {e}")

# ================= PAYMENT PHOTO =================
async def payment_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    if uid not in pending_payments:
        return

    photo = update.message.photo[-1]
    username = update.message.from_user.username or "No username"

    await context.bot.send_photo(
        PAYMENT_CHANNEL_ID,
        photo.file_id,
        caption=f"💰 VIP Payment Proof\n👤 {uid}\n@{username}"
    )

    pending_payments.remove(uid)
    await update.message.reply_text("✅ Screenshot ပို့ပြီးပါပြီ။ Admin စစ်ဆေးနေပါသည်။")

# ================= ADMIN COMMANDS =================
async def approvevip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("/approvevip USER_ID")
        return
    uid = int(context.args[0])
    set_vip(uid, True)
    await update.message.reply_text(f"✅ VIP Approved: {uid}")
    try:
        await context.bot.send_message(uid, "🎉 VIP Activated!\n💎 Lifetime VIP")
    except:
        pass

async def rejectvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("/rejectvip USER_ID")
        return
    uid = int(context.args[0])
    set_vip(uid, False)
    await update.message.reply_text(f"❌ VIP Rejected: {uid}")
    try:
        await context.bot.send_message(uid, "❌ VIP Removed")
    except:
        pass

async def viplist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    vips = get_vip_users()
    if not vips:
        await update.message.reply_text("📭 VIP မရှိပါ")
        return
    text = "💎 VIP LIST\n\n"
    for i, uid in enumerate(vips, 1):
        text += f"{i}. `{uid}`\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approvevip", approvevip))
    app.add_handler(CommandHandler("rejectvip", rejectvip))
    app.add_handler(CommandHandler("viplist", viplist))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.PHOTO, payment_photo))

    print("🤖 Bot running (FULL ADMIN FEATURES)")
    app.run_polling()
