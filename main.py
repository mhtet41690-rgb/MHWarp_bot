import os
import subprocess
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest

# --- Settings ---
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = "@mhwarp" # သင့် Channel Username ကို ပြောင်းပါ
WGCF_URL = "https://github.com/ViRb3/wgcf/releases/latest/download/wgcf_2.2.30_linux_amd64"

def setup_wgcf():
    if not os.path.exists("wgcf"):
        response = requests.get(WGCF_URL)
        with open("wgcf", "wb") as f:
            f.write(response.content)
        os.chmod("wgcf", 0o755)

async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['left', 'kicked']:
            return False
        return True
    except BadRequest:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Button တည်ဆောက်ခြင်း
    keyboard = [
        [InlineKeyboardButton("🚀 Generate WARP Config", callback_data="gen_warp")],
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"မင်္ဂလာပါ။ Cloudflare WARP Config ထုတ်ယူရန် အောက်က Button ကို နှိပ်ပါ။\n\n(Channel join ထားရန် လိုအပ်ပါသည်)",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Button နှိပ်လိုက်တာကို bot က သိအောင် အကြောင်းပြန်ခြင်း

    if query.data == "gen_warp":
        # Force Join Check
        is_member = await check_membership(update, context)
        if not is_member:
            await query.message.reply_text(
                f"❌ အသုံးပြုခွင့် မရှိသေးပါ။\n\nကျေးဇူးပြု၍ {CHANNEL_USERNAME} ကို အရင် Join ပေးပါ။"
            )
            return

        status_msg = await query.message.reply_text("Processing... Please wait.")
        try:
            setup_wgcf()
            for f in ["wgcf-account.json", "wgcf-profile.conf"]:
                if os.path.exists(f): os.remove(f)

            subprocess.run(["./wgcf", "register", "--accept-tos"], check=True)
            subprocess.run(["./wgcf", "generate"], check=True)

            if os.path.exists("wgcf-profile.conf"):
                with open("wgcf-profile.conf", "r") as f:
                    content = f.read()
                
                new_content = content.replace(":2408", ":500")
                
                with open("wgcf-profile.conf", "w") as f:
                    f.write(new_content)

                with open("wgcf-profile.conf", "rb") as file:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=file, 
                        filename="MH_Warp.conf",
                        caption="Conf ကိုဒေါင်းပြီး wireguard တွင်အသုံးပြုနိုင်ပါပြီ။❗ရောင်းချခွင့် မပြု ❗"
                    )
            else:
                await query.message.reply_text("Failed to generate config.")
        except Exception as e:
            await query.message.reply_text(f"Error: {e}")
        finally:
            for f in ["wgcf-account.json", "wgcf-profile.conf"]:
                if os.path.exists(f): os.remove(f)
            await status_msg.delete()

if __name__ == '__main__':
    setup_wgcf()
    if TOKEN:
        app = ApplicationBuilder().token(TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        # Button နှိပ်ခြင်းကို handle လုပ်ရန်
        app.add_handler(CallbackQueryHandler(button_handler))
        
        app.run_polling()
