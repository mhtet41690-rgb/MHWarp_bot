import os
import subprocess
import requests
import time
import threading
import http.server
import socketserver
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest

# --- Settings ---
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = "@mhwarp"  # သင့် Channel Username ကို ပြောင်းပါ
WGCF_URL = "https://github.com/ViRb3/wgcf/releases/latest/download/wgcf_2.2.30_linux_amd64"

# --- Koyeb Health Check Server ---
def run_health_server():
    """Koyeb Health Check အောင်မြင်ရန် Port 8080 (သို့မဟုတ် ပေးထားသော Port) တွင် Server ဖွင့်ခြင်း"""
    PORT = int(os.environ.get("PORT", 8080))
    Handler = http.server.SimpleHTTPRequestHandler
    # အငြင်းပွားမှုမရှိစေရန် အောက်ပါအတိုင်း ဖွင့်လှစ်ပါသည်
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Health Server running on port {PORT}")
        httpd.serve_forever()

def setup_wgcf():
    if not os.path.exists("wgcf"):
        print("Downloading wgcf binary...")
        response = requests.get(WGCF_URL)
        with open("wgcf", "wb") as f:
            f.write(response.content)
        os.chmod("wgcf", 0o755)

async def is_user_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📢 Join Our Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton("✅ Join ပြီးပါပြီ (Generate)", callback_data="check_and_gen")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"WARP Config ထုတ်ယူရန် ကျွန်ုပ်တို့၏ Channel ကို အရင် Join ပေးပါ။\n\nChannel: {CHANNEL_USERNAME}",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "check_and_gen":
        joined = await is_user_member(update, context)
        if not joined:
            await query.message.reply_text(f"⚠️ {CHANNEL_USERNAME} ကို အရင် Join ပေးပါ။", show_alert=True)
            return

        status_msg = await query.message.reply_text("⏳ Cloudflare နှင့် ချိတ်ဆက်နေပါသည်...")
        
        cwd = os.getcwd()
        wgcf_path = os.path.join(cwd, "wgcf")
        files_to_clean = ["wgcf-account.json", "wgcf-profile.conf", "wgcf-identity.json"]

        for f in files_to_clean:
            if os.path.exists(os.path.join(cwd, f)): os.remove(os.path.join(cwd, f))

        try:
            setup_wgcf()
            
            # Retry logic for Cloudflare IP blocks
            success = False
            for i in range(3):
                reg = subprocess.run([wgcf_path, "register", "--accept-tos"], capture_output=True, text=True, cwd=cwd)
                if reg.returncode == 0:
                    gen = subprocess.run([wgcf_path, "generate"], capture_output=True, text=True, cwd=cwd)
                    if gen.returncode == 0:
                        success = True
                        break
                time.sleep(2)

            if success and os.path.exists("wgcf-profile.conf"):
                with open("wgcf-profile.conf", "r") as f:
                    content = f.read()
                
                new_content = content.replace(":2408", ":500")
                with open("wgcf-profile.conf", "w") as f:
                    f.write(new_content)

                with open("wgcf-profile.conf", "rb") as file:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=file, 
                        filename="MH_WARP.conf",
                        caption="Configကိုဒေါင်းပြီ Wireguard တွင်အသုံးပြုနိုင်ပါပြီ။"
                    )
            else:
                await query.message.reply_text("❌ Cloudflare အလုပ်များနေပါသည်။ ခဏနေမှ ပြန်စမ်းပါ။")

        except Exception as e:
            await query.message.reply_text(f"❌ Error: {str(e)[:50]}")
        
        finally:
            for f in files_to_clean:
                if os.path.exists(os.path.join(cwd, f)): os.remove(os.path.join(cwd, f))
            await status_msg.delete()

if __name__ == '__main__':
    setup_wgcf()
    
    # Koyeb အတွက် Health Server ကို Background Thread ဖြင့် Run ပါ
    threading.Thread(target=run_health_server, daemon=True).start()
    
    if TOKEN:
        print("Bot is starting on Koyeb...")
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.run_polling()
