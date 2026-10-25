-- Sample menu. Users and sample orders are created by init_db.py
-- because passwords must be hashed by the application, never typed into SQL.
USE foodease;

INSERT INTO categories (category_name) VALUES
('Pizza'), ('Burger'), ('Beverages'), ('Starters'), ('Desserts');

INSERT INTO food_items (category_id, name, price) VALUES
(1, 'Margherita Pizza',     199.00),
(1, 'Farmhouse Pizza',      279.00),
(1, 'Paneer Tikka Pizza',   299.00),
(2, 'Veg Burger',            99.00),
(2, 'Cheese Burger',        129.00),
(2, 'Crispy Paneer Burger', 149.00),
(3, 'Cold Coffee',           79.00),
(3, 'Masala Chaas',          39.00),
(3, 'Fresh Lime Soda',       59.00),
(4, 'French Fries',          89.00),
(4, 'Garlic Bread',         109.00),
(5, 'Chocolate Brownie',    119.00);
