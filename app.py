"""FoodEase - online food ordering and restaurant management (Flask + MySQL).

Run:  python app.py      then open http://127.0.0.1:5000
"""
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session
from flask.json.provider import DefaultJSONProvider
from werkzeug.security import check_password_hash, generate_password_hash

import config
import db

# --------------------------------------------------------------------------
# Business rules
# --------------------------------------------------------------------------
TRANSITIONS = {
    "Placed": ["Preparing", "Cancelled"],
    "Preparing": ["Out for Delivery", "Cancelled"],
    "Out for Delivery": ["Delivered"],
    "Delivered": [],
    "Cancelled": [],
}
PAYMENT_METHODS = ("UPI", "Card", "Cash")
MAX_QTY_PER_ITEM = 20
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\d{10,15}$")


# --------------------------------------------------------------------------
# App setup
# --------------------------------------------------------------------------
def _json_default(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return DefaultJSONProvider.default(value)


class JSONProvider(DefaultJSONProvider):
    default = staticmethod(_json_default)


app = Flask(__name__)
app.json = JSONProvider(app)
app.config.update(
    SECRET_KEY=config.SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",  # blocks cross-site POSTs (CSRF) for the JSON API
)


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


@app.errorhandler(ApiError)
def handle_api_error(err):
    return jsonify(error=err.message), err.status


@app.errorhandler(db.DatabaseError)
def handle_db_error(err):
    app.logger.exception("Database error: %s", err)
    return jsonify(error="The database could not complete that request. Please try again."), 500


@app.errorhandler(404)
def handle_404(err):
    if request.path.startswith("/api/"):
        return jsonify(error="Not found."), 404
    return render_template("message.html", title="Page not found",
                           text="That page doesn't exist."), 404


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def session_user():
    if "uid" in session:
        return {"id": session["uid"], "name": session["name"], "role": session["role"]}
    return None


@app.context_processor
def inject_user():
    return {"user": session_user()}


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session_user():
            raise ApiError("Please log in first.", 401)
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = session_user()
        if not user:
            raise ApiError("Please log in first.", 401)
        if user["role"] != "admin":
            raise ApiError("Only restaurant admins can do that.", 403)
        return fn(*args, **kwargs)
    return wrapper


def payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Send the request as JSON.")
    return data


def text_field(data, key, label, max_len, required=True):
    value = data.get(key)
    value = value.strip() if isinstance(value, str) else ""
    if required and not value:
        raise ApiError(f"{label} is required.")
    if len(value) > max_len:
        raise ApiError(f"{label} must be {max_len} characters or fewer.")
    return value


def money(value, label="Price"):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ApiError(f"{label} must be a number.")
    if amount < 0 or amount > Decimal("100000"):
        raise ApiError(f"{label} must be between 0 and 100000.")
    return amount


def dec(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def set_session(row):
    session.clear()
    session["uid"], session["name"], session["role"] = row["customer_id"], row["name"], row["role"]


def public_user(row):
    return {"id": row["customer_id"], "name": row["name"], "email": row["email"], "role": row["role"]}


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
@app.get("/")
def page_menu():
    return render_template("menu.html")


@app.get("/cart")
def page_cart():
    return render_template("cart.html")


@app.get("/orders")
def page_orders():
    if not session_user():
        return redirect("/login?next=/orders")
    return render_template("orders.html")


@app.get("/admin")
def page_admin():
    user = session_user()
    if not user:
        return redirect("/login?next=/admin")
    if user["role"] != "admin":
        return render_template("message.html", title="Admins only",
                               text="This page is for restaurant staff."), 403
    return render_template("admin.html")


@app.get("/login")
def page_login():
    return render_template("login.html")


@app.get("/register")
def page_register():
    return render_template("register.html")


# --------------------------------------------------------------------------
# Auth API
# --------------------------------------------------------------------------
@app.post("/api/register")
def api_register():
    data = payload()
    name = text_field(data, "name", "Name", 100)
    email = text_field(data, "email", "Email", 150).lower()
    phone = re.sub(r"[\s\-+]", "", text_field(data, "phone", "Phone number", 20))
    password = data.get("password") if isinstance(data.get("password"), str) else ""
    if not EMAIL_RE.match(email):
        raise ApiError("Enter a valid email address.")
    if not PHONE_RE.match(phone):
        raise ApiError("Enter a phone number with 10 to 15 digits.")
    if len(password) < 8:
        raise ApiError("Password must be at least 8 characters.")

    with db.transaction() as conn:
        if conn.one("SELECT customer_id FROM customers WHERE email = %s", (email,)):
            raise ApiError("An account with this email already exists. Log in instead.", 409)
        try:
            new_id = conn.run(
                "INSERT INTO customers (name, email, phone, password_hash) VALUES (%s, %s, %s, %s)",
                (name, email, phone, generate_password_hash(password)),
            )
        except db.IntegrityError:
            raise ApiError("An account with this email already exists. Log in instead.", 409)
        row = conn.one("SELECT * FROM customers WHERE customer_id = %s", (new_id,))
    set_session(row)
    return jsonify(user=public_user(row)), 201


@app.post("/api/login")
def api_login():
    data = payload()
    email = text_field(data, "email", "Email", 150).lower()
    password = data.get("password") if isinstance(data.get("password"), str) else ""
    with db.connection() as conn:
        row = conn.one("SELECT * FROM customers WHERE email = %s", (email,))
    if not row or not check_password_hash(row["password_hash"], password):
        raise ApiError("Incorrect email or password.", 401)
    set_session(row)
    return jsonify(user=public_user(row))


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def api_me():
    return jsonify(user=session_user())


# --------------------------------------------------------------------------
# Menu API (public read, admin write)
# --------------------------------------------------------------------------
def fetch_menu(conn, q="", category_id=None):
    sql = (
        "SELECT f.food_id, f.name, f.price, f.is_available, c.category_id, c.category_name "
        "FROM food_items f JOIN categories c ON f.category_id = c.category_id WHERE 1 = 1"
    )
    params = []
    if q:
        sql += " AND f.name LIKE %s"
        params.append(f"%{q}%")
    if category_id:
        sql += " AND c.category_id = %s"
        params.append(category_id)
    sql += " ORDER BY c.category_name, f.name"
    items = conn.all(sql, params)
    for item in items:
        item["is_available"] = bool(item["is_available"])
    categories = conn.all(
        "SELECT c.category_id, c.category_name, COUNT(f.food_id) AS item_count "
        "FROM categories c LEFT JOIN food_items f ON f.category_id = c.category_id "
        "GROUP BY c.category_id, c.category_name ORDER BY c.category_name"
    )
    return {"categories": categories, "items": items}


@app.get("/api/menu")
def api_menu():
    q = (request.args.get("q") or "").strip()[:60]
    category_id = request.args.get("category", type=int)
    with db.connection() as conn:
        return jsonify(fetch_menu(conn, q, category_id))


def read_food(data):
    name = text_field(data, "name", "Item name", 100)
    price = money(data.get("price"))
    try:
        category_id = int(data.get("category_id"))
    except (TypeError, ValueError):
        raise ApiError("Choose a category.")
    return name, price, category_id, 1 if data.get("is_available", True) else 0


@app.post("/api/admin/foods")
@admin_required
def api_food_create():
    name, price, category_id, available = read_food(payload())
    with db.transaction() as conn:
        if not conn.one("SELECT category_id FROM categories WHERE category_id = %s", (category_id,)):
            raise ApiError("That category doesn't exist.")
        new_id = conn.run(
            "INSERT INTO food_items (category_id, name, price, is_available) VALUES (%s, %s, %s, %s)",
            (category_id, name, price, available),
        )
    return jsonify(food_id=new_id), 201


@app.put("/api/admin/foods/<int:food_id>")
@admin_required
def api_food_update(food_id):
    name, price, category_id, available = read_food(payload())
    with db.transaction() as conn:
        if not conn.one("SELECT food_id FROM food_items WHERE food_id = %s", (food_id,)):
            raise ApiError("Menu item not found.", 404)
        if not conn.one("SELECT category_id FROM categories WHERE category_id = %s", (category_id,)):
            raise ApiError("That category doesn't exist.")
        conn.run(
            "UPDATE food_items SET name = %s, price = %s, category_id = %s, is_available = %s WHERE food_id = %s",
            (name, price, category_id, available, food_id),
        )
    return jsonify(ok=True)


@app.delete("/api/admin/foods/<int:food_id>")
@admin_required
def api_food_delete(food_id):
    with db.transaction() as conn:
        if conn.scalar("SELECT COUNT(*) FROM order_items WHERE food_id = %s", (food_id,)):
            raise ApiError("This item appears in past orders, so it can't be deleted. "
                           "Mark it unavailable instead.", 409)
        conn.run("DELETE FROM food_items WHERE food_id = %s", (food_id,))
    return jsonify(ok=True)


@app.post("/api/admin/categories")
@admin_required
def api_category_create():
    name = text_field(payload(), "category_name", "Category name", 60)
    with db.transaction() as conn:
        if conn.one("SELECT category_id FROM categories WHERE category_name = %s", (name,)):
            raise ApiError("That category already exists.", 409)
        new_id = conn.run("INSERT INTO categories (category_name) VALUES (%s)", (name,))
    return jsonify(category_id=new_id), 201


# --------------------------------------------------------------------------
# Orders
# --------------------------------------------------------------------------
ORDER_SELECT = (
    "SELECT s.order_id, s.customer_id, s.customer_name, s.order_date, s.status, s.total_amount, "
    "(SELECT p.method FROM payments p WHERE p.order_id = s.order_id ORDER BY p.payment_id DESC LIMIT 1) AS payment_method, "
    "(SELECT p.status FROM payments p WHERE p.order_id = s.order_id ORDER BY p.payment_id DESC LIMIT 1) AS payment_status "
    "FROM order_summary s"
)


def attach_details(conn, orders):
    """Add line items, status history and the allowed next statuses to each order."""
    if not orders:
        return orders
    ids = [o["order_id"] for o in orders]
    marks = ",".join(["%s"] * len(ids))
    items = conn.all(
        "SELECT oi.order_id, f.name, oi.quantity, oi.unit_price "
        "FROM order_items oi JOIN food_items f ON f.food_id = oi.food_id "
        f"WHERE oi.order_id IN ({marks}) ORDER BY oi.order_item_id", ids)
    history = conn.all(
        "SELECT order_id, old_status, new_status, changed_at FROM order_status_history "
        f"WHERE order_id IN ({marks}) ORDER BY history_id", ids)
    for order in orders:
        order["items"] = [i for i in items if i["order_id"] == order["order_id"]]
        order["history"] = [h for h in history if h["order_id"] == order["order_id"]]
        order["next"] = TRANSITIONS.get(order["status"], [])
    return orders


def create_order(customer_id, requested, method):
    """Place an order inside one transaction: order + items + payment, or nothing."""
    quantities = {}
    for line in requested:
        if not isinstance(line, dict):
            raise ApiError("Your cart has an invalid item.")
        try:
            food_id, qty = int(line.get("food_id")), int(line.get("quantity"))
        except (TypeError, ValueError):
            raise ApiError("Your cart has an invalid item.")
        if qty < 1 or qty > MAX_QTY_PER_ITEM:
            raise ApiError(f"You can order 1 to {MAX_QTY_PER_ITEM} of each item.")
        quantities[food_id] = quantities.get(food_id, 0) + qty
    if not quantities:
        raise ApiError("Your cart is empty.")
    if any(q > MAX_QTY_PER_ITEM for q in quantities.values()):
        raise ApiError(f"You can order 1 to {MAX_QTY_PER_ITEM} of each item.")
    if method not in PAYMENT_METHODS:
        raise ApiError("Choose a payment method.")

    with db.transaction() as conn:
        ids = list(quantities)
        marks = ",".join(["%s"] * len(ids))
        rows = conn.all(
            f"SELECT food_id, name, price, is_available FROM food_items WHERE food_id IN ({marks}){db.FOR_UPDATE}",
            ids)
        found = {r["food_id"]: r for r in rows}
        for food_id in ids:
            row = found.get(food_id)
            if not row:
                raise ApiError("An item in your cart is no longer on the menu. Remove it and try again.", 409)
            if not row["is_available"]:
                raise ApiError(f"{row['name']} is sold out right now. Remove it and try again.", 409)

        order_id = conn.run("INSERT INTO orders (customer_id) VALUES (%s)", (customer_id,))
        total = Decimal("0.00")
        for food_id, qty in quantities.items():
            unit_price = dec(found[food_id]["price"])  # price comes from the database, never the browser
            conn.run(
                "INSERT INTO order_items (order_id, food_id, quantity, unit_price) VALUES (%s, %s, %s, %s)",
                (order_id, food_id, qty, unit_price))
            total += unit_price * qty
        # Card/UPI are marked paid at once because there is no real payment gateway in this project.
        conn.run(
            "INSERT INTO payments (order_id, amount, method, status) VALUES (%s, %s, %s, %s)",
            (order_id, total, method, "Pending" if method == "Cash" else "Paid"))
    return order_id, total


def change_status(order_id, new_status, customer_id=None):
    """Move an order to a new status. If customer_id is given, the caller is a customer cancelling."""
    with db.transaction() as conn:
        order = conn.one(
            "SELECT order_id, customer_id, status FROM orders WHERE order_id = %s" + db.FOR_UPDATE, (order_id,))
        if not order or (customer_id is not None and order["customer_id"] != customer_id):
            raise ApiError("Order not found.", 404)
        if customer_id is not None and not (order["status"] == "Placed" and new_status == "Cancelled"):
            raise ApiError("You can only cancel an order before the kitchen starts preparing it.", 409)
        if new_status not in TRANSITIONS.get(order["status"], []):
            raise ApiError(f"An order that is {order['status']} can't be changed to {new_status}.", 409)

        conn.run("UPDATE orders SET status = %s WHERE order_id = %s", (new_status, order_id))
        if new_status == "Cancelled":
            conn.run("UPDATE payments SET status = 'Refunded' WHERE order_id = %s AND status = 'Paid'", (order_id,))
            conn.run("UPDATE payments SET status = 'Failed' WHERE order_id = %s AND status = 'Pending'", (order_id,))
        elif new_status == "Delivered":
            conn.run("UPDATE payments SET status = 'Paid' WHERE order_id = %s AND status = 'Pending'", (order_id,))


@app.post("/api/orders")
@login_required
def api_order_create():
    data = payload()
    items = data.get("items")
    if not isinstance(items, list):
        raise ApiError("Your cart is empty.")
    order_id, total = create_order(session["uid"], items, data.get("method"))
    return jsonify(order_id=order_id, total=total), 201


@app.get("/api/orders")
@login_required
def api_orders_mine():
    with db.connection() as conn:
        orders = conn.all(ORDER_SELECT + " WHERE s.customer_id = %s ORDER BY s.order_id DESC", (session["uid"],))
        return jsonify(orders=attach_details(conn, orders))


@app.post("/api/orders/<int:order_id>/cancel")
@login_required
def api_order_cancel(order_id):
    change_status(order_id, "Cancelled", customer_id=session["uid"])
    return jsonify(ok=True)


# --------------------------------------------------------------------------
# Admin API
# --------------------------------------------------------------------------
@app.get("/api/admin/orders")
@admin_required
def api_admin_orders():
    status = request.args.get("status", "")
    sql = ORDER_SELECT.replace("FROM order_summary s",
                               ", c.phone AS customer_phone FROM order_summary s "
                               "JOIN customers c ON c.customer_id = s.customer_id")
    params = []
    if status:
        if status not in TRANSITIONS:
            raise ApiError("Unknown status.")
        sql += " WHERE s.status = %s"
        params.append(status)
    sql += " ORDER BY s.order_id DESC LIMIT 100"
    with db.connection() as conn:
        return jsonify(orders=attach_details(conn, conn.all(sql, params)))


@app.patch("/api/admin/orders/<int:order_id>/status")
@admin_required
def api_admin_order_status(order_id):
    status = payload().get("status")
    if status not in TRANSITIONS:
        raise ApiError("Unknown status.")
    change_status(order_id, status)
    return jsonify(ok=True)


@app.get("/api/admin/menu")
@admin_required
def api_admin_menu():
    with db.connection() as conn:
        return jsonify(fetch_menu(conn))


@app.get("/api/admin/reports")
@admin_required
def api_admin_reports():
    live = "o.status <> 'Cancelled'"
    start = date.today() - timedelta(days=6)
    with db.connection() as conn:
        stats = {
            "revenue": conn.scalar(
                "SELECT COALESCE(SUM(oi.quantity * oi.unit_price), 0) FROM order_items oi "
                f"JOIN orders o ON o.order_id = oi.order_id WHERE {live}"),
            "orders_total": conn.scalar("SELECT COUNT(*) FROM orders"),
            "orders_active": conn.scalar(
                "SELECT COUNT(*) FROM orders WHERE status IN ('Placed', 'Preparing', 'Out for Delivery')"),
            "customers": conn.scalar("SELECT COUNT(*) FROM customers WHERE role = 'customer'"),
        }
        daily = conn.all(
            "SELECT DATE(o.order_date) AS sale_day, COUNT(DISTINCT o.order_id) AS orders, "
            "SUM(oi.quantity * oi.unit_price) AS revenue "
            "FROM orders o JOIN order_items oi ON oi.order_id = o.order_id "
            f"WHERE {live} AND o.order_date >= %s GROUP BY DATE(o.order_date) ORDER BY sale_day",
            (start.isoformat() + " 00:00:00",))
        by_day = {str(r["sale_day"]): r for r in daily}
        last7 = []
        for offset in range(7):
            day = (start + timedelta(days=offset)).isoformat()
            row = by_day.get(day)
            last7.append({"day": day, "orders": row["orders"] if row else 0,
                          "revenue": row["revenue"] if row else 0})
        popular = conn.all(
            "SELECT f.name, SUM(oi.quantity) AS units_sold, SUM(oi.quantity * oi.unit_price) AS revenue "
            "FROM order_items oi JOIN food_items f ON oi.food_id = f.food_id "
            f"JOIN orders o ON oi.order_id = o.order_id WHERE {live} "
            "GROUP BY f.food_id, f.name ORDER BY units_sold DESC, f.name LIMIT 8")
        by_category = conn.all(
            "SELECT c.category_name, SUM(oi.quantity) AS units_sold, SUM(oi.quantity * oi.unit_price) AS revenue "
            "FROM order_items oi JOIN food_items f ON oi.food_id = f.food_id "
            "JOIN categories c ON f.category_id = c.category_id "
            f"JOIN orders o ON oi.order_id = o.order_id WHERE {live} "
            "GROUP BY c.category_id, c.category_name ORDER BY revenue DESC")
        top_customers = conn.all(
            "SELECT c.name, COUNT(DISTINCT o.order_id) AS orders, SUM(oi.quantity * oi.unit_price) AS spent "
            "FROM customers c JOIN orders o ON o.customer_id = c.customer_id "
            f"JOIN order_items oi ON oi.order_id = o.order_id WHERE {live} "
            "GROUP BY c.customer_id, c.name ORDER BY spent DESC LIMIT 5")
    return jsonify(stats=stats, last7=last7, popular=popular,
                   by_category=by_category, top_customers=top_customers)


if __name__ == "__main__":
    app.run(debug=True)