ALTER TABLE user_activity DROP CONSTRAINT user_activity_action_type_check;
ALTER TABLE user_activity ADD CONSTRAINT user_activity_action_type_check CHECK (action_type IN ('register', 'login', 'add_to_cart', 'checkout', 'logout', 'clear_cart', 'cancel_order'));

CREATE OR REPLACE VIEW user_orders_count AS
SELECT 
    u.id,
    u.username,
    u.email,
    COUNT(o.id) as total_orders
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.username, u.email;

SELECT * FROM user_orders_count ORDER BY total_orders DESC;

DROP PROCEDURE delete_product;

CREATE OR REPLACE PROCEDURE delete_product(_product_id INT)
LANGUAGE plpgsql
AS $$
BEGIN
    -- Удаляем записи из корзины, где есть этот товар
    DELETE FROM cart WHERE product_id = _product_id;

    -- Удаляем записи из истории цен
    DELETE FROM price_history WHERE product_id = _product_id;

    -- Удаляем записи из отзывов
    DELETE FROM reviews WHERE product_id = _product_id;

    -- Удаляем связи товара с акциями (если такая связь существует напрямую)
    -- DELETE FROM promotion_products WHERE product_id = _product_id;

    -- Удаляем соответствующие строки из order_items
    DELETE FROM order_items WHERE product_id = _product_id;

    -- Удаляем сам товар
    DELETE FROM products WHERE id = _product_id;
END;
$$;

SELECT * FROM products;