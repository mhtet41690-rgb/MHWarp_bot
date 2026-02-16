import os
import time
import uuid
import shutil
import subprocess
import qrcode
import sqlite3
from datetime import datetime, timedelta

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
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
    "💎 Unlimited Server Access\n"
    "💵 Price: 5000 Ks\n"
    "📆 VIP → တစ်ရက်တစ်ခါ Generate"
)

VIP_TUTORIAL_VIDEO = "BAACAgUAAxkBAAIBVGmStP8VBxAIVUMR5Nbm_zMg7kiQAAJiHQACAnOJVBqp01m3JfeDOgQ"

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
            await update.message.reply_text("💎 VIP User")
            await context.bot.send_video(uid, VIP_TUTORIAL_VIDEO)
            await context.bot.send_message(uid, VIP_TUTORIAL_TEXT)
        else:
            await update.message.reply_text(VIP_PRICE, reply_markup=VIP_FREE_KB)

    elif text == "💰 Buy VIP":
        await update.message.reply_text(
            "💳 Payment ပြုလုပ်ပြီး Screenshot ကို ဒီ chat ထဲပို့ပါ",
            reply_markup=VIP_BACK_KB
        )

    elif text == "🔙 Back":
        await update.message.reply_text("🏠 Main Menu", reply_markup=MAIN_KB)

# ================= PAYMENT PHOTO =================
async def payment_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid = user.id
    username = f"@{user.username}" if user.username else "No username"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{uid}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject:{uid}")
        ]
    ])

    caption = (
        "💰 VIP Payment Screenshot\n\n"
        f"👤 User ID: `{uid}`\n"
        f"👤 Name: {user.full_name}\n"
        f"👤 Username: {username}"
    )

    await context.bot.send_photo(
        chat_id=PAYMENT_CHANNEL_ID,
        photo=update.message.photo[-1].file_id,
        caption=caption,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    await update.message.reply_text("✅ Screenshot ပို့ပြီးပါပြီ\n⏳ စစ်ဆေးနေပါသည်")

# ================= CALLBACK =================
async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("Admin only", show_alert=True)
        return

    action, uid = query.data.split(":")
    uid = int(uid)

    if action == "approve":
        set_vip(uid, True)
        await query.edit_message_caption(query.message.caption + "\n\n✅ Approved")

        await context.bot.send_message(uid, "🎉 VIP Activated!")
        await context.bot.send_video(uid, VIP_TUTORIAL_VIDEO)
        await context.bot.send_message(uid, VIP_TUTORIAL_TEXT)

    elif action == "reject":
        set_vip(uid, False)
        await query.edit_message_caption(query.message.caption + "\n\n❌ Rejected")
        await context.bot.send_message(uid, "❌ VIP Request Rejected")

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(payment_callback))
    app.add_handler(MessageHandler(filters.PHOTO, payment_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu))

    print("🤖 BOT RUNNING")
    app.run_polling()
