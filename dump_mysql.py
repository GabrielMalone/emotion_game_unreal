"""Database dump utility — exports camodb schema + data to a .sql file.

Reads credentials from environment variables (same .env as the server).
Usage:
    python dump_mysql.py
    # Writes to ./camodb_dump.sql by default.
    # Override with DUMP_OUTPUT env var.
"""

import os
import datetime
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "camodb")
DB_SSL_CA = os.getenv("DB_SSL_CA", "")

ssl_config = {}
if DB_SSL_CA and os.path.exists(DB_SSL_CA):
    ssl_config = {
        "ssl_ca": DB_SSL_CA,
        "ssl_verify_cert": True,
        "ssl_verify_identity": True,
    }

conn = mysql.connector.connect(
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    charset="utf8mb4",
    use_unicode=True,
    **ssl_config,
)
cur = conn.cursor(buffered=True)

out = []

out.append(f"-- MySQL dump of {DB_NAME}")
out.append(f"-- Generated: {datetime.datetime.now()}")
out.append("SET NAMES utf8mb4;")
out.append("SET FOREIGN_KEY_CHECKS=0;")
out.append("")

cur.execute("SHOW TABLES")
tables = [t[0] for t in cur.fetchall()]

for table in tables:
    cur.execute(f"SHOW CREATE TABLE `{table}`")
    row = cur.fetchone()
    create_sql = row[1]
    out.append(f"DROP TABLE IF EXISTS `{table}`;")
    out.append(create_sql + ";")
    out.append("")

    cur.execute(f"SELECT * FROM `{table}`")
    cols = [d[0] for d in cur.description]
    col_names = ", ".join(f"`{c}`" for c in cols)

    batch = []
    for row in cur:
        vals = []
        for v in row:
            if v is None:
                vals.append("NULL")
            elif isinstance(v, (int, float)):
                vals.append(str(v))
            elif isinstance(v, bytes):
                vals.append("X'" + v.hex() + "'")
            elif isinstance(v, datetime.datetime):
                vals.append(f"'{v.strftime('%Y-%m-%d %H:%M:%S')}'")
            elif isinstance(v, datetime.date):
                vals.append(f"'{v.strftime('%Y-%m-%d')}'")
            else:
                s = str(v).replace("\\", "\\\\").replace("'", "\\'")
                vals.append(f"'{s}'")
        batch.append(f"({', '.join(vals)})")

        if len(batch) >= 100:
            out.append(f"INSERT INTO `{table}` ({col_names}) VALUES")
            out.append(",\n".join(batch) + ";")
            batch = []

    if batch:
        out.append(f"INSERT INTO `{table}` ({col_names}) VALUES")
        out.append(",\n".join(batch) + ";")
    out.append("")

out.append("SET FOREIGN_KEY_CHECKS=1;")

cur.close()
conn.close()

# Write to file (configurable path)
dump_path = os.environ.get(
    "DUMP_OUTPUT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "camodb_dump.sql"),
)
with open(dump_path, "w", encoding="utf-8") as f:
    f.write("\n".join(out))

print(f"Dump written to {dump_path}")
print(f"Size: {os.path.getsize(dump_path)} bytes")
