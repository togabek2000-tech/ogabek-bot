"""
OG'ABEK_UC - ПОЛНОЦЕННЫЙ TELEGRAM БОТ ДЛЯ ПРОДАЖИ PUBG MOBILE UC
Все паки, все способы оплаты (СБП, Карты, Click, Uzum, Crypto),
проверка PUBG ID, приём чеков и админ-панель.

Техподдержка: @dasturchi_HTML_CSS
"""

import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

# ==================== НАСТРОЙКИ МАГАЗИНА ====================
BOT_TOKEN = "ВСТАВЬТЕ_СЮДА_ВАШ_ТОКЕН_ОТ_BOTFATHER"
ADMIN_ID = 51885488519  # Ваш Telegram ID (из личного кабинета BOT-T)
SUPPORT_CONTACT = "@dasturchi_HTML_CSS"

# Реквизиты для оплаты:
CARD_SBP_INFO = "Номер СБП / Карты РФ: +7 (999) 000-00-00 (Т-Банк / Сбер)"
CLICK_UZUM_INFO = "Click / Uzum (Узбекистан): 8600 0000 0000 0000 (Получатель: Og'abek)"
CRYPTO_WALLET_INFO = "USDT (TRC20): TYourTrc20AddressHere...\nTON: EQYourTonWalletAddressHere..."

# ==================== КАТАЛОГ ПАКОВ UC ====================
# Цены дешевле secreti4 на 4-10 рублей
CATALOG = {
    "uc_60": {"name": "60 UC", "uc": 60, "rub": 85, "uzs": 11900},
    "uc_120": {"name": "120 UC", "uc": 120, "rub": 172, "uzs": 24100},
    "uc_180": {"name": "180 UC", "uc": 180, "rub": 258, "uzs": 36100},
    "uc_325": {"name": "325 UC (300+25)", "uc": 325, "rub": 442, "uzs": 61900},
    "uc_385": {"name": "385 UC (360+25)", "uc": 385, "rub": 527, "uzs": 73800},
    "uc_660": {"name": "660 UC (Royale Pass)", "uc": 660, "rub": 871, "uzs": 121900},
    "uc_720": {"name": "720 UC", "uc": 720, "rub": 956, "uzs": 133800},
    "uc_985": {"name": "985 UC", "uc": 985, "rub": 1310, "uzs": 183400},
    "uc_1320": {"name": "1320 UC", "uc": 1320, "rub": 1739, "uzs": 243500},
    "uc_1800": {"name": "1800 UC", "uc": 1800, "rub": 2189, "uzs": 306500},
    "uc_2125": {"name": "2125 UC", "uc": 2125, "rub": 2625, "uzs": 367500},
    "uc_3850": {"name": "3850 UC", "uc": 3850, "rub": 4339, "uzs": 607500},
    "uc_5650": {"name": "5650 UC", "uc": 5650, "rub": 6530, "uzs": 914200},
    "uc_8100": {"name": "8100 UC", "uc": 8100, "rub": 8689, "uzs": 1216500},
    "uc_16200": {"name": "16200 UC", "uc": 16200, "rub": 17289, "uzs": 2420000},
    "uc_32400": {"name": "32400 UC", "uc": 32400, "rub": 34489, "uzs": 4825000},
}

# ==================== БАЗА ДАННЫХ SQLITE ====================
def init_db():
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            pack_key TEXT,
            pack_name TEXT,
            player_id TEXT,
            amount_rub INTEGER,
            amount_uzs INTEGER,
            pay_method TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ==================== FSM СОСТОЯНИЯ ====================
class OrderState(StatesGroup):
    entering_pubg_id = State()
    choosing_method = State()
    waiting_receipt = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

