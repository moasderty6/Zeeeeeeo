import asyncio
import os
import asyncpg
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, Update

# =============================
# ENV VARIABLES
# =============================
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", 8080))
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# =============================
# DATABASE INIT
# =============================
async def init_db(app):
    app["db_pool"] = await asyncpg.create_pool(DATABASE_URL)
    async with app["db_pool"].acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    print("✅ Database ready")

# =============================
# HANDLERS (الأوامر)
# =============================

@dp.message(F.command("start"))
async def start_handler(message: Message, db_pool: asyncpg.Pool):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username)
            VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING
        """, message.from_user.id, message.from_user.username)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 قناة زينو", url="https://t.me/zainaldinmaham1")],
        [InlineKeyboardButton(text="📬 للتواصل", url="https://t.me/Sasam132")]
    ])
    await message.answer(f"أهلاً بك {message.from_user.first_name} 👋\nتم تسجيلك بنجاح!", reply_markup=keyboard)

@dp.message(F.command("stats"))
async def stats_handler(message: Message, db_pool: asyncpg.Pool):
    async with db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
    await message.answer(f"📊 عدد المستخدمين المسجلين: {count}")

# أمر الإذاعة (للمدير فقط - استبدل 123456 بـ ID حسابك)
@dp.message(F.command("broadcast"))
async def broadcast(message: Message, db_pool: asyncpg.Pool):
    # ADMIN_ID = 12345678  # فك التعليق وضع رقمك هنا للحماية
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        return await message.answer("أرسل النص بعد الأمر، مثال: /broadcast مرحبا")

    async with db_pool.acquire() as conn:
        users = await conn.fetch("SELECT user_id FROM users")
    
    count = 0
    for user in users:
        try:
            await bot.send_message(user['user_id'], text)
            count += 1
            await asyncio.sleep(0.05) # حماية من السبام
        except: continue
    await message.answer(f"✅ تم الإرسال إلى {count} مستخدم.")

# =============================
# WEB INTERFACE
# =============================

async def homepage(request): # الدالة التي كانت تسبب الخطأ
    return web.Response(text="Zino Bot Status: Online ✅")

async def handle_webhook(request):
    try:
        data = await request.json()
        update = Update(**data)
        await dp.feed_update(bot, update, db_pool=request.app["db_pool"])
        return web.Response(text="OK")
    except Exception as e:
        print(f"Webhook Error: {e}")
        return web.Response(status=500)

async def on_startup(app):
    await init_db(app)
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print(f"🚀 Webhook set to: {WEBHOOK_URL}/webhook")

async def on_shutdown(app):
    await app["db_pool"].close()
    await bot.session.close()

# =============================
# MAIN RUNNER
# =============================
async def main():
    app = web.Application()
    app.router.add_get("/", homepage) # الآن homepage معرفة مسبقاً
    app.router.add_post("/webhook", handle_webhook)
    
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
