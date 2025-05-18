SELECT o.user_id, oi.product_id, oi.quantity, o.created_at,
       p.category_id, p.brand_id, p.volume, p.strength,
       p.price, p.name as product_name,
       c.name as category_name,
       b.name as brand_name
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
JOIN products p ON oi.product_id = p.id
JOIN categories c ON p.category_id = c.id
JOIN brands b ON p.brand_id = b.id
WHERE o.status = 'completed'
ORDER BY o.created_at
LIMIT 5;

SELECT o.user_id, oi.product_id, oi.quantity, o.created_at
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
LIMIT 5;

CREATE TABLE cart_items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL,
    price DECIMAL(10, 2) NOT NULL, -- Цена товара в момент добавления в корзину
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, product_id) -- У пользователя может быть только одна запись для каждого товара в корзине
);

ALTER TABLE promotions
ADD COLUMN category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL;

DROP TABLE cart_items;

ALTER TABLE promotions
DROP COLUMN category_id;

UPDATE promotions 
SET discount_percent = 66.67 
WHERE name = '3 пива по цене 2' AND product_id = 14;

ALTER TABLE user_activity DROP CONSTRAINT user_activity_action_type_check;

ALTER TABLE user_activity ADD CONSTRAINT user_activity_action_type_check CHECK (action_type IN ('register', 'login', 'add_to_cart', 'checkout', 'logout', 'clear_cart'));