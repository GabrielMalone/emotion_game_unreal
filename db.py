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
        _pool = MySQLConnectionPool(
            pool_name="emotion_game_pool",
            pool_size=5,
            pool_reset_session=True,
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            host=os.getenv("DB_HOST", "localhost"),
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
def transactional():
    """
    Context manager for multi-statement transactions.
    Commits on success, rolls back on error, always closes.

    Usage:
        with transactional() as (conn, cur):
            cur.execute(...)
            cur.execute(...)
    """
    conn = connect()
    try:
        cursor = conn.cursor()
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
