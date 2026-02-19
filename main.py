import os
import time
import uuid
import shutil
import subprocess
import qrcode
import sqlite3
import requests
import json
import base64
from datetime import datetime, timezone, timedelta

from nacl.public import PrivateKey
import base64 as b64

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# ================= CONFIG (Environment Variables) =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
PAYMENT_CHANNEL_ID = int(os.getenv("PAYMENT_CHANNEL_ID"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))

WGCF_BIN = "./wgcf"
WGCF_URL = "https://github.com/ViRb3/wgcf/releases/latest/download/wgcf_2.2.30_linux_amd64"
FIXED_ENDPOINT = "162.159.192.1:500"
API = "https://api.cloudflareclient.com/v0i1909051800"

# ================= MESSAGES =================
VIP_PRICE = (
    "🥰 *VIP Lifetime* 🥰\n\n"
    "💐 စင်္ကာပူ၊ ထိုင်း အစရှိသည့် server များကို lifetime အသုံးပြုနိုင်ပါမည်။\n"
    "💎 တစ်ခါဝယ်ရုံဖြင့် တစ်သက်စာ အသုံးပြုရမည်။\n"
    "🎊 File ban ခံရပါက VIP များအတွက် အသစ်ပြန်ပေးပါမည်။\n\n"
    "💵 *Price: 3000 Ks Lifetime*\n"
    "📆 VIP -> ၁ ရက် ၁ ခါ ထုတ်ယူနိုင်သည်"
)

VIP_TUTORIAL_VIDEO = "BAACAgUAAxkBAAIB9WmS1Mwvr42_VTJgDBs_nD8DN5-lAAL0GAACIkeZVPJRAAF0x4zJMzoE"
VIP_TUTORIAL_TEXT = "📘 *VIP Tutorial*\n\n1️⃣ V2box App Install ပါ\n2️⃣ Video အတိုင်း Sub link ထည့်သွင်းပါ"

PAYMENT_INFO = (
    "💳 *Payment Info*\n\n"
    "🏦 Kpay (09982383696)\n"
    "🏦 Wave Money (09972752831)\n\n"
    "💵 Amount : 3000 Ks\n"
    "📸 ပြေစာပုံ ပို့ပေးပါ။ Admin မှ စစ်ဆေးပေးပါမည်။"
)

# ================= KEYBOARD =================
MAIN_KB = ReplyKeyboardMarkup(
    [["⚡ Generate WARP", "🧩 Hiddify Conf"], ["💎 VIP Info", "📢 Join Channel"]],
    resize_keyboard=True
)
VIP_FREE_KB = ReplyKeyboardMarkup([["💰 Buy VIP"], ["🔙 Back"]], resize_keyboard=True)
VIP_BACK_KB = ReplyKeyboardMarkup([["🔙 Back"]], resize_keyboard=True)

# ================= SQLITE DB =================
DB_PATH = "/data/users.db"
os.makedirs("/data", exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, vip INTEGER DEFAULT 0, last INTEGER DEFAULT 0)")
conn.commit()

# ================= HELPERS =================
def setup_wgcf():
    if not os.path.exists(WGCF_BIN):
        r = requests.get(WGCF_URL); f = open(WGCF_BIN, "wb"); f.write(r.content); f.close()
        os.chmod(WGCF_BIN, 0o755)

def reset_wgcf():
    for f in ["wgcf-account.toml", "wgcf-profile.conf"]:
        if os.path.exists(f): os.remove(f)

def wg_genkey():
    priv = PrivateKey.generate()
    return b64.b64encode(bytes(priv)).decode()

def wg_pubkey(priv_b64):
    priv = PrivateKey(b64.b64decode(priv_b64))
    return b64.b64encode(bytes(priv.public_key)).decode()

def api_call(method, path, token=None, data=None):
    headers = {"user-agent": "", "content-type": "application/json"}
    if token: headers["authorization"] = f"Bearer {token}"
    r = requests.request(method, f"{API}/{path}", headers=headers, json=data, timeout=20)
    r.raise_for_status()
    return r.json()

def remaining(sec):
    d, h, m = sec // 86400, (sec % 86400) // 3600, (sec % 3600) // 60
    return f"{d}ရက် {h}နာရီ {m}မိနစ်"

