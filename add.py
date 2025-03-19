import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database import Database

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
GROUP_ID = int(os.getenv("GROUP_ID"))

# Инициализация бота
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
db = Database()

# Главное меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="🛒 Корзина")],
        [KeyboardButton(text="📦 Мои заказы"), KeyboardButton(text="📞 Контакты")]
    ],
    resize_keyboard=True
)

# Команда /start
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer("👋 Добро пожаловать в магазин!", reply_markup=main_menu)

# Обработчик кнопки "🛍 Каталог"
@dp.message(lambda message: message.text == "🛍 Каталог")
async def show_catalog(message: types.Message):
    products = db.get_products()
    if not products:
        await message.answer("❌ Товары пока не добавлены.")
        return
    
    for product in products:
        buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Купить", callback_data=f"buy_{product[0]}")],
            [InlineKeyboardButton(text="ℹ️ Подробнее", callback_data=f"details_{product[0]}")]
        ])
        await message.answer(f"{product[1]}\n💰 Цена: {product[2]}₽", reply_markup=buttons)

# Обработчик кнопки "ℹ️ Подробнее"
@dp.callback_query(lambda c: c.data.startswith("details_"))
async def product_details(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    product = db.get_product_details(product_id)
    if not product:
        await callback.answer("❌ Товар не найден.", show_alert=True)
        return
    
    name, description, price, image = product
    text = f"📌 <b>{name}</b>\n\n📄 {description}\n💰 Цена: {price}₽"
    if image and image.startswith("http"):
        await bot.send_photo(callback.message.chat.id, photo=image, caption=text, parse_mode="HTML")
    else:
        await bot.send_message(callback.message.chat.id, text, parse_mode="HTML")
    await callback.answer()

# Добавление товара в корзину
@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def add_to_cart(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    db.add_to_cart(user_id, product_id)
    await callback.answer("✅ Товар добавлен в корзину!")


@dp.message(lambda message: message.text == "🛒 Корзина")
async def show_cart2(message: types.Message, update=False):
    user_id = message.from_user.id
    cart_items = db.show_cart(user_id)
    
    if not cart_items:
        await message.answer("🛒 Ваша корзина пуста.")
        return
    
    text = "🛍 *Ваша корзина:*\n\n"
    total_price = 0
    inline_kb = []
    
    for item in cart_items:
        product_id, name, price, quantity = item
        total_price += price * quantity
        text += f"{name} - {price}₽ (x{quantity})\n"
        inline_kb.append([
            InlineKeyboardButton(text="➖", callback_data=f"decrease_{product_id}"),
            InlineKeyboardButton(text=f"{quantity}", callback_data="ignore"),
            InlineKeyboardButton(text="➕", callback_data=f"increase_{product_id}"),
            InlineKeyboardButton(text="❌ Удалить", callback_data=f"remove_{product_id}")
        ])
    
    text += f"\n💰 *Итого:* {total_price}₽"
    inline_kb.append([InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")])
    
    markup = InlineKeyboardMarkup(inline_keyboard=inline_kb)
    if update:
        await message.edit_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await message.answer(text, parse_mode="Markdown", reply_markup=markup)
# 🔹 Увеличение количества товара в корзине
@dp.callback_query(lambda c: c.data.startswith("increase_"))
async def increase_quantity(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    product_id = int(callback.data.split("_")[1])
    db.increase_cart_item(user_id, product_id)
    await callback.answer("➕ Количество товара увеличено!")
    await db.show_cart(callback.message)

# 🔹 Уменьшение количества товара в корзине
@dp.callback_query(lambda c: c.data.startswith("decrease_"))
async def decrease_quantity(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    product_id = int(callback.data.split("_")[1])
    db.decrease_cart_item(user_id, product_id)
    await callback.answer("➖ Количество товара уменьшено!")
    await db.show_cart(callback.message)

# 🔹 Удаление товара из корзины
@dp.callback_query(lambda c: c.data.startswith("remove_"))
async def remove_item(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    product_id = int(callback.data.split("_")[1])
    db.remove_from_cart(user_id, product_id)
    await callback.answer("❌ Товар удален из корзины!")
    await db.show_cart(callback.message)

# 🔹 Оформление заказа
class OrderState(StatesGroup):
    waiting_for_phone = State()

# Создание клавиатуры для запроса номера телефона
phone_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📲 Отправить номер", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)

# 🔹 Запрос номера телефона перед оформлением заказа
@dp.callback_query(lambda c: c.data.startswith("checkout"))
async def request_phone(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📞 Пожалуйста, отправьте ваш номер телефона, нажав на кнопку ниже:", reply_markup=phone_keyboard)
    await state.set_state(OrderState.waiting_for_phone)

# 🔹 Обработка номера телефона и завершение оформления заказа
@dp.message(lambda message: message.contact)
async def checkout(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    phone_number = message.contact.phone_number  # Получаем номер телефона пользователя
    cart_items = db.show_cart(user_id)  # Получаем корзину пользователя
    
    if not cart_items:
        await message.answer("❌ Ваша корзина пуста.", reply_markup=main_menu)
        return

    total_price = sum(item[2] * item[3] for item in cart_items)
    
    # Уменьшаем количество товаров на складе
    for item in cart_items:
        db.update_stock(item[0], item[3])  # item[0] — product_id, item[3] — количество
    
    # Очищаем корзину пользователя
    db.clear_cart(user_id)

    # Отправляем сообщение в группу с заказом и номером телефона
    order_text = f"🆕 Новый заказ от {message.from_user.full_name} (ID: {user_id})\n"
    order_text += f"📞 Номер телефона: {phone_number}\n"
    order_text += "\n".join([f"{item[1]} - {item[3]} шт." for item in cart_items])
    order_text += f"\n💰 Общая сумма: {total_price}₽"
    
    await bot.send_message(GROUP_ID, order_text)
    await message.answer("✅ Ваш заказ оформлен! Мы свяжемся с вами для уточнения деталей.", reply_markup=main_menu)

    # Сброс состояния
    await state.clear()

# 🔹 Мои заказы
@dp.message(lambda message: message.text == "📦 Мои заказы")
async def my_orders(message: types.Message):
    user_id = message.from_user.id
    orders = db.get_orders_by_user(user_id)
    if not orders:
        await message.answer("🛒 У вас пока нет заказов.")
        return
    
    text = "📦 *Ваши заказы:*\n\n"
    for order in orders:
        text += f"🆔 Заказ #{order[0]}\n📅 Дата: {order[1]}\n💰 Сумма: {order[2]}₽\n📦 Статус: {order[3]}\n\n"
    await message.answer(text, parse_mode="Markdown")

# 🔹 Контакты
@dp.message(lambda message: message.text == "📞 Контакты")
async def contacts(message: types.Message):
    await message.answer("📞 +7 977 412 60 27\n📧 Email: example@mail.com")

# 🔹 Запуск бота
async def main():
    logging.basicConfig(level=logging.INFO)
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())