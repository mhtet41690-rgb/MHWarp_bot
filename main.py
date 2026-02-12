import os
import subprocess
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Railway Variables ထဲမှာ BOT_TOKEN ထည့်ထားပေးပါ
TOKEN = os.getenv("BOT_TOKEN")
WGCF_URL = "https://github.com/ViRb3/wgcf/releases/latest/download/wgcf_2.2.23_linux_amd64"

def setup_wgcf():
    if not os.path.exists("wgcf"):
        print("Downloading wgcf...")
        response = requests.get(WGCF_URL)
        with open("wgcf", "wb") as f:
            f.write(response.content)
        os.chmod("wgcf", 0o755)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cloudflare WARP Config ထုတ်ရန် /generate ကို နှိပ်ပါ။")

async def generate_warp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("Processing... Please wait.")
    try:
        setup_wgcf()
        # အဟောင်းတွေ ဖျက်မယ်
        for f in ["wgcf-account.json", "wgcf-profile.conf"]:
            if os.path.exists(f): os.remove(f)

        # Config အသစ်ထုတ်မယ်
        subprocess.run(["./wgcf", "register", "--accept-tos"], check=True)
        subprocess.run(["./wgcf", "generate"], check=True)

        if os.path.exists("wgcf-profile.conf"):
            # --- Port 500 သို့ ပြောင်းလဲခြင်း ---
            with open("wgcf-profile.conf", "r") as f:
                content = f.read()
            
            # ပုံမှန် port 2408 ကို 500 နဲ့ အစားထိုးပါတယ်
            new_content = content.replace(":2408", ":500")
            
            with open("wgcf-profile.conf", "w") as f:
                f.write(new_content)
            # --------------------------------

            with open("wgcf-profile.conf", "rb") as file:
                await update.message.reply_document(
                    document=file, 
                    filename="WARP_Port500.conf",
                    caption="Conf ကိုဒေါင်းပြီး wireguard တွင်အသုံးပြုနိုင်ပါပြီ ။"
                )
        else:
            await update.message.reply_text("Failed to generate config.")
            
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
    finally:
        # File တွေကို ပြန်ဖျက်ထုတ်မယ် (Privacy အတွက်)
        for f in ["wgcf-account.json", "wgcf-profile.conf"]:
            if os.path.exists(f): os.remove(f)
        await status_msg.delete()

if __name__ == '__main__':
    setup_wgcf()
    if not TOKEN:
        print("Error: BOT_TOKEN is missing!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("generate", generate_warp))
        app.run_polling()