# ==================== КЛАВИАТУРЫ ====================
def get_main_menu():
    kb = [
        [KeyboardButton(text="💎 Купить UC"), KeyboardButton(text="📊 Прайс-лист")],
        [KeyboardButton(text="🆔 Как узнать Player ID"), KeyboardButton(text="🆘 Техподдержка")],
        [KeyboardButton(text="📦 Мои заказы")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_catalog_kb():
    buttons = []
    for key, item in CATALOG.items():
        text = f"{item['name']} — {item['rub']} ₽ / {item['uzs']:,} UZS".replace(",", " ")
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"buy_{key}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_pay_methods_kb():
    buttons = [
        [InlineKeyboardButton(text="🇷🇺 СБП / Карты РФ (МИР, Сбер, Т-Банк)", callback_data="method_sbp")],
        [InlineKeyboardButton(text="🇺🇿 Click / Uzum Bank / Payme", callback_data="method_uz")],
        [InlineKeyboardButton(text="🪙 Криптовалюта (USDT / TON / CryptoBot)", callback_data="method_crypto")],
        [InlineKeyboardButton(text="❌ Отменить заказ", callback_data="cancel_order")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ==================== ОБРАБОТЧИКИ ====================
@dp.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer(
        f"👋 **Добро пожаловать в магазин Og'abek_UC!**\n\n"
        f"⚡ Здесь вы можете купить PUBG Mobile UC мгновенно по Player ID.\n"
        f"🔥 Цены на 4–10 ₽ ниже рынка (дешевле secreti4)!\n"
        f"💳 Оплата: **СБП, Карты РФ, Click, Uzum и Крипта**.\n\n"
        f"🆘 Менеджер техподдержки: {SUPPORT_CONTACT}",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

@dp.message(F.text == "📊 Прайс-лист")
async def show_price(msg: Message):
    text = "📋 **Каталог цен Og'abek_UC:**\n━━━━━━━━━━━━━━━━━━\n"
    for _, item in CATALOG.items():
        text += f"• **{item['name']}** — {item['rub']} ₽ ({item['uzs']:,} UZS)\n".replace(",", " ")
    text += f"━━━━━━━━━━━━━━━━━━\n⚡ Доставка за 1-5 минут.\n🆘 Поддержка: {SUPPORT_CONTACT}"
    await msg.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🆔 Как узнать Player ID")
async def show_id_guide(msg: Message):
    await msg.answer(
        "📌 **Как найти свой PUBG Player ID:**\n\n"
        "1. Зайдите в игру PUBG Mobile.\n"
        "2. В левом верхнем углу нажмите на аватар своего профиля.\n"
        "3. Под вашим ником будет числовой код из 8-11 цифр (например, `5182947261`).\n"
        "4. Нажмите иконку копирования рядом с ним и вставьте сюда при заказе.",
        parse_mode="Markdown"
    )

@dp.message(F.text == "🆘 Техподдержка")
async def show_support(msg: Message):
    await msg.answer(
        f"👨‍💻 **Служба технической поддержки Og'abek_UC:**\n\n"
        f"По всем вопросам начисления, проверки ID и сотрудничества:\n"
        f"👉 **{SUPPORT_CONTACT}** (Отвечаем 24/7)",
        parse_mode="Markdown"
    )

@dp.message(F.text == "📦 Мои заказы")
async def my_orders(msg: Message):
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("SELECT id, pack_name, player_id, amount_rub, status FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 5", (msg.from_user.id,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        await msg.answer("У вас пока нет заказов.")
        return

    text = "📦 **Ваши последние заказы:**\n\n"
    for r in rows:
        status_ico = "🟡 В обработке" if r[4] == "pending" else "🟢 Выполнен"
        text += f"• Заказ #{r[0]}: **{r[1]}** (ID: `{r[2]}`) — {r[3]} ₽ [{status_ico}]\n"
    await msg.answer(text, parse_mode="Markdown")

@dp.message(F.text == "💎 Купить UC")
async def buy_uc(msg: Message):
    await msg.answer("🔥 **Выберите нужный номинал UC:**", reply_markup=get_catalog_kb())

@dp.callback_query(F.data.startswith("buy_"))
async def pack_selected(call: CallbackQuery, state: FSMContext):
    pack_key = call.data.replace("buy_", "")
    pack = CATALOG.get(pack_key)
    if not pack:
        await call.answer("Товар не найден", show_alert=True)
        return

    await state.update_data(pack_key=pack_key, pack=pack)
    await call.message.edit_text(
        f"💎 Вы выбрали: **{pack['name']}**\n"
        f"💰 К оплате: **{pack['rub']} ₽** (или {pack['uzs']:,} UZS)\n\n"
        f"✍️ **Введите ваш числовой PUBG Player ID** (например, `5182947261`):".replace(",", " "),
        parse_mode="Markdown"
    )
    await state.set_state(OrderState.entering_pubg_id)
    await call.answer()

@dp.message(OrderState.entering_pubg_id)
async def process_pubg_id(msg: Message, state: FSMContext):
    player_id = msg.text.strip()
    if not player_id.isdigit() or len(player_id) < 7 or len(player_id) > 15:
        await msg.answer("❌ **Неверный формат ID!**\nВведите только цифры (от 7 до 12 цифр без пробелов и букв):")
        return

    await state.update_data(player_id=player_id)
    data = await state.get_data()
    pack = data["pack"]

    await msg.answer(
        f"📋 **ПОДТВЕРЖДЕНИЕ ЗАКАЗА:**\n━━━━━━━━━━━━━━━━━━\n"
        f"📦 Пакет: **{pack['name']}**\n"
        f"🎮 PUBG Player ID: `{player_id}`\n"
        f"💰 Стоимость: **{pack['rub']} ₽** ({pack['uzs']:,} UZS)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Выберите удобный способ оплаты:".replace(",", " "),
        reply_markup=get_pay_methods_kb(),
        parse_mode="Markdown"
    )
    await state.set_state(OrderState.choosing_method)

@dp.callback_query(OrderState.choosing_method, F.data == "cancel_order")
async def cancel_order(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Заказ отменен. Вы можете начать заново в главном меню.")
    await call.answer()

@dp.callback_query(OrderState.choosing_method, F.data.startswith("method_"))
async def process_payment_method(call: CallbackQuery, state: FSMContext):
    method = call.data
    data = await state.get_data()
    pack = data["pack"]
    player_id = data["player_id"]
    user = call.from_user

    # Сохраняем заказ в базу данных
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (user_id, username, pack_key, pack_name, player_id, amount_rub, amount_uzs, pay_method) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user.id, user.username or "none", data["pack_key"], pack["name"], player_id, pack["rub"], pack["uzs"], method)
    )
    order_id = cur.lastrowid
    conn.commit()
    conn.close()

    await state.update_data(order_id=order_id, pay_method=method)

    if method == "method_sbp":
        text = (
            f"💳 **Оплата через СБП / Карту РФ** (Заказ #{order_id})\n\n"
            f"💰 Сумма к переводу: **{pack['rub']} ₽**\n\n"
            f"Реквизиты:\n`{CARD_SBP_INFO}`\n\n"
            f"⚠️ **ИНСТРУКЦИЯ:**\n"
            f"1. Переведите точную сумму **{pack['rub']} ₽**.\n"
            f"2. Сделайте скриншот чека об успешном переводе.\n"
            f"3. **Отправьте скриншот чека сюда сообщением** в ответ этому боту!"
        )
    elif method == "method_uz":
        text = (
            f"🇺🇿 **Оплата через Click / Uzum / Payme** (Заказ #{order_id})\n\n"
            f"💰 Сумма к переводу: **{pack['uzs']:,} UZS**\n\n"
            f"Реквизиты:\n`{CLICK_UZUM_INFO}`\n\n"
            f"⚠️ **ИНСТРУКЦИЯ:**\n"
            f"1. Откройте Click или Uzum и переведите **{pack['uzs']:,} UZS**.\n"
            f"2. Сделайте скриншот квитанции.\n"
            f"3. **Отправьте скриншот чека прямо сюда в чат**!".replace(",", " ")
        )
    else:
        text = (
            f"🪙 **Оплата Криптовалютой** (Заказ #{order_id})\n\n"
            f"💰 Сумма: **{pack['rub']} ₽ в эквиваленте USDT / TON**\n\n"
            f"Кошельки:\n`{CRYPTO_WALLET_INFO}`\n\n"
            f"Отправьте скриншот транзакции или Hash в ответ на это сообщение!"
        )

    await call.message.edit_text(text, parse_mode="Markdown")
    await state.set_state(OrderState.waiting_receipt)
    await call.answer()

@dp.message(OrderState.waiting_receipt, F.photo)
async def process_receipt_photo(msg: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data["order_id"]
    pack = data["pack"]
    player_id = data["player_id"]
    user = msg.from_user

    # Уведомляем клиента
    await msg.answer(
        f"✅ **Чек по заказу #{order_id} принят!**\n\n"
        f"Администратор проверяет оплату. UC будут начислены на Player ID `{player_id}` в течение 1–10 минут.\n\n"
        f"При задержках пишите в поддержку: {SUPPORT_CONTACT}",
        parse_mode="Markdown"
    )

    # Клавиатура подтверждения для владельца (Админа)
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выдать UC (Подтвердить)", callback_data=f"adm_ok_{order_id}_{user.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm_no_{order_id}_{user.id}")
        ]
    ])

    admin_caption = (
        f"🚨 **НОВЫЙ ОПЛАЧЕННЫЙ ЗАКАЗ #{order_id}!**\n\n"
        f"👤 Покупатель: @{user.username or 'нет'} (ID: `{user.id}`)\n"
        f"📦 Товар: **{pack['name']}**\n"
        f"🎮 PUBG Player ID: `{player_id}`\n"
        f"💰 Сумма: **{pack['rub']} ₽** ({pack['uzs']} UZS)\n"
        f"💳 Способ: {data['pay_method']}\n\n"
        f"Пополните ID игрока на Midasbuy и нажмите кнопку ниже:"
    )

    # Пересылаем фото чека администратору
    photo_id = msg.photo[-1].file_id
    try:
        await bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=admin_caption, reply_markup=admin_kb, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Не удалось отправить заказ админу: {e}")

    await state.clear()

@dp.callback_query(F.data.startswith("adm_ok_"))
async def admin_approve(call: CallbackQuery):
    _, _, order_id, user_id = call.data.split("_")
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status='completed' WHERE id=?", (order_id,))
    conn.commit()
    conn.close()

    await call.message.edit_caption(caption=call.message.caption + "\n\n✅ **ВЫПОЛНЕНО (UC НАЧИСЛЕНЫ)**")
    try:
        await bot.send_message(
            int(user_id),
            f"🎉 **Заказ #{order_id} успешно выполнен!**\n\n"
            f"UC зачислены на ваш игровой аккаунт PUBG Mobile. Заходите в игру и проверяйте баланс!\n\n"
            f"Спасибо за покупку в Og'abek_UC! Ждем вас снова 🔥",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await call.answer("Заказ подтвержден!")

@dp.callback_query(F.data.startswith("adm_no_"))
async def admin_reject(call: CallbackQuery):
    _, _, order_id, user_id = call.data.split("_")
    conn = sqlite3.connect("shop.db")
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status='rejected' WHERE id=?", (order_id,))
    conn.commit()
    conn.close()

    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ **ОТКЛОНЕНО (Чек не найден или ошибка)**")
    try:
        await bot.send_message(
            int(user_id),
            f"⚠️ **Заказ #{order_id} отклонен.**\n\n"
            f"Оплата не поступила или чек не распознан. Пожалуйста, напишите в техподдержку: {SUPPORT_CONTACT}",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await call.answer("Заказ отклонен!")

async def main():
    print(">>> Бот Og'abek_UC успешно запущен и готов к продажам! <<<")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
