-- Удаляем все таблицы, если они существуют, с каскадным удалением зависимостей
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS promotion_categories CASCADE;
DROP TABLE IF EXISTS promotions CASCADE;
DROP TABLE IF EXISTS cart CASCADE;
DROP TABLE IF EXISTS price_history CASCADE;
DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS brands CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS user_activity CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Таблица пользователей
-- Хранит данные пользователей (покупатели, админы)
-- Добавлены registered_at и registration_source для отслеживания регистрации
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    phone VARCHAR(20),
    address TEXT,
    role VARCHAR(20) DEFAULT 'customer' CHECK (role IN ('customer', 'admin')),
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Время регистрации
    registration_source VARCHAR(20) DEFAULT 'web' CHECK (registration_source IN ('web', 'mobile', 'api')), -- Источник регистрации
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица активности пользователей
-- Хранит логи действий пользователей (регистрация, вход, добавление в корзину и т.д.)
CREATE TABLE user_activity (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL CHECK (action_type IN ('register', 'login', 'add_to_cart', 'checkout', 'logout')),
    action_details TEXT, -- Дополнительная информация (например, ID товара для add_to_cart)
    action_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица категорий
-- Хранит категории товаров (например, "Красное вино", "Чипсы")
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    type VARCHAR(20) CHECK (type IN ('alcohol', 'snack')) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица брендов
-- Хранит производителей (например, "Талка", "Lays")
CREATE TABLE brands (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица товаров
-- Хранит товары (алкоголь и закуски)
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    brand_id INTEGER NOT NULL REFERENCES brands(id) ON DELETE RESTRICT,
    name VARCHAR(100) NOT NULL,
    volume INTEGER CHECK (volume > 0),
    strength DECIMAL(4,1) CHECK (strength >= 0),
    description TEXT,
    price DECIMAL(10,2) NOT NULL CHECK (price > 0),
    stock INTEGER NOT NULL CHECK (stock >= 0),
    image_url VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица истории цен
CREATE TABLE price_history (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    price DECIMAL(10,2) NOT NULL CHECK (price > 0),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица корзины
CREATE TABLE cart (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица акций
CREATE TABLE promotions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    discount_percent DECIMAL(5,2) CHECK (discount_percent >= 0 AND discount_percent <= 100),
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица связи акций с категориями
CREATE TABLE promotion_categories (
    id SERIAL PRIMARY KEY,
    promotion_id INTEGER NOT NULL REFERENCES promotions(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE
);

-- Таблица заказов
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    total_price DECIMAL(10,2) NOT NULL CHECK (total_price > 0),
    delivery_address TEXT NOT NULL,
    delivery_method VARCHAR(50) NOT NULL CHECK (delivery_method IN ('courier', 'pickup', 'post')),
    delivery_cost DECIMAL(10,2) NOT NULL CHECK (delivery_cost >= 0),
    payment_method VARCHAR(50) NOT NULL CHECK (payment_method IN ('card', 'cash', 'online')),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'shipped', 'delivered', 'canceled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица элементов заказа
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price DECIMAL(10,2) NOT NULL CHECK (price > 0),
    discount_applied DECIMAL(10,2) DEFAULT 0 CHECK (discount_applied >= 0)
);

-- Таблица отзывов
CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Вставка тестовых данных

-- Категории
INSERT INTO categories (name, type) VALUES
('Красное вино', 'alcohol'),
('Белое вино', 'alcohol'),
('Водка', 'alcohol'),
('Пиво', 'alcohol'),
('Коньяк', 'alcohol'),
('Виски', 'alcohol'),
('Чипсы', 'snack'),
('Орешки', 'snack'),
('Сыр', 'snack'),
('Шоколад', 'snack');

-- Бренды
INSERT INTO brands (name, description) VALUES
('Талка', 'Российский производитель водки'),
('Охота', 'Производитель крепкого пива'),
('Киндзмараули', 'Грузинское вино'),
('Lays', 'Производитель чипсов'),
('NutsCo', 'Производитель орешков'),
('Beluga', 'Премиальная российская водка'),
('Heineken', 'Нидерландское пиво'),
('Hennessy', 'Французский коньяк'),
('Jack Daniel''s', 'Американский виски'),
('Baron Otard', 'Французский коньяк'),
('Santa Carolina', 'Чилийское вино'),
('Castello del Poggio', 'Итальянское вино'),
('Pringles', 'Производитель чипсов'),
('Alto', 'Производитель закусок'),
('Milka', 'Производитель шоколада'),
('Johnnie Walker', 'Шотландский виски'),
('Absolut', 'Шведская водка'),
('Camus', 'Французский коньяк'),
('Bavaria', 'Нидерландское пиво'),
('Chivas Regal', 'Шотландский виски');

-- Товары (на основе ассортимента Winelab)
INSERT INTO products (category_id, brand_id, name, volume, strength, description, price, stock, image_url) VALUES
-- Красное вино
(1, 3, 'Киндзмараули', 750, 12.0, 'Красное полусладкое вино из Грузии', 800.00, 50, 'https://example.com/kindzmarauli.jpg'),
(1, 11, 'Santa Carolina Carmenere', 750, 13.5, 'Красное сухое вино из Чили', 650.00, 60, 'https://example.com/santa_carolina.jpg'),
(1, 12, 'Castello del Poggio Rosso', 750, 12.5, 'Красное полусухое вино из Италии', 700.00, 40, 'https://example.com/castello_rosso.jpg'),
(1, 11, 'Santa Carolina Merlot', 750, 13.0, 'Красное сухое вино с фруктовыми нотами', 620.00, 55, 'https://example.com/santa_merlot.jpg'),
(1, 3, 'Мукузани', 750, 13.0, 'Красное сухое вино из Грузии', 900.00, 30, 'https://example.com/mukuzani.jpg'),
-- Белое вино
(2, 11, 'Santa Carolina Sauvignon Blanc', 750, 12.5, 'Белое сухое вино с цитрусовыми нотами', 600.00, 70, 'https://example.com/santa_sauvignon.jpg'),
(2, 12, 'Castello del Poggio Moscato', 750, 7.0, 'Белое полусладкое вино из Италии', 750.00, 45, 'https://example.com/castello_moscato.jpg'),
(2, 11, 'Santa Carolina Chardonnay', 750, 13.0, 'Белое сухое вино с кремовыми нотами', 630.00, 50, 'https://example.com/santa_chardonnay.jpg'),
(2, 12, 'Castello del Poggio Pinot Grigio', 750, 12.0, 'Белое сухое вино с цветочными ароматами', 720.00, 60, 'https://example.com/castello_pinot.jpg'),
-- Водка
(3, 1, 'Талка', 500, 40.0, 'Классическая русская водка', 500.00, 100, 'https://example.com/talka.jpg'),
(3, 6, 'Beluga Noble', 700, 40.0, 'Премиальная водка с мягким вкусом', 2000.00, 30, 'https://example.com/beluga_noble.jpg'),
(3, 17, 'Absolut Blue', 700, 40.0, 'Шведская водка с чистым вкусом', 1500.00, 40, 'https://example.com/absolut_blue.jpg'),
(3, 1, 'Талка Серебряная', 500, 40.0, 'Водка с фильтрацией серебром', 550.00, 80, 'https://example.com/talka_silver.jpg'),
-- Пиво
(4, 2, 'Охота Крепкое', 1000, 8.1, 'Крепкое пиво с насыщенным вкусом', 150.00, 200, 'https://example.com/ohota.jpg'),
(4, 7, 'Heineken', 500, 5.0, 'Светлое пиво премиум-класса', 120.00, 150, 'https://example.com/heineken.jpg'),
(4, 19, 'Bavaria Premium', 500, 5.0, 'Нидерландское светлое пиво', 110.00, 180, 'https://example.com/bavaria.jpg'),
(4, 2, 'Охота Светлое', 1000, 4.7, 'Легкое светлое пиво', 130.00, 160, 'https://example.com/ohota_light.jpg'),
(4, 7, 'Heineken Non-Alcoholic', 500, 0.0, 'Безалкогольное пиво', 100.00, 100, 'https://example.com/heineken_non.jpg'),
-- Коньяк
(5, 8, 'Hennessy VS', 700, 40.0, 'Классический французский коньяк', 3500.00, 25, 'https://example.com/hennessy_vs.jpg'),
(5, 10, 'Baron Otard VSOP', 700, 40.0, 'Коньяк с фруктовыми и ванильными нотами', 4000.00, 20, 'https://example.com/otard_vsop.jpg'),
(5, 18, 'Camus VS Elegance', 700, 40.0, 'Коньяк с мягким цветочным вкусом', 3800.00, 22, 'https://example.com/camus_vs.jpg'),
(5, 8, 'Hennessy VSOP', 700, 40.0, 'Коньяк с насыщенным вкусом', 5000.00, 15, 'https://example.com/hennessy_vsop.jpg'),
-- Виски
(6, 9, 'Jack Daniel''s Old No.7', 700, 40.0, 'Американский виски с карамельными нотами', 2500.00, 35, 'https://example.com/jack_daniels.jpg'),
(6, 16, 'Johnnie Walker Red Label', 700, 40.0, 'Шотландский виски с пряным вкусом', 2000.00, 40, 'https://example.com/johnnie_red.jpg'),
(6, 20, 'Chivas Regal 12', 700, 40.0, 'Шотландский виски с мягким вкусом', 3500.00, 30, 'https://example.com/chivas_12.jpg'),
(6, 9, 'Jack Daniel''s Honey', 700, 35.0, 'Виски с медовыми нотами', 2700.00, 25, 'https://example.com/jack_honey.jpg'),
-- Чипсы
(7, 4, 'Lays Краб', NULL, NULL, 'Чипсы со вкусом краба', 100.00, 150, 'https://example.com/lays_crab.jpg'),
(7, 13, 'Pringles Original', NULL, NULL, 'Чипсы с классическим вкусом', 200.00, 120, 'https://example.com/pringles_original.jpg'),
(7, 4, 'Lays Сметана и Зелень', NULL, NULL, 'Чипсы со вкусом сметаны и зелени', 100.00, 140, 'https://example.com/lays_sour_cream.jpg'),
-- Орешки
(8, 5, 'Арахис NutsCo Соль', NULL, NULL, 'Жареный арахис в соли', 120.00, 80, 'https://example.com/nutsco_salt.jpg'),
(8, 5, 'Миндаль NutsCo Жареный', NULL, NULL, 'Жареный миндаль без соли', 250.00, 60, 'https://example.com/nutsco_almond.jpg'),
-- Сыр
(9, 14, 'Alto Parmesan', NULL, NULL, 'Твердый сыр пармезан', 500.00, 50, 'https://example.com/alto_parmesan.jpg'),
(9, 14, 'Alto Gouda', NULL, NULL, 'Полутвердый сыр гауда', 450.00, 55, 'https://example.com/alto_gouda.jpg'),
-- Шоколад
(10, 15, 'Milka Milk Chocolate', NULL, NULL, 'Молочный шоколад', 150.00, 100, 'https://example.com/milka_milk.jpg'),
(10, 15, 'Milka Hazelnut', NULL, NULL, 'Шоколад с лесным орехом', 160.00, 90, 'https://example.com/milka_hazelnut.jpg');

-- История цен
INSERT INTO price_history (product_id, price, changed_at) VALUES
(1, 800.00, '2025-05-01'), (2, 650.00, '2025-05-01'), (3, 700.00, '2025-05-01'), (4, 620.00, '2025-05-01'),
(5, 900.00, '2025-05-01'), (6, 600.00, '2025-05-01'), (7, 750.00, '2025-05-01'), (8, 630.00, '2025-05-01'),
(9, 720.00, '2025-05-01'), (10, 500.00, '2025-05-01'), (11, 2000.00, '2025-05-01'), (12, 1500.00, '2025-05-01'),
(13, 550.00, '2025-05-01'), (14, 150.00, '2025-05-01'), (15, 120.00, '2025-05-01'), (16, 110.00, '2025-05-01'),
(17, 130.00, '2025-05-01'), (18, 100.00, '2025-05-01'), (19, 3500.00, '2025-05-01'), (20, 4000.00, '2025-05-01'),
(21, 3800.00, '2025-05-01'), (22, 5000.00, '2025-05-01'), (23, 2500.00, '2025-05-01'), (24, 2000.00, '2025-05-01'),
(25, 3500.00, '2025-05-01'), (26, 2700.00, '2025-05-01'), (27, 100.00, '2025-05-01'), (28, 200.00, '2025-05-01'),
(29, 100.00, '2025-05-01'), (30, 120.00, '2025-05-01'), (31, 250.00, '2025-05-01'), (32, 500.00, '2025-05-01'),
(33, 450.00, '2025-05-01'), (34, 150.00, '2025-05-01'), (35, 160.00, '2025-05-01');

-- Пользователи
INSERT INTO users (username, password_hash, email, first_name, last_name, phone, address, role, registered_at, registration_source) VALUES
('ivan123', '$2b$12$examplehash', 'ivan@mail.ru', 'Иван', 'Иванов', '+79991234567', 'Москва, ул. Ленина, 10', 'customer', '2025-05-01 10:00:00', 'web'),
('admin', '$2b$12$L4l0T/BK6LhvE2QK//nGr.ffVSP7oYdY6tqxJ4V7UiXesQXh/Yw3S', 'admin@mail.ru', 'Админ', 'Админов', NULL, NULL, 'admin', '2025-05-01 09:00:00', 'web');

-- Активность пользователей
INSERT INTO user_activity (user_id, action_type, action_details, action_at) VALUES
(1, 'register', 'User registered via web', '2025-05-01 10:00:00'),
(1, 'login', 'User logged in via web', '2025-05-01 10:05:00'),
(1, 'add_to_cart', 'Added product_id: 14 (Охота Крепкое)', '2025-05-01 10:10:00'),
(2, 'register', 'Admin registered via web', '2025-05-01 09:00:00'),
(2, 'login', 'Admin logged in via web', '2025-05-01 09:05:00');

-- Акции
INSERT INTO promotions (name, description, discount_percent, product_id, start_date, end_date) VALUES
('3 пива по цене 2', 'Купи 3 бутылки Охота Крепкое, плати за 2', 33.33, 14, '2025-05-01', '2025-06-01'),
('Скидка на чипсы', 'Скидка на все чипсы', 20.00, NULL, '2025-05-01', '2025-05-15');

-- Связь акций с категориями
INSERT INTO promotion_categories (promotion_id, category_id) VALUES
(2, 7); -- Скидка на чипсы применяется к категории "Чипсы"

-- Триггер для обновления updated_at в таблице orders
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

SELECT * FROM brands;
SELECT * FROM users;
UPDATE users SET role = 'admin' WHERE username = 'super_admin';
SELECT * FROM products;

-- Создаем функцию, которая будет уменьшать stock товаров при вставке записей в order_items
CREATE OR REPLACE FUNCTION decrease_stock_on_order_item()
RETURNS TRIGGER AS $$
BEGIN
    -- Проверяем, достаточно ли товара на складе
    IF (SELECT stock FROM products WHERE id = NEW.product_id) < NEW.quantity THEN
        RAISE EXCEPTION 'Недостаточно товара на складе для product_id = %', NEW.product_id;
    END IF;

    -- Уменьшаем stock товара
    UPDATE products
    SET stock = stock - NEW.quantity
    WHERE id = NEW.product_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Создаем триггер на вставку в order_items
CREATE TRIGGER trg_decrease_stock
AFTER INSERT ON order_items
FOR EACH ROW
EXECUTE FUNCTION decrease_stock_on_order_item();

SELECT o.id as order_id, o.user_id, u.username, u.email, o.total_price, o.delivery_address,
       o.delivery_method, o.delivery_cost, o.payment_method, o.status, o.created_at
FROM orders o
JOIN users u ON o.user_id = u.id
ORDER BY o.created_at DESC

