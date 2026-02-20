import os
import requests
import logging
import psycopg2 
import asyncio
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    CallbackQueryHandler
)

# --- الإعدادات ---
TOKEN = "7751947016:AAHFArUstq0G0HqvNy1jQFZXQ2Xx5Cto39Q"
CMC_API_KEY = "8a097472-4ae1-4e81-811d-c930269d0613"
WEBHOOK_URL = "https://zeeeeeeo.onrender.com" 
PORT = int(os.environ.get('PORT', 5000))
ADMIN_ID = 6172153716 
DATABASE_URL = "postgresql://neondb_owner:npg_yPL6dYWRZQ4o@ep-little-firefly-aifch2tu-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- إدارة قاعدة بيانات PostgreSQL ---
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id BIGINT PRIMARY KEY, 
                  username TEXT, 
                  balance INTEGER DEFAULT 1000, 
                  wallet TEXT DEFAULT 'غير محدد')''')
    
    # حساب تجريبي للمطور
    c.execute("""
        INSERT INTO users (id, username, balance, wallet) 
        VALUES (565965404, 'Tester', 100000, 'غير محدد') 
        ON CONFLICT (id) DO UPDATE SET balance = 100000
    """)
    conn.commit()
    c.close()
    conn.close()

def get_user(user_id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, username, balance, wallet FROM users WHERE id=%s", (user_id,))
        user = c.fetchone()
        c.close()
        conn.close()
        return user
    except:
        return None

def save_user(user_id, username, balance, wallet):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (id, username, balance, wallet) 
        VALUES (%s, %s, %s, %s) 
        ON CONFLICT (id) DO UPDATE SET username=%s, wallet=%s
    """, (user_id, username, balance, wallet, username, wallet))
    conn.commit()
    c.close()
    conn.close()

def update_balance(user_id, amount):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
    conn.commit()
    c.close()
    conn.close()

# --- جلب السعر اللحظي ---
def get_crypto_price(symbol):
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        parameters = {'symbol': symbol.strip().upper(), 'convert': 'USD'}
        headers = {'Accepts': 'application/json', 'X-CMC_PRO_API_KEY': CMC_API_KEY}
        response = requests.get(url, headers=headers, params=parameters, timeout=10)
        data = response.json()
        return data['data'][symbol.upper()]['quote']['USD']['price']
    except:
        return None

# --- معالجة الرهان ---
async def process_bet(context, user_id, symbol, entry_price, direction):
    await asyncio.sleep(30)
    exit_price = get_crypto_price(symbol)
    if exit_price:
        if exit_price == entry_price:
            status = "🟡 **تعادل!**"
            result_msg = "السعر مستقر تماماً، تم استعادة رصيدك. 🤝"
        else:
            win = (direction == "up" and exit_price > entry_price) or (direction == "down" and exit_price < entry_price)
            amount = 200 if win else -200 
            update_balance(user_id, amount)
            status = "🟢 **صفقة ناجحة!** +200" if win else "🔴 **فشل التحليل!** -200"
            result_msg = "استمر في تحليل السوق، الفرص لا تنتهي! 🚀" if not win else "أحسنت! رؤيتك للسوق ثاقبة. 🔥"
        
        msg = (f"📊 **تقرير التداول: {symbol}**\n"
               f"━━━━━━━━━━━━━━\n"
               f"📉 سعر الدخول: `${entry_price:.4f}`\n"
               f"📈 سعر الإغلاق: `${exit_price:.4f}`\n"
               f"━━━━━━━━━━━━━━\n"
               f"💰 النتيجة: {status}\n"
               f"✨ {result_msg}")
        await context.bot.send_message(user_id, msg, parse_mode='HTML')
    else:
        await context.bot.send_message(user_id, "⚠️ **عذراً!** حدث اضطراب في الاتصال بالسوق، تم حفظ نقاطك.")

# --- الأوامر الأساسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"User_{user_id}"
    
    if not get_user(user_id):
        if context.args:
            try:
                ref_id = int(context.args[0])
                if get_user(ref_id):
                    update_balance(ref_id, 200)
                    await context.bot.send_message(ref_id, "🎉 **مكافأة إحالة!** صديقك انضم وحصلت على 200 نقطة.", parse_mode='HTML')
            except: pass
        save_user(user_id, username, 1000, "غير محدد")

    keyboard = [
        ['💎 ابدأ التداول'],
        ['📋 المحفظة', '👤 بروفايلي'],
        ['💸 سحب الأرباح', '🔥 نقاط مجانية']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"👋 **أهلاً بك في بوت زينو محاميد!**\n\n"
        f"أنت الآن في قلب سوق الكريبتو. توقع حركة العملات، اجمع النقاط، وحوّلها إلى أرباح حقيقية! 💹\n\n"
        f"🎁 **هدية البداية:** 1,000 نقطة مجانية!",
        reply_markup=reply_markup, parse_mode='HTML'
    )

# --- معالجة الرسائل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user: return

    if text == '👤 بروفايلي':
        msg = (f"👤 **معلومات المتداول: {user[1]}**\n"
               f"━━━━━━━━━━━━━━\n"
               f"🆔 المعرف: `{user[0]}`\n"
               f"💰 رصيدك: **{user[2]:,} نقطة**\n"
               f"💵 القيمة التقديرية: **${user[2]/1000:.2f} USDT**\n"
               f"🏦 عنوان السحب: `{user[3]}`\n"
               f"━━━━━━━━━━━━━━\n"
               f"💡 استمر في التداول لرفع قيمتك السوقية!")
        await update.message.reply_text(msg, parse_mode='HTML')

    elif text == '💎 ابدأ التداول':
        if user[2] < 200:
            bot_info = await context.bot.get_me()
            share_link = f"https://t.me/{bot_info.username}?start={user_id}"
            await update.message.reply_text(
                f"❌ **الرصيد غير كافٍ!**\n\nأنت بحاجة لـ 200 نقطة لفتح صفقة جديدة.\n\n"
                f"شارك رابطك واحصل على نقاط فورية:\n{share_link}",
                parse_mode='HTML'
            )
            return

        coins = ['BTC', 'ETH', 'BNB', 'SOL', 'TON', 'XRP', 'DOT', 'DOGE', 'AVAX', 'ADA']
        keyboard = [[InlineKeyboardButton(f"🪙 {c}", callback_data=f"bet_{c}")] for c in coins]
        await update.message.reply_text("🎯 **اختر العملة التي تريد تحليل مسارها:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif text == '📋 المحفظة':
        await update.message.reply_text("📥 **تحديث بيانات السحب**\n\nأرسل الآن عنوان محفظتك (USDT-TRC20) لاستلام أرباحك عليه:", parse_mode='HTML')
        context.user_data['waiting_for_wallet'] = True

    elif text == '💸 سحب الأرباح':
        if user[2] < 10000:
            await update.message.reply_text(
                f"🚧 **عذراً، لم تصل للحد الأدنى!**\n\nالحد الأدنى للسحب هو: **10,000 نقطة**.\n"
                f"رصيدك الحالي: **{user[2]:,} نقطة**.\n\nشد حيلك يا بطل، اقتربت من الهدف! 🚀", 
                parse_mode='HTML'
            )
        elif user[3] == "غير محدد":
            await update.message.reply_text("⚠️ **المحفظة غير مسجلة!**\nيرجى الضغط على زر 'المحفظة' وإرسال عنوانك أولاً.", parse_mode='HTML')
        else:
            await update.message.reply_text(
                f"💰 **طلب سحب أرباح**\n\nرصيدك القابل للسحب: **{user[2]:,} نقطة**\n"
                f"أرسل الكمية التي تود تحويلها الآن:",
                parse_mode='HTML'
            )
            context.user_data['waiting_for_withdraw_amount'] = True

    elif text == '🔥 نقاط مجانية':
        bot_info = await context.bot.get_me()
        share_link = f"https://t.me/{bot_info.username}?start={user_id}"
        msg = (f"🤝 **برنامج شركاء زينو محاميد**\n\n"
               f"شارك رابطك مع أصدقائك، وعند انضمام أي شخص ستحصل على **200 نقطة** فوراً!\n\n"
               f"🔗 **رابطك الخاص:**\n`{share_link}`")
        await update.message.reply_text(msg, parse_mode='HTML')

    elif context.user_data.get('waiting_for_wallet'):
        save_user(user_id, user[1], user[2], text)
        context.user_data['waiting_for_wallet'] = False
        await update.message.reply_text("✅ **تم حفظ العنوان بنجاح!** يمكنك الآن سحب أرباحك عند وصولك للحد الأدنى.")

    elif context.user_data.get('waiting_for_withdraw_amount'):
        try:
            amount = int(text)
            if amount < 10000:
                await update.message.reply_text("❌ الحد الأدنى للسحب هو 10,000 نقطة.")
            elif amount > user[2]:
                await update.message.reply_text(f"❌ رصيدك الحالي {user[2]:,} فقط.")
            else:
                update_balance(user_id, -amount)
                context.user_data['waiting_for_withdraw_amount'] = False
                await update.message.reply_text(f"✅ **تم استلام طلبك!**\n\nسيتم مراجعة العملية وإرسال **{amount:,} نقطة** إلى محفظتك خلال 24 ساعة. 🎖", parse_mode='HTML')
                admin_msg = (f"🔔 **طلب سحب جديد**\n\nالمستخدم: @{user[1]}\nID: `{user[0]}`\nالكمية: {amount:,}\nالمحفظة: `{user[3]}`")
                await context.bot.send_message(ADMIN_ID, admin_msg, parse_mode='HTML')
        except:
            await update.message.reply_text("⚠️ يرجى إدخال أرقام صحيحة فقط.")

async def bet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user = get_user(user_id)
    
    await query.answer()
    
    if not user or user[2] < 200:
        await query.edit_message_text("❌ رصيدك لا يسمح بفتح صفقة.")
        return

    if query.data.startswith("bet_"):
        symbol = query.data.split("_")[1]
        price = get_crypto_price(symbol)
        if not price:
            await query.edit_message_text("❌ عذراً، تعذر جلب السعر اللحظي حالياً.")
            return
        context.user_data.update({'coin': symbol, 'price': price})
        keyboard = [[InlineKeyboardButton("📈 صعود (Long)", callback_data="dir_up"), 
                     InlineKeyboardButton("📉 هبوط (Short)", callback_data="dir_down")]]
        await query.edit_message_text(f"📊 **سوق {symbol}**\nالسعر الحالي: `${price:.4f}`\n\nتوقع اتجاه السعر بعد 30 ثانية من الآن:", 
                                     reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    elif query.data.startswith("dir_"):
        direction = "up" if query.data.split("_")[1] == "up" else "down"
        dir_text = "صعود 📈" if direction == "up" else "هبوط 📉"
        await query.edit_message_text(f"⚡️ **تم فتح الصفقة بنجاح!**\nتوقعك: {dir_text}\n\nيرجى الانتظار 30 ثانية لمعالجة النتيجة... ⏳", parse_mode='HTML')
        asyncio.create_task(process_bet(context, query.from_user.id, context.user_data['coin'], context.user_data['price'], direction))

# --- تشغيل البوت ---
if __name__ == '__main__':
    init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(bet_callback))
    application.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")