def get_user(uid):
    cur.execute("SELECT vip, last FROM users WHERE user_id=?", (str(uid),))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO users (user_id, vip, last) VALUES (?,0,0)", (str(uid),))
        conn.commit()
        return {"vip": False, "last": 0}
    return {"vip": bool(r[0]), "last": r[1]}

def set_vip(uid, v=True):
    cur.execute("UPDATE users SET vip=? WHERE user_id=?", (1 if v else 0, str(uid)))
    conn.commit()

def set_last(uid):
    cur.execute("UPDATE users SET last=? WHERE user_id=?", (int(time.time()), str(uid)))
    conn.commit()

# ================= CORE LOGIC =================
def generate_hiddify_base64():
    priv = wg_genkey(); pub = wg_pubkey(priv)
    reg = api_call("POST", "reg", data={
        "install_id": "", "tos": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "key": pub, "fcm_token": "", "type": "ios", "locale": "en_US",
    })
    cid, token = reg["result"]["id"], reg["result"]["token"]
    res = api_call("PATCH", f"reg/{cid}", token, {"warp_enabled": True})
    cfg = res["result"]["config"]
    conf = {
        "outbounds": [{
            "tag": "WARP", "mtu": 1280, "private_key": priv, "type": "wireguard",
            "reserved": list(base64.b64decode(cfg["client_id"])),
            "local_address": [f'{cfg["interface"]["addresses"]["v4"]}/32', f'{cfg["interface"]["addresses"]["v6"]}/128'],
            "peer_public_key": cfg["peers"][0]["public_key"],
            "server": "162.159.192.1", "server_port": 500,
            "fake_packets": "5-10", "fake_packets_size": "40-100", "fake_packets_mode": "m4"
        }]
    }
    profile = "//profile-title: MHwarp\n" + json.dumps(conf, separators=(",", ":"))
    return base64.b64encode(profile.encode()).decode()

async def is_joined_channel(bot, uid):
    try:
        m = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", uid)
        return m.status in ("member", "administrator", "creator")
    except: return False

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 မင်္ဂလာပါ\n\nလိုင်းကောင်းတဲ့ VPN Key ထုတ်နိုင်ပါပြီ", reply_markup=MAIN_KB)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.message.from_user.id
    user = get_user(uid)
    now = datetime.now()

    if text == "📢 Join Channel":
        await update.message.reply_text(f"https://t.me/{CHANNEL_USERNAME}"); return
    elif text == "💎 VIP Info":
        if user["vip"]:
            await context.bot.send_video(chat_id=uid, video=VIP_TUTORIAL_VIDEO)
            await update.message.reply_text(VIP_TUTORIAL_TEXT, parse_mode="Markdown")
        else: await update.message.reply_text(VIP_PRICE, reply_markup=VIP_FREE_KB, parse_mode="Markdown")
        return
    elif text == "💰 Buy VIP":
        await update.message.reply_text(PAYMENT_INFO, reply_markup=VIP_BACK_KB, parse_mode="Markdown"); return
    elif text == "🔙 Back":
        await update.message.reply_text("🏠 Main Menu", reply_markup=MAIN_KB); return

    if text in ["⚡ Generate WARP", "🧩 Hiddify Conf"]:
        if not await is_joined_channel(context.bot, uid):
            await update.message.reply_text(f"🚫 Channel Join လုပ်ပါ\nhttps://t.me/{CHANNEL_USERNAME}"); return

        if text == "🧩 Hiddify Conf" and not user["vip"] and uid != ADMIN_ID:
            await update.message.reply_text("🚫 Hiddify သည် VIP သီးသန့်ဖြစ်ပါသည်။", reply_markup=VIP_FREE_KB); return

        if uid != ADMIN_ID and user["last"]:
            limit = 1 if user["vip"] else 7
            nt = datetime.fromtimestamp(user["last"]) + timedelta(days=limit)
            if now < nt:
                await update.message.reply_text(f"⏳ ကျန်ချိန်: {remaining(int((nt-now).total_seconds()))}"); return

        status = await update.message.reply_text("⚙️ လုပ်ဆောင်နေပါသည်...")
        try:
            if text == "🧩 Hiddify Conf":
                b64_str = generate_hiddify_base64()
                await update.message.reply_text(f"✅ *Hiddify VIP*\n\n`{b64_str}`", parse_mode="MarkdownV2")
            else:
                setup_wgcf(); reset_wgcf()
                subprocess.run([WGCF_BIN, "register", "--accept-tos"], check=True, timeout=30)
                subprocess.run([WGCF_BIN, "generate"], check=True, timeout=30)
                with open("wgcf-profile.conf", "r") as f:
                    data = f.read().replace("engage.cloudflareclient.com:2408", FIXED_ENDPOINT)
                
                name = f"MH_{uuid.uuid4().hex[:8]}"
                with open(f"{name}.conf", "w") as f: f.write(data)
                qrcode.make(data).save(f"{name}.png")
                
                await update.message.reply_document(open(f"{name}.conf", "rb"))
                await update.message.reply_photo(photo=open(f"{name}.png", "rb"), caption="📱 QR Code Scan")
                os.remove(f"{name}.conf"); os.remove(f"{name}.png")

            if uid != ADMIN_ID: set_last(uid)
            await status.delete()
        except Exception as e: await status.edit_text(f"❌ Error: {e}")

