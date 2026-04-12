import os

os.environ["BOT_TOKEN"] = "8554736433:AAFz8wxgr0W0sH_qlCJtmeZXb7C0xNfKMRk"
os.environ["ADMIN_ID"] = "916940521"
os.environ["CARD_NUMBER"] = "9860 0803 8838 5637"
os.environ["CARD_HOLDER"] = "Jamshidbek Tojimatov"
os.environ["SUPPORT_USERNAME"] = "@jamshiidbek"


import os
import asyncio
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Update
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)

# =========================
# ENVIRONMENT VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi")

if not RENDER_EXTERNAL_URL:
    raise ValueError("RENDER_EXTERNAL_URL topilmadi")

# Render domain oxirida / bo'lsa olib tashlaymiz
BASE_URL = RENDER_EXTERNAL_URL.rstrip("/")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"

# Render port
PORT = int(os.getenv("PORT", 10000))

# =========================
# BOT / DISPATCHER
# =========================
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# =========================
# KEYBOARD
# =========================
main_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Stars", callback_data="stars")],
        [InlineKeyboardButton(text="👑 Premium", callback_data="premium")]
    ]
)

# =========================
# HANDLERS
# =========================
@dp.message(CommandStart())
async def start_handler(message: Message):
    text = (
        f"Salom, {message.from_user.first_name}!\n\n"
        "Bot webhook orqali ishlayapti ✅\n"
        "Quyidagi bo‘limlardan birini tanlang:"
    )
    await message.answer(text, reply_markup=main_kb)


@dp.callback_query(F.data == "stars")
async def stars_handler(callback: CallbackQuery):
    await callback.message.answer(
        "⭐ Stars bo‘limi tanlandi.\n\n"
        "Bu yerga keyin stars menyularingni qo‘shamiz."
    )
    await callback.answer()


@dp.callback_query(F.data == "premium")
async def premium_handler(callback: CallbackQuery):
    await callback.message.answer(
        "👑 Premium bo‘limi tanlandi.\n\n"
        "Bu yerga keyin premium tariflaringni qo‘shamiz."
    )
    await callback.answer()


# =========================
# STARTUP / SHUTDOWN
# =========================
async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook o'rnatildi: {WEBHOOK_URL}")


async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    await bot.session.close()
    logging.info("Webhook o'chirildi")


async def healthcheck(request: web.Request):
    return web.Response(text="Bot is running")


def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()

    app.router.add_get("/", healthcheck)
    app.router.add_get("/health", healthcheck)

    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()

import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from dotenv import load_dotenv


# =========================
# ENV
# =========================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CARD_NUMBER = os.getenv("CARD_NUMBER", "KARTA_KIRITILMAGAN")
CARD_HOLDER = os.getenv("CARD_HOLDER", "KARTA_EGASI")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@jamshiidek")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi. .env faylga yozing.")

if ADMIN_ID == 0:
    raise ValueError("ADMIN_ID topilmadi. .env faylga yozing.")


# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)

# =========================
# BOT / DP
# =========================
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())


# =========================
# DATABASE
# =========================
conn = sqlite3.connect("shop.db")
cursor = conn.cursor()


