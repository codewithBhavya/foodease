"""Configuration. Values come from environment variables or a local .env file."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(os.path.join(BASE_DIR, ".env"))

# "mysql" is the main database. "sqlite" is only a quick-start fallback.
DB_BACKEND = os.getenv("FOODEASE_DB", "mysql").lower()

MYSQL = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "foodease"),
}

SQLITE_PATH = os.getenv("SQLITE_PATH", os.path.join(BASE_DIR, "foodease.db"))
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
