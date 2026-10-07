"""
MySQL connection configuration.

All settings are read from environment variables (optionally loaded
from a local `.env` file) so credentials never need to be hardcoded.
Sensible localhost defaults are provided so the app still runs
out-of-the-box against a local MySQL server with default XAMPP/Homebrew
style settings (root user, no password).

Environment variables:
    MYSQL_HOST      (default: localhost)
    MYSQL_PORT      (default: 3306)
    MYSQL_USER      (default: root)
    MYSQL_PASSWORD  (default: "")
    MYSQL_DATABASE  (default: placement_analyzer)
"""

import os

try:
    # Optional: if python-dotenv is installed and a .env file is present,
    # load it. This is not required -- plain environment variables work too.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = _get_int("MYSQL_PORT", 3306)
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "placement_analyzer")

# Passed to pymysql.connect(**DB_CONFIG). Deliberately excludes `database`
# so callers that need to CREATE DATABASE IF NOT EXISTS first (see
# database.py: _ensure_database_exists) can connect without selecting a
# database that may not exist yet.
DB_CONFIG = {
    "host": MYSQL_HOST,
    "port": MYSQL_PORT,
    "user": MYSQL_USER,
    "password": MYSQL_PASSWORD,
    "charset": "utf8mb4",
    "autocommit": False,
}
