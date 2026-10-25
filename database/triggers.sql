-- Triggers for MySQL. In MySQL Workbench run the whole file as-is.
-- (DELIMITER lines are understood by Workbench and by init_db.py.)
USE foodease;

DROP TRIGGER IF EXISTS trg_orders_validate_status;
DROP TRIGGER IF EXISTS trg_orders_log_insert;
DROP TRIGGER IF EXISTS trg_orders_log_update;

DELIMITER $$

-- Only allow sensible status changes: a Delivered order can never go back to Preparing.
CREATE TRIGGER trg_orders_validate_status
BEFORE UPDATE ON orders
FOR EACH ROW
BEGIN
    IF NEW.status <> OLD.status THEN
        IF NOT (
            (OLD.status = 'Placed'           AND NEW.status IN ('Preparing', 'Cancelled')) OR
            (OLD.status = 'Preparing'        AND NEW.status IN ('Out for Delivery', 'Cancelled')) OR
            (OLD.status = 'Out for Delivery' AND NEW.status = 'Delivered')
        ) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Invalid order status transition';
        END IF;
    END IF;
END$$

-- Record the first status of every new order.
CREATE TRIGGER trg_orders_log_insert
AFTER INSERT ON orders
FOR EACH ROW
BEGIN
    INSERT INTO order_status_history (order_id, old_status, new_status)
    VALUES (NEW.order_id, NULL, NEW.status);
END$$

-- Record every later status change.
CREATE TRIGGER trg_orders_log_update
AFTER UPDATE ON orders
FOR EACH ROW
BEGIN
    IF NEW.status <> OLD.status THEN
        INSERT INTO order_status_history (order_id, old_status, new_status)
        VALUES (NEW.order_id, OLD.status, NEW.status);
    END IF;
END$$

DELIMITER ;
