import os
import subprocess
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest

# --- Settings ---
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = "@mhwarp" # သင့် Channel Username ကို အမှန်ပြင်ထည့်ပါ
WGCF_URL = "https://github.com/ViRb3/wgcf/releases/latest/download/wgcf_2.2.30_linux_amd64"

def setup_wgcf():
    if not os.path.exists("wgcf"):
        response = requests.get(WGCF_URL)
        with open("wgcf", "wb") as f:
            f.write(response.content)
        os.chmod("wgcf", 0o755)

async def is_user_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User က Channel ကို Join ထားသလား စစ်ဆေးခြင်း"""
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        # member status က left သို့မဟုတ် kicked မဟုတ်ရင် Join ထားတယ်လို့ သတ်မှတ်တယ်
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except BadRequest:
        # Bot က Channel မှာ Admin မဟုတ်ရင် ဒါမှမဟုတ် Chat မတွေ့ရင် Error တက်နိုင်တယ်
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Channel Join ရန် Button ပြပေးခြင်း
    keyboard = [
        [InlineKeyboardButton("📢 Join Our Channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton("✅ Join ပြီးပါပြီ (Generate)", callback_data="check_and_gen")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"မင်္ဂလာပါ။ WARP Config ထုတ်ယူနိုင်ရန် ကျွန်ုပ်တို့၏ Channel ကို အရင် Join ပေးပါ။\n\nChannel: {CHANNEL_USERNAME}",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "check_and_gen":
        # ၁။ Join ထားခြင်း ရှိ/မရှိ အရင်စစ်မယ်
        joined = await is_user_member(update, context)
        
        if not joined:
            await query.message.reply_text(
                f"⚠️ သင် Channel ကို မ Join ရသေးပါ။ ကျေးဇူးပြု၍ {CHANNEL_USERNAME} ကို အရင် Join ပေးပါ။",
                show_alert=True # Alert box အနေနဲ့ ပြမယ်
            )
            return

        # ၂။ Join ထားရင် Config စထုတ်မယ်
        status_msg = await query.message.reply_text("⏳ Membership အတည်ပြုပြီးပါပြီ။ Config ထုတ်နေပါသည်...")
        
        cwd = os.getcwd()
        wgcf_path = os.path.join(cwd, "wgcf")
        files_to_clean = ["wgcf-account.json", "wgcf-profile.conf", "wgcf-identity.json"]

        try:
            setup_wgcf()
            # အဟောင်းများ ရှင်းလင်းခြင်း
            for f in files_to_clean:
                if os.path.exists(os.path.join(cwd, f)): os.remove(os.path.join(cwd, f))

            # Register & Generate
            subprocess.run([wgcf_path, "register", "--accept-tos"], check=True, cwd=cwd, capture_output=True)
            subprocess.run([wgcf_path, "generate"], check=True, cwd=cwd, capture_output=True)

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
                        filename="WARP_MH.conf",
                        caption="✅ Channel Join ထားပေးသည့်အတွက် ကျေးဇူးတင်ပါသည်။\n\nWireGuard တွင် အသုံးပြုနိုင်ပါပြီ။"
                    )
            else:
                await query.message.reply_text("❌ Config ဖိုင် ထုတ်မရဖြစ်နေပါသည်။ ခဏနေမှ ပြန်စမ်းပါ။")

        except Exception as e:
            await query.message.reply_text(f"❌ Error: {str(e)[:100]}")
        
        finally:
            for f in files_to_clean:
                if os.path.exists(os.path.join(cwd, f)): os.remove(os.path.join(cwd, f))
            await status_msg.delete()

if __name__ == '__main__':
    setup_wgcf()
    if TOKEN:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.run_polling()