# ================= ADMIN & PAYMENT =================
async def payment_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid = user.id
    caption = (
        f"💰 *VIP Payment Request*\n\n"
        f"👤 Name: {user.full_name}\n"
        f"🆔 ID: `{uid}`\n"
        f"🔗 User: @{user.username if user.username else 'N/A'}\n\n"
        f"Approve: `/approvevip {uid}`\n"
        f"Reject: `/rejectvip {uid}`"
    )
    await context.bot.send_photo(chat_id=PAYMENT_CHANNEL_ID, photo=update.message.photo[-1].file_id, caption=caption, parse_mode="Markdown")
    await update.message.reply_text("✅ ပြေစာ ပို့ပြီးပါပြီ။ Admin စစ်ဆေးပေးပါမည်။")

async def approvevip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args: return
    uid = context.args[0]; set_vip(uid, True)
    await update.message.reply_text(f"✅ VIP Approved: {uid}")
    await context.bot.send_message(uid, "🎉 VIP အဖြစ် အတည်ပြုပြီးပါပြီ။ Hiddify Conf ထုတ်ယူနိုင်ပါပြီ။")

async def rejectvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args: return
    uid = context.args[0]; set_vip(uid, False)
    await update.message.reply_text(f"❌ VIP Rejected: {uid}")
    await context.bot.send_message(uid, "❌ သင်၏ VIP လျှောက်ထားမှု ငြင်းပယ်ခံရပါသည်။")

async def viplist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    cur.execute("SELECT user_id FROM users WHERE vip=1")
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("❌ VIP User မရှိသေးပါ")
        return

    text = "💎 VIP USER LIST (ID & Username)\n\n"

    for i, (uid,) in enumerate(rows, start=1):
        try:
            chat = await context.bot.get_chat(int(uid))
            username = f"@{chat.username}" if chat.username else "❌ Not set"
        except:
            username = "❌ Not found"

        text += f"{i}. 👤 ID: {uid}\n   👤 Username: {username}\n\n"

        # Telegram message length safety
        if len(text) > 3500:
            await update.message.reply_text(text)
            text = ""

    if text:
        await update.message.reply_text(text)

async def allmsg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not update.message.reply_to_message: return
    cur.execute("SELECT user_id FROM users"); users = cur.fetchall()
    sent = 0
    for (uid,) in users:
        try: await update.message.reply_to_message.copy(chat_id=int(uid)); sent += 1
        except: continue
    await update.message.reply_text(f"📢 Broadcast Done. Sent: {sent}")

async def send_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not update.message.reply_to_message or not context.args: return
    try:
        await update.message.reply_to_message.copy(chat_id=int(context.args[0]))
        await update.message.reply_text("✅ Message Sent.")
    except Exception as e: await update.message.reply_text(f"❌ Failed: {e}")

# ================= MAIN =================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approvevip", approvevip))
    app.add_handler(CommandHandler("rejectvip", rejectvip))
    app.add_handler(CommandHandler("viplist", viplist))
    app.add_handler(CommandHandler("allmsg", allmsg))
    app.add_handler(CommandHandler("send", send_user))
    app.add_handler(MessageHandler(filters.PHOTO, payment_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu))
    print("🤖 BOT STARTED")
    app.run_polling()
