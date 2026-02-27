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
    "💎 တစ်ခါဝယ်ရုံဖြင့် တစ်သက်စာ အသုံးပြုရမည်။\n"
    "🎊 File ban ခံရပါက VIP များအတွက် အသစ်ပြန်ပေးပါမည်။\n\n"
    "💵 *Price: 3000 Ks Lifetime*\n"
    "📆 VIP ->Vpn Key ၁ ရက် ၁ ခါ ထုတ်ယူနိုင်သည်"
)

PAYMENT_INFO = (
    "💳 *Payment Info*\n\n"
    "🏦 Kpay : Win Htut Kyaw \n"
    "📞(09982383696)\n\n"
    "🏦 Wave Money : Mg Kyaw Kyaw Naing\n"
    "📞 09972752831\n\n"
    "💵 Amount : 3000 Ks\n\n"
    "📷 ပြေစာပုံ ကို bot မှာ ပို့ပေးပါ ။ admin မှ စစ်ဆေးပေးသွားပါမည်။\n\n"
    "🕣 မိနစ် ၃၀ အတွင်း vip မဖြစ်ပါက\n"
    "🧑admin @mhwarpadmin သို့ဆက်သွယ်ပေးပါ။"
    
)

# ================= KEYBOARD =================
MAIN_KB = ReplyKeyboardMarkup(
    [["⚡ Wireguard Key", "🧩 Hiddify Key"], ["💎 VIP Info", "📢 Join Channel"]],
    resize_keyboard=True
)
VIP_FREE_KB = ReplyKeyboardMarkup([["💰 Buy VIP"], ["🔙 Back"]], resize_keyboard=True)
VIP_BACK_KB = ReplyKeyboardMarkup([["🔙 Back"]], resize_keyboard=True)

