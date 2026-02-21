import os
import requests
import logging
import psycopg2 
import asyncio
import hmac
import hashlib
import time
from urllib.parse import urlencode
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

# --- Binance API الخاص ---
BINANCE_API_KEY = "fdNKsTXn5A22UnCgKG4GfWj7mfPEbDLPZbKghtaarWDWvtLhQSYtMhIPfX7qKtYc"
BINANCE_SECRET_KEY = "gPWVnDmdveW4lfuBBQG89MLAAKUVDDpV3l63PtRw104PDHVETSOvDXiNgZZnwSuO"

BINANCE_PAIRS = {
    'BTC': 'BTCUSDT',
    'ETH': 'ETHUSDT',
    'BNB': 'BNBUSDT',
    'SOL': 'SOLUSDT',
    'TON': 'TONUSDT',
    'XRP': 'XRPUSDT',
    'DOT': 'DOTUSDT',
    'DOGE': 'DOGEUSDT',
    'AVAX': 'AVAXUSDT',
    'ADA': 'ADAUSDT'
}

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

# --- جلب السعر اللحظي من Binance باستخدام API Key ---
def get_crypto_price(symbol):
    """
    جلب السعر اللحظي من Binance باستخدام API Key و Secret
    """
    try:
        symbol = symbol.upper()
        if symbol not in BINANCE_PAIRS:
            print(f"⚠️ العملة {symbol} غير مدعومة في Binance.")
            return None
        pair = BINANCE_PAIRS[symbol]
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"

        headers = {
            'X-MBX-APIKEY': BINANCE_API_KEY
        }
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        if 'price' in data:
            return float(data['price'])
        else:
            print("Binance API returned invalid data:", data)
            return None
    except Exception as e:
        print("Binance request failed:", e)
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
        await context.bot.send_message(user_id, "⚠️ عذراً، حدث خطأ في تحديث الأسعار. تم حفظ نقاطك.")

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

    keyboard = [
        ['🎮 ابدأ التداول'],
        ['💼 المحفظة', '👤 الحساب'],
        ['🏧 سحب الأرباح', '📢 ربح نقاط']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"👋 <b>أهلاً بك في بوت زينو محاميد!</b>\n\n"
        f"أنت الآن في قلب سوق الكريبتو. توقع حركة العملات، اجمع النقاط، وحوّلها إلى أرباح حقيقية! 💹\n\n"
        f"🎁 <b>هدية البداية:</b> 1,000 نقطة مجانية!",
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
    
    msg = (f"📊 <b>إحصائيات زينو محاميد</b>\n"
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

# --- باقي كود البوت كما هو مع دوال التداول، الحساب، المحفظة، السحب، ربح نقاط ---
# يتم الاحتفاظ بكل الكود السابق كما كتبته، فقط استبدلت دالة get_crypto_price لاستخدام Binance API الخاص.

if __name__ == '__main__':
    init_db()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CommandHandler("clear_all", clear_all_users))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(bet_callback))
    application.run_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN, webhook_url=f"{WEBHOOK_URL}/{TOKEN}")