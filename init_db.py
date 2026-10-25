"""Create the FoodEase database, tables, triggers and sample data.

    python init_db.py           create anything missing; add sample data only if the database is empty
    python init_db.py --reset   DROP everything and start again (deletes all data!)
"""
import os
import sys
from datetime import timedelta

from werkzeug.security import generate_password_hash

import config
import db

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database")

DEMO_USERS = [
    # name, email, phone, password, role
    ("FoodEase Admin", "admin@foodease.com", "9000000000", "Admin@123", "admin"),
    ("Aarav Patel", "aarav@example.com", "9876543210", "Customer@123", "customer"),
    ("Diya Shah", "diya@example.com", "9876543211", "Customer@123", "customer"),
]

# (customer email, days ago, status, payment method, [(food name, qty), ...])
DEMO_ORDERS = [
    ("aarav@example.com", 6, "Delivered", "UPI", [("Margherita Pizza", 2), ("Cold Coffee", 1)]),
    ("diya@example.com", 5, "Delivered", "Cash", [("Veg Burger", 2), ("French Fries", 1)]),
    ("aarav@example.com", 4, "Delivered", "Card", [("Paneer Tikka Pizza", 1), ("Fresh Lime Soda", 2)]),
    ("diya@example.com", 3, "Cancelled", "UPI", [("Cheese Burger", 1)]),
    ("aarav@example.com", 2, "Delivered", "UPI", [("Veg Burger", 1), ("Masala Chaas", 2), ("Chocolate Brownie", 1)]),
    ("diya@example.com", 1, "Delivered", "Cash", [("Farmhouse Pizza", 1), ("Garlic Bread", 1)]),
    ("aarav@example.com", 0, "Placed", "UPI", [("Crispy Paneer Burger", 2), ("Cold Coffee", 2)]),
]


def read_statements(path):
    """Split a MySQL script into statements, honouring DELIMITER lines."""
    delimiter, buffer, statements = ";", [], []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped.upper().startswith("DELIMITER "):
                delimiter = stripped.split(None, 1)[1]
                continue
            if not buffer and (not stripped or stripped.startswith("--")):
                continue
            buffer.append(line)
            if stripped.endswith(delimiter):
                text = "".join(buffer).strip()
                statements.append(text[: -len(delimiter)].strip())
                buffer = []
    return [s for s in statements if s]


def run_script(conn, filename):
    path = os.path.join(HERE, filename)
    if db.IS_MYSQL:
        for statement in read_statements(path):
            conn.run(statement)
    else:
        with open(path, encoding="utf-8") as fh:
            lines = [ln for ln in fh if not ln.strip().upper().startswith("USE ")]
        conn.raw.executescript("".join(lines))


def create_structure(reset):
    if db.IS_MYSQL:
        raw = db._connect(with_database=False)
        conn = db.Conn(raw)
        if reset:
            conn.run(f"DROP DATABASE IF EXISTS {config.MYSQL['database']}")
        existed = conn.scalar(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s AND table_name = 'customers'",
            (config.MYSQL["database"],),
        )
        run_script(conn, "schema.sql")
        if not existed:
            run_script(conn, "indexes.sql")
        run_script(conn, "triggers.sql")
        raw.commit()
        raw.close()
    else:
        if reset and os.path.exists(config.SQLITE_PATH):
            os.remove(config.SQLITE_PATH)
        with db.connection() as conn:
            run_script(conn, "schema_sqlite.sql")
            conn.raw.commit()


def seed():
    with db.transaction() as conn:
        if conn.scalar("SELECT COUNT(*) FROM customers"):
            print("Database already has data - sample data skipped (use --reset to start over).")
            return
        for name, email, phone, password, role in DEMO_USERS:
            conn.run(
                "INSERT INTO customers (name, email, phone, password_hash, role) VALUES (%s, %s, %s, %s, %s)",
                (name, email, phone, generate_password_hash(password), role),
            )
        run_script(conn, "sample_data.sql")
        for email, days_ago, status, method, lines in DEMO_ORDERS:
            customer_id = conn.scalar("SELECT customer_id FROM customers WHERE email = %s", (email,))
            order_id = conn.run(
                "INSERT INTO orders (customer_id, order_date, status) VALUES (%s, %s, %s)",
                (customer_id, db.now_string(timedelta(days=days_ago)), status),
            )
            total = 0
            for food_name, qty in lines:
                food = conn.one("SELECT food_id, price FROM food_items WHERE name = %s", (food_name,))
                conn.run(
                    "INSERT INTO order_items (order_id, food_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                    (order_id, food["food_id"], qty, food["price"]),
                )
                total += float(food["price"]) * qty
            if status == "Cancelled":
                pay_status = "Refunded" if method != "Cash" else "Failed"
            elif status == "Delivered" or method != "Cash":
                pay_status = "Paid"
            else:
                pay_status = "Pending"
            conn.run(
                "INSERT INTO payments (order_id, amount, method, status) VALUES (%s, %s, %s, %s)",
                (order_id, round(total, 2), method, pay_status),
            )
    print("Sample data added.")
    print("  Admin    : admin@foodease.com / Admin@123")
    print("  Customer : aarav@example.com / Customer@123")
    print("Change these passwords before showing the project to anyone.")


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    if reset and "--yes" not in sys.argv:
        if input("This deletes ALL FoodEase data. Type YES to continue: ").strip() != "YES":
            sys.exit("Cancelled.")
    create_structure(reset)
    seed()
    where = config.MYSQL["database"] if db.IS_MYSQL else config.SQLITE_PATH
    print(f"Database ready ({config.DB_BACKEND}): {where}")
