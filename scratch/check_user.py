import sqlite3
conn = sqlite3.connect('tender_system.db')
cur = conn.cursor()
res = cur.execute('SELECT id FROM users WHERE email="contractor@tender.com"').fetchone()
print(f'Contractor ID: {res[0]}' if res else 'User not found')
conn.close()
