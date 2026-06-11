"""
Shared database connection module for emotionGame.

Provides a single source of truth for MySQL connections with
connection pooling via mysql.connector pooling.
"""

import os
from contextlib import contextmanager
from typing import Optional

import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
from dotenv import load_dotenv

load_dotenv()

_pool: Optional[MySQLConnectionPool] = None


def _get_pool() -> MySQLConnectionPool:
    """Lazy-initialize and return the connection pool."""
    global _pool
    if _pool is None:
        # --- debug mode: use local DB when DEBUG_SHORT_RESPONSES is set ---
        _debug = os.getenv("DEBUG_SHORT_RESPONSES")
        if _debug:
            print("[db] DEBUG_SHORT_RESPONSES set - using local DB")
            _user = os.getenv("DB_USER", "root")
            _password = os.getenv("DB_DEBUG_PASSWORD") or os.getenv("DB_PASSWORD", "")
            _database = os.getenv("DB_NAME", "camodb")
            _host = "localhost"
            _port = int(os.getenv("DB_DEBUG_PORT", "3306"))
        else:
            _user = os.getenv("DB_USER", "root")
            _password = os.getenv("DB_PASSWORD", "")
            _database = os.getenv("DB_NAME", "camodb")
            _host = os.getenv("DB_HOST", "localhost")
            _port = int(os.getenv("DB_PORT", "3306"))
        # --- SSL: configure when DB_SSL_CA env var is set ---
        _ssl_ca = os.getenv("DB_SSL_CA")
        _ssl_config: dict = {}
        if _ssl_ca:
            _ssl_config["ssl_ca"] = _ssl_ca
            _ssl_config["ssl_verify_cert"] = os.getenv("DB_SSL_VERIFY_CERT", "true").lower() == "true"
            _ssl_config["ssl_disabled"] = False
        _pool = MySQLConnectionPool(
            pool_name="emotion_game_pool",
            pool_size=5,
            pool_reset_session=True,
            user=_user,
            password=_password,
            database=_database,
            host=_host,
            port=_port,
            **_ssl_config,
        )
    return _pool


def connect() -> mysql.connector.MySQLConnection:
    """Get a connection from the pool."""
    return _get_pool().get_connection()


@contextmanager
def get_cursor(dictionary: bool = False):
    """
    Context manager that yields a (connection, cursor) pair.
    Automatically closes cursor and returns connection to pool on exit.

    Usage:
        with get_cursor(dictionary=True) as (conn, cur):
            cur.execute("SELECT ...")
            rows = cur.fetchall()
    """
    conn = connect()
    try:
        cursor = conn.cursor(dictionary=dictionary)
        yield conn, cursor
    except mysql.connector.Error as err:
        conn.rollback()
        raise
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


@contextmanager
def transactional(dictionary: bool = False):
    """
    Context manager for multi-statement transactions.
    Commits on success, rolls back on error, always closes.

    Usage:
        with transactional(dictionary=True) as (conn, cur):
            cur.execute(...)
            cur.execute(...)
    """
    conn = connect()
    try:
        cursor = conn.cursor(dictionary=dictionary)
        yield conn, cursor
        conn.commit()
    except mysql.connector.Error:
        conn.rollback()
        raise
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
