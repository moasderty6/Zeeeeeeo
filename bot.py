import os
import requests
import logging
import psycopg2 
import asyncio
import json
import websockets
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
WEBHOOK_URL = "https://zeeeeeeo.onrender.com" 
PORT = int(os.environ.get('PORT', 5000))
ADMIN_ID = 6172153716 
DATABASE_URL = "postgresql://neondb_owner:npg_yPL6dYWRZQ4o@ep-little-firefly-aifch2tu-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"

# قاموس لتخزين الأسعار اللحظية من الـ WebSocket
LIVE_PRICES = {}
COINS_LIST = ['btc', 'eth', 'bnb', 'sol', 'ton', 'xrp', 'dot', 'doge', 'avax', 'ada']

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

# --- محرك Binance WebSocket لجلب الأسعار بالملي ثانية ---
async def binance_ws_engine():
    """فتح اتصال دائم مع بايننس لتحديث الأسعار لحظياً"""
    # بناء رابط الـ stream لجميع العملات المختارة
    streams = "/".join([f"{coin}usdt@ticker" for coin in COINS_LIST])
    url = f"wss://stream.binance.com:9443/ws/{streams}"
    
    while True:
        try:
            async with websockets.connect(url) as ws:
                logging.info("Binance WebSocket Connected ✅")
                while True:
                    data = json.loads(await ws.recv())
                    symbol = data['s'].replace('USDT', '').upper()
                    price = float(data['c'])
                    LIVE_PRICES[symbol] = price
        except Exception as e:
            logging.error(f"WebSocket Error: {e}, Reconnecting in 5s...")
            await asyncio.sleep(5)

# --- دالة جلب السعر من الذاكرة اللحظية ---
def get_crypto_price(symbol):
    sym = symbol.strip().upper()
    # جلب السعر من القاموس الذي يحدثه الـ WebSocket
    return LIVE_PRICES.get(sym)

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
        await context.bot.send_message(user_id, "⚠️ عذراً، حدث خطأ في تحديث الأسعار اللحظية.")

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
                    await context.bot.send_message(ref_id, "🚀 <b>صديق جديد انضم!</b> حصلت على 200 نقطة.", parse_mode='HTML')
            except: pass
        save_user(user_id, username, 1000, "غير محدد")

    keyboard = [['🎮 ابدأ التداول'], ['💼 المحفظة', '👤 الحساب'], ['🏧 سحب الأرباح', '📢 ربح نقاط']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"👋 <b>أهلاً بك في بوت زينو محاميد!</b>\n\nتوقع حركة العملات لحظياً واجمع الأرباح! 💹",
        reply_markup=reply_markup, parse_mode='HTML'
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID: return 
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(balance) FROM users")
    stats = c.fetchone()
    c.close()
    conn.close()
    
    msg = (f"📊 <b>إحصائيات الإدارة</b>\n━━━━━━━━━━━━━━\n👥 المستخدمين: {stats[0]}\n💰 النقاط: {stats[1]:,}")
    await update.message.reply_text(msg, parse_mode='HTML')

async def clear_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    conn = get_db_connection(); c = conn.cursor(); c.execute("DELETE FROM users"); conn.commit(); c.close(); conn.close()
    await update.message.reply_text("✅ تم مسح جميع البيانات.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user: return

    if text == '👤 الحساب':
        msg = (f"🚀 <b>@{user[1]}</b>\n━━━━━━━━━━━━━━\n💰 <b>الرصيد:</b> {user[2]:,} نقطة\n🏦 <b>المحفظة:</b> <code>{user[3]}</code>")
        await update.message.reply_text(msg, parse_mode='HTML')

    elif text == '🎮 ابدأ التداول':
        if user[2] < 200:
            await update.message.reply_text("❌ رصيدك غير كافٍ (تحتاج 200 نقطة).")
            return
        keyboard = [[InlineKeyboardButton(f"🪙 {c.upper()}", callback_data=f"bet_{c.upper()}")] for c in COINS_LIST]
        await update.message.reply_text("✨ <b>اختر العملة للتحليل:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif text == '💼 المحفظة':
        await update.message.reply_text("🔗 أرسل عنوان <b>TRC20</b> الخاص بك:")
        context.user_data['waiting_for_wallet'] = True

    elif text == '🏧 سحب الأرباح':
        if user[2] < 10000:
            await update.message.reply_text(f"🚧 الحد الأدنى 10,000 نقطة. لديك: {user[2]:,}")
        elif user[3] == "غير محدد":
            await update.message.reply_text("❌ اضبط المحفظة أولاً.")
        else:
            await update.message.reply_text("أدخل الكمية التي تريد سحبها:")
            context.user_data['waiting_for_withdraw_amount'] = True

    elif text == '📢 ربح نقاط':
        bot_info = await context.bot.get_me()
        await update.message.reply_text(f"🤝 شارك رابطك واربح 200 نقطة:\nhttps://t.me/{bot_info.username}?start={user_id}")

    elif context.user_data.get('waiting_for_wallet'):
        save_user(user_id, user[1], user[2], text)
        context.user_data['waiting_for_wallet'] = False
        await update.message.reply_text("✅ تم حفظ المحفظة.")

    elif context.user_data.get('waiting_for_withdraw_amount'):
        try:
            amount = int(text)
            if amount >= 10000 and amount <= user[2]:
                update_balance(user_id, -amount)
                await update.message.reply_text(f"🎊 تم طلب سحب {amount:,} نقطة.")
                await context.bot.send_message(ADMIN_ID, f"🔔 طلب سحب من @{user[1]}\nالكمية: {amount}\nالمحفظة: {user[3]}")
            else: await update.message.reply_text("❌ كمية غير صالحة.")
        except: await update.message.reply_text("❌ أدخل أرقاماً فقط.")
        context.user_data['waiting_for_withdraw_amount'] = False

async def bet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user = get_user(user_id)
    await query.answer()
    
    if query.data.startswith("bet_"):
        symbol = query.data.split("_")[1]
        price = get_crypto_price(symbol)
        if not price:
            await query.edit_message_text("⚠️ انتظر ثوانٍ لتجهيز بيانات السوق اللحظية...")
            return
        context.user_data.update({'coin': symbol, 'price': price})
        keyboard = [[InlineKeyboardButton("📈 صعود", callback_data="dir_up"), InlineKeyboardButton("📉 هبوط", callback_data="dir_down")]]
        await query.edit_message_text(f"🪙 <b>سوق {symbol}</b>\nالسعر: <code>${price:.4f}</code>\nتوقع الحركة خلال 30 ثانية:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    elif query.data.startswith("dir_"):
        direction = "up" if query.data.split("_")[1] == "up" else "down"
        await query.edit_message_text(f"🚀 تم الدخول.. انتظر النتيجة ⏳", parse_mode='HTML')
        asyncio.create_task(process_bet(context, user_id, context.user_data['coin'], context.user_data['price'], direction))

if __name__ == '__main__':
    init_db()
    application = Application.builder().token(TOKEN).build()
    
    # تشغيل الـ WebSocket في الخلفية كـ Task
    loop = asyncio.get_event_loop()
    loop.create_task(binance_ws_engine())
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CommandHandler("clear_all", clear_all_users))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(bet_callback))
    
    application.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")