def init_db():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            full_name TEXT,
            username TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            customer_name TEXT,
            product_type TEXT,
            product_name TEXT,
            recipient_username TEXT,
            receipt_text TEXT,
            receipt_file_id TEXT,
            receipt_file_type TEXT,
            status TEXT,
            created_at TEXT,
            confirmed_at TEXT,
            delivered_at TEXT
        )
    """)
    conn.commit()
    ensure_columns()


def ensure_columns():
    cursor.execute("PRAGMA table_info(orders)")
    columns = [row[1] for row in cursor.fetchall()]

    if "receipt_file_id" not in columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN receipt_file_id TEXT")
    if "receipt_file_type" not in columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN receipt_file_type TEXT")

    conn.commit()


init_db()


# =========================
# FSM
# =========================
class OrderState(StatesGroup):
    entering_recipient = State()
    entering_receipt = State()


# =========================
# KEYBOARDS
# =========================
def start_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⭐ Premium"), KeyboardButton(text="🎁 Gift")],
            [KeyboardButton(text="✨ Stars"), KeyboardButton(text="📦 Buyurtmalarim")],
            [KeyboardButton(text="📜 Qoidalar"), KeyboardButton(text="🆘 Yordam")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Kerakli bo‘limni tanlang..."
    )


def main_menu_inline():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Premium", callback_data="menu_premium")],
            [InlineKeyboardButton(text="🎁 Gift", callback_data="menu_gift")],
            [InlineKeyboardButton(text="✨ Stars", callback_data="menu_stars")],
            [InlineKeyboardButton(text="📦 Buyurtmalarim", callback_data="my_orders")],
            [InlineKeyboardButton(text="📜 Qoidalar", callback_data="rules")],
            [InlineKeyboardButton(text="🆘 Yordam", callback_data="help")],
        ]
    )

def premium_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1️⃣ Akkountga kirmasdan", callback_data="premium_no_login")],
            [InlineKeyboardButton(text="2️⃣ Akkountga kirib", callback_data="premium_with_login")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_main")],
        ]
    )

def premium_no_login_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 3 oy — 175 000 so‘m", callback_data="buy_premium_3m_no_login")],
            [InlineKeyboardButton(text="👑 6 oy — 220 000 so‘m", callback_data="buy_premium_6m_no_login")],
            [InlineKeyboardButton(text="🏆 12 oy — 375 000 so‘m", callback_data="buy_premium_12m_no_login")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu_premium")],
        ]
    )


def premium_with_login_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔐 1 oy — 45 000 so‘m", callback_data="buy_premium_1m_login")],
            [InlineKeyboardButton(text="🔐 12 oy — 280 000 so‘m", callback_data="buy_premium_12m_login")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu_premium")],
        ]
    )

def stars_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ 50 Stars — 12 000 so‘m", callback_data="buy_stars_50")],
            [InlineKeyboardButton(text="⭐ 75 Stars — 16 000 so‘m", callback_data="buy_stars_75")],
            [InlineKeyboardButton(text="⭐ 100 Stars — 23 000 so‘m", callback_data="buy_stars_100")],
            [InlineKeyboardButton(text="⭐ 150 Stars — 34 000 so‘m", callback_data="buy_stars_150")],
            [InlineKeyboardButton(text="⭐ 250 Stars — 55 000 so‘m", callback_data="buy_stars_250")],
            [InlineKeyboardButton(text="⭐ 500 Stars — 105 000 so‘m", callback_data="buy_stars_500")],
            [InlineKeyboardButton(text="⭐ 1000 Stars — 205 000 so‘m", callback_data="buy_stars_1000")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_main")],
        ]
    )

def gift_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Gift Basic", callback_data="gift_basic_menu")],
            [InlineKeyboardButton(text="💎 Gift Premium", callback_data="buy_gift_premium")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_main")],
        ]
    )

def gift_basic_stars_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ 15 Stars — 3 500 so‘m", callback_data="buy_stars_15")],
            [InlineKeyboardButton(text="⭐ 25 Stars — 6 000 so‘m", callback_data="buy_stars_25")],
            [InlineKeyboardButton(text="⭐ 50 Stars — 12 000 so‘m", callback_data="buy_stars_50")],
            [InlineKeyboardButton(text="⭐ 100 Stars — 23 000 so‘m", callback_data="buy_stars_100")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu_gift")],
        ]
    )



def admin_order_buttons(order_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin_confirm_{order_id}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"admin_reject_{order_id}")
            ],
            [
                InlineKeyboardButton(text="🎁 Yetkazildi", callback_data=f"admin_delivered_{order_id}")
            ]
        ]
    )


def back_to_main_button():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="back_main")]
        ]
    )


# =========================
# HELPERS
# =========================
PRODUCTS = {
    "buy_premium_3m_no_login": ("Premium", "Premium 3 oy (Akkountga kirmasdan) — 175 000 so‘m"),
    "buy_premium_6m_no_login": ("Premium", "Premium 6 oy (Akkountga kirmasdan) — 220 000 so‘m"),
    "buy_premium_12m_no_login": ("Premium", "Premium 12 oy (Akkountga kirmasdan) — 375 000 so‘m"),

    "buy_premium_1m_login": ("Premium", "Premium 1 oy (Akkountga kirib) — 45 000 so‘m"),
    "buy_premium_12m_login": ("Premium", "Premium 12 oy (Akkountga kirib) — 280 000 so‘m"),

    "buy_stars_50": ("Stars", "50 Stars — 12 000 so‘m"),
    "buy_stars_75": ("Stars", "75 Stars — 16 000 so‘m"),
    "buy_stars_100": ("Stars", "100 Stars — 23 000 so‘m"),
    "buy_stars_150": ("Stars", "150 Stars — 34 000 so‘m"),
    "buy_stars_250": ("Stars", "250 Stars — 55 000 so‘m"),
    "buy_stars_500": ("Stars", "500 Stars — 105 000 so‘m"),
    "buy_stars_1000": ("Stars", "1000 Stars — 205 000 so‘m"),

    "buy_gift_premium": ("Gift", "Gift Premium"),
    
    "buy_stars_15": ("Stars", "15 Stars — 3 500 so‘m"),
    "buy_stars_25": ("Stars", "25 Stars — 6 000 so‘m"),
    "buy_stars_50": ("Stars", "50 Stars — 12 000 so‘m"),
    "buy_stars_100": ("Stars", "100 Stars — 23 000 so‘m"),

   
}


def save_user(telegram_id: int, full_name: str, username: str | None):
    cursor.execute("""
        INSERT OR REPLACE INTO users (telegram_id, full_name, username, created_at)
        VALUES (?, ?, ?, COALESCE((SELECT created_at FROM users WHERE telegram_id=?), ?))
    """, (
        telegram_id,
        full_name,
        username or "",
        telegram_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()


def create_order(
    user_id: int,
    customer_name: str,
    product_type: str,
    product_name: str,
    recipient_username: str,
    receipt_text: str = "",
    receipt_file_id: str = "",
    receipt_file_type: str = ""
) -> int:
    cursor.execute("""
        INSERT INTO orders (
            user_id, customer_name, product_type, product_name,
            recipient_username, receipt_text, receipt_file_id, receipt_file_type,
            status, created_at, confirmed_at, delivered_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        customer_name,
        product_type,
        product_name,
        recipient_username,
        receipt_text,
        receipt_file_id,
        receipt_file_type,
        "pending",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "",
        ""
    ))
    conn.commit()
    return cursor.lastrowid


