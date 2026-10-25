# FoodEase: Online Food Ordering and Restaurant Management

Flask + MySQL + HTML/CSS/JavaScript. Every account, menu item, order, payment and status change is stored in MySQL.

## Run it (MySQL, 5 steps)
1. Install Python 3.10+ and MySQL 8.0.16+.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and put your MySQL password in it.
4. `python init_db.py` creates the database, tables, view, triggers, menu and demo users/orders.
5. `python app.py`, then open http://127.0.0.1:5000

Demo logins: admin `admin@foodease.com` / `Admin@123`, customer `aarav@example.com` / `Customer@123`.
Change these before showing the project to anyone.

No MySQL yet? Set `FOODEASE_DB=sqlite` in `.env` for a quick demo. The real project database is MySQL.

## How the database is connected
`db.py` opens MySQL connections (PyMySQL). `app.py` calls it for every action. All queries are parameterised.
Checkout runs as one transaction (order + items + payment), so a failure rolls everything back.

## DBMS topics, and where they are
| Topic | Where |
|---|---|
| ER design, 3NF | `database/schema.sql`, 7 tables |
| Constraints (PK, FK, UNIQUE, CHECK) | `schema.sql` |
| Joins, aggregates, subqueries, HAVING | `database/queries.sql`, `app.py` reports |
| View | `order_summary` |
| Triggers | `database/triggers.sql`: status-transition rule and audit log |
| Transactions | `create_order()` and `change_status()` in `app.py`; demo H in `queries.sql` |
| Indexes, EXPLAIN | `database/indexes.sql`, `queries.sql` K |
| Security | hashed passwords, roles, `database/security.sql` (least-privilege accounts) |

Changes from the original plan: `customers` also holds `password_hash` and `role` for login; a seventh table, `order_status_history`, stores the audit trail. Order totals are never stored; they are always calculated from `order_items`.

## Pages
Menu `/`, Cart and checkout `/cart`, My orders `/orders`, Admin `/admin` (overview, orders, menu, reports), Login `/login`, Register `/register`.

## Limits to mention in your report
Card/UPI payment is simulated. There is no login rate-limiting. Use HTTPS and a strong `SECRET_KEY` if you ever deploy it.
