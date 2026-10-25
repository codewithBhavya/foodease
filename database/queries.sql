-- FoodEase: queries for the DBMS viva. Run in MySQL Workbench.
USE foodease;

-- A. JOIN: menu with categories
SELECT f.name, c.category_name, f.price
FROM food_items f JOIN categories c ON f.category_id = c.category_id;

-- B. Aggregate: total of every order
SELECT o.order_id, SUM(oi.quantity * oi.unit_price) AS total_amount
FROM orders o JOIN order_items oi ON o.order_id = oi.order_id
GROUP BY o.order_id;

-- C. GROUP BY + ORDER BY: most popular dishes
SELECT f.name, SUM(oi.quantity) AS units_sold
FROM order_items oi
JOIN food_items f ON oi.food_id = f.food_id
JOIN orders o ON oi.order_id = o.order_id
WHERE o.status <> 'Cancelled'
GROUP BY f.food_id, f.name
ORDER BY units_sold DESC;

-- D. Subquery: customers who have placed orders
SELECT name FROM customers WHERE customer_id IN (SELECT customer_id FROM orders);

-- E. View
SELECT * FROM order_summary;

-- F. HAVING: customers who spent more than 500
SELECT c.name, SUM(oi.quantity * oi.unit_price) AS spent
FROM customers c
JOIN orders o ON o.customer_id = c.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status <> 'Cancelled'
GROUP BY c.customer_id, c.name
HAVING spent > 500;

-- G. LEFT JOIN: dishes never ordered
SELECT f.name FROM food_items f
LEFT JOIN order_items oi ON oi.food_id = f.food_id
WHERE oi.order_item_id IS NULL;

-- H. Transaction (checkout). Change ROLLBACK to COMMIT to keep it.
START TRANSACTION;
INSERT INTO orders (customer_id) VALUES (2);
SET @new_order_id = LAST_INSERT_ID();
INSERT INTO order_items (order_id, food_id, quantity, unit_price) VALUES
    (@new_order_id, 1, 2, 199.00), (@new_order_id, 7, 1, 79.00);
INSERT INTO payments (order_id, amount, method) VALUES (@new_order_id, 477.00, 'UPI');
ROLLBACK;

-- I. Trigger demo: this must FAIL with 'Invalid order status transition'
UPDATE orders SET status = 'Preparing' WHERE status = 'Delivered' LIMIT 1;

-- J. Status audit trail written by the triggers
SELECT * FROM order_status_history ORDER BY history_id;

-- K. Index / query plan
EXPLAIN SELECT * FROM orders WHERE customer_id = 2;
EXPLAIN SELECT * FROM orders WHERE order_date >= '2026-10-01';