def get_user_orders(user_id: int):
    cursor.execute("""
        SELECT id, product_name, recipient_username, status, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 10
    """, (user_id,))
    return cursor.fetchall()


def get_order(order_id: int):
    cursor.execute("""
        SELECT id, user_id, customer_name, product_type, product_name,
               recipient_username, receipt_text, receipt_file_id, receipt_file_type,
               status, created_at, confirmed_at, delivered_at
        FROM orders
        WHERE id = ?
    """, (order_id,))
    return cursor.fetchone()


def update_order_status(order_id: int, status: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if status == "confirmed":
        cursor.execute("""
            UPDATE orders SET status = ?, confirmed_at = ? WHERE id = ?
        """, (status, now, order_id))
    elif status == "delivered":
        cursor.execute("""
            UPDATE orders SET status = ?, delivered_at = ? WHERE id = ?
        """, (status, now, order_id))
    else:
        cursor.execute("""
            UPDATE orders SET status = ? WHERE id = ?
        """, (status, order_id))

    conn.commit()


def format_status(status: str) -> str:
    mapping = {
        "pending": "⏳ Kutilmoqda",
        "confirmed": "✅ Tasdiqlandi",
        "rejected": "❌ Bekor qilindi",
        "delivered": "🎁 Yetkazildi",
    }
    return mapping.get(status, status)


def get_welcome_text(full_name: str) -> str:
    return (
        f"╔════════════════════╗\n"
        f"   <b>🌟 PREMIUM SHOP BOT 🌟</b>\n"
        f"╚════════════════════╝\n\n"
        f"👋 <b>Xush kelibsiz, {full_name}</b>\n\n"
        f"Bu bot orqali siz:\n"
        f"• ⭐ Premium xarid qilasiz\n"
        f"• 🎁 Gift yuborasiz\n"
        f"• 📦 Buyurtmalarni kuzatasiz\n"
        f"• 🆘 Yordam olasiz\n\n"
        f"Pastdagi menyudan kerakli bo‘limni tanlang."
    )


# =========================
# START
# =========================
@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()

    save_user(
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username
    )

    await message.answer(
        get_welcome_text(message.from_user.full_name),
        reply_markup=start_menu_keyboard()
    )

    await message.answer(
        "✨ <b>Interaktiv menyu</b>\nKerakli bo‘limni tanlang:",
        reply_markup=main_menu_inline()
    )


# =========================
# REPLY KEYBOARD HANDLERS
# =========================
@dp.message(F.text == "⭐ Premium")
async def reply_premium_handler(message: Message):
    await message.answer(
        "⭐ <b>Premium bo‘limi</b>\n\nPaketni tanlang:",
        reply_markup=premium_menu()
    )


@dp.message(F.text == "🎁 Gift")
async def reply_gift_handler(message: Message):
    await message.answer(
        "🎁 <b>Gift bo‘limi</b>\n\nVariantni tanlang:",
        reply_markup=gift_menu()
    )

@dp.callback_query(F.data == "gift_basic_menu")
async def gift_basic_menu_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "⭐ <b>Gift Basic Stars</b>\n\nKerakli stars paketini tanlang:",
        reply_markup=gift_basic_stars_menu()
    )
    await callback.answer()

