import os
import json
import time
import uuid
import shutil
import subprocess
import requests
import qrcode
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================= CONFIG =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PAYMENT_CHANNEL_ID = int(os.getenv("PAYMENT_CHANNEL_ID", "0"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")

DATA_FILE = "users.json"

WGCF_URL = "https://github.com/ViRb3/wgcf/releases/latest/download/wgcf_2.2.30_linux_amd64"
WGCF_BIN = "./wgcf"

ENDPOINT_IP = "162.159.192.1"
ENDPOINT_PORT = 500
# ========================================


# ============ Utils ============
def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

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
    with open(conf, "r") as f:
        for line in f:
            if line.startswith("Endpoint"):
                line = f"Endpoint = {ENDPOINT_IP}:{ENDPOINT_PORT}\n"
            lines.append(line)
    with open(conf, "w") as f:
        f.writelines(lines)

def generate_qr(conf, out):
    with open(conf, "r") as f:
        data = f.read()
    img = qrcode.make(data)
    img.save(out)

async def is_joined(bot, uid):
    try:
        m = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", uid)
        return m.status in ("member", "administrator", "creator")
    except:
        return False
# ==========================================


# ============ UI ============
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 VIP Info", callback_data="vipinfo")],
        [InlineKeyboardButton("⚡ Generate WARP", callback_data="generate")]
    ])
# ============================


# ============ Commands ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome\n\n"
        "💎 VIP = Lifetime\n"
        "⚡ VIP → 1 day 1 generate",
        reply_markup=main_keyboard()
    )


# ============ Buttons ============
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    if q.data == "vipinfo":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Buy Now", callback_data="buynow")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ])
        await q.edit_message_text(
            "💎 VIP Status\n\n"
            "• Lifetime VIP\n"
            "• 1 day 1 generate\n"
            "• No expiry",
            reply_markup=kb
        )

    elif q.data == "buynow":
        await q.edit_message_text(
            "💳 Payment Info\n\n"
            "KBZ: 09xxxxxxx\n"
            "Wave: 09xxxxxxx\n\n"
            "📸 Payment screenshot ကို ဒီ bot ထဲပို့ပါ"
        )

    elif q.data == "generate":
        if not await is_joined(context.bot, uid):
            await q.edit_message_text("⛔ Channel join first")
            return

        users = load_users()
        today = datetime.now().strftime("%Y-%m-%d")

        if str(uid) not in users or not users[str(uid)].get("vip"):
            await q.edit_message_text("❌ VIP only")
            return

        if users[str(uid)].get("last_generate") == today:
            await q.edit_message_text("⛔ Today limit reached")
            return

        msg = await q.message.reply_text("⚙️ Generating...")

        try:
            setup_wgcf()
            reset_wgcf()
            subprocess.run([WGCF_BIN, "register", "--accept-tos"], check=True)
            subprocess.run([WGCF_BIN, "generate"], check=True)

            patch_endpoint("wgcf-profile.conf")

            name = f"VIP_{uuid.uuid4().hex[:6]}"
            conf = f"{name}.conf"
            qr = f"{name}.png"

            shutil.move("wgcf-profile.conf", conf)
            generate_qr(conf, qr)

            await q.message.reply_document(open(conf, "rb"))
            await q.message.reply_photo(open(qr, "rb"))

            users[str(uid)]["last_generate"] = today
            save_users(users)

            os.remove(conf)
            os.remove(qr)
            await msg.delete()

        except Exception as e:
            await msg.delete()
            await q.message.reply_text(str(e))

    elif q.data == "cancel":
        await q.edit_message_text("Cancelled", reply_markup=main_keyboard())


# ============ Payment Screenshot ============
async def payment_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo = update.message.photo[-1]

    caption = (
        "💳 New Payment Screenshot\n\n"
        f"👤 @{user.username}\n"
        f"🆔 {user.id}"
    )

    await context.bot.send_photo(
        chat_id=PAYMENT_CHANNEL_ID,
        photo=photo.file_id,
        caption=caption
    )

    await update.message.reply_text("✅ Payment received. Admin will review.")


# ============ Admin Approve VIP ============
async def approvevip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /approvevip USER_ID")
        return

    uid = context.args[0]
    users = load_users()

    users[uid] = {
        "vip": True,
        "vip_type": "lifetime",
        "last_generate": None
    }
    save_users(users)

    await context.bot.send_message(
        chat_id=int(uid),
        text="🎉 You are VIP (Lifetime)\n1 day 1 generate"
    )

    await update.message.reply_text(f"✅ VIP approved: {uid}")


# ============ Admin Reject VIP ============
async def rejectvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Usage: /rejectvip USER_ID")
        return

    uid = context.args[0]
    users = load_users()

    if uid not in users or not users[uid].get("vip"):
        await update.message.reply_text("❌ User is not VIP")
        return

    users[uid]["vip"] = False
    users[uid]["vip_type"] = None
    users[uid]["last_generate"] = None
    save_users(users)

    try:
        await context.bot.send_message(
            chat_id=int(uid),
            text="❌ VIP request rejected.\nPlease contact admin."
        )
    except:
        pass

    await update.message.reply_text(f"🚫 VIP rejected: {uid}")


# ============ Main ============
if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN missing")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approvevip", approvevip))
    app.add_handler(CommandHandler("rejectvip", rejectvip))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.PHOTO, payment_photo))

    print("🤖 Bot running...")
    app.run_polling()
