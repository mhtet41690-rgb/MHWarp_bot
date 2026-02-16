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

ENDPOINT_IP = "162.159.192.1"
ENDPOINT_PORT = 500

VIP_PRICE = (
    "🥰 VIP Lifetime 🥰\n\n"
    "💐စင်္ကာပူ၊ထိုင်း အစရှိသည့် server များကိုလည်း lifetime အသုံးပြုလို့ရမှာပါ။\n"
    "💎 တစ်ခါဝယ်ထားယုံဖြင့် တစ်သက်စာ အသုံးပြုလို့ရသွားမှာပါ။\n"
    "🎊ဒါ့အပြင် Warp file ကို ispဘတ်မှ ban ခဲ့ပါက ။ Vip များအတွတ် File အသစ်ပေးသွားမှာပါ။\n"
    "💵 Price: 3000 Ks\n"
    "📆 VIP → တစ်ရက်တစ်ခါ Generate လုပ်လို့ရ"
)

VIP_TUTORIAL_VIDEO = "BAACAgUAAxkBAAIB9WmS1Mwvr42_VTJgDBs_nD8DN5-lAAL0GAACIkeZVPJRAAF0x4zJMzoE"

VIP_TUTORIAL_TEXT = (
    "📘 VIP Tutorial\n\n"
    "1️⃣ V2box App Install\n"
    "2️⃣ https://mhwarp.netlify.app/mh.txt\n"
    "3️⃣ Video အတိုင်းလုပ်ပါ\n"
    "Vip Group သို့ Join ထားပါ။\n"
    "https://t.me/+KtgnAAUsu6hiNDBl"
)

PAYMENT_INFO = (
    "💳 Payment Banking Info\n\n"
    "🏦 Kpay\n"
    "👤 Name : Win Htut Kyaw\n"
    "📱 Acc No : `09982383696`\n\n"
    "📱 Wave Money Money\n"
    "👤 Name : Mg Kyaw Kyaw Naing\n"
    "📱 No : `09972752831`\n\n"
    "💵 Amount : 3000 Ks\n\n"
    "📸 ငွေပေးချေပြီးပါက Screenshot ကို ဒီ bot ထဲမှာပို့ပါ"
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
            
def patch_endpoint(conf_path, new_ip, new_port):
    lines = []
    with open(conf_path, "r") as f:
        for line in f:
            if line.strip().startswith("Endpoint"):
                line = f"Endpoint = {new_ip}:{new_port}\n"
            lines.append(line)

    with open(conf_path, "w") as f:
        f.writelines(lines)

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
        f"⚡ Limit : {'Gemerate နေ့စဉ် ၁ ကြိမ်' if u['vip'] else 'Generate ၇ ရက်တစ်ကြိမ်'}"
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
        await update.message.reply_text(PAYMENT_INFO, reply_markup=VIP_BACK_KB)

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

        subprocess.run([WGCF_BIN, "register", "--accept-tos"], check=True)
        subprocess.run([WGCF_BIN, "generate"], check=True)

        patch_endpoint("wgcf-profile.conf", ENDPOINT_IP, ENDPOINT_PORT)

        conf_name = f"MHWARP_{uuid.uuid4().hex[:8]}.conf"
        qr_name = conf_name.replace(".conf", ".png")

        shutil.move("wgcf-profile.conf", conf_name)
        generate_qr(conf_name, qr_name)

        with open(conf_name, "rb") as f:
            await query.message.reply_document(
                document=f,
                filename=conf_name,
                caption="✅ WARP Config File"
            )

        with open(qr_name, "rb") as img:
            await query.message.reply_photo(
                photo=img,
                caption="📱 QR Code (WireGuard app မှာ Scan လုပ်ပါ)"
            )

        users[str(user_id)] = {"last": now_ts()}
        save_users(users)

        await processing_msg.delete()
        await query.message.reply_text(
            "‼️ရောင်းချခွင့် မပြုပါ‼️",
            reply_markup=main_keyboard()
        )

        os.remove(conf_name)
        os.remove(qr_name)

    except Exception as e:
        await processing_msg.delete()
        await query.message.reply_text(
            f"❌ Error:\n{e}",
            reply_markup=main_keyboard()
        )


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
            f"👤 Username: {username}"
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

async def vipmsg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❗ အသုံးပြုပုံ:\n"
            "ပို့ချင်တဲ့ message / photo / file ကို reply လုပ်ပြီး\n"
            "/vipmsg လို့ရိုက်ပါ"
        )
        return

    src = update.message.reply_to_message

    cur.execute("SELECT user_id FROM users WHERE vip=1")
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("❌ VIP User မရှိပါ")
        return

    sent = 0
    failed = 0

    for (uid,) in rows:
        try:
            await src.copy(chat_id=int(uid))
            sent += 1
        except:
            failed += 1

    await update.message.reply_text(
        f"✅ VIP Broadcast Done\n\n"
        f"📤 Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )
    
async def allmsg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❗ အသုံးပြုပုံ\n"
            "ပို့ချင်တဲ့ message / photo / video ကို reply လုပ်ပြီး\n"
            "/allmsg လို့ရိုက်ပါ"
        )
        return

    src = update.message.reply_to_message

    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()

    sent = 0
    failed = 0

    for (uid,) in users:
        try:
            await src.copy(chat_id=int(uid))
            sent += 1
        except:
            failed += 1

    await update.message.reply_text(
        f"📢 Broadcast Finished\n\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )
    
async def send_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❗ အသုံးပြုပုံ:\n"
            "ပို့ချင်တဲ့ message ကို reply လုပ်ပြီး\n"
            "/send user_id လို့ရိုက်ပါ"
        )
        return

    if not context.args:
        await update.message.reply_text("❗ user_id ထည့်ပါ")
        return

    uid = int(context.args[0])
    src = update.message.reply_to_message

    try:
        await src.copy(chat_id=uid)
        await update.message.reply_text(f"✅ {uid} ဆီပို့ပြီးပါပြီ")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")
# ================= MAIN =================
if __name__ == "__main__":
    setup_wgcf()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approvevip", approvevip))
    app.add_handler(CommandHandler("rejectvip", rejectvip))
    app.add_handler(CommandHandler("viplist", viplist))
    app.add_handler(CommandHandler("vipmsg", vipmsg))
    app.add_handler(CommandHandler("allmsg", allmsg))
    app.add_handler(CommandHandler("send", send_user))
    app.add_handler(MessageHandler(filters.PHOTO, payment_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu))

    print("🤖 BOT RUNNING (GENERATE FIXED)")
    app.run_polling()