# ================= SQLITE DB (Migration Support) =================
DB_PATH = "/data/users.db"
os.makedirs("/data", exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

# Table အသစ်ဆောက်ခြင်း
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY, 
    vip INTEGER DEFAULT 0, 
    last_warp INTEGER DEFAULT 0,
    last_hiddify INTEGER DEFAULT 0
)
""")

# ရှိပြီးသား Database ကို Data မပျက်စေဘဲ Update လုပ်ခြင်း
cur.execute("PRAGMA table_info(users)")
columns = [column[1] for column in cur.fetchall()]

if "last_warp" not in columns:
    try:
        cur.execute("ALTER TABLE users ADD COLUMN last_warp INTEGER DEFAULT 0")
        cur.execute("ALTER TABLE users ADD COLUMN last_hiddify INTEGER DEFAULT 0")
        if "last" in columns:
            cur.execute("UPDATE users SET last_warp = last")
        conn.commit()
        print("✅ Database Migrated Successfully.")
    except Exception as e:
        print(f"⚠️ Migration Error: {e}")

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
    cur.execute("SELECT vip, last_warp, last_hiddify FROM users WHERE user_id=?", (str(uid),))
    r = cur.fetchone()
    if not r:
        cur.execute("INSERT INTO users (user_id, vip, last_warp, last_hiddify) VALUES (?,0,0,0)", (str(uid),))
        conn.commit()
        return {"vip": False, "last_warp": 0, "last_hiddify": 0}
    return {"vip": bool(r[0]), "last_warp": r[1], "last_hiddify": r[2]}

def set_vip(uid, v=True):
    cur.execute("UPDATE users SET vip=? WHERE user_id=?", (1 if v else 0, str(uid)))
    conn.commit()

def set_last_time(uid, col_name):
    cur.execute(f"UPDATE users SET {col_name}=? WHERE user_id=?", (int(time.time()), str(uid)))
    conn.commit()

# ================= CORE LOGIC ===============
def base64_to_decimal(b64_str):
    """Base64 string ကို Decimal array (Reserved bytes) အဖြစ်ပြောင်းပေးတဲ့ function"""
    decoded_bytes = base64.b64decode(b64_str)
    return [int(b) for b in decoded_bytes]

def generate_hiddify_base64():
    priv = wg_genkey()
    pub = wg_pubkey(priv)
    
    # Register account
    reg = api_call("POST", "reg", data={
        "install_id": "", 
        "tos": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "key": pub, "fcm_token": "", "type": "ios", "locale": "en_US",
    })
    
    cid, token = reg["result"]["id"], reg["result"]["token"]
    
    # Enable WARP and get config
    res = api_call("PATCH", f"reg/{cid}", token, {"warp_enabled": True})
    cfg = res["result"]["config"]
    
    # --- Reserved bytes ကို ယူတဲ့အပိုင်း ---
    # API response ထဲက client_id ကို ယူပြီး Decimal ပြောင်းတယ်
    client_id_b64 = cfg.get("client_id", "")
    reserved_values = base64_to_decimal(client_id_b64) if client_id_b64 else [0, 0, 0]
    # -----------------------------------

    conf = {
 "outbounds": [],
 "endpoints": [
  {
   "type": "wireguard",
   "tag": "@mhwarp_bot",
   "mtu": 1280,
   "address": [
    "172.16.0.2/32",
    "2606:4700:110:8f4c:7e47:7e79:dfc3:ea74/128"
   ],
   "private_key": priv,
   "peers": [
    {
     "address": "162.159.192.1",
     "port": 500,
     "public_key": cfg["peers"][0]["public_key"],
     "allowed_ips": [
      "0.0.0.0/0",
      "::/0"
     ],
     "reserved": reserved_values,
    }
   ],
   "noise": {
    "fake_packet": {
     "enabled": true,
     "count": "2-10",
     "size": "30-50",
     "delay": "30-50",
     "mode": "m4"
    }
   }
  }
 ]
}
    
    profile = "//profile-title: tg @mhwarp\n" + json.dumps(conf, separators=(",", ":"))
    return base64.b64encode(profile.encode()).decode()
    
async def is_joined_channel(bot, uid):
    try:
        m = await bot.get_chat_member(f"@{CHANNEL_USERNAME}", uid)
        return m.status in ("member", "administrator", "creator")
    except: return False

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 မင်္ဂလာပါ\n\nလိုင်းကောင်းတဲ့ VPN Key ထုတ်နိုင်ပါပြီ\n\n အောက်မှ ခလုပ်များကိုနှိပ်ပြီး ထုတ်ပါ", reply_markup=MAIN_KB)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.message.from_user.id
    user = get_user(uid)
    now = datetime.now()

    if text == "📢 Join Channel":
        await update.message.reply_text(f"https://t.me/{CHANNEL_USERNAME}"); return
    elif text == "💎 VIP Info":
        # User ရဲ့ Status ကို စစ်ဆေးမယ်
        status_text = "💎 **Your Status**\n\n"
        if user["vip"]:
            status_text += "✅ Status: **VIP User (Lifetime)**\n"
            status_text += "🎊 သင်သည် VIP ဝန်ဆောင်မှုများကို အသုံးပြုနိုင်ပါပြီ။"
        else:
            status_text += "❌ Status: **Free User**\n\n"
            status_text += VIP_PRICE # အပေါ်မှာသတ်မှတ်ထားတဲ့ ဈေးနှုန်း message ပြမယ်

        # VIP status ပြသခြင်း (Tutorial video မပါတော့ပါ)
        if not user["vip"]:
            await update.message.reply_text(status_text, reply_markup=VIP_FREE_KB, parse_mode="Markdown")
        else:
            await update.message.reply_text(status_text, reply_markup=MAIN_KB, parse_mode="Markdown")
        return
    elif text == "💰 Buy VIP":
        await update.message.reply_text(PAYMENT_INFO, reply_markup=VIP_BACK_KB, parse_mode="Markdown"); return
    elif text == "🔙 Back":
        await update.message.reply_text("🏠 Main Menu", reply_markup=MAIN_KB); return

    if text in ["⚡ Wireguard Key", "🧩 Hiddify Key"]:
        # ၁။ Channel Join ထားခြင်း ရှိမရှိ အရင်စစ်မယ်
        if not await is_joined_channel(context.bot, uid):
            await update.message.reply_text(f"🚫 Channel Join ပြီးမှထုတ်ယူနိုင်ပါမည်။\nhttps://t.me/{CHANNEL_USERNAME}")
            return

        # ၂။ VIP မဟုတ်ရင် (Admin လည်းမဟုတ်ရင်) နှစ်ခုလုံး ပိတ်ထားမယ်
        if not user["vip"] and uid != ADMIN_ID:
            msg = (
                "🚫 **Key များ limit ပြည့်သွားသောကြောင့် အခမဲ့ ထုတ်ယူ၍မရနိုင်တော့ပါ။**\n\n"
                "✅ လိုင်းပိုမိုကောင်းမွန်ပြီး တည်ငြိမ်စွာအသုံးပြုနိုင်ရန် \n\n"
                "💎VIP Key Lifetime ကုန်ရက်မရှိ ကို 3000ks ဖြင့် ဝယ်ယူနိုင်ပါသည်\n\n✍️Channel ထဲတွင် အသုံးပြုသူများ၏ review ကို ကြည့်နိုင်ပါမည်။\n\n💎 vip user များတွတ် key ကို isp ဘတ်မှ ban ခဲ့ပါက အသစ်ပြန်ချိန်းပေးမည်ဖြစ်ကြောင်း\n\n 🥰ဝယ်ယူမည်ဆိုပါက အောက်က Buy Vip ခလုပ်ကိုနှိပ်၍ ဝယ်ယူနိုင်ပါတယ်ဗျ"
            )
            await update.message.reply_text(msg, reply_markup=VIP_FREE_KB, parse_mode="Markdown")
            return

        # ၃။ VIP user များအတွက် Time Limit စစ်ဆေးခြင်း
        col_to_check = "last_warp" if text == "⚡ Wireguard Key" else "last_hiddify"
        last_action_time = user[col_to_check]

        if uid != ADMIN_ID and last_action_time:
            limit = 1  # VIP ဆိုရင် ၁ ရက် ၁ ခါပဲ ထုတ်ခွင့်ပြုမယ်
            nt = datetime.fromtimestamp(last_action_time) + timedelta(days=limit)
            if now < nt:
                await update.message.reply_text(f"⏳ {text} အတွက် ကျန်ချိန်: {remaining(int((nt-now).total_seconds()))}")
                return

        # ၄။ အားလုံးအိုကေရင် Generate လုပ်ပေးမယ်
        status = await update.message.reply_text("⚙️ လုပ်ဆောင်နေပါသည်...")
        # ... (ကျန်တဲ့ generate logic တွေ ဆက်သွားပါမယ်)
        try:
            if text == "🧩 Hiddify Key":
                b64_str = generate_hiddify_base64()
                await update.message.reply_text(f"`{b64_str}`", parse_mode="MarkdownV2")
                guide = "👆 အပေါ်က code ကို copy ယူပါ။\n\nHiddify App ထဲဝင်ပြီး **➕အပေါင်း ခလုပ်နှိပ်ပါ** -> **Clipboard** နှိပ်ပါ။\n\n Tap To Connect နှိပ်ပြီးခနစောင့်ပါ"
                await update.message.reply_text(guide, parse_mode="Markdown")
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

            if uid != ADMIN_ID: 
                set_last_time(uid, col_to_check)
            await status.delete()
        except Exception as e: await status.edit_text(f"❌ Error: {e}")

# ================= ADMIN & LOGGING =================
async def payment_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid = user.id
    full_name = user.full_name
    username = f"@{user.username}" if user.username else "မရှိပါ"

    # Admin အတွက် အချက်အလက် caption စာသား
    admin_info = (
        "📩 *New Message Received*\n\n"
        f"👤 **Name:** {full_name}\n"
        f"🔗 **Username:** {username}\n"
        f"🆔 **ID:** `{uid}`\n\n"
        f"Approve: `/approvevip {uid}`\n"
        f"Reject: `/rejectvip {uid}`"
    )

    try:
        # ၁။ အကယ်၍ user ပို့လိုက်တာ စာသားသက်သက် (Text) ဖြစ်နေရင်
        if update.message.text:
            user_msg = update.message.text
            final_text = f"{admin_info}\n\n💬 *User Message:*\n{user_msg}"
            await context.bot.send_message(
                chat_id=PAYMENT_CHANNEL_ID, 
                text=final_text, 
                parse_mode="Markdown"
            )
        
        # ၂။ အကယ်၍ user ပို့လိုက်တာ ပုံ (Photo) သို့မဟုတ် ဖိုင် (Document/Video) ဖြစ်နေရင်
        else:
            await update.message.copy(
                chat_id=PAYMENT_CHANNEL_ID, 
                caption=admin_info, 
                parse_mode="Markdown"
            )
            
        await update.message.reply_text("Welcome...")

    except Exception as e:
        print(f"Error forwarding message: {e}")

async def approvevip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args: return
    uid = context.args[0]; set_vip(uid, True)
    await update.message.reply_text(f"✅ VIP Approved: {uid}")
    await context.bot.send_message(uid, "🎉 VIP Activated! Conf File ထုတ်ယူနိုင်ပါပြီ။\n\n ( /start ) 👈 နှိပ်ပေးပါ")

async def rejectvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args: return
    uid = context.args[0]; set_vip(uid, False)
    await update.message.reply_text(f"❌ VIP Rejected: {uid}")
    await context.bot.send_message(uid, "❌ VIP Rejected! ")

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

async def backup_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    try:
        # DB ဖိုင်ရှိမရှိ အရင်စစ်ပြီး ပို့ပေးမယ်
        if os.path.exists(DB_PATH):
            await update.message.reply_document(
                document=open(DB_PATH, "rb"),
                caption=f"📂 Database Backup\n📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            await update.message.reply_text("❌ Database file not found.")
    except Exception as e:
        await update.message.reply_text(f"❌ Backup failed: {e}")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 မင်္ဂလာပါ\n\n အဆင်မပြေဖြစ်ပါက\nadmin @mhwarpadmin သို့ဆက်သွယ်နိုင်ပါတယ်ဗျ။", reply_markup=MAIN_KB)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    # ၁။ Command တွေကို အရင်ဆုံးထားပါ (ဒါမှ /start တို့ /approveတို့ အလုပ်လုပ်မှာပါ)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approvevip", approvevip))
    app.add_handler(CommandHandler("rejectvip", rejectvip))
    app.add_handler(CommandHandler("viplist", viplist))
    app.add_handler(CommandHandler("vipmsg", vipmsg))
    app.add_handler(CommandHandler("allmsg", allmsg))
    app.add_handler(CommandHandler("send", send_user))
    app.add_handler(CommandHandler("backup", backup_db))
    app.add_handler(CommandHandler("admin", admin))

    # ၂။ Menu Buttons စာသားတွေကို ဒုတိယ ဦးစားပေးထားပါ
    # ဒီကောင်က MessageText ဖြစ်လို့ payment_photo ရဲ့ အပေါ်မှာ ရှိရပါမယ်
    menu_filter = filters.Text(["⚡ Wireguard Key", "🧩 Hiddify Key", "💎 VIP Info", "📢 Join Channel", "💰 Buy VIP", "🔙 Back"])
    app.add_handler(MessageHandler(menu_filter, menu))

    # ၃။ နောက်ဆုံးမှ User ပို့သမျှ (ပုံ၊ စာ၊ ဖိုင်) ကို ဖမ်းပြီး Channel ပို့ခိုင်းပါ
    # Command တွေနဲ့ Menu Button တွေ မဟုတ်တဲ့ အခြားအရာမှန်သမျှ ဒီထဲရောက်ပါမယ်
    app.add_handler(MessageHandler(
        (filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.TEXT) & ~filters.COMMAND, 
        payment_photo
    ))

    print("🤖 BOT STARTED")
    app.run_polling()
