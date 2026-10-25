"""Database layer.

All SQL in the project is written once, with %s placeholders, and runs on
MySQL (PyMySQL). A SQLite fallback exists only so the app can be tried
without installing MySQL; set FOODEASE_DB=sqlite to use it.

Every query is parameterised, so user input never becomes part of the SQL text.
"""
import datetime
import decimal
import sqlite3
from contextlib import contextmanager

import config

IS_MYSQL = config.DB_BACKEND == "mysql"

if IS_MYSQL:
    import pymysql
    import pymysql.cursors

    IntegrityError = pymysql.err.IntegrityError
    DatabaseError = pymysql.MySQLError
else:
    IntegrityError = sqlite3.IntegrityError
    DatabaseError = sqlite3.Error

# Row locking so two customers cannot change the same order at once.
FOR_UPDATE = " FOR UPDATE" if IS_MYSQL else ""


def _connect(with_database=True):
    if IS_MYSQL:
        settings = dict(config.MYSQL)
        if not with_database:
            settings.pop("database")
        return pymysql.connect(
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
            **settings,
        )
    conn = sqlite3.connect(config.SQLITE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row(row):
    data = dict(row)
    if not IS_MYSQL:  # SQLite sums floats; keep money at 2 decimals
        for key, value in data.items():
            if isinstance(value, float):
                data[key] = round(value, 2)
    return data


class Conn:
    """Small wrapper so the rest of the code does not care which engine is used."""

    def __init__(self, raw):
        self.raw = raw

    def _execute(self, sql, params):
        cur = self.raw.cursor()
        if IS_MYSQL:
            cur.execute(sql, tuple(params))
        else:  # SQLite cannot bind Decimal values
            values = tuple(float(p) if isinstance(p, decimal.Decimal) else p for p in params)
            cur.execute(sql.replace("%s", "?"), values)
        return cur

    def all(self, sql, params=()):
        cur = self._execute(sql, params)
        rows = [_row(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def one(self, sql, params=()):
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql, params=()):
        row = self.one(sql, params)
        return next(iter(row.values())) if row else None

    def run(self, sql, params=()):
        """Run INSERT/UPDATE/DELETE. Returns the new auto-increment id (if any)."""
        cur = self._execute(sql, params)
        new_id = cur.lastrowid
        cur.close()
        return new_id


@contextmanager
def connection():
    conn = Conn(_connect())
    try:
        yield conn
    finally:
        conn.raw.close()


@contextmanager
def transaction():
    """START TRANSACTION ... COMMIT, or ROLLBACK if anything inside fails."""
    with connection() as conn:
        try:
            yield conn
            conn.raw.commit()
        except Exception:
            conn.raw.rollback()
            raise


def now_string(delta=None):
    moment = datetime.datetime.now() - (delta or datetime.timedelta())
    return moment.strftime("%Y-%m-%d %H:%M:%S")
