import sqlite3
from contextlib import closing

class Database:
    def __init__(self):
        self.conn = sqlite3.connect("shop.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        with closing(self.conn.cursor()) as cursor:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                description TEXT,
                price REAL,
                quantity INTEGER,
                image TEXT
            )""")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                PRIMARY KEY (user_id, product_id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )""")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT DEFAULT CURRENT_TIMESTAMP,
                total_price REAL,
                status TEXT DEFAULT 'Ожидает обработки'
            )""")

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                order_id INTEGER,
                product_id INTEGER,
                quantity INTEGER,
                price REAL,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )""")
            
            self.conn.commit()

    def add_product(self, name, description, price, quantity, image):
        with closing(self.conn.cursor()) as cursor:
            cursor.execute("""
            INSERT INTO products (name, description, price, quantity, image)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET description=excluded.description, price=excluded.price, quantity=excluded.quantity, image=excluded.image
            """, (name, description, price, quantity, image))
            self.conn.commit()

    def get_products(self):
        with closing(self.conn.cursor()) as cursor:
            cursor.execute("SELECT id, name, price FROM products")
            return cursor.fetchall()

    def get_product_details(self, product_id):
        with closing(self.conn.cursor()) as cursor:
            cursor.execute("SELECT name, description, price, image FROM products WHERE id = ?", (product_id,))
            return cursor.fetchone()

    def add_to_cart(self, user_id, product_id):
        with closing(self.conn.cursor()) as cursor:
            cursor.execute("""
            INSERT INTO cart (user_id, product_id, quantity)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + 1
            """, (user_id, product_id))
            self.conn.commit()

    def show_cart(self, user_id):
        with closing(self.conn.cursor()) as cursor:
            cursor.execute("""
            SELECT c.product_id, p.name, p.price, c.quantity 
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = ?
            """, (user_id,))
            return cursor.fetchall()

    def get_orders_by_user(self, user_id):
        with closing(self.conn.cursor()) as cursor:
            cursor.execute("""
            SELECT id, date, total_price, status FROM orders WHERE user_id = ? ORDER BY date DESC
            """, (user_id,))
            return cursor.fetchall()

    def increase_cart_item(self, user_id, product_id):
        """Увеличивает количество товара в корзине"""
        self.cursor.execute("UPDATE cart SET quantity = quantity + 1 WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        self.conn.commit()

    def decrease_cart_item(self, user_id, product_id):
        """Уменьшает количество товара в корзине или удаляет товар, если количество стало 0"""
        self.cursor.execute("SELECT quantity FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        result = self.cursor.fetchone()
        if result and result[0] > 1:
            self.cursor.execute("UPDATE cart SET quantity = quantity - 1 WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        else:
            self.cursor.execute("DELETE FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        self.conn.commit()

    def remove_from_cart(self, user_id, product_id):
        """Удаляет товар из корзины"""
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

    
    def close(self):
        self.conn.close()
