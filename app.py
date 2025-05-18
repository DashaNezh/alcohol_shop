from flask import Flask, request, jsonify, session, render_template, send_from_directory, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor
from flask_cors import CORS
import uuid
import os
from dotenv import load_dotenv
from decimal import Decimal
from werkzeug.utils import secure_filename
import time
from functools import wraps
from recommendation_system import RecommendationSystem

# Загрузка переменных окружения
load_dotenv()

app = Flask(__name__)
app.secret_key = str(uuid.uuid4())
CORS(app)


# Декоратор для проверки прав администратора
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return jsonify({'error': 'Forbidden'}), 403
        return f(*args, **kwargs)

    return decorated_function


# Настройка для загрузки файлов
UPLOAD_FOLDER = 'static/images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Маршрут для получения изображений
@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# Маршрут для загрузки изображения
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if not session.get('is_admin'):
        return jsonify({'error': 'Forbidden'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Добавляем уникальный префикс к имени файла
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        return jsonify({
            'message': 'File uploaded successfully',
            'filename': unique_filename,
            'url': f'/static/uploads/{unique_filename}'
        }), 201

    return jsonify({'error': 'File type not allowed'}), 400


# Функция для создания соединения с базой данных
def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "alcohol_shop"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "123"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        return conn
    except psycopg2.Error as e:
        app.logger.error(f"Failed to connect to database: {e}")
        raise


# Маршрут для рендеринга index.html
@app.route('/')
def index():
    return render_template('welcome.html')


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/register')
def register_page():
    return render_template('register.html')


@app.route('/shop')
def shop():
    return render_template('index.html')


@app.route('/profile')
def user_profile():
    if 'user_id' not in session:
        return redirect(url_for('login_page')) # Перенаправляем на логин, если не авторизован
    return render_template('profile.html')


@app.route('/admin')
def admin_panel():
    if not session.get('is_admin'):
        return "Access denied", 403
    return render_template('admin_panel.html')  # Отдельный шаблон для админа


# Вспомогательная функция для логирования активности
def log_user_activity(user_id, action_type, action_details=None):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "INSERT INTO user_activity (user_id, action_type, action_details) VALUES (%s, %s, %s)",
                (user_id, action_type, action_details)
            )
            conn.commit()
    except psycopg2.Error as e:
        app.logger.error(f"Failed to log user activity: {e}")
        raise
    finally:
        conn.close()


# Регистрация пользователя
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    phone = data.get('phone')
    address = data.get('address')
    registration_source = data.get('registration_source', 'web')

    if not username or not password or not email:
        return jsonify({'error': 'Missing fields'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
            if cursor.fetchone():
                return jsonify({'error': 'User already exists'}), 400

            password_hash = generate_password_hash(password)
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, email, first_name, last_name, phone, address, registration_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (username, password_hash, email, first_name, last_name, phone, address, registration_source)
            )
            user_id = cursor.fetchone()['id']
            conn.commit()

            log_user_activity(user_id, 'register', f'User registered via {registration_source}')

            return jsonify({'message': 'User registered', 'user_id': user_id}), 201
    except psycopg2.Error as e:
        conn.rollback()
        app.logger.error(f"Failed to register user: {e}")
        return jsonify({'error': 'Registration failed'}), 500
    finally:
        conn.close()


# Авторизация пользователя
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT id, password_hash, role FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()

            if not user or not check_password_hash(user['password_hash'], password):
                return jsonify({'error': 'Invalid credentials'}), 401

            session['user_id'] = user['id']  # <---- Добавить эту строку
            session['user_role'] = user['role']
            session['is_admin'] = (user['role'] == 'admin')

            log_user_activity(user['id'], 'login', 'User logged in via web')

            return jsonify({'message': 'Logged in', 'user_id': user['id'], 'role': user['role']}), 200
    finally:
        conn.close()


# Выход из системы
@app.route('/api/logout', methods=['POST'])
def logout():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    user_id = session['user_id']
    session.pop('user_id', None)

    log_user_activity(user_id, 'logout', 'User logged out')

    return jsonify({'message': 'Logged out'}), 200


# Получение списка товаров
@app.route('/api/products', methods=['GET'])
def get_products():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT p.*, c.name as category_name, b.name as brand_name
                FROM products p
                JOIN categories c ON p.category_id = c.id
                JOIN brands b ON p.brand_id = b.id
            """)
            products = cursor.fetchall()
            return jsonify(products), 200
    finally:
        conn.close()


# Получение данных о товаре
@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT p.*, c.name as category_name, b.name as brand_name
                FROM products p
                JOIN categories c ON p.category_id = c.id
                JOIN brands b ON p.brand_id = b.id
                WHERE p.id = %s
            """, (product_id,))
            product = cursor.fetchone()
            if not product:
                return jsonify({'error': 'Product not found'}), 404
            return jsonify(product), 200
    finally:
        conn.close()


# Получение списка брендов
@app.route('/api/brands', methods=['GET'])
def get_brands():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT id, name, description FROM brands ORDER BY name")
            brands = cursor.fetchall()
            return jsonify(brands), 200
    finally:
        conn.close()


# Добавление нового бренда
@app.route('/api/brands', methods=['POST'])
@admin_required
def add_brand():
    data = request.get_json()
    name = data.get('name')
    description = data.get('description')

    if not name:
        return jsonify({'error': 'Brand name is required'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO brands (name, description) VALUES (%s, %s) RETURNING id",
                (name, description)
            )
            brand_id = cursor.fetchone()[0]
            conn.commit()
            return jsonify({'message': 'Brand added successfully', 'id': brand_id}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# Обновление маршрута добавления товара
@app.route('/api/products', methods=['POST'])
@admin_required
def add_product():
    data = request.get_json()
    name = data.get('name')
    category_name = data.get('category_name')
    brand_id = data.get('brand_id')
    price = Decimal(data.get('price'))
    volume = data.get('volume')
    strength = data.get('strength')
    stock = data.get('stock')
    image_url = data.get('image_url')

    if not all([name, category_name, brand_id, price, volume, strength, stock]):
        return jsonify({'error': 'All fields are required'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Получаем ID категории по имени
            cursor.execute("SELECT id FROM categories WHERE name = %s", (category_name,))
            category = cursor.fetchone()
            if not category:
                return jsonify({'error': 'Category not found'}), 404
            category_id = category[0]

            cursor.execute(
                """
                INSERT INTO products (name, category_id, brand_id, price, volume, strength, stock, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (name, category_id, brand_id, price, volume, strength, stock, image_url)
            )
            conn.commit()
            return jsonify({'message': 'Product added successfully'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# Добавление товара в корзину
@app.route('/api/cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)
    app.logger.info(f'Received add_to_cart request: product_id={product_id}, quantity={quantity}') # Логирование 1

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Проверяем наличие товара
            cursor.execute("SELECT id, name, stock FROM products WHERE id = %s", (product_id,))
            product = cursor.fetchone()
            if not product:
                app.logger.warning(f'Product not found: product_id={product_id}')
                return jsonify({'error': 'Product not found'}), 404

            # Проверяем, есть ли уже этот товар в корзине
            cursor.execute(
                "SELECT id, quantity FROM cart WHERE user_id = %s AND product_id = %s",
                (session['user_id'], product_id)
            )
            existing_item = cursor.fetchone()

            if existing_item:
                # Если товар уже есть в корзине, обновляем количество
                new_quantity = existing_item['quantity'] + quantity
                app.logger.info(f"Updating cart item id={existing_item['id']}: old_quantity={existing_item['quantity']}, new_quantity={new_quantity}") # Логирование 2 (Update)
                cursor.execute(
                    "UPDATE cart SET quantity = %s WHERE id = %s",
                    (new_quantity, existing_item['id'])
                )
                cart_id = existing_item['id']
            else:
                # Если товара нет в корзине, создаем новую запись
                app.logger.info(f"Inserting new cart item: user_id={session['user_id']}, product_id={product_id}, quantity={quantity}") # Логирование 2 (Insert)
                cursor.execute(
                    "INSERT INTO cart (user_id, product_id, quantity) VALUES (%s, %s, %s) RETURNING id",
                    (session['user_id'], product_id, quantity)
                )
                cart_id = cursor.fetchone()['id']

            log_user_activity(session['user_id'], 'add_to_cart', f'Added product_id: {product_id} ({product["name"]})')

            conn.commit()
            app.logger.info(f'Cart updated successfully. Cart item id: {cart_id}')
            return jsonify({'message': 'Added to cart', 'cart_id': cart_id}), 201
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Failed to add to cart: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# Получение содержимого корзины
@app.route('/api/cart', methods=['GET'])
def get_cart():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT c.id, c.quantity, p.id as product_id, p.name, p.price, p.category_id, p.volume, p.strength
                FROM cart c
                JOIN products p ON c.product_id = p.id
                WHERE c.user_id = %s
            """, (session['user_id'],))
            cart_items = cursor.fetchall()

            # --- Расчет цен с учетом скидок в корзине ---
            processed_cart_items = []
            # Если корзина пуста, возвращаем пустой список
            if not cart_items:
                return jsonify([]), 200

            # Сначала сгруппируем товары по product_id, чтобы учесть общее количество для акций типа 'N по цене M'
            items_by_product = {}
            for item in cart_items:
                if item['product_id'] not in items_by_product:
                    items_by_product[item['product_id']] = []
                items_by_product[item['product_id']].append(item)

            for product_id, items in items_by_product.items():
                total_quantity = sum(item['quantity'] for item in items)
                # Предполагаем, что все позиции одного product_id имеют одинаковую базовую цену
                original_price_per_item = float(items[0]['price'])

                # Поиск активной акции для товара
                cursor.execute('''
                    SELECT id, name, discount_percent FROM promotions
                    WHERE (
                        (product_id = %s) OR
                        (id IN (SELECT promotion_id FROM promotion_categories WHERE category_id = %s))
                    )
                    AND start_date <= NOW() AND end_date >= NOW()
                    ORDER BY discount_percent DESC LIMIT 1
                ''', (product_id, items[0]['category_id']))
                promo = cursor.fetchone()

                applied_discount_percent = 0
                total_discount_for_product = 0
                effective_price_per_item = original_price_per_item
                promotion_name = None

                if promo:
                    promotion_name = promo['name']
                    promo_id = promo['id']
                    promo_discount_percent = float(promo['discount_percent'])

                    # Специальная логика для акции '3 пива по цене 2'
                    if promotion_name == '3 пива по цене 2' and product_id == 14 and total_quantity >= 3:
                        # Скидка применяется к наименее дорогим товарам. В акции 3 по цене 2, один товар бесплатен.
                        num_free_items = total_quantity // 3
                        total_discount_for_product = num_free_items * original_price_per_item
                        # Рассчитываем эффективную цену за единицу для отображения
                        total_price_for_product_with_discount = (
                                                                            total_quantity * original_price_per_item) - total_discount_for_product
                        effective_price_per_item = total_price_for_product_with_discount / total_quantity if total_quantity > 0 else original_price_per_item
                        applied_discount_percent = (total_discount_for_product / (
                                                                      total_quantity * original_price_per_item)) * 100 if (
                                                                                                    total_quantity * original_price_per_item) > 0 else 0
                        applied_discount_percent = round(applied_discount_percent, 2)
                    # Добавляем проверку: если это акция '3 по цене 2', не применяем стандартную процентную скидку, если количество меньше 3
                    elif not (promotion_name == '3 пива по цене 2' and product_id == 14) and promo_discount_percent > 0:
                        # Для обычных процентных скидок
                        effective_price_per_item = round(original_price_per_item * (1 - promo_discount_percent / 100),
                                                         2)
                        applied_discount_percent = promo_discount_percent
                        total_discount_for_product = (
                                                                 original_price_per_item - effective_price_per_item) * total_quantity

                # Добавляем каждую позицию обратно с рассчитанными ценами и скидками
                for item in items:
                    processed_cart_items.append({
                        'id': item['id'],
                        'product_id': item['product_id'],
                        'name': item['name'],
                        'quantity': item['quantity'],
                        'original_price': original_price_per_item,
                        'discounted_price': effective_price_per_item,  # Используем эффективную цену за единицу
                        'price': effective_price_per_item,
                        # Используем эффективную цену за единицу для отображения итогов
                        'discount_percent': applied_discount_percent,
                        'discount_applied_per_item': round((original_price_per_item - effective_price_per_item), 2),
                        'promotion_name': promotion_name
                    })

            return jsonify(processed_cart_items), 200
    except Exception as e:
        app.logger.error(f"Failed to get cart contents: {e}")
        return jsonify({'error': 'Failed to get cart contents'}), 500
    finally:
        conn.close()


# Очистка корзины
@app.route('/api/cart', methods=['DELETE'])
def clear_cart():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM cart WHERE user_id = %s", (session['user_id'],))
            conn.commit()
            log_user_activity(session['user_id'], 'clear_cart', 'Cart cleared')
            return jsonify({'message': 'Cart cleared successfully'}), 200
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Failed to clear cart: {e}")
        return jsonify({'error': 'Failed to clear cart'}), 500
    finally:
        conn.close()


@app.route('/api/me', methods=['GET'])
def me():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT username, email, role FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                return jsonify({'error': 'User not found'}), 404

            return jsonify({
                'username': user['username'],
                'email': user['email'],
                'is_admin': user['role'] == 'admin'
            })
    finally:
        conn.close()


@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    if not session.get('is_admin'):
        return jsonify({'error': 'Forbidden'}), 403

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT id, username, email, role FROM users ORDER BY id")
            users = cursor.fetchall()
            # Преобразуем поле role в is_admin для ответа
            for u in users:
                u['is_admin'] = (u['role'] == 'admin')
            return jsonify(users)
    finally:
        conn.close()


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    # Проверка, что текущий пользователь — админ
    if not session.get('is_admin'):
        return jsonify({'error': 'Access denied'}), 403

    # Не даём удалять самого себя
    if session.get('user_id') == user_id:
        return jsonify({'error': 'Cannot delete yourself'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Проверяем, существует ли пользователь
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Удаляем пользователя
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

            # Опционально — логируем это действие (можно вызвать твою функцию log_user_activity)
            # log_user_activity(session.get('user_id'), 'delete_user', f'Deleted user_id {user_id}')

            return jsonify({'message': 'User deleted successfully'}), 200
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Failed to delete user: {e}")
        return jsonify({'error': 'Failed to delete user'}), 500
    finally:
        conn.close()


@app.route('/api/admin/orders', methods=['GET'])
def get_all_orders():
    if not session.get('is_admin'):
        return jsonify({'error': 'Forbidden'}), 403

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Выбираем заказы вместе с данными пользователя
            cursor.execute("""
                SELECT o.id as order_id, o.user_id, u.username, u.email, o.total_price, o.delivery_address,
                       o.delivery_method, o.delivery_cost, o.payment_method, o.status, o.created_at
                FROM orders o
                JOIN users u ON o.user_id = u.id
                ORDER BY o.created_at DESC
            """)
            orders = cursor.fetchall()

            # Для каждого заказа подгружаем позиции заказа
            for order in orders:
                cursor.execute("""
                    SELECT oi.product_id, p.name as product_name, oi.quantity, oi.price
                    FROM order_items oi
                    JOIN products p ON oi.product_id = p.id
                    WHERE oi.order_id = %s
                """, (order['order_id'],))
                order_items = cursor.fetchall()
                order['items'] = order_items

            return jsonify(orders), 200
    finally:
        conn.close()


# Получение заказов текущего пользователя
@app.route('/api/orders', methods=['GET'])
def get_user_orders():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT o.id as order_id, o.total_price, o.delivery_address,
                       o.delivery_method, o.delivery_cost, o.payment_method, o.status, o.created_at
                FROM orders o
                WHERE o.user_id = %s
                ORDER BY o.created_at DESC
            """, (session['user_id'],))
            orders = cursor.fetchall()

            for order in orders:
                cursor.execute("""
                    SELECT oi.product_id, p.name as product_name, oi.quantity, oi.price, oi.discount_applied
                    FROM order_items oi
                    JOIN products p ON oi.product_id = p.id
                    WHERE oi.order_id = %s
                """, (order['order_id'],))
                order_items = cursor.fetchall()
                order['items'] = order_items

            return jsonify(orders), 200
    except Exception as e:
        app.logger.error(f"Failed to get user orders: {e}")
        return jsonify({'error': 'Failed to get user orders'}), 500
    finally:
        conn.close()


# Оформление заказа
@app.route('/api/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    delivery_address = data.get('delivery_address')
    delivery_method = data.get('delivery_method')
    payment_method = data.get('payment_method')

    if not delivery_address or not delivery_method or not payment_method:
        return jsonify({'error': 'Missing delivery or payment details'}), 400

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT c.quantity, p.id as product_id, p.price, p.name, p.stock, p.category_id
                FROM cart c
                JOIN products p ON c.product_id = p.id
                WHERE c.user_id = %s
            """, (session['user_id'],))
            cart_items = cursor.fetchall()

            if not cart_items:
                return jsonify({'error': 'Cart is empty'}), 400

            # Проверка остатков
            for item in cart_items:
                if item['stock'] < item['quantity']:
                    return jsonify({'error': f'Insufficient stock for {item["name"]}'}), 400

            # --- Применение скидок ---
            total_price = 0
            discounted_items = []
            now = "CURRENT_TIMESTAMP"
            for item in cart_items:
                # Поиск активной акции для товара
                cursor.execute('''
                    SELECT discount_percent FROM promotions
                    WHERE (
                        (product_id = %s) OR
                        (id IN (SELECT promotion_id FROM promotion_categories WHERE category_id = %s))
                    )
                    AND start_date <= NOW() AND end_date >= NOW()
                    ORDER BY discount_percent DESC LIMIT 1
                ''', (item['product_id'], item['category_id']))
                promo = cursor.fetchone()
                discount_percent = float(promo['discount_percent']) if promo else 0
                price = float(item['price'])
                discount_applied = 0
                if discount_percent > 0:
                    discount_applied = round(price * discount_percent / 100, 2)
                    price = round(price - discount_applied, 2)
                total_price += price * item['quantity']
                discounted_items.append({
                    'product_id': item['product_id'],
                    'quantity': item['quantity'],
                    'price': price,
                    'discount_applied': discount_applied
                })

            delivery_cost = 300.00 if delivery_method == 'courier' else 0.00

            cursor.execute(
                """
                INSERT INTO orders (user_id, total_price, delivery_address, delivery_method, delivery_cost, payment_method, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (session['user_id'], total_price + delivery_cost, delivery_address, delivery_method, delivery_cost,
                 payment_method, 'paid')
            )
            order_id = cursor.fetchone()['id']

            for item in discounted_items:
                cursor.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, price, discount_applied) VALUES (%s, %s, %s, %s, %s)",
                    (order_id, item['product_id'], item['quantity'], item['price'], item['discount_applied'])
                )

            log_user_activity(session['user_id'], 'checkout',
                              f'Order placed: order_id {order_id}, total {total_price + delivery_cost}')

            cursor.execute("DELETE FROM cart WHERE user_id = %s", (session['user_id'],))
            conn.commit()
            return jsonify(
                {'message': 'Заказ оформлен', 'order_id': order_id,
                 'total_price': str(total_price + delivery_cost)}), 201
    finally:
        conn.close()


@app.route('/api/products/<int:product_id>', methods=['PUT'])
@admin_required
def update_product(product_id):
    try:
        # Получаем данные из формы
        name = request.form.get('name')
        category_name = request.form.get('category')
        brand_name = request.form.get('brand')
        price = request.form.get('price')
        volume = request.form.get('volume')
        strength = request.form.get('strength')
        stock = request.form.get('stock')

        # Проверяем наличие всех необходимых полей
        if not all([name, category_name, brand_name, price, volume, strength, stock]):
            return jsonify({'success': False, 'error': 'Все поля должны быть заполнены'})

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Проверяем, существует ли товар
                cursor.execute('SELECT id FROM products WHERE id = %s', (product_id,))
                if not cursor.fetchone():
                    return jsonify({'success': False, 'error': 'Товар не найден'})

                # Получаем ID категории и бренда
                cursor.execute('SELECT id FROM categories WHERE name = %s', (category_name,))
                category = cursor.fetchone()
                if not category:
                    return jsonify({'success': False, 'error': 'Категория не найдена'})

                cursor.execute('SELECT id FROM brands WHERE name = %s', (brand_name,))
                brand = cursor.fetchone()
                if not brand:
                    return jsonify({'success': False, 'error': 'Бренд не найден'})

                # Обрабатываем изображение, если оно было загружено
                image_url = None
                if 'image' in request.files:
                    file = request.files['image']
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        # Добавляем timestamp к имени файла для уникальности
                        filename = f"{int(time.time())}_{filename}"
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        image_url = f"/static/images/{filename}"

                # Обновляем товар в базе данных
                if image_url:
                    cursor.execute('''
                        UPDATE products 
                        SET name = %s, category_id = %s, brand_id = %s, price = %s, 
                            volume = %s, strength = %s, stock = %s, image_url = %s
                        WHERE id = %s
                    ''', (name, category[0], brand[0], price, volume, strength, stock, image_url, product_id))
                else:
                    cursor.execute('''
                        UPDATE products 
                        SET name = %s, category_id = %s, brand_id = %s, price = %s, 
                            volume = %s, strength = %s, stock = %s
                        WHERE id = %s
                    ''', (name, category[0], brand[0], price, volume, strength, stock, product_id))

                conn.commit()
                return jsonify({'success': True})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/promotions/active')
def get_active_promotion():
    product_id = request.args.get('product_id', type=int)
    category_id = request.args.get('category_id', type=int)
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute('''
                SELECT discount_percent FROM promotions
                WHERE (
                    (product_id = %s) OR
                    (id IN (SELECT promotion_id FROM promotion_categories WHERE category_id = %s))
                )
                AND start_date <= NOW() AND end_date >= NOW()
                ORDER BY discount_percent DESC LIMIT 1
            ''', (product_id, category_id))
            promo = cursor.fetchone()
            if promo:
                return jsonify({'discount_percent': float(promo['discount_percent'])})
            else:
                return jsonify({})
    finally:
        conn.close()


# Создаем экземпляр системы рекомендаций
recommender = RecommendationSystem()
try:
    recommender.prepare_data()
    recommender.compute_similarities()
except Exception as e:
    app.logger.error(f"Failed to initialize recommendation system: {e}")


@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    if 'user_id' not in session:
        # Для неавторизованных пользователей возвращаем популярные товары
        try:
            recommendations = recommender.get_popular_recommendations(6)
            return jsonify(recommendations), 200
        except Exception as e:
            app.logger.error(f"Failed to get popular recommendations: {e}")
            return jsonify([]), 200

    try:
        # Для авторизованных пользователей возвращаем персонализированные рекомендации
        recommendations = recommender.get_user_recommendations(session['user_id'], 6)
        return jsonify(recommendations), 200
    except Exception as e:
        app.logger.error(f"Failed to get user recommendations: {e}")
        # В случае ошибки возвращаем популярные товары
        try:
            recommendations = recommender.get_popular_recommendations(6)
            return jsonify(recommendations), 200
        except Exception as e:
            app.logger.error(f"Failed to get popular recommendations: {e}")
            return jsonify([]), 200


if __name__ == '__main__':
    app.run(debug=True)