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
        win = (direction == "up" and exit_price > entry_price) or (direction == "down" and exit_price < entry_price)
        if exit_price == entry_price:
            status = "🟡 تعادل! السعر لم يتغير"
            result_msg = "لم تخسر أي نقاط. 🤝"
        else:
            amount = 200 if win else -200 
            update_balance(user_id, amount)
            status = "🟢 ربح! +200 نقطة" if win else "🔴 خسارة! -200 نقطة"
            result_msg = "تم اكتمال تحليل السوق بنجاح."
        
        msg = (f"🏆 <b>نتيجة تداول {symbol}</b>\n"
               f"━━━━━━━━━━━━━━\n"
               f"📉 دخول: <code>${entry_price:.4f}</code>\n"
               f"📈 خروج: <code>${exit_price:.4f}</code>\n"
               f"━━━━━━━━━━━━━━\n"
               f"<b>{status}</b>\n"
               f"{result_msg}")
        await context.bot.send_message(user_id, msg, parse_mode='HTML')
    else:
        await context.bot.send_message(user_id, "⚠️ عذراً، حدث خطأ في تحديث الأسعار.")

# --- أوامر الإدمن ---
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(balance) FROM users")
    stats = c.fetchone()
    c.close()
    conn.close()
    msg = (f"📊 <b>إحصائيات زينو محاميد</b>\n\n"
           f"👥 المستخدمين: {stats[0]}\n"
           f"💰 إجمالي النقاط: {stats[1]:,}")
    await update.message.reply_text(msg, parse_mode='HTML')

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
                    await context.bot.send_message(ref_id, "🚀 <b>صديق جديد انضم!</b> حصلت على 200 نقطة.", parse_mode='HTML')
            except: pass
        save_user(user_id, username, 1000, "غير محدد")

    keyboard = [['🎮 ابدأ التداول'], ['💼 المحفظة', '👤 الحساب'], ['🏧 سحب الأرباح', '📢 ربح نقاط']]
    await update.message.reply_text(
        f"👋 <b>أهلاً بك في بوت زينو محاميد!</b>\n\nتوقع حركة السوق واربح النقاط. 💹\n🎁 هدية: 1,000 نقطة!",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True), parse_mode='HTML'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user: return

    if text == '👤 الحساب':
        msg = (f"🚀 <b>طيار زينو محاميد: @{user[1]}</b>\n"
               f"💰 الرصيد: <b>{user[2]:,} نقطة</b>\n"
               f"🏦 المحفظة: <code>{user[3]}</code>")
        await update.message.reply_text(msg, parse_mode='HTML')

    elif text == '🎮 ابدأ التداول':
        if user[2] < 200:
            bot_info = await context.bot.get_me()
            link = f"https://t.me/{bot_info.username}?start={user_id}"
            await update.message.reply_text(f"❌ رصيدك ضعيف! ادعُ أصدقاءك:\n{link}", parse_mode='HTML')
            return
        coins = ['BTC', 'ETH', 'BNB', 'SOL', 'TON']
        keyboard = [[InlineKeyboardButton(f"🪙 {c}", callback_data=f"bet_{c}")] for c in coins]
        await update.message.reply_text("✨ <b>اختر العملة:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif text == '📢 ربح نقاط':
        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={user_id}"
        await update.message.reply_text(f"🤝 <b>ادعُ أصدقاءك واحصل على 200 نقطة!</b>\n\nرابطك:\n{link}", parse_mode='HTML')

    elif text == '💼 المحفظة':
        await update.message.reply_text("🔗 أرسل عنوان <b>TRC20</b> الخاص بك الآن:", parse_mode='HTML')
        context.user_data['waiting_for_wallet'] = True

    elif text == '🏧 سحب الأرباح':
        if user[2] < 10000:
            await update.message.reply_text(f"🚧 عذراً، تحتاج 10,000 نقطة للسحب.\nرصيدك: {user[2]:,}", parse_mode='HTML')
        elif user[3] == "غير محدد":
            await update.message.reply_text("⚠️ يرجى ضبط المحفظة أولاً.", parse_mode='HTML')
        else:
            await update.message.reply_text(f"✅ رصيدك {user[2]:,}\nأرسل الكمية المراد سحبها:", parse_mode='HTML')
            context.user_data['waiting_for_withdraw_amount'] = True

    elif context.user_data.get('waiting_for_wallet'):
        save_user(user_id, user[1], user[2], text)
        context.user_data['waiting_for_wallet'] = False
        await update.message.reply_text("✅ تم الحفظ!", parse_mode='HTML')

    elif context.user_data.get('waiting_for_withdraw_amount'):
        try:
            amt = int(text)
            if amt >= 10000 and amt <= user[2]:
                update_balance(user_id, -amt)
                await update.message.reply_text(f"🎊 تم استلام طلب سحب {amt:,} نقطة!")
                await context.bot.send_message(ADMIN_ID, f"🔔 طلب سحب:\nID: {user[0]}\nالكمية: {amt}\nالمحفظة: {user[3]}")
                context.user_data['waiting_for_withdraw_amount'] = False
        except: await update.message.reply_text("⚠️ أدخل رقماً صحيحاً.")

async def bet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("bet_"):
        symbol = query.data.split("_")[1]
        price = get_crypto_price(symbol)
        if not price: return
        context.user_data.update({'coin': symbol, 'price': price})
        keyboard = [[InlineKeyboardButton("📈 UP", callback_data="dir_up"), InlineKeyboardButton("📉 DOWN", callback_data="dir_down")]]
        await query.edit_message_text(f"🪙 <b>سوق {symbol}</b>\nالسعر: <code>${price:.4f}</code>\nتوقع الاتجاه:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    elif query.data.startswith("dir_"):
        direction = query.data.split("_")[1]
        await query.edit_message_text(f"⚡️ <b>تم فتح الصفقة!</b>\nانتظر 30 ثانية...", parse_mode='HTML')
        asyncio.create_task(process_bet(context, query.from_user.id, context.user_data['coin'], context.user_data['price'], direction))

if __name__ == '__main__':
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(bet_callback))
    app.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")
