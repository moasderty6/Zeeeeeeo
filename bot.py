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

# قاموس لتخزين الأسعار اللحظية
LIVE_PRICES = {}
COINS_LIST = ['btc', 'eth', 'bnb', 'sol', 'ton', 'xrp', 'dot', 'doge', 'avax', 'ada']

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- إدارة قاعدة البيانات ---
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id BIGINT PRIMARY KEY, username TEXT, balance INTEGER DEFAULT 1000, wallet TEXT DEFAULT 'غير محدد')''')
    conn.commit()
    c.close(); conn.close()

def get_user(user_id):
    try:
        conn = get_db_connection(); c = conn.cursor()
        c.execute("SELECT id, username, balance, wallet FROM users WHERE id=%s", (user_id,))
        user = c.fetchone()
        c.close(); conn.close()
        return user
    except: return None

def update_balance(user_id, amount):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))
    conn.commit(); c.close(); conn.close()

def save_user(user_id, username, balance, wallet):
    conn = get_db_connection(); c = conn.cursor()
    c.execute("INSERT INTO users (id, username, balance, wallet) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET username=%s, wallet=%s", 
              (user_id, username, balance, wallet, username, wallet))
    conn.commit(); c.close(); conn.close()

# --- محرك الأسعار المزدوج (WebSocket + API Backup) ---
async def binance_ws_engine():
    streams = "/".join([f"{coin}usdt@ticker" for coin in COINS_LIST])
    url = f"wss://stream.binance.com:9443/ws/{streams}"
    while True:
        try:
            async with websockets.connect(url) as ws:
                logging.info("WebSocket Connected ✅")
                while True:
                    data = json.loads(await ws.recv())
                    if 's' in data:
                        symbol = data['s'].replace('USDT', '').upper()
                        LIVE_PRICES[symbol] = float(data['c'])
        except Exception as e:
            logging.error(f"WS Error: {e}")
            await asyncio.sleep(5)

def get_crypto_price(symbol):
    sym = symbol.strip().upper()
    # 1. جرب الـ WebSocket أولاً (الأسرع)
    price = LIVE_PRICES.get(sym)
    if price: return price
    
    # 2. إذا كان الـ WS معلقاً، اجلب فوراً من الـ API (الاحتياطي)
    try:
        url = f"https://api1.binance.com/api/v3/ticker/price?symbol={sym}USDT"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            price = float(res.json()['price'])
            LIVE_PRICES[sym] = price # حدث القاموس للاستخدام القادم
            return price
    except: pass
    return None

# --- معالجة الرهان ---
async def process_bet(context, user_id, symbol, entry_price, direction):
    await asyncio.sleep(30)
    exit_price = get_crypto_price(symbol)
    if exit_price:
        if exit_price == entry_price:
            status = "🟡 تعادل! السعر لم يتغير"
            msg_res = "رصيدك لم يتأثر. 🤝"
        else:
            win = (direction == "up" and exit_price > entry_price) or (direction == "down" and exit_price < entry_price)
            amount = 200 if win else -200 
            update_balance(user_id, amount)
            status = "🟢 ربح! +200 نقطة" if win else "🔴 خسارة! -200 نقطة"
            msg_res = "تمت معالجة الصفقة."
        
        msg = (f"🏆 <b>نتيجة {symbol}</b>\n━━━━━━━━━━━━━━\n📉 دخول: <code>${entry_price:.6f}</code>\n📈 خروج: <code>${exit_price:.6f}</code>\n━━━━━━━━━━━━━━\n<b>{status}</b>\n{msg_res}")
        await context.bot.send_message(user_id, msg, parse_mode='HTML')
    else:
        await context.bot.send_message(user_id, "⚠️ فشل تحديث السعر، تم حفظ نقاطك.")

# --- الأوامر والرسائل ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not get_user(user_id): save_user(user_id, update.effective_user.username, 1000, "غير محدد")
    keyboard = [['🎮 ابدأ التداول'], ['💼 المحفظة', '👤 الحساب'], ['🏧 سحب الأرباح', '📢 ربح نقاط']]
    await update.message.reply_text("👋 مرحباً بك في بوت التداول اللحظي!", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text; user_id = update.effective_user.id; user = get_user(user_id)
    if not user: return
    
    if text == '🎮 ابدأ التداول':
        if user[2] < 200: await update.message.reply_text("❌ رصيدك ضعيف."); return
        keyboard = [[InlineKeyboardButton(f"🪙 {c.upper()}", callback_data=f"bet_{c.upper()}")] for c in COINS_LIST]
        await update.message.reply_text("✨ اختر العملة:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif text == '👤 الحساب':
        await update.message.reply_text(f"👤 <b>@{user[1]}</b>\n💰 الرصيد: {user[2]:,}\n🏦 المحفظة: {user[3]}", parse_mode='HTML')

    elif text == '💼 المحفظة':
        await update.message.reply_text("أرسل عنوان TRC20:"); context.user_data['wait_w'] = True

    elif context.user_data.get('wait_w'):
        save_user(user_id, user[1], user[2], text); context.user_data['wait_w'] = False
        await update.message.reply_text("✅ تم الربط.")

async def bet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if query.data.startswith("bet_"):
        symbol = query.data.split("_")[1]
        price = get_crypto_price(symbol)
        if not price: await query.edit_message_text("❌ السوق مغلق حالياً."); return
        context.user_data.update({'c': symbol, 'p': price})
        keyboard = [[InlineKeyboardButton("📈 صعود", callback_data="dir_up"), InlineKeyboardButton("📉 هبوط", callback_data="dir_down")]]
        await query.edit_message_text(f"🪙 <b>{symbol}</b>\nالسعر: <code>${price:.6f}</code>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    elif query.data.startswith("dir_"):
        direction = query.data.split("_")[1]
        await query.edit_message_text("🚀 تم تنفيذ الطلب... ⏳")
        asyncio.create_task(process_bet(context, query.from_user.id, context.user_data['c'], context.user_data['p'], direction))

# --- التشغيل الرئيسي (معدل لـ Render) ---
if __name__ == '__main__':
    init_db()
    application = Application.builder().token(TOKEN).build()
    
    # ربط الـ WebSocket بالـ Loop الخاص بالبوت
    asyncio.get_event_loop().create_task(binance_ws_engine())
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(bet_callback))
    
    application.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")
