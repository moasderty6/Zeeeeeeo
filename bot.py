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
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))

DATABASE_URL = os.getenv("DATABASE_URL")

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN is not set")

if not WEBHOOK_URL:
    raise ValueError("❌ WEBHOOK_URL is not set")

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL is not set")

WEBHOOK_URL = WEBHOOK_URL.rstrip("/")

# =============================
# BOT INIT
# =============================

bot = Bot(token=TOKEN)
dp = Dispatcher()


# =============================
# DATABASE
# =============================

async def init_db(app):
    app["db"] = await asyncpg.create_pool(DATABASE_URL)

    async with app["db"].acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    print("✅ Database ready")


# =============================
# HANDLERS
# =============================

@dp.message(F.command("start"))
async def start_handler(message: Message):
    async with message.bot.get("db").acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
        """, message.from_user.id, message.from_user.username)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 قناة زينو ياسر محاميد الرسمية", url="https://t.me/Tgstarssavebot")],
        [InlineKeyboardButton(text="🗣 منتدى شبكة زينو الإخبارية", url="https://t.me/Tgstarssavebot")],
        [InlineKeyboardButton(text="📬 للتواصل مع زينو", url="https://t.me/Tgstarssavebot")]
    ])

    await message.answer(
        f"أهلاً بك {message.from_user.first_name} 👋\nتم تسجيلك بنجاح ✅",
        reply_markup=keyboard
    )


@dp.message(F.command("stats"))
async def stats_handler(message: Message):
    async with message.bot.get("db").acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM users")

    await message.answer(f"📊 عدد المستخدمين: {count}")


# =============================
# WEBHOOK
# =============================

async def handle_webhook(request):
    try:
        data = await request.json()
        update = Update(**data)
        await dp.feed_update(bot, update)
        return web.Response(text="OK")
    except Exception as e:
        print("❌ Webhook Error:", e)
        return web.Response(status=500)


async def homepage(request):
    return web.Response(text="Bot is running ✅")


async def on_startup(app):
    await init_db(app)
    await bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    print("🚀 Webhook set:", f"{WEBHOOK_URL}/webhook")


async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()
    await app["db"].close()
    print("🛑 Bot stopped")


# =============================
# MAIN
# =============================

async def main():
    app = web.Application()

    app.router.add_get("/", homepage)
    app.router.add_post("/webhook", handle_webhook)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    print(f"🌍 Server started on port {PORT}")

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
