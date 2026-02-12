import os
import subprocess
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# --- Settings ---
TOKEN = os.getenv("BOT_TOKEN")
# Join စေချင်တဲ့ Channel Username ကို ဒီမှာထည့်ပါ (တိုက်တွန်းရုံသက်သက်ဖြစ်သည်)
CHANNEL_USERNAME = "@mhwarp" 
WGCF_URL = "https://github.com/ViRb3/wgcf/releases/latest/download/wgcf_2.2.30_linux_amd64"

def setup_wgcf():
    if not os.path.exists("wgcf"):
        response = requests.get(WGCF_URL)
        with open("wgcf", "wb") as f:
            f.write(response.content)
        os.chmod("wgcf", 0o755)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Button ၂ ခုပြမယ် (Join ဖို့ တိုက်တွန်းတဲ့ Button နဲ့ တန်းထုတ်မယ့် Button)
    keyboard = [
        [InlineKeyboardButton("📢 Join Our Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton("🚀 Generate WARP Config", callback_data="gen_warp")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"မင်္ဂလာပါ။ Update အသစ်တွေသိရဖို့ {CHANNEL_USERNAME} ကို Join ထားနိုင်ပါတယ်။\n\nConfig ထုတ်ယူရန် Generate Button ကို နှိပ်ပါ။",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "gen_warp":
        status_msg = await query.message.reply_text("Processing... Please wait.")
        try:
            setup_wgcf()
            for f in ["wgcf-account.json", "wgcf-profile.conf"]:
                if os.path.exists(f): os.remove(f)

            subprocess.run(["./wgcf", "register", "--accept-tos"], check=True)
            subprocess.run(["./wgcf", "generate"], check=True)

            if os.path.exists("wgcf-profile.conf"):
                # Port 500 သို့ ပြောင်းလဲခြင်း
                with open("wgcf-profile.conf", "r") as f:
                    content = f.read()
                
                new_content = content.replace(":2408", ":500")
                
                with open("wgcf-profile.conf", "w") as f:
                    f.write(new_content)

                # User ထံသို့ File ပို့ပေးခြင်း
                with open("wgcf-profile.conf", "rb") as file:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=file, 
                        filename="MHWarp.conf",
                        caption="conf ကို ဒေါင်းပြီး wireguard တွင်အသုံးပြုနိုင်ပါပြီ ❗ရောင်းချခွင့်မပြု❗။"
                    )
            else:
                await query.message.reply_text("Error: Config ဖိုင်ထုတ်ယူ၍ မရနိုင်ပါ။")
        
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
        app.add_handler(CallbackQueryHandler(button_handler))
        app.run_polling()
