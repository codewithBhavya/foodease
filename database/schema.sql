-- FoodEase schema for MySQL 8.0.16+ (CHECK constraints are enforced from 8.0.16).
-- Run in MySQL Workbench, or let `python init_db.py` run it for you.
-- Keep comments on their own lines: init_db.py splits this file into statements.

CREATE DATABASE IF NOT EXISTS foodease CHARACTER SET utf8mb4;
USE foodease;

-- customers also holds the login (password hash + role), so one table serves
-- both customers and restaurant admins.
CREATE TABLE IF NOT EXISTS customers (
    customer_id   INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    phone         VARCHAR(15)  NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(10)  NOT NULL DEFAULT 'customer',
    created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (role IN ('customer', 'admin'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS categories (
    category_id   INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(60) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS food_items (
    food_id      INT AUTO_INCREMENT PRIMARY KEY,
    category_id  INT NOT NULL,
    name         VARCHAR(100) NOT NULL,
    price        DECIMAL(10,2) NOT NULL CHECK (price >= 0),
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
    order_id    INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    order_date  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status      VARCHAR(20) NOT NULL DEFAULT 'Placed',
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    CHECK (status IN ('Placed', 'Preparing', 'Out for Delivery', 'Delivered', 'Cancelled'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id      INT NOT NULL,
    food_id       INT NOT NULL,
    quantity      INT NOT NULL CHECK (quantity > 0),
    unit_price    DECIMAL(10,2) NOT NULL CHECK (unit_price >= 0),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (food_id)  REFERENCES food_items(food_id),
    UNIQUE (order_id, food_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS payments (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id   INT NOT NULL,
    amount     DECIMAL(10,2) NOT NULL CHECK (amount >= 0),
    method     VARCHAR(20) NOT NULL,
    status     VARCHAR(20) NOT NULL DEFAULT 'Pending',
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    CHECK (method IN ('Cash', 'UPI', 'Card')),
    CHECK (status IN ('Pending', 'Paid', 'Failed', 'Refunded'))
) ENGINE=InnoDB;

-- Audit trail: filled automatically by triggers (see triggers.sql).
CREATE TABLE IF NOT EXISTS order_status_history (
    history_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id   INT NOT NULL,
    old_status VARCHAR(20) NULL,
    new_status VARCHAR(20) NOT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
) ENGINE=InnoDB;

-- Order totals are never stored. They are always derived from order_items.
CREATE OR REPLACE VIEW order_summary AS
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
