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

if not TOKEN or not WEBHOOK_URL or not DATABASE_URL:
    print("❌ خطأ: تأكد من ضبط متغيرات البيئة (TOKEN, WEBHOOK_URL, DATABASE_URL)")
    exit(1)

# =============================
# BOT INIT
# =============================
bot = Bot(token=TOKEN)
dp = Dispatcher()

# =============================
# HANDLERS
# =============================

@dp.message(F.command("start"))
async def start_handler(message: Message, db_pool: asyncpg.Pool): # استلام الـ pool مباشرة
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
        """, message.from_user.id, message.from_user.username)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 قناة زينو ياسر محاميد الرسمية", url="https://t.me/zainaldinmaham1")],
        [InlineKeyboardButton(text="🗣 منتدى شبكة زينو الإخبارية", url="https://t.me/zedan432")],
        [InlineKeyboardButton(text="📬 للتواصل مع زينو", url="https://t.me/Sasam132")]
    ])

    await message.answer(
        f"أهلاً بك {message.from_user.first_name} 👋\nتم تسجيلك بنجاح ✅",
        reply_markup=keyboard
    )

@dp.message(F.command("stats"))
async def stats_handler(message: Message, db_pool: asyncpg.Pool):
    async with db_pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
    await message.answer(f"📊 عدد المستخدمين: {count}")

# =============================
# WEBHOOK & SERVER
# =============================

async def handle_webhook(request):
    try:
        data = await request.json()
        update = Update(**data)
        # تمرير الـ pool مع التحديث
        await dp.feed_update(bot, update, db_pool=request.app["db_pool"])
        return web.Response(text="OK")
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        return web.Response(status=500)

async def on_startup(app):
    # إنشاء اتصال قاعدة البيانات
    app["db_pool"] = await asyncpg.create_pool(DATABASE_URL)
    
    # إنشاء الجدول
    async with app["db_pool"].acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    # ضبط الويب هوك وتنظيف الرسائل القديمة
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print("🚀 Bot is Live and Webhook is set!")

async def on_shutdown(app):
    await bot.delete_webhook()
    await app["db_pool"].close()
    await bot.session.close()

async def main():
    app = web.Application()

    # جعل البوت يستقبل التحديثات على / وعلى /webhook لضمان عدم حدوث 404
    app.router.add_get("/", homepage)
    app.router.add_post("/webhook", handle_webhook)
    app.router.add_post("/", handle_webhook) # إضافة هذا السطر كاحتياط

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render يفضل أحياناً استخدام PORT المعرف في النظام مباشرة
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    print(f"🌍 Server started on port {PORT}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
