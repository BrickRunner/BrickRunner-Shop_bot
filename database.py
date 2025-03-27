import sqlite3
from contextlib import closing

class Database:
    def __init__(self):
        self.conn = sqlite3.connect("shop.db")
        self.cursor = self.conn.cursor()
        self.add_phone_number_column()
        self.create_tables()

    def create_tables(self):
        """Создает таблицы, если их нет"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                description TEXT,
                price REAL,
                discount_price REAL,
                quantity INTEGER,
                image TEXT
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                PRIMARY KEY (user_id, product_id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                phone_number TEXT NOT NULL,  -- ДОЛЖНО БЫТЬ phone_number, НЕ phone!
                total_price REAL NOT NULL,
                status TEXT DEFAULT 'processing',
                date DATETIME DEFAULT CURRENT_TIMESTAMP,
                message_id INTEGER
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, product_id),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        """)

        self.conn.commit()


    def add_product(self, name, description, price, discount_price, quantity, image):
        """Добавляет новый товар в БД"""
        self.cursor.execute("""
            INSERT INTO products (name, description, price, discount_price, quantity, image) 
            VALUES (?, ?, ?, ?, ?, ?)
            """, (name, description, price, discount_price, quantity, image))
        self.conn.commit()


    def get_product_info(self, product_id):
        """Получает информацию о товаре по ID"""
        self.cursor.execute("SELECT name, description, price, discount_price, quantity, image FROM products WHERE id = ?", (product_id,))
        return self.cursor.fetchone()


    def add_to_favorites(self, user_id, product_id):
        """Добавляет товар в избранное пользователя."""
        conn = sqlite3.connect("shop.db")
        cursor = conn.cursor()


        cursor.execute("""
            INSERT INTO favorites (user_id, product_id) 
            VALUES (?, ?)
        """, (user_id, product_id))
        
        conn.commit()


    def get_favorites_by_user(self, user_id):
        """Возвращает все избранные товары пользователя."""
        conn = sqlite3.connect("shop.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.id, p.name, p.price, p.discount_price 
            FROM favorites f
            JOIN products p ON f.product_id = p.id
            WHERE f.user_id = ?
        """, (user_id,))
        
        favorites = cursor.fetchall()
        
        return favorites


    def remove_favorite(self, user_id: int, product_id: int):
        """Удаляет товар из избранного пользователя, но НЕ удаляет сам товар из каталога."""
        conn = sqlite3.connect("shop.db")
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM favorites WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        conn.commit()


    def get_products_sorted_by_discount(self):
        """Возвращает товары, отсортированные по размеру скидки (от максимальной к минимальной)."""
        self.cursor.execute("""
            SELECT id, name, price, discount_price, image
            FROM products
            WHERE discount_price < price
            ORDER BY (price - discount_price) DESC
        """)
        return self.cursor.fetchall()


    def get_product_info_by_id(self, product_id):
        """Возвращает информацию о товарах"""
        query = "SELECT name, price, discount_price FROM products WHERE id = ?"
        self.cursor.execute(query, (product_id,))
        result = self.cursor.fetchone()
    
        if result:
            return {
                "name": result[0],
                "price": result[1],
                "discount_price": result[2] if result[2] is not None else result[1]  
            }
        return None


    def save_order_message_id(self, order_id, message_id):
        """Сохраняет ID сообщения заказа в группе."""
        self.cursor.execute("UPDATE orders SET message_id = ? WHERE id = ?", (message_id, order_id))
        self.conn.commit()


    def get_order_message_id(self, order_id):
        """Получает ID сообщения заказа в группе."""
        self.cursor.execute("SELECT message_id FROM orders WHERE id = ?", (order_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None


    def add_phone_number_column(self):
        """Добавляет колонку phone_number, если ее нет"""
        try:
            self.cursor.execute("ALTER TABLE orders ADD COLUMN phone_number TEXT")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  


    def get_product_quantity(self, product_id):
        """Возвращает количество товара в наличии"""
        self.cursor.execute("SELECT quantity FROM products WHERE id = ?", (product_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 0


    def reduce_product_quantity(self, product_id, quantity):
        """Уменьшает количество товара в наличии"""
        self.cursor.execute(
            "UPDATE products SET quantity = quantity - ? WHERE id = ? AND quantity >= ?",
            (quantity, product_id, quantity)
        )
        self.conn.commit()


    def get_cart_quantity(self, user_id, product_id):
        """Возвращает количество товара в корзине у пользователя"""
        self.cursor.execute(
            "SELECT quantity FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id)
        )
        result = self.cursor.fetchone()
        return result[0] if result else 0


    def add_to_cart(self, user_id, product_id, quantity):
        """Добавляет товар в корзину, если общее количество не превышает доступное"""
        available_quantity = self.get_product_quantity(product_id)
        current_cart_quantity = self.get_cart_quantity(user_id, product_id)

        if current_cart_quantity + quantity > available_quantity:
            return False  

        self.cursor.execute(
            "INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + ?",
            (user_id, product_id, quantity, quantity)
        )
        self.conn.commit()
        return True


    def get_product_by_id(self, product_id):
        """ Получает товар по его ID. """
        self.cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        return self.cursor.fetchone()
    


    def delete_product(self, product_id):
        """ Удаляет товар из базы данных по его ID. """
        self.cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        self.conn.commit()


    def get_product(self):
        """Получает информацию о товарах"""
        self.cursor.execute("SELECT id, name, price, discount_price FROM products") 
        return self.cursor.fetchall()


    def get_product_by_name(self, name):
        """Получает информацию о товаре по его имени"""
        self.cursor.execute("SELECT * FROM products WHERE name = ?", (name,))
        return self.cursor.fetchone()


    def delete_product_by_name(self, name):
        """Удаляет товар по его имени"""
        self.cursor.execute("DELETE FROM products WHERE name = ?", (name,))
        self.conn.commit()


    def get_product_details(self, product_id):
        """Получает подробную информацию  о товаре"""
        with closing(self.conn.cursor()) as cursor:
            cursor.execute("SELECT name, description, price, discount_price, image FROM products WHERE id = ?", (product_id,))
            return cursor.fetchone()


    def show_cart(self, user_id):
        """Возвращает список товаров в корзине пользователя"""
        self.cursor.execute("""
            SELECT p.id, p.name, p.discount_price, c.quantity
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = ?
        """, (user_id,))
    
        return self.cursor.fetchall()


    def get_orders_by_user(self, user_id):
        """Возвращает все товара пользователя"""
        self.cursor.execute(
            "SELECT id, date, total_price, status FROM orders WHERE user_id = ?", (user_id,)
        )
        result = self.cursor.fetchall()
        print("Результат запроса:", result) 
        return result


    def update_order_status(self, order_id, new_status):
        """Обновляет статус заказа"""
        self.cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        self.conn.commit()


    def get_user_by_order(self, order_id):
        """Получает user_id по номеру заказа"""
        self.cursor.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None


    def increase_cart_item(self, user_id, product_id):
        """ Увеличивает количество товара в корзине, если хватает на складе """
        available_quantity = self.get_product_quantity(product_id)
        current_cart_quantity = self.get_cart_quantity(user_id, product_id)

        if current_cart_quantity < available_quantity:
            self.cursor.execute(
            "UPDATE cart SET quantity = quantity + 1 WHERE user_id = ? AND product_id = ?",
            (user_id, product_id)
            )
            self.conn.commit()
            return True
        return False  


    def decrease_cart_item(self, user_id, product_id):
        """ Уменьшает количество товара в корзине, удаляя товар, если он становится 0 """
        self.cursor.execute(
            "UPDATE cart SET quantity = quantity - 1 WHERE user_id = ? AND product_id = ? AND quantity > 1",
            (user_id, product_id)
        )
        self.cursor.execute("DELETE FROM cart WHERE user_id = ? AND product_id = ? AND quantity = 0", (user_id, product_id))
        self.conn.commit()


    def remove_from_cart(self, user_id, product_id):
        """ Удаляет товар из корзины """
        self.cursor.execute("DELETE FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        self.conn.commit()


    def update_stock(self, product_id, quantity_sold):
        """Обновляет количество товара после оформления заказа"""
        self.cursor.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (quantity_sold, product_id))
        self.conn.commit()


    def clear_cart(self, user_id):
        """Очищает корзину пользователя"""
        self.cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        self.conn.commit()


    def create_order(self, user_id, phone_number, total_price, message_id):
        """Создает заказ и сохраняет его в базе."""
        self.cursor.execute(
            "INSERT INTO orders (user_id, phone_number, total_price, status, message_id) VALUES (?, ?, ?, 'pending', ?)",
            (user_id, phone_number, total_price, message_id)
        )
        self.conn.commit()
        return self.cursor.lastrowid 


    def add_order_item(self, order_id, product_id, quantity, price):
        """Сохраняет товары в заказе"""
        self.cursor.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
            (order_id, product_id, quantity, price)
        )
        self.conn.commit()


    def get_order_by_id(self, order_id):
        """Получает информацию о заказе по его ID"""
        self.cursor.execute("SELECT id, user_id, phone, total_price, status FROM orders WHERE id = ?", (order_id,))
        return self.cursor.fetchone()


    def get_all_products_with_stock(self):
        """Получает все товары и их количество"""
        query = "SELECT name, quantity FROM products"  
        self.cursor.execute(query)
        return self.cursor.fetchall()


    def close(self):
        self.conn.close()