@dp.message(F.text == "📦 Buyurtmalarim")
async def reply_my_orders_handler(message: Message):
    orders = get_user_orders(message.from_user.id)

    if not orders:
        await message.answer("📦 Sizda hali buyurtmalar yo‘q.")
        return

    lines = ["📦 <b>So‘nggi buyurtmalaringiz:</b>\n"]
    for order_id, product_name, recipient_username, status, created_at in orders:
        lines.append(
            f"🆔 <b>#{order_id}</b>\n"
            f"📦 Mahsulot: {product_name}\n"
            f"🎯 Qabul qiluvchi: {recipient_username}\n"
            f"📌 Status: {format_status(status)}\n"
            f"🕒 Sana: {created_at}\n"
        )

    await message.answer("\n".join(lines))


@dp.message(F.text == "📜 Qoidalar")
async def reply_rules_handler(message: Message):
    text = (
        "📜 <b>Qoidalar</b>\n\n"
        "1. To‘lov tasdiqlanmaguncha buyurtma bajarilmaydi.\n"
        "2. Username noto‘g‘ri kiritilsa, javobgarlik foydalanuvchida bo‘ladi.\n"
        "3. Soxta chek yuborish taqiqlanadi.\n"
        "4. Yetkazib berish admin tomonidan amalga oshiriladi.\n"
        "5. Chek rasm yoki matn ko‘rinishida yuborilishi mumkin."
    )
    await message.answer(text)


@dp.message(F.text == "🆘 Yordam")
async def reply_help_handler(message: Message):
    await message.answer(
        f"🆘 <b>Yordam</b>\n\nAdmin: {SUPPORT_USERNAME}\nMuammo bo‘lsa yozing."
    )


# =========================
# INLINE MENU
# =========================
@dp.callback_query(F.data == "back_main")
async def back_main_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🏠 <b>Bosh menyu</b>\n\nKerakli bo‘limni tanlang:",
        reply_markup=main_menu_inline()
    )
    await callback.answer()
@dp.callback_query(F.data == "menu_premium")
async def premium_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "⭐ <b>Premium bo‘limi</b>\n\nVariantni tanlang:",
        reply_markup=premium_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "premium_no_login")
async def premium_no_login_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "1️⃣ <b>Akkountga kirmasdan premium</b>\n\nPaketni tanlang:",
        reply_markup=premium_no_login_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "premium_with_login")
async def premium_with_login_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "2️⃣ <b>Akkountga kirib premium</b>\n\nPaketni tanlang:",
        reply_markup=premium_with_login_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "menu_stars")
async def stars_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "✨ <b>Stars bo‘limi</b>\n\nKerakli stars paketini tanlang:",
        reply_markup=stars_menu()
    )
    await callback.answer()

@dp.message(F.text == "✨ Stars")
async def reply_stars_handler(message: Message):
    await message.answer(
        "✨ <b>Stars bo‘limi</b>\n\nKerakli stars paketini tanlang:",
        reply_markup=stars_menu()
    )

