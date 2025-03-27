import asyncio
import logging
import os
import pytz
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime
from aiogram.utils.markdown import hbold
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
router = Router()

# Класс состояний для удаления товара
class DeleteProductState(StatesGroup):
    waiting_product_choice = State()

# Класс состояний для запроса номера телефона
class OrderState(StatesGroup):
    waiting_for_phone = State()

# Класс состояний для добавления товара в каталог
class AddProduct(StatesGroup):
    name = State()
    description = State()
    price = State()
    discount_price = State()
    quantity = State()
    image = State()

# Главное меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="🛒 Корзина")],
        [KeyboardButton(text="👤 Личный кабинет"), KeyboardButton(text="📞 Контакты")],
        [KeyboardButton(text="🔥 Специальные предложения"), KeyboardButton(text="🚚 Информация о доставке")]
    ],
    resize_keyboard=True
)

# Клавиатура иформации о доставке
delivery_info_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚚 Информация о доставке")],
        [KeyboardButton(text="🔙 Назад")]
    ],
    resize_keyboard=True
)

# Клавиатура личного кабинета
personal_account_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Мои заказы")],
        [KeyboardButton(text="❤️ Мое избранное")],
        [KeyboardButton(text="🔙 Назад")]
    ],
    resize_keyboard=True
)


