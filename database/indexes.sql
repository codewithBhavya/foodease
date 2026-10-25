-- Extra indexes for the columns the app searches and joins on most.
-- Kept separate from schema.sql because CREATE INDEX has no IF NOT EXISTS in MySQL;
-- init_db.py runs this file only when it creates the tables for the first time.
USE foodease;

CREATE INDEX idx_orders_date     ON orders (order_date);
CREATE INDEX idx_orders_status   ON orders (status);
CREATE INDEX idx_payments_order  ON payments (order_id);
CREATE INDEX idx_history_order   ON order_status_history (order_id);

-- Compare query plans before and after:
-- EXPLAIN SELECT * FROM orders WHERE order_date >= '2026-10-01';