@dp.message(OrderState.entering_recipient)
async def recipient_handler(message: Message, state: FSMContext):
    recipient = (message.text or "").strip()

    if not recipient.startswith("@") or len(recipient) < 5:
        await message.answer("❌ Username noto‘g‘ri. Masalan: <code>@username</code>")
        return

    await state.update_data(recipient_username=recipient)
    await state.set_state(OrderState.entering_receipt)

    text = (
        "💳 <b>To‘lov ma’lumotlari</b>\n\n"
        f"💳 Karta: <code>{CARD_NUMBER}</code>\n"
        f"👤 Karta egasi: <b>{CARD_HOLDER}</b>\n\n"
        "⚠️ <b>Eslatma:</b>\n"
        "Faqat o‘zingiz tanlagan buyurtmangizga to‘g‘ri keladigan to‘lov summasini yozing va to‘lov qiling!\n\n"
        "To‘lov qilgach, quyidagilardan birini yuboring:\n"
        "• chek rasmi\n"
        "• screenshot\n"
        "• PDF / fayl\n"
        "• yoki matnli izoh\n\n"
        "Masalan:\n"
        "<code>Payme orqali to‘lov qildim. Chek ilova qilindi.</code>"
    )
    await message.answer(text)
@dp.message(F.text == "⭐ Premium")
async def reply_premium_handler(message: Message):
    await message.answer(
        "⭐ <b>Premium bo‘limi</b>\n\nVariantni tanlang:",
        reply_markup=premium_menu()
    )
@dp.callback_query(F.data == "menu_premium")
async def premium_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "⭐ <b>Premium bo‘limi</b>\n\nPaketni tanlang:",
        reply_markup=premium_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "menu_gift")
async def gift_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎁 <b>Gift bo‘limi</b>\n\nVariantni tanlang:",
        reply_markup=gift_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "rules")
async def rules_handler(callback: CallbackQuery):
    text = (
        "📜 <b>Qoidalar</b>\n\n"
        "1. To‘lov tasdiqlanmaguncha buyurtma bajarilmaydi.\n"
        "2. Username noto‘g‘ri kiritilsa, javobgarlik foydalanuvchida bo‘ladi.\n"
        "3. Soxta chek yuborish taqiqlanadi.\n"
        "4. Yetkazib berish admin tomonidan qo‘lda amalga oshiriladi.\n"
        "5. Chek rasm, screenshot yoki matn bo‘lishi mumkin."
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_button())
    await callback.answer()


@dp.callback_query(F.data == "help")
async def help_handler(callback: CallbackQuery):
    text = (
        "🆘 <b>Yordam</b>\n\n"
        f"Support: {SUPPORT_USERNAME}\n\n"
        "Muammo bo‘lsa, admin bilan bog‘laning."
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_button())
    await callback.answer()


@dp.callback_query(F.data == "my_orders")
async def my_orders_handler(callback: CallbackQuery):
    orders = get_user_orders(callback.from_user.id)

    if not orders:
        await callback.message.edit_text(
            "📦 Sizda hali buyurtmalar yo‘q.",
            reply_markup=back_to_main_button()
        )
        await callback.answer()
        return

    lines = ["📦 <b>So‘nggi buyurtmalaringiz:</b>\n"]
    for order_id, product_name, recipient_username, status, created_at in orders:
        lines.append(
            f"🆔 <b>#{order_id}</b>\n"
            f"📦 Mahsulot: {product_name}\n"
            f"🎯 Qabul qiluvchi: {recipient_username}\n"
            f"📌 Status: {format_status(status)}\n"
            f"🕒 Sana: {created_at}\n"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=back_to_main_button()
    )
    await callback.answer()


# =========================
# ORDER FLOW
# =========================
@dp.callback_query(F.data.in_(PRODUCTS.keys()))
async def choose_product_handler(callback: CallbackQuery, state: FSMContext):
    product_type, product_name = PRODUCTS[callback.data]

    await state.update_data(product_type=product_type, product_name=product_name)
    await state.set_state(OrderState.entering_recipient)

    await callback.message.edit_text(
        f"✅ Siz tanladingiz: <b>{product_name}</b>\n\n"
        "Endi qabul qiluvchining Telegram username sini yuboring.\n"
        "Masalan: <code>@username</code>"
    )
    await callback.answer()