# Панель администратора для изменения статуса заказа
def admin_panel(order_id):
    """Создает клавиатуру для изменения статуса заказа"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 В обработке", callback_data=f"status_{order_id}_processing")],
        [InlineKeyboardButton(text="✅ Подтвержден", callback_data=f"status_{order_id}_confirmed")],
        [InlineKeyboardButton(text="🚚 В пути", callback_data=f"status_{order_id}_shipped")],
        [InlineKeyboardButton(text="🛑 Отменен", callback_data=f"status_{order_id}_canceled")],
        [InlineKeyboardButton(text="🎉 Завершен", callback_data=f"status_{order_id}_completed")]
    ])


# Клавиатура подтверждения оферты
offer_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Подтвердить заказ")],
        [KeyboardButton(text="❌ Отменить заказ")]
    ],
    resize_keyboard=True
)


# Клавиатура для отправки номера телефона
phone_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📲 Отправить номер", request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)


# Команда /start
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer_sticker(os.getenv('STICKER_ID'))
    await message.answer("👋 Добро пожаловать в магазин!", reply_markup=main_menu)


# Команда добавления товара (только для администратора)
@dp.message(Command("add_product"))
async def add_product(message: types.Message, state: FSMContext):
    if message.from_user.id != int(os.getenv("ADMIN_ID")):
        await message.answer("❌ У вас нет прав для добавления товаров.")
        return
    
    await message.answer("Введите название товара:")
    await state.set_state(AddProduct.name)

@dp.message(AddProduct.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите описание товара:")
    await state.set_state(AddProduct.description)

@dp.message(AddProduct.description)
async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Введите основную цену товара (в рублях):")
    await state.set_state(AddProduct.price)

@dp.message(AddProduct.price)
async def process_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        if price <= 0:
            raise ValueError
        await state.update_data(price=price)
        await message.answer("Введите скидочную цену товара (в рублях):")
        await state.set_state(AddProduct.discount_price)
    except ValueError:
        await message.answer("❌ Цена должна быть положительным числом. Попробуйте снова.")

@dp.message(AddProduct.discount_price)
async def process_discount_price(message: types.Message, state: FSMContext):
    try:
        discount_price = float(message.text)
        data = await state.get_data()
        price = data["price"]

        if discount_price >= price:
            await message.answer("❌ Скидочная цена должна быть меньше основной. Введите снова:")
            return

        await state.update_data(discount_price=discount_price)
        await message.answer("Введите количество товара на складе:")
        await state.set_state(AddProduct.quantity)
    except ValueError:
        await message.answer("❌ Скидочная цена должна быть числом. Попробуйте снова.")

@dp.message(AddProduct.quantity)
async def process_quantity(message: types.Message, state: FSMContext):
    try:
        quantity = int(message.text)
        if quantity < 1:
            raise ValueError
        await state.update_data(quantity=quantity)
        await message.answer("Введите ссылку на изображение товара (или отправьте 'без изображения'):")
        await state.set_state(AddProduct.image)
    except ValueError:
        await message.answer("❌ Количество должно быть целым положительным числом.")

@dp.message(AddProduct.image)
async def process_image(message: types.Message, state: FSMContext):
    image = message.text if message.text.lower() != 'без изображения' else None
    data = await state.get_data()

    db.add_product(
        name=data["name"],
        description=data["description"],
        price=data["price"],
        discount_price=data["discount_price"],
        quantity=data["quantity"],
        image=image
    )

    discount_percent = round((1 - data["discount_price"] / data["price"]) * 100, 2)
    
    await message.answer(
        f"✅ Товар '{data['name']}' успешно добавлен!\n"
        f"💰 Цена: {data['price']}₽\n"
        f"💸 Скидочная цена: {data['discount_price']}₽ (-{discount_percent}%)"
    )
    await state.clear()


# Команда для удаления товаров (доступно только админу)
@dp.message(Command("delete_product"))
async def delete_product(message: types.Message, admin_id=None):
    if admin_id is None and message.from_user.id != int(os.getenv("ADMIN_ID")):
        await message.answer("У вас нет прав для удаления товаров ❌")
        return

    products = db.get_product()
    
    if not products:
        await message.answer("📭 Каталог пуст, нечего удалять.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🗑 {name} - {price}₽", callback_data=f"delete_product_{product_id}")]
            for product_id, name, price, discount_price in products
        ]
    )


    await message.answer("Выберите товар для удаления:", reply_markup=keyboard)


# Обработчик удаления товара
@dp.callback_query(lambda c: c.data.startswith("delete_product_"))
async def process_delete_product(callback: types.CallbackQuery):
    admin_id = callback.from_user.id
    try:
        product_id = int(callback.data.split("_")[2])
    except ValueError:
        await callback.answer("⚠ Ошибка: некорректный идентификатор товара!", show_alert=True)
        return

    product = db.get_product_by_id(product_id)
    if not product:
        await callback.answer("❌ Товар не найден.", show_alert=True)
        return

    db.delete_product(product_id)
    await callback.answer(f"✅ Товар «{product[1]}» удален!", show_alert=True)
    await callback.message.delete()

    await delete_product(callback.message, admin_id=admin_id)


# Обработчик кнопки "🛍 Каталог"
@router.message(lambda message: message.text == "🛍 Каталог")
async def show_catalog(message: types.Message):
    products = db.get_product()

    if not products:
        await message.answer("❌ Товары пока не добавлены.")
        return

    for product in products:
        if len(product) == 4:  
            product_id, name, price, discount_price = product
        else:  
            product_id, name, price = product
            discount_price = price  

        if discount_price < price:
            discount_percent = round((1 - discount_price / price) * 100, 2)
            price_text = (
                f"🔥 <b>АКЦИЯ!</b> 🔥\n"
                f"🎯 Старая цена: <s>{price}₽</s>\n"
                f"💥 Новая цена: <b>{discount_price}₽</b>\n"
                f"🎉 Вы экономите <b>-{discount_percent}%</b>!"
            )
        else:
            price_text = f"💰 Цена: <b>{price}₽</b>"

        buttons = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🛒 Купить", callback_data=f"add_to_cart_{product_id}")],
                [InlineKeyboardButton(text="ℹ️ Подробнее", callback_data=f"details_{product_id}")],
                [InlineKeyboardButton(text="❤️ Добавить в избранное", callback_data=f"add_favorite_{product_id}")]
            ]
        )

        await message.answer(
            f"{hbold(name)}\n💰 Цена: {price_text}", 
            reply_markup=buttons, 
            parse_mode="HTML"
        )


# Обработчик кнопки "ℹ️ Подробнее"
@router.callback_query(lambda c: c.data.startswith("details_"))
async def product_details(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    product = db.get_product_details(product_id)
    
    if not product:
        await callback.answer("❌ Товар не найден.", show_alert=True)
        return
    
    # Обрабатываем случай, если image может отсутствовать
    if len(product) == 4:
        name, description, price, discount_price = product
        image = None
    else:
        name, description, price, discount_price, image = product

    # Проверяем, что discount_price является числом
    try:
        discount_price = float(discount_price)
    except ValueError:
        discount_price = None  # Если это не число, устанавливаем значение None

    # Преобразуем цену в float
    price = float(price)

    text = f"📌 {hbold(name)}\n\n📄 {description}\n\n"

    if discount_price is not None and discount_price < price:
        discount_percent = round((1 - discount_price / price) * 100, 2)
        text += f"🔥 <s>{price}₽</s> ➝ {discount_price}₽ (-{discount_percent}%)\n"
    else:
        text += f"💰 {price}₽\n"

    if image and image.startswith("http"):
        await callback.message.answer_photo(photo=image, caption=text, parse_mode="HTML")
    else:
        await callback.message.answer(text, parse_mode="HTML")

    await callback.answer()


# Доюавление товара в избранное
@router.callback_query(lambda c: c.data.startswith('add_favorite_'))
async def add_to_favorite_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    product_id = int(callback_query.data.split('_')[-1])
    
    db.add_to_favorites(user_id, product_id)

    await callback_query.answer("Товар добавлен в избранное! ❤️")


# Добавление товара в корзину
@dp.callback_query(lambda c: c.data.startswith("add_to_cart_"))
async def add_to_cart(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    product_id = int(callback.data.split("_")[3])
    quantity = 1  

    
    if db.add_to_cart(user_id, product_id, quantity):
        await callback.answer("✅ Товар добавлен в корзину!")
    else:
        await callback.answer("❌ Ошибка при добавлении товара в корзину.", show_alert=True)


# Показ корзины
@dp.message(lambda message: message.text == "🛒 Корзина")
async def show_cart(message: types.Message, update=False):
    user_id = message.from_user.id
    cart_items = db.show_cart(user_id)

    print(f"🛒 Корзина для пользователя {user_id}: {cart_items}") 

    if not cart_items:
        await message.answer("🛒 Ваша корзина пуста.")
        return
    
    text = "🛍 *Ваша корзина:*\n\n"
    total_price = 0
    inline_kb = []

    for item in cart_items:
        try:
            product_id, name, discount_price, quantity = item
        except ValueError as e:
            print(f"❌ Ошибка распаковки данных корзины: {e}, item = {item}")
            continue
        
        total_price += discount_price  * quantity
        text += f"{name} - {discount_price }₽ (x{quantity})\n"
        inline_kb.append([
            InlineKeyboardButton(text="➖", callback_data=f"decrease_{product_id}"),
            InlineKeyboardButton(text=f"{quantity}", callback_data="ignore"),
            InlineKeyboardButton(text="➕", callback_data=f"increase_{product_id}"),
            InlineKeyboardButton(text="❌ Удалить", callback_data=f"rremove_{product_id}")
        ])

    text += f"\n💰 *Итого:* {total_price}₽"
    inline_kb.append([InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout")])

    markup = InlineKeyboardMarkup(inline_keyboard=inline_kb)

    if update:
        await message.answer(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await message.answer(text, parse_mode="Markdown", reply_markup=markup)


# Увеличение количества товара в корзине
@dp.callback_query(lambda c: c.data.startswith("increase_"))
async def increase_quantity(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    product_id = int(callback.data.split("_")[1])

    if db.increase_cart_item(user_id, product_id): 
        await callback.answer("➕ Количество товара увеличено!")
    else:
        await callback.answer("❌ Недостаточно товара на складе!", show_alert=True)

    cart_items = db.show_cart(user_id)
    if cart_items:
        await show_cart(callback.message, update=True)  
    else:
        await callback.message.delete() 


# Уменьшение количества товара в корзине
@dp.callback_query(lambda c: c.data.startswith("decrease_"))
async def decrease_quantity(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    product_id = int(callback.data.split("_")[1])

    db.decrease_cart_item(user_id, product_id)

    cart_items = db.show_cart(user_id)
    if cart_items:
        await callback.answer("➖ Количество товара уменьшено!")
        await show_cart(callback.message, update=True) 
    else:
        await callback.message.delete()  
        await callback.answer("🛒 Ваша корзина пуста.")


# Удаление товара из корзины
@dp.callback_query(lambda c: c.data.startswith("rremove_"))
async def remove_item(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data_parts = callback.data.split("_")

    if len(data_parts) < 2 or not data_parts[1].isdigit():
        await callback.answer("⚠ Ошибка: некорректный запрос!", show_alert=True)
        return

    product_id = int(data_parts[1])

    db.remove_from_cart(user_id, product_id)

    cart_items = db.show_cart(user_id)
    if cart_items:
        await callback.answer("❌ Товар удален из корзины!")
        await show_cart(callback.message, update=True)
    else:
        await callback.message.delete()
        await callback.answer("🛒 Ваша корзина пуста.")


# Специальные предложения
@dp.message(lambda message: message.text == "🔥 Специальные предложения")
async def special_offers(message: types.Message):
    products = db.get_products_sorted_by_discount() 

    if not products:
        await message.answer("❌ Нет товаров со скидкой.")
        return

    text = "🔥 <b>Специальные предложения:</b>\n\n"
    buttons = []

    for product in products:
        product_id, name, price, discount_price, image = product
        discount_percent = round((1 - discount_price / price) * 100, 2) if discount_price < price else 0

        text += f"🛍️ <b>{name}</b>\n"
        if discount_percent > 0:
            text += f"💰 <s>{price}₽</s> → <b>{discount_price}₽</b> (-{discount_percent}%)\n\n"
        else:
            text += f"💰 {price}₽\n\n"

        buttons.append([
            InlineKeyboardButton(text=f"🔍 {name}", callback_data=f"view_product_{product_id}"),
            InlineKeyboardButton(text="🛒 В корзину", callback_data=f"add_to_cart_{product_id}")
        ])

    if buttons:
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer("❌ Нет товаров со скидкой.")


# Оферта перед заказом
@dp.callback_query(lambda c: c.data == "checkout")
async def send_offer(callback: types.CallbackQuery):
    offer_text = (
        "⚖️ Оферта для оформления заказа ⚖️\n\n"
        "Перед тем как подтвердить ваш заказ, пожалуйста, внимательно ознакомьтесь с нашими условиями.\n\n"
        "1. Предмет оферты: Мы обязуемся предоставить товар согласно вашему заказу, который вы оформляете через наш интернет-магазин.\n"
        "2. Цена товара: Цена каждого товара указана на странице с его описанием. Мы оставляем за собой право изменить цену товара, но не позднее чем за 3 дня до его отправки.\n"
        "3. Способы оплаты: Оплата заказа возможна только картой через защищенные платежные системы.\n"
        "4. Доставка: Стоимость и сроки доставки зависят от выбранного вами способа доставки. Информация о доставке будет указана в процессе оформления заказа.\n"
        "5. Возврат товара: В случае ненадлежащего качества товара, вы можете вернуть его в течение 14 дней с момента получения, при соблюдении условий возврата.\n"
        "6. Ответственность сторон: Мы не несем ответственности за товары, поврежденные по вине доставки или неправильно указанные вами данные.\n"
        "7. Подтверждение заказа: После подтверждения вами заказа, оферта вступает в силу, и заказ считается оформленным.\n\n"
        "💡 Важно: Подтверждая заказ, вы принимаете все условия нашей оферты и соглашаетесь с ними.\n\n"
        "Для подтверждения заказа, пожалуйста, нажмите 'Подтвердить заказ'. Для отмены - 'Отменить заказ'."
    )
    await callback.message.answer(offer_text, reply_markup=offer_keyboard)


# Запрос номера телефона перед оформлением заказа
@dp.message(lambda message: message.text == "✅ Подтвердить заказ")
async def request_phone(message: types.Message, state: FSMContext):
    cart_items = db.show_cart(message.from_user.id)  

    if not cart_items:
        await message.answer("❌ Ваша корзина пуста.", reply_markup=main_menu)
        return

    cart_text = "🛒 *Ваша корзина:*\n\n"
    cart_text += "\n".join([f"{item[1]} - {item[3]} шт. ({item[2] * item[3]}₽)" for item in cart_items])
    cart_text += f"\n\n💰 *Итого:* {sum(item[2] * item[3] for item in cart_items)}₽"

    await message.answer(cart_text, parse_mode="Markdown")
    await message.answer("📞 Пожалуйста, отправьте ваш номер телефона, нажав на кнопку ниже:", reply_markup=phone_keyboard)
    await state.set_state(OrderState.waiting_for_phone)


# Обработка номера телефона и завершение оформления заказа
@dp.message(lambda message: message.contact)
async def checkout(message: types.Message, state: FSMContext):

    user_id = message.from_user.id
    phone_number = message.contact.phone_number  
    cart_items = db.show_cart(user_id)  

    if not cart_items:
        await message.answer("❌ Ваша корзина пуста.", reply_markup=main_menu)
        return

    total_price = sum(item[2] * item[3] for item in cart_items)
    
    order_id = db.create_order(user_id, phone_number, total_price, None)

    order_text = f"🆕 *Новый заказ #{order_id}* от {message.from_user.full_name} (ID: {user_id})\n"
    order_text += f"📞 Телефон: {phone_number}\n"
    order_text += "\n".join([f"{item[1]} - {item[3]} шт." for item in cart_items])
    order_text += f"\n💰 *Итого:* {total_price}₽\n📦 *Статус:* 🟡 В обработке"

    sent_message = await bot.send_message(GROUP_ID, order_text, parse_mode="Markdown", reply_markup=admin_panel(order_id))

    db.save_order_message_id(order_id, sent_message.message_id)

    for item in cart_items:
        db.update_stock(item[0], item[3])

    db.clear_cart(user_id)

    await message.answer('✅ Ваш заказ оформлен! Мы свяжемся с вами.', reply_markup=main_menu)

    await state.clear()
    await state.clear()


# Обработчик изменения статуса заказа
@dp.callback_query(lambda c: c.data.startswith("status_"))
async def change_order_status(callback: types.CallbackQuery):
    chat_admins = await bot.get_chat_administrators(GROUP_ID)
    admin_ids = [admin.user.id for admin in chat_admins]

    if callback.from_user.id not in admin_ids:
        await callback.answer("❌ У вас нет прав для изменения статуса!", show_alert=True)
        return

    _, order_id, new_status = callback.data.split("_")
    order_id = int(order_id)

    db.update_order_status(order_id, new_status)

    user_id = db.get_user_by_order(order_id)
    message_id = db.get_order_message_id(order_id)

    if not message_id:
        await callback.answer("⚠ Не найдено сообщение заказа в группе!", show_alert=True)
        return

    status_map = {
    "processing": "📦 В обработке",
    "confirmed": "✅ Подтвержден",
    "shipped": "🚚 В пути",
    "canceled": "🛑 Отменен",
    "completed": "🎉 Завершен"
    }

    new_status_text = status_map.get(new_status, "🔄 В обработке")

    updated_text = callback.message.text.split("\n📦 *Статус:*")[0] + f"\n📦 *Статус:* {new_status_text}"
    await bot.edit_message_text(
    text=updated_text,
    chat_id=str(GROUP_ID), 
    message_id=message_id,
    parse_mode="Markdown",
    reply_markup=callback.message.reply_markup
)

    if user_id:
        await bot.send_message(user_id, f"📦 Ваш заказ #{order_id} теперь имеет статус: {new_status_text}")

    await callback.answer("✅ Статус заказа обновлен!")


# Команда для подсчета остатков на складе
@dp.message(Command("count_products"))
async def count_products(message: types.Message):
    # Проверка на администратора
    if message.from_user.id != int(os.getenv('ADMIN_ID')):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    # Получаем список товаров и их количество из базы данных
    products = db.get_all_products_with_stock()  

    if not products:
        await message.answer("❌ Товары не найдены в базе данных.")
        return

    # Создаем список кнопок
    inline_buttons = []
    for product in products:
        product_name, quantity = product  # Предполагается, что каждый элемент — это кортеж (название товара, количество)
        button = InlineKeyboardButton(text=f"{product_name} - {quantity} шт.", callback_data=f"product_{product_name}")
        inline_buttons.append([button])  # Добавляем кнопку в строку

    # Создаем клавиатуру с кнопками
    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_buttons)

    # Отправляем сообщение с клавиатурой
    await message.answer("📦 Список товаров и их количества:", reply_markup=keyboard)


# Личный кабинет
@dp.message(lambda message: message.text == "👤 Личный кабинет")
async def personal_account(message: types.Message):
    await message.answer("👤 Вы в личном кабинете. Выберите действие:", reply_markup=personal_account_kb)


# Заказы пользователя
@dp.message(lambda message: message.text == "📦 Мои заказы")
async def my_orders(message: types.Message):
    user_id = message.from_user.id
    orders = db.get_orders_by_user(user_id)

    if not orders:
        await message.answer("🛒 У вас пока нет заказов.")
        return

    text = "📦 *Ваши заказы:*\n\n"
    
    moscow_timezone = pytz.timezone("Europe/Moscow")
    
    for order in orders:
        print(order) 

        order_id, date, total_price, status_code = order 
        
        status_dict = {
            "processing": "📦 В обработке",
            "confirmed": "✅ Подтвержден",
            "shipped": "🚚 В пути",
            "canceled": "🛑 Отменен",
            "completed": "🎉 Завершен",
            "failed": "❌ Неудача",
            "pending": "⏳ Ожидает"  
        }

        status = status_dict.get(status_code, "Неизвестный статус") 
        print(f"Получен статус: {status_code}")
        order_date = date

        order_date_obj = datetime.strptime(order_date, "%Y-%m-%d %H:%M:%S")
        
        order_date_obj = pytz.utc.localize(order_date_obj)  
        order_date_obj = order_date_obj.astimezone(moscow_timezone)
        
        formatted_date = order_date_obj.strftime("%d.%m.%Y %H:%M")
        text += f"🆔 *Заказ #{order_id}*\n📅 Дата: {formatted_date}\n💰 Сумма: {total_price}₽\n📦 Статус: *{status}*\n\n"

    await message.answer(text, parse_mode="Markdown")


# Избранное
@dp.message(lambda message: message.text == "❤️ Мое избранное")
async def view_favorites(message: types.Message):
    user_id = message.from_user.id
    favorites = db.get_favorites_by_user(user_id)

    if not favorites:
        await message.answer("Ваше избранное пусто.")
        return

    text = "❤️ <b>Ваши избранные товары:</b>\n\n"
    buttons = []

    for fav in favorites:
        product_id = fav[0]
        product_info = db.get_product_info_by_id(product_id)

        if not product_info:
            continue

        name = product_info["name"]
        price = float(product_info["price"])
        discount_price = float(product_info.get("discount_price", price))

        if discount_price < price:
            discount_percent = round((1 - discount_price / price) * 100, 2)
            text += f"🛍️ <b>{name}</b>\n🔥 <s>{price}₽</s> → <b>{discount_price}₽</b> (-{discount_percent}%)\n\n"
        else:
            text += f"🛍️ <b>{name}</b> - {price}₽\n"

        # Добавляем кнопку для удаления товара из избранного
        callback_data = f"remove_favorite_{product_id}"
        print(f"DEBUG: создаем кнопку с callback_data: {callback_data}")
        buttons.append([
            InlineKeyboardButton(text=f"🔍 {name}", callback_data=f"view_product_{product_id}"),
            InlineKeyboardButton(text="❌ Удалить", callback_data=callback_data)
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


# Просмотр товара в избранном
@dp.callback_query(lambda c: c.data.startswith("view_product_"))
async def view_product_from_favorites(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[2]) 
    product = db.get_product_details(product_id)

    if not product:
        await callback.answer("❌ Товар не найден.", show_alert=True)
        return
    
    name, description, price, discount_price, image = product

    text = f"📌 <b>{name}</b>\n\n📄 {description}\n💰 Цена: {price}₽"
    if discount_price < price:
        discount_percent = round((1 - discount_price / price) * 100, 2)
        text += f"\n🔥 <s>{price}₽</s> → <b>{discount_price}₽</b> (-{discount_percent}%)"

    buttons = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Купить", callback_data=f"add_to_cart_{product_id}")]
        ]
    )

    if image and image.startswith("http"):
        await callback.message.answer_photo(photo=image, caption=text, parse_mode="HTML", reply_markup=buttons)
    else:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=buttons)

    await callback.answer()


# Удаление товара из избранного
@dp.callback_query(lambda c: c.data.startswith("remove_favorite_"))
async def remove_favorite(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    product_id = int(parts[2])
    db.remove_favorite(user_id, product_id)

    await callback.answer("❌ Товар удалён из избранного.", show_alert=True)
    await callback.message.delete()


# Возвращение в главное меню
@dp.message(lambda message: message.text == "🔙 Назад")
async def back_to_main(message: types.Message):
    await message.answer("🔙 Возвращаем вас в главное меню.", reply_markup=main_menu)


# Обработчик для команды "Информация о доставке"
@dp.message(lambda message: message.text == "🚚 Информация о доставке")
async def delivery_info(message: types.Message):
    delivery_details = (
        "🚚 *Информация о доставке:*\n\n"
        "Мы предоставляем удобные и быстрые способы доставки товаров:\n\n"
        "1. 🚚 *Доставка через СДЭК*: Товары отправляются СДЭКом, срок доставки (по Москве) — от 1 до 2 рабочих дней.\n"
        "2. 📍 *Самовывоз*: Заберите заказ в нашем магазине, указав ваше имя и номер заказа.\n\n"
        "*Стоимость доставки*: Зависит от выбранного способа и региона доставки. Подробности уточняйте у нашего оператора.\n"
        "Если у вас возникли вопросы, не стесняйтесь обратиться к нам через поддержку!"
    )

    await message.answer(delivery_details, parse_mode="Markdown", reply_markup=delivery_info_kb)\


# Контакты
@dp.message(lambda message: message.text == "📞 Контакты")
async def contacts(message: types.Message):
    await message.answer("📞 +7 977 412 60 27\n📧 Email: example@mail.com")


# Запуск бота
async def main():
    logging.basicConfig(level=logging.INFO)
    dp.include_router(router)
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())