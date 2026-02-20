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

# --- معالجة الرهان (30 ثانية) ---
async def process_bet(context, user_id, symbol, entry_price, direction):
    await asyncio.sleep(30)
    exit_price = get_crypto_price(symbol)
    if exit_price:
        if exit_price == entry_price:
            status = "🟡 تعادل! السعر لم يتغير"
            result_msg = "لم تخسر أي نقاط. رصيدك كما هو. 🤝"
        else:
            win = (direction == "up" and exit_price > entry_price) or (direction == "down" and exit_price < entry_price)
            amount = 200 if win else -200 
            update_balance(user_id, amount)
            status = "🟢 ربح! +200 نقطة" if win else "🔴 خسارة! -200 نقطة"
            result_msg = "تم اكتمال تحليل السوق."
        
        msg = (f"🏆 <b>نتيجة تداول {symbol}</b>\n"
               f"━━━━━━━━━━━━━━\n"
               f"📉 دخول: <code>${entry_price:.4f}</code>\n"
               f"📈 خروج: <code>${exit_price:.4f}</code>\n"
               f"━━━━━━━━━━━━━━\n"
               f"<b>{status}</b>\n"
               f"{result_msg}")
        await context.bot.send_message(user_id, msg, parse_mode='HTML')
    else:
        await context.bot.send_message(user_id, "⚠️ خطأ في الشبكة. تم إعادة النقاط لرصيدك.")

# --- الأوامر الأساسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"Pilot_{user_id}"
    
    if not get_user(user_id):
        if context.args:
            try:
                ref_id = int(context.args[0])
                if get_user(ref_id):
                    update_balance(ref_id, 200)
                    await context.bot.send_message(ref_id, "🚀 <b>طيار جديد انضم!</b> لقد حصلت على 200 نقطة.", parse_mode='HTML')
            except: pass
        save_user(user_id, username, 1000, "غير محدد")

    keyboard = [
        ['🎮 ابدأ التداول'],
        ['💼 المحفظة', '👤 الحساب'],
        ['🏧 سحب الأرباح', '📢 ربح نقاط']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"🌕 <b>أهلاً بك في Binance Moonbix بالعربي!</b>\n\nاستكشف مجرة العملات الرقمية واربح النقاط عبر توقع حركة السوق. 🚀",
        reply_markup=reply_markup, parse_mode='HTML'
    )

# --- أوامر الإدمن ---
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return 

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(balance) FROM users")
    stats = c.fetchone()
    c.close()
    conn.close()

    total_users = stats[0] or 0
    total_balance = stats[1] or 0
    
    msg = (f"📊 <b>إحصائيات Binance Moonbix</b>\n"
           f"━━━━━━━━━━━━━━\n"
           f"👥 إجمالي المستخدمين: <b>{total_users}</b>\n"
           f"💰 إجمالي النقاط: <b>{total_balance:,} نقطة</b>\n"
           f"💵 القيمة الإجمالية: <b>${total_balance/1000:,.2f} USDT</b>")
    await update.message.reply_text(msg, parse_mode='HTML')