@dp.message(OrderState.entering_recipient)
async def recipient_handler(message: Message, state: FSMContext):
    recipient = (message.text or "").strip()

    if not recipient.startswith("@") or len(recipient) < 5:
        await message.answer("❌ Username noto‘g‘ri. Masalan: <code>@username</code>")
        return

    await state.update_data(recipient_username=recipient)
    await state.set_state(OrderState.entering_receipt)

    text = (
        "💳 <b>To‘lov ma’lumotlari</b>\n\n"
        f"💳 Karta: <code>{CARD_NUMBER}</code>\n"
        f"👤 Karta egasi: <b>{CARD_HOLDER}</b>\n\n"
        "To‘lov qilgach, quyidagilardan birini yuboring:\n"
        "• chek rasmi\n"
        "• screenshot\n"
        "• PDF / fayl\n"
        "• yoki matnli izoh\n\n"
        "Masalan:\n"
        "<code>Payme orqali 50 000 so‘m to‘ladim. Chek raqami: 12345</code>"
    )
    await message.answer(text)


@dp.message(OrderState.entering_receipt, F.photo)
async def receipt_photo_handler(message: Message, state: FSMContext):
    data = await state.get_data()

    caption_text = message.caption.strip() if message.caption else ""
    photo = message.photo[-1]
    file_id = photo.file_id

    order_id = create_order(
        user_id=message.from_user.id,
        customer_name=message.from_user.full_name,
        product_type=data["product_type"],
        product_name=data["product_name"],
        recipient_username=data["recipient_username"],
        receipt_text=caption_text,
        receipt_file_id=file_id,
        receipt_file_type="photo"
    )

    user_text = (
        f"✅ <b>Buyurtmangiz qabul qilindi</b>\n\n"
        f"🆔 Buyurtma ID: <code>#{order_id}</code>\n"
        f"📦 Mahsulot: <b>{data['product_name']}</b>\n"
        f"🎯 Qabul qiluvchi: {data['recipient_username']}\n"
        f"📌 Status: ⏳ Kutilmoqda\n\n"
        "Admin chekni tekshiradi."
    )
    await message.answer(user_text, reply_markup=main_menu_inline())

    admin_caption = (
        "📥 <b>Yangi buyurtma (chek rasmi)</b>\n\n"
        f"🆔 Buyurtma: <code>#{order_id}</code>\n"
        f"👤 Mijoz: {message.from_user.full_name}\n"
        f"🪪 User ID: <code>{message.from_user.id}</code>\n"
        f"📦 Mahsulot: <b>{data['product_name']}</b>\n"
        f"🎯 Qabul qiluvchi: {data['recipient_username']}\n"
        f"📝 Izoh: {caption_text if caption_text else 'Yo‘q'}\n"
        f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=file_id,
        caption=admin_caption,
        reply_markup=admin_order_buttons(order_id)
    )

    await state.clear()


