import mysql.connector
import datetime
import os

conn = mysql.connector.connect(
    host='localhost', user='root', password='4119',
    database='camodb', charset='utf8mb4', use_unicode=True
)
cur = conn.cursor(buffered=True)

out = []

out.append("-- MySQL dump of camodb")
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

# Write to file
dump_path = r"F:\emotion_game_unreal\camodb_dump.sql"
with open(dump_path, "w", encoding="utf-8") as f:
    f.write("\n".join(out))

print(f"Dump written to {dump_path}")
print(f"Size: {os.path.getsize(dump_path)} bytes")
