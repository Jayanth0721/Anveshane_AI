
import sqlite3
import os

db_path = "tender_system.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT role, email FROM users")
    rows = cursor.fetchall()
    print("Role\tEmail")
    for row in rows:
        print(f"{row[0]}\t{row[1]}")
    conn.close()
else:
    print("Database not found")
