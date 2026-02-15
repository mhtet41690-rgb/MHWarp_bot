import os
import time
import json
import uuid
import shutil
import subprocess
import requests
import qrcode
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
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
DATA_FILE = "users.json"

ENDPOINT_IP = "162.159.192.1"
ENDPOINT_PORT = 500

VIP_PRICE = "One-time payment (Lifetime)"

BANKING_TEXT = (
    "💳 Payment Methods\n\n"
    "🏦 KBZ Bank\n"
    "Name: Mg Aung Aung\n"
    "Acc: 123-456-789\n\n"
    "🏦 WavePay\n"
    "Phone: 09xxxxxxxx\n\n"
    "📸 ငွေလွှဲပြီး Screenshot ကို ဒီ bot ထဲမှာပဲ ပို့ပါ"
)

pending_payments = set()
# =========================================


# ---------------- Utils ----------------
def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def now_ts():
    return int(time.time())

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

def patch_endpoint(conf_path, ip, port):
    lines = []
    with open(conf_path, "r") as f:
        for line in f:
            if line.strip().startswith("Endpoint"):
                line = f"Endpoint = {ip}:{port}\n"
            lines.append(line)
    with open(conf_path, "w") as f:
        f.writelines(lines)

def generate_qr(conf_path, out_png):
    with open(conf_path, "r") as f:
        data = f.read()
    img = qrcode.make(data)
    img.save(out_png)

async def is_user_joined(bot, user_id):
    try:
        m = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return m.status in ("member", "administrator", "creator")
    except:
        return False


# ---------------- UI ----------------
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME}")],
        [InlineKeyboardButton("⚡ Generate WARP Config", callback_data="generate")],
        [InlineKeyboardButton("💎 VIP User", callback_data="vip_info")]
    ])

def vip_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_vip"),
            InlineKeyboardButton("💰 Buy Now", callback_data="buy_now")
        ]
    ])


# ---------------- Commands ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 မင်္ဂလာပါ\n\n📌 Channel join လုပ်ပြီးမှ WARP config ထုတ်နိုင်ပါတယ်",
        reply_markup=main_keyboard()
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Help\n\n"
        "• Free → အပတ်တစ်ခါ\n"
        "• VIP (Lifetime) → တစ်ရက်တစ်ခါ\n"
        "• Admin → Unlimited",
        reply_markup=main_keyboard()
    )


# ---------------- Buttons ----------------
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    users = load_users()
    user_id = query.from_user.id
    user = users.get(str(user_id), {})

    if query.data == "vip_info":
        is_vip = user.get("vip", False)
        status = "💎 VIP (Lifetime)" if is_vip else "❌ Free User"

        await query.edit_message_text(
            f"💎 VIP Status\n\n"
            f"👤 Status: {status}\n\n"
            f"🎁 Benefits:\n"
            f"• Lifetime VIP\n"
            f"• Generate တစ်ရက်တစ်ခါ\n\n"
            f"💵 {VIP_PRICE}",
            reply_markup=vip_keyboard()
        )
        return

    if query.data == "cancel_vip":
        await query.edit_message_text("🔙 Main Menu", reply_markup=main_keyboard())
        return

    if query.data == "buy_now":
        await query.edit_message_text(
            BANKING_TEXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Send Payment Screenshot", callback_data="send_payment")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_vip")]
            ])
        )
        return

    if query.data == "send_payment":
        pending_payments.add(user_id)
        await query.edit_message_text("📸 Payment Screenshot ကို ပို့ပါ (Photo only)")
        return

    if query.data != "generate":
        return

    if not await is_user_joined(context.bot, user_id):
        await query.edit_message_text("⛔ Channel join လုပ်ပါ", reply_markup=main_keyboard())
        return

    is_admin = user_id == ADMIN_ID
    is_vip = user.get("vip", False)
    last_ts = user.get("last", 0)
    now = datetime.now()

    if not is_admin and not is_vip and last_ts:
        if now - datetime.fromtimestamp(last_ts) < timedelta(days=7):
            await query.edit_message_text("⛔ Free User က အပတ်တစ်ခါပဲရပါတယ်", reply_markup=main_keyboard())
            return

    if not is_admin and is_vip and last_ts:
        if now - datetime.fromtimestamp(last_ts) < timedelta(days=1):
            await query.edit_message_text("⛔ VIP User က တစ်ရက်တစ်ခါပဲရပါတယ်", reply_markup=main_keyboard())
            return

    msg = await query.message.reply_text("⚙️ Generating...")

    try:
        setup_wgcf()
        reset_wgcf()
        subprocess.run([WGCF_BIN, "register", "--accept-tos"], check=True)
        subprocess.run([WGCF_BIN, "generate"], check=True)

        patch_endpoint("wgcf-profile.conf", ENDPOINT_IP, ENDPOINT_PORT)

        conf = f"MHWARP_{uuid.uuid4().hex[:8]}.conf"
        qr = conf.replace(".conf", ".png")

        shutil.move("wgcf-profile.conf", conf)
        generate_qr(conf, qr)

        await query.message.reply_document(open(conf, "rb"))
        await query.message.reply_photo(open(qr, "rb"))

        users[str(user_id)] = user | {"last": now_ts()}
        save_users(users)

        os.remove(conf)
        os.remove(qr)
        await msg.delete()

    except Exception as e:
        await msg.delete()
        await query.message.reply_text(f"❌ Error: {e}")


# ---------------- Payment Screenshot ----------------
async def payment_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in pending_payments:
        return

    photo = update.message.photo[-1]

    caption = (
        "💰 VIP Payment Proof\n\n"
        f"User ID: {user_id}\n"
        f"Username: @{update.message.from_user.username}"
    )

    await context.bot.send_photo(
        PAYMENT_CHANNEL_ID,
        photo.file_id,
        caption=caption
    )

    pending_payments.remove(user_id)

    await update.message.reply_text(
        "✅ Screenshot ကို Admin ဆီပို့ပြီးပါပြီ\n⏳ စစ်ဆေးပြီး VIP ဖွင့်ပေးပါမယ်"
    )


# ---------------- Approve VIP (NO REPLY) ----------------
async def approvevip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("❌ Usage:\n/approvevip USER_ID")
        return

    user_id = context.args[0]
    if not user_id.isdigit():
        await update.message.reply_text("❌ Invalid User ID")
        return

    users = load_users()
    users[user_id] = {"vip": True, "last": 0}
    save_users(users)

    try:
        await context.bot.send_message(
            int(user_id),
            "🎉 VIP Activated!\n\n💎 Lifetime VIP\n⏳ Generate: တစ်ရက်တစ်ခါ"
        )
    except:
        pass

    await update.message.reply_text(f"✅ VIP Approved: {user_id}")


# ---------------- Main ----------------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("approvevip", approvevip))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.PHOTO, payment_photo))

    print("🤖 Bot running...")
    app.run_polling()