async def clear_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM users")
        conn.commit()
        c.close()
        conn.close()
        await update.message.reply_text("✅ <b>تم مسح البيانات:</b> تم حذف جميع المستخدمين من السجلات.", parse_mode='HTML')
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ أثناء المسح: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user: return

    if text == '👤 الحساب':
        msg = (f"🚀 <b>طيار Moonbix: @{user[1]}</b>\n"
               f"━━━━━━━━━━━━━━\n"
               f"🆔 المعرف: <code>{user[0]}</code>\n"
               f"💰 الرصيد: <b>{user[2]:,} نقطة</b>\n"
               f"💵 القيمة: <b>${user[2]/1000:.2f} USDT</b>\n"
               f"🏦 المحفظة (TRC20): <code>{user[3]}</code>")
        await update.message.reply_text(msg, parse_mode='HTML')

    elif text == '🎮 ابدأ التداول':
        if user[2] < 200:
            bot_info = await context.bot.get_me()
            share_link = f"https://t.me/{bot_info.username}?start={user_id}"
            await update.message.reply_text(
                f"❌ <b>رصيدك غير كافٍ:</b>\n\nتحتاج على الأقل لـ 200 نقطة للعب.\n\n"
                f"ادعُ أصدقاءك للحصول على المزيد من النقاط! 🚀\n\n"
                f"🔗 رابط الإحالة الخاص بك:\n{share_link}",
                parse_mode='HTML'
            )
            return

        coins = ['BTC', 'ETH', 'BNB', 'SOL', 'TON', 'XRP', 'DOT', 'DOGE', 'AVAX', 'ADA']
        keyboard = [[InlineKeyboardButton(f"🪙 {c}", callback_data=f"bet_{c}")] for c in coins]
        await update.message.reply_text("✨ <b>اختر العملة للتحليل:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif text == '💼 المحفظة':
        await update.message.reply_text("🔗 <b>إعداد المحفظة</b>\nمن فضلك أرسل عنوان <b>TRC20</b> الخاص بك:", parse_mode='HTML')
        context.user_data['waiting_for_wallet'] = True

    elif text == '🏧 سحب الأرباح':
        if user[2] < 10000:
            await update.message.reply_text(
                f"⚠️ <b>الوصول مرفوض!</b>\n\nالحد الأدنى للسحب: <b>10,000 نقطة</b>.\n"
                f"رصيدك الحالي: <b>{user[2]:,} نقطة</b>.\n\nواصل التداول للوصول للقمر! 🚀", 
                parse_mode='HTML'
            )
        elif user[3] == "غير محدد":
            await update.message.reply_text("❌ <b>المحفظة مفقودة!</b>\nيرجى ضبط عنوان TRC20 الخاص بك أولاً.", parse_mode='HTML')
        else:
            await update.message.reply_text(
                f"✅ <b>جاهز للإقلاع!</b>\n\nالمتاح للسحب: {user[2]:,} نقطة\n"
                f"أدخل الكمية التي تريد سحبها:",
                parse_mode='HTML'
            )
            context.user_data['waiting_for_withdraw_amount'] = True

    elif text == '📢 ربح نقاط':
        bot_info = await context.bot.get_me()
        share_link = f"https://t.me/{bot_info.username}?start={user_id}"
        msg = (f"🎁 <b>برنامج إحالة Moonbix</b>\n\n"
               f"ادعُ أصدقاءك واحصل على <b>200 نقطة</b> فوراً لكل صديق!\n\n"
               f"🔗 <b>رابط الدعوة الخاص بك:</b>\n{share_link}")
        await update.message.reply_text(msg, parse_mode='HTML', disable_web_page_preview=True)

    elif context.user_data.get('waiting_for_wallet'):
        save_user(user_id, user[1], user[2], text)
        context.user_data['waiting_for_wallet'] = False
        await update.message.reply_text("✅ <b>تم ربط المحفظة بنجاح!</b>", parse_mode='HTML')

    elif context.user_data.get('waiting_for_withdraw_amount'):
        try:
            amount = int(text)
            if amount < 10000:
                await update.message.reply_text("⚠️ <b>كمية غير صالحة!</b>\nالحد الأدنى للسحب 10,000 نقطة.")
            elif amount > user[2]:
                await update.message.reply_text(f"❌ <b>رصيد غير كافٍ!</b>\nلديك فقط {user[2]:,} نقطة.")
            else:
                update_balance(user_id, -amount)
                context.user_data['waiting_for_withdraw_amount'] = False
                await update.message.reply_text(f"🎊 <b>تم إرسال طلب السحب!</b>\n\nجاري معالجة {amount:,} نقطة.", parse_mode='HTML')
                admin_msg = (f"🔔 <b>طلب سحب جديد</b>\n\nالطيار: @{user[1]}\nID: <code>{user[0]}</code>\nالكمية: {amount:,} Pts\nالمحفظة: <code>{user[3]}</code>")
                await context.bot.send_message(ADMIN_ID, admin_msg, parse_mode='HTML')
        except:
            await update.message.reply_text("❌ <b>خطأ!</b> يرجى إدخال أرقام فقط.")

async def bet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user = get_user(user_id)
    
    await query.answer()
    
    if not user or user[2] < 200:
        await query.edit_message_text("❌ رصيدك نفذ أو المستخدم غير موجود!")
        return

    if query.data.startswith("bet_"):
        symbol = query.data.split("_")[1]
        price = get_crypto_price(symbol)
        if not price:
            await query.edit_message_text("❌ خطأ في البيانات. حاول عملة أخرى.")
            return
        context.user_data.update({'coin': symbol, 'price': price})
        keyboard = [[InlineKeyboardButton("📈 صعود (UP)", callback_data="dir_up"), 
                     InlineKeyboardButton("📉 هبوط (DOWN)", callback_data="dir_down")]]
        await query.edit_message_text(f"🪙 <b>سوق {symbol}</b>\nالسعر الحالي: <code>${price:.4f}</code>\n\nتوقع الحركة خلال 30 ثانية:", 
                                     reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    elif query.data.startswith("dir_"):
        direction = "up" if query.data.split("_")[1] == "up" else "down"
        dir_text = "صعود 📈" if direction == "up" else "هبوط 📉"
        await query.edit_message_text(f"🚀 <b>تم تنفيذ الصفقة!</b>\nالاتجاه: {dir_text}\nانتظر (30 ثانية)... ⏳", parse_mode='HTML')
        asyncio.create_task(process_bet(context, query.from_user.id, context.user_data['coin'], context.user_data['price'], direction))

if __name__ == '__main__':
    init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CommandHandler("clear_all", clear_all_users))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(bet_callback))
    application.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")
