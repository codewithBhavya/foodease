-- Quick-start fallback only (FOODEASE_DB=sqlite). The real project database is MySQL: see schema.sql.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    customer_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name          VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    phone         VARCHAR(15)  NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(10)  NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'admin')),
    created_at    TIMESTAMP    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS categories (
    category_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name VARCHAR(60) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS food_items (
    food_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id  INTEGER NOT NULL REFERENCES categories(category_id),
    name         VARCHAR(100) NOT NULL,
    price        DECIMAL(10,2) NOT NULL CHECK (price >= 0),
    is_available BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
    order_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date  TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime')),
    status      VARCHAR(20) NOT NULL DEFAULT 'Placed'
        CHECK (status IN ('Placed', 'Preparing', 'Out for Delivery', 'Delivered', 'Cancelled'))
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id),
    food_id       INTEGER NOT NULL REFERENCES food_items(food_id),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    unit_price    DECIMAL(10,2) NOT NULL CHECK (unit_price >= 0),
    UNIQUE (order_id, food_id)
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(order_id),
    amount     DECIMAL(10,2) NOT NULL CHECK (amount >= 0),
    method     VARCHAR(20) NOT NULL CHECK (method IN ('Cash', 'UPI', 'Card')),
    status     VARCHAR(20) NOT NULL DEFAULT 'Pending'
        CHECK (status IN ('Pending', 'Paid', 'Failed', 'Refunded'))
);

CREATE TABLE IF NOT EXISTS order_status_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(order_id),
    old_status VARCHAR(20),
    new_status VARCHAR(20) NOT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_date     ON orders (order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status   ON orders (status);
CREATE INDEX IF NOT EXISTS idx_food_category   ON food_items (category_id);
CREATE INDEX IF NOT EXISTS idx_payments_order  ON payments (order_id);
CREATE INDEX IF NOT EXISTS idx_history_order   ON order_status_history (order_id);

DROP VIEW IF EXISTS order_summary;
CREATE VIEW order_summary AS
SELECT o.order_id,
       o.customer_id,
       c.name AS customer_name,
       o.order_date,
       o.status,
       COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total_amount
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
LEFT JOIN order_items oi ON o.order_id = oi.order_id
GROUP BY o.order_id, o.customer_id, c.name, o.order_date, o.status;

DROP TRIGGER IF EXISTS trg_orders_validate_status;
CREATE TRIGGER trg_orders_validate_status
BEFORE UPDATE OF status ON orders
FOR EACH ROW
WHEN NEW.status <> OLD.status AND NOT (
    (OLD.status = 'Placed'           AND NEW.status IN ('Preparing', 'Cancelled')) OR
    (OLD.status = 'Preparing'        AND NEW.status IN ('Out for Delivery', 'Cancelled')) OR
    (OLD.status = 'Out for Delivery' AND NEW.status = 'Delivered')
)
BEGIN
    SELECT RAISE(ABORT, 'Invalid order status transition');
END;

DROP TRIGGER IF EXISTS trg_orders_log_insert;
CREATE TRIGGER trg_orders_log_insert
AFTER INSERT ON orders
FOR EACH ROW
BEGIN
    INSERT INTO order_status_history (order_id, old_status, new_status)
    VALUES (NEW.order_id, NULL, NEW.status);
END;

DROP TRIGGER IF EXISTS trg_orders_log_update;
CREATE TRIGGER trg_orders_log_update
AFTER UPDATE OF status ON orders
FOR EACH ROW
WHEN NEW.status <> OLD.status
BEGIN
    INSERT INTO order_status_history (order_id, old_status, new_status)
    VALUES (NEW.order_id, OLD.status, NEW.status);
END;