@dp.message(OrderState.entering_receipt, F.document)
async def receipt_document_handler(message: Message, state: FSMContext):
    data = await state.get_data()

    caption_text = message.caption.strip() if message.caption else ""
    file_id = message.document.file_id

    order_id = create_order(
        user_id=message.from_user.id,
        customer_name=message.from_user.full_name,
        product_type=data["product_type"],
        product_name=data["product_name"],
        recipient_username=data["recipient_username"],
        receipt_text=caption_text,
        receipt_file_id=file_id,
        receipt_file_type="document"
    )

    user_text = (
        f"✅ <b>Buyurtmangiz qabul qilindi</b>\n\n"
        f"🆔 Buyurtma ID: <code>#{order_id}</code>\n"
        f"📦 Mahsulot: <b>{data['product_name']}</b>\n"
        f"🎯 Qabul qiluvchi: {data['recipient_username']}\n"
        f"📌 Status: ⏳ Kutilmoqda\n\n"
        "Admin chekni tekshiradi."
    )
    await message.answer(user_text, reply_markup=main_menu_inline())

    admin_caption = (
        "📥 <b>Yangi buyurtma (fayl/PDF)</b>\n\n"
        f"🆔 Buyurtma: <code>#{order_id}</code>\n"
        f"👤 Mijoz: {message.from_user.full_name}\n"
        f"🪪 User ID: <code>{message.from_user.id}</code>\n"
        f"📦 Mahsulot: <b>{data['product_name']}</b>\n"
        f"🎯 Qabul qiluvchi: {data['recipient_username']}\n"
        f"📝 Izoh: {caption_text if caption_text else 'Yo‘q'}\n"
        f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    await bot.send_document(
        chat_id=ADMIN_ID,
        document=file_id,
        caption=admin_caption,
        reply_markup=admin_order_buttons(order_id)
    )

    await state.clear()


@dp.message(OrderState.entering_receipt, F.text)
async def receipt_text_handler(message: Message, state: FSMContext):
    data = await state.get_data()

    receipt_text = message.text.strip()
    order_id = create_order(
        user_id=message.from_user.id,
        customer_name=message.from_user.full_name,
        product_type=data["product_type"],
        product_name=data["product_name"],
        recipient_username=data["recipient_username"],
        receipt_text=receipt_text,
        receipt_file_id="",
        receipt_file_type="text"
    )

    user_text = (
        f"✅ <b>Buyurtmangiz qabul qilindi</b>\n\n"
        f"🆔 Buyurtma ID: <code>#{order_id}</code>\n"
        f"📦 Mahsulot: <b>{data['product_name']}</b>\n"
        f"🎯 Qabul qiluvchi: {data['recipient_username']}\n"
        f"📌 Status: ⏳ Kutilmoqda\n\n"
        "Admin to‘lovni tekshiradi."
    )
    await message.answer(user_text, reply_markup=main_menu_inline())

    admin_text = (
        "📥 <b>Yangi buyurtma</b>\n\n"
        f"🆔 Buyurtma: <code>#{order_id}</code>\n"
        f"👤 Mijoz: {message.from_user.full_name}\n"
        f"🪪 User ID: <code>{message.from_user.id}</code>\n"
        f"📦 Mahsulot: <b>{data['product_name']}</b>\n"
        f"🎯 Qabul qiluvchi: {data['recipient_username']}\n"
        f"🧾 Chek: {receipt_text}\n"
        f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    await bot.send_message(
        ADMIN_ID,
        admin_text,
        reply_markup=admin_order_buttons(order_id)
    )

    await state.clear()


# =========================
# ADMIN ACTIONS
# =========================
@dp.callback_query(F.data.startswith("admin_"))
async def admin_actions(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Siz admin emassiz.", show_alert=True)
        return

    parts = callback.data.split("_")
    action = parts[1]
    order_id = int(parts[2])

    order = get_order(order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi.", show_alert=True)
        return

    (
        _id, user_id, customer_name, product_type, product_name,
        recipient_username, receipt_text, receipt_file_id, receipt_file_type,
        status, created_at, confirmed_at, delivered_at
    ) = order

    if action == "confirm":
        update_order_status(order_id, "confirmed")
        await bot.send_message(
            user_id,
            f"✅ <b>Buyurtmangiz tasdiqlandi</b>\n\n"
            f"🆔 Buyurtma ID: <code>#{order_id}</code>\n"
            f"📦 Mahsulot: <b>{product_name}</b>"
        )

    elif action == "reject":
        update_order_status(order_id, "rejected")
        await bot.send_message(
            user_id,
            f"❌ <b>Buyurtmangiz bekor qilindi</b>\n\n"
            f"🆔 Buyurtma ID: <code>#{order_id}</code>\n"
            f"Savol bo‘lsa admin bilan bog‘laning."
        )

    elif action == "delivered":
        update_order_status(order_id, "delivered")
        await bot.send_message(
            user_id,
            f"🎁 <b>Buyurtmangiz yetkazildi</b>\n\n"
            f"🆔 Buyurtma ID: <code>#{order_id}</code>\n"
            f"📦 Mahsulot: <b>{product_name}</b>\n"
            f"🎯 Qabul qiluvchi: {recipient_username}"
        )

    await callback.answer("Bajarildi")


# =========================
# ADMIN COMMAND
# =========================
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Siz admin emassiz.")
        return

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")
    pending = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='confirmed'")
    confirmed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders WHERE status='delivered'")
    delivered = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    text = (
        "👑 <b>ADMIN PANEL</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{total_users}</b>\n"
        f"⏳ Kutilayotgan buyurtmalar: <b>{pending}</b>\n"
        f"✅ Tasdiqlanganlar: <b>{confirmed}</b>\n"
        f"🎁 Yetkazilganlar: <b>{delivered}</b>"
    )
    await message.answer(text)


# =========================
# FALLBACK
# =========================
@dp.message()
async def fallback_handler(message: Message):
    await message.answer(
        "Kerakli bo‘limni menyudan tanlang yoki /start bosing.",
        reply_markup=start_menu_keyboard()
    )


# =========================
# MAIN
# =========================
async def main():
    print("Bot ishga tushdi 🚀")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
